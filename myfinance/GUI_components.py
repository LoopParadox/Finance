import myfinance.static as stt
import threading
from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal, QStringListModel, QTimer, QObject
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as ptch
import numpy as np
import pandas as pd
import os
from datetime import datetime


class TwoStatesToggleButton(QtWidgets.QPushButton):
    clicked = pyqtSignal(bool)
    current_status = False

    def __init__(self, title_list):  # class 선언 시 두 개의 string 을 갖는 list 를 입력으로 받음
        self.str_false = title_list[0]  # 기본 title
        self.str_true = title_list[1]  # True 상태의 title
        super().__init__(self.str_false)  # 기본 title 로 PushButton class 상속

    def mousePressEvent(self, event):  # 마우스 클릭 이벤트 override
        self.clicked.emit(not self.current_status)  # clicked 이벤트에 target status 를 같이 전달
        QtWidgets.QPushButton.mousePressEvent(self, event)

    @pyqtSlot(bool)
    def change_status(self, logical_status):  # 상태 변환 함수
        self.current_status = logical_status
        if logical_status:
            self.setText(self.str_true)
        else:
            self.setText(self.str_false)


class ClickableLineEdit(QtWidgets.QLineEdit):
    clicked = pyqtSignal(int)

    def __init__(self, line_text, edit_id=-1):
        super().__init__(line_text)
        self.edit_id = edit_id
        self.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
        self.def_text = line_text

    def mousePressEvent(self, event):
        self.clicked.emit(self.edit_id)
        QtWidgets.QLineEdit.mousePressEvent(self, event)

    def set_edit_id(self, edit_id):
        self.edit_id = edit_id

    def set_yellow(self):
        self.setStyleSheet('background:yellow')

    def set_white(self):
        self.setStyleSheet('background:white')


class StockDataTable(QtWidgets.QTableWidget):
    selected_row_data = pyqtSignal(dict)

    def __init__(self, header=stt.LIST_data_stock):
        self.header = header
        super().__init__(0, len(self.header))
        self.setHorizontalHeaderLabels(self.header)
        self.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.itemSelectionChanged.connect(self.row_selected)

    def update_data(self, data_frame):
        rowcount = len(data_frame)
        colcount = len(self.header)
        self.setRowCount(rowcount)
        for idx in range(0, rowcount):
            for idy in range(0, colcount):
                colitem = QtWidgets.QTableWidgetItem()
                colitem.setTextAlignment(Qt.AlignCenter)
                colitem.setText(f'{data_frame.loc[idx, self.header[idy]]}')
                self.setItem(idx, idy, colitem)
        self.resizeRowsToContents()
        self.resizeColumnsToContents()

    @pyqtSlot()
    def row_selected(self):
        rownum = list(set(index.row() for index in self.selectedIndexes()))[0]
        self.selected_row_data.emit(self.get_row_data(rownum))

    def get_row_data(self, row_num):
        output = dict()
        for idx, item in enumerate(self.header):
            output[item] = self.item(row_num, idx).text()
        return output


