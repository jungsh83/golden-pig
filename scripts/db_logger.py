"""NocoDB REST API 로깅 모듈

trade_log, signal_log, screener_log 테이블에 적재.
환경변수:
  NOCODB_URL      - NocoDB 서버 주소 (기본: http://localhost:8088)
  NOCODB_TOKEN    - API 토큰
  NOCODB_BASE_ID  - Base ID
  NOCODB_TABLE_TRADE    - trade_log 테이블 ID
  NOCODB_TABLE_SIGNAL   - signal_log 테이블 ID
  NOCODB_TABLE_SCREENER - screener_log 테이블 ID
"""

import os
import json
import urllib.request
from datetime import datetime
from pathlib import Path

# 환경변수 로드 (미리 로드 안 된 경우 대비)
for _env_path in [
    Path(__file__).parent.parent / ".env",
    Path.home() / ".env",
]:
    if _env_path.exists():
        for line in _env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

_URL = os.environ.get("NOCODB_URL", "http://localhost:8088")
_TOKEN = os.environ.get("NOCODB_TOKEN", "")
_BASE = os.environ.get("NOCODB_BASE_ID", "")
_TABLE_TRADE = os.environ.get("NOCODB_TABLE_TRADE", "")
_TABLE_SIGNAL = os.environ.get("NOCODB_TABLE_SIGNAL", "")
_TABLE_SCREENER = os.environ.get("NOCODB_TABLE_SCREENER", "")


def _insert(table_id: str, row: dict) -> bool:
    if not _TOKEN or not _BASE or not table_id:
        return False
    url = f"{_URL}/api/v1/db/data/noco/{_BASE}/{table_id}"
    data = json.dumps(row).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={
            "xc-token": _TOKEN,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        print(f"[db_logger] NocoDB 적재 실패 ({table_id}): {e}")
        return False


def log_trade(
    symbol: str,
    side: str,
    qty: int,
    price: float,
    order_id: str = "",
    profit: float = 0.0,
    profit_rate: float = 0.0,
    rsi: float = 0.0,
    signal: str = "",
    mode: str = "paper",
):
    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "price": price,
        "order_id": order_id,
        "profit": round(profit, 2),
        "profit_rate": round(profit_rate, 2),
        "rsi": round(rsi, 2),
        "signal": signal,
        "mode": mode,
    }
    return _insert(_TABLE_TRADE, row)


def log_signal(
    symbol: str,
    signal: str,
    rsi: float,
    macd_diff: float,
    strength: float,
    price: float,
    bars_count: int = 0,
    mode: str = "paper",
):
    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": symbol,
        "signal": signal,
        "rsi": round(rsi, 2),
        "macd_diff": round(macd_diff, 5),
        "strength": round(strength, 3),
        "price": price,
        "bars_count": bars_count,
        "mode": mode,
    }
    return _insert(_TABLE_SIGNAL, row)


def log_screener(
    name: str,
    code: str,
    market: str,
    signal: str,
    tech_score: float,
    sentiment_score: float,
    final_score: float,
    rsi,
    key_topics: list,
    sentiment_reason: str = "",
):
    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "name": name,
        "code": code,
        "market": market,
        "signal": signal,
        "tech_score": round(tech_score, 3),
        "sentiment_score": round(sentiment_score, 3),
        "final_score": round(final_score, 3),
        "rsi": rsi,
        "key_topics": ", ".join(key_topics) if key_topics else "",
        "sentiment_reason": sentiment_reason,
    }
    return _insert(_TABLE_SCREENER, row)
