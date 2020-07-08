import yfinance as yf
import pandas as pd
import numpy as np
import os


class StockData:
    def __init__(self, Ticker, is_yf=False):
        self.ticker = Ticker
        self.libpath = '.\\Lib\\'
        self.columns = ['Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits']
        self.histfilename = Ticker + '.his'
        self.infofilename = Ticker + '.nfo'
        self.yahoo = is_yf
        if self.yahoo:
            self.yfstock = yf.Ticker(Ticker)
        else:
            self.yfstock = None
        self.info = pd.Series()
        self.history = pd.DataFrame(columns=self.columns)
        if not (os.path.isdir(self.libpath)):
            os.makedirs(os.path.join(self.libpath))
        if os.path.isfile(self.libpath + self.histfilename):
            self.history = pd.read_pickle(self.libpath + self.histfilename)
        else:
            if self.yahoo:
                self.history = self.get_history()
            else:
                self.history = pd.DataFrame(columns=self.columns)

    def get_history(self, period="max"):
        if self.yfstock is None:
            return None
        else:
            hist = self.yfstock.history(period=period)
            return hist

    def update_history(self, **kwargs):
        if self.yahoo:
            if 'start' in kwargs:
                start = kwargs['start']
                update = self.yfstock.history(start=start, end=None)
            elif 'period' in kwargs:
                period = kwargs['period']
                update = self.yfstock.history(period=period)
            else:
                print('Enter some input arguments at "start" or "period"')
                return
            try:
                self.history = self.history.append(update)
            except:
                print('Got some errors')
                return
        else:
            return

    def get_info_from_yf(self):
        if self.yahoo:
            info = pd.Series(self.yfstock.info)
            return info
        else:
            return

    def get_name(self):
        return self.info['shortName']

    def get_type(self):
        return self.info['quoteType'].upper()

    def get_exchange(self):
        return self.info['exchange']

    def get_start_timestamp(self):
        return self.history.index[0]

    def get_latest_timestamp(self):
        return self.history.index[-1]

    def save_history(self):
        self.history.to_pickle(self.libpath + self.histfilename)

    def load_history(self):
        if self.is_hist_file():
            self.history = pd.read_pickle(self.libpath + self.histfilename)

    def save_info(self):
        self.info.to_pickle(self.libpath + self.infofilename)

    def load_info(self):
        if self.is_info_file():
            self.info = pd.read_pickle(self.libpath + self.infofilename)

    def is_info_file(self):
        return os.path.isfile(self.libpath + self.infofilename)

    def is_hist_file(self, libpath='.\\Lib\\'):
        return os.path.isfile(libpath + self.histfilename)

    def sort_drop_dup(self):
        self.history.index.name = 'Date'
        self.history = self.history.sort_index()
        self.history = self.history.drop_duplicate()
        if not self.history.index.is_unique:
            uniq_index = self.history.index.unique().to_numpy()
            unindex = uniq_index[((self.history['Close'].groupby(level=0).count() > 1).to_numpy().nonzero()[0])]
            unindex = np.flip(unindex)
            for idx in unindex:
                sliceidx = self.history.index.get_loc(idx)
                dup = self.history[sliceidx]
                remdup = dup.iloc[np.argmax(dup['Volume'].to_numpy())]
                self.history = self.history.iloc[0:sliceidx.start].append(remdup).append(self.history.iloc[sliceidx.stop:])
