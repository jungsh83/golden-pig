#!/usr/bin/env python3
"""
X(Twitter) 게시 초안 생성 → Discord 전송

사용법:
  python post_to_x.py trade   — 당일 매매 성과 스레드 초안 (크론 자동 실행)
  python post_to_x.py system "오늘 개선 내용 요약"  — 시스템 일지 초안
"""

import os
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, date

for _env_path in [
    Path(__file__).parent.parent / ".env",
    Path.home() / ".claude/channels/discord/.env",
]:
    if _env_path.exists():
        for line in _env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_CHAT_ID = "1502591461063917670"
NOCODB_URL = os.environ.get("NOCODB_URL", "http://localhost:8088")
NOCODB_TOKEN = os.environ.get("NOCODB_TOKEN", "")
NOCODB_BASE = os.environ.get("NOCODB_BASE_ID", "")
NOCODB_TRADE = os.environ.get("NOCODB_TABLE_TRADE", "")
NOCODB_SIGNAL = os.environ.get("NOCODB_TABLE_SIGNAL", "")


def send_discord(message: str):
    url = f"https://discord.com/api/v10/channels/{DISCORD_CHAT_ID}/messages"
    data = json.dumps({"content": message}).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": f"Bot {DISCORD_TOKEN.strip()}",
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (https://github.com/discord/discord-api-docs, 10)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"Discord 전송 실패: {e}")


def _noco_get(table_id: str, where: str = "", limit: int = 100) -> list:
    params = f"?limit={limit}"
    if where:
        params += f"&where={urllib.parse.quote(where, safe='(,)%')}"
    url = f"{NOCODB_URL}/api/v1/db/data/noco/{NOCODB_BASE}/{table_id}{params}"
    req = urllib.request.Request(url, headers={"xc-token": NOCODB_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read()).get("list", [])
    except Exception as e:
        print(f"NocoDB 조회 실패: {e}")
        return []


def build_trade_draft() -> str:
    today_str = date.today().strftime("%Y-%m-%d")
    trades = _noco_get(NOCODB_TRADE, where=f"(timestamp,like,{today_str}%)")
    signals = _noco_get(NOCODB_SIGNAL, where=f"(timestamp,like,{today_str}%)")

    buy_cnt = sum(1 for t in trades if t.get("side") == "BUY")
    sell_cnt = sum(1 for t in trades if t.get("side") == "SELL")
    sig_buy = sum(1 for s in signals if s.get("signal") == "BUY")
    sig_sell = sum(1 for s in signals if s.get("signal") == "SELL")
    sig_hold = sum(1 for s in signals if s.get("signal") == "HOLD")
    total_profit = sum(t.get("profit", 0) or 0 for t in trades if t.get("side") == "SELL")
    mode = trades[0].get("mode", "paper") if trades else "paper"
    mode_label = "🔵모의" if mode == "paper" else "🔴실전"

    profit_str = ""
    if sell_cnt:
        emoji = "🟢" if total_profit >= 0 else "🔴"
        profit_str = f"\n총 실현손익: {emoji} {total_profit:+,.0f}원"

    trade_lines = ""
    for t in trades:
        se = "🟢" if t["side"] == "BUY" else "🔴"
        ts = (t.get("timestamp") or "")[:16]
        p = f" → {t['profit']:+,.0f}원 ({t['profit_rate']:+.1f}%)" if t.get("profit") else ""
        trade_lines += f"\n{se} {ts} {t['side']} {t['qty']}주 @ {t['price']:,.0f}원{p}"

    draft = (
        f"📊 [{today_str}] 일일 자동매매 성과 {mode_label}\n\n"
        f"종목: 삼성전자(005930) 15분봉 전략\n"
        f"신호체크: {len(signals)}회 (매수 {sig_buy} / 매도 {sig_sell} / 홀드 {sig_hold})\n"
        f"체결: 매수 {buy_cnt}회 / 매도 {sell_cnt}회"
        f"{profit_str}\n"
        f"\n📋 체결 내역"
        f"{trade_lines if trade_lines else chr(10) + '없음 (HOLD)'}\n"
        f"\n⚙️ MACD(8/17/6) + RSI(14) | 가용현금 20% | 손실한도 -3%\n"
        f"\n#자동매매 #삼성전자 #퀀트투자 #GoldenPig"
    )
    return draft


def build_system_draft(summary: str) -> list[str]:
    """280자 제한에 맞게 여러 트윗으로 분할."""
    today_str = date.today().strftime("%Y-%m-%d")
    TAGS = "#자동매매 #개발일지 #GoldenPig"
    LIMIT = 275

    lines = [l for l in summary.strip().splitlines() if l.strip()]
    tweets = []
    header = f"🛠️ [{today_str}] 시스템 개선 일지\n\n"

    chunk = header
    for line in lines:
        candidate = chunk + line + "\n"
        if len(candidate) + len(TAGS) + 5 > LIMIT:
            tweets.append(chunk.strip() + (f"\n\n{TAGS}" if not tweets else ""))
            chunk = line + "\n"
        else:
            chunk = candidate

    if chunk.strip() and chunk.strip() != header.strip():
        tweets.append(chunk.strip() + f"\n\n{TAGS}")

    # 트윗 번호 표시
    total = len(tweets)
    if total > 1:
        tweets = [t.rstrip() + f" {i+1}/{total}" for i, t in enumerate(tweets)]

    return tweets


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "trade"

    if mode == "trade":
        draft = build_trade_draft()
        msg = (
            "**📋 X 게시 초안 — 일일 매매 성과**\n"
            "아래 내용을 X에 복붙해주세요 👇\n"
            "```\n" + draft + "\n```"
        )
        send_discord(msg)
        print(draft)

    elif mode == "system":
        summary = " ".join(sys.argv[2:])
        if not summary:
            print("사용법: python post_to_x.py system '오늘 개선 내용'")
            return
        tweets = build_system_draft(summary)
        total = len(tweets)
        header = f"**📋 X 게시 초안 — 시스템 개선 일지 ({total}개 트윗)**\n각각 순서대로 X에 올려주세요 👇\n"
        blocks = "\n".join(f"**[{i+1}/{total}]**\n```\n{t}\n```" for i, t in enumerate(tweets))
        send_discord(header + blocks)
        for i, t in enumerate(tweets, 1):
            print(f"\n[{i}/{total}]\n{t}")


if __name__ == "__main__":
    main()
