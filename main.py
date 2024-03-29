import sys
import os
import logging
import queue

from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox
from PyQt5.QtCore import QSettings, pyqtSlot
from PyQt5.QtSql import QSqlDatabase, QSqlQuery
from mainWindow import UiMainWindow

from wssserver import WSSServer
from wssclient import WSSClient, FromQToF, TimeToF

from threading import Lock
from loginWindow import LoginWindow
import bcrypt   #pip install bcrypt
import hashlib
from Cryptodome.Cipher import AES # pip install pycryptodome
import numpy as np

NUMTICKS = 128


class MainWindow(QMainWindow, UiMainWindow):

    settings = QSettings("./config.ini", QSettings.IniFormat)
    serveraddress = settings.value('serveraddress')
    serverport = settings.value('serverport')

    version = '1.3.2'
    lock = Lock()

    hashpsw = {}
    pilots = {}
    rockets = {}

    rel = {'.DGTXBTCUSD':'BTCUSD-PERP', '.DGTXETHUSD':'ETHUSD-PERP'}
    expanses = {'BTCUSD-PERP':np.zeros(shape=(NUMTICKS, 1), dtype=float), 'ETHUSD-PERP':np.zeros(shape=(NUMTICKS, 1), dtype=float)}

    psw = None


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
        logging.basicConfig(filename='info.log', level=logging.CRITICAL, format='%(asctime)s %(message)s')
        #  подключаем базу SQLite
        self.db = QSqlDatabase.addDatabase("QSQLITE", 'maindb')
        if not opendb():
            msg_box = QMessageBox()
            msg_box.setText("Ошибка открытия файла базы данных")
            msg_box.exec()
            sys.exit()

        self.fillhashpsw()

        # создание визуальной формы
        self.setupui(self)
        self.show()

    def closeEvent(self, *args, **kwargs):
        if self.db.isOpen():
            self.db.close()

    def fillhashpsw(self):
        q1 = QSqlQuery(self.db)
        q1.prepare("SELECT * FROM clients")
        q1.exec_()
        while q1.next():
            self.hashpsw[q1.value(0)] = q1.value(1)

    def getak(self, ak):
        IV_SIZE = 16  # 128 bit, fixed for the AES algorithm
        KEY_SIZE = 32  # 256 bit meaning AES-256, can also be 128 or 192 bits
        SALT_SIZE = 16  # This size is arbitrary
        en_ak_int = int(ak)
        en_ak_byte = en_ak_int.to_bytes((en_ak_int.bit_length() + 7) // 8, sys.byteorder)
        salt = en_ak_byte[0:SALT_SIZE]
        derived = hashlib.pbkdf2_hmac('sha256', self.psw.encode('utf-8'), salt, 100000,
                                      dklen=IV_SIZE + KEY_SIZE)
        iv = derived[0:IV_SIZE]
        key = derived[IV_SIZE:]
        ak_enc = AES.new(key, AES.MODE_CFB, iv).decrypt(en_ak_byte[SALT_SIZE:]).decode('utf-8')
        return ak_enc

    def checkpsw(self, psw):
        if bcrypt.checkpw(psw.encode('utf-8'), self.hashpsw['core'].encode('utf-8')):
            #   если пароль прошел проверку
            self.pb_enter.setText('вход выполнен: ')
            self.pb_enter.setStyleSheet("color:rgb(64, 192, 64); font: bold 12px;border: none")
            self.psw = psw

            #   запускаем websocket-сервер
            self.wssserver = WSSServer(self)
            self.wssserver.daemon = True
            self.wssserver.start()

            # -----------------------------------------------------------------------

            corereceiveq = queue.Queue()
            serveraddress = 'ws://'+self.serveraddress+':'+self.serverport
            self.wsscore = WSSClient(corereceiveq, serveraddress)
            self.wsscore.daemon = True
            self.wsscore.start()

            self.corereceiver = FromQToF(self.receivemessagefromcore, corereceiveq)
            self.corereceiver.daemon = True
            self.corereceiver.start()

            self.coresendq = queue.Queue()
            self.coresender = FromQToF(self.wsscore.send, self.coresendq)
            self.coresender.daemon = True
            self.coresender.start()

            # -----------------------------------------------------------------------

            dgtxreceiveq = queue.Queue()

            self.wssdgtx = WSSClient(dgtxreceiveq, "wss://ws.mapi.digitexfutures.com")
            self.wssdgtx.daemon = True
            self.wssdgtx.start()

            self.dgtxreceiver = FromQToF(self.receivemessagefromdgtx, dgtxreceiveq)
            self.dgtxreceiver.daemon = True
            self.dgtxreceiver.start()

            self.dgtxsendq = queue.Queue()

            self.dgtxsender = FromQToF(self.wssdgtx.send, self.dgtxsendq)
            self.dgtxsender.daemon = True
            self.dgtxsender.start()
            # -----------------------------------------------------------------------
            self.timetof = TimeToF(self.market_analizator, 1)
            self.timetof.daemon = True
            self.timetof.start()

        else:
            self.pb_enter.setText('вход не выполнен')
            self.pb_enter.setStyleSheet("color:rgb(255, 96, 96); font: bold 12px;border: none")

    def receivemessagefromcore(self, mes):
        command = mes.get('command')
        if command == 'on_open':
            q1 = QSqlQuery(self.db)
            q1.prepare('SELECT login, name, apikey FROM pilots')
            q1.exec_()
            pilots = {}
            while q1.next():
                login = q1.value(0)
                name = q1.value(1)
                ak = self.getak(q1.value(2))
                pilots[login] = {'name':name, 'ak':ak}
            data = {'command': 'sc_pilotsinfo', 'pilots': pilots}
            self.coresendq.put(data)

    def receivemessagefromdgtx(self, mes):
        ch = mes.get('ch')
        if ch == 'index':
            data = mes.get('data')
            indexSymbol = data.get('indexSymbol')
            self.dgtxindex(self.rel.get(indexSymbol), data.get('spotPx'))
        elif ch == 'on_open':
            params = []
            for expanse in self.expanses.keys():
                params.append(expanse + '@index')
            data = {'id': 1, 'method': 'subscribe', 'params': params}
            self.dgtxsendq.put(data)

    @pyqtSlot()
    def buttonLogin_clicked(self):
        #   если еще не авторизован - вызываем окно авторизации
        if not self.psw:
            rw = LoginWindow()
            rw.userlogined.connect(lambda: self.checkpsw(rw.psw))
            rw.setupUi()
            rw.exec_()

    def dgtxindex(self, symbol, spotPx):
        self.lock.acquire()
        ar = self.expanses[symbol]
        res = np.empty_like(ar)
        res[:-1] = ar[1:]
        res[-1] = spotPx
        self.expanses[symbol] = res
        self.lock.release()

    def market_analizator(self):
        if self.wsscore.flConnect:
            for expanse in self.expanses.keys():
                self.lock.acquire()
                ar = np.array(self.expanses[expanse])
                self.lock.release()
                ar = np.absolute(ar[1:] - ar[:-1])
                market_volatility_128 = round(np.mean(ar), 3)
                data = {'command': 'sc_marketinfo', 'info': {'symbol': expanse, 'market_volatility_128': market_volatility_128}}
                self.coresendq.put(data)


app = QApplication([])
win = MainWindow()
sys.exit(app.exec_())
