import sys
import os
import logging

from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox
from PyQt5.QtCore import QSettings, pyqtSlot
from PyQt5.QtSql import QSqlDatabase, QSqlQuery
from mainWindow import UiMainWindow
from wss import DGTXIndex, DGTXBalance, WSSServer
import numpy as np
from threading import Lock
from loginWindow import LoginWindow
import bcrypt   #pip install bcrypt
import hashlib
from Crypto.Cipher import AES # pip install pycryptodome


NUMTICKS = 128

class MainWindow(QMainWindow, UiMainWindow):
    version = '1.0.6'
    settings = QSettings("./config.ini", QSettings.IniFormat)   # файл настроек
    lock = Lock()

    hashpsw = {}
    pilots = {}
    expanses = {'BTCUSD-PERP':None, 'ETHUSD-PERP':None}
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
        logging.basicConfig(filename='info.log', level=logging.INFO, format='%(asctime)s %(message)s')
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

    def fillpilots(self):
        q1 = QSqlQuery(self.db)
        q1.prepare('SELECT login, name, apikey FROM pilots')
        q1.exec_()
        while q1.next():
            login = q1.value(0)
            name = q1.value(1)
            ak = self.getak(q1.value(2))
            dgtxbalance = DGTXBalance(self, login, ak, self.expanses)
            dgtxbalance.daemon = True
            dgtxbalance.start()
            self.pilots[login] = {'name': name, 'ak':ak, 'status': 0, 'agent':dgtxbalance, 'info':{}}

    def fillexpanses(self):
        for expanse in self.expanses.keys():
            dgtxindex = DGTXIndex(self, expanse)
            dgtxindex.daemon = True
            dgtxindex.start()
            self.expanses[expanse] = dgtxindex

    def checkpsw(self, psw):
        if bcrypt.checkpw(psw.encode('utf-8'), self.hashpsw['core'].encode('utf-8')):
            self.pb_enter.setText('вход выполнен: ')
            self.pb_enter.setStyleSheet("color:rgb(64, 192, 64); font: bold 12px;border: none")
            self.psw = psw
            self.fillpilots()
            self.fillexpanses()
            self.wssserver = WSSServer(self)
            self.wssserver.daemon = True
            self.wssserver.start()
        else:
            self.pb_enter.setText('вход не выполнен')
            self.pb_enter.setStyleSheet("color:rgb(255, 96, 96); font: bold 12px;border: none")

    @pyqtSlot()
    def buttonLogin_clicked(self):
        rw = LoginWindow()
        rw.userlogined.connect(lambda: self.checkpsw(rw.psw))
        rw.setupUi()
        rw.exec_()


app = QApplication([])
win = MainWindow()
sys.exit(app.exec_())
