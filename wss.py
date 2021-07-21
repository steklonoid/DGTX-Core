from threading import Thread
import bcrypt   #pip install bcrypt
import websocket
import json
import time
import logging
import websockets
import asyncio
from threading import Lock

PSW = 'asd'

class WSSServer(Thread):

    connections = {}
    managers = {}
    rockets = {}

    def __init__(self, pc):
        super(WSSServer, self).__init__()
        self.pc = pc

    def run(self) -> None:

        async def register(websocket):
            self.connections[websocket] = {'id':int(time.time()*10000000), 'ts':time.time(), 'type':'wait'}

        async def unregister(websocket):
            self.connections.pop(websocket, None)
            if self.managers.get(websocket):
                self.managers.pop(websocket, None)
                await managers_changed()
            if self.rockets.get(websocket):
                self.rockets.pop(websocket, None)
                await rockets_changed()

#   ====================================================================================================================
        async def pilotinfo(websocket, pilot):
            pilots = self.pc.pilots
            pilot_data = {pilot:{'name':pilots[pilot]['name'], 'status':pilots[pilot]['status'], 'info':pilots[pilot]['info']}}
            data = {'message_type': 'cm', 'data': {'command': 'cm_pilotinfo', 'pilot': pilot_data}}
            data = json.dumps(data)
            await asyncio.wait([websocket.send(data)])
    #   ----------------------------------------------------------------------------------------------------------------
        async def rocketinfo(websocket):
            rockets_data = {self.connections[k]['id']:{'version':v['version'], 'status':v['status']} for k,v in self.rockets.items()}
            data = {'message_type':'cm', 'data':{'command':'cm_rocketinfo', 'rockets':rockets_data}}
            data = json.dumps(data)
            await asyncio.wait([websocket.send(data)])

        async def managersinfo(websocket):
            managers_data = [v['user'] for v in self.managers.values()]
            data = {'message_type':'cm', 'data':{'command':'cm_managersinfo', 'managers':managers_data}}
            data = json.dumps(data)
            await asyncio.wait([websocket.send(data)])

        async def pilotsinfo(websocket):
            for pilot in self.pc.pilots.keys():
                await pilotinfo(websocket, pilot)

        #   ----------------------------------------------------------------------------------------------------------------
        async def rockets_changed():
            for websocket in self.managers.keys():
                await rocketinfo(websocket)

        async def add_rocket(websocket, data):
            if not self.rockets.get(websocket):
                psw = data.get('psw')
                if bcrypt.checkpw(psw.encode('utf-8'), self.pc.hashpsw['rocket'].encode('utf-8')):
                    self.rockets[websocket] = {'ts':time.time(), 'version':data['version'], 'status':0, 'pilot':None, 'parameters':{}, 'info':{}}
                    self.connections[websocket]['type'] = 'rocket'
                    str = {'message_type':'registration', 'data':{'status':'ok'}}
                    await rocket_changed()
                else:
                    str = {'message_type': 'registration', 'data': {'status': 'error', 'message': 'Неверный пароль'}}
            else:
                str = {'message_type': 'registration', 'data': {'status': 'error', 'message':'Есть уже такая ракета'}}
            str = json.dumps(str)
            await asyncio.wait([websocket.send(str)])

        async def managers_changed():
            for websocket in self.managers.keys():
                await managersinfo(websocket)

        async def add_manager(websocket, data):
            if not self.managers.get(websocket):
                psw = data.get('psw')
                if bcrypt.checkpw(psw.encode('utf-8'), self.pc.hashpsw['manager'].encode('utf-8')):
                    self.pc.hashpsw['psw'] = psw
                    self.managers[websocket] = {'ts': time.time(), 'user':data['user']}
                    self.connections[websocket]['type'] = 'manager'
                    str = {'message_type':'registration', 'data':{'status':'ok'}}
                    await managers_changed()
                else:
                    str = {'message_type': 'registration', 'data': {'status': 'error', 'message': 'Неверный пароль'}}
            else:
                str = {'message_type': 'registration', 'data': {'status': 'error', 'message':'Есть уже такой менеджер'}}
            str = json.dumps(str)
            await asyncio.wait([websocket.send(str)])

        #   ----------------------------------------------------------------------------------------------------------------
        async def bc_authpilot(pilot):
            self.pc.pilots[pilot]['status'] = 2

        async def bc_raceinfo():
            pass
        #   ----------------------------------------------------------------------------------------------------------------

        async def mc_authpilot(pilot, rocket):
            websocket_rocket = [k for k,v in self.connections.items() if v['id'] == rocket][0]
            ak = self.pc.pilots[pilot]['ak']
            data = {'message_type': 'cb', 'data': {'command': 'authpilot', 'pilot': pilot, 'ak':ak}}
            data = json.dumps(data)
            await asyncio.wait([websocket_rocket.send(data)])

        async def mc_setparameters(rocket, parameters):
            data = {'message_type': 'cb', 'data': {'command': 'cb_setparameters', 'parameters': parameters}}
            data = json.dumps(data)
            await asyncio.wait([rocket.send(data)])

        #   ----------------------------------------------------------------------------------------------------------------

        async def mainroutine(websocket, path):
            await register(websocket)
            try:
                async for message in websocket:
                    mes = json.loads(message)
                    print(mes)
                    message_type = mes.get('message_type')
                    data = mes.get('data')
                    if message_type == 'registration':
                        typereg = data.get('typereg')
                        if typereg == 'rocket':
                            await add_rocket(websocket, data)
                        elif typereg == 'manager':
                            await add_manager(websocket, data)
                        else:
                            pass
                    elif message_type == 'mc':
                        if self.managers.get(websocket):
                            command = data.get('command')
                            if command == 'mc_authpilot':
                                pilot = data.get('pilot')
                                rocket = int(data.get('rocket'))
                                await mc_authpilot(pilot, rocket)
                            elif command == 'mc_setparameters':
                                parameters = data.get('parameters')
                                rocket = int(data.get('rocket'))
                                await mc_setparameters(rocket, parameters)
                            else:
                                pass
                        else:
                            pass
                    elif message_type == 'bc':
                        if self.rockets.get(websocket):
                            command = data.get('command')
                            if command == 'bc_authpilot':
                                status = data.get('status')
                                if status == 'ok':
                                    pilot = data.get('pilot')
                                    await bc_authpilot(pilot)
                            elif command == 'bc_raceinfo':
                                parameters = data.get('parameters')
                                info = data.get('info')
                                # await bc_raceinfo(websocket, parameters, info)
                            else:
                                pass
                        else:
                            pass
                    else:
                        pass
            finally:
                await unregister(websocket)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        start_server = websockets.serve(mainroutine, "localhost", 6789)
        loop.run_until_complete(start_server)
        loop.run_forever()


