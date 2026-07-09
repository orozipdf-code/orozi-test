#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collect_issues.py  (SerpApi 버전)
---------------------------------
윌북 계열(윌북 / 윌북주니어 / 윌북아트) 도서에 대해 구글 '최근 1일' 웹 검색
결과(블로그·인스타·Threads·브런치·뉴스 등 전체 탭)를 SerpApi로 수집하여
issues.json 으로 저장합니다.

- API 키는 코드에 넣지 않습니다. 환경변수 SERPAPI_KEY 에서 읽습니다.
  (GitHub Actions에서는 Secrets에 SERPAPI_KEY 를 등록해두면 자동 주입)
- 입력: kyobo_bestseller.csv / aladin_bestseller.csv / yes24_bestseller.csv
        (한글 헤더: 순위, 제목, 저자, 출판사 …)  출판사가 윌북 계열인 행만.
- 출력: issues.json
        { generated_at, book_count, books:[{title, author, publisher, items:[...]}] }

검색 1회 = 책 1권. 윌북 책이 보통 2~3권이라 하루 1번 실행 시 월 60~90회로
SerpApi 무료 한도(월 100회) 안에서 동작합니다.
"""

import csv
import json
import os
import re
import sys
import time
import datetime
import urllib.parse
import urllib.request

# ---------------------------------------------------------------- 설정
CSV_FILES = ["kyobo_bestseller.csv", "aladin_bestseller.csv", "yes24_bestseller.csv"]

# 긴 이름부터: '윌북주니어'가 '윌북'으로 잘못 안 잡히게
OUR_PUBLISHERS = ["윌북주니어", "윌북아트", "윌북"]

MAX_ITEMS_PER_BOOK = 8       # 책당 화면에 보여줄 최대 결과 수
REQUEST_DELAY_SEC = 1.5      # SerpApi 요청 간 간격
OUTPUT = "issues.json"
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"

# 검색 기간: 먼저 1일(qdr:d)로 찾고, 결과가 없으면 1주(qdr:w)로 자동 확장.
# 확장 검색도 SerpApi 검색 1회를 더 쓰므로, 무료 한도가 빠듯하면
# TIME_FALLBACK 를 False 로 두거나 PRIMARY_RANGE 를 "qdr:w"로 바꾸세요.
PRIMARY_RANGE = "qdr:d"      # 1차 검색 기간 (qdr:d=1일, qdr:w=1주, qdr:m=1달)
FALLBACK_RANGE = "qdr:w"     # 0건일 때 넓혀서 재검색할 기간
TIME_FALLBACK = True         # 0건이면 FALLBACK_RANGE로 한 번 더 검색할지

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
    for name in OUR_PUBLISHERS:
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


def serpapi_search(query, api_key, time_range="qdr:d"):
    """구글 웹 검색 · 지정 기간 · 한국어. organic_results 리스트를 반환."""
    params = {
        "engine": "google",
        "q": query,
        "tbs": time_range,    # qdr:d=1일, qdr:w=1주, qdr:m=1달
        "hl": "ko",
        "gl": "kr",
        "num": "10",
        "api_key": api_key,
    }
    url = SERPAPI_ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "orozi-issue-collector/2.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("search_metadata", {}).get("status") == "Error":
        raise RuntimeError(data.get("error", "SerpApi error"))
    return data.get("organic_results", []) or []


def to_items(organic, limit):
    items = []
    for r in organic:
        title = (r.get("title") or "").strip()
        link = (r.get("link") or "").strip()
        if not title or not link:
            continue
        source = (r.get("source") or "").strip()
        if not source:
            dl = r.get("displayed_link") or ""
            source = dl.split("›")[0].strip() if dl else ""
        snippet = (r.get("snippet") or "").strip()
        # SerpApi가 주는 날짜(예: "3시간 전", "2026. 7. 9.")가 있으면 사용
        date = (r.get("date") or "").strip()
        items.append({
            "title": title,
            "link": link,
            "source": source,
            "published": date,     # 상대/절대 문자열 그대로 (프론트에서 표시)
            "snippet": snippet[:180],
        })
        if len(items) >= limit:
            break
    return items


def main():
    api_key = os.environ.get("SERPAPI_KEY", "").strip()
    if not api_key:
        print("[error] 환경변수 SERPAPI_KEY 가 없습니다. "
              "GitHub Secrets에 SERPAPI_KEY 를 등록하세요.")
        sys.exit(1)

    all_books = []
    for path in CSV_FILES:
        all_books.extend(read_will_books(path))
    books = merge(all_books)
    print(f"[info] 윌북 계열 도서 {len(books)}권 (검색 {len(books)}회 예정)")

    results = []
    used = 0
    for i, b in enumerate(books, 1):
        # 검색어: 제목만 큰따옴표로 묶어 정확 매칭 (저자는 넣지 않음).
        # 저자를 넣으면 검색이 과하게 좁아져 0건이 잦음. 제목 문구 고정이
        # 노이즈는 줄이면서 블로그·인스타·브런치 등을 폭넓게 잡습니다.
        title = b["title"].strip()
        query = f'"{title}"'

        items = []
        # 1차: PRIMARY_RANGE(기본 1일)
        print(f"  ({i}/{len(books)}) 검색[{PRIMARY_RANGE}]: {query}")
        try:
            organic = serpapi_search(query, api_key, PRIMARY_RANGE)
            items = to_items(organic, MAX_ITEMS_PER_BOOK)
            used += 1
        except Exception as e:
            print(f"    [warn] 검색 실패: {e}")
        time.sleep(REQUEST_DELAY_SEC)

        # 2차: 0건이면 FALLBACK_RANGE(기본 1주)로 넓혀서 재검색
        used_range = PRIMARY_RANGE
        if TIME_FALLBACK and not items:
            print(f"       └ 0건 → 재검색[{FALLBACK_RANGE}]")
            try:
                organic = serpapi_search(query, api_key, FALLBACK_RANGE)
                items = to_items(organic, MAX_ITEMS_PER_BOOK)
                used += 1
                used_range = FALLBACK_RANGE
            except Exception as e:
                print(f"    [warn] 재검색 실패: {e}")
            time.sleep(REQUEST_DELAY_SEC)

        b["items"] = items
        b["item_count"] = len(items)
        b["time_range"] = used_range if items else PRIMARY_RANGE
        results.append(b)
        time.sleep(REQUEST_DELAY_SEC)

    payload = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "publisher_filter": "윌북 계열",
        "source": "google (serpapi, qdr:d)",
        "book_count": len(results),
        "searches_used": used,
        "books": results,
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[done] {OUTPUT} · {len(results)}권 · 검색 {used}회 사용 · "
          f"총 {sum(r['item_count'] for r in results)}건")


if __name__ == "__main__":
    main()
