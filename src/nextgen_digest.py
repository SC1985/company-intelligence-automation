from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from render_email import render_email
from chartgen import sparkline_png_base64

import os
import asyncio

def _to_float(x: Any, percent: bool=False) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x) if not percent else float(x)
        s = str(x).strip()
        if percent and s.endswith('%'):
            s = s[:-1]
        s = s.replace(',', '')
        return float(s)
    except Exception:
        return None

def _pct_change(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    try:
        if curr is None or prev is None or prev == 0:
            return None
        return (curr/prev - 1.0) * 100.0
    except Exception:
        return None

def _nearest(closes: List[float], k_back: int) -> Optional[float]:
    # k_back=1 means previous bar; our series is ASC sorted (old->new)
    if not closes: return None
    idx = len(closes) - 1 - k_back
    if idx < 0 or idx >= len(closes):
        return None
    return closes[idx]

def _ytd_ref(dates: List[datetime], closes: List[float]) -> Optional[float]:
    if not dates or not closes: return None
    # last trading day of previous year
    target_year = dates[-1].year - 1
    for i in range(len(dates)-1, -1, -1):
        if dates[i].year == target_year:
            return closes[i]
        if dates[i].year < target_year:
            break
    return None

def _pos_in_range(price, low, high) -> float:
    try:
        price, low, high = float(price), float(low), float(high)
        if high <= low: return 50.0
        v = (price - low) / (high - low) * 100.0
        return max(0.0, min(100.0, v))
    except Exception:
        return 50.0

async def _fetch_daily_series(symbol: str, api_key: Optional[str], logger) -> Tuple[List[datetime], List[float]]:
    # Use Alpha Vantage TIME_SERIES_DAILY_ADJUSTED for recent history
    if not api_key:
        return [], []
    import aiohttp
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": symbol,
        "outputsize": "compact",  # ~100 bars
        "apikey": api_key
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.warning(f"History fetch failed for {symbol}: HTTP {resp.status}")
                    return [], []
                data = await resp.json()
        ts = data.get("Time Series (Daily)") or {}
        if not isinstance(ts, dict) or not ts:
            logger.warning(f"History missing for {symbol}: unexpected payload")
            return [], []
        # sort by date ASC
        keys = sorted(ts.keys())
        dt, cl = [], []
        for d in keys:
            row = ts[d] or {}
            ac = row.get("5. adjusted close") or row.get("4. close")
            try:
                if ac is not None:
                    # AlphaVantage dates are like "2025-08-19"
                    dt.append(datetime.fromisoformat(d))
                    cl.append(float(str(ac).replace(',', '')))
            except Exception:
                continue
        return dt, cl
    except Exception as e:
        logger.warning(f"History exception for {symbol}: {e}")
        return [], []

def _pick_news(news_for_symbol: Dict[str, Any]) -> Dict[str, Optional[str]]:
    # Your engine returns: {'article_count': n, 'top_articles': [...], 'sentiment': {...}}
    if not isinstance(news_for_symbol, dict):
        return {}
    arts = news_for_symbol.get("top_articles") or []
    if not arts:
        return {}
    a = arts[0]
    title = a.get("title")
    src = None
    src_obj = a.get("source")
    if isinstance(src_obj, dict):
        src = src_obj.get("name") or src_obj.get("id")
    when = a.get("publishedAt") or a.get("published_at")
    return {"title": title, "source": src, "when": when}

async def build_nextgen_html(logger) -> str:
    # Use the project's engine
    from main import StrategicIntelligenceEngine
    engine = StrategicIntelligenceEngine()

    logger.info("NextGen: collecting market/news from engine")
    market = await engine._harvest_constellation_data()
    news = await engine._synthesize_strategic_news()

    alpha_key = os.getenv("ALPHA_VANTAGE_API_KEY")

    companies = []
    up = down = 0
    movers = []  # for winners/losers (by 1D)

    # For each ticker returned by engine
    if isinstance(market, dict):
        for ticker, item in market.items():
            t = ticker.upper()
            meta = item.get("position_data") or {}
            name = meta.get("name") or t

            # Map the engine's GLOBAL_QUOTE fields
            price = _to_float(item.get("price"))
            change = _to_float(item.get("change"))
            change_pct = _to_float(item.get("change_percent"), percent=True)

            # 1D can come from change_percent; fallback compute from change
            p1d = change_pct
            if p1d is None and price is not None and change is not None:
                prev = price - change
                p1d = _pct_change(price, prev)

            # Try to enrich with daily history for 1W/1M/YTD, sparkline, 52w
            dates, closes = await _fetch_daily_series(t, alpha_key, logger)
            if dates and closes:
                latest_close = closes[-1]
                # Use market spot price if available; otherwise last close
                last = price if price is not None else latest_close

                # 1W ≈ last vs 5 trading days back; 1M ≈ 21 trading days back
                d1 = _nearest(closes, 1)  # previous trading day close
                w1 = _nearest(closes, 5)
                m1 = _nearest(closes, 21)
                ytd0 = _ytd_ref(dates, closes)

                # If market "price" is live and differs significantly, prefer historical last close for stability
                base = latest_close if latest_close is not None else last

                # recompute 1D from closes if available
                if base is not None and d1 is not None:
                    p1d = _pct_change(base, d1)

                p1w = _pct_change(base, w1)
                p1m = _pct_change(base, m1)
                pytd = _pct_change(base, ytd0)
                low52 = min(closes[-252:]) if len(closes) >= 252 else min(closes)
                high52 = max(closes[-252:]) if len(closes) >= 252 else max(closes)
                pos_pct = _pos_in_range(base or 0.0, low52, high52)
                spark_b64 = sparkline_png_base64(closes[-21:])
                price_show = base
            else:
                # No history: show price + 1D only; omit others
                p1w = p1m = pytd = None
                low52 = high52 = 0.0
                pos_pct = 50.0
                spark_b64 = None
                price_show = price if price is not None else 0.0

            # Count breadth & collect movers
            if p1d is not None:
                if p1d >= 0: up += 1
                else: down += 1
                movers.append({"ticker": t, "pct": p1d})

            # Pull one headline from your engine's news shape
            h = {}
            if isinstance(news, dict) and t in news:
                h = _pick_news(news.get(t))

            companies.append({
                "name": name, "ticker": t, "price": price_show or 0.0,
                "pct_1d": p1d, "pct_1w": p1w, "pct_1m": p1m, "pct_ytd": pytd,
                "low_52w": low52 or 0.0, "high_52w": high52 or 0.0,
                "range_pct": pos_pct, "spark_b64": spark_b64,
                "headline": h.get("title"), "source": h.get("source"), "when": h.get("when"),
                "next_event": meta.get("earningsDate") or meta.get("nextEvent"),
                "vol_x_avg": None
            })

            # Respect AlphaVantage rate limit when history is used (5 req/min on free tier)
            if dates and closes:
                await asyncio.sleep(12)

    winners = sorted([m for m in movers if m["pct"] is not None], key=lambda x: x["pct"], reverse=True)[:3]
    losers  = sorted([m for m in movers if m["pct"] is not None], key=lambda x: x["pct"])[:3]

    summary = {
        "as_of_ct": datetime.now().strftime("%b %d, %Y %H:%M CT"),
        "up_count": up, "down_count": down,
        "top_winners": winners, "top_losers": losers
    }

    html = render_email(summary, companies)
    return html
