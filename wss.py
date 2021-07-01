from threading import Thread
from PyQt5.QtSql import QSqlQuery
import websocket
import json
import time
import logging
import websockets
import asyncio

PSW = 'asd'

class WSSServer(Thread):
    def __init__(self, pc, db):
        super(WSSServer, self).__init__()
        self.pc = pc
        self.db = db

    def run(self) -> None:

        connections = {}
        managers = {}
        pilots = {}
        rockets = {}
        races = {}

        async def rockets_changed():
            for websocket in managers.keys():
                await mc_getrockets(websocket, 0)

        async def add_rocket(websocket, id, data):
            if not rockets.get(websocket):
                rockets[websocket] = {'ts':time.time(), 'version':data['version'], 'status':0}
                connections[websocket]['type'] = 'rocket'
                str = {'id':id, 'message_type':'registration', 'data':{'status':'ok'}}
                await rockets_changed()
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
                if psw == PSW:
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
            pilots_data = {k:{'name':v['name'], 'status':v['status']} for k,v in pilots.items()}
            data = {'id':id, 'message_type':'cm', 'data':{'command':'getpilots', 'pilots':pilots_data}}
            data = json.dumps(data)
            await asyncio.wait([websocket.send(data)])

        async def mc_races(websocket, id):
            pass

        async def cb_authpilot(pilot, rocket):
            websocket_rocket = [k for k,v in connections.items() if v['id'] == rocket][0]
            ak = pilots[pilot]['apikey']
            data = {'id': 11, 'message_type': 'cb', 'data': {'command': 'authpilot', 'pilot': pilot, 'ak':ak, 'rocket':rocket}}
            data = json.dumps(data)
            await asyncio.wait([websocket_rocket.send(data)])

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
                            elif command == 'getraces':
                                await mc_races(websocket, id)
                            elif command == 'authpilot':
                                pilot = data.get('pilot')
                                rocket = int(data.get('rocket'))
                                await cb_authpilot(pilot, rocket)
                            elif command == 'getpilotinfo':
                                pass
                            elif command == 'getraceinfo':
                                pass
                            elif command == 'getraceparameters':
                                pass
                            elif command == 'setraceparameters':
                                pass
                            else:
                                pass
                        else:
                            pass
                    elif message_type == 'rocket_responce':
                        pass
                    else:
                        pass
            finally:
                await unregister(websocket)

        q1 = QSqlQuery(self.db)
        q1.prepare('SELECT login, name, psw, apikey FROM pilots')
        q1.exec_()
        while q1.next():
            pilots[q1.value(0)] = {'name':q1.value(1), 'psw':q1.value(2), 'apikey':q1.value(3), 'status':0}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        start_server = websockets.serve(mainroutine, "localhost", 6789)
        loop.run_until_complete(start_server)
        loop.run_forever()

class WSThread(Thread):
    def __init__(self, pc):
        super(WSThread, self).__init__()
        self.pc = pc
        self.flClosing = False

    def run(self) -> None:
        def on_open(wsapp):
            logging.info('open')
            self.pc.flConnect = True
            self.pc.statusbar.showMessage('Есть соединение с сервером')
            self.changeEx(self.pc.symbol)

        def on_close(wsapp, close_status_code, close_msg):
            logging.info('close / ' + str(close_status_code) + ' / ' + str(close_msg))
            self.pc.flConnect = False
            self.pc.statusbar.showMessage('Нет соединения с сервером')

        def on_error(wsapp, error):
            logging.info(error)

        def on_message(wssapp, message):
            if message == 'ping':
                wssapp.send('pong')
            else:
                self.message = json.loads(message)
                id = self.message.get('id')
                status = self.message.get('status')
                ch = self.message.get('ch')
                if ch:
                    self.pc.listf[ch]['q'].put(self.message.get('data'))
                elif status:
                    if status == 'error':
                        logging.info(self.message)

        while not self.flClosing:
            try:
                self.wsapp = websocket.WebSocketApp("wss://ws.mapi.digitexfutures.com", on_open=on_open,
                                                    on_close=on_close, on_error=on_error, on_message=on_message)
                self.wsapp.run_forever()
                self.pc.statusbar.showMessage('Восстановление соединения с сервером')
            except:
                pass
            time.sleep(1)

    def changeEx(self, name):
        self.send_public('subscribe', name + '@index', name + '@orderbook_1')

    def send_public(self, method, *params):
        pd = {'id':1, 'method':method}
        if params:
            pd['params'] = list(params)
        strpar = json.dumps(pd)
        self.pc.sendq.put(strpar)

    def send_privat(self, method, **params):
        pd = {'id':self.methods.get(method), 'method':method, 'params':params}
        strpar = json.dumps(pd)
        self.pc.sendq.put(strpar)


class Worker(Thread):
    def __init__(self, q, f):
        super(Worker, self).__init__()
        self.q = q
        self.f = f

    def run(self) -> None:
        while True:
            data = self.q.get()
            self.f(data)


class Senderq(Thread):
    def __init__(self, q, th):
        super(Senderq, self).__init__()
        self.q = q
        self.th = th
        self.flClosing = False

    def run(self) -> None:
        while not self.flClosing:
            data = self.q.get()
            try:
                self.th.wsapp.send(data)
            except:
                pass
            time.sleep(0.1)


class InTimer(Thread):
    def __init__(self, pc):
        super(InTimer, self).__init__()
        self.pc = pc
        self.delay = 0.1
        self.pnlStartTime = 0
        self.pnlTime = 0
        self.workingStartTime = 0
        self.flWorking = False
        self.flClosing = False

    def run(self) -> None:
        while not self.flClosing:
            if self.flWorking:
                self.pnlTime = time.time() - self.pnlStartTime
            time.sleep(self.delay)


class Analizator(Thread):

    def __init__(self, f):
        super(Analizator, self).__init__()
        self.delay = 1
        self.flClosing = False
        self.f = f

    def run(self) -> None:
        while not self.flClosing:
            self.f()
            time.sleep(self.delay)