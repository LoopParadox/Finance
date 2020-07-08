import myfinance.stocklist as slib
import pandas as pd


test_library = slib.StockList('Korea')
dataCounts = (test_library.library['Latest'] - test_library.library['Start'])
suff = dataCounts>pd.Timedelta(300, unit='D')
idx = suff.to_numpy().nonzero()[0]
