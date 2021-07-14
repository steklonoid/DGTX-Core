from threading import Thread
import bcrypt   #pip install bcrypt
import websocket
import json
import time
import logging
import websockets
import asyncio
import sys
import hashlib
from Crypto.Cipher import AES # pip install pycryptodome

PSW = 'asd'

class WSSServer(Thread):
    def __init__(self, pc, pilots):
        super(WSSServer, self).__init__()
        self.pc = pc
        self.pilots = pilots

    def run(self) -> None:

        connections = {}
        managers = {}
        pilots = self.pilots
        rockets = {}

        async def rockets_changed():
            for websocket in managers.keys():
                await mc_getrockets(websocket, 0)

        async def add_rocket(websocket, id, data):
            if not rockets.get(websocket):
                psw = data.get('psw')
                if bcrypt.checkpw(psw.encode('utf-8'), self.pc.hashpsw['rocket'].encode('utf-8')):
                    rockets[websocket] = {'ts':time.time(), 'version':data['version'], 'status':0, 'pilot':None, 'parameters':{}, 'info':{}}
                    connections[websocket]['type'] = 'rocket'
                    str = {'id':id, 'message_type':'registration', 'data':{'status':'ok'}}
                    await rockets_changed()
                else:
                    str = {'id': id, 'message_type': 'registration', 'data': {'status': 'error', 'message': 'Неверный пароль'}}
            else:
                str = {'id': id, 'message_type': 'registration', 'data': {'status': 'error', 'message':'Есть уже такая ракета'}}
            str = json.dumps(str)
            await asyncio.wait([websocket.send(str)])

        async def managers_changed():
            for websocket in managers.keys():
                await mc_getmanagers(websocket, 0)

        async def add_manager(websocket, id, data):
            if not managers.get(websocket):
                psw = data.get('psw')
                if bcrypt.checkpw(psw.encode('utf-8'), self.pc.hashpsw['manager'].encode('utf-8')):
                    self.pc.hashpsw['psw'] = psw
                    managers[websocket] = {'ts': time.time(), 'user':data['user']}
                    connections[websocket]['type'] = 'manager'
                    str = {'id':id, 'message_type':'registration', 'data':{'status':'ok'}}
                    await managers_changed()
                else:
                    str = {'id': id, 'message_type': 'registration', 'data': {'status': 'error', 'message': 'Неверный пароль'}}
            else:
                str = {'id': id, 'message_type': 'registration', 'data': {'status': 'error', 'message':'Есть уже такой менеджер'}}
            str = json.dumps(str)
            await asyncio.wait([websocket.send(str)])
        #
        # async def race_info(rocket, parameters, info):
        #     if races.get(rocket):
        #         print('here')
        #         pilot = races[rocket]['pilot']
        #         races[rocket]['parameters'] = parameters
        #         races[rocket]['info'] = info
        #         flRace = parameters.get('flRace')
        #         if flRace:
        #             rockets[rocket]['status'] = 2
        #             pilots[pilot]['status'] = 2
        #             races[rocket]['status'] = 1
        #         else:
        #             rockets[rocket]['status'] = 1
        #             pilots[pilot]['status'] = 1
        #             races[rocket]['status'] = 0
        #         await races_changed()

        async def register(websocket):
            connections[websocket] = {'id':int(time.time()*10000000), 'ts':time.time(), 'type':'wait'}

        async def unregister(websocket):
            connections.pop(websocket, None)
            if managers.get(websocket):
                managers.pop(websocket, None)
                await managers_changed()
            if rockets.get(websocket):
                rockets.pop(websocket, None)
                await rockets_changed()
            # if races.get(websocket):
            #     pilot = races[websocket]['pilot']
            #     pilots[pilot]['status'] = 0
            #     races.pop(websocket, None)
            #     await races_changed()

