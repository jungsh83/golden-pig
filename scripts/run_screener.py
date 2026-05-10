#!/usr/bin/env python3
"""
종목 발굴 스크리너 - 뉴스/소셜 센티먼트 + 기술적 신호 통합
실행: uv run python scripts/run_screener.py
"""

import os
import sys
import json
import time
import urllib.request
from pathlib import Path
from datetime import datetime

# 환경변수 로드 (여러 위치 탐색)
for _env_path in [
    Path.home() / ".claude/channels/discord/.env",
    Path(__file__).parent.parent / ".env",
    Path.home() / ".env",
]:
    if _env_path.exists():
        for line in _env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backtester"))

from screener.universe import ALL_STOCKS
from screener.data_sources import collect_stock_data
from screener.sentiment import analyze_sentiment
from screener.technical import get_technical_signal
from db_logger import log_screener

DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_CHAT_ID = "1491445572345790626"  # 스크리닝 전용 채널
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

SECTOR_EMOJI = {
    "반도체_KR": "🔵", "바이오_KR": "🟢", "2차전지_KR": "🟡",
    "반도체_US": "🟣", "바이오_US": "🔵",
}
SIGNAL_EMOJI = {"BUY": "🚀", "WATCH": "👀", "HOLD": "⚪", "SELL": "🔴", "UNKNOWN": "❓"}


def send_discord(message: str):
    url = f"https://discord.com/api/v10/channels/{DISCORD_CHAT_ID}/messages"
    token = DISCORD_TOKEN.strip()
    data = json.dumps({"content": message}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
        "User-Agent": "DiscordBot (https://github.com/discord/discord-api-docs, 10)",
    })
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"Discord 전송 실패: {e}")


def compute_final_score(tech_score: float, sentiment_score: float) -> float:
    """기술적 점수(60%) + 센티먼트 점수(40%) 가중 합산"""
    norm_sentiment = (sentiment_score + 1) / 2  # -1~+1 → 0~1
    return round(tech_score * 0.6 + norm_sentiment * 0.4, 3)


def run_screener():
    now = datetime.now().strftime("%m/%d %H:%M")
    print(f"[{now}] 종목 발굴 스크리너 시작 ({len(ALL_STOCKS)}종목)")

    send_discord(f"**📡 [{now}] 종목 발굴 스크리너 실행 중...** ({len(ALL_STOCKS)}종목 분석)")

    results = []

    for i, stock in enumerate(ALL_STOCKS):
        print(f"  [{i+1}/{len(ALL_STOCKS)}] {stock['name']} ({stock['code']}) 분석 중...")

        # 1. 기술적 신호
        tech = get_technical_signal(stock)

        # 2. 뉴스/소셜 데이터 수집
        raw_data = collect_stock_data(stock)
        time.sleep(0.3)

        # 3. 감성 분석
        if ANTHROPIC_API_KEY and (raw_data["news"] or raw_data["social"]):
            sentiment = analyze_sentiment(stock["name"], raw_data["news"], raw_data["social"])
        else:
            sentiment = {"score": 0.0, "label": "NEUTRAL", "reason": "데이터 없음", "key_topics": []}

        # 4. 종합 점수
        final_score = compute_final_score(tech["technical_score"], sentiment["score"])

        result = {
            **tech,
            "sentiment_score": sentiment["score"],
            "sentiment_label": sentiment["label"],
            "sentiment_reason": sentiment["reason"],
            "key_topics": sentiment.get("key_topics", []),
            "final_score": final_score,
        }
        results.append(result)
        log_screener(
            name=stock["name"], code=stock["code"], market=stock["market"],
            signal=result["signal"], tech_score=result["technical_score"],
            sentiment_score=result["sentiment_score"], final_score=result["final_score"],
            rsi=result.get("rsi"), key_topics=result.get("key_topics", []),
            sentiment_reason=result["sentiment_reason"],
        )

        time.sleep(0.5)

    # 정렬: BUY/WATCH 신호 우선, 최종 점수 내림차순
    signal_priority = {"BUY": 0, "WATCH": 1, "HOLD": 2, "SELL": 3, "UNKNOWN": 4}
    results.sort(key=lambda x: (signal_priority.get(x["signal"], 4), -x["final_score"]))

    # Discord 결과 전송
    _send_results(results, now)
    return results


def _send_results(results: list, now: str):
    # 상위 BUY/WATCH 종목만 먼저
    top_picks = [r for r in results if r["signal"] in ("BUY", "WATCH")][:8]

    if not top_picks:
        send_discord(f"**📊 [{now}] 스크리닝 완료 — 현재 매수 신호 종목 없음**\n시장 관망 구간입니다.")
        return

    lines = [f"**📊 [{now}] 종목 발굴 스크리닝 결과**\n"]
    lines.append("```")
    lines.append(f"{'종목':<12} {'신호':<6} {'기술':>5} {'센티':>5} {'종합':>5} {'RSI':>5}")
    lines.append("-" * 45)
    for r in top_picks:
        sig_e = SIGNAL_EMOJI.get(r["signal"], "")
        t_score = f"{r['technical_score']:.2f}"
        s_score = f"{r['sentiment_score']:+.2f}"
        f_score = f"{r['final_score']:.2f}"
        rsi = f"{r['rsi']}" if r["rsi"] else "N/A"
        lines.append(f"{r['name']:<12} {sig_e}{r['signal']:<5} {t_score:>5} {s_score:>5} {f_score:>5} {rsi:>5}")
    lines.append("```\n")

    # 상세 설명 (상위 3종목)
    for r in top_picks[:3]:
        sig_e = SIGNAL_EMOJI.get(r["signal"], "")
        topics = ", ".join(r.get("key_topics", [])[:2]) or "N/A"
        price = f"{r['current_price']:,.0f}원" if r["current_price"] else "N/A"
        ema_gap = f"{r['ema_gap']:+.1f}%" if r["ema_gap"] is not None else "N/A"
        lines.append(
            f"{sig_e} **{r['name']}** ({r['code']}) — 종합 {r['final_score']:.2f}\n"
            f"  현재가: {price} | EMA이격: {ema_gap} | RSI: {r['rsi']}\n"
            f"  센티먼트: {r['sentiment_label']} — {r['sentiment_reason']}\n"
            f"  주요이슈: {topics}\n"
        )

    send_discord("\n".join(lines))
    print(f"결과 전송 완료: {len(top_picks)}개 매수/관심 종목")


if __name__ == "__main__":
    run_screener()
