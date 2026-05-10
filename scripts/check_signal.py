#!/usr/bin/env python3
"""
삼성전자(005930) MACD+RSI 적극 전략 신호 확인 스크립트
MACD(8/17/6) cross + RSI(14) 기반으로 BUY/SELL/HOLD 신호를 계산해 Discord로 전송.
"""

import sys
import os
import json
import urllib.request
from pathlib import Path
from datetime import date, timedelta

# backtester 루트를 sys.path에 추가
BACKTESTER_DIR = Path(__file__).parent.parent / "backtester"
sys.path.insert(0, str(BACKTESTER_DIR))
sys.path.insert(0, str(Path(__file__).parent))

from db_logger import log_signal

DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_CHAT_ID = "1502591461063917670"
SYMBOL = "005930"


def send_discord(message: str):
    url = f"https://discord.com/api/v10/channels/{DISCORD_CHAT_ID}/messages"
    data = json.dumps({"content": message}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bot {DISCORD_TOKEN.strip()}",
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (https://github.com/discord/discord-api-docs, 10)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Discord 전송 실패: {e}")
        return False


def compute_ema(series, period):
    k = 2 / (period + 1)
    ema = [series[0]]
    for price in series[1:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema


def compute_macd(closes, fast=8, slow=17, signal=6):
    ema_fast = compute_ema(closes, fast)
    ema_slow = compute_ema(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = compute_ema(macd_line, signal)
    return macd_line, signal_line


def compute_rsi(closes, period=14):
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    rsi_values = []
    for i in range(period, len(gains)):
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - 100 / (1 + rs))
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    return rsi_values


def get_signal():
    from kis_backtest.providers.kis.auth import KISAuth
    from kis_backtest.providers.kis.data import KISDataProvider

    auth = KISAuth.from_env()
    provider = KISDataProvider(auth)

    end = date.today()
    start = end - timedelta(days=90)
    bars = provider.get_history(SYMBOL, start, end)

    if not bars or len(bars) < 40:
        return None, None, None, None

    closes = [b.close for b in bars]
    current_price = closes[-1]

    macd_line, signal_line = compute_macd(closes)
    rsi_values = compute_rsi(closes)

    # 최근 2개 값으로 크로스 판단
    m_prev, m_curr = macd_line[-2], macd_line[-1]
    s_prev, s_curr = signal_line[-2], signal_line[-1]
    rsi = rsi_values[-1]

    cross_above = m_prev <= s_prev and m_curr > s_curr
    cross_below = m_prev >= s_prev and m_curr < s_curr

    if cross_above and rsi > 40:
        signal = "BUY"
        strength = min((rsi - 40) / 30, 1.0)
    elif cross_below or rsi > 70:
        signal = "SELL"
        strength = min((rsi - 70) / 30, 1.0) if rsi > 70 else 0.7
    else:
        signal = "HOLD"
        strength = 0.0

    return signal, round(strength, 2), round(rsi, 1), current_price


def main():
    global DISCORD_TOKEN
    if not DISCORD_TOKEN:
        env_path = Path(__file__).parent.parent.parent.parent / ".claude/channels/discord/.env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("DISCORD_BOT_TOKEN="):
                    os.environ["DISCORD_BOT_TOKEN"] = line.split("=", 1)[1].strip()
                    DISCORD_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
                    break

    from datetime import datetime
    now = datetime.now().strftime("%m/%d %H:%M")

    try:
        signal, strength, rsi, price = get_signal()

        if signal is None:
            send_discord(f"⚠️ [{now}] 005930 신호 확인 실패: 데이터 부족")
            return

        macd_diff = 0.0
        try:
            from kis_backtest.providers.kis.auth import KISAuth
            auth = KISAuth.from_env()
            mode = "paper" if auth.is_paper else "live"
        except Exception:
            mode = "paper"
        log_signal(SYMBOL, signal, rsi, macd_diff, strength or 0.0, price, mode=mode)

        emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(signal, "⚪")
        bar = "█" * int((strength or 0) * 10) + "░" * (10 - int((strength or 0) * 10))

        msg = (
            f"**{emoji} [{now}] 삼성전자(005930) 매매 신호**\n"
            f"```\n"
            f"신호:    {signal}\n"
            f"강도:    [{bar}] {int((strength or 0) * 100)}%\n"
            f"현재가:  {price:,.0f}원\n"
            f"RSI(14): {rsi}\n"
            f"전략:    MACD(8/17/6) + RSI\n"
            f"```"
        )
        send_discord(msg)
        print(f"[{now}] {signal} ({strength}) 전송 완료")

    except Exception as e:
        send_discord(f"⚠️ [{now}] 005930 신호 오류: {e}")
        print(f"오류: {e}")


if __name__ == "__main__":
    main()
