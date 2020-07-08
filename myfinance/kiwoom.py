from PyQt5.QAxContainer import *
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QTime, QTimer
from myfinance.commlogg import CommLog
from myfinance.GUI_components import PredData
import myfinance.static as stt
import pandas as pd
import numpy as np
from myfinance.que_control import kwQueue


class KWcomm(QObject):
    error_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(str)
    data_list = pyqtSignal(list)
    data_dict = pyqtSignal(dict)
    history_data = pyqtSignal(dict)
    account_data = pyqtSignal(dict)
    order_data = pyqtSignal(dict)
    data_history = pyqtSignal(dict)
    login_signal = pyqtSignal(bool)
    comm_query_order = pyqtSignal()
    comm_query_stock = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.kwinst = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self.account = 0
        self.list_account = []
        self.stock_data = StockDataCurrent()
        self.contract_list = StockDataCurrent(header=stt.LIST_contract_stock, query=2)
        self.prediction = PredData()
        self.que_main = Queue()
        self.que_main.call_info.connect(self.__call_information_queue)
        self.que_main.status_signal.connect(self.__send_status)
        self.islogin = False
        self.server_info = dict()
        self.req_no = 0
        self.logger = CommLog().logger
        self.kwinst.OnEventConnect.connect(self.__on_event_connect)
        self.kwinst.OnReceiveTrData.connect(self.__on_receive_tr_data)  # tr 수신 이벤트
        self.kwinst.OnReceiveRealData.connect(self.__on_receive_realtime_data)
        self.kwinst.OnReceiveMsg.connect(self.__on_receive_message)  # 서버메세지 수신 이벤트
        self.kwinst.OnReceiveChejanData.connect(self.__on_receive_chejan_data)  # 체결/잔고 수신 이벤트
        self.comm_query_stock.connect(self.__query_stocks_command)
        self.comm_query_order.connect(self.__query_orders_command)

    def __run_next_queue(self):
        self.que_main.run_next()

    def __send_error(self, error_msg):
        self.error_signal.emit(error_msg)

    @pyqtSlot(str)
    def __send_status(self, status_msg):
        self.status_signal.emit(status_msg)

    @pyqtSlot(str)
    def __send_progress(self, progress_msg):
        self.progress_signal.emit(progress_msg)

    def __send_login_status(self):
        self.login_signal.emit(self.islogin)

    def __send_data_list(self, data_list):
        self.data_list.emit(data_list)

    def __send_single_data_dict(self, data_dict):
        self.stock_data.update_values_from_dict(data_dict)
        self.contract_list.update_current_price(data_dict)
        if data_dict is not None:
            self.data_dict.emit(data_dict)
        self.__run_next_queue()

    def __send_multiple_data_dict(self, data_dict):
        self.stock_data.update_multiple_values(data_dict)
        if data_dict is not None:
            self.data_dict.emit(data_dict)
        self.__run_next_queue()

    def __send_order_data(self, order_dict):
        if order_dict is not None:
            self.contract_list.renew_order_data(order_dict)
            self.order_data.emit(order_dict)
            self.__run_next_queue()

    def __send_data_history(self, data_dict):
        if data_dict is not None:
            self.history_data.emit(data_dict)
        self.__run_next_queue()

    def __on_event_connect(self, nErrCode):
        if nErrCode == stt.RESP_ERR_NONE:
            self.islogin = True
            self.req_no = 1
            self.server_info = self.__get_server_info()
            self.stock_data.list_stocks = self.get_code_list_by_market(0)
            if self.server_info['mode'] == stt.RESP_SERVER_GUBUN_SIMU:
                mode = 'Simulation mode'
            else:
                mode = 'Real mode'
            self.__send_status(f'Login Success : {mode}')
        elif nErrCode == stt.RESP_ERR_USR:
            self.islogin = False
            self.req_no = 0
            self.__send_error('Failed to exchange user information')
        elif nErrCode == stt.RESP_ERR_CONNECTION:
            self.islogin = False
            self.req_no = 0
            self.__send_error('Failed to connect server')
        elif nErrCode == stt.RESP_ERR_VERSION:
            self.islogin = False
            self.req_no = 0
            self.__send_error('Failed to version update')
        self.__send_login_status()

    def __on_receive_tr_data(self, sScrNo, sRQName, sTrCode, sRecordName, sPreNext, _nDLength=0, _sError='', _sMsg='',
                             _sSplmMsg=''):
        # print(f'TR type : {sTrCode}')
        if sTrCode == stt.TR_PRICE_DAILY:  # Daily Price
            self.__send_data_history(self.__TR_history_data(sPreNext=sPreNext))
        if sTrCode == stt.TR_INDEX_DAILY:  # Daily Price
            self.__send_data_history(self.__TR_history_data(sRQName=sRQName, sTrCode=sTrCode, sPreNext=sPreNext))
        elif sTrCode == stt.TR_INTERESTS:
            self.__send_multiple_data_dict(self.__TR_multi_data())
        elif sTrCode == stt.TR_INFO_BASIC:
            self.__send_single_data_dict(self.__TR_basic_info())
        elif sTrCode == stt.TR_HOLDING_STOCKS:
            self.__send_multiple_data_dict(self.__TR_multi_data(sRQName=sRQName, sTrCode=sTrCode))
        elif sTrCode == stt.TR_ACC_EVAL:
            self.account_data.emit(self.__TR_account_evaluation())
        elif sTrCode == stt.TR_ORDER_NOT_CONTRACTED:
            self.__send_order_data(self.__TR_multi_data(sRQName=sRQName, sTrCode=sTrCode))
        elif sTrCode == 'KOA_NORMAL_BUY_KP_ORD':
            order_num = self.kwinst.GetCommData(sTrCode, sRQName, 0, '주문번호').strip()
            self.__send_progress(f'Order No. : {order_num}')

    def __on_receive_realtime_data(self, sCode, sRealType, sRealData):
        rtdata = {stt.HD_out_dict_type: 'RT', stt.HD_out_dict_code: [sCode], stt.HD_out_dict_tr: sRealType}
        if sRealType in stt.LIST_RT_type:
            rtypeid = stt.LIST_RT_type.index(sRealType)
            rtcodequery = stt.LIST_RT_code[rtypeid]
            for fid in rtcodequery:
                rtdata[stt.RTcode[fid]] = self.kwinst.GetCommRealData(sCode, fid)
        self.__send_single_data_dict(rtdata)

    def __on_receive_message(self, sScrNo, sRQName, sTrCode, sMsg):
        self.__send_progress(f'{sTrCode} : {sMsg}')

    def __on_receive_chejan_data(self, sGubun, nItemCnt, sFIdList):
        if sGubun == '0':
            self.__send_progress(f'주문/체결 신호 획득 : 주문체결')
            self.comm_query_order.emit()
        elif sGubun == '1':
            self.__send_progress(f'주문/체결 획득 : 잔고획득')
            self.comm_query_stock.emit()
        else:
            return

    @pyqtSlot()
    def __query_orders_command(self):
        self.query_orders_not_contracted()

    @pyqtSlot()
    def __query_stocks_command(self):
        self.query_holding_stocks()

    def __TR_history_data(self, sScrNo=stt.SCR_STOCK_PRICE_DAILY, sRQName=stt.TR_PRICE_DAILY,
                          sTrCode=stt.TR_PRICE_DAILY, sRecordName='', sPreNext=0):
        if sTrCode == stt.TR_PRICE_DAILY:
            inputVal = stt.TROI_PRICE_DAILY
        elif sTrCode == stt.TR_INDEX_DAILY:
            inputVal = stt.TROI_INDEX_DAILY
        else:
            return None
        outputVal = list(range(0, len(inputVal)))
        dataCol = ['Open', 'High', 'Low', 'Close', 'Volume']
        data = pd.DataFrame(columns=dataCol)
        dataCount = self.kwinst.GetRepeatCnt(sTrCode, sRQName)
        if sTrCode == stt.TR_PRICE_DAILY:
            code = self.kwinst.GetCommData(sTrCode, sRQName, 0, stt.TRII_PRICE_DAILY[0]).strip()
        elif sTrCode == stt.TR_INDEX_DAILY:
            code = self.kwinst.GetCommData(sTrCode, sRQName, 0, stt.TRII_INDEX_DAILY[0]).strip()
        else:
            return None
        self.__send_status(f'TR({code}: {dataCount} pts) received')
        output_dict = {stt.HD_out_dict_type: 'TR', stt.HD_out_dict_tr: stt.TR_PRICE_DAILY,
                       stt.HD_out_dict_code: code, stt.HD_out_dict_count: dataCount,
                       stt.HD_out_dict_repeat: sPreNext}
        for dataIdx in range(0, dataCount):
            for idx, j in enumerate(inputVal):
                if idx < 1:
                    outputVal[idx] = self.kwinst.GetCommData(sTrCode, sRQName, dataIdx, j).strip()
                else:
                    outputVal[idx] = int(self.kwinst.GetCommData(sTrCode, sRQName, dataIdx, j).strip())
            dataline = pd.DataFrame(data=[outputVal[1:]], index=[pd.Timestamp(outputVal[0])], columns=dataCol)
            data = data.append(dataline)
        data.index.name = 'Date'
        output_dict[stt.HD_out_dict_data] = data
        target = self.que_main.latest[stt.HD_que_target]
        data_start = data.index.min()
        if (int(sPreNext) > 0) & (target < data_start):
            self.que_main.add_repeat()
        return output_dict

    def __TR_multi_data(self, sScrNo=stt.SCR_STOCK_PRICE_CUR, sRQName=stt.TR_INTERESTS,
                        sTrCode=stt.TR_INTERESTS, sRecordName='', sPreNext=0):
        if sTrCode == stt.TR_INTERESTS:
            inputVal = stt.TROI_INTERESTS
            code_header = '종목코드'
        elif sTrCode == stt.TR_HOLDING_STOCKS:
            inputVal = stt.TROI_HOLDING_STOCKS
            code_header = '종목코드'
        elif sTrCode == stt.TR_ORDER_NOT_CONTRACTED:
            inputVal = stt.TROI_ORDER_NOT_CONTRACTED
            code_header = '주문번호'
        else:
            return None
        outputVal = [''] * len(inputVal)
        data = pd.DataFrame(columns=inputVal)
        dataCount = self.kwinst.GetRepeatCnt(sTrCode, sRQName)
        self.__send_status(f'TR({dataCount} pts) received')
        for dataIdx in range(0, dataCount):
            for idx, j in enumerate(inputVal):
                dcell = self.kwinst.GetCommData(sTrCode, sRQName, dataIdx, j).strip()
                outputVal[idx] = dcell
            data.loc[dataIdx] = outputVal
        code = data[code_header].tolist()
        if len(code) < 1:
            return None
        output_dict = {stt.HD_out_dict_type: 'TR', stt.HD_out_dict_tr: sTrCode,
                       stt.HD_out_dict_code: code, stt.HD_out_dict_count: dataCount,
                       stt.HD_out_dict_repeat: sPreNext, stt.HD_out_dict_data: data}
        return output_dict

    def __TR_basic_info(self, sScrNo=stt.SCR_STOCK_PRICE_CUR, sRQName=stt.TR_INFO_BASIC,
                        sTrCode=stt.TR_INFO_BASIC, sRecordName='', sPreNext=0):
        self.__send_status(f'TR({sTrCode}) received')
        inputVal = stt.TROI_INFO_BASIC
        outputVal = [''] * len(inputVal)
        data = pd.DataFrame(columns=inputVal)
        dataCount = self.kwinst.GetRepeatCnt(sTrCode, sRQName)
        for idx, j in enumerate(inputVal):
            dcell = self.kwinst.GetCommData(sTrCode, sRQName, 0, j).strip()
            outputVal[idx] = dcell
        data.loc[0] = outputVal
        code = data[stt.TROI_INTERESTS[0]].tolist()
        output_dict = {stt.HD_out_dict_type: 'TR', stt.HD_out_dict_tr: sTrCode,
                       stt.HD_out_dict_code: code, stt.HD_out_dict_count: dataCount,
                       stt.HD_out_dict_repeat: sPreNext, stt.HD_out_dict_data: data}
        return output_dict

    def __TR_account_evaluation(self, sScrNo=stt.SCR_STOCK_PRICE_CUR, sRQName=stt.TR_ACC_EVAL,
                                sTrCode=stt.TR_ACC_EVAL, sRecordName='', sPreNext=0):
        inputVal = stt.TROI_ACC_EVAL
        account_data = dict()
        for item in inputVal:
            dcell = self.kwinst.GetCommData(sTrCode, sRQName, 0, item).strip()
            account_data[item] = int(dcell)
        return account_data

    def loginAPI(self):
        if self.kwinst is None:
            self.kwinst = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self.kwinst.dynamicCall(stt.COM_LOGIN)

    def logoutAPI(self):
        if self.islogin:
            self.kwinst = None
            self.islogin = False
            self.__send_login_status()
            self.__send_status('Log out success')

    def __get_server_info(self):
        gubun = int(self.kwinst.dynamicCall(stt.COM_LOGIN_INFO, [stt.ARG_LOGIN_SERVER_GUBUN]))
        acc_count = int(self.kwinst.dynamicCall(stt.COM_LOGIN_INFO, [stt.ARG_LOGIN_ACCOUNT_CNT]))
        acc_list = self.kwinst.dynamicCall(stt.COM_LOGIN_INFO, [stt.ARG_LOGIN_ACCLIST])
        usrid = self.kwinst.dynamicCall(stt.COM_LOGIN_INFO, [stt.ARG_LOGIN_USR_ID])
        usrname = self.kwinst.dynamicCall(stt.COM_LOGIN_INFO, [stt.ARG_LOGIN_USR_NAME])
        keysf = int(self.kwinst.dynamicCall(stt.COM_LOGIN_INFO, [stt.ARG_LOGIN_KEY_SAFETY]))
        firewall = int(self.kwinst.dynamicCall(stt.COM_LOGIN_INFO, [stt.ARG_LOGIN_FIREWALL]))
        output_dict = {'mode': gubun, 'count': acc_count, 'list': acc_list, 'id': usrid, 'name': usrname,
                       'keysf': keysf, 'firewall': firewall}
        self.list_account = output_dict['list'].split(';')
        self.account = self.list_account[0]
        # print(f'User account : {self.account}')
        return output_dict

    def get_code_list_by_market(self, market):
        code_list = self.kwinst.dynamicCall(stt.COM_GET_CODELIST, market)
        code_list = code_list.split(';')
        return code_list[:-1]

    def get_code_name(self, code_str):
        return self.kwinst.dynamicCall(stt.COM_GET_CODENAME, code_str)

    def get_intersted_stock_info(self, codelist):
        codeinput = ';'.join(codelist)
        codelength = len(codelist)
        return self.kwinst.CommKwRqData(codeinput, False, codelength, 0, stt.TR_INTERESTS,
                                        stt.SCR_STOCK_PRICE_CUR)

    def call_basic_info(self, code):
        # input parameters
        self.que_main.add_task(stt.TR_INFO_BASIC, [code])
        self.__run_next_queue()

    def call_daily_price_list(self, codelist, today, latest):
        self.que_main.add_history_task_from_codelist(stt.TR_PRICE_DAILY, codelist, today, latest)
        self.__run_next_queue()

    def call_daily_index_list(self, codelist, today, latest):
        # input parameters
        self.que_main.add_history_task_from_codelist(stt.TR_INDEX_DAILY, codelist, today, latest)
        self.__run_next_queue()

    def query_account_evaluation(self):
        self.que_main.add_task(stt.TR_ACC_EVAL, [self.account, '', '1', '00'])
        self.__run_next_queue()

    def query_holding_stocks(self):
        self.que_main.add_task(stt.TR_HOLDING_STOCKS, [self.account])
        self.__run_next_queue()

    def query_orders_not_contracted(self):
        self.que_main.add_task(stt.TR_ORDER_NOT_CONTRACTED, [self.account, '', '', '', ''])
        self.__run_next_queue()

    def start_query_price_list(self, codelist):
        self.que_main.add_query_task_from_codelist(codelist)
        self.__run_next_queue()

    @pyqtSlot(dict)
    def __call_information_queue(self, queue):
        # input parameters
        task = queue[stt.HD_que_task]
        rparg = queue[stt.HD_que_repeat]
        parameters = queue[stt.HD_que_param]
        if task == stt.TR_INFO_BASIC:
            input_list = stt.TRII_INFO_BASIC
        elif task == stt.TR_PRICE_DAILY:
            input_list = stt.TRII_PRICE_DAILY
        elif task == stt.TR_PRICE_CALL:
            input_list = stt.TRII_PRICE_CALL
        elif task == stt.TR_INDEX_DAILY:
            input_list = stt.TRII_INDEX_DAILY
        elif task == stt.TR_HOLDING_STOCKS:
            input_list = stt.TRII_HOLDING_STOCKS
        elif task == stt.TR_ACC_EVAL:
            input_list = stt.TRII_ACC_EVAL
        elif task == stt.TR_ORDER_NOT_CONTRACTED:
            input_list = stt.TRII_ORDER_NOT_CONTRACTED
        else:
            self.__send_error('Not available task')
            return
        for idx, item in enumerate(input_list):
            self.kwinst.SetInputValue(item, parameters[idx])
        # sRQName, sTrCode, nPrevNext, sScreenNo
        return self.kwinst.CommRqData(task, task, rparg, stt.SCR_NORM)

    def get_stock_table(self):
        return self.stock_data.print_data()

    def get_contract_list(self):
        return self.contract_list.print_data()

    def send_order(self, nOrderType, sCode, nQty, nPrice, nPriceType=stt.TYPE_price_fixed, sOrgOrderNo=''):
        sRQName = 'ord0001'
        sScreenNo = '0001'
        self.kwinst.dynamicCall(stt.COM_SEND_ORDER,
                                [sRQName, sScreenNo, self.account, nOrderType, sCode, nQty, nPrice, nPriceType,
                                 sOrgOrderNo])

    @pyqtSlot(dict)
    def send_order_dict(self, input_dict):
        input_args = list()
        if stt.ARG_request_name in input_dict:
            input_args.append(input_dict[stt.ARG_request_name])
        else:
            input_args.append('ord0001')
        if stt.ARG_screen_number in input_dict:
            input_args.append(input_dict[stt.ARG_screen_number])
        else:
            input_args.append('0001')
        input_args.append(self.account)
        for item in stt.LIST_order_args:
            if item in input_dict:
                input_args.append(input_dict[item])
            else:
                self.__send_error(f'Not enough arguments: {item}')
                return
        ret = self.kwinst.dynamicCall(stt.COM_SEND_ORDER, input_args)
        if ret == 0:
            self.__send_status('Ordered successfully')
            buysell_str = stt.LIST_buy_sell[input_dict[stt.ARG_order_type] - 1]
            self.__send_progress(
                f'Order ({input_dict[stt.ARG_stock_code]} {buysell_str} : {input_dict[stt.ARG_price]}) sent')
        else:
            self.__send_error('Failed to order')

    def get_stock_list(self):
        return self.stock_data.list_stocks


