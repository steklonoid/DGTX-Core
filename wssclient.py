from threading import Thread
import websocket
import json
import time


class WSSClient(Thread):
    def __init__(self, q, address):
        super(WSSClient, self).__init__()
        self.q = q
        self.address = address
        self.flConnect = False
        self.flClosing = False

    def run(self) -> None:
        def on_open(wsapp):
            print(self.address, 'open')
            self.flConnect = True

        def on_close(wsapp, close_status_code, close_msg):
            print(self.address, 'close')
            self.flConnect = False

        def on_error(wsapp, error):
            self.flConnect = False

        def on_message(wssapp, message):
            if message == 'ping':
                self.wsapp.send('pong')
            else:
                data = json.loads(message)
                self.q.put(data)

        while not self.flClosing:
            try:
                self.wsapp = websocket.WebSocketApp(self.address, on_open=on_open,
                                                               on_close=on_close, on_error=on_error, on_message=on_message)
                self.wsapp.run_forever()
            except:
                pass
            finally:
                time.sleep(1)

    # def sc_marketinfo(self, info):
    #     str = {'command':'sc_marketinfo', 'info':info}
    #     self.send_sc(str)

    def send(self, data):
        # str = {'message_type':'sc', 'data':data}
        str = json.dumps(data)
        self.wsapp.send(str)


class FromQToF(Thread):

    def __init__(self, f, q):
        super(FromQToF, self).__init__()
        self.f = f
        self.q = q

    def run(self) -> None:
        while True:
            data = self.q.get()
            self.f(data)