class ManualOrder(QtWidgets.QGroupBox):
    KEY_account = stt.LIST_manual_order_input[0]
    KEY_buysell = stt.LIST_manual_order_input[1]
    KEY_code = stt.LIST_manual_order_input[2]
    KEY_name = stt.LIST_manual_order_input[3]
    KEY_type = stt.LIST_manual_order_input[4]
    KEY_price = stt.LIST_manual_order_input[5]
    KEY_qty = stt.LIST_manual_order_input[6]
    KEY_ordernum = stt.LIST_manual_order_input[7]
    header_labels = [KEY_buysell, KEY_code, KEY_name, KEY_type, KEY_price, KEY_qty, KEY_ordernum]
    header_input = [KEY_account, KEY_code, KEY_name, KEY_ordernum]
    header_account = [KEY_account, '예수금', '현금', '매입금액', '평가액', '단순손익']
    widget_type = ['cmb', 'edit', 'edit', 'cmb', 'spin', 'spin', 'edit']
    buysell_type = stt.LIST_buy_sell
    buysell_code = [stt.TYPE_buy_new, stt.TYPE_sell_new, stt.TYPE_buy_cancel, stt.TYPE_sell_cancel,
                    stt.TYPE_buy_correct, stt.TYPE_sell_correct]
    price_type = ['지정가', '시장가', '조건부 지정가', '최유리 지정가', '최우선 지정가']
    price_code = [stt.TYPE_price_fixed, stt.TYPE_price_market, stt.TYPE_price_fixed_conditional,
                  stt.TYPE_price_fixed_advantageous, stt.TYPE_price_fixed_top_priority]
    code_list = []
    changed_account = pyqtSignal(str)
    changed_code = pyqtSignal(str)
    signal_add = pyqtSignal(str)
    signal_order = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setFixedWidth(500)
        self.btn_add = QtWidgets.QPushButton('Add to List')
        self.btn_add.clicked.connect(self.add_stock_to_list)
        self.btn_order = QtWidgets.QPushButton('Order')
        self.btn_order.clicked.connect(self.place_order)
        self.btn_add.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        self.btn_order.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        self.grid = QtWidgets.QGridLayout()
        self.grid.setHorizontalSpacing(20)
        self.grid.setVerticalSpacing(5)
        self.labels = dict()
        self.widgets = dict()
        for idx, item in enumerate(self.header_labels):
            self.labels[item] = QtWidgets.QLabel(item)
            self.labels[item].setAlignment(Qt.AlignRight)
            if self.widget_type[idx] == 'cmb':
                self.widgets[item] = QtWidgets.QComboBox()
            elif self.widget_type[idx] == 'spin':
                self.widgets[item] = QtWidgets.QSpinBox()
                self.widgets[item].setMinimum(0)
                self.widgets[item].setMaximum(9999999)
                self.widgets[item].setAlignment(Qt.AlignRight)
            else:
                self.widgets[item] = QtWidgets.QLineEdit()
                self.widgets[item].setAlignment(Qt.AlignRight)
            self.widgets[item].setFixedWidth(130)
        for item in self.header_account:
            self.labels[item] = QtWidgets.QLabel(item)
            self.labels[item].setAlignment(Qt.AlignRight)
            if item == self.KEY_account:
                self.widgets[item] = QtWidgets.QComboBox()
            else:
                self.widgets[item] = QtWidgets.QLineEdit()
                self.widgets[item].setReadOnly(True)
                self.widgets[item].setAlignment(Qt.AlignRight)
            self.widgets[item].setFixedWidth(130)
        self.widgets[self.KEY_account].currentTextChanged.connect(self.changed_account.emit)
        self.widgets[self.KEY_name].setReadOnly(True)
        self.widgets[self.KEY_code].textEdited.connect(self.send_code_string)
        self.arrange_grid()
        btnlayout = QtWidgets.QHBoxLayout()
        btnlayout.addWidget(self.btn_add)
        btnlayout.addWidget(self.btn_order)
        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(self.grid)
        layout.addLayout(btnlayout)
        self.init_settings()
        self.setLayout(layout)

    def arrange_grid(self):
        for idx, item in enumerate(self.header_account):
            self.grid.addWidget(self.labels[item], idx, 0)
            self.grid.addWidget(self.widgets[item], idx, 1)
        for idx, item in enumerate(self.header_labels):
            self.grid.addWidget(self.labels[item], idx, 2)
            self.grid.addWidget(self.widgets[item], idx, 3)

    def init_settings(self):
        self.widgets[self.KEY_buysell].clear()
        self.widgets[self.KEY_buysell].addItems(self.buysell_type)
        self.widgets[self.KEY_type].clear()
        self.widgets[self.KEY_type].addItems(self.price_type)

    def get_type_codes(self):
        order_type = self.buysell_code[self.widgets[self.KEY_buysell].currentIndex()]
        price_type = self.price_code[self.widgets[self.KEY_type].currentIndex()]
        output = {stt.ARG_order_type: order_type, stt.ARG_price_type: price_type}
        return output

    def add_code_list(self, code_list):
        model = QStringListModel()
        model.setStringList(code_list)
        completer = QtWidgets.QCompleter()
        completer.setModel(model)
        self.widgets[self.KEY_code].setCompleter(completer)
        self.code_list = code_list

    def set_account_list(self, account_list):
        self.widgets[self.KEY_account].clear()
        self.widgets[self.KEY_account].addItems(account_list)
        self.widgets[self.KEY_account].setCurrentIndex(0)

    @pyqtSlot(dict)
    def set_account_information(self, data_dict):
        self.widgets[self.header_account[1]].setText(str(data_dict['예수금']) + ' 원')
        self.widgets[self.header_account[2]].setText(str(data_dict['예탁자산평가액']) + ' 원')
        self.widgets[self.header_account[3]].setText(str(data_dict['총매입금액']) + ' 원')
        self.widgets[self.header_account[4]].setText(str(data_dict['유가잔고평가액']) + ' 원')
        self.widgets[self.header_account[5]].setText(str(data_dict['유가잔고평가액'] - data_dict['총매입금액']) + ' 원')

    @pyqtSlot()
    def send_code_string(self):
        code_str = self.widgets[self.KEY_code].text()
        if code_str in self.code_list:
            self.changed_code.emit(code_str)

    def set_stock_name(self, name_str):
        self.widgets[self.KEY_name].setText(name_str)

    @pyqtSlot()
    def add_stock_to_list(self):
        code_str = self.widgets[self.KEY_code].text()
        self.signal_add.emit(code_str)

    @pyqtSlot()
    def place_order(self):
        output = dict()
        output[stt.ARG_request_name] = 'ord0001'
        output[stt.ARG_screen_number] = '0001'
        output[stt.ARG_stock_code] = self.widgets[self.KEY_code].text()
        output[stt.ARG_quantity] = self.widgets[self.KEY_qty].value()
        output[stt.ARG_price] = self.widgets[self.KEY_price].value()
        ntypes = self.get_type_codes()
        output.update(ntypes)
        if output[stt.ARG_order_type] > 2:
            output[stt.ARG_order_number] = self.widgets[self.KEY_ordernum].text()
        else:
            output[stt.ARG_order_number] = ''
        self.signal_order.emit(output)

    @pyqtSlot(dict)
    def set_input_arguments(self, data_dict):
        for item in self.header_input:
            if item in data_dict:
                self.widgets[item].setText(data_dict[item])
            elif '현재가' in data_dict:
                cur_price = abs(int(data_dict['현재가']))
                self.widgets[self.KEY_price].setValue(cur_price)


