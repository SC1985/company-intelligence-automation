
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import json, os, time, re

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from render_email import render_email

CENTRAL_TZ = ZoneInfo("America/Chicago") if ZoneInfo else None

# ---------- File loader ----------

def _load_entities() -> List[Dict[str, Any]]:
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.normpath(os.path.join(here, "..", "data", "companies.json"))
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        items = []
        for key in ("equities","companies","digital_assets","assets","items"):
            arr = data.get(key)
            if isinstance(arr, list):
                items.extend(arr)
        if not items:
            raise ValueError("companies.json object did not contain a recognized list key")
        return items
    elif isinstance(data, list):
        return data
    else:
        raise ValueError("Unsupported companies.json structure")

# ---------- History helpers (equities) ----------

def _fetch_stooq(symbol: str) -> Tuple[List[datetime], List[float], List[float], List[float]]:
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
            dt, cl, hi, lo = [], [], [], []
            reader = csv.DictReader(raw.splitlines())
            for row in reader:
                if not row.get("Date") or not row.get("Close"):
                    continue
                try:
                    d = datetime.fromisoformat(row["Date"])
                    c = float(row["Close"].replace(",", ""))
                    h = float((row.get("High") or c))
                    l = float((row.get("Low") or c))
                except Exception:
                    continue
                dt.append(d); cl.append(c); hi.append(h); lo.append(l)
            if len(cl) >= 30:
                return dt, cl, hi, lo
        except Exception:
            continue
    return [], [], [], []

def _fetch_alpha_vantage_equity(symbol: str, api_key: Optional[str]) -> Tuple[List[datetime], List[float], List[float], List[float]]:
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
        keys = sorted(ts.keys())
        dt, cl, hi, lo = [], [], [], []
        for k in keys[-500:]:
            row = ts.get(k) or {}
            ac = row.get("5. adjusted close") or row.get("4. close")
            h = row.get("2. high"); l = row.get("3. low")
            if ac is None:
                continue
            try:
                dt.append(datetime.fromisoformat(k))
                cval = float(str(ac).replace(",", ""))
                cl.append(cval)
                hi.append(float(str(h).replace(",", "")) if h is not None else cval)
                lo.append(float(str(l).replace(",", "")) if l is not None else cval)
            except Exception:
                continue
        if cl:
            time.sleep(12)  # free-tier pacing
        return dt, cl, hi, lo
    except Exception:
        return [], [], [], []

def _get_equity_history(symbol: str, api_key: Optional[str]) -> Tuple[str, List[datetime], List[float], List[float], List[float]]:
    dt, cl, hi, lo = _fetch_stooq(symbol)
    if len(cl) >= 30:
        return "stooq", dt, cl, hi, lo
    dt, cl, hi, lo = _fetch_alpha_vantage_equity(symbol, api_key)
    if len(cl) >= 30:
        return "alphavantage", dt, cl, hi, lo
    return "none", [], [], [], []

# ---------- History helpers (crypto via Alpha Vantage) ----------

