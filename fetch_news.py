"""
삼성창원병원 경영 뉴스 수집기
  - 네이버 뉴스 검색 API로 6개 언론사 기사 수집
  - 결과를 news.json으로 저장 (hospital_news.html이 읽음)

사전 준비:
  1. https://developers.naver.com 에서 애플리케이션 등록
  2. '검색' API 사용 신청 후 CLIENT_ID / CLIENT_SECRET 발급
  3. 아래 두 줄에 발급받은 값 입력
"""

import urllib.request
import urllib.parse
import json
import re
import os
import sys
from datetime import datetime
from collections import Counter

# ── ① API 키 설정 ────────────────────────────────────────────────────────────
# 로컬 실행: run_local.bat 또는 환경변수로 설정
# GitHub Actions: 저장소 Secrets에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 등록
CLIENT_ID     = os.environ.get("NAVER_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")

# ── ② 수집 대상 언론사 ────────────────────────────────────────────────────────
SOURCES = [
    {"name": "데일리메디",   "domain": "dailymedi.com",     "home": "https://www.dailymedi.com"},
    {"name": "메디칼타임즈", "domain": "medicaltimes.com",  "home": "https://www.medicaltimes.com"},
    {"name": "청년의사",     "domain": "docdocdoc.co.kr",   "home": "https://www.docdocdoc.co.kr"},
    {"name": "의협신문",     "domain": "doctorsnews.co.kr", "home": "https://www.doctorsnews.co.kr"},
    {"name": "연합뉴스",     "domain": "yna.co.kr",         "home": "https://www.yna.co.kr/health/index"},
    {"name": "메디파나뉴스", "domain": "medipana.com",       "home": "https://medipana.com"},
]

# ── ③ 검색 키워드 목록 ────────────────────────────────────────────────────────
QUERIES = [
    "의료정책 수가",
    "건강보험 병원",
    "전공의 의사",
    "상급종합병원",
    "병원 경영 재무",
    "의료법 복지부",
    "간호사 인력",
    "심평원 의료급여",
    "의료기관 경영난",
    "의대 의료개혁",
]

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news.json")


def search_naver(query, display=100):
    """네이버 뉴스 검색 API 호출 (표준 라이브러리만 사용)"""
    params = urllib.parse.urlencode({"query": query, "display": display, "sort": "date"})
    url = f"https://openapi.naver.com/v1/search/news.json?{params}"
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", CLIENT_ID)
    req.add_header("X-Naver-Client-Secret", CLIENT_SECRET)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")).get("items", [])
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"  ⚠ HTTP {e.code} ({query}): {body[:120]}")
        return []
    except Exception as e:
        print(f"  ⚠ 오류 ({query}): {e}")
        return []


def clean(text):
    """HTML 태그·엔티티 제거"""
    text = re.sub(r"<[^>]+>", "", text or "")
    for old, new in [("&lt;","<"),("&gt;",">"),("&amp;","&"),("&quot;",'"'),("&#39;","'")]:
        text = text.replace(old, new)
    return text.strip()


def find_source(item):
    """originallink 또는 link에서 언론사 판별"""
    for url in [item.get("originallink", ""), item.get("link", "")]:
        for src in SOURCES:
            if src["domain"] in url:
                return src["name"]
    return None


def parse_date(date_str):
    """RSS 날짜 문자열 → datetime 변환"""
    for fmt in ["%a, %d %b %Y %H:%M:%S +0900", "%a, %d %b %Y %H:%M:%S +0000"]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    return datetime.min


def main():
    # API 키 미설정 확인
    if not CLIENT_ID or not CLIENT_SECRET:
        print("=" * 55)
        print("  오류: API 키가 설정되지 않았습니다.")
        print()
        print("  fetch_news.py 파일을 열어 아래 두 줄을 수정하세요:")
        print('  CLIENT_ID     = "발급받은_클라이언트_아이디"')
        print('  CLIENT_SECRET = "발급받은_클라이언트_시크릿"')
        print()
        print("  발급 방법: https://developers.naver.com")
        print("  → 애플리케이션 등록 → 검색 API 사용 신청")
        print("=" * 55)
        return

    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 네이버 뉴스 수집 시작")
    print(f"검색어 {len(QUERIES)}개, 언론사 {len(SOURCES)}개\n")

    seen_urls = set()
    articles = []

    for query in QUERIES:
        print(f"  검색: {query}")
        items = search_naver(query)
        for item in items:
            link = item.get("originallink") or item.get("link", "")
            if not link or link in seen_urls:
                continue
            src_name = find_source(item)
            if not src_name:
                continue
            seen_urls.add(link)
            articles.append({
                "title":       clean(item.get("title", "")),
                "link":        link,
                "description": clean(item.get("description", "")),
                "pubDate":     item.get("pubDate", ""),
                "_src":        src_name,
            })

    # 날짜 내림차순 정렬
    articles.sort(key=lambda a: parse_date(a["pubDate"]), reverse=True)

    output = {
        "updated":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "count":    len(articles),
        "articles": articles,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 결과 요약 출력
    cnt = Counter(a["_src"] for a in articles)
    print(f"\n총 {len(articles)}건 저장 → news.json")
    print("-" * 30)
    for src in SOURCES:
        n = cnt.get(src["name"], 0)
        bar = "█" * min(n, 20)
        print(f"  {'O' if n else 'X'} {src['name']:<12} {n:>3}건  {bar}")
    print("-" * 30)
    print("완료\n")


if __name__ == "__main__":
    main()
