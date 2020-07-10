import pandas as pd
import numpy as np
from datetime import datetime
from myfinance.QTstockdata import StockData
import myfinance.static as stt
import os
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject


class StockList(QObject):
    status_update = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, list_name):
        super().__init__()
        self.libpath = '.\\Lib\\'
        self.libfilename = list_name + '.lib'
        self.libcol = ['Tickers', 'Name', 'Type', 'Exchange', 'Start', 'Latest', 'nfo', 'active']
        if not (os.path.isdir(self.libpath)):
            os.makedirs(os.path.join(self.libpath))
        if os.path.isfile(self.libpath + self.libfilename):
            self.library = self.load_list()
            self.file_exist = True
        else:
            self.library = pd.DataFrame(columns=self.libcol)
            self.file_exist = False

    @pyqtSlot(str)
    def log(self, log_string):
        self.status_update.emit(log_string)

    def error_generate(self, error_msg):
        self.error_signal.emit(f'{error_msg}')

    def add_tickers_yf(self, items):
        for ticker in items:
            self.log('Current Ticker : ' + ticker)
            if np.any(self.library['Tickers'].to_numpy() == ticker):
                self.log('X - ' + ticker + ' is already in your library.')
            else:
                try:
                    yftick = StockData(ticker, is_yf=True)
                    self.library.loc[len(self.library)] = [ticker, yftick.get_name(), yftick.get_type(),
                                                           yftick.get_exchange(), yftick.get_start_timestamp(),
                                                           yftick.get_latest_timestamp(), True, True]
                    yftick.save_info()
                    yftick.save_history()
                    self.log('O - Ticker "' + ticker + '" has been added.')
                except Exception as e:
                    self.error_generate(f'Could not download the information. : {e}')
                    continue

    def add_tickers_yf_from_csv(self, csvfilepath):
        codetable = pd.read_csv(csvfilepath)
        self.log('\n' + str(codetable) + '\n')
        for idx in range(0, len(codetable)):
            ticker = str(codetable['Code'][idx])
            self.log('Current Ticker : ' + ticker)
            if np.any(self.library['Tickers'].to_numpy() == ticker):
                self.log('X - ' + ticker + ' is already in your library.')
            else:
                try:
                    yftick = StockData(ticker, is_yf=True)
                    source = codetable.loc[idx]
                    yftick.info = source
                    nfo = False
                except Exception as e:
                    self.error_generate(f'Ticker "{ticker}" couldn\'t be added. : {e}')
                    continue
                if nfo:
                    yftick.save_info()
                yftick.sort_drop_dup()
                yftick.save_history()
                self.library.loc[len(self.library)] = [ticker, yftick.get_name(), yftick.get_type(),
                                                       yftick.get_exchange(), yftick.get_start_timestamp(),
                                                       yftick.get_latest_timestamp(), True, True]
                self.log('O - Ticker "' + ticker + '" has been added.')
        self.save_list()

    def update_list_yf(self, csvfilepath):
        try:
            if not self.file_exist:
                self.log('Add tickers to index library')
                self.add_tickers_yf_from_csv(csvfilepath)
            today_stamp = pd.Timestamp(datetime.today())
            up2date_stamp = pd.Timestamp(today_stamp.timestamp() - 3600 * 24, unit='s')
            need2update = (self.library['Latest'] < up2date_stamp).to_numpy()
            if np.any(need2update):
                for idx in need2update.nonzero()[0]:
                    ticker = self.library.loc[idx, 'Tickers']
                    finaldate = self.library.loc[idx, 'Latest']
                    startdate = pd.Timestamp(finaldate.timestamp() + 3600 * 24, unit='s')
                    yftick = self.load_ticker(idx, is_yf=True)
                    yftick.update_history_yh(start=startdate.strftime('%Y-%m-%d'), end=None)
                    yftick.sort_drop_dup()
                    yftick.save_history()
                    self.library.loc[idx, 'Latest'] = yftick.get_latest_timestamp()
                    self.log('Ticker "' + ticker + '" has been updated.')
            self.save_list()
        except Exception as e:
            self.error_generate(e)
            raise

    def kw_stock_codes_update(self, csvfilepath):
        try:
            self.log('Load tickers list from ' + csvfilepath)
            today_stamp = pd.Timestamp(datetime.today())
            codetable = pd.read_csv(csvfilepath)
            code_list = []
            code_length = 6
            for idx in range(0, len(codetable)):
                if codetable['exchange'][idx] == 'KSC':
                    ticker = str(codetable['Code'][idx]).zfill(code_length) + '.KS'
                elif codetable['exchange'][idx] == 'KOE':
                    ticker = str(codetable['Code'][idx]).zfill(code_length) + '.KQ'
                else:
                    ticker = str(codetable['Code'][idx])
                # print('Current Ticker : ' + ticker)
                if np.any(self.library['Tickers'].to_numpy() == ticker):
                    tick_no = self.find_ticker_idx(ticker, exact=True)
                    tickline = self.library.loc[tick_no]
                    active = tickline['active']
                    isupdate, ref_stamp = stt.timestamp_comp_stockmarket(tickline['Latest'], today_stamp)
                    if isupdate & active:
                        code_list.append(ticker[0:code_length])
                else:
                    source = codetable.loc[idx]
                    kwtick = StockData(ticker, is_yf=False)
                    kwtick.info = source
                    nfo = False
                    active = True
                    tick_no = len(self.library)
                    latest_stamp = pd.Timestamp(0, unit='s')
                    self.library.loc[tick_no] = [ticker, source['shortName'], source['quoteType'], source['exchange'],
                                                 latest_stamp, latest_stamp, nfo, active]
                    self.save_list()
                    code_list.append(ticker[0:code_length])
                    self.log('O - Ticker "' + ticker + '" has been added.')
            return code_list
        except Exception as e:
            self.error_generate(e)
            raise

    def kw_stock_codes_update_interested(self, csvfilepath):
        try:
            self.log('Load tickers list from ' + csvfilepath)
            today_stamp = pd.Timestamp(datetime.today())
            codetable = pd.read_csv(csvfilepath)
            code_list_normal = []
            code_list_interested = []
            code_length = 6
            for idx in range(0, len(codetable)):
                if codetable['exchange'][idx] == 'KSC':
                    ticker = str(codetable['Code'][idx]).zfill(code_length) + '.KS'
                elif codetable['exchange'][idx] == 'KOE':
                    ticker = str(codetable['Code'][idx]).zfill(code_length) + '.KQ'
                else:
                    ticker = str(codetable['Code'][idx])
                # print('Current Ticker : ' + ticker)
                if np.any(self.library['Tickers'].to_numpy() == ticker):
                    tick_no = self.find_ticker_idx(ticker, exact=True)
                    tickline = self.library.loc[tick_no]
                    active = tickline['active']
                    latest_date = tickline['Latest']
                    isupdate, ref_stamp = stt.timestamp_comp_stockmarket(latest_date, today_stamp)
                    if isupdate & active:
                        if stt.timestamp_islatestworkingday(latest_date):
                            code_list_interested.append(ticker[0:code_length])
                        else:
                            code_list_normal.append(ticker[0:code_length])
                else:
                    source = codetable.loc[idx]
                    kwtick = StockData(ticker, is_yf=False)
                    kwtick.info = source
                    nfo = False
                    active = True
                    tick_no = len(self.library)
                    latest_stamp = pd.Timestamp(0, unit='s')
                    self.library.loc[tick_no] = [ticker, source['shortName'], source['quoteType'], source['exchange'],
                                                 latest_stamp, latest_stamp, nfo, active]
                    self.save_list()
                    code_list_normal.append(ticker[0:code_length])
                    self.log('O - Ticker "' + ticker + '" has been added.')
            return code_list_normal, code_list_interested
        except Exception as e:
            self.error_generate(e)
            raise

    def kw_index_codes_update(self, csvfilepath):
        try:
            today_stamp = pd.Timestamp(datetime.today())
            codetable = pd.read_csv(csvfilepath)
            code_list = []
            code_length = 3
            for idx in range(0, len(codetable)):
                ticker = str(codetable['Code'][idx]).zfill(code_length) + '.KOR'
                # print('Current Ticker : ' + ticker)
                if np.any(self.library['Tickers'].to_numpy() == ticker):
                    tick_no = self.find_ticker_idx(ticker, exact=True)
                    tickline = self.library.loc[tick_no]
                    active = tickline['active']
                    isupdate, ref_stamp = stt.timestamp_comp_stockmarket(tickline['Latest'], today_stamp)
                    if isupdate & active:
                        code_list.append(ticker[0:code_length])
                else:
                    source = codetable.loc[idx]
                    kwtick = StockData(ticker, is_yf=False)
                    kwtick.info = source
                    nfo = False
                    active = True
                    tick_no = len(self.library)
                    latest_stamp = pd.Timestamp(0, unit='s')
                    self.library.loc[tick_no] = [ticker, source['shortName'], source['quoteType'], source['exchange'],
                                                 latest_stamp, latest_stamp, nfo, active]
                    self.save_list()
                    code_list.append(ticker[0:code_length])
                    self.log('O - Ticker "' + ticker + '" has been added.')
            return code_list
        except Exception as e:
            self.error_generate(e)
            raise

    def get_latest_updated_dates_from_codes(self, code_list):
        try:
            latest_list = list()
            for code in code_list:
                time_list = self.library.loc[self.library['Tickers'].str.contains(code), 'Latest']
                if len(time_list) > 0:
                    latest_list.append(pd.Timestamp(time_list.values[0]))
            return latest_list
        except Exception as e:
            self.error_generate(e)
            raise

    def find_ticker_idx(self, ticker, **kwargs):
        try:
            exact = kwargs['exact']
            if exact:
                restick = self.library[(self.library['Tickers'] == ticker)]
            else:
                restick = self.library[self.library['Tickers'].str.contains(ticker)]
            if len(restick.index) < 1:
                return -1
            else:
                return restick.index[0]
        except Exception as e:
            self.error_generate(e)
            raise

    def save_list(self):
        self.library.to_pickle(self.libpath + self.libfilename)
        self.log('Library saved as ' + self.libfilename)

    def load_list(self):
        tickers = pd.read_pickle(self.libpath + self.libfilename)
        return tickers

    def is_ticker_file(self, idx):
        data = StockData(self.library['Tickers'][idx])
        return data.is_hist_file()

    def load_ticker(self, idx, is_yf=False):
        data = StockData(self.library['Tickers'][idx], is_yf=is_yf)
        if data.is_hist_file():
            data.load_history()
        return data

    def get_ticker(self, idx):
        return self.library['Tickers'][idx]