#   получает цены по инсрументу
class DGTXIndex(Thread):

    def __init__(self, pc, ex):
        super(DGTXIndex, self).__init__()
        self.pc = pc
        self.ex = ex
        self.flClosing = False

    def run(self) -> None:
        def on_open(wsapp):
            logging.info(self.ex + ' ' + 'Соединение с DGTX установлено')
            self.send_public('subscribe', self.ex + '@index')

        def on_close(wsapp, close_status_code, close_msg):
            logging.info(self.ex + ' close / ' + str(close_status_code) + ' / ' + str(close_msg))

        def on_error(wsapp, error):
            logging.info(self.ex + ' ' + 'Ошибка соединения с DGTX')
            time.sleep(1)

        def on_message(wssapp, message):
            if message == 'ping':
                wssapp.send('pong')
            else:
                mes = json.loads(message)
                status = mes.get('status')
                ch = mes.get('ch')
                if ch:
                    if ch == 'index':
                        pass
                elif status:
                    if status == 'error':
                        logging.info(self.message)

        while not self.flClosing:
            try:
                self.wsapp = websocket.WebSocketApp("wss://ws.mapi.digitexfutures.com", on_open=on_open,
                                                    on_close=on_close, on_error=on_error, on_message=on_message)
                self.wsapp.run_forever()
            except:
                pass
            finally:
                time.sleep(1)

    def send_public(self, method, *params):
        pd = {'id':1, 'method':method}
        if params:
            pd['params'] = list(params)
        strpar = json.dumps(pd)
        self.wsapp.send(strpar)

#   получает инфу пилота
class DGTXBalance(Thread):

    lock = Lock()

    def __init__(self, pc, pilot, ak, expanses):
        super(DGTXBalance, self).__init__()
        self.pc = pc
        self.pilot = pilot
        self.ak = ak
        self.expanses = expanses
        self.flClosing = False

    def run(self) -> None:
        def on_open(wsapp):
            logging.info(self.pilot + ' Соединение с DGTX установлено')
            self.send_privat('auth', type='token', value=self.ak)

        def on_close(wsapp, close_status_code, close_msg):
            logging.info(self.pilot + ' close / ' + str(close_status_code) + ' / ' + str(close_msg))

        def on_error(wsapp, error):
            logging.info(self.pilot + ' Ошибка соединения с DGTX')
            time.sleep(1)

        def on_message(wssapp, message):
            # print(message)
            if message == 'ping':
                wssapp.send('pong')
            else:
                mes = json.loads(message)
                status = mes.get('status')
                ch = mes.get('ch')
                if ch == 'tradingStatus':
                    data = mes.get('data')
                    available = data.get('available')
                    if available:
                        self.lock.acquire()
                        self.pc.pilots[self.pilot]['status'] = 1
                        self.lock.release()
                elif ch == 'traderStatus':
                    data = mes.get('data')
                    expanse = data.get('symbol')
                    balance = data.get('traderBalance')
                    contracts = len(data.get('contracts'))
                    orders = len(data.get('activeOrders'))
                    self.lock.acquire()
                    self.pc.pilots[self.pilot]['info'][expanse] = {'balance':balance, 'contracts':contracts, 'orders':orders}
                    self.lock.release()
                elif status:
                    if status == 'error':
                        logging.info(self.message)

        while not self.flClosing:
            try:
                self.wsapp = websocket.WebSocketApp("wss://ws.mapi.digitexfutures.com", on_open=on_open,
                                                    on_close=on_close, on_error=on_error, on_message=on_message)
                self.wsapp.run_forever()
            except:
                pass
            finally:
                time.sleep(1)

    def getinfo(self):
        for expanse in self.expanses.keys():
            self.send_privat('getTraderStatus', symbol=expanse)
            time.sleep(0.1)

    def close(self):
        self.flClosing = True
        self.wsapp.close()

    def send_privat(self, method, **params):
        pd = {'id': 0, 'method': method, 'params': params}
        strpar = json.dumps(pd)
        self.wsapp.send(strpar)


class InfoRecipient(Thread):

    lock = Lock()

    def __init__(self, pc, delay):
        super(InfoRecipient, self).__init__()
        self.flClosing = False
        self.pc = pc
        self.delay = delay

    def run(self) -> None:
        while not self.flClosing:
            self.lock.acquire()
            for pilot in self.pc.pilots.keys():
                self.pc.getpilotinfo(pilot)
            self.lock.release()
            time.sleep(self.delay)