class PredictionAnalyzer(QObject):
    error_signal = pyqtSignal(str)
    ref_date = stt.timestamp_ref_date()
    pred_file = f'..\\MachineLearningTest\\prediction_data\\KOSPI-multi\\{stt.timestamp_kw_str(ref_date)}.pkl'
    y_data_file = f'..\\MachineLearningTest\\prediction_data\\KOSPI-multi\\{stt.timestamp_kw_str(ref_date)}.npy'
    isnone = False
    pred_df = pd.DataFrame()
    data_y = np.array([])
    CLASS_0 = 'class_0'
    CLASS_1 = 'class_1'
    CLASS_2 = 'class_2'

    def __init__(self, **kwargs):
        super().__init__()
        if 'latest' in kwargs:
            self.set_reference_date(kwargs['latest'])
        self.load_prediction_data()
        self.verify_price()

    def set_reference_date(self, ref_date):
        self.ref_date = pd.Timestamp(ref_date)
        self.pred_file = f'..\\MachineLearningTest\\prediction_data\\KOSPI-multi\\{stt.timestamp_kw_str(self.ref_date)}.pkl'
        self.y_data_file = f'..\\MachineLearningTest\\prediction_data\\KOSPI-multi\\{stt.timestamp_kw_str(self.ref_date)}.npy'

    def load_prediction_data(self):
        self.isnone = False
        if os.path.isfile(self.pred_file):
            self.pred_df = pd.read_pickle(self.pred_file)
        else:
            self.pred_df = pd.DataFrame()
            self.isnone = True
        if os.path.isfile(self.y_data_file):
            self.data_y = np.load(self.y_data_file)
        else:
            self.data_y = np.array([])
            self.isnone = True

    def extract_codes(self):
        if not self.isnone:
            return self.pred_df[stt.PD_col_codes].str.slice(0, 6).values

    def verify_price(self):
        if not self.isnone:
            self.pred_df[self.CLASS_0] = self.pred_df[stt.PD_col_ratio] > 1.05
            self.pred_df[self.CLASS_1] = (self.pred_df[stt.PD_col_ratio] < 1.05) & (self.pred_df[stt.PD_col_ratio] > 1.0)
            self.pred_df[self.CLASS_2] = self.pred_df[stt.PD_col_ratio] < 1.0
            col_high = [f'High-{day}' for day in range(1, 6)]
            self.pred_df['highest'] = self.pred_df[col_high].max(axis=1)
            self.pred_df['code'] = self.pred_df[stt.PD_col_codes].str.slice(stop=6)
            self.pred_df['Sell'] = ((self.pred_df['highest'] - 1.0) * 0.3 + 1.0) * self.pred_df['Close']
            self.pred_df['Buy'] = ((self.pred_df['Low-1'] - 1.0) * 0.5 + 1.0) * self.pred_df['Close']
            ticksize = self.pred_df['Close'].apply(stt.get_tick_size)
            self.pred_df['Sell'] = (self.pred_df['Sell'] / ticksize).astype(int) * ticksize
            self.pred_df['Buy'] = (self.pred_df['Buy'] / ticksize).astype(int) * ticksize

    def get_stocklist_by_class(self, bsclass):
        return self.pred_df.loc[self.pred_df[bsclass], 'code'].to_list()


