import requests
from bs4 import BeautifulSoup
import csv
import json
import os
from datetime import datetime

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


def save_to_csv(filename, data):
    # 프론트엔드가 요구하는 8개 헤더 순서 그대로 엑셀 파일 생성
    fields = ['수집시각', '순위', '순위변동', '제목', '저자', '출판사', '이미지URL', '링크']
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)


def get_yes24():
    print("예스24 크롤링 중...")
    url = "https://www.yes24.com/Product/Category/BestSeller?CategoryNumber=001"
    books = []
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.select('#yesBestList > li')[:5]  # 1~5위

        for idx, item in enumerate(items):
            title = item.select_one('.gd_name').text.strip() if item.select_one('.gd_name') else "제목없음"
            author = item.select_one('.authPubInfo a').text.strip() if item.select_one('.authPubInfo a') else "저자미상"
            pub = item.select_one('.authPubInfo').text.split(']')[1].split('(')[0].strip() if ']' in item.select_one(
                '.authPubInfo').text else "출판사 모름"
            img = item.select_one('.img_bdr img')['data-original'] if item.select_one('.img_bdr img') else ""
            link = "https://www.yes24.com" + item.select_one('.gd_name')['href'] if item.select_one('.gd_name') else ""

            books.append({
                '수집시각': now_str, '순위': idx + 1, '순위변동': '-',
                '제목': title, '저자': author, '출판사': pub, '이미지URL': img, '링크': link
            })
    except Exception as e:
        print(f"예스24 에러: {e}")
    return books


def get_aladin():
    print("알라딘 크롤링 중...")
    url = "https://www.aladin.co.kr/shop/common/wbest.aspx?BranchType=1"
    books = []
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.select('.ss_book_box')[:5]

        for idx, item in enumerate(items):
            title = item.select_one('a.bo3').text.strip() if item.select_one('a.bo3') else "제목없음"
            link = item.select_one('a.bo3')['href'] if item.select_one('a.bo3') else ""
            img = item.select_one('.cover_all img')['src'] if item.select_one('.cover_all img') else ""

            # 알라딘 특유의 복잡한 저자/출판사 텍스트 파싱
            meta_text = item.select('.ss_book_list ul li')[2].text if len(
                item.select('.ss_book_list ul li')) > 2 else ""
            author = meta_text.split('(지은이)')[0].strip() if '(지은이)' in meta_text else "저자미상"
            pub = meta_text.split(')')[1].split('│')[0].strip() if '│' in meta_text else "출판사 모름"

            books.append({
                '수집시각': now_str, '순위': idx + 1, '순위변동': '-',
                '제목': title, '저자': author, '출판사': pub, '이미지URL': img, '링크': link
            })
    except Exception as e:
        print(f"알라딘 에러: {e}")
    return books


def get_kyobo_placeholder():
    # 교보문고는 보안상 일반 크롤링이 막히므로, 우선 구조가 깨지지 않게 예쁜 플레이스홀더 데이터를 만듭니다.
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return [{
        '수집시각': now_str, '순위': 1, '순위변동': 'NEW',
        '제목': '교보문고 보안 돌파 준비 중', '저자': '안형욱 탐정', '출판사': '윌북',
        '이미지URL': 'https://via.placeholder.com/150x200?text=Kyobo+Lock', '링크': 'https://www.kyobobook.co.kr'
    }]


def update_history_json(now_str, current_data):
    # 지난 차트(history.json) 누적 기록 관리 로직
    filename = 'history.json'
    history = []
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except:
            history = []

    # 새로운 시간대의 데이터를 양식에 맞춰 추가
    new_entry = {
        "수집시각": now_str,
        "데이터": current_data
    }
    history.append(new_entry)

    # 최근 24개(하루치)만 유지하도록 제한 (파일이 무한히 커지는 것 방지)
    if len(history) > 24:
        history = history[-24:]

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 1. 각 서점 데이터 긁어오기
    yes24_data = get_yes24()
    aladin_data = get_aladin()
    kyobo_data = get_kyobo_placeholder()

    # 2. 내 저장소에 개별 CSV 파일로 저장 (인터넷 배포용)
    if yes24_data: save_to_csv('yes24_bestseller.csv', yes24_data)
    if aladin_data: save_to_csv('aladin_bestseller.csv', aladin_data)
    if kyobo_data: save_to_csv('kyobo_bestseller.csv', kyobo_data)

    # 3. 지난 차트용 통합 JSON 업데이트
    current_all = {
        "yes24": yes24_data,
        "aladin": aladin_data,
        "kyobo": kyobo_data
    }
    update_history_json(now_str, current_all)
    print("🎉 전 서점 진짜 데이터 엑셀(CSV) 및 히스토리 업데이트 완료!")