# модуль главного окна
from PyQt5.QtCore import Qt, pyqtSlot, QRectF
from PyQt5.QtWidgets import QWidget, QGridLayout, QStatusBar, QHBoxLayout, QPushButton, QLabel, QSplitter, QOpenGLWidget, QSizePolicy, QGroupBox, QTableView, QAbstractItemView, QHeaderView, QCheckBox
from PyQt5.QtGui import QIcon, QPainter, QStandardItemModel, QStandardItem, QPen, QColor, QFont, QPainterPath, QMouseEvent
from OpenGL import GL
import time

class UiMainWindow(object):
    def __init__(self):
        self.buttonlist = []
        self.numcontbuttonlist = []

    def setupui(self, mainwindow):
        mainwindow.setObjectName("MainWindow")
        mainwindow.setWindowTitle('DLM Core v ' + mainwindow.version)
        mainwindow.resize(320, 120)

        self.centralwidget = QWidget(mainwindow)
        self.centralwidget.setObjectName("centralwidget")
        mainwindow.setCentralWidget(self.centralwidget)

        self.gridLayout = QGridLayout(self.centralwidget)
        self.gridLayout.setContentsMargins(1, 1, 1, 1)
        self.gridLayout.setObjectName("gridLayout")

        self.pb_enter = QPushButton()
        self.pb_enter.setText('вход не выполнен')
        self.pb_enter.setStyleSheet("color:rgb(255, 96, 96); font: bold 12px;border: none")
        self.pb_enter.setCursor(Qt.PointingHandCursor)
        self.gridLayout.addWidget(self.pb_enter, 0, 0, 1, 1)
        self.pb_enter.clicked.connect(self.buttonLogin_clicked)