class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=3, height=3, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        FigureCanvas.__init__(self, fig)
        self.setParent(parent)
        FigureCanvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

    def clear(self):
        self.axes.clear()

    def plot_edge(self, pd_series):
        xf = pd_series['X']
        yf = pd_series['Y']
        al = pd_series['a_left']
        ar = pd_series['a_right']
        if (al.shape[0] < 2) | (ar.shape[0] < 2):
            al = np.append(al, 0)
            ar = np.append(ar, 0)
        b = [-pd_series['b1'], pd_series['b2']]
        b_tot = pd_series['b_tot']
        b_guide = np.max(yf) + 1
        k = pd_series['k']
        xrange = [np.min(xf), np.max(xf)]
        yrange = [np.min(yf) - 2, np.max(yf) + 2]
        ylin_l = al[0] + al[1] * xf  # pipe shape(left)
        ylin_r = ar[0] + ar[1] * xf  # pipe shape(left)
        self.axes.plot(xf, yf, 'r-')
        self.axes.set_xlim(xrange[0], xrange[1])
        self.axes.set_ylim(yrange[0], yrange[1])
        self.axes.set_title('Captured edge (mm)')
        self.axes.plot(xf, ylin_l, 'c--')
        self.axes.plot(xf, ylin_r, 'y--')
        self.axes.arrow(0, 0, 0, k, color='black', shape='full', head_width=0.3, head_length=0.15,
                        length_includes_head=True)
        self.axes.arrow(0, k, 0, -k, color='black', shape='full', head_width=0.3, head_length=0.15,
                        length_includes_head=True)
        self.axes.text(0.1, k / 2, 'K')
        self.axes.arrow(b[0], b_guide, b_tot, 0, color='black', shape='full', head_width=0.15, head_length=0.3,
                        length_includes_head=True)
        self.axes.arrow(b[1], b_guide, -b_tot, 0, color='black', shape='full', head_width=0.15, head_length=0.3,
                        length_includes_head=True)
        self.axes.plot(b, [b_guide, b_guide], 'k')
        self.axes.plot([b, b], [[0.2, 0.2], [b_guide, b_guide]], 'k--')
        self.axes.text(0, b_guide + 0.1, 'B')
        self.axes.arrow(0, al[0], 0, ar[0] - al[0], color='black', shape='full', head_width=0.3, head_length=0.15,
                        length_includes_head=True)
        self.axes.arrow(0, ar[0], 0, al[0] - ar[0], color='black', shape='full', head_width=0.3, head_length=0.15,
                        length_includes_head=True)
        self.axes.text(-1, np.min([al[0], ar[0]]) - 0.3, 'Mis-alignment')
        self.draw()

    def plot_circle(self):
        circle = ptch.Circle((0, 0), 1, facecolor='none', edgecolor=(0.2, 0.2, 0.2), linewidth=3, alpha=0.5)
        self.axes.add_patch(circle)
        self.axes.set_xlim(-1.2, 1.2)
        self.axes.set_ylim(-1.2, 1.2)
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        self.axes.plot([[-1.5, 0], [1.5, 0]], [[0, -1.5], [0, 1.5]], color='gray', linestyle='dashed')
        self.axes.text(0.8, -0.15, '0')
        self.axes.text(-0.2, 0.8, '90')
        self.axes.text(-0.91, -0.15, '180')
        self.axes.text(0.05, -0.87, '-90')

    def plot_test_done_circle(self, test_done_logical, edges):
        for idx in range(0, len(test_done_logical)):
            if test_done_logical[idx]:
                donearc = ptch.Arc((0, 0), 2.12, 2.12, theta1=edges[idx] + 0.3, theta2=edges[idx + 1] - 0.3, color='k',
                                   linewidth=7, alpha=0.5)
                self.axes.add_patch(donearc)

    def draw_testpts(self, polar_pos_rad, passfail):
        if passfail.shape[0] < 1:
            return
        xp = np.array([np.cos(polar_pos_rad), 1.1 * np.cos(polar_pos_rad)])
        yp = np.array([np.sin(polar_pos_rad), 1.1 * np.sin(polar_pos_rad)])
        for idx in range(polar_pos_rad.shape[0]):
            if passfail[idx]:
                self.axes.plot(xp[:, idx], yp[:, idx], c='g', linewidth=2, alpha=0.5)
            else:
                self.axes.plot(xp[:, idx], yp[:, idx], c='r', linewidth=2, alpha=0.5)
        self.draw()

    def draw_pie_chart(self, values, **kwargs):
        explode = np.full(len(values), 0.1)
        if 'labels' in kwargs:
            labels = kwargs['labels']
            self.axes.pie(values, explode=explode, labels=labels, shadow=True, startangle=90)
        else:
            self.axes.pie(values, explode=explode, shadow=True, startangle=90)
        self.axes.axis('equal')

    def draw_bar_chart(self, values, **kwargs):
        ind = np.arange(len(values))
        width = 0.35
        rects = self.axes.bar(ind, values, width)
        # Add some text for labels, title and custom x-axis tick labels, etc.
        self.axes.set_ylabel('Cases')
        self.axes.set_title('Test results')
        self.axes.set_xticks(ind)
        if 'labels' in kwargs:
            self.axes.set_xticklabels(kwargs['labels'])
        for rect in rects:
            height = rect.get_height()
            self.axes.annotate('{}'.format(height), xy=(rect.get_x() + rect.get_width() / 2, height), xytext=(0, 3),
                               textcoords="offset points", ha='center', va='bottom')
