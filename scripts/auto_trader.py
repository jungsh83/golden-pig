#!/usr/bin/env python3
"""
다종목 자동매매 스크립트 — 15분봉 기반
사용법: python auto_trader.py [심볼]  (기본값: 005930)
  python auto_trader.py 005930   — 삼성전자 MACD(8/17/6) + RSI
  python auto_trader.py 000660   — SK하이닉스 듀얼MACD(6/13/5 진입 / 12/26/9 청산) + RSI

리스크 컨트롤:
- MAX_INVEST_RATIO: 가용 현금의 최대 투자 비율 (기본 20%)
- DAILY_LOSS_LIMIT: 일일 손실 한도 (기본 -3%)
- 중복 매수 방지: 이미 보유 중이면 추가 매수 안 함
- 장 시간 외 주문 차단 (09:05 ~ 15:15 KST)
"""

import sys
import os
import json
import time
import urllib.request
from pathlib import Path
from datetime import datetime, date, timedelta, time as dtime

BACKTESTER_DIR = Path(__file__).parent.parent / "backtester"
sys.path.insert(0, str(BACKTESTER_DIR))

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

DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_CHAT_ID = "1491445955185217587"  # 거래 알림 전용 채널
STATE_FILE = Path(__file__).parent / "trader_state.json"

from db_logger import log_trade, log_signal

MAX_INVEST_RATIO = 0.30   # 신호 강도 100%일 때 최대 비중
MIN_INVEST_RATIO = 0.10   # 신호 강도 0%일 때 최소 비중
DAILY_LOSS_LIMIT = -0.03
MARKET_OPEN = dtime(9, 5)
MARKET_CLOSE = dtime(15, 15)
BAR_MINUTES = 15
MIN_BARS = 40
LOOKBACK_DAYS = 5

# 종목별 전략 파라미터
STRATEGIES = {
    "005930": {
        "name": "삼성전자",
        "macd_entry": {"fast": 6, "slow": 13, "signal": 5},
        "macd_exit": {"fast": 12, "slow": 26, "signal": 9},
        "rsi_entry": 45,
        "rsi_exit": 75,
    },
    "000660": {
        "name": "SK하이닉스",
        "macd_entry": {"fast": 6, "slow": 13, "signal": 5},
        "macd_exit": {"fast": 12, "slow": 26, "signal": 9},  # 듀얼 MACD: 청산은 느린 MACD
        "rsi_entry": 45,
        "rsi_exit": 75,
    },
    "003490": {
        "name": "대한항공",
        "macd_entry": {"fast": 12, "slow": 26, "signal": 9},
        "macd_exit": {"fast": 12, "slow": 26, "signal": 9},
        "rsi_entry": 45,
        "rsi_exit": 74,
    },
}


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


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def _trading_days_back(n: int) -> list[date]:
    result = []
    d = date.today()
    while len(result) < n:
        if d.weekday() < 5:
            result.append(d)
        d -= timedelta(days=1)
    return list(reversed(result))


