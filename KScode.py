import myfinance.stocklist as slib
import pandas as pd

liblist = slib.StockList('Korea')
liblist.load_list()

KScode = pd.read_csv('KOSPI_code.csv')
KQcode = pd.read_csv('KOSDAQ_code.csv')

KSstr = []
for idx in range(0, len(KScode)):
    KSstr.append(str(KScode['Code'][idx]).zfill(6) + '.KS')
KQstr = []
for idx in range(0, len(KQcode)):
    KQstr.append(str(KQcode['Code'][idx]).zfill(6) + '.KQ')

liblist.add_tickers_yf(KSstr)
liblist.add_tickers_yf(KQstr)
liblist.save_list()