#!/usr/bin/env python3
"""
삼성전자(DS부문) + SK하이닉스 전일 뉴스 종합 분석 → 스크리닝 채널 전송 + NocoDB 기록
실행: uv run python scripts/morning_briefing.py
크론: 매 평일 06:30 KST (UTC 21:30 전날)
"""

import os
import sys
import json
import html
import urllib.request
from pathlib import Path
from datetime import datetime, date, timedelta

for _env_path in [
    Path.home() / ".claude/channels/discord/.env",
    Path(__file__).parent.parent / ".env",
]:
    if _env_path.exists():
        for line in _env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backtester"))

from screener.data_sources import fetch_naver_news, fetch_google_news_rss
from db_logger import log_screener

try:
    from screener.sentiment import analyze_sentiment as _analyze_sentiment
    _SENTIMENT_AVAILABLE = True
except Exception:
    _SENTIMENT_AVAILABLE = False
    _analyze_sentiment = None


def analyze_sentiment(stock_name, news_items, social_items):
    if not _SENTIMENT_AVAILABLE or _analyze_sentiment is None:
        return {"score": 0.0, "label": "NEUTRAL", "reason": "감성분석 불가 (transformers 미설치)", "key_topics": []}
    try:
        return _analyze_sentiment(stock_name, news_items, social_items)
    except Exception as e:
        return {"score": 0.0, "label": "NEUTRAL", "reason": f"분석 오류: {e}", "key_topics": []}

DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_SCREENER_CH = "1491445572345790626"

TARGETS = [
    {
        "code": "005930",
        "name": "삼성전자 DS부문",
        "market": "KOSPI",
        "search_terms": ["삼성전자 반도체", "삼성 DS부문", "삼성 HBM", "삼성전자 파운드리"],
    },
    {
        "code": "000660",
        "name": "SK하이닉스",
        "market": "KOSPI",
        "search_terms": ["SK하이닉스", "하이닉스 HBM", "하이닉스 실적"],
    },
]


def send_discord(message: str):
    url = f"https://discord.com/api/v10/channels/{DISCORD_SCREENER_CH}/messages"
    data = json.dumps({"content": message}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bot {DISCORD_TOKEN.strip()}",
        "Content-Type": "application/json",
        "User-Agent": "DiscordBot (https://github.com/discord/discord-api-docs, 10)",
    })
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"Discord 전송 실패: {e}")


def collect_news(target: dict) -> list:
    """복수 검색어로 네이버 뉴스 수집 후 중복 제거"""
    seen_titles = set()
    all_news = []
    for term in target["search_terms"]:
        items = fetch_naver_news(term, max_items=4)
        if not items:
            items = fetch_google_news_rss(term, max_items=4)
        for item in items:
            title = item.get("title", "")
            if title and title not in seen_titles:
                seen_titles.add(title)
                all_news.append(item)
        if len(all_news) >= 10:
            break
    return all_news[:10]


def format_sentiment_bar(score: float) -> str:
    filled = int((score + 1) / 2 * 10)
    filled = max(0, min(10, filled))
    return "▓" * filled + "░" * (10 - filled)


def run_briefing():
    today = date.today()
    yesterday = today - timedelta(days=1)
    now_str = datetime.now().strftime("%m/%d %H:%M")
    target_date = yesterday.strftime("%Y-%m-%d")

    print(f"[{now_str}] 모닝 브리핑 시작 — {target_date} 뉴스 분석")

    header = f"**📰 [{today.strftime('%Y-%m-%d')} 06:30] 반도체 모닝 브리핑**\n전일({target_date}) 삼성전자DS·SK하이닉스 뉴스 종합 분석\n"
    send_discord(header)

    sections = []

    for target in TARGETS:
        print(f"  [{target['name']}] 뉴스 수집 중...")
        news = collect_news(target)

        if not news:
            sections.append(f"**{target['name']}** — 수집된 뉴스 없음\n")
            log_screener(
                name=target["name"], code=target["code"], market=target["market"],
                signal="UNKNOWN", tech_score=0.0, sentiment_score=0.0, final_score=0.0,
                rsi=None, key_topics=[], sentiment_reason="뉴스 없음",
            )
            continue

        sentiment = analyze_sentiment(target["name"], news, [])
        score = sentiment["score"]
        label = sentiment["label"]
        topics = sentiment.get("key_topics", [])

        # NocoDB 기록
        log_screener(
            name=target["name"], code=target["code"], market=target["market"],
            signal=label, tech_score=0.0, sentiment_score=score, final_score=score,
            rsi=None, key_topics=topics, sentiment_reason=sentiment["reason"],
        )

        label_emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "⚪"}.get(label, "⚪")
        bar = format_sentiment_bar(score)

        news_lines = ""
        for item in news[:5]:
            title = html.unescape(item.get("title", "")).strip()
            url = item.get("url", "").strip()
            if url:
                news_lines += f"  • [{title}]({url})\n"
            else:
                news_lines += f"  • {title}\n"

        section = (
            f"**{label_emoji} {target['name']}** ({target['code']})\n"
            f"```\n"
            f"센티먼트: [{bar}] {score:+.2f} ({label})\n"
            f"주요이슈:  {', '.join(topics) if topics else 'N/A'}\n"
            f"요약:      {sentiment['reason']}\n"
            f"```\n"
            f"**주요 기사 ({len(news)}건)**\n"
            f"{news_lines}"
        )
        sections.append(section)
        print(f"  [{target['name']}] {label} {score:+.2f} — 기사 {len(news)}건")

    full_msg = "\n".join(sections)
    send_discord(full_msg)
    print(f"[{now_str}] 브리핑 전송 완료")


if __name__ == "__main__":
    run_briefing()
