import sys
import threading
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QAxContainer import *
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QObject, QTimer, QCoreApplication
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as ptch
from datetime import datetime
from myfinance.kiwoom import KWcomm
import myfinance.constants as kwconst
import myfinance.QTstocklist as StLib
import myfinance.GUI_components as GuiC
from myfinance.que_control import Que_element, Que_Temp
import myfinance.static as stt
import time


class FinanceWindow(QObject):
    EXIT_CODE_DONE = 0
    EXIT_CODE_REBOOT = -1

    def __init__(self):
        super().__init__()
        self.kwAPI = KWcomm()
        self.req_no = 0
        self.code_interested = []

        self.index_list_world = StLib.StockList('index')
        self.taskcode = 0
        self.index_list_kor = StLib.StockList('ind_kor')
        self.korea_list = StLib.StockList('Korea')
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.quit)
        self.timer.start()

    @pyqtSlot()
    def quit(self):
        qApp.exit(self.EXIT_CODE_DONE)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    myWindow = FinanceWindow()
    sys.exit(app.exec_())
