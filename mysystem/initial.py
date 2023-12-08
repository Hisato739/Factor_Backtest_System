import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False
import warnings
warnings.filterwarnings('ignore')
import pickle
from utils import get_date_list, get_ticker_list
import tushare as ts
ts.set_token('0bd4d0db1c8d8d9479f1d653f6f7ebc84073083fa41a8cb87ad889f6')
pro = ts.pro_api()
import time
import os
module_path = os.path.dirname(__file__)

def initialize_stk_daily():
    if not os.path.exists(module_path + '/cooked_data'):
        os.makedirs(module_path + '/cooked_data')

    print('-----initialize stk daily-----')
    df = pd.read_feather(os.path.dirname(os.path.dirname(module_path)) + '/data/stk_daily.feather')

    # 剔除北交所股票
    place = df['stk_id'].apply(lambda x: x[-2:])
    df = df.loc[place != 'BJ']

    # 价格复权
    prices = ['open','high','low','close']
    df[[f'{p}_adj' for p in prices]] = df[prices].multiply(df['cumadj'], axis = 0)

    # 获取stk_id列表和date列表
    ticker_list = df['stk_id'].unique()
    date_list = df['date'].unique()

    # cols为需要dump的字段
    cols = [c for c in df.columns if c not in ['stk_id','date','cumadj']]

    # 按股票代码划分df
    groups = list(df.groupby('stk_id'))
    for ticker, ticker_df in groups:
        ticker_df.set_index('date', inplace = True)

    # 将各字段dump为以date_list为index，以ticker_list为columns的DataFrame
    for c in cols:
        print(f'dumping {c}.pkl')
        df_c = pd.DataFrame(index = date_list, columns = ticker_list)
        for ticker, ticker_df in tqdm(groups):
            df_c[ticker] = ticker_df[c]
        with open(module_path + f'/cooked_data/{c}.pkl', 'wb') as f:
            pickle.dump(df_c, f)
    
    with open(module_path + f'/cooked_data/ticker_list.pkl', 'wb') as f:
        pickle.dump(ticker_list, f)
    with open(module_path + f'/cooked_data/date_list.pkl', 'wb') as f:
        pickle.dump(date_list, f)

def initialize_trade_flag():
    if not os.path.exists(os.path.dirname(module_path) + '/newdata'):
        os.makedirs(os.path.dirname(module_path) + '/newdata')

    print('-----initialize trade flag-----')
    # 获取交易信息trade_flag, True表示正常交易, False表示停牌
    ticker_list = get_ticker_list()
    date_list = get_date_list()
    trade_flag = pd.DataFrame(index = date_list, columns = ticker_list)

    for date in tqdm(date_list):
        df = pro.suspend_d(suspend_type = 'S', trade_date = date.strftime('%Y%m%d'))
        trade_flag.loc[date, df['ts_code'].loc[df['ts_code'].isin(ticker_list)].values] = False
        time.sleep(0.1)
    trade_flag = trade_flag.fillna(True)
    with open(os.path.dirname(module_path) + f'/newdata/trade_flag.pkl', 'wb') as f:
        pickle.dump(trade_flag, f)

def initialize_HS300():
    print('-----initialize HS300-----')
    # 获取沪深300成分股信息valid_HS300，True表示某股票在当期沪深300成分股内，反之为False
    ticker_list = get_ticker_list()
    date_list = get_date_list()

    valid_HS300 = pd.DataFrame(index = date_list, columns = ticker_list)
    start_date = ['20200101','20200701','20210101','20210701','20220101','20220701']
    end_date = ['20200630','20201231','20210630','20211231','20220630','20221231']

    for i in range(len(start_date)):
        df = pro.index_weight(index_code = '399300.SZ', start_date = start_date[i], end_date = end_date[i])
        dates = df['trade_date'].unique()
        for date in dates:
            tickers = df.loc[df['trade_date'] == date, 'con_code']
            valid_HS300.loc[pd.to_datetime(date), tickers] = True
            valid_HS300.loc[pd.to_datetime(date)] = valid_HS300.loc[pd.to_datetime(date)].fillna(False)
    valid_HS300 = valid_HS300.ffill()

    with open(os.path.dirname(module_path) + f'/newdata/valid_HS300.pkl', 'wb') as f:
        pickle.dump(valid_HS300, f)

if __name__ == '__main__':
    initialize_stk_daily()
    initialize_trade_flag()
    initialize_HS300()