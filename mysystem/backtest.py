import numpy as np
import pandas as pd
from mysystem.utils import get_date_list, get_ticker_list, get_trade_flag
from tqdm import tqdm
import pickle
import os
import time
import matplotlib.pyplot as plt
import seaborn as sns
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False
ticker_list = get_ticker_list()
date_list = get_date_list()
trade_flag = get_trade_flag()
module_path = os.path.dirname(__file__)

class AlphaBacktest:
    # 因子字典回测，传入因子字典alpha_dict和工程名project_name
    def __init__(self, alpha_dict, project_name):
        self.alpha_dict = alpha_dict

        # self.ipool为用于回测的复权收盘价数据
        self.ipool = pd.read_pickle(module_path + '/cooked_data/close_adj.pkl')

        # 根据工程名和当前时刻生成回测结果保存路径
        self.project_name = project_name + '_' + time.strftime('%Y%m%d_%H%M%S', time.localtime())
        if not os.path.exists(module_path + f'/output/{self.project_name}'):
            os.makedirs(module_path + f'/output/{self.project_name}')
        
    def start_backtest(self, start, end, 
                       dump_alpha = True,
                       dump_weight = True,
                       dump_pnl = True, 
                       dump_performance = True,
                       dump_correlation = True
                       ):
        #根据需求dump相应的文件
        pnl_list = []
        performance_list = []

        for alpha in self.alpha_dict:
            print(f'====={alpha}开始回测=====')
            alpha_df = self.alpha_dict[alpha]

            if dump_alpha:
                with open(module_path + f'/output/{self.project_name}/{alpha}.pkl', 'wb') as f:
                    pickle.dump(alpha_df, f)
                print(f'-----已输出{alpha}因子值文件-----')

            if dump_weight:
                weight = self.get_weight(alpha_df, start, end).round(4)
                weight.to_csv(module_path + f'/output/{self.project_name}/{alpha}_weight.csv')
                print(f'-----已输出{alpha}权重文件-----')

            net = self.get_net(weight)
            pnl = net.cumsum() + 1
            pnl_list.append(pnl)
            print(f'-----{alpha}收益计算完毕')

            performance = self.get_performance(pnl)
            IC_res = self.get_IC(alpha_df, start, end)
            performance = pd.concat([performance, IC_res])
            performance_list.append(performance)
            print(f'-----{alpha}性能指标计算完毕')

        if dump_pnl:
            pnl_df = pd.concat(pnl_list, axis = 1).round(4)
            pnl_df.columns = list(self.alpha_dict.keys())
            pnl_df.to_csv(module_path + f'/output/{self.project_name}/pnl.csv')
            plt.figure(figsize = (12,6))
            for alpha in list(self.alpha_dict.keys()):
                plt.plot(pnl_df[alpha], label = alpha)
            plt.legend()
            plt.savefig(module_path + f'/output/{self.project_name}/pnl.jpg')
            plt.close()
            print('-----已输出全因子pnl文件-----')
        
        if dump_performance:
            performance_df = pd.concat(performance_list, axis = 1).round(4)
            performance_df.columns = list(self.alpha_dict.keys())
            performance_df.to_csv(module_path + f'/output/{self.project_name}/performance.csv')
            print('-----已输出全因子回测指标文件-----')

        if dump_correlation:
            res_corr = self.get_correlation(start, end)
            res_corr_df = pd.DataFrame(res_corr, index = list(self.alpha_dict), columns = list(self.alpha_dict))
            plt.figure(figsize = (15, 15))
            sns.heatmap(res_corr_df, cmap="YlGnBu", annot = True)
            plt.savefig(module_path + f'/output/{self.project_name}/correlation.jpg')
            plt.close()
            print('-----已输出相关系数矩阵文件-----')

        print('=====全因子结束回测=====')

    def get_weight(self, alpha_df, start, end):
        # 根据因子值生成持仓权重，在保持比例的同时，多头权重的绝对值加上空头权重的绝对值归一化为1
        alpha_df_sample = alpha_df.loc[start: end]
        weight = pd.DataFrame(index = alpha_df_sample.index, columns = ticker_list)
        abssum = abs(alpha_df_sample).sum(axis = 1)
        loc = abssum > 1e-10
        weight.loc[loc] = (alpha_df_sample.loc[loc].T / abssum[loc]).T
        weight = weight.fillna(0)
        return weight
    
    def get_IC(self, alpha_df, start, end):
        # 计算单因子的平均IC、平均rankIC和IR指标
        alpha_df_sample = alpha_df.loc[start: end]
        IC = pd.DataFrame(index = alpha_df_sample.index[:-1], columns = ['IC', 'rankIC'])
        ret_df = self.ipool.shift(-1).loc[IC.index] / self.ipool.loc[IC.index] - 1
        for date in ret_df.index:
            IC.loc[date, 'IC'] = ret_df.loc[date].corr(alpha_df_sample.loc[date])
            IC.loc[date, 'rankIC'] = ret_df.loc[date].rank().corr(alpha_df_sample.loc[date].rank())
        IC_res = pd.Series(index = ['平均IC', '平均rankIC', 'IR'])
        IC_res.loc['平均IC'] = IC['IC'].mean()
        IC_res.loc['平均rankIC'] = IC['rankIC'].mean()
        IC_res.loc['IR'] = IC['IC'].mean() / IC['IC'].std()
        return IC_res
    
    def get_net(self, weight):
        # 单利回测，其中停牌的股票不计入收益
        ret_df = self.ipool.shift(-1).loc[weight.index] / self.ipool.loc[weight.index] - 1
        for date in tqdm(ret_df.index):
            ret_df.loc[date] = trade_flag.loc[date] * ret_df.loc[date]
        net = (weight * ret_df).sum(axis = 1).shift().fillna(0)
        return net
    
    def get_performance(self, pnl):
        # 计算年化收益率、标准差、夏普比率及最大回撤，年化时假定一年有252个交易日
        performance = pd.Series(index = ['年化收益率', '年化标准差', '夏普比率', '最大回撤'])
        ret = pnl.diff().dropna()
        performance['年化收益率'] = ret.mean() * 252
        performance['年化标准差'] = ret.std() * np.sqrt(252)
        performance['夏普比率'] = performance['年化收益率'] / performance['年化标准差']
        c_max = pnl.iloc[0]
        mdd = 0
        for i in range(1, len(pnl)):
            c_max = max(c_max, pnl.iloc[i])
            mdd = max(mdd, c_max - pnl.iloc[i])
        performance['最大回撤'] = mdd
        return performance
    
    def get_correlation(self, start, end):
        # 因子之间计算截面相关系数再在时序取平均
        sample_dates = date_list[(date_list >= pd.to_datetime(start)) & (date_list <= pd.to_datetime(end))]
        res_corr = np.zeros((len(self.alpha_dict), len(self.alpha_dict)))
        for date in sample_dates:
            alpha_date_list = []
            for alpha in self.alpha_dict:
                alpha_date_list.append(self.alpha_dict[alpha].loc[date])
            res_corr += pd.concat(alpha_date_list, axis = 1).corr().values
        res_corr = res_corr / len(sample_dates)
        return res_corr