class Queue(QObject):
    call_info = pyqtSignal(dict)
    command_order = pyqtSignal(dict)
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    holdon_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.quelist = list()
        self.latest = dict()
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.execute)
        self.holdsec = 0
        self.rqnum = 0
        self.ticktime = pd.Timestamp.now()

    def __send_status(self, status_msg):
        self.status_signal.emit(status_msg)

    def __send_error(self, error_msg):
        self.error_signal.emit(error_msg)

    def init_tick(self):
        self.ticktime = pd.Timestamp.now()

    def send_call_info(self):
        # print(f'send {self.latest[kwconst.HD_que_task]}')
        self.call_info.emit(self.latest)

    def send_command(self):
        self.command_order.emit(self.latest)

    def add_task(self, task, parameters, repeat=False, first=False, target=pd.Timestamp(0)):
        if repeat:
            rparg = 2
        else:
            rparg = 0
        if task in stt.LIST_TR:
            tasktype = stt.TYPE_task_TR
        else:
            tasktype = stt.TYPE_task_order
        que = {stt.HD_que_type: tasktype, stt.HD_que_task: task, stt.HD_que_repeat: rparg,
               stt.HD_que_param: parameters, stt.HD_que_target: pd.Timestamp(target)}
        if first:
            self.quelist.insert(0, que)
        else:
            self.quelist.append(que)

    def add_repeat(self):
        que_r = self.latest
        que_r[stt.HD_que_repeat] = 2
        self.quelist.insert(0, que_r)

    def add_history_task_from_codelist(self, task, codelist, today, latest=None):
        today_str = stt.timestamp_kw_str(pd.Timestamp(today))
        if latest is None:
            latest = [pd.Timestamp(0)] * len(codelist)
        if len(codelist) != len(latest):
            self.__send_error('No appropriate data input')
            return
        for idx, code in enumerate(codelist):
            self.add_task(task, [code, today_str, '0'], target=latest[idx])

    def add_query_task_from_codelist(self, codelist):
        for code in codelist:
            self.add_task(stt.TR_INFO_BASIC, [code])

    def run_next(self):
        if len(self.quelist) > 0:
            self.latest = self.quelist.pop(0)
            self.rqnum = self.rqnum + 1
            if (self.rqnum > 0) & (self.rqnum % 4 == 0):
                self.holdsec = 0
                self.timer.setInterval(1000)
                self.timer.start()
                return
            elif (self.rqnum > 0) & (self.rqnum % 10 == 0):
                self.rqnum = 0
                deltatime = pd.Timestamp.now() - self.ticktime
                self.holdsec = int(70 - deltatime.seconds + 1)
                if self.holdsec < 0:
                    self.holdsec = 0
                self.__send_status(f'Hold on for {self.holdsec} sec to avoid the request limitation')
                self.timer.setInterval(1000)
                self.timer.start()
                return
            else:
                self.execute()

    @pyqtSlot()
    def execute(self):
        if self.holdsec > 0:
            self.holdsec = self.holdsec - 1
            self.__send_status(f'Hold on for {self.holdsec} sec to avoid the request limitation')
        else:
            self.timer.stop()
            if self.latest[stt.HD_que_type] == stt.TYPE_task_TR:
                self.send_call_info()
            else:
                self.send_command()


