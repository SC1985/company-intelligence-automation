from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import json
import time
from urllib.request import urlopen
from urllib.parse import urlencode

from render_email import render_email
from chartgen import sparkline_png_base64

def _to_float(x: Any, percent: bool=False) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
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
    # k_back=1 => previous bar, assuming closes sorted ASC (old->new)
    if not closes: return None
    idx = len(closes) - 1 - k_back
    if 0 <= idx < len(closes):
        return closes[idx]
    return None

def _ytd_ref(dates: List[datetime], closes: List[float]) -> Optional[float]:
    if not dates or not closes: return None
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
        return max(0.0, min(100.0, (price-low)/(high-low)*100.0))
    except Exception:
        return 50.0

def _extract_series_from_engine(item: Dict[str, Any]) -> Tuple[List[datetime], List[float]]:
    # Try common shapes your engine might expose
    dt, cl = [], []
    try:
        # Pattern A: {'series': [{'date': 'YYYY-MM-DD', 'close': 123.4}, ...]}
        if "series" in item and isinstance(item["series"], list):
            for row in item["series"][-400:]:
                d = row.get("date") or row.get("time") or row.get("timestamp")
                c = row.get("close") or row.get("price") or row.get("adjusted_close")
                if d and c is not None:
                    try:
                        if isinstance(d, str):
                            d = datetime.fromisoformat(d.replace("Z",""))
                        elif isinstance(d, (int, float)):
                            d = datetime.fromtimestamp(d)
                        dt.append(d); cl.append(float(c))
                    except Exception:
                        continue
        # Pattern B: {'timeseries': {'date': [...], 'close': [...]}}
        elif "timeseries" in item and isinstance(item["timeseries"], dict):
            dlist = item["timeseries"].get("date") or item["timeseries"].get("dates")
            clist = item["timeseries"].get("close") or item["timeseries"].get("closes")
            if isinstance(dlist, list) and isinstance(clist, list) and len(dlist)==len(clist):
                for d, c in zip(dlist[-400:], clist[-400:]):
                    try:
                        if isinstance(d, str):
                            d = datetime.fromisoformat(d.replace("Z",""))
                        elif isinstance(d, (int,float)):
                            d = datetime.fromtimestamp(d)
                        dt.append(d); cl.append(float(c))
                    except Exception:
                        continue
    except Exception:
        pass
    return dt, cl

def _fetch_daily_series_av(symbol: str, api_key: Optional[str], logger) -> Tuple[List[datetime], List[float]]:
    if not api_key:
        return [], []
    try:
        qs = urlencode({
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "full",  # ensure 52w span
            "datatype": "json",
            "apikey": api_key
        })
        url = f"https://www.alphavantage.co/query?{qs}"
        with urlopen(url, timeout=25) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
        if "Note" in data or "Error Message" in data:
            logger.warning(f"AV note/error for {symbol}: {data.get('Note') or data.get('Error Message')}")
            return [], []
        ts = data.get("Time Series (Daily)") or {}
        if not isinstance(ts, dict) or not ts:
            logger.warning(f"AV empty timeseries for {symbol}")
            return [], []
        keys = sorted(ts.keys())  # ascending
        dt, cl = [], []
        for k in keys[-400:]:  # last ~400 days
            row = ts.get(k) or {}
            ac = row.get("5. adjusted close") or row.get("4. close")
            if ac is None: 
                continue
            try:
                dt.append(datetime.fromisoformat(k))
                cl.append(float(str(ac).replace(',', '')))
            except Exception:
                continue
        logger.info(f"AV history {symbol}: {len(cl)} bars")
        return dt, cl
    except Exception as e:
        logger.warning(f"AV fetch exception for {symbol}: {e}")
        return [], []

def _pick_headline(news_bucket: Dict[str, Any]) -> Dict[str, Optional[str]]:
    if not isinstance(news_bucket, dict):
        return {}
    arts = news_bucket.get("top_articles") or []
    if not arts: return {}
    a = arts[0]
    title = a.get("title")
    src = a.get("source",{}).get("name") if isinstance(a.get("source"), dict) else None
    when = a.get("publishedAt") or a.get("published_at")
    return {"title": title, "source": src, "when": when}

