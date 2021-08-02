from threading import Thread
import websocket
import json
import time
import logging


#   получает цены по инсрументу
class WSSDGTX(Thread):

    def __init__(self, q):
        super(WSSDGTX, self).__init__()
        self.q = q
        self.flConnect = False

    def run(self) -> None:
        def on_open(wsapp):
            logging.info(self.ex + ' ' + 'Соединение с DGTX установлено')
            self.flConnect = True
            # self.send_public('subscribe', self.ex + '@index')

        def on_close(wsapp, close_status_code, close_msg):
            logging.info(self.ex + ' close / ' + str(close_status_code) + ' / ' + str(close_msg))
            self.flConnect = False

        def on_error(wsapp, error):
            logging.info(self.ex + ' ' + 'Ошибка соединения с DGTX')
            self.flConnect = False
            time.sleep(1)

        def on_message(wssapp, message):
            if message == 'ping':
                wssapp.send('pong')
            else:
                mes = json.loads(message)
                self.q.put(mes)
                ch = mes.get('ch')
                if ch == 'index':
                    self.tickcounter += 1
                    self.pc.dgtxindex(self.ex, mes.get('data')['spotPx'])
                    if self.tickcounter > 128:
                        if time.time() - self.lasttime > 5:
                            self.lasttime = time.time()
                            self.pc.market_analizator(self.ex)

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