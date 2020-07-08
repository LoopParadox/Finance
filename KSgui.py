import sys
import threading
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QAxContainer import *
from PyQt5.QtCore import pyqtSlot, QCoreApplication
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


class FinanceWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyStock")
        self.setGeometry(300, 100, 1200, 800)
        self.kwAPI = KWcomm()
        self.req_no = 0
        self.code_interested = []

        self.index_list_world = StLib.StockList('index')
        self.taskcode = 0
        self._task_thread = threading.Thread(target=self._thread)
        self.index_list_kor = StLib.StockList('ind_kor')
        self.korea_list = StLib.StockList('Korea')
        self.index_list_world.status_update.connect(self.progress_update)

        self.btn_login = GuiC.TwoStatesToggleButton(['Login', 'Logout'])
        self.btn_login.clicked.connect(self.login_logout)
        btn_index_world = QPushButton("Update Worldwide Index", self)
        btn_index_world.clicked.connect(self.update_index_world)
        btn_index_korea = QPushButton("Update Korean Index", self)
        btn_index_korea.clicked.connect(self.update_index_korea)
        btn_stock_korea = QPushButton("Update Korean Stock", self)
        btn_stock_korea.clicked.connect(self.update_stock_korea)
        self.data_txt = QTextEdit('')
        self.edit_status = QLineEdit('Auto Trading UI')
        self.edit_status.setReadOnly(True)
        self.data_txt.setReadOnly(True)
        self.data_txt.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.txt_scroll = ''
        self.man_order = GuiC.ManualOrder()
        self.tabwidget = QTabWidget()
        self.stock_list_table = GuiC.StockDataTable()
        self.order_list_table = GuiC.StockDataTable(header=kwconst.LIST_contract_stock)
        self.tabwidget.addTab(self.stock_list_table, 'Interested Stocks')
        self.tabwidget.addTab(self.order_list_table, 'Placed Orders')

        topLayOut = QHBoxLayout()
        topLayOut.addWidget(self.btn_login)
        topLayOut.addWidget(btn_index_world)
        topLayOut.addWidget(btn_index_korea)
        topLayOut.addWidget(btn_stock_korea)

        leftLayOut = QVBoxLayout()
        leftLayOut.addWidget(self.edit_status)
        leftLayOut.addWidget(self.data_txt)
        middleLayOut = QHBoxLayout()
        middleLayOut.addWidget(self.man_order)
        middleLayOut.addLayout(leftLayOut)
        verLayOut = QVBoxLayout()
        verLayOut.addLayout(topLayOut)
        verLayOut.addLayout(middleLayOut)
        verLayOut.addWidget(self.tabwidget)

        centralwidget = QWidget()
        centralwidget.setLayout(verLayOut)
        self.setCentralWidget(centralwidget)
        self.init_kiwoom()
        self.show()

    def init_kiwoom(self):
        self.kwAPI.status_signal.connect(self.status_update)
        self.kwAPI.error_signal.connect(self.error_popup)
        self.kwAPI.login_signal.connect(self.login_status_changed)
        self.kwAPI.progress_signal.connect(self.progress_update)
        self.kwAPI.data_dict.connect(self.arrange_data_dict)
        self.kwAPI.account_data.connect(self.man_order.set_account_information)
        self.kwAPI.order_data.connect(self.arrange_orders)
        self.kwAPI.history_data.connect(self.update_history)
        self.man_order.changed_code.connect(self.find_stock_name_from_code)
        self.man_order.signal_add.connect(self.query_stock_code)
        self.man_order.signal_order.connect(self.kwAPI.send_order_dict)
        self.stock_list_table.selected_row_data.connect(self.man_order.set_input_arguments)
        self.order_list_table.selected_row_data.connect(self.man_order.set_input_arguments)

    @pyqtSlot(str)
    def error_popup(self, error_msg):
        QMessageBox.about(self, 'Error Message', error_msg)

    @pyqtSlot(bool)
    def login_status_changed(self, islogin):
        self.btn_login.change_status(islogin)
        if islogin:
            self.man_order.set_account_list(self.kwAPI.list_account)
            self.man_order.add_code_list(self.kwAPI.get_stock_list())
            self.kwAPI.query_account_evaluation()
            self.kwAPI.query_holding_stocks()
            self.kwAPI.query_orders_not_contracted()

    @pyqtSlot(str)
    def find_stock_name_from_code(self, code_str):
        code_name = self.kwAPI.get_code_name(code_str)
        self.man_order.set_stock_name(code_name)

    @pyqtSlot(dict)
    def arrange_data_dict(self, data_dict):
        codes = data_dict['code']
        query_all = False
        for code in codes:
            if code not in self.code_interested:
                self.code_interested.append(code)
                query_all = True
        self.stock_list_table.update_data(self.kwAPI.get_stock_table())
        self.order_list_table.update_data(self.kwAPI.get_contract_list())
        if query_all:
            self.kwAPI.get_intersted_stock_info(self.code_interested)

    @pyqtSlot(dict)
    def arrange_orders(self, order_dict):
        self.order_list_table.update_data(self.kwAPI.get_contract_list())
        # order_code = self.kwAPI.contract_list.get_current_stock_codes()
        # code_list = self.code_interested + order_code
        # ex_list = list(set(code_list))
        # print(self.code_interested, ex_list)
        # if len(ex_list) > len(self.code_interested):
        #     self.kwAPI.get_intersted_stock_info(ex_list)

    @pyqtSlot(str)
    def status_update(self, inputstr):
        self.edit_status.setText(inputstr)

    @pyqtSlot(str)
    def progress_update(self, inputstr):
        self.data_txt.append(inputstr)

    @pyqtSlot(str)
    def data_update(self, inputstr):
        self.txt_scroll = self.txt_scroll + inputstr + '\n'
        self.data_txt.setPlainText(self.txt_scroll)
        self.data_txt.verticalScrollBar().setValue(self.data_txt.verticalScrollBar().maximum())

    @pyqtSlot(bool)
    def login_logout(self, login):
        if login:
            self.status_update('Logging in to Kiwoom Server...')
            self.kwAPI.loginAPI()
        else:
            self.kwAPI.logoutAPI()
            # QCoreApplication.instance().quit()

    def data_window_reset(self):
        self.txt_scroll = ''
        self.data_txt.setPlainText(self.txt_scroll)

    @pyqtSlot(str)
    def query_stock_code(self, code_str):
        if code_str not in self.code_interested:
            self.code_interested.append(code_str)
        self.kwAPI.get_intersted_stock_info(self.code_interested)

    @pyqtSlot(dict)
    def update_history(self, data_dict):
        data_frame = data_dict['data']
        self.progress_update(f'{data_frame}')

    @pyqtSlot()
    def update_index_world(self):
        self.taskcode = 0
        self._task_thread.start()

    def __task_world(self):
        self.index_list_world.update_list_yf('index_list.csv')
        self.taskcode = -1
        return

    def _thread(self):
        if self.taskcode < 0:
            return
        elif self.taskcode == 0:
            self.__task_world()

    @pyqtSlot()
    def update_index_korea(self):
        if self.kwAPI.islogin:
            code_list = self.index_list_kor.kw_index_codes_update('index_kor_list.csv')
            latest_list = self.index_list_kor.get_latest_updated_dates_from_codes(code_list)
            today = stt.timestamp_ref_date()
            self.kwAPI.call_daily_index_list(code_list, today, latest_list)
        else:
            self.error_popup('You should log in to Kiwoom API server.')

    @pyqtSlot()
    def update_stock_korea(self):
        if self.kwAPI.islogin:
            code_list = self.korea_list.kw_stock_codes_update('korea_stocklist.csv')
            latest_list = self.korea_list.get_latest_updated_dates_from_codes(code_list)
            today = stt.timestamp_ref_date()
            self.kwAPI.call_daily_price_list(code_list, today, latest_list)
        else:
            self.error_popup('You should log in to Kiwoom API server.')


if __name__ == "__main__":
    app = QApplication(sys.argv)
    myWindow = FinanceWindow()
    sys.exit(app.exec_())