async def build_nextgen_html(logger) -> str:
    from main import StrategicIntelligenceEngine
    engine = StrategicIntelligenceEngine()

    logger.info("NextGen: collecting market/news from engine")
    market = await engine._harvest_constellation_data()
    news = await engine._synthesize_strategic_news()
    api_key = __import__("os").getenv("ALPHA_VANTAGE_API_KEY")

    companies: List[Dict[str, Any]] = []
    up = down = 0
    movers: List[Dict[str, Any]] = []

    if isinstance(market, dict):
        for ticker, item in market.items():
            t = str(ticker).upper()

            # Company meta
            meta = item.get("position_data") or item.get("meta") or {}
            name = meta.get("name") or meta.get("companyName") or t

            # Spot/current fields (GLOBAL_QUOTE-like)
            price = _to_float(item.get("price"))
            change = _to_float(item.get("change"))
            change_pct = _to_float(item.get("change_percent"), percent=True)
            p1d = change_pct
            if p1d is None and price is not None and change is not None:
                prev = price - change
                p1d = _pct_change(price, prev)

            # Try series from engine first
            dates, closes = _extract_series_from_engine(item)

            # If no series, pull from Alpha Vantage
            if not closes:
                dts, cls = _fetch_daily_series_av(t, api_key, logger)
                dates, closes = dts, cls
                # rate-limit to 5/min free tier
                if closes:
                    time.sleep(12)

            # Compute multi-window returns + 52w
            p1w = p1m = pytd = None
            low52 = high52 = 0.0
            pos_pct = 50.0
            price_show = price if price is not None else (closes[-1] if closes else 0.0)

            if closes:
                last_close = closes[-1]
                base = price_show if price_show is not None else last_close

                d1 = _nearest(closes, 1)
                w1 = _nearest(closes, 5)
                m1 = _nearest(closes, 21)
                ytd0 = _ytd_ref(dates, closes) if dates else None

                if d1 is not None:
                    p1d = _pct_change(base, d1)  # recompute on close basis

                p1w = _pct_change(base, w1)
                p1m = _pct_change(base, m1)
                pytd = _pct_change(base, ytd0)

                # 52w bounds prefer last ~252 trading days if available
                window = closes[-252:] if len(closes) >= 252 else closes
                low52 = min(window); high52 = max(window)
                pos_pct = _pos_in_range(base, low52, high52)

            spark_b64 = sparkline_png_base64(closes[-21:] if closes else [])

            # One headline per ticker (from engine's bucketed news)
            headline = {}
            if isinstance(news, dict) and t in news:
                headline = _pick_headline(news[t])

            if p1d is not None:
                if p1d >= 0: up += 1
                else: down += 1
                movers.append({"ticker": t, "pct": p1d})

            companies.append({
                "name": name, "ticker": t, "price": price_show or 0.0,
                "pct_1d": p1d, "pct_1w": p1w, "pct_1m": p1m, "pct_ytd": pytd,
                "low_52w": low52 or 0.0, "high_52w": high52 or 0.0,
                "range_pct": pos_pct, "spark_b64": spark_b64,
                "headline": headline.get("title"), "source": headline.get("source"), "when": headline.get("when"),
                "next_event": meta.get("earningsDate") or meta.get("nextEvent"),
                "vol_x_avg": None
            })

    winners = sorted([m for m in movers if m["pct"] is not None], key=lambda x: x["pct"], reverse=True)[:3]
    losers  = sorted([m for m in movers if m["pct"] is not None], key=lambda x: x["pct"])[:3]

    summary = {
        "as_of_ct": datetime.now().strftime("%b %d, %Y %H:%M CT"),
        "up_count": up, "down_count": down,
        "top_winners": winners, "top_losers": losers
    }

    html = render_email(summary, companies)
    return html
