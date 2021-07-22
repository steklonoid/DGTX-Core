from threading import Thread
import websocket
import json
import time
import logging
from threading import Lock


class DGTXBalance(Thread):

    lock = Lock()

    def __init__(self, pc, pilot, ak):
        super(DGTXBalance, self).__init__()
        self.pc = pc
        self.pilot = pilot
        self.ak = ak
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
                    self.lock.acquire()
                    if available:
                        self.pc.pilots[self.pilot]['status'] = 1
                    else:
                        self.pc.pilots[self.pilot]['status'] = 0
                    self.lock.release()
                elif ch == 'traderStatus':
                    data = mes.get('data')
                    self.pc.getpilotinfo(self.pilot, data)
                else:
                    pass

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
        self.send_privat('getTraderStatus', symbol='BTCUSD-PERP')
        time.sleep(0.1)

    def close(self):
        self.flClosing = True
        self.wsapp.close()

    def send_privat(self, method, **params):
        pd = {'id': 0, 'method': method, 'params': params}
        strpar = json.dumps(pd)
        self.wsapp.send(strpar)