def _fetch_alpha_vantage_crypto(symbol: str, market: str, api_key: Optional[str]) -> Tuple[List[datetime], List[float]]:
    if not api_key:
        return [], []
    from urllib.request import urlopen
    from urllib.parse import urlencode
    try:
        qs = urlencode({
            "function": "DIGITAL_CURRENCY_DAILY",
            "symbol": symbol.replace("-USD",""),  # e.g., "BTC-USD" -> "BTC"
            "market": market,
            "datatype": "json",
            "apikey": api_key
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
                cval = float(str(close).replace(",", ""))
                cl.append(cval)
            except Exception:
                continue
        if cl:
            time.sleep(12)
        return dt, cl
    except Exception:
        return [], []

# ---------- Analytics helpers ----------

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

def _pos_in_range(price, low, high) -> float:
    try:
        price, low, high = float(price), float(low), float(high)
        if high <= low:
            return 50.0
        return max(0.0, min(100.0, (price - low) / (high - low) * 100.0))
    except Exception:
        return 50.0

# ---------- News coalescing (per-ticker scoring) ----------

def _first_url_from_item(a, ticker: str) -> Optional[str]:
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

def _score_article_for_ticker(t: str, a: Dict[str, Any]) -> int:
    t = t.upper()
    score = 0
    for key in ("tickers", "symbols", "relatedTickers", "symbolsMentioned"):
        arr = a.get(key) or []
        if isinstance(arr, list) and any(str(x).upper() == t for x in arr):
            score += 100
    title = (a.get("title") or a.get("headline") or "")[:200]
    summary = (a.get("summary") or a.get("description") or "")[:400]
    import re as _re
    if _re.search(rf'\\b{_re.escape(t)}\\b', title, _re.I):
        score += 40
    if _re.search(rf'\\b{_re.escape(t)}\\b', summary, _re.I):
        score += 20
    url = _first_url_from_item(a, t)
    if _re.search(rf'/quote/{_re.escape(t)}\\b', url, _re.I) or _re.search(rf'/\\b{_re.escape(t)}\\b', url, _re.I):
        score += 25
    rivals = ["NVDA","AMD","INTC","TSLA","AAPL","MSFT","META","GOOGL","AMZN"]
    if any(_re.search(rf'\\b{r}\\b', title, _re.I) for r in rivals if r != t):
        score -= 15
    return score

def _pick_best_for_ticker(t: str, arts: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    best = None; best_score = -1
    for a in arts:
        s = _score_article_for_ticker(t, a)
        if s > best_score:
            best, best_score = a, s
    if best and best_score > 0:
        title = best.get("title") or best.get("headline")
        src = best.get("source")
        if isinstance(src, dict): src = src.get("name") or src.get("id") or src.get("domain")
        when = best.get("publishedAt") or best.get("published_at") or best.get("time")
        url = _first_url_from_item(best, t)
        return {"title": title, "source": src if isinstance(src, str) else None, "when": when, "url": url}
    return {"title": None, "source": None, "when": None, "url": f"https://finance.yahoo.com/quote/{t}/news"}

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
                out[t] = _pick_best_for_ticker(t, arts)
        items = news.get("items") or news.get("results") or []
        if isinstance(items, list):
            grouped: Dict[str, List[Dict[str, Any]]] = {}
            for a in items:
                t = a.get("ticker") or a.get("symbol")
                if not t:
                    for key in ("tickers","symbols","relatedTickers"):
                        arr = a.get(key) or []
                        if isinstance(arr, list) and arr:
                            t = str(arr[0])
                            break
                if not t:
                    continue
                T = str(t).upper()
                grouped.setdefault(T, []).append(a)
            for T, arr in grouped.items():
                if T not in out:
                    out[T] = _pick_best_for_ticker(T, arr)
    return out

# ---------- Main builder ----------

async def build_nextgen_html(logger) -> str:
    # News may be provided by your engine; we use it if available and fallback to per-ticker pages.
    try:
        from main import StrategicIntelligenceEngine
        engine = StrategicIntelligenceEngine()
        logger.info("NextGen: collecting news from engine")
        news = await engine._synthesize_strategic_news()
        news_map = _coalesce_news_map(news)
    except Exception:
        news_map = {}

    alpha_key = os.getenv("ALPHA_VANTAGE_API_KEY") or None
    entities = _load_entities()

    companies: List[Dict[str, Any]] = []
    cryptos: List[Dict[str, Any]] = []
    up = down = 0
    movers: List[Dict[str, Any]] = []

    # Helper to compute pct and range
    def pct(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
        try:
            if curr is None or prev is None or prev == 0:
                return None
            return (curr/prev - 1.0) * 100.0
        except Exception:
            return None

    for item in entities:
        symbol = str(item.get("symbol") or "").upper()
        name = item.get("name") or symbol
        asset_class = (item.get("asset_class") or ("crypto" if symbol.endswith("-USD") else "equity")).lower()

        if asset_class == "crypto":
            dtc, clc = _fetch_alpha_vantage_crypto(symbol, "USD", alpha_key)
            if not clc:
                continue
            latest = clc[-1]
            d1 = _nearest(clc, 1)
            w1 = _nearest(clc, 7)
            m1 = _nearest(clc, 30)
            # approximate YTD baseline: close nearest to last day of previous year
            ytd0 = None
            if dtc and clc:
                last_year = dtc[-1].year - 1
                for i in range(len(dtc)-1, -1, -1):
                    if dtc[i].year == last_year:
                        ytd0 = clc[i]; break

            p1d = pct(latest, d1); p1w = pct(latest, w1); p1m = pct(latest, m1); pytd = pct(latest, ytd0)
            window = clc[-365:] if len(clc) >= 365 else clc
            low52 = float(min(window)); high52 = float(max(window))
            range_pct = _pos_in_range(latest, low52, high52)

            # Press links by symbol
            press_map = {
                "BTC-USD": "https://bitcoin.org",
                "ETH-USD": "https://blog.ethereum.org",
                "DOGE-USD": "https://blog.dogecoin.com",
                "XRP-USD": "https://ripple.com/insights/",
            }
            cryptos.append({
                "name": name, "ticker": symbol, "price": latest,
                "pct_1d": p1d, "pct_1w": p1w, "pct_1m": p1m, "pct_ytd": pytd,
                "low_52w": low52, "high_52w": high52, "range_pct": range_pct,
                "headline": None, "source": None, "when": None,
                "next_event": None, "vol_x_avg": None,
                "news_url": f"https://finance.yahoo.com/quote/{symbol}/news",
                "pr_url": press_map.get(symbol, f"https://finance.yahoo.com/quote/{symbol}/press-releases"),
            })

        else:
            # equities
            src, dt, cl, hi, lo = _get_equity_history(symbol, alpha_key)
            if not cl:
                continue
            latest = cl[-1]
            d1 = _nearest(cl, 1)
            w1 = _nearest(cl, 6)
            m1 = _nearest(cl, 22)
            ytd0 = None
            if dt and cl:
                last_year = dt[-1].year - 1
                for i in range(len(dt)-1, -1, -1):
                    if dt[i].year == last_year:
                        ytd0 = cl[i]; break
            p1d = pct(latest, d1); p1w = pct(latest, w1); p1m = pct(latest, m1); pytd = pct(latest, ytd0)

            if p1d is not None:
                if p1d >= 0: up += 1
                else: down += 1
                movers.append({"ticker": symbol, "pct": p1d})

            window = cl[-252:] if len(cl) >= 252 else cl
            low52 = float(min(window)); high52 = float(max(window))
            range_pct = _pos_in_range(latest, low52, high52)

            nm = news_map.get(symbol, {})
            news_url = nm.get("url") or f"https://finance.yahoo.com/quote/{symbol}/news"

            companies.append({
                "name": name, "ticker": symbol, "price": latest,
                "pct_1d": p1d, "pct_1w": p1w, "pct_1m": p1m, "pct_ytd": pytd,
                "low_52w": low52, "high_52w": high52, "range_pct": range_pct,
                "headline": nm.get("title"), "source": nm.get("source"), "when": nm.get("when"),
                "next_event": None, "vol_x_avg": None,
                "news_url": news_url, "pr_url": f"https://finance.yahoo.com/quote/{symbol}/press-releases",
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
