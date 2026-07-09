#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collect_issues.py
-----------------
윌북 계열(윌북 / 윌북주니어 / 윌북아트) 도서에 대해 '최근 1일' 구글 뉴스
검색 결과를 수집하여 issues.json 으로 저장합니다. API 키 불필요.

- 입력: kyobo_bestseller.csv / aladin_bestseller.csv / yes24_bestseller.csv
        (컬럼: 순위, 제목, 저자, 출판사, ... 한글 헤더)
        '출판사' 값에 윌북 계열이 포함된 행만 대상.
- 출력: issues.json  { generated_at, book_count, books:[{title, author, publisher, items:[...]}] }
"""

import csv
import json
import re
import time
import html
import datetime
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------- 설정
CSV_FILES = ["kyobo_bestseller.csv", "aladin_bestseller.csv", "yes24_bestseller.csv"]

# 긴 이름부터: '윌북주니어'가 '윌북'으로 잘못 안 잡히게
OUR_PUBLISHERS = ["윌북주니어", "윌북아트", "윌북"]

MAX_ITEMS_PER_BOOK = 8
REQUEST_DELAY_SEC = 1.0
OUTPUT = "issues.json"

COL = {
    "title":     ["제목", "title", "책명", "도서명", "상품명"],
    "author":    ["저자", "author", "지은이"],
    "publisher": ["출판사", "publisher", "펴낸곳"],
}


def pick(headers, keys):
    low = [h.strip().lower().lstrip("\ufeff") for h in headers]
    for k in keys:
        if k.lower() in low:
            return low.index(k.lower())
    return -1


def is_ours(publisher):
    p = publisher or ""
    return any(name in p for name in OUR_PUBLISHERS)


def which_brand(publisher):
    for name in OUR_PUBLISHERS:      # 긴 것부터
        if name in (publisher or ""):
            return name
    return ""


def read_will_books(path):
    out = []
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
    except FileNotFoundError:
        print(f"[skip] {path} 없음")
        return out
    if not rows:
        return out
    hs = rows[0]
    ti, ai, pi = pick(hs, COL["title"]), pick(hs, COL["author"]), pick(hs, COL["publisher"])
    if ti == -1:
        print(f"[warn] {path}: 제목 컬럼을 못 찾음 (헤더: {hs})")
        return out
    for r in rows[1:]:
        def cell(i):
            return r[i].strip() if 0 <= i < len(r) else ""
        title, publisher = cell(ti), cell(pi)
        if title and is_ours(publisher):
            out.append({
                "title": title,
                "author": cell(ai),
                "publisher": publisher,
                "brand": which_brand(publisher),
            })
    return out


def merge(books):
    m = {}
    for b in books:
        key = re.sub(r"\s+", "", b["title"]).lower()
        if key not in m:
            m[key] = {"title": b["title"], "author": b["author"],
                      "publisher": b["publisher"], "brand": b["brand"]}
        elif not m[key]["author"] and b["author"]:
            m[key]["author"] = b["author"]
    return list(m.values())


def google_news_rss(query):
    q = urllib.parse.quote(f"{query} when:1d")
    url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; orozi-issue-collector/1.0)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def parse_rss(xml_bytes, limit):
    items = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return items
    for item in root.iter("item"):
        def text(tag):
            el = item.find(tag)
            return el.text if el is not None and el.text else ""
        title = html.unescape(text("title"))
        link = text("link")
        pub = text("pubDate")
        src_el = item.find("source")
        source = src_el.text if src_el is not None and src_el.text else ""
        desc = html.unescape(strip_tags(text("description")))
        if not source and " - " in title:
            source = title.rsplit(" - ", 1)[-1].strip()
        items.append({
            "title": title, "link": link, "source": source,
            "published": pub, "snippet": desc[:180],
        })
        if len(items) >= limit:
            break
    return items


def main():
    all_books = []
    for path in CSV_FILES:
        all_books.extend(read_will_books(path))
    books = merge(all_books)
    print(f"[info] 윌북 계열 도서 {len(books)}권")

    results = []
    for i, b in enumerate(books, 1):
        query = b["title"]
        if b["author"]:
            query = f'{b["title"]} {b["author"].split(",")[0].strip()}'
        print(f"  ({i}/{len(books)}) 검색: {query}")
        items = []
        try:
            items = parse_rss(google_news_rss(query), MAX_ITEMS_PER_BOOK)
        except Exception as e:
            print(f"    [warn] 실패: {e}")
        b["items"] = items
        b["item_count"] = len(items)
        results.append(b)
        time.sleep(REQUEST_DELAY_SEC)

    payload = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "publisher_filter": "윌북 계열",
        "book_count": len(results),
        "books": results,
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[done] {OUTPUT} · {len(results)}권 · "
          f"총 {sum(r['item_count'] for r in results)}건")


if __name__ == "__main__":
    main()