class StockDataCurrent:
    list_stocks = []

    def __init__(self, header=stt.LIST_data_stock, query=0):
        self.header = header
        self.stocktable = pd.DataFrame(columns=self.header)
        self.header_query = self.header[query]

    def get_data_count(self):
        return len(self.stocktable)

    def init_stocktable(self):
        self.stocktable = pd.DataFrame(columns=self.header)

    def add_to_stock_table(self, data_frame):
        data_frame_reset = data_frame.reset_index(drop=True)
        data_info = pd.DataFrame(data_frame_reset, columns=self.header)  # , index=range(0, len(data_frame_reset)))
        data_t = data_info.transpose()
        data_t[data_t.isnull()] = ''
        data_info = data_t.transpose()
        self.stocktable = self.stocktable.append(data_info, ignore_index=True)

    def update_values_from_dict(self, data_dict):
        code = data_dict[stt.HD_out_dict_code]
        for idx, item in enumerate(code):
            if item not in self.list_stocks:
                code.pop(idx)
        if len(code) < 1:
            return
        if data_dict[stt.HD_que_type] == 'TR':
            data_frame = data_dict[stt.HD_out_dict_data]
        else:
            data_frame = pd.DataFrame(data_dict, index=[0])
        if self.header_query in data_frame.columns:
            header = self.header_query
        elif stt.HD_out_dict_code in data_frame.columns:
            header = stt.HD_out_dict_code
        else:
            return
        if self.code_exist(code):
            row_index = self.isin_code(code)
            datakeys = data_frame.columns.to_list()
            c_header = list(set(self.header).intersection(datakeys))
            for key in c_header:
                self.stocktable.loc[row_index, key] = data_frame.loc[0, key]
        else:
            self.add_to_stock_table(data_frame)

    def update_multiple_values(self, data_dict):
        code_list = data_dict[stt.HD_out_dict_code]
        if isinstance(code_list, list):
            code_num = len(code_list)
        else:
            return
        if code_num > 0:
            data_frame = data_dict[stt.HD_out_dict_data]
        else:
            return
        if self.header_query in data_frame.columns:
            for code in code_list:
                row_input = data_frame[self.header_query].isin([code])
                if self.code_exist([code]):
                    row_index = self.isin_code([code])
                    datakeys = data_frame.columns.to_list()
                    c_header = list(set(self.header).intersection(datakeys))
                    for key in c_header:
                        self.stocktable.loc[row_index, key] = data_frame.loc[row_input, key]
                else:
                    self.add_to_stock_table(data_frame.loc[row_input])

    def update_current_price(self, data_dict):
        code = data_dict[stt.HD_out_dict_code]
        if len(code) < 1:
            return
        if data_dict[stt.HD_que_type] == 'TR':
            data_frame = data_dict[stt.HD_out_dict_data]
        else:
            data_frame = pd.DataFrame(data_dict, index=[0])
        if self.stocktable[self.header[0]].isin(code).any():
            row_index = self.stocktable[self.header[0]].isin(code)
            datakeys = data_frame.columns.to_list()
            c_header = list(set(self.header).intersection(datakeys))
            for key in c_header:
                self.stocktable.loc[row_index, key] = data_frame.loc[0, key]

    def renew_order_data(self, order_dict):
        self.init_stocktable()
        code = order_dict[stt.HD_out_dict_code]
        if order_dict[stt.HD_que_type] == 'TR':
            data_frame = order_dict[stt.HD_out_dict_data]
        else:
            data_frame = pd.DataFrame(order_dict, index=[0])
        if self.header_query in data_frame.columns:
            header = self.header_query
        elif stt.HD_out_dict_code in data_frame.columns:
            header = stt.HD_out_dict_code
        else:
            return
        if len(code) > 0:
            datakeys = data_frame.columns.to_list()
            c_header = list(set(self.header).intersection(datakeys))
            self.stocktable = pd.DataFrame(data_frame, columns=self.header)
        else:
            self.init_stocktable()

    def get_row_by_index(self, idx):
        return self.stocktable.loc[idx]

    def get_row_by_code(self, code):
        if self.code_exist(code):
            return self.stocktable.loc[self.isin_code(code)]

    def code_exist(self, code):
        return self.isin_code(code).any()

    def isin_code(self, code):
        return self.stocktable[self.header_query].isin(code)

    def print_data(self):
        return self.stocktable

    def get_current_stock_codes(self):
        return self.stocktable['종목코드'].unique().tolist()