def aggregate_to_15min(bars_1m: list) -> list:
    if not bars_1m:
        return []

    buckets: dict[datetime, dict] = {}
    for bar in bars_1m:
        t = bar.time
        bucket_min = (t.minute // BAR_MINUTES) * BAR_MINUTES
        bucket_dt = t.replace(minute=bucket_min, second=0, microsecond=0)

        if bucket_dt not in buckets:
            buckets[bucket_dt] = {
                "open": bar.open, "high": bar.high,
                "low": bar.low, "close": bar.close, "volume": bar.volume,
            }
        else:
            b = buckets[bucket_dt]
            b["high"] = max(b["high"], bar.high)
            b["low"] = min(b["low"], bar.low)
            b["close"] = bar.close
            b["volume"] += bar.volume

    from kis_backtest.models import Bar
    return [
        Bar(time=dt, open=v["open"], high=v["high"], low=v["low"],
            close=v["close"], volume=v["volume"])
        for dt, v in sorted(buckets.items())
    ]


def compute_ema(series, period):
    k = 2 / (period + 1)
    ema = [series[0]]
    for price in series[1:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema


def compute_macd(closes, fast, slow, signal):
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
    if len(gains) < period:
        return []
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


def get_signal_15min(symbol: str, cfg: dict):
    """최근 5거래일 15분봉으로 전략별 MACD+RSI 신호 산출"""
    from kis_backtest.providers.kis.auth import KISAuth
    from kis_backtest.providers.kis.data import KISDataProvider
    from kis_backtest.models import Resolution

    auth = KISAuth.from_env()
    provider = KISDataProvider(auth)

    trading_days = _trading_days_back(LOOKBACK_DAYS)
    all_bars_1m = []
    for d in trading_days:
        bars = provider.get_history(symbol, d, d, resolution=Resolution.MINUTE)
        all_bars_1m.extend(bars)
        time.sleep(0.4)

    bars_15m = aggregate_to_15min(all_bars_1m)

    if len(bars_15m) < MIN_BARS:
        print(f"15분봉 데이터 부족: {len(bars_15m)}봉 (최소 {MIN_BARS}봉 필요)")
        return None, None, None, None, None, None, None

    closes = [b.close for b in bars_15m]
    current_price = closes[-1]

    # 진입용 MACD
    ep = cfg["macd_entry"]
    entry_macd, entry_signal = compute_macd(closes, ep["fast"], ep["slow"], ep["signal"])

    # 청산용 MACD (듀얼이면 별도, 아니면 진입과 동일)
    xp = cfg["macd_exit"] or ep
    if cfg["macd_exit"]:
        exit_macd, exit_signal = compute_macd(closes, xp["fast"], xp["slow"], xp["signal"])
    else:
        exit_macd, exit_signal = entry_macd, entry_signal

    rsi_values = compute_rsi(closes)
    if not rsi_values:
        return None, None, None, None, None, None, None

    rsi = rsi_values[-1]

    # 진입 크로스 (빠른 MACD)
    em_prev, em_curr = entry_macd[-2], entry_macd[-1]
    es_prev, es_curr = entry_signal[-2], entry_signal[-1]
    cross_above = em_prev <= es_prev and em_curr > es_curr

    # 청산 크로스 (느린 MACD 또는 동일)
    xm_prev, xm_curr = exit_macd[-2], exit_macd[-1]
    xs_prev, xs_curr = exit_signal[-2], exit_signal[-1]
    cross_below = xm_prev >= xs_prev and xm_curr < xs_curr

    rsi_entry = cfg["rsi_entry"]
    rsi_exit = cfg["rsi_exit"]

    if cross_above and rsi > rsi_entry:
        trade_signal = "BUY"
        strength = min((rsi - rsi_entry) / (100 - rsi_entry), 1.0)
    elif cross_below or rsi > rsi_exit:
        trade_signal = "SELL"
        strength = min((rsi - rsi_exit) / (100 - rsi_exit), 1.0) if rsi > rsi_exit else 0.7
    else:
        trade_signal = "HOLD"
        strength = 0.0

    macd_diff = round(em_curr - es_curr, 5)
    return trade_signal, round(strength, 2), round(rsi, 1), current_price, auth, macd_diff, len(bars_15m)


def check_market_hours() -> bool:
    now = datetime.now().time()
    return MARKET_OPEN <= now <= MARKET_CLOSE


def run_auto_trader(symbol: str):
    cfg = STRATEGIES[symbol]
    name = cfg["name"]
    now_str = datetime.now().strftime("%m/%d %H:%M")
    today = date.today().isoformat()

    if not check_market_hours():
        print(f"[{now_str}] [{name}] 장 시간 외 — 주문 생략")
        return

    signal, strength, rsi, current_price, auth, macd_diff, bars_count = get_signal_15min(symbol, cfg)
    if signal is None:
        send_discord(f"⚠️ [{now_str}] {name}({symbol}) 15분봉 신호 계산 실패 (데이터 부족)")
        return

    mode = "paper" if auth.is_paper else "live"
    log_signal(symbol, signal, rsi, macd_diff, strength or 0.0, current_price, bars_count, mode)

    if signal == "HOLD":
        print(f"[{now_str}] [{name}] HOLD — 주문 없음 (RSI {rsi})")
        return

    from kis_backtest.providers.kis.brokerage import KISBrokerageProvider
    from kis_backtest.models import OrderSide, OrderType

    broker = KISBrokerageProvider.from_auth(auth)
    balance = broker.get_balance()
    time.sleep(0.5)
    positions = broker.get_positions()

    state = load_state()
    # 종목별로 상태 분리
    state_key = f"{today}_{symbol}"
    today_state = state.get(state_key, {})

    start_equity = today_state.get("start_equity")
    if start_equity is None:
        start_equity = balance.total_equity
        today_state["start_equity"] = start_equity
        state[state_key] = today_state
        save_state(state)

    if start_equity > 0:
        daily_return = (balance.total_equity - start_equity) / start_equity
        if daily_return < DAILY_LOSS_LIMIT:
            msg = (
                f"🛑 [{now_str}] **{name}({symbol}) 일일 손실 한도 초과 — 자동매매 중단**\n"
                f"일일 손익: {daily_return:+.2%} (한도: {DAILY_LOSS_LIMIT:.0%})"
            )
            send_discord(msg)
            print(f"[{name}] 일일 손실 한도 초과: {daily_return:+.2%}")
            return

    holding = next((p for p in positions if p.symbol == symbol), None)
    holding_qty = holding.quantity if holding else 0

    if signal == "BUY":
        if holding_qty > 0:
            print(f"[{now_str}] [{name}] 이미 {holding_qty}주 보유 중 — 중복 매수 방지")
            return

        # 신호 강도 기반 비중: 강도 0% → MIN(10%), 강도 100% → MAX(20%)
        s = strength or 0.0
        invest_ratio = MIN_INVEST_RATIO + (MAX_INVEST_RATIO - MIN_INVEST_RATIO) * s
        invest_amount = balance.available_cash * invest_ratio
        qty = int(invest_amount // current_price)
        if qty < 1:
            send_discord(f"⚠️ [{now_str}] {name}({symbol}) 잔고 부족 — 매수 불가 (가용현금: {balance.available_cash:,.0f}원)")
            return

        order = broker.submit_order(symbol, OrderSide.BUY, qty, OrderType.MARKET)
        log_trade(symbol, "BUY", qty, current_price, order.id, 0.0, 0.0, rsi, signal, mode)
        today_state.setdefault("trades", []).append({
            "time": now_str, "side": "BUY", "qty": qty,
            "price": current_price, "order_id": order.id,
        })
        state[state_key] = today_state
        save_state(state)

        bar = "█" * int(s * 10) + "░" * (10 - int(s * 10))

        ep = cfg["macd_entry"]
        xp = cfg["macd_exit"]
        macd_desc = f"MACD({ep['fast']}/{ep['slow']}/{ep['signal']})"
        if xp:
            macd_desc += f" 진입 | MACD({xp['fast']}/{xp['slow']}/{xp['signal']}) 청산"

        msg = (
            f"🟢 [{now_str}] **{name}({symbol}) 자동 매수 주문 완료**\n"
            f"```\n"
            f"주문번호: {order.id}\n"
            f"수량:     {qty}주\n"
            f"현재가:   {current_price:,.0f}원\n"
            f"투자금:   {qty * current_price:,.0f}원 (가용현금의 {invest_ratio:.0%}, 강도 {int(s*100)}%)\n"
            f"RSI(14):  {rsi}  (15분봉)\n"
            f"강도:     [{bar}] {int(s * 100)}%\n"
            f"전략:     {macd_desc}\n"
            f"```"
        )
        send_discord(msg)
        print(f"[{now_str}] [{name}] 매수 주문: {qty}주 @ {current_price:,.0f}원")

    elif signal == "SELL":
        if holding_qty == 0:
            print(f"[{now_str}] [{name}] 보유 없음 — 매도 생략")
            return

        # 매도 사유 판단
        rsi_exit = cfg["rsi_exit"]
        if rsi > rsi_exit:
            sell_reason = f"과열 익절 (RSI {rsi} > {rsi_exit})"
        else:
            sell_reason = "MACD 데드크로스"

        order = broker.submit_order(symbol, OrderSide.SELL, holding_qty, OrderType.MARKET)
        profit = (current_price - holding.average_price) * holding_qty
        profit_rate = (current_price - holding.average_price) / holding.average_price * 100
        log_trade(symbol, "SELL", holding_qty, current_price, order.id, profit, profit_rate, rsi, signal, mode)

        today_state.setdefault("trades", []).append({
            "time": now_str, "side": "SELL", "qty": holding_qty,
            "price": current_price, "order_id": order.id,
            "profit": round(profit), "profit_rate": round(profit_rate, 2),
        })
        state[state_key] = today_state
        save_state(state)

        emoji = "🔴" if profit < 0 else "🟢"
        msg = (
            f"🔴 [{now_str}] **{name}({symbol}) 자동 매도 주문 완료**\n"
            f"```\n"
            f"주문번호: {order.id}\n"
            f"수량:     {holding_qty}주\n"
            f"현재가:   {current_price:,.0f}원\n"
            f"손익:     {emoji} {profit:+,.0f}원 ({profit_rate:+.2f}%)\n"
            f"RSI(14):  {rsi}  (15분봉)\n"
            f"사유:     {sell_reason}\n"
            f"```"
        )
        send_discord(msg)
        print(f"[{now_str}] [{name}] 매도 주문: {holding_qty}주 @ {current_price:,.0f}원 (손익 {profit:+,.0f}원, {sell_reason})")


def main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else "005930"
    if symbol not in STRATEGIES:
        print(f"지원하지 않는 종목: {symbol}. 지원 종목: {list(STRATEGIES.keys())}")
        sys.exit(1)

    now_str = datetime.now().strftime("%m/%d %H:%M")
    try:
        run_auto_trader(symbol)
    except Exception as e:
        name = STRATEGIES[symbol]["name"]
        send_discord(f"⚠️ [{now_str}] {name}({symbol}) 자동매매 오류: {e}")
        print(f"오류: {e}")
        raise


if __name__ == "__main__":
    main()
