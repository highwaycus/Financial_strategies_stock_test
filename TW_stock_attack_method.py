import os
import gc
import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay
import requests
from bs4 import BeautifulSoup
import datetime
import time
from production_setting import tw_path_setting, sub_process_bar


# Right-Angle Attakc
# condition: close price stand on all the avg line.
# return: the open price one day after the condition is confirrmed.

loading_path = tw_path_setting(collapse='daily')[0]
# for file in os.listdir(loading_path):

# for the end_date, does it need to be the latest date or the end of month?


def load_stock_price(stock='2330', start_date=20120101, end_date=None):
    if end_date is None:
        end_date = (datetime.datetime.today() + datetime.timedelta(hours=12)).strftime('%Y%m%d')
    try:
        trans_dict = np.load('tw_data/price/{}.npy'.format(stock), allow_pickle=True).item()
    except FileNotFoundError:
        trans_dict = {}
    if len(trans_dict) and end_date in trans_dict:
        return
    timestamp_0 = time.mktime(datetime.datetime.strptime(str(start_date), '%Y%m%d').timetuple())
    timestamp_1 = time.mktime(datetime.datetime.strptime(str(end_date), '%Y%m%d').timetuple())
    url = 'https://ws.api.cnyes.com/ws/api/v1/charting/history?resolution=D&symbol=TWS:{}:STOCK&from={}&to={}&quote=1'.format(
        stock, int(timestamp_1), int(timestamp_0))
    # url = 'https://invest.cnyes.com/twstock/TWS/2330/history'
    resp = requests.get(url)

    soup = BeautifulSoup(resp.text, 'lxml')
    str_record = soup.body.p.__dict__['next_element']
    str_record = str_record.replace('null', '\"\"')
    import ast
    res = ast.literal_eval(str(str_record))
    # null不能放進去
    for i in range(len(res['data']['t'])):
        day_ = int(datetime.datetime.fromtimestamp(int(res['data']['t'][i])).strftime('%Y%m%d'))
        if day_ not in trans_dict:
            trans_dict[day_] = {'o': res['data']['o'][i], 'h': res['data']['h'][i], 'l': res['data']['l'][i],
                                'c': res['data']['c'][i], 'v': res['data']['v'][i]}
    save_dir = 'tw_data/price/'
    try:
        os.makedirs(save_dir)
    except:
        pass
    if not trans_dict:
        print('\n{} is empty'.format(stock))
        return
    np.save(save_dir + '{}.npy'.format(stock), trans_dict, allow_pickle=True)
    gc.collect()


def feature_engineering(stock, df=None, load_dir='tw_data/price/'):
    if df is None:
        try:
            df = np.load(load_dir + '{}.npy'.format(stock), allow_pickle=True).item()
        except FileNotFoundError:
            print('\n{} has no file'.format(stock))
            return
    tmp_df = pd.DataFrame(df).T
    tmp_df = tmp_df.sort_index()
    ma_list = [3, 5, 10, 20, 60]
    for ma in ma_list:
        tmp_df['ma_{}'.format(ma)] = tmp_df['c'].rolling(ma).mean()
    # Dragon on Sky: price > all ma line
    tmp_df['sky'] = tmp_df.apply(lambda x: 1 if (x['c'] > max([x['ma_{}'.format(m)] for m in ma_list])) and (str(x['ma_{}'.format(max(ma_list))]) != 'nan') else 0, axis=1)
    tmp_df['sky-1'] = tmp_df['sky'].shift(1)
    tmp_df['take_off'] = tmp_df.apply(lambda x: 1 if x['sky'] and (not x['sky-1']) and (str(x['sky-1']) != 'nan') else 0, axis=1)
    tmp_df['take_off_signal'] = tmp_df['take_off'].shift(1)
    # return: open to close
    h_list = [0, 1, 2, 3, 4, 5, 10]
    for h in h_list:
        tmp_df['o-h{}'.format(h)] = tmp_df['o'].shift(h)
        tmp_df['h{}_return'.format(h)] = tmp_df.apply(lambda x: (x['c'] - x['o-h{}'.format(h)])/x['o-h{}'.format(h)] if str(x['o-h{}'.format(h)]) not in ['nan', '0', '0.0'] else 0, axis=1)
        del tmp_df['o-h{}'.format(h)]
    for pre in [-1, -2, -3, -4, -5, -10]:
        tmp_df['pct_{}d'.format(pre)] = tmp_df['c'].pct_change(pre)
    tmp_df['3d_max_return'] = tmp_df.apply(lambda x: max([x['h{}_return'.format(h)] for h in [0, 1, 2,3]]) if str(x['h3_return']) not in ['nan', '0'] else np.NAN, axis=1)
    df = {d: {c: tmp_df.loc[d, c] for c in list(tmp_df.columns)} for d in tmp_df.index}
    np.save(load_dir + '{}.npy'.format(stock), df, allow_pickle=True)
    del tmp_df


def data_process_init():
    stock_list = [file.split('_')[1][:-4] for file in os.listdir('tw_data/日法人持股估計/')]
    jj, total_step = 1, len(stock_list)
    for stock in stock_list:
        load_stock_price(stock=stock, start_date=20120101, end_date=None)
        feature_engineering(stock, df=None, load_dir='tw_data/price/')
        jj = sub_process_bar(jj, total_step)


def collect_record():
    load_dir = 'tw_data/price/'
    summary = {}
    for file in os.listdir(load_dir):
        df = np.load(load_dir + file, allow_pickle=True).item()
        tmp = {'{}_{}'.format(file[:-4], c): df[c] for c in df if df[c]['take_off_signal'] }
        summary = {**summary, ** tmp}


def plot_main(summary):
    import matplotlib.pyplot as plt
    plt.figure()
    d3max_list = [summary[c]['3d_max_return'] for c in summary if summary[c]['3d_max_return'] < 0.11]
    print(np.mean(d3max_list))
    print(np.median(d3max_list))
    plt.hist(d3max_list, bins=50)


def show_signal(stock, record=None, load_dir='tw_data/price/'):
    if record is None:
        try:
            record = np.load(load_dir + '{}.npy'.format(stock), allow_pickle=True).item()
        except FileNotFoundError:
            return
    if max(record) >= int((datetime.datetime.today() -BDay(2)).strftime('%Y%m%d')):
        max_d = max(record)
        if record[max_d]['take_off_signal']:
            print('\n', stock, max_d)


def daily_main(load_dir='tw_data/price/'):
    jj, total_step = 1, len(os.listdir(load_dir))
    for file in os.listdir(load_dir):
        if file.endswith('npy') and file.find('summary') == -1:
            stock = file[:-4]
            load_stock_price(stock=stock, start_date=20210831, end_date=None)
            feature_engineering(stock, df=None, load_dir=load_dir)
            # show_signal(stock, record=None, load_dir=load_dir)
        jj = sub_process_bar(jj, total_step)


