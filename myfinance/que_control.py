from datetime import datetime
import myfinance.static as stt
from PyQt5.QtCore import pyqtSignal, QObject, pyqtSlot


class kwQueue(QObject):
    def __init__(self):
        super().__init__()
        self.status = 0  # 0 : no que, n : number of que's
        self.temp = []


class Que_Temp:
    def __init__(self):
        self.status = 0  # 0 : no que, n : number of que's
        self.temp = []

    def add_que_class(self, que_class, position=-1):
        if position < 0:
            self.temp.append(que_class)
        else:
            self.temp.insert(position, que_class)
        self.status = len(self.temp)

    def gen_from_code_list(self, task=81, **kwargs):
        if task == 1:
            code_list = kwargs['code']
            for code in code_list:
                task_arg = [code]
                self.temp.append(Que_element(task, task_arg))
        elif (task == 81) | (task == 20006):
            code_list = kwargs['code']
            ref_day = stt.timestamp_kw_str(stt.timestamp_ref_date())
            for idx in range(0, len(code_list)):
                task_arg = [code_list[idx], ref_day]
                self.temp.append(Que_element(task, task_arg))
        elif task == 60000:
            code_list = kwargs['code']
            code_length = len(code_list)
            if code_length < 101:
                task_arg = [code_list]
                self.temp.append(Que_element(task, task_arg))
            else:
                lh = int(code_length / 100)
                for i0 in range(0, lh):
                    task_arg = [code_list[(i0 * 100):((i0 + 1) * 100)]]
                    self.temp.append(Que_element(task, task_arg))
                if not (code_length % 100 == 0):
                    task_arg = [code_list[(lh * 100):]]
                    self.temp.append(Que_element(task, task_arg))
        self.status = len(self.temp)

    def pop_first(self):
        que_temp = self.temp.pop(0)
        self.status = len(self.temp)
        return que_temp


class Que_element:
    def __init__(self, task_no=0, args=None):
        self.task = task_no  # 1 : search information, 81 : call price list
        self.task_args = args  # input arguments for desired task

    def set_as_callDailyPrice(self, code, ref_date):
        self.task = 81
        self.task_args = [code, ref_date]

    def set_as_callDailyIndex(self, code, ref_date):
        self.task = 20006
        self.task_args = [code, ref_date]

    def set_as_callBasicInfo(self, code):
        self.task = 1
        self.task_args = [code]

    def set_as_interestedStockPrice(self, code_list):
        self.task = 60000
        self.task_args = [code_list]
