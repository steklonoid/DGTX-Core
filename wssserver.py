from threading import Thread
import bcrypt   #pip install bcrypt
import json
import time
import websockets
import asyncio


class Pilot():

    def __init__(self, name, ak, rocket=None, authstate=0, info=None, parameters=None):
        self.name = name
        self.ak = ak
        self.rocket = rocket
        self.authstate = authstate
        self.info = info
        self.parameters = parameters


class WSSServer(Thread):

    connections = {}
    managers = {}
    pilots = {}

    def __init__(self, pc):
        super(WSSServer, self).__init__()
        self.pc = pc

    def run(self) -> None:

        async def sendpilottoall(login):
            pilot = self.pilots[login]
            data = {'command': 'cm_pilotinfo', 'pilot': login, 'name':pilot.name, 'authstate':pilot.authstate, 'info':pilot.info, 'parameters':pilot.parameters}
            str = json.dumps(data)
            for manager_websocket in self.managers.keys():
                await asyncio.wait([manager_websocket.send(str)])

        #   ----------------------------------------------------------------------------------------------------------------

        async def register(websocket):
            self.connections[websocket] = {'ts':time.time(), 'type':'wait'}

        async def unregister(websocket):
            connection = self.connections.get(websocket)
            if connection['type'] == 'manager':
                await managers_change()
                self.managers.pop(websocket, None)
            elif connection['type'] == 'rocket':
                await rocket_delete(websocket)
            self.connections.pop(websocket, None)

        #   ----------------------------------------------------------------------------------------------------------------

        async def rocket_delete(rocket_websocket):
            for login,pilot in self.pilots.items():
                if pilot.rocket == rocket_websocket:
                    pilot.rocket = None
                    await sendpilottoall(login)
                    break

        #   ----------------------------------------------------------------------------------------------------------------

        async def managers_change():
            managers_data = [v for v in self.managers.values()]
            managers_data = {'command': 'cm_managersinfo', 'managers': managers_data}
            managers_data = json.dumps(managers_data)
            for websocket in self.managers.keys():
                await asyncio.wait([websocket.send(managers_data)])

            for pilot in self.pilots.keys():
                await sendpilottoall(pilot)

        async def register_manager(manager_websocket, user, psw):
            if not self.managers.get(manager_websocket):
                if bcrypt.checkpw(psw.encode('utf-8'), self.pc.hashpsw['manager'].encode('utf-8')):
                    self.managers[manager_websocket] = user
                    self.connections[manager_websocket]['type'] = 'manager'
                    str = {'command':'cm_registration', 'status':'ok'}
                    await managers_change()
                else:
                    str = {'command':'cm_registration', 'status': 'error', 'message': 'Неверный пароль'}
            else:
                str = {'command':'cm_registration', 'status': 'error', 'message':'Есть уже такой менеджер'}
            str = json.dumps(str)
            await asyncio.wait([manager_websocket.send(str)])

        #   ----------------------------------------------------------------------------------------------------------------
        async def bc_registration(rocket_websocket, psw):
            if bcrypt.checkpw(psw.encode('utf-8'), self.pc.hashpsw['rocket'].encode('utf-8')):
                self.connections[rocket_websocket]['type'] = 'rocket'
                isFreePilot = False
                for login,pilot in self.pilots.items():
                    if not pilot.rocket:
                        isFreePilot = True
                        self.pilots[login].rocket = rocket_websocket
                        data = {'command': 'cb_registration', 'status':'ok', 'pilot': login, 'ak': pilot.ak}
                        break
                if not isFreePilot:
                    data = {'command': 'cb_registration', 'status': 'error', 'message': 'Нет свободных пилотов'}
            else:
                data = {'command':'cb_registration', 'status': 'error', 'message': 'Неверный пароль'}
            str = json.dumps(data)
            await asyncio.wait([rocket_websocket.send(str)])

        async def bc_authpilot(login, status):
            pilot = self.pilots[login]
            if status == 'ok':
                pilot.authstate = 1
            else:
                pilot.authstate = 2
            await sendpilottoall(pilot)

        async def bc_raceinfo(rocket_websocket, parameters, info):
            pass

        #   ----------------------------------------------------------------------------------------------------------------

        async def mc_setparameters(rocket_id, parameters):
            websocket_rocket = [k for k, v in self.connections.items() if v['id'] == rocket_id][0]
            data = {'command': 'cb_setparameters', 'parameters': parameters}
            data = json.dumps(data)
            await asyncio.wait([websocket_rocket.send(data)])

        #   ----------------------------------------------------------------------------------------------------------------

        async def sc_pilotsinfo(pilots):
            for login,pilot in pilots.items():
                self.pilots[login] = Pilot(pilot['name'], pilot['ak'])

        async def sc_marketinfo(info):
            data = {'command': 'cb_marketinfo', 'info': info}
            data = json.dumps(data)
            listrw = [v.rocket for v in self.pilots.values() if v.rocket]
            for rocket_websocket in listrw:
                await asyncio.wait([rocket_websocket.send(data)])
            data = {'command': 'cm_marketinfo', 'info': info}
            data = json.dumps(data)
            for manager_websocket in self.managers.keys():
                await asyncio.wait([manager_websocket.send(data)])

        #   ----------------------------------------------------------------------------------------------------------------

        async def mainroutine(websocket, path):
            await register(websocket)
            try:
                async for message in websocket:
                    print(message)
                    mes = json.loads(message)
                    # print(mes)
                    command = mes.get('command')
                    if command == 'mc_registration':
                        user = mes.get('user')
                        psw = mes.get('psw')
                        await register_manager(websocket, user, psw)
                    elif command == 'mc_setparameters':
                        parameters = mes.get('parameters')
                        rocket = mes.get('rocket')
                        await mc_setparameters(rocket, parameters)
                    elif command == 'bc_registration':
                        psw = mes.get('psw')
                        await bc_registration(websocket, psw)
                    elif command == 'bc_authpilot':
                        status = mes.get('status')
                        pilot = mes.get('pilot')
                        await bc_authpilot(pilot, status)
                    elif command == 'bc_raceinfo':
                        parameters = mes.get('parameters')
                        info = mes.get('info')
                        await bc_raceinfo(websocket, parameters, info)
                    elif command == 'sc_pilotsinfo':
                        pilots = mes.get('pilots')
                        await sc_pilotsinfo(pilots)
                    elif command == 'sc_marketinfo':
                        info = mes.get('info')
                        await sc_marketinfo(info)
                    else:
                        pass
            finally:
                print('unregister')
                await unregister(websocket)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        start_server = websockets.serve(mainroutine, self.pc.serveraddress, int(self.pc.serverport))
        loop.run_until_complete(start_server)
        loop.run_forever()


