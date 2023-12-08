# <center> 截面因子回测系统 <center>

## 一、初始化系统

本系统使用python 3.11.0，所需的python包见requirements.txt

在初始化之前，需要保证系统目录"Factor_Backtest_System"与原始数据"data"处于同一工作目录，之后在cmd终端运行命令：

```
python Factor_Backtest_System/mysystem/initial.py
```

即可初始化系统，用于原数据的加工以及从tushare平台获取一些必要的新数据，该过程需耗费数分钟。

## 二、模块导入

下面以"Factor_Backtest_System"目录下已创建的样例代码test.ipynb为例说明本系统因子回测的全流程。

本系统提供了一些方便因子回测的功能函数，我们首先导入这些函数：

``` python
from mysystem.utils import *
```
而将计算好的因子进行回测则需要用到backtest库中的AlphaBacktest：
``` python
from mysystem.backtest import AlphaBacktest
```

## 三、数据获取

模型加工好的数据都是规整的DataFrame格式，其中Index固定为2020~2022所有交易日，columns为该时间段的沪深全市场股票（剔除了北交所股票）。

其中，每个DataFrame都是一个字段，我们可以通过get_item()函数调取一个或多个字段（都需传入列表），例如：

``` python
data_dict = get_item(['close_adj','volume'])
```
得到一个长度为2的字典，keys即为字段名，values为复权收盘价和成交量对应的DataFrame.

本系统支持的所有字段如下：

|  字段名   | 含义  |
|  :----:  | :----:  |
| open  | 开盘价 |
| close  | 收盘价 |
| high  | 最高价 |
| low  | 最低价 |
| open_adj  | 复权开盘价 |
| close_adj  | 复权收盘价 |
| high_adj  | 复权最高价 |
| low_adj  | 复权最低价 |
| volume  | 成交量 |
| amount  | 成交额 |

此外，get_ticker_list()函数可以获取本系统的全部股票代码、get_date_list()函数可以获取2020~2022的所有交易日：

``` python
ticker_list = get_ticker_list()
date_list = get_date_list()
```

## 四、对原始因子进行资产池过滤

利用获取到的数据可以轻松地构建简单的因子，例如：

``` python
alpha1 = -data_dict['close_adj'].pct_change(5).shift()
```

alpha1为一个5日反转因子，注意，本系统会将当期因子值直接用于当期的交易，所以<font color=Red>当期因子值禁止使用当期数据，否则就会涉及未来信息</font>，因此上述因子构建的代码中会加入shift()操作。

注意到上述因子值是对所有股票都计算的，如果要在给定的资产池中回测，则需要对因子值进行过滤，非资产池的股票将会被填充为nan，注意每一期的资产池可能不一样。

本系统提供两种默认的资产池如下：

|  资产池   | 含义  |
|  :----:  | :----:  |
| all  | 全市场上一交易日非停牌股票 |
| HS300  | 全市场上一交易日非停牌股票且为上一交易日沪深300成分股 |

资产池过滤函数为valid_filter()，例如对alpha1进行HS300过滤：

``` python
alpha1 = valid_filter(alpha1, 'HS300')
```

由于资产池过滤总是可以处理停牌的股票，因此我们推荐<font color=Red>对任何因子总是使用valid_filter函数进行过滤</font>。此外，过滤时采用的信息也是截止到上一交易日的，有效地避免使用未来信息。

## 五、因子预处理

本系统提供两种因子预处理函数如下：

|  因子预处理函数   | 含义  |
|  :----:  | :----:  |
| OpZscore()  | 截面z-score标准化，将截面分布调整为均值为0，标准差为1 |
| OpCleanOutlier()  | 截面均值方差法去极值，把阈值以外的极值压缩到阈值，默认上下阈值均为5倍标准差，可以由ub和lb参数控制 |

以alpha1为例，可以将两种因子预处理函数套用如下：

``` python
alpha1 = OpZscore(OpCleanOutlier(alpha1))
```

## 六、因子字典回测

假设我们已经构造了三个因子alpha1, alpha2, alpha3, 分别代表5日反转因子、20日反转因子、量比因子（具体过程见样例代码），我们可以同时对这三个单因子进行回测。

首先构建因子字典：

``` python
alpha_dict = {'5dr': alpha1, '20dr': alpha2, 'volume_ratio': alpha3}
```

然后确定本次回测的工程名，例如project1，再选定回测区间即可，例如：

``` python
project_name = 'project1'
AlphaBacktest(alpha_dict, project_name).start_backtest('20200701','20221231')
```

在运行AlphaBacktest后，系统会在output文件夹自动创建一个"工程名+当前时间"的文件夹（避免多次尝试时文件夹覆盖），在里面存储全部回测文件，包括：每个因子的因子值、持仓权重、全部因子的pnl、性能指标、相关系数热力图，其中的计算细节如下表：

|  回测计算内容   | 细节  |
|  :----:  | :----:  |
| 因子权重  | 对于每个因子，每个截面，在保持比例的同时，多头权重的绝对值加上空头权重的绝对值归一化为1 |
| pnl  | 单利回测，每个截面固定用单位资金1进行交易，无手续费 |
| 性能指标  | 包括年化收益率、年化标准差、夏普比率（无风险利率取0）、最大回撤、平均IC、平均rankIC、IR |
| 相关系数热力图  | 在每个截面计算因子值间的相关系数，并在截面取平均 |

用户也可以根据需求调整输出文件，在start_backtest()函数中有默认参数：

``` python
dump_alpha = True, dump_weight = True, dump_pnl = True, dump_performance = True, dump_correlation = True
```

调整参数值为False即可不输出对应的文件。
