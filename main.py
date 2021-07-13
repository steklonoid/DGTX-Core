import sys
import os
import logging

from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox
from PyQt5.QtCore import QSettings
from PyQt5.QtSql import QSqlDatabase, QSqlQuery
from mainWindow import UiMainWindow
from wss import DGTXIndex, DGTXBalances, WSSServer
import numpy as np
from threading import Lock


NUMTICKS = 128

class MainWindow(QMainWindow, UiMainWindow):
    version = '1.0.6'
    settings = QSettings("./config.ini", QSettings.IniFormat)   # файл настроек
    lock = Lock()

    hashpsw = {}
    pilots = {}

    exlist = ['BTCUSD-PERP', 'ETHUSD-PERP']

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

        self.dgtxbalances = DGTXBalances(self)
        self.dgtxbalances.daemon = True
        self.dgtxbalances.start()

        self.dgtxindex = []
        for ex in self.exlist:
            dgtxindex = DGTXIndex(self, ex)
            dgtxindex.daemon = True
            dgtxindex.start()
            self.dgtxindex.append(dgtxindex)

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


app = QApplication([])
win = MainWindow()
sys.exit(app.exec_())
