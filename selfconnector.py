from threading import Thread
import websocket
import json
import time


class SelfConnector(Thread):
    def __init__(self, pc):
        super(SelfConnector, self).__init__()
        self.pc = pc
        self.flConnect = False
        self.flClosing = False

    def run(self) -> None:
        def on_open(wsapp):
            self.flConnect = True

        def on_close(wsapp, close_status_code, close_msg):
            self.flConnect = False

        def on_error(wsapp, error):
            self.flConnect = False

        def on_message(wssapp, message):
            print(message)
            mes = json.loads(message)
            message_type = mes.get('message_type')
            data = mes.get('data')
            if message_type == 'registration':
                status = data.get('status')
                if status == 'ok':
                    pass
                else:
                    pass
            elif message_type == 'cs':
                command = data.get('command')
                if command == 'cs_pilotadd':
                    pass
                elif command == 'cs_pilotdelete':
                    pass
                else:
                    pass
            else:
                pass

        while not self.flClosing:
            try:
                self.wsapp = websocket.WebSocketApp("ws://localhost:6789", on_open=on_open,
                                                               on_close=on_close, on_error=on_error, on_message=on_message)
                self.wsapp.run_forever()
            except:
                pass
            finally:
                time.sleep(1)

    def pilot_info(self, pilot, info):
        str = {'command':'sc_pilotinfo', 'pilot':pilot, 'info':info}
        self.send_sc(str)

    def market_info(self, info):
        str = {'command':'sc_marketinfo', 'info':info}
        self.send_sc(str)

    def send_sc(self, data):
        str = {'message_type':'sc', 'data':data}
        str = json.dumps(str)
        self.wsapp.send(str)