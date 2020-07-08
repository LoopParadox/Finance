import sys
import subprocess
import threading
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QAxContainer import *
from PyQt5.QtCore import pyqtSignal, QObject, QTime, QTimer, pyqtSlot


class AutoScheduler(QMainWindow):
    EXIT_CODE_NORMAL = 0
    EXIT_CODE_REBOOT = -1
    EXIT_CODE_CONTINUE = 1

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Scheduler")
        self.setGeometry(300, 300, 800, 800)
        centralwidget = QWidget()
        centralwidget.setLayout(horLayOut)
        self.setCentralWidget(centralwidget)
        self.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    guiwindow = AutoScheduler()
    sys.exit(app.exec_())
