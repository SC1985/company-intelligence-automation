import io
import time
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any

import requests

# We'll try yfinance first; if unavailable at runtime, we'll fall back to Stooq.
def _yf_history(symbol: str) -> Tuple[List[datetime], List[float]]:
    try:
        import yfinance as yf  # type: ignore
        import pandas as pd  # type: ignore
        t = yf.Ticker(symbol)
        # auto_adjust=True gets adjusted close; 2y should cover 52-week bounds
        df = t.history(period="2y", interval="1d", auto_adjust=True)
        if df is None or getattr(df, "empty", True):
            return [], []
        closes = df["Close"].dropna()
        if closes.empty:
            return [], []
        idx = closes.index
        # Normalize index to datetime (naive) if tz-aware
        try:
            idx = pd.to_datetime(idx).tz_localize(None)
        except Exception:
            idx = pd.to_datetime(idx)
        dates = [d.to_pydatetime() for d in idx]
        return dates, [float(v) for v in closes.tolist()]
    except Exception:
        return [], []

def _stooq_symbol(symbol: str) -> str:
    # Stooq expects .us suffix for US tickers; strip special chars
    s = symbol.strip()
    s = s.replace("^","").replace(".","-")  # crude normalization
    return f"{s.lower()}.us"

def _stooq_history(symbol: str) -> Tuple[List[datetime], List[float]]:
    import pandas as pd  # type: ignore
    url = f"https://stooq.com/q/d/l/?s={_stooq_symbol(symbol)}&i=d"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        if df is None or df.empty or "Close" not in df.columns:
            return [], []
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
        closes = df["Close"].dropna()
        if closes.empty:
            return [], []
        dates = [d.to_pydatetime() for d in df["Date"].tolist()]
        return dates, [float(v) for v in closes.tolist()]
    except Exception:
        return [], []

def get_daily_history(symbol: str) -> Tuple[str, List[datetime], List[float]]:
    # Try Yahoo first
    dts, closes = _yf_history(symbol)
    if dts and closes:
        return "yf", dts, closes
    # Fallback to Stooq
    dts, closes = _stooq_history(symbol)
    if dts and closes:
        return "stooq", dts, closes
    return "none", [], []

def _pct(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    try:
        if curr is None or prev is None or prev == 0:
            return None
        return (curr/prev - 1.0) * 100.0
    except Exception:
        return None

def _nearest(closes: List[float], k_back: int) -> Optional[float]:
    if not closes: return None
    idx = len(closes) - 1 - k_back
    if 0 <= idx < len(closes):
        return closes[idx]
    return None

def _ytd_ref(dates: List[datetime], closes: List[float]) -> Optional[float]:
    if not dates or not closes: return None
    yr = dates[-1].year - 1
    # find last bar of previous year
    for i in range(len(dates)-1, -1, -1):
        if dates[i].year == yr:
            return closes[i]
        if dates[i].year < yr:
            break
    return None

def _pos_in_range(price: float, low: float, high: float) -> float:
    try:
        if high <= low: return 50.0
        v = (price - low) / (high - low) * 100.0
        return max(0.0, min(100.0, v))
    except Exception:
        return 50.0

def compute_metrics(symbol: str) -> Dict[str, Any]:
    provider, dates, closes = get_daily_history(symbol)
    # sleep a bit only when we hit Stooq repeatedly (be nice); yfinance handles its own pacing
    if provider == "stooq":
        time.sleep(1.0)

    latest = closes[-1] if closes else None
    d1 = _nearest(closes, 1)
    w1 = _nearest(closes, 5)
    m1 = _nearest(closes, 21)
    y0 = _ytd_ref(dates, closes)

    p1d = _pct(latest, d1)
    p1w = _pct(latest, w1)
    p1m = _pct(latest, m1)
    pytd = _pct(latest, y0)

    window = closes[-252:] if len(closes) >= 252 else closes
    low52 = min(window) if window else 0.0
    high52 = max(window) if window else 0.0
    range_pct = _pos_in_range(latest or 0.0, low52, high52)

    return {
        "provider": provider,
        "bars": len(closes),
        "price": latest or 0.0,
        "pct_1d": p1d, "pct_1w": p1w, "pct_1m": p1m, "pct_ytd": pytd,
        "low_52w": float(low52), "high_52w": float(high52), "range_pct": float(range_pct),
        "closes": closes  # for sparkline
    }
