from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import json, os, time

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from render_email import render_email

CENTRAL_TZ = ZoneInfo("America/Chicago") if ZoneInfo else None

# -------------------- Load entities --------------------

def _load_entities() -> List[Dict[str, Any]]:
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.normpath(os.path.join(here, "..", "data", "companies.json"))
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    items: List[Dict[str, Any]] = []
    for key in ("equities", "companies", "digital_assets", "assets", "items"):
        arr = data.get(key)
        if isinstance(arr, list):
            items.extend(arr)
    if not items:
        raise ValueError("companies.json did not contain a recognized list of entities")
    return items

# -------------------- HTTP helpers --------------------

def _http_get_json(url: str, timeout: float = 25.0) -> Optional[Dict[str, Any]]:
    try:
        from urllib.request import urlopen, Request
        req = Request(url, headers={"User-Agent": "ci-digest/1.0 (+https://example.local)"})
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return None

# -------------------- History helpers (equities) --------------------

def _fetch_stooq(symbol: str) -> Tuple[List[datetime], List[float]]:
    import csv
    from urllib.request import urlopen
    candidates = [symbol.lower(), f"{symbol.lower()}.us"]
    for s in candidates:
        try:
            url = f"https://stooq.com/q/d/l/?s={s}&i=d"
            with urlopen(url, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            if not raw or "<html" in raw.lower():
                continue
            dt, cl = [], []
            for row in csv.DictReader(raw.splitlines()):
                ds = row.get("Date"); cs = row.get("Close")
                if not ds or not cs:
                    continue
                try:
                    d = datetime.fromisoformat(ds)
                    c = float(cs.replace(",", ""))
                except Exception:
                    continue
                dt.append(d); cl.append(c)
            if len(cl) >= 30:
                return dt, cl
        except Exception:
            continue
    return [], []

def _fetch_alpha_vantage_equity(symbol: str, api_key: Optional[str]) -> Tuple[List[datetime], List[float]]:
    if not api_key:
        return [], []
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
            return [], []
        keys = sorted(ts.keys())
        dt, cl = [], []
        for k in keys[-500:]:
            row = ts.get(k) or {}
            ac = row.get("5. adjusted close") or row.get("4. close")
            if ac is None:
                continue
            try:
                dt.append(datetime.fromisoformat(k))
                cl.append(float(str(ac).replace(",", "")))
            except Exception:
                continue
        if cl:
            time.sleep(12)  # free-tier pacing
        return dt, cl
    except Exception:
        return [], []

def _get_equity_series(symbol: str, alpha_key: Optional[str]) -> Tuple[str, List[datetime], List[float]]:
    dt, cl = _fetch_stooq(symbol)
    if len(cl) >= 30:
        return "stooq", dt, cl
    dt, cl = _fetch_alpha_vantage_equity(symbol, alpha_key)
    if len(cl) >= 30:
        return "alphavantage", dt, cl
    return "none", [], []

# -------------------- History helpers (crypto) --------------------

# CoinGecko IDs; can be overridden by companies.json field "coingecko_id"
COINGECKO_IDS = {
    "BTC-USD": "bitcoin",
    "ETH-USD": "ethereum",
    "DOGE-USD": "dogecoin",
    "XRP-USD": "ripple",
}

def _fetch_coingecko_crypto(symbol_usd: str, id_hint: Optional[str] = None) -> Tuple[List[datetime], List[float]]:
    # Returns daily closes (UTC) for up to ~400 days
    cid = (id_hint or COINGECKO_IDS.get(symbol_usd) or symbol_usd.replace("-USD", "").lower())
    url = f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart?vs_currency=usd&days=400"
    data = _http_get_json(url)
    if not data or "prices" not in data:
        return [], []
    dt, cl = [], []
    for ts, price in data.get("prices", []):
        try:
            d = datetime.utcfromtimestamp(float(ts) / 1000.0)
            p = float(price)
        except Exception:
            continue
        dt.append(d); cl.append(p)
    return dt, cl

def _fetch_alpha_vantage_crypto(symbol_usd: str, alpha_key: Optional[str]) -> Tuple[List[datetime], List[float]]:
    if not alpha_key:
        return [], []
    from urllib.request import urlopen
    from urllib.parse import urlencode
    try:
        symbol = symbol_usd.replace("-USD", "")
        qs = urlencode({
            "function": "DIGITAL_CURRENCY_DAILY",
            "symbol": symbol,
            "market": "USD",
            "datatype": "json",
            "apikey": alpha_key
        })
        url = f"https://www.alphavantage.co/query?{qs}"
        with urlopen(url, timeout=25) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
        ts = data.get("Time Series (Digital Currency Daily)") or {}
        if not isinstance(ts, dict) or not ts:
            return [], []
        keys = sorted(ts.keys())
        dt, cl = [], []
        for k in keys[-500:]:
            row = ts.get(k) or {}
            close = row.get("4a. close (USD)") or row.get("4b. close (USD)") or row.get("4a. close (usd)")
            if close is None:
                continue
            try:
                dt.append(datetime.fromisoformat(k))
                cl.append(float(str(close).replace(",", "")))
            except Exception:
                continue
        if cl:
            time.sleep(12)
        return dt, cl
    except Exception:
        return [], []

# -------------------- Math helpers --------------------

def _pct(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    try:
        if curr is None or prev is None or prev == 0:
            return None
        return (curr/prev - 1.0) * 100.0
    except Exception:
        return None

def _pos_in_range(price, low, high) -> float:
    try:
        price, low, high = float(price), float(low), float(high)
        if high <= low:
            return 50.0
        return max(0.0, min(100.0, (price - low)/(high - low)*100.0))
    except Exception:
        return 50.0

def _nearest(series: List[float], k_back: int) -> Optional[float]:
    if not series:
        return None
    idx = len(series) - 1 - k_back
    if 0 <= idx < len(series):
        return series[idx]
    return None

# -------------------- Main builder --------------------

async def build_nextgen_html(logger) -> str:
    # Attempt engine-provided news (optional)
    try:
        from main import StrategicIntelligenceEngine
        engine = StrategicIntelligenceEngine()
        logger.info("NextGen: news synthesis via engine")
        news = await engine._synthesize_strategic_news()
    except Exception:
        news = {}

    alpha_key = os.getenv("ALPHA_VANTAGE_API_KEY") or None
    entities = _load_entities()

    companies: List[Dict[str, Any]] = []
    cryptos:   List[Dict[str, Any]] = []
    up = down = 0
    movers: List[Dict[str, Any]] = []

    def _news_url_for(t: str) -> str:
        return f"https://finance.yahoo.com/quote/{t}/news"

    # Pace crypto calls to be friendly to providers
    last_call_ts = 0.0
    def _pace(min_interval=2.0):
        nonlocal last_call_ts
        now = time.time()
        delta = now - last_call_ts
        if delta < min_interval:
            time.sleep(min_interval - delta)
        last_call_ts = time.time()

    # Build lists
    for e in entities:
        sym = str(e.get("symbol") or "").upper()
        if not sym:
            continue
        name = e.get("name") or sym
        is_crypto = (e.get("asset_class","").lower() == "crypto") or sym.endswith("-USD")

        if is_crypto:
            # Try CoinGecko first (no key), then Alpha Vantage, else placeholder
            cid = e.get("coingecko_id")
            _pace(2.0)
            dt, cl = _fetch_coingecko_crypto(sym, id_hint=cid)
            provider = "coingecko" if cl else None

            if not cl:
                _pace(15.0)  # AV free-tier pacing
                dt, cl = _fetch_alpha_vantage_crypto(sym, alpha_key)
                provider = "alphavantage" if cl else None

            if cl:
                latest = cl[-1]
                d1 = _nearest(cl, 1)
                w1 = _nearest(cl, 7)
                m1 = _nearest(cl, 30)
                window = cl[-365:] if len(cl) >= 365 else cl
                low52, high52 = float(min(window)), float(max(window))
                range_pct = _pos_in_range(latest, low52, high52)
                # YTD baseline = last close of previous year
                pytd = None
                if dt:
                    last_year = dt[-1].year - 1
                    for i in range(len(dt)-1, -1, -1):
                        if dt[i].year == last_year:
                            pytd = _pct(latest, cl[i]); break

                cryptos.append({
                    "name": name, "ticker": sym, "price": latest,
                    "pct_1d": _pct(latest, d1), "pct_1w": _pct(latest, w1),
                    "pct_1m": _pct(latest, m1), "pct_ytd": pytd,
                    "low_52w": low52, "high_52w": high52, "range_pct": range_pct,
                    "headline": None, "source": None, "when": None,
                    "next_event": None, "vol_x_avg": None,
                    "news_url": _news_url_for(sym),
                    "pr_url": {
                        "BTC-USD":"https://bitcoin.org",
                        "ETH-USD":"https://blog.ethereum.org",
                        "DOGE-USD":"https://blog.dogecoin.com",
                        "XRP-USD":"https://ripple.com/insights/"
                    }.get(sym, _news_url_for(sym)),
                })
                try:
                    import logging
                    logging.getLogger("ci-entrypoint").info(f"{sym}: crypto provider={provider} bars={len(cl)} last={latest:.6f} pos%={range_pct:.2f}")
                except Exception:
                    pass
            else:
                # Still render a card so section remains visible
                cryptos.append({
                    "name": name, "ticker": sym, "price": 0.0,
                    "pct_1d": None, "pct_1w": None, "pct_1m": None, "pct_ytd": None,
                    "low_52w": 0.0, "high_52w": 0.0, "range_pct": 50.0,
                    "headline": None, "source": None, "when": None,
                    "next_event": None, "vol_x_avg": None,
                    "news_url": _news_url_for(sym),
                    "pr_url": _news_url_for(sym),
                })
                try:
                    import logging
                    logging.getLogger("ci-entrypoint").warning(f"{sym}: crypto providers unavailable – rendering placeholder")
                except Exception:
                    pass
            continue

        # ---- Equities ----
        src, dt, cl = _get_equity_series(sym, alpha_key)
        if not cl:
            try:
                import logging
                logging.getLogger("ci-entrypoint").warning(f"{sym}: equity history unavailable – skipped")
            except Exception:
                pass
            continue
        latest = cl[-1]
        d1 = cl[-2] if len(cl) >= 2 else None
        w1 = cl[-6] if len(cl) >= 6 else None
        m1 = cl[-22] if len(cl) >= 22 else None
        window = cl[-252:] if len(cl) >= 252 else cl
        low52, high52 = float(min(window)), float(max(window))
        range_pct = _pos_in_range(latest, low52, high52)

        p1d, p1w, p1m = _pct(latest, d1), _pct(latest, w1), _pct(latest, m1)
        if p1d is not None:
            if p1d >= 0: up += 1
            else: down += 1
            movers.append({"ticker": sym, "pct": p1d})

        companies.append({
            "name": name, "ticker": sym, "price": latest,
            "pct_1d": p1d, "pct_1w": p1w, "pct_1m": p1m, "pct_ytd": None,
            "low_52w": low52, "high_52w": high52, "range_pct": range_pct,
            "headline": None, "source": None, "when": None,
            "next_event": None, "vol_x_avg": None,
            "news_url": _news_url_for(sym), "pr_url": f"https://finance.yahoo.com/quote/{sym}/press-releases",
        })

    winners = sorted([m for m in movers if m["pct"] is not None], key=lambda x: x["pct"], reverse=True)[:3]
    losers  = sorted([m for m in movers if m["pct"] is not None], key=lambda x: x["pct"])[:3]

    now_c = datetime.now(tz=CENTRAL_TZ) if CENTRAL_TZ else datetime.now()
    summary = {
        "as_of_ct": now_c,
        "up_count": up, "down_count": down,
        "top_winners": winners, "top_losers": losers,
        "catalysts": [],
    }

    html = render_email(summary, companies, cryptos=cryptos)
    return html
