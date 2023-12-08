import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')
import os
module_path = os.path.dirname(__file__)

# 获取已加工的数据字典
def get_item(items): 
    d = dict()
    for item in items:
        d[item] = pd.read_pickle(module_path + '/cooked_data' + f'/{item}.pkl')
    return d

# z-score标准化
def OpZscore(alpha):
    alpha_copy = alpha.copy()
    mean = alpha_copy.mean(axis = 1)
    std = alpha_copy.std(axis = 1)
    # 仅对标准差大于0的行标准化
    loc = std > 1e-10
    alpha_copy.loc[loc] = alpha.loc[loc].sub(mean[loc], axis = 0).div(std[loc], axis = 0)
    return alpha_copy

# 均值方差法去极值，极值压缩到边界
def OpCleanOutlier(alpha, ub = 5, lb = -5):
    alpha_copy = alpha.copy()
    alpha_copy = alpha_copy.replace([np.inf, -np.inf], np.nan)
    mean = alpha_copy.mean(axis = 1)
    std = alpha_copy.std(axis = 1)
    loc = std > 1e-10
    for date in alpha_copy.index[loc]:
        sr = alpha_copy.loc[date]
        alpha_copy.loc[date, sr > mean.loc[date] + ub * std.loc[date]] = mean.loc[date] + ub * std.loc[date]
        alpha_copy.loc[date, sr < mean.loc[date] + lb * std.loc[date]] = mean.loc[date] + lb * std.loc[date]
    return alpha_copy

# 获取全部股票代码
def get_ticker_list():
    return pd.read_pickle(module_path + '/cooked_data/ticker_list.pkl')

# 获取全部交易日历
def get_date_list():
    return pd.read_pickle(module_path + '/cooked_data/date_list.pkl')

# 获取交易/停牌信息
def get_trade_flag():
    return pd.read_pickle(os.path.dirname(module_path) + '/newdata/trade_flag.pkl')

# 获取资产池
def get_valid(ipool):
    trade_flag = get_trade_flag()

    # 该函数仅支持两种默认资产池
    assert ipool in ['all', 'HS300'], 'ipool not available!'

    if ipool == 'all':
        return trade_flag
    
    if ipool == 'HS300':
        valid_HS300 = pd.read_pickle(os.path.dirname(module_path) + '/newdata/valid_HS300.pkl')
        return valid_HS300 * trade_flag
    
# 用资产池过滤因子
def valid_filter(alpha, ipool):
    valid = get_valid(ipool)
    alpha_copy = pd.DataFrame(index = alpha.index, columns = alpha.columns)
    for i in range(1, len(alpha_copy)):
        # 细节：用上一个交易日的valid信息去过滤，否则就会用到未来信息
        date = alpha_copy.index[i]
        last_date = alpha_copy.index[i-1]
        alpha_copy.loc[date, valid.loc[last_date]] = alpha.loc[date, valid.loc[last_date]]
    return alpha_copy
