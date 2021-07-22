from threading import Thread
import time
from threading import Lock


class Timer(Thread):

    lock = Lock()

    def __init__(self):
        super(Timer, self).__init__()
        self.d = {}
        self.delay = 5

    def run(self) -> None:
        while True:
            self.lock.acquire()
            dv = list(self.d.values())
            self.lock.release()
            for v in dv:
                v.getinfo()
            time.sleep(self.delay)

    def pilotadd(self, login, agent):
        self.lock.acquire()
        self.d[login] = agent
        self.lock.release()

    def pilotremove(self, login):
        self.lock.acquire()
        self.d.pop(login, None)
        self.lock.release()

class Worker(Thread):
    def __init__(self, f, delay):
        super(Worker, self).__init__()
        self.f = f
        self.delay = delay

    def run(self) -> None:
        while True:
            self.f()
            time.sleep(self.delay)