#   ====================================================================================================================
        async def cm_pilot(websocket, pilot, id):
            pilot_data = {pilot:{'name':pilots[pilot]['name'], 'status':pilots[pilot]['status'], 'balance':pilots[pilot]['balance']}}
            data = {'id': id, 'message_type': 'cm', 'data': {'command': 'getpilot', 'pilot': pilot_data}}
            data = json.dumps(data)
            await asyncio.wait([websocket.send(data)])
    #   ----------------------------------------------------------------------------------------------------------------
        async def mc_getrockets(websocket, id):
            rockets_data = {connections[k]['id']:{'version':v['version'], 'status':v['status']} for k,v in rockets.items()}
            data = {'id':id, 'message_type':'cm', 'data':{'command':'getrockets', 'rockets':rockets_data}}
            data = json.dumps(data)
            await asyncio.wait([websocket.send(data)])

        async def mc_getmanagers(websocket, id):
            managers_data = [v['user'] for v in managers.values()]
            data = {'id':id, 'message_type':'cm', 'data':{'command':'getmanagers', 'managers':managers_data}}
            data = json.dumps(data)
            await asyncio.wait([websocket.send(data)])

        async def mc_getpilots(websocket, id):
            for pilot in pilots.keys():
                await cm_pilot(websocket, pilot, id)

        # async def mc_getraces(websocket, id):
        #     races_data = {connections[k]['id']: {'pilot': v['pilot'], 'status': v['status'], 'parameters':v['parameters'], 'info':v['info']} for k, v in races.items()}
        #     data = {'id': id, 'message_type': 'cm', 'data': {'command': 'getraces', 'races': races_data}}
        #     data = json.dumps(data)
        #     await asyncio.wait([websocket.send(data)])

        #   ----------------------------------------------------------------------------------------------------------------

        async def cb_authpilot(pilot, rocket):
            websocket_rocket = [k for k,v in connections.items() if v['id'] == rocket][0]
            ak = pilots[pilot]['apikey']

            IV_SIZE = 16  # 128 bit, fixed for the AES algorithm
            KEY_SIZE = 32  # 256 bit meaning AES-256, can also be 128 or 192 bits
            SALT_SIZE = 16  # This size is arbitrary
            en_ak_int = int(ak)
            en_ak_byte = en_ak_int.to_bytes((en_ak_int.bit_length() + 7) // 8, sys.byteorder)
            salt = en_ak_byte[0:SALT_SIZE]
            derived = hashlib.pbkdf2_hmac('sha256', self.pc.hashpsw['psw'].encode('utf-8'), salt, 100000,
                                          dklen=IV_SIZE + KEY_SIZE)
            iv = derived[0:IV_SIZE]
            key = derived[IV_SIZE:]
            ak = AES.new(key, AES.MODE_CFB, iv).decrypt(en_ak_byte[SALT_SIZE:]).decode('utf-8')
            data = {'id': 11, 'message_type': 'cb', 'data': {'command': 'authpilot', 'pilot': pilot, 'ak':ak}}
            data = json.dumps(data)
            await asyncio.wait([websocket_rocket.send(data)])

        async def cb_setparameters(rocket, parameters):
            data = {'id': 15, 'message_type': 'cb', 'data': {'command': 'cb_setparameters', 'parameters': parameters}}
            data = json.dumps(data)
            await asyncio.wait([rocket.send(data)])

        #   ----------------------------------------------------------------------------------------------------------------

        async def mainroutine(websocket, path):
            await register(websocket)
            try:
                async for message in websocket:
                    mes = json.loads(message)
                    print(mes)
                    id = mes.get('id')
                    message_type = mes.get('message_type')
                    data = mes.get('data')
                    if message_type == 'registration':
                        typereg = data.get('typereg')
                        if typereg == 'rocket':
                            await add_rocket(websocket, id, data)
                        elif typereg == 'manager':
                            await add_manager(websocket, id, data)
                        else:
                            pass
                    elif message_type == 'mc':
                        if managers.get(websocket):                            
                            command = data.get('command')
                            if command == 'getrockets':
                                await mc_getrockets(websocket, id)
                            elif command == 'getmanagers':
                                await mc_getmanagers(websocket, id)
                            elif command == 'getpilots':
                                await mc_getpilots(websocket, id)
                            # elif command == 'getraces':
                            #     await mc_getraces(websocket, id)
                            elif command == 'authpilot':
                                pilot = data.get('pilot')
                                rocket = int(data.get('rocket'))
                                await cb_authpilot(pilot, rocket)
                            elif command == 'setparameters':
                                parameters = data.get('parameters')
                                rocket = int(data.get('rocket'))
                                await cb_setparameters(rocket, parameters)
                            else:
                                pass
                        else:
                            pass
                    elif message_type == 'bc':
                        if rockets.get(websocket):
                            command = data.get('command')
                            if command == 'authpilot':
                                status = data.get('status')
                                if status == 'ok':
                                    pilot = data.get('pilot')
                                    # await add_race(websocket, pilot)
                            # elif command == 'race_info':
                            #     parameters = data.get('parameters')
                            #     info = data.get('info')
                            #     await race_info(websocket, parameters, info)
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
                id = mes.get('id')
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


class DGTXBalance(Thread):

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
            print(message)
            if message == 'ping':
                wssapp.send('pong')
            else:
                mes = json.loads(message)
                id = mes.get('id')
                status = mes.get('status')
                ch = mes.get('ch')
                if ch == 'tradingStatus':
                    data = mes.get('data')
                    available = data.get('available')
                    if available:
                        self.pc.pilots[self.pilot]['status'] = 1
                        self.send_privat('getTraderStatus', symbol='BTCUSD-PERP')
                        # self.getinfo()
                elif ch == 'traderStatus':
                    data = mes.get('data')
                    expanse = data.get('symbol')
                    balance = data.get('traderBalance')
                    contracts = len(data.get('contracts'))
                    orders = len(data.get('activeOrders'))
                    self.pc.pilots[self.pilot]['info'][expanse] = {'balance':balance, 'contracts':contracts, 'orders':orders}
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
        time.sleep(1)
        self.getinfo()


    def message_tradingStatus(self, data):
        status = data.get('available')

    def message_traderStatus(self, data):
        pass

    def send_privat(self, method, **params):
        pd = {'id': 0, 'method': method, 'params': params}
        strpar = json.dumps(pd)
        self.wsapp.send(strpar)

