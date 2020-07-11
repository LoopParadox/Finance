import sys
import subprocess
import threading
import os
import pandas as pd
import myfinance.static as stt
from PyQt5.QtWidgets import *
from PyQt5.QtCore import pyqtSignal, QTimer, pyqtSlot, Qt


class RunExtApp(QGroupBox):
    run_signal = pyqtSignal()
    alarm_changed = pyqtSignal(int)
    target_time = pd.Timestamp.now()

    def __init__(self, group_title, label_latest, label_alarm, button_str, init_alarm=0):
        super().__init__(group_title)
        self.__btn_run = QPushButton(button_str)
        self.__btn_run.clicked.connect(self.__emit_run_signal)
        lbl_latest = QLabel(label_latest)
        self.__edit_latest = QLineEdit()
        self.__edit_latest.setReadOnly(True)
        self.__edit_latest.setAlignment(Qt.AlignRight)
        lbl_alarm = QLabel(label_alarm)
        self.__spin_alarm = QSpinBox()
        self.__spin_alarm.setFixedWidth(70)
        self.__spin_alarm.setMinimum(0)
        self.__spin_alarm.setMaximum(23)
        self.__spin_alarm.setAlignment(Qt.AlignRight)
        self.__spin_alarm.setValue(init_alarm)
        self.__spin_alarm.valueChanged.connect(self.__emit_alarm_changed)
        self.__lbl_left = QLabel()
        self.__lbl_left.setFixedWidth(100)
        self.__lbl_left.setAlignment(Qt.AlignRight)
        latest_label = QWidget()
        latest_layout = QHBoxLayout()
        latest_layout.addWidget(lbl_latest)
        latest_layout.addWidget(self.__edit_latest)
        latest_label.setLayout(latest_layout)
        alarm_label = QWidget()
        alarm_layout = QHBoxLayout()
        alarm_layout.addWidget(lbl_alarm)
        alarm_layout.addWidget(self.__spin_alarm)
        alarm_layout.addWidget(self.__lbl_left)
        alarm_label.setLayout(alarm_layout)
        mainlayout = QVBoxLayout()
        mainlayout.addWidget(latest_label)
        mainlayout.addWidget(alarm_label)
        mainlayout.addWidget(self.__btn_run)
        self.setLayout(mainlayout)
        self.time_left = QTimer(self)
        self.time_left.timeout.connect(self.set_alarm_left)
        self.time_left.setInterval(60000)
        self.alarm = QTimer(self)
        self.alarm.timeout.connect(self.__emit_run_signal)
        self.set_alarm()

    @pyqtSlot()
    def __emit_run_signal(self):
        self.run_signal.emit()

    @pyqtSlot()
    def __emit_alarm_changed(self):
        self.set_alarm()
        self.alarm_changed.emit(self.get_alarm_hour())

    def set_alarm(self):
        self.alarm.stop()
        self.target_time = stt.timestamp_find_next_opening(opening_time=self.get_alarm_hour())
        interval = stt.cal_alarm_interval_until_target(self.target_time)
        self.alarm.setInterval(interval)
        self.alarm.start()
        self.init_alarm_left()

    def init_alarm_left(self):
        self.time_left.stop()
        self.time_left.start()
        self.set_alarm_left()

    @pyqtSlot()
    def set_alarm_left(self):
        timedelta_left = self.target_time - pd.Timestamp.now()
        minute_left = int(timedelta_left.total_seconds()/60)
        self.__lbl_left.setText(f'{minute_left} min.')

    def get_alarm_hour(self):
        return self.__spin_alarm.value()

    def set_latest_timestamp(self, latest_timestamp):
        self.__edit_latest.setText(latest_timestamp.strftime('%Y.%m.%d %H:%M'))

    def set_running_state(self, isrunning):
        if isrunning:
            self.__btn_run.setEnabled(False)
            self.alarm.stop()
        else:
            self.__btn_run.setEnabled(True)
            self.set_alarm()


