# src/nextgen_digest.py
# Builds the NextGen HTML while preserving watchlist order and applying:
# - Breaking News (top 1–2 across any category)
# - Section-specific heroes (max 3 per section)
# - 7-day article cutoff
# - Alpha Vantage for equities & commodities, CoinGecko for crypto
# - NO changes to mailer/entrypoint or mobile padding

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import json, os, time, re

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from render_email import render_email

CENTRAL_TZ = ZoneInfo("America/Chicago") if ZoneInfo else None

# ----------------------- Utilities -----------------------

def _ct_now() -> datetime:
    try:
        return datetime.now(CENTRAL_TZ)
    except Exception:
        return datetime.now()

def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        s = value.strip()
        s2 = s[:-1] + "+00:00" if s.endswith("Z") else s
        dt = datetime.fromisoformat(s2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def _http_get_json(url: str, timeout: float = 25.0, headers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    # Minimal stdlib GET with retry
    for attempt in range(3):
        try:
            from urllib.request import urlopen, Request
            hdrs = {"User-Agent": "ci-digest/1.0"}
            if headers: hdrs.update(headers)
            req = Request(url, headers=hdrs)
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            return json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return None

# ----------------------- Config / Sources -----------------------

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
ALPHA_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

COINGECKO_IDS = {
    "BTC-USD": "bitcoin",
    "ETH-USD": "ethereum",
    "XRP-USD": "ripple",
    "DOGE-USD": "dogecoin",
}

# ----------------------- Data Loading -----------------------

def _load_companies() -> List[Dict[str, Any]]:
    """Load companies.json from ../data WITHOUT changing order."""
    here = os.path.dirname(os.path.abspath(__file__))
    path_comp = os.path.normpath(os.path.join(here, "..", "data", "companies.json"))
    with open(path_comp, "r", encoding="utf-8") as f:
        data = json.load(f)
    companies: List[Dict[str, Any]] = []
    for c in data:
        sym = str(c.get("symbol") or "").upper()
        if not sym: 
            continue
        out = {
            "ticker": sym,
            "symbol": sym,
            "name": c.get("name") or sym,
            "category": "equity",
            "industry": c.get("sector"),
        }
        companies.append(out)
    return companies

# ----------------------- Headlines (NewsAPI / Yahoo / CoinGecko) -----------------------

def _news_headline_via_newsapi(symbol: str, name: str) -> Optional[Dict[str, Any]]:
    if not NEWSAPI_KEY:
        return None
    # Very light symbol search; rely on NewsAPI recency + provider filtering
    q = f"{symbol} OR \"{name}\""
    url = f"https://newsapi.org/v2/everything?q={q}&pageSize=3&sortBy=publishedAt&language=en&apiKey={NEWSAPI_KEY}"
    data = _http_get_json(url, timeout=20.0)
    if not data or data.get("status") != "ok":
        return None
    arts = data.get("articles") or []
    for art in arts:
        title = (art.get("title") or "").strip()
        if not title:
            continue
        when = art.get("publishedAt")
        src = (art.get("source") or {}).get("name")
        url = art.get("url")
        desc = art.get("description") or ""
        return {"title": title, "when": when, "source": src, "url": url, "description": desc}
    return None

# ----------------------- Prices -----------------------

def _calculate_ytd(dates: List[str], closes: List[float]) -> Optional[float]:
    """Calculate YTD percentage from daily price data."""
    if not dates or not closes or len(dates) != len(closes):
        return None
    
    current_year = datetime.now().year
    ytd_start_price = None
    
    # Find first trading day of current year or last of previous year
    for i, date_str in enumerate(dates):
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            if date.year == current_year:
                if ytd_start_price is None:
                    ytd_start_price = closes[i]
                    break
            elif date.year == current_year - 1:
                ytd_start_price = closes[i]
        except:
            continue
    
    if ytd_start_price and ytd_start_price > 0:
        return ((closes[-1] / ytd_start_price) - 1.0) * 100.0
    
    return None

def _alpha_daily(symbol: str) -> Tuple[List[str], List[float]]:
    """Daily prices via Alpha Vantage (equities/commodities). Returns (dates, closes)."""
    if not ALPHA_KEY:
        return [], []
    from urllib.parse import urlencode
    qs = urlencode({
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": symbol,
        "outputsize": "full",  # FIX 1: Changed to full for YTD calculation
        "apikey": ALPHA_KEY,
    })
    url = f"https://www.alphavantage.co/query?{qs}"
    data = _http_get_json(url, timeout=30.0)
    ts = data.get("Time Series (Daily)") if isinstance(data, dict) else None
    if not isinstance(ts, dict):
        return [], []
    keys = sorted(ts.keys())
    # Get more data for YTD calculation
    keys_to_use = keys[-400:] if len(keys) > 400 else keys
    dates: List[str] = []
    closes: List[float] = []
    for k in keys_to_use:
        row = ts.get(k) or {}
        ac = row.get("5. adjusted close") or row.get("4. close")
        try:
            price = float(str(ac).replace(",", ""))
        except Exception:
            continue
        dates.append(k)
        closes.append(price)
    return dates, closes

def _coingecko_price(symbol: str, id_hint: Optional[str]) -> Optional[Dict[str, Any]]:
    # Minimal CoinGecko price call via market data endpoint (public)
    try:
        if not id_hint:
            id_hint = COINGECKO_IDS.get(symbol)
        if not id_hint:
            return None
        url = f"https://api.coingecko.com/api/v3/coins/{id_hint}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false"
        data = _http_get_json(url, timeout=20.0)
        if not data:
            return None
        m = data.get("market_data") or {}
        price = (m.get("current_price") or {}).get("usd")
        pct_1d = (m.get("price_change_percentage_24h"))
        pct_1w = (m.get("price_change_percentage_7d"))
        pct_1m = (m.get("price_change_percentage_30d"))
        # FIX 2: Better YTD for crypto
        pct_ytd = m.get("price_change_percentage_200d")  # Use 200d as proxy
        low_52w = (m.get("low_24h") or {}).get("usd")
        high_52w = (m.get("high_24h") or {}).get("usd")
        return {"price": price, "pct_1d": pct_1d, "pct_1w": pct_1w, "pct_1m": pct_1m, "pct_ytd": pct_ytd,
                "low_52w": low_52w, "high_52w": high_52w}
    except Exception:
        return None

# ----------------------- Hero Scoring -----------------------

_BREAKING_KWS = {
    "urgent": ["breaking", "just in", "alert", "exclusive", "developing"],
    "major": ["announces", "launches", "unveils", "reveals", "reports", "surges", "plunges", "soars", "crashes"],
    "earnings": ["earnings", "revenue", "profit", "beat", "miss", "guidance"],
    "deal": ["acquisition", "merger", "buyout", "partnership", "deal"],
    "reg": ["sec", "fda", "approval", "investigation", "lawsuit", "ruling"],
}
_BACKUP_KWS = {
    "analysis": ["analysis", "outlook", "forecast", "expects"],
    "market": ["market", "stocks", "trading", "investors", "wall street"],
    "sector": ["tech", "ai", "crypto", "energy", "healthcare"],
}

def _score_headline(headline: str, published: Optional[datetime]) -> Tuple[int, int]:
    bl = headline.lower()
    breaking, backup = 0, 0
    for kw in _BREAKING_KWS["urgent"]:   breaking += 25 if kw in bl else 0
    for kw in _BREAKING_KWS["major"]:    breaking += 20 if kw in bl else 0
    for kw in _BREAKING_KWS["earnings"]: breaking += 18 if kw in bl else 0
    for kw in _BREAKING_KWS["deal"]:     breaking += 18 if kw in bl else 0
    for kw in _BREAKING_KWS["reg"]:      breaking += 15 if kw in bl else 0
    for group, kws in _BACKUP_KWS.items():
        for kw in kws:
            if kw in bl:
                backup += 8 if group == "analysis" else 10 if group == "market" else 9
    # Recency boost
    if published:
        hours_ago = (datetime.now(timezone.utc) - published).total_seconds() / 3600
        if hours_ago < 2:   breaking += 20; backup += 20
        elif hours_ago < 6: breaking += 15; backup += 15
        elif hours_ago < 12:breaking += 10; backup += 10
        elif hours_ago < 24:breaking += 5;  backup += 5
    return breaking, backup

# ----------------------- Main -----------------------

async def build_nextgen_html(logger) -> str:
    companies = _load_companies()  # PRESERVES ORDER
    cryptos = [
        {"ticker": "BTC-USD", "symbol": "BTC-USD", "name": "Bitcoin", "category": "crypto", "coingecko_id": "bitcoin"},
        {"ticker": "XRP-USD", "symbol": "XRP-USD", "name": "XRP", "category": "crypto", "coingecko_id": "ripple"},
    ]
    
    assets = companies + cryptos
    up = down = 0
    failed = 0

    # Collect per-asset fields we render (we will not reorder assets)
    enriched: List[Dict[str, Any]] = []

    # Gather news map; use engine if available, else NewsAPI/Yahoo/CoinGecko when possible
    engine_news: Dict[str, Dict[str, Any]] = {}
    try:
        from main import StrategicIntelligenceEngine  # optional
        engine = StrategicIntelligenceEngine()
        logger.info("NextGen: attempting news via engine")
        news = await engine._synthesize_strategic_news()
        # Expecting iterable of {symbol,title,url,when,source,description}
        for item in news or []:
            sym = str(item.get("symbol") or "").upper()
            if not sym: 
                continue
            engine_news[sym] = {
                "title": item.get("title"),
                "url": item.get("url"),
                "when": item.get("when"),
                "source": item.get("source"),
                "description": item.get("description"),
            }
        logger.info(f"Engine provided news for {len(engine_news)} symbols")
    except Exception as e:
        logger.warning(f"Engine news unavailable: {e}")

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    for a in assets:
        sym = a["symbol"]
        name = a["name"]
        cat  = a["category"]

        # --------- Headline (prefer engine; otherwise NewsAPI/Yahoo/CoinGecko) ----------
        headline = None; h_url = None; h_source = None; h_when = None; desc = ""
        m = engine_news.get(sym)
        if m and m.get("title"):
            headline = m["title"]; h_url = m.get("url"); h_source = m.get("source")
            h_when = m.get("when"); desc = m.get("description") or ""
        elif NEWSAPI_KEY:
            r = _news_headline_via_newsapi(sym, name)
            if r and r.get("title"):
                headline = r["title"]; h_url = r.get("url"); h_source = r.get("source"); h_when = r.get("when"); desc = r.get("description") or ""

        # Enforce 7-day cutoff on articles (skip if older)
        if h_when:
            pub_dt = _parse_iso(h_when)
            if pub_dt and pub_dt < seven_days_ago:
                headline = None; h_url = None; h_source = None; h_when = None; desc = ""

        # --------- Pricing ----------
        price = None; pct_1d = pct_1w = pct_1m = pct_ytd = None
        low_52w = high_52w = None
        if cat in ("equity", "commodity"):  # FIX 1: Include commodity
            dt, cl = _alpha_daily(sym)
            if cl:
                price = cl[-1]
                if len(cl) >= 2: pct_1d = ((cl[-1]/cl[-2])-1.0)*100.0
                if len(cl) >= 6: pct_1w = ((cl[-1]/cl[-6])-1.0)*100.0
                if len(cl) >= 22: pct_1m = ((cl[-1]/cl[-22])-1.0)*100.0
                pct_ytd = _calculate_ytd(dt, cl)  # FIX 2: Proper YTD calculation
                if len(cl) >= 252:
                    low_52w, high_52w = min(cl[-252:]), max(cl[-252:])
                elif cl:
                    low_52w, high_52w = min(cl), max(cl)
        elif cat == "crypto":
            cg = _coingecko_price(sym, a.get("coingecko_id"))
            if cg and cg.get("price") is not None:
                price = cg["price"]; pct_1d = cg.get("pct_1d"); pct_1w = cg.get("pct_1w"); pct_1m = cg.get("pct_1m"); pct_ytd = cg.get("pct_ytd")
                low_52w = cg.get("low_52w"); high_52w = cg.get("high_52w")

        if pct_1d is not None:
            if pct_1d >= 0: up += 1
            else: down += 1

        # Calculate range percentage
        range_pct = 50.0
        if price and low_52w and high_52w and high_52w > low_52w:
            range_pct = ((price - low_52w) / (high_52w - low_52w)) * 100.0

        enriched.append({
            **a,
            "price": price,
            "pct_1d": pct_1d, "pct_1w": pct_1w, "pct_1m": pct_1m, "pct_ytd": pct_ytd,
            "low_52w": low_52w, "high_52w": high_52w, "range_pct": range_pct,
            "headline": headline, "news_url": h_url, "source": h_source, "when": h_when, "description": desc,
        })

    # ----------------- Build hero lists -----------------

    # Score and collect candidates
    breaking_candidates: List[Tuple[int, Dict[str, Any]]] = []
    section_candidates: Dict[str, List[Tuple[int, Dict[str, Any]]]] = {"equity": [], "crypto": []}

    for e in enriched:
        title = (e.get("headline") or "").strip()
        if not title:
            continue
        pub = _parse_iso(e.get("when")) if e.get("when") else None
        if pub and pub < seven_days_ago:
            continue

        b, g = _score_headline(title, pub)
        if b > 15:
            breaking_candidates.append((b, e))
        if g > 5:
            sec = e.get("category")
            if sec in section_candidates:
                section_candidates[sec].append((g, e))

    breaking_candidates.sort(key=lambda x: x[0], reverse=True)
    heroes_breaking = []
    for score, e in breaking_candidates[:2]:
        heroes_breaking.append({
            "title": e["headline"],
            "url": e.get("news_url") or f"https://finance.yahoo.com/quote/{e.get('ticker','')}/news",
            "source": e.get("source"),
            "when": e.get("when"),
            "description": e.get("description") or "",
        })

    heroes_by_section: Dict[str, List[Dict[str, Any]]] = {}
    for sec, arr in section_candidates.items():
        arr.sort(key=lambda x: x[0], reverse=True)
        chosen = []
        seen_titles = set()
        for score, e in arr:
            if len(chosen) >= 3:
                break
            t = (e.get("headline") or "").strip()
            if not t or t in seen_titles:
                continue
            seen_titles.add(t)
            chosen.append({
                "title": t,
                "url": e.get("news_url") or f"https://finance.yahoo.com/quote/{e.get('ticker','')}/news",
                "source": e.get("source"),
                "when": e.get("when"),
                "description": e.get("description") or "",
            })
        if chosen:
            heroes_by_section[sec] = chosen

    # ----------------- Summary + render -----------------

    now_c = _ct_now()
    summary = {
        "as_of_ct": now_c,
        "up_count": up, "down_count": down,
        "heroes_breaking": heroes_breaking,
        "heroes_by_section": heroes_by_section,
        "data_quality": {
            "successful_entities": len(enriched),
            "failed_entities": failed,
            "total_entities": len(assets),
        },
    }

    html = render_email(summary, enriched)
    return html
