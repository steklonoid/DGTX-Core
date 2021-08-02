from threading import Thread
import bcrypt   #pip install bcrypt
import json
import time
import websockets
import asyncio


class WSSServer(Thread):

    connections = {}
    managers = {}
    rockets = {}
    pilots = {}
    marketinfo = {}

    def __init__(self, pc):
        super(WSSServer, self).__init__()
        self.pc = pc

    def run(self) -> None:

        async def sendpilottoall(pilot):
            info = self.pilots[pilot]
            pilot_info = {'name': info['name'], 'status': info['status'], 'balance': info['balance']}
            data = {'command': 'cm_pilotinfo', 'pilot': pilot, 'info':pilot_info}
            str = {'message_type': 'cm', 'data': data}
            str = json.dumps(str)
            for manager_websocket in self.managers.keys():
                await asyncio.wait([manager_websocket.send(str)])

        async def sendrockettoall(rocket_websocket):
            rocket_data = {self.connections[rocket_websocket]['id']: self.rockets[rocket_websocket]}
            data = {'command': 'cm_rocketinfo', 'rocket': rocket_data}
            str = {'message_type': 'cm', 'data': data}
            str = json.dumps(str)
            for manager_websocket in self.managers.keys():
                await asyncio.wait([manager_websocket.send(str)])
        #   ----------------------------------------------------------------------------------------------------------------

        async def register(websocket):
            self.connections[websocket] = {'id':str(int(time.time()*10000000)), 'ts':time.time(), 'type':'wait'}

        async def unregister(websocket):
            if self.managers.get(websocket):
                await managers_change()
                self.managers.pop(websocket, None)
            if self.rockets.get(websocket):
                await rocket_delete(websocket)
                self.rockets.pop(websocket, None)
            self.connections.pop(websocket, None)

        #   ----------------------------------------------------------------------------------------------------------------

        async def rocket_change(rocket_websocket, parameters=None, info=None):
            if parameters:
                self.rockets[rocket_websocket]['parameters'] = parameters
            if info:
                self.rockets[rocket_websocket]['info'] = info
            await sendrockettoall(rocket_websocket)

        async def rocket_delete(rocket_websocket):
            pilot = self.rockets[rocket_websocket]['pilot']
            if pilot:
                self.pilots[pilot]['status'] = 1
                await sendpilottoall(pilot)
            id = self.connections[rocket_websocket]['id']
            data = {'message_type': 'cm', 'data': {'command': 'cm_rocketdelete', 'rocket': id}}
            data = json.dumps(data)
            for manager_websocket in self.managers.keys():
                await asyncio.wait([manager_websocket.send(data)])

        async def register_rocket(rocket_websocket, psw, version):
            if not self.rockets.get(rocket_websocket):
                if bcrypt.checkpw(psw.encode('utf-8'), self.pc.hashpsw['rocket'].encode('utf-8')):
                    self.rockets[rocket_websocket] = {'version':version, 'status':0, 'pilot':None, 'parameters':{}, 'info':{}}
                    self.connections[rocket_websocket]['type'] = 'rocket'
                    data = {'message_type':'cb', 'data':{'command':'cb_registration', 'status':'ok'}}
                    await rocket_change(rocket_websocket)
                else:
                    data = {'message_type': 'cb', 'data': {'command':'cb_registration', 'status': 'error', 'message': 'Неверный пароль'}}
            else:
                data = {'message_type': 'cb', 'data': {'command':'cb_registration', 'status': 'error', 'message':'Есть уже такая ракета'}}
            str = json.dumps(data)
            await asyncio.wait([rocket_websocket.send(str)])

        #   ----------------------------------------------------------------------------------------------------------------

        async def managers_change():
            managers_data = [v['user'] for v in self.managers.values()]
            managers_data = {'message_type': 'cm', 'data': {'command': 'cm_managersinfo', 'managers': managers_data}}
            managers_data = json.dumps(managers_data)
            for websocket in self.managers.keys():
                await asyncio.wait([websocket.send(managers_data)])

            for rocket_websocket in self.rockets.keys():
                await sendrockettoall(rocket_websocket)

            for pilot in self.pilots.keys():
                await sendpilottoall(pilot)

        async def register_manager(manager_websocket, user, psw):
            if not self.managers.get(manager_websocket):
                if bcrypt.checkpw(psw.encode('utf-8'), self.pc.hashpsw['manager'].encode('utf-8')):
                    self.managers[manager_websocket] = {'ts': time.time(), 'user':user}
                    self.connections[manager_websocket]['type'] = 'manager'
                    str = {'message_type':'cm', 'data':{'command':'cm_registration', 'status':'ok'}}
                    await managers_change()
                else:
                    str = {'message_type': 'cm', 'data': {'command':'cm_registration', 'status': 'error', 'message': 'Неверный пароль'}}
            else:
                str = {'message_type': 'cm', 'data': {'command':'cm_registration', 'status': 'error', 'message':'Есть уже такой менеджер'}}
            str = json.dumps(str)
            await asyncio.wait([manager_websocket.send(str)])

        #   ----------------------------------------------------------------------------------------------------------------

        async def bc_authpilot(pilot, rocket_websocket):
            self.pilots[pilot]['status'] = 2
            self.rockets[rocket_websocket]['status'] = 1
            self.rockets[rocket_websocket]['pilot'] = pilot
            await sendpilottoall(pilot)
            await sendrockettoall(rocket_websocket)

        async def bc_raceinfo(rocket_websocket, parameters, info):
            await rocket_change(rocket_websocket, parameters, info)

        #   ----------------------------------------------------------------------------------------------------------------

        async def mc_authpilot(pilot, rocket_id):
            websocket_rocket = [k for k,v in self.connections.items() if v['id'] == rocket_id][0]
            ak = self.pilots[pilot]['ak']
            data = {'command': 'cb_authpilot', 'pilot': pilot, 'ak':ak}
            str = {'message_type': 'cb', 'data': data}
            str = json.dumps(str)
            await asyncio.wait([websocket_rocket.send(str)])

        async def mc_setparameters(rocket_id, parameters):
            websocket_rocket = [k for k, v in self.connections.items() if v['id'] == rocket_id][0]
            data = {'message_type': 'cb', 'data': {'command': 'cb_setparameters', 'parameters': parameters}}
            data = json.dumps(data)
            await asyncio.wait([websocket_rocket.send(data)])

        #   ----------------------------------------------------------------------------------------------------------------

        async def sc_pilotinfo(pilot, info):
            self.pilots[pilot] = info
            await sendpilottoall(pilot)

        async def sc_marketinfo(info):
            market_data = info
            data = {'message_type': 'cb', 'data': {'command': 'cb_marketinfo', 'info': market_data}}
            data = json.dumps(data)
            for rocket_websocket in self.rockets.keys():
                await asyncio.wait([rocket_websocket.send(data)])
            data = {'message_type': 'cm', 'data': {'command': 'cm_marketinfo', 'info': market_data}}
            data = json.dumps(data)
            for manager_websocket in self.managers.keys():
                await asyncio.wait([manager_websocket.send(data)])

        #   ----------------------------------------------------------------------------------------------------------------

        async def mainroutine(websocket, path):
            await register(websocket)
            try:
                async for message in websocket:
                    mes = json.loads(message)
                    message_type = mes.get('message_type')
                    data = mes.get('data')
                    if message_type == 'mc':
                        command = data.get('command')
                        if command == 'mc_registration':
                            user = data.get('user')
                            psw = data.get('psw')
                            await register_manager(websocket, user, psw)
                        elif command == 'mc_authpilot':
                            if self.managers.get(websocket):
                                pilot = data.get('pilot')
                                rocket = data.get('rocket')
                                await mc_authpilot(pilot, rocket)
                        elif command == 'mc_setparameters':
                            if self.managers.get(websocket):
                                parameters = data.get('parameters')
                                rocket = data.get('rocket')
                                await mc_setparameters(rocket, parameters)
                        else:
                            pass
                    elif message_type == 'bc':
                        command = data.get('command')
                        if command == 'bc_registration':
                            psw = data.get('psw')
                            version = data.get('version')
                            await register_rocket(websocket, psw, version)
                        elif command == 'bc_authpilot':
                            if self.rockets.get(websocket):
                                status = data.get('status')
                                if status == 'ok':
                                    pilot = data.get('pilot')
                                    await bc_authpilot(pilot, websocket)
                        elif command == 'bc_raceinfo':
                            if self.rockets.get(websocket):
                                parameters = data.get('parameters')
                                info = data.get('info')
                                await bc_raceinfo(websocket, parameters, info)
                        else:
                            pass
                    elif message_type == 'sc':
                        command = data.get('command')
                        if command == 'sc_pilotinfo':
                            pilot = data.get('pilot')
                            info = data.get('info')
                            await sc_pilotinfo(pilot, info)
                        elif command == 'sc_marketinfo':
                            info = data.get('info')
                            await sc_marketinfo(info)
                        else:
                            pass
                    else:
                        pass
            finally:
                await unregister(websocket)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        start_server = websockets.serve(mainroutine, "localhost", 16789)
        loop.run_until_complete(start_server)
        loop.run_forever()


