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
            pilot_data = {pilot: {'name': info['name'], 'status': info['status'], 'balance': info['balance']}}
            data = {'message_type': 'cm', 'data': {'command': 'cm_pilotinfo', 'pilot': pilot_data}}
            data = json.dumps(data)
            for manager_websocket in self.managers.keys():
                await asyncio.wait([manager_websocket.send(data)])

        #   ----------------------------------------------------------------------------------------------------------------

        async def register(websocket):
            self.connections[websocket] = {'id':int(time.time()*10000000), 'ts':time.time(), 'type':'wait'}

        async def unregister(websocket):
            if self.managers.get(websocket):
                self.managers.pop(websocket, None)
                await managers_change()
            if self.rockets.get(websocket):
                self.rockets.pop(websocket, None)
                await rocket_delete(self.connections[websocket]['id'])
            self.connections.pop(websocket, None)

        #   ----------------------------------------------------------------------------------------------------------------

        async def rocket_change(rocket_websocket, parameters=None, info=None):
            self.rockets[rocket_websocket]['parameters'] = parameters
            self.rockets[rocket_websocket]['info'] = info
            rocket_data = {self.connections[rocket_websocket]['id']: self.rockets[rocket_websocket]}
            data = {'message_type': 'cm', 'data': {'command': 'cm_rocketinfo', 'rocket': rocket_data}}
            data = json.dumps(data)
            for manager_websocket in self.managers.keys():
                await asyncio.wait([manager_websocket.send(data)])

        async def rocket_delete(id):
            data = {'message_type': 'cm', 'data': {'command': 'cm_rocketdelete', 'rocket': id}}
            data = json.dumps(data)
            for manager_websocket in self.managers.keys():
                await asyncio.wait([manager_websocket.send(data)])

        async def register_rocket(rocket_websocket, data):
            if not self.rockets.get(rocket_websocket):
                psw = data.get('psw')
                if bcrypt.checkpw(psw.encode('utf-8'), self.pc.hashpsw['rocket'].encode('utf-8')):
                    self.rockets[rocket_websocket] = {'ts':time.time(), 'version':data['version'], 'status':0, 'pilot':None, 'parameters':{}, 'info':{}}
                    self.connections[rocket_websocket]['type'] = 'rocket'
                    str = {'message_type':'registration', 'data':{'status':'ok'}}
                    await rocket_change(rocket_websocket)
                else:
                    str = {'message_type': 'registration', 'data': {'status': 'error', 'message': 'Неверный пароль'}}
            else:
                str = {'message_type': 'registration', 'data': {'status': 'error', 'message':'Есть уже такая ракета'}}
            str = json.dumps(str)
            await asyncio.wait([rocket_websocket.send(str)])

        #   ----------------------------------------------------------------------------------------------------------------

        async def managers_change():
            managers_data = [v['user'] for v in self.managers.values()]
            managers_data = {'message_type': 'cm', 'data': {'command': 'cm_managersinfo', 'managers': managers_data}}
            managers_data = json.dumps(managers_data)
            for websocket in self.managers.keys():
                await asyncio.wait([websocket.send(managers_data)])

            for rocket_websocket in self.rockets.keys():
                rocket_data = {self.connections[rocket_websocket]['id']: self.rockets[rocket_websocket]}
                rocket_data = {'message_type': 'cm', 'data': {'command': 'cm_rocketinfo', 'rocket': rocket_data}}
                rocket_data = json.dumps(rocket_data)
                for manager_websocket in self.managers.keys():
                    await asyncio.wait([manager_websocket.send(rocket_data)])

            for pilot in self.pilots.keys():
                await sendpilottoall(pilot)

        async def register_manager(manager_websocket, data):
            if not self.managers.get(manager_websocket):
                psw = data.get('psw')
                if bcrypt.checkpw(psw.encode('utf-8'), self.pc.hashpsw['manager'].encode('utf-8')):
                    self.managers[manager_websocket] = {'ts': time.time(), 'user':data['user']}
                    self.connections[manager_websocket]['type'] = 'manager'
                    str = {'message_type':'registration', 'data':{'status':'ok'}}
                    await managers_change()
                else:
                    str = {'message_type': 'registration', 'data': {'status': 'error', 'message': 'Неверный пароль'}}
            else:
                str = {'message_type': 'registration', 'data': {'status': 'error', 'message':'Есть уже такой менеджер'}}
            str = json.dumps(str)
            await asyncio.wait([manager_websocket.send(str)])

        #   ----------------------------------------------------------------------------------------------------------------

        async def bc_authpilot(pilot):
            self.pilots[pilot]['status'] = 2
            await sendpilottoall(pilot)

        async def bc_raceinfo(rocket_websocket, pilot, parameters, info):
            pass

        #   ----------------------------------------------------------------------------------------------------------------

        async def mc_authpilot(pilot, rocket_id):
            websocket_rocket = [k for k,v in self.connections.items() if v['id'] == rocket_id][0]
            ak = self.pilots[pilot]['ak']
            data = {'message_type': 'cb', 'data': {'command': 'cb_authpilot', 'pilot': pilot, 'ak':ak}}
            data = json.dumps(data)
            print(data)
            print(websocket_rocket)
            await asyncio.wait([websocket_rocket.send(data)])

        async def mc_setparameters(rocket, parameters):
            data = {'message_type': 'cb', 'data': {'command': 'cb_setparameters', 'parameters': parameters}}
            data = json.dumps(data)
            await asyncio.wait([rocket.send(data)])

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
                    # print(message)
                    mes = json.loads(message)
                    message_type = mes.get('message_type')
                    data = mes.get('data')
                    if message_type == 'registration':
                        typereg = data.get('typereg')
                        if typereg == 'rocket':
                            await register_rocket(websocket, data)
                        elif typereg == 'manager':
                            await register_manager(websocket, data)
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
                                pilot = data.get('pilot')
                                parameters = data.get('parameters')
                                info = data.get('info')
                                await bc_raceinfo(websocket, pilot, parameters, info)
                            else:
                                pass
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
        start_server = websockets.serve(mainroutine, "localhost", 6789)
        loop.run_until_complete(start_server)
        loop.run_forever()