class AutoScheduler(QMainWindow):
    task_finished = pyqtSignal(int)
    trade_finished = pyqtSignal(int)
    KEY_CONTINUE = 'continue'
    KEY_LATEST = 'latest'
    KEY_SHUTDOWN = 'shutdown'
    KEY_TRADE = 'trade'
    status_file = 'status.dat'
    pred_stat_file = f'..\\MachineLearningTest\\{status_file}'
    update_status = pd.Series({KEY_CONTINUE: 0, KEY_LATEST: pd.Timestamp(0)})
    prediction_status = pd.Series({KEY_LATEST: pd.Timestamp(0)})
    status_change = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Scheduler")
        # self.setGeometry(300, 100, 600, 100)
        self.update_manager = RunExtApp(group_title='Update Library', label_latest='Latest Update : ',
                                        label_alarm='Update Time (0-23) : ', button_str='Update Library', init_alarm=5)
        self.trade_manager = RunExtApp(group_title='Auto-Trading', label_latest='Latest Prediction : ',
                                       label_alarm='Trade Time (0-23) : ', button_str='Start Auto-Trade', init_alarm=8)
        self.update_manager.run_signal.connect(self.update_library)
        self.trade_manager.run_signal.connect(self.auto_trade)
        self.__call_thread = None
        self.__trade_thread = None
        self.isupdating = False
        self.istrading = False
        self.status_change.connect(self.set_running_status)
        centerlayout = QVBoxLayout()
        centerlayout.addWidget(self.update_manager)
        centerlayout.addWidget(self.trade_manager)
        centralwidget = QWidget()
        centralwidget.setLayout(centerlayout)
        self.setCentralWidget(centralwidget)
        self.task_finished.connect(self.task_done_handler)
        if self.load_update_status():
            self.refresh_latest_update()
        if self.load_prediction_status():
            self.refresh_latest_prediction()
        self.show()

    def load_update_status(self):
        if os.path.isfile(self.status_file):
            self.update_status = pd.read_pickle(self.status_file)
            return True
        else:
            return False

    def load_prediction_status(self):
        if os.path.isfile(self.pred_stat_file):
            self.prediction_status = pd.read_pickle(self.pred_stat_file)
            return True
        else:
            return False

    def save_status(self):
        self.update_status.to_pickle(self.status_file)

    def refresh_latest_update(self):
        self.update_manager.set_latest_timestamp(self.update_status[self.KEY_LATEST])

    def refresh_latest_prediction(self):
        self.trade_manager.set_latest_timestamp(self.prediction_status[self.KEY_LATEST])

    @pyqtSlot()
    def set_running_status(self):
        self.update_manager.set_running_state(self.isupdating)
        self.trade_manager.set_running_state(self.istrading)

    @pyqtSlot(int)
    def task_done_handler(self, done_code):
        self.__call_thread = None
        if done_code == 0:
            if self.load_update_status():
                if self.update_status[self.KEY_CONTINUE] == 1:
                    self.update_library()
                else:
                    self.refresh_latest_update()
                    self.isupdating = False
                    self.status_change.emit()

    @pyqtSlot(int)
    def trade_done_handler(self, done_code):
        self.__trade_thread = None
        self.istrading = False
        self.status_change.emit()
        self.refresh_latest_prediction()

    @pyqtSlot()
    def update_library(self):
        if self.load_update_status():
            self.update_status[self.KEY_CONTINUE] = 2
            self.update_status[self.KEY_SHUTDOWN] = 1
            self.save_status()
        self.__call_thread = threading.Thread(target=self.__call_thread_constructor)
        self.__call_thread.start()
        self.isupdating = True
        self.status_change.emit()

    def __call_thread_constructor(self):
        output = subprocess.call(['C:\\Users\\sangw\\AppData\\Local\\Programs\\Python\\Python37-32\\python.exe',
                                  'C:/Users/sangw/Documents/Finance/update_price.py'], shell=True)
        self.task_finished.emit(output)

    @pyqtSlot()
    def auto_trade(self):
        self.__trade_thread = threading.Thread(target=self.__trade_thread_constructor)
        self.__trade_thread.start()
        self.istrading = True
        self.status_change.emit()

    def __trade_thread_constructor(self):
        output = subprocess.call(['C:\\Users\\sangw\\AppData\\Local\\Programs\\Python\\Python37-32\\python.exe',
                                  'C:/Users/sangw/Documents/Finance/KSgui.py'], shell=True)
        self.trade_finished.emit(output)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    guiwindow = AutoScheduler()
    sys.exit(app.exec_())
