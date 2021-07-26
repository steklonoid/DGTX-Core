from threading import Thread
import time
from threading import Lock
import numpy as np


class Analizator(Thread):

    lock = Lock()

    def __init__(self, expanses, selfconnector):
        super(Analizator, self).__init__()
        self.expanses = expanses
        self.selfconnector = selfconnector

    def run(self) -> None:
        while True:
            self.market_analizator()
            time.sleep(5)

    def market_analizator(self):
        self.lock.acquire()
        ex = dict(self.expanses)
        self.lock.release()
        for symbol in ex.keys():
            ar = np.array(ex[symbol])
            ar = np.absolute(ar[1:] - ar[:-1])
            market_volatility_128 = round(np.mean(ar), 3)
            info = {'symbol': symbol, 'market_volatility_128': market_volatility_128}
            print(info)
            self.selfconnector.market_info(info)