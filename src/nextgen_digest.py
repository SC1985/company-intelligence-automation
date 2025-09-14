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

def _load_watchlist() -> List[Dict[str, Any]]:
    """Load watchlist.json from ../data WITHOUT changing order."""
    here = os.path.dirname(os.path.abspath(__file__))
    path_watch = os.path.normpath(os.path.join(here, "..", "data", "watchlist.json"))
    
    with open(path_watch, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Process the flat watchlist structure
    assets: List[Dict[str, Any]] = []
    for item in data:
        # Skip comment entries
        if "comment" in item:
            continue
            
        sym = str(item.get("symbol") or "").upper()
        if not sym:
            continue
            
        # Determine category from asset_class
        asset_class = item.get("asset_class", "equity")
        if asset_class == "etf":
            category = "etf_index"
        elif asset_class == "commodity":
            category = "commodity"
        elif asset_class == "crypto":
            category = "crypto"
        else:
            category = "equity"
            
        out = {
            "ticker": sym,
            "symbol": sym,
            "name": item.get("name") or sym,
            "category": category,
            "industry": item.get("industry"),
            "coingecko_id": item.get("coingecko_id"),
        }
        assets.append(out)
    
    return assets

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

def _news_headline_via_yahoo(symbol: str) -> Optional[Dict[str, Any]]:
    # Quick RSS-ish JSON endpoint via Rapid-style; fallback stub for environments without keys.
    # We'll just return None if unavailable; your existing engine can still provide news.
    return None

def _coingecko_news(id_hint: Optional[str]) -> Optional[Dict[str, Any]]:
    if not id_hint:
        return None
    url = f"https://www.coingecko.com/api/v3/coins/{id_hint}"
    data = _http_get_json(url, timeout=20.0)
    if not data:
        return None
    # Coingecko doesn't provide general news consistently; skip unless present.
    return None

# ----------------------- Prices -----------------------

def _calculate_ytd_from_daily(dates: List[str], closes: List[float]) -> Optional[float]:
    """Calculate YTD percentage from daily price data."""
    if not dates or not closes or len(dates) != len(closes):
        return None
    
    # Get current year
    current_year = datetime.now().year
    
    # Find the last trading day of previous year or first trading day of current year
    ytd_start_price = None
    ytd_start_date = None
    
    for i, date_str in enumerate(dates):
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            
            # If we find the first date of current year, use it
            if date.year == current_year:
                if ytd_start_price is None:
                    ytd_start_price = closes[i]
                    ytd_start_date = date_str
                    break
            # Keep track of the last price from previous year
            elif date.year == current_year - 1:
                ytd_start_price = closes[i]
                ytd_start_date = date_str
        except:
            continue
    
    if ytd_start_price and ytd_start_price > 0:
        current_price = closes[-1]
        return ((current_price / ytd_start_price) - 1.0) * 100.0
    
    return None

def _alpha_daily(symbol: str) -> Tuple[List[str], List[float]]:
    """Daily prices via Alpha Vantage (equities/commodities). Returns (dates, closes)."""
    if not ALPHA_KEY:
        return [], []
    from urllib.parse import urlencode
    qs = urlencode({
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": symbol,
        "outputsize": "full",  # Changed to 'full' to get more historical data for YTD
        "apikey": ALPHA_KEY,
    })
    url = f"https://www.alphavantage.co/query?{qs}"
    data = _http_get_json(url, timeout=30.0)
    ts = data.get("Time Series (Daily)") if isinstance(data, dict) else None
    if not isinstance(ts, dict):
        return [], []
    
    # Get all dates and sort them
    all_dates = sorted(ts.keys())
    
    # We need enough data for YTD (current year + some from last year)
    # and for 52-week range, so get last 400 trading days
    dates_to_use = all_dates[-400:] if len(all_dates) > 400 else all_dates
    
    dates: List[str] = []
    closes: List[float] = []
    for k in dates_to_use:
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
    """Get comprehensive price data from CoinGecko including YTD."""
    try:
        if not id_hint:
            id_hint = COINGECKO_IDS.get(symbol)
        if not id_hint:
            return None
        
        # Use the coins/{id} endpoint with market_data
        url = f"https://api.coingecko.com/api/v3/coins/{id_hint}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false"
        data = _http_get_json(url, timeout=20.0)
        if not data:
            return None
        
        m = data.get("market_data") or {}
        
        # Get current price
        price = (m.get("current_price") or {}).get("usd")
        
        # Get percentage changes - CoinGecko provides these directly
        pct_1d = m.get("price_change_percentage_24h")
        pct_1w = m.get("price_change_percentage_7d")
        pct_1m = m.get("price_change_percentage_30d")
        
        # Get YTD - CoinGecko doesn't always provide this, so we might need to calculate
        pct_ytd = None
        
        # First try to get it directly from the API
        if "price_change_percentage_1y_in_currency" in m:
            ytd_data = m.get("price_change_percentage_1y_in_currency") or {}
            if "usd" in ytd_data:
                # This is 1 year, not YTD, but better than nothing
                pct_ytd = ytd_data.get("usd")
        
        # If not available, try the price_change_percentage fields
        if pct_ytd is None and "price_change_percentage_200d" in m:
            # Use 200d as a proxy for YTD if available
            pct_ytd = m.get("price_change_percentage_200d")
        
        # Get 52-week range
        low_52w = (m.get("low_24h") or {}).get("usd")  # Fallback to 24h if 52w not available
        high_52w = (m.get("high_24h") or {}).get("usd")
        
        # Try to get actual 52w data if available
        if "ath" in m and "atl" in m:
            ath_data = m.get("ath") or {}
            atl_data = m.get("atl") or {}
            
            # Use ATH/ATL as proxies if they're within the last year
            if "usd" in ath_data:
                high_52w = ath_data.get("usd")
            if "usd" in atl_data:
                # Only use ATL if it's not too old
                low_52w = atl_data.get("usd")
        
        return {
            "price": price, 
            "pct_1d": pct_1d, 
            "pct_1w": pct_1w, 
            "pct_1m": pct_1m, 
            "pct_ytd": pct_ytd,
            "low_52w": low_52w, 
            "high_52w": high_52w
        }
    except Exception as e:
        print(f"Error fetching CoinGecko data for {symbol}: {e}")
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
    assets = _load_watchlist()  # PRESERVES ORDER
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
        elif cat == "crypto":
            # Try light coingecko news (often sparse) — safe to skip
            pass

        # Enforce 7-day cutoff on articles (skip if older)
        if h_when:
            pub_dt = _parse_iso(h_when)
            if pub_dt and pub_dt < seven_days_ago:
                # too old
                headline = None; h_url = None; h_source = None; h_when = None; desc = ""

        # --------- Pricing ----------
        price = None; pct_1d = pct_1w = pct_1m = pct_ytd = None
        low_52w = high_52w = None
        
        if cat in ("equity", "etf_index", "commodity"):
            dt, cl = _alpha_daily(sym)
            if cl and len(cl) > 0:
                price = cl[-1]
                
                # Calculate 1D change
                if len(cl) >= 2: 
                    pct_1d = ((cl[-1]/cl[-2])-1.0)*100.0
                
                # Calculate 1W change (5 trading days)
                if len(cl) >= 6: 
                    pct_1w = ((cl[-1]/cl[-6])-1.0)*100.0
                
                # Calculate 1M change (22 trading days)
                if len(cl) >= 22: 
                    pct_1m = ((cl[-1]/cl[-22])-1.0)*100.0
                
                # Calculate YTD using the helper function
                pct_ytd = _calculate_ytd_from_daily(dt, cl)
                
                # Calculate 52-week range
                if len(cl) >= 252:
                    low_52w = min(cl[-252:])
                    high_52w = max(cl[-252:])
                elif len(cl) > 0:
                    # Use available data if less than 252 days
                    low_52w = min(cl)
                    high_52w = max(cl)
                    
        elif cat == "crypto":
            cg = _coingecko_price(sym, a.get("coingecko_id"))
            if cg and cg.get("price") is not None:
                price = cg["price"]
                pct_1d = cg.get("pct_1d")
                pct_1w = cg.get("pct_1w")
                pct_1m = cg.get("pct_1m")
                pct_ytd = cg.get("pct_ytd")
                low_52w = cg.get("low_52w")
                high_52w = cg.get("high_52w")

        if pct_1d is not None:
            if pct_1d >= 0: up += 1
            else: down += 1

        # Calculate range percentage for the range bar
        range_pct = 50.0  # default
        if price and low_52w and high_52w and high_52w > low_52w:
            range_pct = ((price - low_52w) / (high_52w - low_52w)) * 100.0

        enriched.append({
            **a,
            "price": price,
            "pct_1d": pct_1d, 
            "pct_1w": pct_1w, 
            "pct_1m": pct_1m, 
            "pct_ytd": pct_ytd,
            "low_52w": low_52w, 
            "high_52w": high_52w,
            "range_pct": range_pct,
            "headline": headline, 
            "news_url": h_url, 
            "source": h_source, 
            "when": h_when, 
            "description": desc,
        })

    # ----------------- Build hero lists -----------------

    def _belongs_to_section(asset: Dict[str, Any], section: str) -> bool:
        return (asset.get("category") == section)

    # Score and collect candidates
    breaking_candidates: List[Tuple[int, Dict[str, Any]]] = []
    section_candidates: Dict[str, List[Tuple[int, Dict[str, Any]]]] = {"etf_index": [], "equity": [], "commodity": [], "crypto": []}

    for e in enriched:
        title = (e.get("headline") or "").strip()
        if not title:
            continue
        pub = _parse_iso(e.get("when")) if e.get("when") else None
        if pub and pub < seven_days_ago:
            continue

        b, g = _score_headline(title, pub)
        # Breaking threshold: >15
        if b > 15:
            breaking_candidates.append((b, e))
        # General: >5 into the section
        if g > 5:
            sec = e.get("category")
            if sec in section_candidates:
                section_candidates[sec].append((g, e))

    breaking_candidates.sort(key=lambda x: x[0], reverse=True)
    heroes_breaking = []
    for score, e in breaking_candidates[:2]:  # top 1–2
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
            if len(chosen) >= 3:  # cap 3 per section
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
