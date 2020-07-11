import sys
import logging
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtCore import pyqtSlot
from myfinance.kiwoom import KWcomm
import myfinance.static as stt
import myfinance.GUI_components as GuiC


class FinanceWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyStock")
        self.setGeometry(300, 100, 1200, 800)
        self.logger = logging.getLogger('AutoTradeLogger')
        self.set_logger(log_filename=f'{stt.timestamp_kw_str(pd.Timestamp.now())}_AutoTrade.log')
        self.kwAPI = KWcomm()
        self.req_no = 0
        self.code_interested = set()
        self.btn_login = GuiC.TwoStatesToggleButton(['Login', 'Logout'])
        self.btn_login.clicked.connect(self.login_logout)
        self.data_txt = QTextEdit('')
        self.edit_status = QLineEdit('Auto Trading UI')
        self.edit_status.setReadOnly(True)
        self.data_txt.setReadOnly(True)
        self.data_txt.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.txt_scroll = ''
        self.man_order = GuiC.ManualOrder()
        self.tabwidget = QTabWidget()
        self.stock_list_table = GuiC.StockDataTable()
        self.order_list_table = GuiC.StockDataTable(header=stt.LIST_contract_stock)
        self.tabwidget.addTab(self.stock_list_table, 'Interested Stocks')
        self.tabwidget.addTab(self.order_list_table, 'Placed Orders')

        leftLayOut = QVBoxLayout()
        leftLayOut.addWidget(self.btn_login)
        leftLayOut.addWidget(self.edit_status)
        leftLayOut.addWidget(self.data_txt)
        middleLayOut = QHBoxLayout()
        middleLayOut.addLayout(leftLayOut)
        middleLayOut.addWidget(self.man_order)
        verLayOut = QVBoxLayout()
        verLayOut.addLayout(middleLayOut)
        verLayOut.addWidget(self.tabwidget)

        centralwidget = QWidget()
        centralwidget.setLayout(verLayOut)
        self.setCentralWidget(centralwidget)
        self.init_kiwoom()

        self.prediction = GuiC.PredictionAnalyzer()
        if not self.prediction.isnone:
            self.class_0 = self.prediction.get_stocklist_by_class(self.prediction.CLASS_0)
            self.class_1 = self.prediction.get_stocklist_by_class(self.prediction.CLASS_1)
            self.add_list_to_code_interested(self.class_0 + self.class_1)

        self.login_logout(True)
        self.show()

    def set_logger(self, log_filename='AutoTrade.log'):
        self.logger.setLevel(logging.DEBUG)
        file_handler = logging.FileHandler(log_filename)
        stream_handler = logging.StreamHandler()
        self.logger.addHandler(file_handler)
        self.logger.addHandler(stream_handler)
        self.logger.info('--' * 12)
        self.logger.info(f'Auto Trading Management App. : {pd.Timestamp.now()}')

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

    def add_list_to_code_interested(self, code_list):
        self.code_interested = self.code_interested.union(set(code_list))

    def add_str_to_code_interested(self, code):
        self.code_interested.add(code)

    @pyqtSlot(str)
    def error_popup(self, error_msg):
        self.logger.error(f'{pd.Timestamp.now()} : {error_msg}')
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
        else:
            qApp.exit(0)

    @pyqtSlot(str)
    def find_stock_name_from_code(self, code_str):
        code_name = self.kwAPI.get_code_name(code_str)
        self.man_order.set_stock_name(code_name)

    @pyqtSlot(dict)
    def arrange_data_dict(self, data_dict):
        codes = data_dict['code']
        query_all = False
        code_diff = set(codes).difference(self.code_interested)
        if len(code_diff) > 0:
            query_all = True
            self.add_list_to_code_interested(codes)
        self.stock_list_table.update_data(self.kwAPI.get_stock_table())
        self.order_list_table.update_data(self.kwAPI.get_contract_list())
        if query_all:
            self.kwAPI.get_interested_stock_info(list(self.code_interested))

    @pyqtSlot(dict)
    def arrange_orders(self, order_dict):
        codes = order_dict['data']['종목코드'].to_list()
        query_all = False
        code_diff = set(codes).difference(self.code_interested)
        if len(code_diff) > 0:
            query_all = True
            self.add_list_to_code_interested(codes)
        self.order_list_table.update_data(self.kwAPI.get_contract_list())
        if query_all:
            self.kwAPI.get_interested_stock_info(list(self.code_interested))

    @pyqtSlot(str)
    def status_update(self, inputstr):
        self.edit_status.setText(inputstr)
        self.logger.info(f'{pd.Timestamp.now()} : {inputstr}')

    @pyqtSlot(str)
    def progress_update(self, inputstr):
        self.data_txt.append(inputstr)
        self.logger.info(f'{pd.Timestamp.now()} : {inputstr}')

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
        self.code_interested.add(code_str)
        self.kwAPI.get_interested_stock_info(self.code_interested)

    @pyqtSlot(dict)
    def update_history(self, data_dict):
        data_frame = data_dict['data']
        self.progress_update(f'{data_frame}')


if __name__ == "__main__":
    app = QApplication(sys.argv)
    myWindow = FinanceWindow()
    sys.exit(app.exec_())
