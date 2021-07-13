import sys
import os
import logging

from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox
from PyQt5.QtCore import QSettings
from PyQt5.QtSql import QSqlDatabase, QSqlQuery
from mainWindow import UiMainWindow
from wss import WSThread, Worker, Senderq, WSSServer
import numpy as np
from threading import Lock
import queue


NUMTICKS = 128

class MainWindow(QMainWindow, UiMainWindow):
    version = '1.0.5'
    settings = QSettings("./config.ini", QSettings.IniFormat)   # файл настроек
    lock = Lock()

    listTick = np.zeros((NUMTICKS, 3), dtype=float)          #   массив последних тиков
    tickCounter = 0             #   счетчик тиков

    flConnect = False           #   флаг нормального соединения с сайтом

    hashpsw = {}
    pilots = {}

    def __init__(self):

        def opendb():
            fname = "./conf.db"
            if not os.path.exists(fname):
                return False
            self.db.setDatabaseName(fname)
            self.db.open()
            if self.db.isOpen():
                return True
            else:
                return False

        super().__init__()
        logging.basicConfig(filename='info.log', level=logging.INFO, format='%(asctime)s %(message)s')
        #  подключаем базу SQLite
        self.db = QSqlDatabase.addDatabase("QSQLITE", 'maindb')
        if not opendb():
            msg_box = QMessageBox()
            msg_box.setText("Ошибка открытия файла базы данных")
            msg_box.exec()
            sys.exit()

        self.fillhashpsw()
        self.fillpilots()


        # создание визуальной формы
        self.setupui(self)
        self.show()

        self.wssserver = WSSServer(self, self.pilots)
        self.wssserver.daemon = True
        self.wssserver.start()

        self.sendq = queue.Queue()

        self.dxthread = WSThread(self)
        self.dxthread.daemon = True
        self.dxthread.start()

        self.senderq = Senderq(self.sendq, self.dxthread)
        self.senderq.daemon = True
        self.senderq.start()
        #
        self.listf = {'index':{'q':queue.LifoQueue(), 'f':self.message_index},
                      'tradingStatus': {'q': queue.Queue(), 'f': self.message_tradingStatus},
                      'traderStatus': {'q': queue.Queue(), 'f': self.message_traderStatus}}
        self.listp = []
        for ch in self.listf.keys():
            p = Worker(self.listf[ch]['q'], self.listf[ch]['f'])
            self.listp.append(p)
            p.daemon = True
            p.start()
        #
        # self.intimer = InTimer(self)
        # self.intimer.daemon = True
        # self.intimer.start()
        #
        # self.animator = Animator(self)
        # self.animator.daemon = True
        # self.animator.start()
        #
        # self.analizator = Analizator(self.midvol)
        # self.analizator.daemon = True
        # self.analizator.start()

    def closeEvent(self, *args, **kwargs):
        if self.db.isOpen():
            self.db.close()

    def fillhashpsw(self):
        q1 = QSqlQuery(self.db)
        q1.prepare("SELECT * FROM clients")
        q1.exec_()
        while q1.next():
            self.hashpsw[q1.value(0)] = q1.value(1)

    def fillpilots(self):
        q1 = QSqlQuery(self.db)
        q1.prepare('SELECT login, name, apikey FROM pilots')
        q1.exec_()
        while q1.next():
            self.pilots[q1.value(0)] = {'name': q1.value(1), 'apikey': q1.value(2), 'status': 0, 'balance':0}

    def midvol(self):
        if self.tickCounter > NUMTICKS:
            self.lock.acquire()
            ar = np.array(self.listTick)
            self.lock.release()
            val = round(np.mean(ar, axis=0)[2], 2)
            npvar = round(np.var(ar, axis=0)[1], 3)
            self.l_midvol.setText(str(val))
            self.l_midvar.setText(str(npvar))

    # ========== обработчики сообщений ===========
    # ==== публичные сообщения
    def message_index(self, data):
        self.lock.acquire()
        self.tickCounter += 1
        self.lock.release()

    def message_tradingStatus(self, data):
        pass

    def message_traderStatus(self, data):
        pass

app = QApplication([])
win = MainWindow()
sys.exit(app.exec_())
