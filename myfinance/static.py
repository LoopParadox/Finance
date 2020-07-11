import pandas as pd
import numpy as np
from myfinance.constants import *


STR_date = '%Y%m%d'
PD_col_codes = 'Tickers'
PD_col_ratio = 'Ratio_max'
PD_col_price = 'Price_max'
PD_col_days = list(range(1, 6))
PD_col_targets = ['Close', 'Open', 'High', 'Low']
PD_columns = [PD_col_ratio, PD_col_price] + [f'{item}-{day}' for item in PD_col_targets for day in PD_col_days]


def timestamp_day_before_n_days(today_pandas, n=1):
    yesterday = pd.Timestamp(today_pandas.timestamp() - (n * 3600 * 24), unit='s')
    return yesterday


def timestamp_date_only(timestamp_pandas):
    return pd.Timestamp(timestamp_kw_str(timestamp_pandas))


def timestamp_comp_stockmarket(latest, today):
    time_ref = timestamp_ref_date(today)
    return latest < time_ref, time_ref


def timestamp_ref_date(today=pd.Timestamp.now()):
    if today.hour < 19:
        time_ref = timestamp_day_before_n_days(today)
    else:
        time_ref = today
    ref_weekday = time_ref.weekday()
    if ref_weekday > 4:
        time_ref = timestamp_day_before_n_days(time_ref, n=(ref_weekday - 4))
    time_ref = timestamp_date_only(time_ref)
    return time_ref


def timestamp_islatestworkingday(latest_date):
    timenow = pd.Timestamp.now()
    if timenow.hour > 19:
        today = timestamp_ref_date()
        delta = today - latest_date
        if today.weekday() == 0:
            ref_day = 3
        else:
            ref_day = 1
        if delta.days == ref_day:
            return True
        else:
            return False
    else:
        return False


def timestamp_kw_str(timestamp_pandas):
    return timestamp_pandas.strftime(STR_date)


def timestamp_find_next_opening(today=pd.Timestamp.now(), opening_time=9):
    if today.hour < opening_time:
        next_opening = timestamp_date_only(today) + pd.Timedelta(hours=opening_time)
    else:
        next_opening = timestamp_date_only(today) + pd.Timedelta(days=1, hours=opening_time)
    if next_opening.weekday() > 4:
        next_opening = next_opening + pd.Timedelta(days=(7-next_opening.weekday()))
    return next_opening


def stock_table_indexing():
    """parameters shown in Tester UI"""
    return ['종목코드', '종목명', '현재가', '기준가', '전일대비', '등락율', '거래량', '매도호가', '매수호가']


def get_tick_size(current_price):
    if current_price < 1000:
        tick_size = 1
    elif current_price < 5000:
        tick_size = 5
    elif current_price < 10000:
        tick_size = 10
    elif current_price < 50000:
        tick_size = 50
    elif current_price < 100000:
        tick_size = 100
    elif current_price < 500000:
        tick_size = 500
    else:
        tick_size = 1000
    return tick_size


def cal_alarm_interval(alarm_hour):
    time_now = pd.Timestamp.now()
    if time_now.hour < alarm_hour:
        time_update = pd.Timestamp(time_now.strftime("%Y%m%d")) + pd.Timedelta(hours=alarm_hour)
    else:
        time_update = pd.Timestamp(time_now.strftime("%Y%m%d")) + pd.Timedelta(days=1) + pd.Timedelta(hours=alarm_hour)
    time_delta = time_update - time_now
    return int(time_delta.total_seconds() * 1000)


def cal_alarm_interval_until_target(target):
    time_now = pd.Timestamp.now()
    target_time = pd.Timestamp(target)
    time_delta = target_time - time_now
    if time_now > target_time:
        time_delta = time_delta - pd.Timedelta(days=time_delta.days)
    return int(time_delta.total_seconds() * 1000)
