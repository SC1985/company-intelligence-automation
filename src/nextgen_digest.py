from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import json
import time

from render_email import render_email

# ---------------- History helpers (no external deps required) ----------------

def _fetch_stooq(symbol: str) -> Tuple[List[datetime], List[float], List[float], List[float]]:
    """Fetch daily OHLC from Stooq CSV.
    Returns (dates, closes, highs, lows). May return empty lists if not found.
    """
    import csv
    from urllib.request import urlopen

    candidates = [
        symbol.lower(),
        f"{symbol.lower()}.us",
    ]
    for s in candidates:
        try:
            url = f"https://stooq.com/q/d/l/?s={s}&i=d"
            with urlopen(url, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            # Guard: some bad responses are short or HTML
            if not raw or "<html" in raw.lower():
                continue
            dt, cl, hi, lo = [], [], [], []
            reader = csv.DictReader(raw.splitlines())
            for row in reader:
                if not row.get("Date") or not row.get("Close"):
                    continue
                try:
                    d = datetime.fromisoformat(row["Date"])  # YYYY-MM-DD
                    c = float(row["Close"].replace(",", ""))
                    h = float(row.get("High", c))
                    l = float(row.get("Low", c))
                except Exception:
                    continue
                dt.append(d); cl.append(c); hi.append(h); lo.append(l)
            if len(cl) >= 30:
                return dt, cl, hi, lo
        except Exception:
            continue
    return [], [], [], []

def _fetch_alpha_vantage(symbol: str, api_key: Optional[str]) -> Tuple[List[datetime], List[float], List[float], List[float]]:
    if not api_key:
        return [], [], [], []
    from urllib.request import urlopen
    from urllib.parse import urlencode
    try:
        qs = urlencode({
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "full",
            "datatype": "json",
            "apikey": api_key
        })
        url = f"https://www.alphavantage.co/query?{qs}"
        with urlopen(url, timeout=25) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
        ts = data.get("Time Series (Daily)") or {}
        if not isinstance(ts, dict) or not ts:
            return [], [], [], []
        keys = sorted(ts.keys())  # ASC
        dt, cl, hi, lo = [], [], [], []
        for k in keys[-500:]:
            row = ts.get(k) or {}
            ac = row.get("5. adjusted close") or row.get("4. close")
            h = row.get("2. high")
            l = row.get("3. low")
            if ac is None:
                continue
            try:
                dt.append(datetime.fromisoformat(k))
                cl.append(float(str(ac).replace(",", "")))
                hi.append(float(str(h).replace(",", "")) if h is not None else cl[-1])
                lo.append(float(str(l).replace(",", "")) if l is not None else cl[-1])
            except Exception:
                continue
        # Respect free tier
        if cl:
            time.sleep(12)
        return dt, cl, hi, lo
    except Exception:
        return [], [], [], []

def _get_history(symbol: str, api_key: Optional[str]) -> Tuple[str, List[datetime], List[float], List[float], List[float]]:
    # Prefer Stooq (fast, no key). If insufficient, fall back to Alpha Vantage.
    dt, cl, hi, lo = _fetch_stooq(symbol)
    if len(cl) >= 30:
        return "stooq", dt, cl, hi, lo
    dt, cl, hi, lo = _fetch_alpha_vantage(symbol, api_key)
    if len(cl) >= 30:
        return "alphavantage", dt, cl, hi, lo
    # Last resort: nothing
    return "none", [], [], [], []

# ---------------- Analytics helpers ----------------

def _pct_change(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    try:
        if curr is None or prev is None or prev == 0:
            return None
        return (curr / prev - 1.0) * 100.0
    except Exception:
        return None

def _nearest(closes: List[float], k_back: int) -> Optional[float]:
    if not closes:
        return None
    idx = len(closes) - 1 - k_back
    if 0 <= idx < len(closes):
        return closes[idx]
    return None

def _ytd_ref(dates: List[datetime], closes: List[float]) -> Optional[float]:
    if not dates or not closes:
        return None
    target_year = dates[-1].year - 1
    for i in range(len(dates) - 1, -1, -1):
        if dates[i].year == target_year:
            return closes[i]
        if dates[i].year < target_year:
            break
    return None

def _pos_in_range(price, low, high) -> float:
    try:
        price, low, high = float(price), float(low), float(high)
        if high <= low:
            return 50.0
        return max(0.0, min(100.0, (price - low) / (high - low) * 100.0))
    except Exception:
        return 50.0

def _first_url_from_item(a: Dict[str, Any], ticker: str) -> Optional[str]:
    for k in ("url", "link", "article_url", "story_url", "source_url", "canonicalUrl"):
        v = a.get(k)
        if isinstance(v, str) and v.startswith(("http://", "https://")):
            return v
    for k in ("source", "meta"):
        obj = a.get(k)
        if isinstance(obj, dict):
            v = obj.get("url") or obj.get("link")
            if isinstance(v, str) and v.startswith(("http://", "https://")):
                return v
    return f"https://finance.yahoo.com/quote/{ticker}/news"

def _coalesce_news_map(news: Any) -> Dict[str, Dict[str, Optional[str]]]:
    out: Dict[str, Dict[str, Optional[str]]] = {}
    if isinstance(news, dict):
        for k, v in news.items():
            t = str(k).upper()
            arts = []
            if isinstance(v, dict):
                arts = v.get("top_articles") or v.get("articles") or v.get("items") or []
            elif isinstance(v, list):
                arts = v
            if isinstance(arts, list) and arts:
                a = arts[0]
                title = a.get("title") or a.get("headline")
                src = a.get("source")
                if isinstance(src, dict):
                    src = src.get("name") or src.get("id") or src.get("domain")
                when = a.get("publishedAt") or a.get("published_at") or a.get("time")
                url = _first_url_from_item(a, t)
                out[t] = {"title": title, "source": src if isinstance(src, str) else None, "when": when, "url": url}
        items = news.get("items") or news.get("results") or []
        if isinstance(items, list):
            for a in items:
                t = a.get("ticker") or a.get("symbol") or (a.get("company", {}) or {}).get("ticker")
                if not t:
                    continue
                t = str(t).upper()
                if t in out:
                    continue
                title = a.get("title") or a.get("headline")
                src = a.get("source") or a.get("domain")
                if isinstance(src, dict):
                    src = src.get("name") or src.get("id") or src.get("domain")
                when = a.get("publishedAt") or a.get("published_at") or a.get("time")
                url = _first_url_from_item(a, t)
                out[t] = {"title": title, "source": src if isinstance(src, str) else None, "when": when, "url": url}
    return out

def _parse_catalyst(meta: Dict[str, Any]) -> Optional[Dict[str, str]]:
    label = None
    date_str = None

    ed = meta.get("earningsDate")
    if isinstance(ed, list) and ed:
        x = ed[0]
        if isinstance(x, dict) and x.get("fmt"):
            date_str = x["fmt"]; label = "Earnings"
        elif isinstance(x, str):
            date_str = x; label = "Earnings"
    elif isinstance(ed, dict) and ed.get("fmt"):
        date_str = ed["fmt"]; label = "Earnings"
    elif isinstance(ed, str):
        date_str = ed; label = "Earnings"

    ne = meta.get("nextEvent") or meta.get("next_event")
    if not date_str and isinstance(ne, dict):
        ds = ne.get("date") or ne.get("when") or ne.get("time")
        if isinstance(ds, str):
            date_str = ds
        label = ne.get("label") or ne.get("name") or "Event"
    elif not date_str and isinstance(ne, str):
        parts = ne.split()
        for p in parts:
            if len(p) >= 10 and p[4:5] == "-" and p[7:8] == "-":
                date_str = p
                label = ne.replace(p, "").strip() or "Event"
                break

    if not (date_str and label):
        return None
    return {"date_str": str(date_str), "label": str(label)}

# ---------------- Main builder ----------------

async def build_nextgen_html(logger) -> str:
    from main import StrategicIntelligenceEngine
    engine = StrategicIntelligenceEngine()

    logger.info("NextGen: collecting market/news from engine")
    market = await engine._harvest_constellation_data()
    news = await engine._synthesize_strategic_news()
    news_map = _coalesce_news_map(news)

    alpha_key = __import__("os").getenv("ALPHA_VANTAGE_API_KEY") or None

    companies: List[Dict[str, Any]] = []
    up = down = 0
    movers: List[Dict[str, Any]] = []

    if isinstance(market, dict):
        for ticker, item in market.items():
            t = str(ticker).upper()
            meta = item.get("position_data") or item.get("meta") or {}
            name = meta.get("name") or meta.get("companyName") or t

            # Spot/series from engine if it exists
            price = None
            try:
                price = float(item.get("price")) if item.get("price") is not None else None
            except Exception:
                price = None

            closes = [float(x) for x in item.get("closes", [])] if isinstance(item.get("closes"), list) else []
            dates = item.get("dates", []) or []

            hist_source = "engine" if len(closes) >= 30 else None
            if len(closes) < 30:
                # Fetch robust history for multi-window returns + 52w
                src, dt, cl, hi, lo = _get_history(t, alpha_key)
                if cl:
                    closes = cl
                    dates = dt
                    hist_source = src
                else:
                    hist_source = "none"

            latest = closes[-1] if closes else price

            # Window baselines: prev day, ~5d, ~21d, YTD
            d1 = _nearest(closes, 1) if closes else None
            w1 = _nearest(closes, 5) if closes else None
            m1 = _nearest(closes, 21) if closes else None
            ytd0 = _ytd_ref(dates, closes) if dates and closes else None

            p1d = _pct_change(latest, d1) if d1 is not None else None
            p1w = _pct_change(latest, w1) if w1 is not None else None
            p1m = _pct_change(latest, m1) if m1 is not None else None
            pytd = _pct_change(latest, ytd0) if ytd0 is not None else None

            if p1d is not None:
                if p1d >= 0: up += 1
                else: down += 1
                movers.append({"ticker": t, "pct": p1d})

            # 52w bounds
            low52 = item.get("low_52w"); high52 = item.get("high_52w")
            try:
                low52 = float(low52) if low52 is not None else None
                high52 = float(high52) if high52 is not None else None
            except Exception:
                low52 = high52 = None

            if (low52 is None or high52 is None) and closes:
                window = closes[-252:] if len(closes) >= 252 else closes
                low52 = float(min(window))
                high52 = float(max(window))

            range_pct = _pos_in_range(latest or 0.0, low52 or 0.0, high52 or 0.0)

            nm = news_map.get(t, {})
            news_url = nm.get("url") or f"https://finance.yahoo.com/quote/{t}/news"
            pr_url = f"https://finance.yahoo.com/quote/{t}/press-releases"

            # Prefer showing live price if present, else last close
            price_show = price if price is not None else (latest or 0.0)

            companies.append({
                "name": name, "ticker": t, "price": price_show or 0.0,
                "pct_1d": p1d, "pct_1w": p1w, "pct_1m": p1m, "pct_ytd": pytd,
                "low_52w": (low52 or 0.0), "high_52w": (high52 or 0.0),
                "range_pct": range_pct,
                "headline": nm.get("title"), "source": nm.get("source"), "when": nm.get("when"),
                "next_event": meta.get("earningsDate") or meta.get("nextEvent"),
                "vol_x_avg": item.get("volume_x_30d") or item.get("volXAvg"),
                "news_url": news_url, "pr_url": pr_url,
            })

            # Log per-symbol history source/bars for troubleshooting
            try:
                import logging
                logging.getLogger("ci-entrypoint").info(f"{t}: history={hist_source} bars={len(closes)} price={'%.2f' % (price_show or 0)}")
            except Exception:
                pass

    # Top movers
    winners = sorted([m for m in movers if m["pct"] is not None], key=lambda x: x["pct"], reverse=True)[:3]
    losers  = sorted([m for m in movers if m["pct"] is not None], key=lambda x: x["pct"])[:3]

    # Catalysts (7 days) — best-effort from meta
    catalysts: List[Dict[str, str]] = []
    now = datetime.now()
    horizon = now + timedelta(days=7)
    for c in companies:
        ne = c.get("next_event")
        if not ne:
            continue
        # Wrap into meta-like structure for parser
        meta = {"nextEvent": ne} if not isinstance(ne, dict) else ne
        meta = {"nextEvent": meta} if "date" in meta or "when" in meta else meta
        parsed = _parse_catalyst({"nextEvent": meta} if not isinstance(meta, dict) else meta)
        if not parsed:
            continue
        ds = str(parsed["date_str"]).strip()
        dt = None
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%b %d, %Y", "%d %b %Y"):
            try:
                dt = datetime.strptime(ds[:19], fmt)
                break
            except Exception:
                continue
        if dt is None and len(ds) >= 10 and ds[4:5] == "-" and ds[7:8] == "-":
            try:
                dt = datetime.strptime(ds[:10], "%Y-%m-%d")
            except Exception:
                pass
        if dt and now <= dt <= horizon:
            catalysts.append({"date_str": dt.strftime("%b %d"), "ticker": c["ticker"], "label": parsed["label"]})
    catalysts = sorted(catalysts, key=lambda x: x["date_str"])[:8]

    summary = {
        "as_of_ct": datetime.now().strftime("%b %d, %Y %H:%M CT"),
        "up_count": up, "down_count": down,
        "top_winners": winners, "top_losers": losers,
        "catalysts": catalysts,
    }

    html = render_email(summary, companies, catalysts=catalysts)
    return html
