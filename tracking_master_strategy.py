'''
1. Trace a master investor's strategy pn internet
2. backtest for his/her strategy (in progress)
'''
import requests
import sys 
import re
import datetime
from bs4 import BeautifulSoup


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
    bt=board_list.find_all('tr')
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
    return '{}{}{}{}'.format(url_head, port_[0].lower().replace(' ', '-'), '-', port_[1].split('mid=')[1].split('&sort')[0] + '.aspx?sort=postdate')


def extract_post_date_from_post(message_main):
    message_main2 = message_main.find(class_='msgDate navGroup2')
    date_1 = message_main2.text.replace('\t', '').replace('\n', '')[5:].split('/')
    post_date = '{}/{}/{}'.format(int(date_1[0]), int(date_1[1]), date_1[2][:4])
    post_date = datetime.datetime.strptime(post_date, '%m/%d/%Y').strftime('%Y%m%d')
    return post_date

def extract_position_from_post(message_main, fortune_code):
    message_main1 = message_main.find(id='message')
    if fortune_code not in message_main1.text:
        return None
    # position_start = message_main1.text[message_main1.text.index(fortune_code):]
    # tmp = message_main1.find_all('b', text='POSITION SIZES')
    pre_list = message_main1.find_all('pre')
    k = 1
    while k <= len(pre_list):
        tmp = message_main1.find_all('pre')[-k].text
        if tmp.startswith('.'):
            break
        k += 1
    position_start = tmp[1:]
    # if '. . ' in position_start:
    #     position_start = position_start[position_start.index('. . ') + 4:]
    # else:
    #     index_ = position_start.index('\t\t\t')
    #     position_start = position_start[:index_].split('. ')[-1] + position_start [index_:]
    position_dict = {}
    position_text = re.split('%|[\t]*', position_start.replace(' ', ''))
    i = 0
    while i < len(position_text):
        if ',' in position_text[i]:
            break
        elif not len(position_text[i]):
            pass
        else:
            try:
                float(position_text[i])
                position_dict[position_text[i - 1]] = float(position_text[i]) / 100
            except:
                pass
        i += 1
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
    if soup.find(id='fcDefault') is not None:
        message_main = soup.find(id='fcDefault').find(class_='ed-container').find(id='ed-mid').find(id='pbcontainer').find(class_='messageLayout')
        if position_find:
            position_dict = extract_position_from_post(message_main, fortune_code)
            if position_dict:
                if sum(position_dict.values()) < 0.95:
                    print('sum of ratio = ', sum(position_dict.values()))
        if date_find:
            post_date = extract_post_date_from_post(message_main)
    return post_date, position_dict


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
def get_portfolio_article_url_main(investor, url_head, first_page_tail='', article_keywords='', board_name=''):
    discussion_page = url_head[:-1] + get_latest_page_main(url_head, first_page_tail, board_name)
    prev_exist = True
    load_path = 'tw_data/'
    if os.path.isfile('{}res-{}_strategy.npy'.format(load_path, investor)):
        res = np.load('{}res-{}_strategy.npy'.format(load_path, investor), allow_pickle=True).tolist()
    else:
        res = []
        max_s ='20000101'
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
                            elif post_date_ <= max_s:
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


def extract_portfolio_info_main(res=None, url_head=''):
    """
    {Date: {'title': port_[0], 'link': port_link, 'portfolio': post_portfolio})
    """
    #######################################
    # Obtain Table of NYSE ticker symbol and company name
    try:
        symbol_dict = np.load('data/NYSE_symbol.npy', allow_pickle=True).item()
    except:
        symbol_dict = crawling_eod_nasdaq()
    #######################################

    if res is None:
        res = np.load('tw_data/res-{}_strategy.npy'.format(investor), allow_pickle=True).tolist()
    portfolio_record = {}
    # j, total_step = 0, len(res)
    for port_ in res:
        print('Record for: ', port_[0].split('of ')[1])
        # see the true post date
        port_link = get_port_link(url_head, port_)
        post_date_, post_portfolio = extract_portfolio_ratio(port_link)
        ori_key = list(post_portfolio.keys()).copy()
        for k in ori_key:
            flag = 0
            if k == 'Square':
                new_key = 'SQ'
            elif k == 'Sentinel':
                new_key = 'S'
            elif k == 'Crowdstrike':
                new_key = 'CRWD'
            else:
                new_key = [nk for nk in symbol_dict if k in nk]
                if not new_key:
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
                if not flag:
                    if len(new_key) > 1:
                        print('bbb: {}'.format(k))
                        break
                    elif len(new_key) == 1:
                        new_key = symbol_dict[new_key[0]]
                    else:
                        print('cannot find {}'.format(k))
                        break
            post_portfolio[new_key] = post_portfolio.pop(k)
        if post_portfolio:
            total_v = sum([i for i in post_portfolio.values()])
            if total_v > 1:
                adj_post_portfolio = {t: post_portfolio[t] / total_v for t in post_portfolio}
            else:
                adj_post_portfolio = post_portfolio
                adj_post_portfolio['cash'] = 1 - total_v
            portfolio_record[post_date_] = {'title': port_[0], 'link': port_link, 'portfolio': adj_post_portfolio}
            # before 20181231, no "POSITION SIZE" --> not the priority
            # mapping full name --> symbol
            # https: // en.wikipedia.org / wiki / List_of_S % 26P_500_companies
            '''
            20220221 22:30 note:
            少數還是有bbb的情形，但大都快ok了
            接下來可以先進historical price的部分
            '''

        else:
            print('No message found:', port_[0])
        # j = sub_process_bar(j, total_step)
    return portfolio_record


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


########################################
def main(investor, url_head, first_page_tail='', article_keywords='', board_name=''):
    resu = get_portfolio_article_url_main(investor, url_head, first_page_tail, article_keywords, board_name)
    portfolio_record_ = extract_portfolio_info_main(resu, url_head)
    ######################
    # Backtest part in progress
    return portfolio_record_


########################################
########################################
if __name__ == '__main__':
    print('Enter Investor to follow:')
    investor = input()
    print('Enter Forum url:')
    url_head = input()
    print('Key Words (Regex style) for Article\'s Title:')
    article_keywords = input()
    tracking_record = main(investor, url_head, article_keywords, board_name)
