# Backtest for the strategy " Follow Mr.S"
import gc

import pandas as pd
import requests
import sys
import re
import os
import datetime
from bs4 import BeautifulSoup
import numpy as np
from pandas.tseries.offsets import MonthEnd
from pandas.tseries.offsets import BDay
import yfinance as yf

def display_setting():
    np.set_printoptions(precision=5, suppress=True, linewidth=150)
    pd.set_option('display.width', 10000)
    pd.set_option('display.max_colwidth', 1000)
    pd.set_option('display.max_rows', 2000)
    pd.set_option('display.max_columns', 500)


def sub_process_bar(j, total_step):
    str_ = '>' * (50 * j // total_step) + ' ' * (50 - 50 * j // total_step)
    sys.stdout.write('\r[' + str_ + '][%s%%]' % (round(100 * j / total_step, 2)))
    sys.stdout.flush()
    j += 1
    return j


def request_setting(url):
    resp = requests.get(url, headers={
        'User-agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like gecko) Chrome/63.0.3239.132 Safari/537.36'})
    resp.encoding = 'utf-8'
    return resp


##############################################
def crawling_eod_nasdaq():
    import string
    eod_url = 'https://eoddata.com/stocklist/NYSE/{}.htm'
    name_list = {}  # {company: symbol}
    for alphabet in string.ascii_uppercase:
        respo = requests.get(eod_url.format(alphabet))
        content = BeautifulSoup(respo.text, 'html.parser')
        table_a = content.find(class_='quotes').findAll('tr')
        for i in range(1, len(table_a)):
            name_list[table_a[i].findAll('td')[1].text] = table_a[i].findAll('td')[0].text
    print('store {} symbols'.format(len(name_list)))

    nasdaq_url = 'http://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt'
    resp = requests.get(nasdaq_url).text
    i = 96
    line = ''
    while i < len(resp):
        if resp[i] != '\n':
            line += resp[i]
        else:
            # print(line)
            company = line.split('|')[1].split('-')[0]
            if company not in name_list:
                name_list[company] = line.split('|')[0]
            line = ''
        i += 1
    np.save('data/NYSE_symbol.npy', name_list, allow_pickle=True)
    return name_list


def csv_to_npy(data_name):
    df = pd.read_csv(data_name)
    df['new_Name'] = df['Name'].apply(
        lambda x: x.replace(' Common Stock', '').replace(' Ordinary Shares', '').replace(' Class A', ''))
    new_dict = {df['new_Name'][j].replace(' Common Stock', ''): df['Symbol'][j] for j in range(len(df))}
    np.save('data/nasdaq_screener.npy', new_dict, allow_pickle=True)


######################################################
def page_level_search(url, investor):
    resp = request_setting(url)

    soup = BeautifulSoup(resp.text, 'html.parser')
    find_table = soup.find(class_='ed-container').find(id='ed-mid').find(id='aspnetForm').find('table',
                                                                                               id='tblMessagesAsp')
    tt = find_table.find_all('tr')
    res_ = []
    for line in tt:
        if line.findAll('td'):
            if len(line.findAll('td')) <= 1:
                continue
            if investor in line.findAll('td')[1].text:
                sub_url = []
                for c in line.find_all('a', href=True):
                    if c.text:
                        sub_url.append(c['href'])
                sub_url = sub_url[0]
                article_title = line.find_all('a', href=True)[0].text.replace('\n', '').replace('\t', '')
                res_.append((article_title, sub_url))
    return res_


def get_latest_page_main(url_head, first_page_tail, board_name):
    # Start from Board website
    board_url = url_head + first_page_tail
    resp = request_setting(board_url)
    soup = BeautifulSoup(resp.text, 'html.parser')
    board_list = soup.find(class_='ed-container').find(id='ed-mid').find('table', id='tblBoardsAsp')
    bt = board_list.find_all('tr')
    for b_line in bt:
        if b_line.findAll('td'):
            if board_name in b_line.findAll('td')[0].text:
                discuss_url = []
                for c in b_line.find_all('a', href=True):
                    if c.text:
                        discuss_url.append(c['href'])
                discuss_url = discuss_url[0]
                break
    return discuss_url


def get_prev_page_link(main_url):
    # main_url = '{}{}'.format(url_head, discuss_url.replace('/', ''))
    resp = request_setting(main_url)
    soup = BeautifulSoup(resp.text, 'html.parser')
    # find "prev" botton

    prev_button = soup.find(class_='ed-container').find(id='ed-mid').find(id='aspnetForm').find(
        class_='messagesControls').find(class_='prevNext')
    page_link = prev_button.find_all('a', href=True)
    if len(page_link) == 2:
        prev_link_sub = page_link[0]['href']
    elif len(page_link) == 1:
        if page_link[0].text == 'Next':
            # First page
            return -1
        else:
            prev_link_sub = page_link[0]['href']
    else:
        return None
    return prev_link_sub


def get_port_link(url_head, port_):
    # This depends on the rule of the website!
    return '{}{}{}{}'.format(url_head, port_[0].lower().replace(' ', '-'), '-',
                             port_[1].split('mid=')[1].split('&sort')[0] + '.aspx?sort=postdate')


def extract_post_date_from_post(message_main):
    message_main2 = message_main.find(class_='msgDate navGroup2')
    date_1 = message_main2.text.replace('\t', '').replace('\n', '')[5:].split('/')
    post_date = '{}/{}/{}'.format(int(date_1[0]), int(date_1[1]), date_1[2][:4])
    post_date = datetime.datetime.strptime(post_date, '%m/%d/%Y').strftime('%Y%m%d')
    return post_date


def extract_position_from_post(message_main, fortune_code, fortune_end='STOCK REVIEWS'):
    message_main1 = message_main.find(id='message')
    if message_main1 is None:
        message_main1 = message_main
    if fortune_code not in message_main1.text:
        position_start = message_main1.text
        i = 0
        while True:
            if (position_start[i:i + 2] == '\t\t') and (position_start[i + 2].isnumeric()):
                break
            i += 1
        monthly_portfolio = {}
        split_list = position_start.split('\n')
        for j in range(len(split_list)):
            target_split = position_start.split('\n')[j]
            if len(target_split.replace(' ', '')) == 0:
                continue
            else:
                if '\t\t' in target_split:
                    target_split = target_split.split('\t\t')
                elif '\t' in target_split:
                    target_split = target_split.split('\t')
                else:
                    continue
                monthly_portfolio[target_split[0].strip()] = target_split[1].strip()
        # check total percentage
        multi_x = 100 / sum([float(k.replace('%', '')) for k in monthly_portfolio.values()])
        for stock in monthly_portfolio:
            monthly_portfolio[stock] = round((float(monthly_portfolio[stock].replace('%', '')) * multi_x) / 100, 2)
        return monthly_portfolio


'''


    position_start = message_main1.text[message_main1.text.index(fortune_code):]
    i = 0
    while True:
        if position_start[i:i+2] == '\t\t':
            break
        i += 1
    while i:
        if position_start[i:i+2] == '. ':
            break
        i -= 1
    i +=2
    if fortune_end not in position_start:
        fortune_end = 'COMPANY REVIEWS'
        if fortune_end not in position_start:
            position_end = -1
        else:
            position_end = position_start.index(fortune_end)
    else:
        position_end = position_start.index(fortune_end)
    position_start = position_start[i:position_end]
    tmp1 = position_start.split('%')
    tmp1 = [t for t in tmp1 if len(t)]
    position_dict = {}
    for j in range(len(tmp1)):
        pos1 = tmp1[j].replace('\t',':')
        company_j = pos1.split(':')[0]
        pos_j = pos1.split(':')[-1]
        if len(company_j.replace(' ','')):
            if company_j == '\n':
                continue
            if company_j.startswith('.'):
                company_j = company_j[1:]
            position_dict[company_j] = float(pos_j)
    return position_dict
    #
    #
    # # tmp = message_main1.find_all('b', text='POSITION SIZES')
    # pre_list = message_main1.find_all('pre')
    # k = 1
    # while k <= len(pre_list):
    #     tmp = message_main1.find_all('pre')[-k].text
    #     if tmp.startswith('.'):
    #         break
    #     k += 1
    # position_start = tmp[1:]
    #
    # # 目前並沒有從fortune code開始找阿...
    #
    # # if '. . ' in position_start:
    # #     position_start = position_start[position_start.index('. . ') + 4:]
    # # else:
    # #     index_ = position_start.index('\t\t\t')
    # #     position_start = position_start[:index_].split('. ')[-1] + position_start [index_:]
    # position_dict = {}
    # position_text = re.split('%|[\t]*', position_start.replace(' ', ''))
    # i = 0
    # while i < len(position_text):
    #     if ',' in position_text[i]:
    #         break
    #     elif not len(position_text[i]):
    #         pass
    #     else:
    #         try:
    #             float(position_text[i])
    #             position_dict[position_text[i - 1]] = float(position_text[i]) / 100
    #         except:
    #             pass
    #     i += 1
    # return position_dict
'''


def extract_position_from_post_v2(message_main):
    split_message = message_main.split('\n')
    split_message = [s.replace('*', '') for s in split_message]
    split_message = [s for s in split_message if len(s) > 0]
    raw_dict = {}
    for s in split_message:
        if len(s.replace(' ', '').replace('.', '')) == 0:
            continue
        if '\t\t' in s:
            s = s.replace('\t', ' ')
        info = s.split('  ')
        raw_dict[info[0]] = float(info[-1].replace('%', '')) / 100
    return raw_dict


def extract_portfolio_ratio_v2(port_link, fortune_code='POSITION SIZES', date_find=True, position_find=True, ver='new'):
    assert ver == 'new'
    post_date, position_dict = None, None
    resp = request_setting(port_link)
    soup = BeautifulSoup(resp.text, 'html.parser')
    redirect_link = soup.find('a').text
    resp2 = request_setting(redirect_link)
    soup = BeautifulSoup(resp2.text, 'html.parser')
    position_size = soup.find(id='post_1').find_all('pre')[-1].text
    position_dict = extract_position_from_post_v2(message_main=position_size)
    # HERE 20230215
    return position_dict


def extract_portfolio_ratio(port_link, fortune_code='POSITION SIZES', date_find=True, position_find=True):
    """
    output:
    : position_dict: {ticker: ratio}
    : post_date: str, 'YYYYmmdd'
    """
    # Before (include) 2017, there's no "POSITION" section
    post_date, position_dict = None, None
    resp = request_setting(port_link)
    soup = BeautifulSoup(resp.text, 'html.parser')
    # if soup.find(id='fcDefault') is not None:
    if soup.find(id='post_1') is not None:
        # message_main = soup.find(id='fcDefault').find(class_='ed-container').find(id='ed-mid').find(id='pbcontainer').find(class_='messageLayout')
        message_main = soup.find(id='post_1').find_all(class_='lang-auto')[-1]

        if position_find:
            position_dict = extract_position_from_post(message_main, fortune_code)
            if position_dict:
                if sum(position_dict.values()) > 3:
                    position_dict = {k: round(v / total, 3) for total in (sum(position_dict.values()),) for k, v in
                                     position_dict.items()}
                if sum(position_dict.values()) < 0.95:
                    print('sum of ratio = ', sum(position_dict.values()))
        # if date_find:
        # post_date = extract_post_date_from_post(message_main)
    return position_dict


########################################
# Sort select article by date
def sort_by_title_date(res):
    for i in range(len(res)):
        if len(res[i]) < 3:
            port_link = get_port_link(url_head, res[i])
            post_date_, post_portfolio = extract_portfolio_ratio(port_link, date_find=True, position_find=False)
            res[i].append(post_date_)
    return sorted(res, key=lambda x: (x[2] is None, x[2]))


########################################
def get_portfolio_article_url_main(investor, url_head, first_page_tail='', article_keywords='', board_name='',
                                   ver='old'):
    cheatsheet = 'https://docs.google.com/document/d/1yF_lLGs3pI4SPcYOfIvpO5FYAbnYquYz_6aSnD0yKRQ/mobilebasic?pli=1'
    # 只到2023/02
    if ver == 'new':
        resp = request_setting(cheatsheet)
        # soup = BeautifulSoup(resp.text, 'html.parser')
        # board_list = soup.find(class_='ed-container').find(id='ed-mid').find('table', id='tblBoardsAsp')
        # bt = board_list.find_all('tr')

        # target_time = datetime.datetime.now()
        target_date = 20221001
        assert target_date < 20221031
        target_time = datetime.datetime.strptime(str(target_date), '%Y%m%d') - MonthEnd(1)
        assert target_time
        current_month_yr = target_time.strftime("%b") + ' ' + target_time.strftime("%Y")
        key_idx = resp.text.find(current_month_yr)
        assert key_idx > -1
        gasp_length = 700
        gasp_text = resp.text[:key_idx][-gasp_length:]
        flag, i = 1, 0
        while flag and (i < len(gasp_text)):
            if gasp_text[i: i + 8] == 'a href="':
                break
            i += 1
        post_url = gasp_text[i + 8: gasp_text[i + 8:].find('"')]
        # go to target post, then use previous sub-function
        pos_dict = extract_portfolio_ratio_v2(port_link=post_url, fortune_code='POSITION SIZES', date_find=True,
                                              position_find=True,
                                              ver=ver)

        resp = request_setting(post_url)
        resp = BeautifulSoup(resp.text, 'html.parser')


    else:
        discussion_page = url_head[:-1] + get_latest_page_main(url_head, first_page_tail, board_name)
    prev_exist = True
    load_path = 'tw_data/'
    if os.path.isfile('{}res-{}_strategy.npy'.format(load_path, investor)):
        res = np.load('{}res-{}_strategy.npy'.format(load_path, investor), allow_pickle=True).tolist()
    else:
        res = []
        max_s = '20000101'
    if res:
        res = sort_by_title_date(res)
        j = -1
        while res[j][2] is None:
            j -= 1
        max_s = res[j][2]

    count_page = 0
    while prev_exist or not count_page:
        # discussion page == latest page
        prev_link_sub = get_prev_page_link(discussion_page)
        if prev_link_sub == -1:
            print('\n Reach the first page')
            prev_exist = False
        else:
            prev_page = url_head[:-1] + prev_link_sub
            get_article = page_level_search(discussion_page, investor)
            if get_article:
                for cont in get_article:
                    if re.findall(article_keywords, cont[0]):
                        if not cont[0].startswith('Re'):
                            port_link = get_port_link(url_head, cont)
                            post_date_, post_portfolio = extract_portfolio_ratio(port_link, date_find=True,
                                                                                 position_find=False)
                            if list(cont) + [post_date_] not in res:
                                res.append(list(cont) + [post_date_])
                            if post_date_ <= max_s:
                                print('End of Searching: {}'.format(post_date_))
                                prev_exist = False
                                break
                            print(cont)
            discussion_page = prev_page
        count_page += 1
        print('Page Count: {}'.format(count_page))
    del_id, use_url = [], []
    for i in range(len(res)):
        if res[i][1] in use_url:
            del_id.append(i)
        else:
            use_url.append(res[i][1])
    res = [res[d] for d in range(len(res)) if d not in del_id]
    np.save('{}res-{}_strategy.npy'.format(load_path, investor), res, allow_pickle=True)
    return res


#################################################
def extract_portfolio_info_main(res=None, url_head=''):
    """
    {Date: {'title': port_[0], 'link': port_link, 'portfolio': post_portfolio})
    """
    #######################################
    # Obtain Table of NASDAQ ticker symbol and company name
    try:
        symbol_dict2 = np.load('data/NYSE_symbol.npy', allow_pickle=True).item()
    except:
        symbol_dict2 = crawling_eod_nasdaq()
    try:
        symbol_dict = np.load('data/nasdaq_screener.npy', allow_pickle=True).item()
    except:
        symbol_dict = csv_to_npy('data/nasdaq_screener.csv')
    symbol_dict.update(symbol_dict2)
    del symbol_dict2
    gc.collect()
    #######################################

    if res is None:
        res = np.load('tw_data/res-{}_strategy.npy'.format(investor), allow_pickle=True).tolist()
    try:
        portfolio_record = np.load('tw_data/historical_portfolio_{}.npy'.format(investor), allow_pickle=True)
    except:
        portfolio_record = {}
    # j, total_step = 0, len(res)
    del_list = []
    for port_ in res:
        # see the true post date
        # [i for i in range(len(res)) if res[i][2] == '20181231']
        print('Record for:', port_[2])
        port_link = get_port_link(url_head, port_)  # ok
        post_date_ = port_[2]
        if (post_date_ in portfolio_record) and sum(portfolio_record[post_date_]) > 0.99:
            print('Record for {} exists'.format(port_[2]))
            continue
        try:
            post_portfolio = extract_portfolio_ratio(port_link)
        except:
            if post_date_ not in portfolio_record:
                print('\nManually input...')
                print(port_link)
                break
        np.save('tw_data/historical_portfolio_{}.npy'.format(investor), portfolio_record, allow_pickle=True)

        if not post_portfolio:
            del_list.append(port_)
            continue

        post_portfolio = {ok.strip(): post_portfolio[ok] for ok in post_portfolio}
        ori_key = list(post_portfolio.keys()).copy()
        ##heere 12/27/2023 --> symbol_dict 缺公司, ex: Mulesoft, Talend, Hubspot
        '''
        new_key = stock symbol
        '''
        for k in ori_key:
            flag = 0
            if k == 'Square':
                new_key = 'SQ'
            elif k == 'Sentinel':
                new_key = 'S'
            elif k == 'Crowdstrike':
                new_key = 'CRWD'
            elif k == 'Mongo':
                new_key = 'MDB'
            elif k == 'Mulesoft':
                new_key = 'MULE'
            elif k.startswith('Guardant is  gone'):
                new_key = k.split('.')[1]
            elif k.startswith('Square’s percentage dropped'):
                new_key = 'Twilio'  # ---> need change
            elif k.startswith('Here are my positions'):
                new_key = k.split('.')[-1]
            elif k == 'Smartsheets':  # ---> need change
                new_key = 'smartsheet'
            # elif k == 'Afterpay':
            #     new_key = 'APT'
            elif k.startswith('No huge change'):
                new_key = k.split('.')[1]
            else:
                # here, 12/31/2023, 改成用startswith/in
                new_key = [nk for nk in symbol_dict if k.lower() in nk.lower()]
                if not new_key:
                    if len(k.split(' ')) > 3:
                        tmp_k = k.split('.')[-1]
                        new_key = [nk for nk in symbol_dict if tmp_k.lower() in nk.lower()]
                    else:
                        k_tmp = ' '.join(re.findall('[A-Z][^A-Z]*', k))
                        new_key = [nk for nk in symbol_dict if k_tmp in nk]
                    if not new_key:
                        k_tmp = k.lower()
                        new_key = [nk for nk in symbol_dict if k_tmp in nk]
                        if not new_key:
                            if (len(k) <= 6) and (k.isupper()):
                                if k in symbol_dict.values():
                                    new_key = k
                                    flag = 1
                                else:
                                    print('cannot find {} in dict'.format(k))
                            else:
                                print('cannot find {} in dict'.format(k))
                else:
                    new_key = symbol_dict[new_key[0]]
                if not flag:
                    if len(new_key) >= 1:
                        new_key = symbol_dict[new_key[0]]

                    else:
                        print('cannot find {}'.format(k))
                        break

            post_portfolio[new_key] = post_portfolio.pop(k)
        if post_portfolio:
            total_v = sum([i for i in post_portfolio.values()])
            if total_v > 1.01:
                adj_post_portfolio = {t: post_portfolio[t] / total_v for t in post_portfolio}
            else:
                adj_post_portfolio = post_portfolio
            portfolio_record[post_date_] = {'title': port_[0], 'link': port_link, 'portfolio': adj_post_portfolio}
            # before 20181231, no "POSITION SIZE" --> not the priority
            # mapping full name --> symbol
            # https: // en.wikipedia.org / wiki / List_of_S % 26P_500_companies
            '''
            20220221 22:30 note:
            少數還是有bbb的情形，但大都快ok了
            接下來可以先進historical price的部分
            '''
            '''
            Record for: 20200228
            cannot find Afterpay in dict

            Record for: 20200530
            cannot find Livingo in dict
            
            Record for: 20200927
            ValueError: could not convert string to float: 'As I wrote above, I’ve trimmed Zoom back to 30'
            '''


        else:
            print('No message found:', port_[0])
        # j = sub_process_bar(j, total_step)
    np.save('tw_data/historical_portfolio_{}.npy'.format(investor), portfolio_record, allow_pickle=True)
    return portfolio_record


##########################################
def trade_simulate(portfolio_record=None, investor='SaulR80683'):
    if not portfolio_record:
        portfolio_record = np.load('tw_data/historical_portfolio_{}.npy'.format(investor), allow_pickle=True).item()
        #should change to self.portfolio_record
    '''
    Trade date = 1 day after the Post
     '''
    amount = 1000
    post_date_list = sorted(list(portfolio_record.keys()))
    for i, rev_ in enumerate(post_date_list):
        # break
    #    first, trade the last stock
        if i > 0:
            if post_date_list[i - 1]...
        else:
            pass
        trade_date = (datetime.datetime.strptime(str(rev_), '%Y%M%d') + BDay(1)).replace(minute=0, second=0)
        data = yf.download(list(portfolio_record[rev_].keys()), trade_date, trade_date + BDay(1))['Close']
        trade_table = {}
        for ticker in portfolio_record[rev_]:
            trade_table[ticker] = {'Q': round(amount * portfolio_record[rev_][ticker]/data.loc[trade_date, ticker],2),
                                                'V' : amount * portfolio_record[rev_][ticker],
                                                'T' : amount}






##########################################
def main(investor, url_head, first_page_tail='', article_keywords='', board_name='', ver='old'):
    resu = get_portfolio_article_url_main(investor, url_head, first_page_tail, article_keywords, board_name, ver)
    portfolio_record_ = extract_portfolio_info_main(resu, url_head)

