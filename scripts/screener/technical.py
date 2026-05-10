"""기술적 지표 계산 (EMA 골든크로스 + RSI)"""

import sys
import json
import urllib.request
from pathlib import Path
from datetime import date, timedelta

BACKTESTER_DIR = Path(__file__).parent.parent.parent / "backtester"
sys.path.insert(0, str(BACKTESTER_DIR))


def _ema(series: list, period: int) -> list:
    k = 2 / (period + 1)
    ema = [series[0]]
    for v in series[1:]:
        ema.append(v * k + ema[-1] * (1 - k))
    return ema


def _rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 2:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def _fetch_crypto_closes(coingecko_id: str, days: int = 120) -> list:
    """CoinGecko 무료 API로 일봉 종가 리스트 반환 (market_chart → 일별 price)"""
    url = (
        f"https://api.coingecko.com/api/v3/coins/{coingecko_id}"
        f"/market_chart?vs_currency=usd&days={days}&interval=daily"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    # data["prices"]: [[timestamp_ms, price], ...]
    return [row[1] for row in data["prices"]]


def _get_crypto_signal(stock: dict) -> dict:
    """암호화폐 기술적 신호 (CoinGecko 일봉)"""
    coingecko_id = stock.get("coingecko_id", "bitcoin")
    try:
        closes = _fetch_crypto_closes(coingecko_id)
        if len(closes) < 65:
            return _no_data_result(stock, error="데이터 부족")

        ema20 = _ema(closes, 20)
        ema60 = _ema(closes, 60)
        rsi = _rsi(closes)
        current_price = closes[-1]

        cross_above = ema20[-2] <= ema60[-2] and ema20[-1] > ema60[-1]
        cross_below = ema20[-2] >= ema60[-2] and ema20[-1] < ema60[-1]
        ema_trend = ema20[-1] > ema60[-1]
        ema_gap = (ema20[-1] - ema60[-1]) / ema60[-1] * 100

        if cross_above and 45 <= rsi <= 70:
            signal = "BUY"
            strength = (rsi - 45) / 25 * 0.5 + 0.5
        elif cross_below or rsi > 75:
            signal = "SELL"
            strength = min((rsi - 75) / 20, 1.0) if rsi > 75 else 0.7
        elif ema_trend and 50 <= rsi <= 65:
            signal = "WATCH"
            strength = (rsi - 50) / 15 * 0.4
        else:
            signal = "HOLD"
            strength = 0.0

        return {
            "code": stock["code"],
            "name": stock["name"],
            "market": stock["market"],
            "signal": signal,
            "technical_score": round(strength, 2),
            "rsi": round(rsi, 1),
            "ema_gap": round(ema_gap, 2),
            "current_price": current_price,
            "cross_above": cross_above,
            "ema_trend": ema_trend,
            "error": None,
        }
    except Exception as e:
        return _no_data_result(stock, error=str(e))


def get_technical_signal(stock: dict) -> dict:
    """가격 데이터를 가져와 기술적 신호 계산 (주식: KIS API, 암호화폐: CoinGecko)"""
    if stock.get("type") == "crypto":
        return _get_crypto_signal(stock)

    try:
        from kis_backtest.providers.kis.auth import KISAuth
        from kis_backtest.providers.kis.data import KISDataProvider

        auth = KISAuth.from_env()
        provider = KISDataProvider(auth)

        end = date.today()
        start = end - timedelta(days=120)
        bars = provider.get_history(stock["code"], start, end)

        if not bars or len(bars) < 65:
            return _no_data_result(stock)

        closes = [b.close for b in bars]
        ema20 = _ema(closes, 20)
        ema60 = _ema(closes, 60)
        rsi = _rsi(closes)
        current_price = closes[-1]

        # 골든크로스 감지 (전일 데드, 당일 골든)
        cross_above = ema20[-2] <= ema60[-2] and ema20[-1] > ema60[-1]
        cross_below = ema20[-2] >= ema60[-2] and ema20[-1] < ema60[-1]
        ema_trend = ema20[-1] > ema60[-1]  # EMA20 > EMA60 유지 중

        # 신호 판단
        if cross_above and 45 <= rsi <= 70:
            signal = "BUY"
            strength = (rsi - 45) / 25 * 0.5 + 0.5
        elif cross_below or rsi > 75:
            signal = "SELL"
            strength = min((rsi - 75) / 20, 1.0) if rsi > 75 else 0.7
        elif ema_trend and 50 <= rsi <= 65:
            signal = "WATCH"  # 추세 유지 중, 모니터링
            strength = (rsi - 50) / 15 * 0.4
        else:
            signal = "HOLD"
            strength = 0.0

        # EMA 이격도 (%)
        ema_gap = (ema20[-1] - ema60[-1]) / ema60[-1] * 100

        return {
            "code": stock["code"],
            "name": stock["name"],
            "market": stock["market"],
            "signal": signal,
            "technical_score": round(strength, 2),
            "rsi": round(rsi, 1),
            "ema_gap": round(ema_gap, 2),
            "current_price": current_price,
            "cross_above": cross_above,
            "ema_trend": ema_trend,
            "error": None,
        }

    except Exception as e:
        return _no_data_result(stock, error=str(e))


def _no_data_result(stock: dict, error: str = "데이터 없음") -> dict:
    return {
        "code": stock["code"],
        "name": stock["name"],
        "market": stock["market"],
        "signal": "UNKNOWN",
        "technical_score": 0.0,
        "rsi": None,
        "ema_gap": None,
        "current_price": None,
        "cross_above": False,
        "ema_trend": False,
        "error": error,
    }
