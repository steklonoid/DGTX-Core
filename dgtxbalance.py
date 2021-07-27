from threading import Thread
import websocket
import json
import time
import logging
from threading import Lock


class DGTXBalance(Thread):

    lock = Lock()

    def __init__(self, selfconnector, pilot, name, ak):
        super(DGTXBalance, self).__init__()
        self.selfconnector = selfconnector
        self.pilot = pilot
        self.name = name
        self.ak = ak

    def run(self) -> None:
        def on_open(wsapp):
            self.send_privat('auth', type='token', value=self.ak)

        def on_message(wssapp, message):
            if message == 'ping':
                wssapp.send('pong')
            else:
                mes = json.loads(message)
                ch = mes.get('ch')
                if ch == 'tradingStatus':
                    data = mes.get('data')
                    available = data.get('available')
                    if available:
                        self.send_privat('getTraderStatus', symbol='BTCUSD-PERP')
                    else:
                        self.sc_pilotinfo(False)
                        self.wsapp.close()
                elif ch == 'traderStatus':
                    data = mes.get('data')
                    self.sc_pilotinfo(True, data)
                    self.wsapp.close()
                else:
                    pass

        self.wsapp = websocket.WebSocketApp("wss://ws.mapi.digitexfutures.com", on_open=on_open, on_message=on_message)
        self.wsapp.run_forever()

    def sc_pilotinfo(self, statusauth, data=None):
        if statusauth:
            status = 1
            balance = data.get('traderBalance')
        else:
            status = 0
            balance = 0
        pilot_info = {'name':self.name, 'ak':self.ak, 'status':status, 'balance':balance}
        self.selfconnector.sc_pilotinfo(self.pilot, pilot_info)

    def send_privat(self, method, **params):
        pd = {'id': 0, 'method': method, 'params': params}
        strpar = json.dumps(pd)
        self.wsapp.send(strpar)
