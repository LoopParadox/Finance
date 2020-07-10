import sys
import pandas as pd
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QAxContainer import *
from PyQt5.QtCore import pyqtSignal, QObject, QTimer, pyqtSlot
from datetime import datetime
import myfinance.constants as kwconst
import myfinance.QTstocklist as StLib
from myfinance.que_control import Que_element, Que_Temp
import myfinance.static as stt
import time
import threading
import os
import logging


class EventForward(QObject):
    GoFoward = pyqtSignal()
    HoldOn = pyqtSignal()


class AutoCommander(QObject):
    def __init__(self):
        super().__init__()
        self.timer = QTimer(self)


class FinanceWindow(QMainWindow):
    EXIT_CODE_NORMAL = 0
    EXIT_CODE_REBOOT = -1
    EXIT_CODE_CONTINUE = 1
    KEY_CONTINUE = 'continue'
    KEY_LATEST = 'latest'
    KEY_SHUTDOWN = 'shutdown'

    task_done = pyqtSignal()
    next_que = pyqtSignal()
    hold_on = pyqtSignal()
    continue_task = pyqtSignal()
    status_file = 'status.dat'
    update_status = pd.Series({KEY_CONTINUE: 0, KEY_LATEST: pd.Timestamp(0), KEY_SHUTDOWN: 0})

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger('StockUpdateLogger')
        self.set_logger()
        self.setWindowTitle("PyStock")
        self.setGeometry(300, 300, 800, 800)
        self._task_thread = threading.Thread(target=self._thread)
        self.taskcode = -1
        self.index_list_world = StLib.StockList('index')
        self.index_list_kor = StLib.StockList('ind_kor')
        self.korea_list = StLib.StockList('Korea')
        self.index_list_kor.status_update.connect(self.status_update)
        self.index_list_world.status_update.connect(self.status_update)
        self.korea_list.status_update.connect(self.status_update)
        self.index_list_kor.error_signal.connect(self.log_error)
        self.index_list_world.error_signal.connect(self.log_error)
        self.korea_list.error_signal.connect(self.log_error)
        self.kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self.kiwoom.OnEventConnect.connect(self.event_connect)
        self.kiwoom.OnReceiveTrData.connect(self.receive_trdata)
        self.task_done.connect(self.log_task_done)
        self.next_que.connect(self.next_task)
        self.hold_on.connect(self.hold_awhile)
        self.continue_task.connect(self.continue_prev_task)
        # self.forwardevent = EventForward()
        # self.forwardevent.GoFoward.connect(self.next_task)
        # self.forwardevent.HoldOn.connect(self.hold_awhile)
        self.que = Que_Temp()
        self.islogin = False
        self.req_no = 0
        self.timer = QTimer(self)
        self.timer.setInterval(100000)
        self.timer.timeout.connect(self.loginTimer)
        self.ticktime = pd.Timestamp(datetime.now())
        self.timeroff = 0
        self.holdsec = 0
        self.timer_running = False

        self.btn_login = QPushButton("Login", self)
        self.btn_login.setFixedWidth(250)
        self.btn_login.clicked.connect(self.loginAPI)
        btn_update_kor = QPushButton("Update Korean StockData", self)
        btn_update_kor.clicked.connect(self.update_kor)
        btn_world_index = QPushButton("Update World index", self)
        btn_world_index.clicked.connect(self._task_wup)
        btn_korea_index = QPushButton("Update Korea index", self)
        btn_korea_index.clicked.connect(self.update_korea_index)
        lbl_request = QLabel('Request No.')
        self.cbx_shutdown = QCheckBox('Auto_shutdown')
        self.cbx_shutdown.stateChanged.connect(self.set_auto_shutdown)
        self.edit_request = QLineEdit('0')
        # self.edit_request.setFixedWidth(100)
        self.edit_status = QTextEdit('Stock price update UI\n')
        self.edit_status.setReadOnly(True)

        request_label = QWidget()
        reqlayout = QHBoxLayout()
        reqlayout.addWidget(lbl_request)
        reqlayout.addWidget(self.edit_request)
        request_label.setLayout(reqlayout)
        toplayout = QHBoxLayout()
        toplayout.setSpacing(50)
        toplayout.addWidget(self.btn_login)
        toplayout.addWidget(request_label)
        toplayout.addWidget(self.cbx_shutdown)
        btnlayout = QHBoxLayout()
        btnlayout.addWidget(btn_update_kor)
        btnlayout.addWidget(btn_world_index)
        btnlayout.addWidget(btn_korea_index)

        centerlayout = QVBoxLayout()
        centerlayout.addLayout(toplayout)
        centerlayout.addLayout(btnlayout)
        centerlayout.addWidget(self.edit_status)
        centralwidget = QWidget()
        centralwidget.setLayout(centerlayout)
        self.setCentralWidget(centralwidget)
        self.show()
        if self.load_status():
            self.continue_task.emit()

    def set_logger(self, log_filename='StockUpdate.log'):
        self.logger.setLevel(logging.DEBUG)
        file_handler = logging.FileHandler(log_filename)
        stream_handler = logging.StreamHandler()
        self.logger.addHandler(file_handler)
        self.logger.addHandler(stream_handler)
        self.logger.info('--' * 12)
        self.logger.info(f'Stock Price Update App. : {pd.Timestamp.now()}')

    @pyqtSlot(str)
    def log_error(self, error_msg):
        self.logger.error(f'Error_occured({kwconst.Err_stocklist}) : {error_msg}')

    @pyqtSlot()
    def log_task_done(self):
        time_now = pd.Timestamp.now()
        self.logger.info(f'{time_now} : Task done successfully')
        self.update_status[self.KEY_LATEST] = time_now
        if self.update_status[self.KEY_CONTINUE] == 0:
            if self.update_status[self.KEY_SHUTDOWN] > 0:
                self.update_status[self.KEY_SHUTDOWN] = 0
                self.close_normal()

    def init_status(self):
        self.update_status = pd.Series({self.KEY_CONTINUE: 0, self.KEY_LATEST: pd.Timestamp(0), self.KEY_SHUTDOWN: 0})

    def load_status(self):
        if os.path.isfile(self.status_file):
            self.update_status = pd.read_pickle(self.status_file)
            if self.update_status[self.KEY_SHUTDOWN] == 1:
                self.cbx_shutdown.setChecked(True)
            else:
                self.cbx_shutdown.setChecked(False)
            return True
        else:
            return False

    def save_status(self):
        self.update_status.to_pickle(self.status_file)

    @pyqtSlot()
    def continue_prev_task(self):
        if self.islogin:
            if self.update_status[self.KEY_CONTINUE] == 1:
                self.update_kor()
            if self.update_status[self.KEY_CONTINUE] == 2:
                self.update_world_index()
                self.update_korea_index()
                self.update_kor()
        else:
            if self.update_status[self.KEY_CONTINUE] > 0:
                self.logger.info(f'{pd.Timestamp.now()} : Continue to update Korean Stock prices')
                self.loginAPI()

    @pyqtSlot()
    def set_auto_shutdown(self):
        self.update_status[self.KEY_SHUTDOWN] = self.cbx_shutdown.isChecked()*1

    def restart(self):
        self.save_status()
        qApp.exit(self.EXIT_CODE_REBOOT)

    def close_app_with_continue_msg(self):
        self.update_status[self.KEY_CONTINUE] = 1
        self.save_status()
        self.logger.info(f'{pd.Timestamp.now()} : Close the app (continue)')
        qApp.exit(self.EXIT_CODE_CONTINUE)

    def close_normal(self):
        self.update_status[self.KEY_CONTINUE] = 0
        self.save_status()
        self.logger.info(f'{pd.Timestamp.now()} : Close the app (normal)')
        qApp.exit(self.EXIT_CODE_NORMAL)

    def closeEvent(self, event):
        self.close_normal()

    @pyqtSlot(str)
    def status_update(self, inputstr):
        if self.timer_running:
            self.edit_status.setPlainText(inputstr)
        else:
            self.edit_status.append(inputstr)

    def _thread(self):
        if self.taskcode < 0:
            return
        elif self.taskcode == 0:
            self.update_world_index()

    def _task_wup(self):
        self.taskcode = 0
        self._task_thread.start()

    def status_window_reset(self):
        self.edit_status.setPlainText('')

    def loginAPI(self):
        try:
            if not self.islogin:
                self.kiwoom.dynamicCall("CommConnect()")
                self.islogin = True
                self.req_no = 1
        except Exception as e:
            self.logger.error(f'Error occured({kwconst.Err_login}) : {e}')
            raise

    def logoutAPI(self):
        if self.islogin:
            self.kiwoom.dynamicCall("CommTerminate()")
            self.islogin = False
            self.status_update('Log out success')

    def hold_awhile(self):
        if self.timeroff == 2:
            self.ticktime = pd.Timestamp(datetime.now())
            self.timeroff = 0
        elif self.timeroff == 1:
            self.status_update('Hold on for 5 sec to log in')
            time.sleep(5)
            self.ticktime = pd.Timestamp(datetime.now())
            self.timeroff = 0
        elif self.req_no > 998:
            self.close_app_with_continue_msg()
            return
        elif self.req_no % 68 == 0:
            deltatime = pd.Timestamp(datetime.now()) - self.ticktime
            self.holdsec = int(70 - deltatime.seconds + 1)
            if self.holdsec < 0:
                self.holdsec = 0
            self.timer_running = True
            self.status_update('Hold on for ' + str(self.holdsec) + ' sec to avoid the request limitation')
            self.timer.setInterval(1000)
            self.timeroff = 3
            self.timer.start()
            return
        elif self.req_no % 4 == 0:
            time.sleep(1)
        self.req_no = self.req_no + 1
        self.edit_request.setText(str(self.req_no))
        self.next_que.emit()

    def loginTimer(self):
        if self.timeroff == 3:
            self.holdsec = self.holdsec - 1
            if self.holdsec < 0:
                self.status_window_reset()
                self.timer.stop()
                self.timer_running = False
                self.timeroff = 2
                self.hold_on.emit()
            else:
                self.status_update('Hold on for ' + str(self.holdsec) + ' sec to avoid the request limitation')
        else:
            self.status_window_reset()
            self.timer.stop()
            if self.islogin:
                self.timeroff = 2
            else:
                self.loginAPI()
                self.timeroff = 1
            self.hold_on.emit()

    def next_task(self):
        if self.que.status < 1:
            self.status_update('Task Done')
            self.task_done.emit()
            return
        que_temp = self.que.pop_first()
        if que_temp.task == 1:
            self.status_update('Call the server for the basic information of ' + que_temp.task_args[0])
            self.callBasicInfo_kw(que_temp.task_args[0])
        elif que_temp.task == 81:
            self.status_update('Call the server for the daily price of ' + que_temp.task_args[0])
            self.callDailyPrice_kw(que_temp.task_args[0], que_temp.task_args[1])
        elif que_temp.task == 20006:
            self.status_update('Call the server for the daily index of ' + que_temp.task_args[0])
            self.callDailyIndex_kw(que_temp.task_args[0], que_temp.task_args[1])
        elif que_temp.task == 60000:
            self.status_update(f'Call the server for the daily price of {que_temp.task_args[0]}')
            self.get_intersted_stock_info(que_temp.task_args[0])

    def event_connect(self, nErrCode):
        try:
            if nErrCode == 0:
                self.status_update('Login Success')
                self.logger.info(f'{pd.Timestamp.now()} : Login Success')
                self.btn_login.setText('Connected')
            elif nErrCode == 100:
                self.status_update("Failed to exchange user information")
                self.logger.error(f'{pd.Timestamp.now()} : Failed to exchange user information')
            elif nErrCode == 101:
                self.status_update("Failed to connect server")
                self.logger.error(f'{pd.Timestamp.now()} : Failed to connect server')
            elif nErrCode == 102:
                self.status_update("Failed to version update")
                self.logger.error(f'{pd.Timestamp.now()} : Failed to version update')
            if self.update_status[self.KEY_CONTINUE] > 0:
                self.continue_task.emit()
        except Exception as e:
            self.logger.error(f'Error occured({kwconst.Err_login}) : {e}')
            pass

    def update_kor(self):
        try:
            if not self.islogin:
                self.status_update('You should login Kiwoom APi firstly...')
                return
            self.status_update('Stock list update started...')
            code_list_normal = self.korea_list.kw_stock_codes_update('korea_stocklist.csv')
            self.status_update(f'You have {len(code_list_normal)} tickers to be updated.')
            self.logger.info(f'{pd.Timestamp.now()} : Update stock price ({len(code_list_normal)})')
            # code_list_normal, code_list_interested = self.korea_list.kw_stock_codes_update_interested('korea_stocklist.csv')
            # self.status_update(f'You have {len(code_list_normal)} and {len(code_list_interested)} tickers to be updated.')
            # self.logger.info(f'{pd.Timestamp.now()} : Update stock price ({len(code_list_normal)}+{len(code_list_interested)})')
            # self.que.gen_from_code_list(task=60000, code=code_list_interested)
            self.que.gen_from_code_list(task=81, code=code_list_normal)
            self.status_update('Que list generated.')
            self.ticktime = pd.Timestamp(datetime.now())
            if self.update_status[self.KEY_CONTINUE] > 0:
                self.update_status[self.KEY_CONTINUE] = 0
            self.next_task()
        except Exception as e:
            self.logger.error(f'Error occured({kwconst.Err_call}) : {e}')
            raise

    def update_korea_index(self):
        try:
            if not self.islogin:
                self.status_update('You should login Kiwoom APi firstly...')
                return
            self.status_update('Index list update started...')
            code_list = self.index_list_kor.kw_index_codes_update('index_kor_list.csv')
            self.status_update(f'You have {len(code_list)} tickers to be updated.')
            self.logger.info(f'{pd.Timestamp.now()} : Update index price ({len(code_list)})')
            self.que.gen_from_code_list(task=20006, code=code_list)
            self.status_update('Que list generated.')
            self.ticktime = pd.Timestamp(datetime.now())
            self.next_task()
        except Exception as e:
            self.logger.error(f'Error occured({kwconst.Err_call}) : {e}')
            raise

    def update_world_index(self):
        try:
            self.index_list_world.update_list_yf('index_list.csv')
            self.taskcode = -1
            self.task_done.emit()
            return
        except Exception as e:
            self.logger.error(f'Error occured({kwconst.Err_call}) : {e}')
            raise

    def get_intersted_stock_info(self, codelist):
        try:
            codeinput = ';'.join(codelist)
            codelength = len(codelist)
            return self.kiwoom.CommKwRqData(codeinput, False, codelength, 0, kwconst.TR_INTERESTS,
                                            kwconst.SCR_STOCK_PRICE_CUR)
        except Exception as e:
            self.logger.error(f'Error occured({kwconst.Err_kwcomm}) : {e}')
            raise

    def callBasicInfo_kw(self, code):
        try:
            # input parameters
            self.kiwoom.SetInputValue("종목코드", code)
            # sRQName, sTrCode, nPrevNext, sScreenNo
            res = self.kiwoom.CommRqData("opt10001", "opt10001", 0, "10001")
            return res
        except Exception as e:
            self.logger.error(f'Error occured({kwconst.Err_kwcomm}) : {e}')
            raise

    def callDailyPrice_kw(self, code, today, repeat=False):
        try:
            if repeat:
                rparg = 2
            else:
                rparg = 0
            # input parameters
            self.kiwoom.SetInputValue("종목코드", code)
            self.kiwoom.SetInputValue("기준일자", today)
            self.kiwoom.SetInputValue("수정주가구분", "0")
            # sRQName, sTrCode, nPrevNext, sScreenNo
            res = self.kiwoom.CommRqData("opt10081", "opt10081", rparg, "10081")
            return res
        except Exception as e:
            self.logger.error(f'Error occured({kwconst.Err_kwcomm}) : {e}')
            raise

    def callDailyIndex_kw(self, code, today, repeat=0):
        try:
            # input parameters
            self.kiwoom.SetInputValue("업종코드", code)
            self.kiwoom.SetInputValue("기준일자", today)
            # sRQName, sTrCode, nPrevNext, sScreenNo
            res = self.kiwoom.CommRqData("opt20006", "opt20006", repeat, "20006")
            return res
        except Exception as e:
            self.logger.error(f'Error occured({kwconst.Err_kwcomm}) : {e}')
            raise

    def receive_trdata(self, sScrNo, sRQName, sTrCode, sRecordName, sPreNext, nDataLength, sErrorCode, sMessage,
                       sSplmMsg):
        try:
            if sTrCode == kwconst.TR_PRICE_DAILY:  # Daily Price
                inputVal = ["일자", "시가", "고가", "저가", "현재가", "거래량"]
                outputVal = ['', '', '', '', '', '']
                dataCol = ['Open', 'High', 'Low', 'Close', 'Volume']
                data = pd.DataFrame(columns=dataCol)
                dataCount = self.kiwoom.GetRepeatCnt(sTrCode, sRQName)
                code = self.kiwoom.GetCommData(sTrCode, sRQName, 0, "종목코드").strip()
                tick_no = self.korea_list.find_ticker_idx(code, exact=False)
                ticker = self.korea_list.library['Tickers'][tick_no]
                tickname = self.korea_list.library['Name'][tick_no]
                self.status_update("Stock code : " + ticker + ", Name : " + tickname + ", Count : " + str(dataCount))
                latest_stamp = self.korea_list.library['Latest'][tick_no]
                today_stamp = pd.Timestamp(datetime.today())
                if stt.timestamp_kw_str(latest_stamp) == '19700101':
                    acq_all = True
                    delta_day = dataCount
                else:
                    acq_all = False
                    # delta_day = dataCount
                    delta_day = min((today_stamp - latest_stamp).days, dataCount)
                for dataIdx in range(0, delta_day):
                    for idx, j in enumerate(inputVal):
                        if idx < 1:
                            outputVal[idx] = self.kiwoom.GetCommData(sTrCode, sRQName, dataIdx, j).strip()
                        else:
                            outputVal[idx] = int(self.kiwoom.GetCommData(sTrCode, sRQName, dataIdx, j).strip())
                    dataline = pd.DataFrame(data=[outputVal[1:]], index=[pd.Timestamp(outputVal[0])], columns=dataCol)
                    data = data.append(dataline)
                data.index.name = 'Date'
                price_data = self.korea_list.load_ticker(tick_no)
                price_data.history = price_data.history.append(data)
                price_data.sort_drop_dup()
                price_data.save_history()
                first_stamp = price_data.history.index[0]
                last_stamp = price_data.history.index[-1]
                if (dataCount < 600) | (not acq_all):
                    self.korea_list.library.loc[tick_no, 'Start'] = first_stamp
                    self.korea_list.library.loc[tick_no, 'Latest'] = last_stamp
                    if (today_stamp - last_stamp).days > 7:
                        self.korea_list.library.loc[tick_no, 'active'] = False
                    self.korea_list.save_list()
                else:
                    up2date_stamp = stt.timestamp_day_before_n_days(first_stamp)
                    up2date_str = stt.timestamp_kw_str(up2date_stamp)
                    que_inst = Que_element()
                    que_inst.set_as_callDailyPrice(code, up2date_str)
                    self.que.add_que_class(que_inst, 0)
            elif sTrCode == kwconst.TR_INDEX_DAILY:  # Daily Index
                inputVal = ["일자", "시가", "고가", "저가", "현재가", "거래량"]
                outputVal = ['', '', '', '', '', '']
                dataCol = ['Open', 'High', 'Low', 'Close', 'Volume']
                data = pd.DataFrame(columns=dataCol)
                dataCount = self.kiwoom.GetRepeatCnt(sTrCode, sRQName)
                code = self.kiwoom.GetCommData(sTrCode, sRQName, 0, "업종코드").strip()
                tick_no = self.index_list_kor.find_ticker_idx(code, exact=False)
                ticker = self.index_list_kor.library['Tickers'][tick_no]
                tickname = self.index_list_kor.library['Name'][tick_no]
                self.status_update("Stock code : " + ticker + ", Name : " + tickname + ", Count : " + str(dataCount))
                latest_stamp = self.index_list_kor.library['Latest'][tick_no]
                today_stamp = pd.Timestamp(datetime.today())
                if stt.timestamp_kw_str(latest_stamp) == '19700101':
                    acq_all = True
                    delta_day = dataCount
                else:
                    acq_all = False
                    delta_day = min((today_stamp - latest_stamp).days, dataCount)
                for dataIdx in range(0, delta_day):
                    for idx, j in enumerate(inputVal):
                        if idx < 1:
                            outputVal[idx] = self.kiwoom.GetCommData(sTrCode, sRQName, dataIdx, j).strip()
                        else:
                            outputVal[idx] = int(self.kiwoom.GetCommData(sTrCode, sRQName, dataIdx, j).strip())
                    dataline = pd.DataFrame(data=[outputVal[1:]], index=[pd.Timestamp(outputVal[0])], columns=dataCol)
                    data = data.append(dataline)
                data.index.name = 'Date'
                price_data = self.index_list_kor.load_ticker(tick_no)
                price_data.history = price_data.history.append(data)
                price_data.sort_drop_dup()
                first_stamp = price_data.history.index[0]
                last_stamp = price_data.history.index[-1]
                if (dataCount < 600) | (not acq_all):
                    self.index_list_kor.library.loc[tick_no, 'Start'] = first_stamp
                    self.index_list_kor.library.loc[tick_no, 'Latest'] = last_stamp
                    if (today_stamp - last_stamp).days > 7:
                        self.index_list_kor.library.loc[tick_no, 'active'] = False
                    self.index_list_kor.save_list()
                else:
                    up2date_stamp = stt.timestamp_day_before_n_days(first_stamp)
                    up2date_str = stt.timestamp_kw_str(up2date_stamp)
                    que_inst = Que_element()
                    que_inst.set_as_callDailyIndex(code, up2date_str)
                    self.que.add_que_class(que_inst, 0)
            elif sTrCode == kwconst.TR_INFO_BASIC:  # basic information
                inputVal = ["종목코드", "종목명", "고가", "저가", "현재가", "거래량"]
                outputVal = ['', '', '', '', '', '']
                dataCol = ['Open', 'High', 'Low', 'Close', 'Volume']
                dataCount = self.kiwoom.GetRepeatCnt(sTrCode, sRQName)
                self.status_update('Total data count : ' + str(dataCount))
                code = self.kiwoom.GetCommData(sTrCode, sRQName, 0, "종목코드")
                self.status_update("Stock code : " + str(code))
                self.status_update("------------------------------")
                # 가장최근에서 10 거래일 전까지 데이터 조회
                for dataIdx in range(0, 10):
                    inputVal = ["일자", "거래량", "시가", "고가", "저가", "현재가"]
                    outputVal = ['', '', '', '', '', '']
                    for idx, j in enumerate(inputVal):
                        outputVal[idx] = self.kiwoom.GetCommData(sTrCode, sRQName, dataIdx, j)
                    for idx, output in enumerate(outputVal):
                        self.status_update(inputVal[idx] + str(output))
                    self.status_update('----------------')
            elif sTrCode == kwconst.TR_INTERESTS:
                inputVal = ['시가', '고가', '저가', '종가', '거래량']
                code_header = '종목코드'
                libcol = ['Open', 'High', 'Low', 'Close', 'Volume']
                code_list = list()
                data = pd.DataFrame(columns=libcol)
                dataCount = self.kiwoom.GetRepeatCnt(sTrCode, sRQName)
                self.status_update(f'TR({dataCount} pts) received')
                for dataIdx in range(0, dataCount):
                    outputVal = list()
                    code_list.append(self.kiwoom.GetCommData(sTrCode, sRQName, dataIdx, code_header).strip())
                    for idx, j in enumerate(inputVal):
                        dcell = self.kiwoom.GetCommData(sTrCode, sRQName, dataIdx, j).strip()
                        outputVal.append(abs(int(dcell)))
                    data.loc[dataIdx] = outputVal
                today = stt.timestamp_ref_date()
                for idx, code in enumerate(code_list):
                    data_input = data.loc[idx]
                    tick_no = self.korea_list.find_ticker_idx(code, exact=False)
                    ticker = self.korea_list.library['Tickers'][tick_no]
                    tickname = self.korea_list.library['Name'][tick_no]
                    self.status_update(
                        f'Stock code : {ticker}, Name : {tickname}, Price(Close) : ' + data_input['Close'])
                    price_data = self.korea_list.load_ticker(tick_no)
                    price_data.history.loc[today] = data_input
                    price_data.sort_drop_dup()
                    price_data.save_history()
                    first_stamp = price_data.history.index[0]
                    last_stamp = price_data.history.index[-1]
                    self.index_list_kor.library.loc[tick_no, 'Start'] = first_stamp
                    self.index_list_kor.library.loc[tick_no, 'Latest'] = last_stamp
            self.hold_on.emit()
        except Exception as e:
            self.logger.error(f'Error occured({kwconst.Err_tr}) : {e}')
            raise


if __name__ == "__main__":
    app = QApplication(sys.argv)
    myWindow = FinanceWindow()
    app.exec_()
