import myfinance.stocklist as mylist


tickers = mylist.StockList('index')
tickerlist = ['^GSPC', '^DJI', '^IXIC', '^N225', '^KS11', '^KQ11', '^RUT', '^FTSE', '^GDAXI', '^HSI', 'EURUSD=X', 'JPY=X', 'KRW=X', 'CL=F', 'GC=F', 'AAPL', 'MSFT']
tickers.add_tickers_yf(tickerlist)
tickers.save_list()