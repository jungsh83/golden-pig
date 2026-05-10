"""뉴스 및 소셜 미디어 데이터 수집"""

import urllib.request
import urllib.parse
import json
import re
import time
from datetime import datetime, timedelta


_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _fetch_url(url: str, headers: dict = None, timeout: int = 10) -> str:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": _BROWSER_UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def fetch_naver_news(search_term: str, max_items: int = 5) -> list[dict]:
    """네이버 뉴스 검색 (제목 + 요약 + URL)"""
    query = urllib.parse.quote(f"{search_term} 주가")
    url = f"https://search.naver.com/search.naver?where=news&query={query}&sort=1"
    raw = _fetch_url(url)
    items = []
    titles = re.findall(r'"title":"([^"]{10,})"', raw)
    descs = re.findall(r'"description":"([^"]{10,})"', raw)
    # 실제 기사 URL: n.news.naver.com 링크
    links = re.findall(r'href="(https://n\.news\.naver\.com/[^"]+)"', raw)
    seen = set()
    for i, title in enumerate(titles):
        title_clean = re.sub(r"<[^>]+>", "", title).strip()
        if not title_clean or title_clean in seen:
            continue
        seen.add(title_clean)
        desc = descs[i] if i < len(descs) else ""
        desc_clean = re.sub(r"<[^>]+>|\\[a-z]", "", desc).strip()[:200]
        link = links[i] if i < len(links) else ""
        items.append({"title": title_clean, "summary": desc_clean, "url": link, "source": "naver"})
        if len(items) >= max_items:
            break
    return items


def fetch_google_news_rss(search_term: str, max_items: int = 5) -> list[dict]:
    """Google News RSS로 뉴스 수집 (제목 + 요약 + URL)"""
    query = urllib.parse.quote(f"{search_term} stock")
    url = f"https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"
    xml = _fetch_url(url)
    items = []
    # <item> 블록 단위로 파싱
    item_blocks = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
    for block in item_blocks[:max_items]:
        title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</title>", block)
        desc_m = re.search(r"<description>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</description>", block, re.DOTALL)
        link_m = re.search(r"<link>(https?://[^\s<]+)</link>", block)
        if not title_m:
            continue
        title = title_m.group(1).strip()
        desc = re.sub(r"<[^>]+>", "", desc_m.group(1)).strip()[:200] if desc_m else ""
        link = link_m.group(1).strip() if link_m else ""
        items.append({"title": title, "summary": desc, "url": link, "source": "google_news"})
    return items


def fetch_stocktwits(ticker: str, max_items: int = 10) -> list[dict]:
    """StockTwits API로 소셜 센티먼트 수집 (NASDAQ 종목)"""
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
    text = _fetch_url(url)
    if not text:
        return []
    try:
        data = json.loads(text)
        messages = data.get("messages", [])[:max_items]
        items = []
        for msg in messages:
            sentiment = msg.get("entities", {}).get("sentiment", {})
            items.append({
                "text": msg.get("body", "")[:300],
                "sentiment_label": sentiment.get("basic", ""),  # Bullish/Bearish/None
                "source": "stocktwits",
            })
        return items
    except Exception:
        return []


def fetch_reddit_mentions(ticker: str, subreddits: list[str] = None, max_items: int = 5) -> list[dict]:
    """Reddit JSON API로 종목 언급 수집"""
    subreddits = subreddits or ["stocks", "investing", "wallstreetbets"]
    items = []
    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/search.json?q={ticker}&sort=new&limit=5&t=day"
        text = _fetch_url(url, headers={"User-Agent": "StockScreener/1.0 (by /u/screener_bot)"})
        if not text:
            continue
        try:
            data = json.loads(text)
            posts = data.get("data", {}).get("children", [])
            for post in posts[:max_items]:
                d = post.get("data", {})
                items.append({
                    "title": d.get("title", ""),
                    "text": (d.get("selftext", "") or "")[:300],
                    "score": d.get("score", 0),
                    "source": f"reddit_{sub}",
                })
        except Exception:
            continue
        time.sleep(0.5)
    return items


def collect_stock_data(stock: dict) -> dict:
    """단일 종목의 뉴스+소셜 데이터 수집"""
    code = stock["code"]
    name = stock["name"]
    market = stock["market"]
    search_terms = stock["search_terms"]

    result = {"code": code, "name": name, "market": market, "news": [], "social": []}

    primary_term = search_terms[0]

    # 뉴스 수집
    if market in ("KOSPI", "KOSDAQ"):
        result["news"] = fetch_naver_news(primary_term, max_items=5)
        if not result["news"]:
            result["news"] = fetch_google_news_rss(primary_term, max_items=5)
    else:
        result["news"] = fetch_google_news_rss(primary_term, max_items=5)
        result["social"] = fetch_stocktwits(code, max_items=10)
        result["social"] += fetch_reddit_mentions(code, max_items=3)

    return result
