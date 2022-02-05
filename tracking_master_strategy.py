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


def extract_portfolio_ratio(port_link):
    """
    output:
    : position_dict: {ticker: ratio}
    : post_date: str, 'YYYYmmdd'
    """
    resp = request_setting(port_link)
    soup = BeautifulSoup(resp.text, 'html.parser')
    message_main = soup.find(id='fcDefault').find(class_='ed-container').find(id='ed-mid').find(id='pbcontainer').find(class_='messageLayout')
    message_main1 = message_main.find(id='message')
    position_start = message_main1.text[message_main1.text.index('POSITION SIZE'):]
    position_start = position_start[position_start.index('. . ') + 4:]
    position_dict = {}
    position_text = re.split('%|[\t]*', position_start)
    i = 0
    while i < len(position_text):
        if re.findall('\s|,', position_text[i]):
            try:
                float(position_text[i])
            except:
                break
        elif not len(position_text[i]):
            pass
        else:
            try:
                float(position_text[i])
            except:
                position_dict[position_text[i]] = float(position_text[i + 1]) / 100
        i += 1
    message_main2 = message_main.find(class_='msgDate navGroup2')
    date_1 = message_main2.text.replace('\t', '').replace('\n', '')[5:].split('/')
    post_date = '{}/{}/{}'.format(int(date_1[0]), int(date_1[1]), date_1[2][:4])
    post_date = datetime.datetime.strptime(post_date, '%m/%d/%Y').strftime('%Y%m%d')
    return post_date, position_dict


########################################
def get_portfolio_article_url_main(investor, url_head, first_page_tail='', article_keywords='', board_name=''):
    discussion_page = url_head[:-1] + get_latest_page_main(url_head, first_page_tail, board_name)
    prev_exist = True
    res = []
    while prev_exist:
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
                            res.append(cont)
                            print(cont)
            discussion_page = prev_page
    return res


def extract_portfolio_info_main(res, url_head):
    portfolio_record = {}
    # {Date:{ticker: ratio}}
    for port_ in res:
        print('Record for: ', port_[0].split('end of ')[1])
        # see the true post date
        port_link = get_port_link(url_head, port_)
        post_date_, post_portfolio = extract_portfolio_ratio(port_link)
        if post_portfolio:
            portfolio_record[post_date_] = post_portfolio
    return portfolio_record


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
