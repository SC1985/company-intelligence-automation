from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import json, os, time, re

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

def _http_get(url: str, timeout: float = 25.0, headers: Optional[Dict[str,str]] = None) -> Optional[bytes]:
    try:
        from urllib.request import urlopen, Request
        hdrs = {"User-Agent": "ci-digest/1.0 (+https://example.local)"}
        if headers:
            hdrs.update(headers)
        req = Request(url, headers=hdrs)
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None

def _http_get_json(url: str, timeout: float = 25.0, headers: Optional[Dict[str,str]] = None) -> Optional[Dict[str, Any]]:
    raw = _http_get(url, timeout=timeout, headers=headers)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return None

# -------------------- History helpers (equities) --------------------

def _fetch_stooq(symbol: str) -> Tuple[List[datetime], List[float]]:
    import csv
    from urllib.request import urlopen, Request
    dt, cl = [], []
    for s in (symbol.lower(), f"{symbol.lower()}.us"):
        try:
            url = f"https://stooq.com/q/d/l/?s={s}&i=d"
            req = Request(url, headers={"User-Agent":"ci-digest/1.0"})
            with urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            if not raw or "<html" in raw.lower():
                continue
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
    from urllib.request import urlopen, Request
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
        req = Request(url, headers={"User-Agent":"ci-digest/1.0"})
        with urlopen(req, timeout=25) as resp:
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

COINGECKO_IDS = {
    "BTC-USD": "bitcoin",
    "ETH-USD": "ethereum",
    "DOGE-USD": "dogecoin",
    "XRP-USD": "ripple",
}

def _fetch_coingecko_crypto(symbol_usd: str, id_hint: Optional[str] = None) -> Tuple[List[datetime], List[float]]:
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
    from urllib.request import urlopen, Request
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
        req = Request(url, headers={"User-Agent":"ci-digest/1.0"})
        with urlopen(req, timeout=25) as resp:
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

# -------------------- News helpers --------------------

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
    if re.search(rf'\b{re.escape(t)}\b', title, re.I):
        score += 40
    if re.search(rf'\b{re.escape(t)}\b', summary, re.I):
        score += 20
    url = _first_url_from_item(a, t)
    if re.search(rf'/quote/{re.escape(t)}\b', url, re.I) or re.search(rf'/\b{re.escape(t)}\b', url, re.I):
        score += 25
    rivals = ["NVDA","AMD","INTC","TSLA","AAPL","MSFT","META","GOOGL","AMZN"]
    if any(re.search(rf'\b{r}\b', title, re.I) for r in rivals if r != t):
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
        # Include description for hero body
        description = best.get("description") or best.get("summary") or ""
        return {
            "title": title, 
            "source": src if isinstance(src, str) else None, 
            "when": when, 
            "url": url,
            "description": description
        }
    return {
        "title": None, 
        "source": None, 
        "when": None, 
        "url": f"https://finance.yahoo.com/quote/{t}/news",
        "description": ""
    }

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

def _news_headline_via_newsapi(ticker: str, name: str) -> Optional[Dict[str, str]]:
    key = os.getenv("NEWSAPI_KEY")
    if not key:
        return None
    from urllib.parse import urlencode
    q = f"{name} OR {ticker}"
    qs = urlencode({"q": q, "pageSize": 5, "sortBy": "publishedAt", "language": "en", "apiKey": key})
    url = f"https://newsapi.org/v2/everything?{qs}"
    data = _http_get_json(url, timeout=20)
    if not data or data.get("status") != "ok":
        return None
    for a in (data.get("articles") or []):
        title = a.get("title"); link = a.get("url")
        src = (a.get("source") or {}).get("name")
        when = a.get("publishedAt")
        # 🔥 DEBUG: Log what we get from NewsAPI
        description = a.get("description") or ""
        try:
            import logging
            logger = logging.getLogger("ci-entrypoint")
            logger.info(f"NewsAPI for {ticker}: title='{title[:50] if title else 'None'}...', description='{description[:100] if description else 'EMPTY'}...'")
        except:
            pass
        
        if title and link:
            return {
                "title": title, 
                "url": link, 
                "source": src, 
                "when": when,
                "description": description
            }
    return None

