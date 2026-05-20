import requests
from bs4 import BeautifulSoup
import csv
import json
import os
from datetime import datetime

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}


def save_to_csv(filename, data):
    fields = ['수집시각', '순위', '순위변동', '제목', '저자', '출판사', '이미지URL', '링크']
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)


def get_yes24():
    url = "https://www.yes24.com/Product/Category/BestSeller?CategoryNumber=001"
    books = []
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.select('#yesBestList > li')[:10]
        for idx, item in enumerate(items):
            title = item.select_one('.gd_name').text.strip() if item.select_one('.gd_name') else "제목없음"
            author = item.select_one('.authPubInfo a').text.strip() if item.select_one('.authPubInfo a') else "저자미상"
            pub = item.select_one('.authPubInfo').text.split(']')[1].split('(')[0].strip() if ']' in item.select_one(
                '.authPubInfo').text else "출판사"
            img = item.select_one('.img_bdr img')['data-original'] if item.select_one('.img_bdr img') else ""
            link = "https://www.yes24.com" + item.select_one('.gd_name')['href'] if item.select_one('.gd_name') else ""
            books.append(
                {'수집시각': now_str, '순위': idx + 1, '순위변동': '-', '제목': title, '저자': author, '출판사': pub, '이미지URL': img,
                 '링크': link})
    except:
        pass
    return books


def get_aladin():
    url = "https://www.aladin.co.kr/shop/common/wbest.aspx?BranchType=1"
    books = []
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.select('.ss_book_box')[:10]
        for idx, item in enumerate(items):
            title = item.select_one('a.bo3').text.strip() if item.select_one('a.bo3') else "제목없음"
            link = item.select_one('a.bo3')['href'] if item.select_one('a.bo3') else ""
            img = item.select_one('.cover_all img')['src'] if item.select_one('.cover_all img') else ""
            meta = item.select('.ss_book_list ul li')[2].text if len(item.select('.ss_book_list ul li')) > 2 else ""
            author = meta.split('(지은이)')[0].strip() if '(지은이)' in meta else "저자미상"
            pub = meta.split(')')[1].split('│')[0].strip() if '│' in meta else "출판사"
            books.append(
                {'수집시각': now_str, '순위': idx + 1, '순위변동': '-', '제목': title, '저자': author, '출판사': pub, '이미지URL': img,
                 '링크': link})
    except:
        pass
    return books


def update_history_json(now_str, current_data):
    filename = 'history.json'
    history = []
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except:
            pass
    history.append({"수집시각": now_str, "데이터": current_data})
    if len(history) > 24: history = history[-24:]
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    y_data = get_yes24()
    a_data = get_aladin()
    # 교보문고는 우선 예쁜 가짜 데이터를 넣어 구조를 유지합니다.
    k_data = [{'수집시각': now_str, '순위': 1, '순위변동': 'NEW', '제목': '안형욱 탐정의 교보 돌파 시도', '저자': '안형욱', '출판사': '윌북',
               '이미지URL': 'https://via.placeholder.com/150x200', '링크': ''}]

    save_to_csv('yes24_bestseller.csv', y_data)
    save_to_csv('aladin_bestseller.csv', a_data)
    save_to_csv('kyobo_bestseller.csv', k_data)
    update_history_json(now_str, {"yes24": y_data, "aladin": a_data, "kyobo": k_data})
    print("데이터 생성 완료!")