def _news_headline_via_yahoo_rss(ticker: str) -> Optional[Dict[str, str]]:
    import xml.etree.ElementTree as ET
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    raw = _http_get(url, timeout=15)
    if not raw:
        return None
    try:
        root = ET.fromstring(raw.decode("utf-8", errors="replace"))
        items = root.findall(".//item")
        if not items:
            return None
        top = items[0]
        title = top.findtext("title")
        link = top.findtext("link")
        pub = top.findtext("pubDate")
        # Try to get description from RSS
        description = top.findtext("description") or ""
        # Clean up HTML tags if present
        if description:
            import re
            description = re.sub(r'<[^>]+>', '', description).strip()
        
        # 🔥 DEBUG: Log what we get from Yahoo RSS
        try:
            import logging
            logger = logging.getLogger("ci-entrypoint")
            logger.info(f"Yahoo RSS for {ticker}: title='{title[:50] if title else 'None'}...', description='{description[:100] if description else 'EMPTY'}...'")
        except:
            pass
        
        return {
            "title": title, 
            "url": link, 
            "source": "Yahoo Finance", 
            "when": pub,
            "description": description
        }
    except Exception:
        return None

def _news_headline_for_crypto_coingecko(coingecko_id: str) -> Optional[Dict[str, str]]:
    if not coingecko_id:
        return None
    url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/status_updates?per_page=1"
    data = _http_get_json(url, timeout=15)
    if not data or not isinstance(data.get("status_updates"), list) or not data["status_updates"]:
        return None
    u = data["status_updates"][0]
    title = u.get("category") or "Update"
    desc = u.get("description") or ""
    src = (u.get("project") or {}).get("name") or "CoinGecko"
    when = u.get("created_at")
    link = u.get("article_url") or (u.get("project") or {}).get("homepage") or "https://www.coingecko.com/"
    if title.lower() in ("general", "milestone", "release", "update") and desc:
        p = desc.strip().split(".")[0].strip()
        if p:
            title = p
    
    # 🔥 DEBUG: Log what we get from CoinGecko
    try:
        import logging
        logger = logging.getLogger("ci-entrypoint")
        logger.info(f"CoinGecko for {coingecko_id}: title='{title[:50] if title else 'None'}...', description='{desc[:100] if desc else 'EMPTY'}...'")
    except:
        pass
    
    return {
        "title": title, 
        "url": link, 
        "source": src, 
        "when": when,
        "description": desc
    }

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
    # Try engine-provided news; we will still do per-ticker fallbacks below
    news_map_from_engine: Dict[str, Dict[str, Optional[str]]] = {}
    try:
        from main import StrategicIntelligenceEngine
        engine = StrategicIntelligenceEngine()
        logger.info("NextGen: news via engine")
        news = await engine._synthesize_strategic_news()
        news_map_from_engine = _coalesce_news_map(news)
    except Exception:
        news_map_from_engine = {}

    alpha_key = os.getenv("ALPHA_VANTAGE_API_KEY") or None
    newsapi_key_present = bool(os.getenv("NEWSAPI_KEY"))
    entities = _load_entities()

    companies: List[Dict[str, Any]] = []
    cryptos:   List[Dict[str, Any]] = []
    up = down = 0
    movers: List[Dict[str, Any]] = []

    def _news_url_for(t: str) -> str:
        return f"https://finance.yahoo.com/quote/{t}/news"

    # Pace external calls
    last_call_ts = 0.0
    def _pace(min_interval=1.5):
        nonlocal last_call_ts
        now = time.time()
        delta = now - last_call_ts
        if delta < min_interval:
            time.sleep(min_interval - delta)
        last_call_ts = time.time()

    for e in entities:
        sym = str(e.get("symbol") or "").upper()
        if not sym:
            continue
        name = e.get("name") or sym
        is_crypto = (e.get("asset_class","").lower() == "crypto") or sym.endswith("-USD")

        # ----- Headline selection per entity -----
        headline = None; h_source = None; h_when = None; h_url = _news_url_for(sym)
        description = ""  # Store article description
        
        # 1) Engine
        m = news_map_from_engine.get(sym)
        if m and m.get("title"):
            headline, h_source, h_when, h_url = m.get("title"), m.get("source"), m.get("when"), m.get("url") or h_url
            description = m.get("description") or ""
            logger.info(f"Engine news for {sym}: headline='{headline[:50] if headline else 'None'}...', description='{description[:50] if description else 'EMPTY'}...'")
        else:
            # 2) NewsAPI (if available)
            if newsapi_key_present:
                _pace(0.8)
                r = _news_headline_via_newsapi(sym, name)
                if r and r.get("title"):
                    headline, h_source, h_when, h_url = r["title"], r.get("source"), r.get("when"), r.get("url", h_url)
                    description = r.get("description") or ""
                    logger.info(f"Selected NewsAPI result for {sym}: description='{description[:50] if description else 'EMPTY'}...'")
            # 3) Yahoo RSS
            if not headline:
                _pace(0.8)
                r = _news_headline_via_yahoo_rss(sym)
                if r and r.get("title"):
                    headline, h_source, h_when, h_url = r["title"], r.get("source"), r.get("when"), r.get("url", h_url)
                    description = r.get("description") or ""
                    logger.info(f"Selected Yahoo RSS result for {sym}: description='{description[:50] if description else 'EMPTY'}...'")
            # 4) Crypto-only: CoinGecko status updates
            if not headline and is_crypto:
                _pace(0.8)
                r = _news_headline_for_crypto_coingecko(e.get("coingecko_id") or COINGECKO_IDS.get(sym))
                if r and r.get("title"):
                    headline, h_source, h_when, h_url = r["title"], r.get("source"), r.get("when"), r.get("url", h_url)
                    description = r.get("description") or ""
                    logger.info(f"Selected CoinGecko result for {sym}: description='{description[:50] if description else 'EMPTY'}...'")

        # 🔥 DEBUG: Log what goes into company/crypto objects
        if headline and description:
            logger.info(f"FINAL: {sym} will have description='{description[:100] if description else 'EMPTY'}...' in company object")
        elif headline:
            logger.warning(f"ISSUE: {sym} has headline='{headline[:50]}...' but NO DESCRIPTION")

        if is_crypto:
            # ---- Crypto prices (CoinGecko -> AV -> placeholder) ----
            _pace(1.5)
            dt, cl = _fetch_coingecko_crypto(sym, id_hint=e.get("coingecko_id"))
            provider = "coingecko" if cl else None
            if not cl:
                _pace(12.0)
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
                    "headline": headline, "source": h_source, "when": h_when,
                    "description": description,  # Article description
                    "next_event": None, "vol_x_avg": None,
                    "news_url": h_url,
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
                cryptos.append({
                    "name": name, "ticker": sym, "price": 0.0,
                    "pct_1d": None, "pct_1w": None, "pct_1m": None, "pct_ytd": None,
                    "low_52w": 0.0, "high_52w": 0.0, "range_pct": 50.0,
                    "headline": headline, "source": h_source, "when": h_when,
                    "description": description,  # Article description
                    "next_event": None, "vol_x_avg": None,
                    "news_url": h_url, "pr_url": h_url,
                })
                try:
                    import logging
                    logging.getLogger("ci-entrypoint").warning(f"{sym}: crypto providers unavailable – rendering placeholder")
                except Exception:
                    pass
            continue

        # ---- Equities ----
        src, dt, cl = _get_equity_series(sym, os.getenv("ALPHA_VANTAGE_API_KEY") or None)
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

        # Compute YTD vs last trading day of previous calendar year
        pytd = None
        if dt:
            last_year = dt[-1].year - 1
            for i2 in range(len(dt)-1, -1, -1):
                if dt[i2].year == last_year:
                    pytd = _pct(latest, cl[i2]); break
        companies.append({
            "name": name, "ticker": sym, "price": latest,
            "pct_1d": p1d, "pct_1w": p1w, "pct_1m": p1m, "pct_ytd": pytd,
            "low_52w": low52, "high_52w": high52, "range_pct": range_pct,
            "headline": headline, "source": h_source, "when": h_when,
            "description": description,  # Article description
            "next_event": None, "vol_x_avg": None,
            "news_url": h_url, "pr_url": f"https://finance.yahoo.com/quote/{sym}/press-releases",
        })

    # 🔥 DEBUG: Log companies that might be used for hero
    for c in companies:
        if c.get("headline"):
            logger.info(f"Company {c.get('ticker')}: headline='{c.get('headline')[:50]}...', description='{c.get('description')[:50] if c.get('description') else 'NO DESCRIPTION'}...'")

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
