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
import traceback

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

def _http_get_json(url: str, timeout: float = 25.0, headers: Optional[Dict[str, str]] = None, logger=None) -> Optional[Dict[str, Any]]:
    """Minimal stdlib GET with retry and logging"""
    for attempt in range(3):
        try:
            from urllib.request import urlopen, Request
            hdrs = {"User-Agent": "ci-digest/1.0"}
            if headers: hdrs.update(headers)
            req = Request(url, headers=hdrs)
            
            if logger:
                # Log URL without sensitive API keys
                safe_url = re.sub(r'(apikey|api_key|key)=[^&]+', r'\1=***', url)
                logger.info(f"HTTP GET attempt {attempt+1}: {safe_url[:100]}...")
            
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                
            result = json.loads(raw.decode("utf-8", errors="replace"))
            
            if logger:
                logger.info(f"HTTP GET success, response size: {len(raw)} bytes")
            
            return result
        except Exception as e:
            if logger:
                logger.warning(f"HTTP GET attempt {attempt+1} failed: {str(e)}")
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
    
    # Now expecting: { "sections": [ { "name": "...", "category": "...", "assets":[...] }, ... ] }
    sections = data.get("sections") or []
    assets: List[Dict[str, Any]] = []
    
    for sec in sections:
        cat = (sec.get("category") or "").strip()  # "etf_index" | "equity" | "commodity" | "crypto"
        sec_assets = sec.get("assets") or []
        for a in sec_assets:  # PRESERVE ORDER as provided
            sym = str(a.get("symbol") or "").upper()
            if not sym: 
                continue
            out = {
                "ticker": sym,
                "symbol": sym,
                "name": a.get("name") or sym,
                "category": cat or "equity",
                "industry": a.get("industry"),
                "coingecko_id": a.get("coingecko_id"),
            }
            assets.append(out)
    return assets

# ----------------------- Fallback Data Source: Stooq -----------------------

def _stooq_daily(symbol: str, logger=None) -> Tuple[List[str], List[float]]:
    """Get daily prices from Stooq (free, no API key needed)."""
    try:
        # Stooq provides CSV data for most US stocks
        url = f"https://stooq.com/q/d/l/?s={symbol.lower()}&i=d"
        
        if logger:
            logger.info(f"Trying Stooq for {symbol}")
        
        from urllib.request import urlopen, Request
        req = Request(url, headers={"User-Agent": "ci-digest/1.0"})
        with urlopen(req, timeout=15.0) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        
        lines = raw.strip().split("\n")
        if len(lines) < 2:
            return [], []
        
        dates = []
        closes = []
        
        # Skip header
        for line in lines[1:]:
            parts = line.split(",")
            if len(parts) >= 5:
                date = parts[0]
                close = parts[4]  # Close price is 5th column
                try:
                    price = float(close)
                    dates.append(date)
                    closes.append(price)
                except:
                    continue
        
        if logger and len(closes) > 0:
            logger.info(f"Stooq success for {symbol}: {len(closes)} prices, latest={closes[-1]:.2f}")
        
        return dates[-120:], closes[-120:]  # Return last 120 days
        
    except Exception as e:
        if logger:
            logger.warning(f"Stooq failed for {symbol}: {str(e)}")
        return [], []

# ----------------------- Headlines (NewsAPI / Yahoo / CoinGecko) -----------------------

def _news_headline_via_newsapi(symbol: str, name: str, logger=None) -> Optional[Dict[str, Any]]:
    if not NEWSAPI_KEY:
        if logger:
            logger.warning("NewsAPI key not configured")
        return None
    
    try:
        # Very light symbol search; rely on NewsAPI recency + provider filtering
        q = f"{symbol} OR \"{name}\""
        url = f"https://newsapi.org/v2/everything?q={q}&pageSize=3&sortBy=publishedAt&language=en&apiKey={NEWSAPI_KEY}"
        
        if logger:
            logger.info(f"Fetching news for {symbol} from NewsAPI")
        
        data = _http_get_json(url, timeout=20.0, logger=logger)
        
        if not data:
            if logger:
                logger.warning(f"NewsAPI returned no data for {symbol}")
            return None
            
        if data.get("status") != "ok":
            if logger:
                logger.warning(f"NewsAPI error for {symbol}: {data.get('message', 'unknown error')}")
            return None
        
        arts = data.get("articles") or []
        
        if logger:
            logger.info(f"NewsAPI returned {len(arts)} articles for {symbol}")
        
        for art in arts:
            title = (art.get("title") or "").strip()
            if not title:
                continue
            when = art.get("publishedAt")
            src = (art.get("source") or {}).get("name")
            url = art.get("url")
            desc = art.get("description") or ""
            
            if logger:
                logger.info(f"Found news for {symbol}: {title[:50]}...")
            
            return {"title": title, "when": when, "source": src, "url": url, "description": desc}
        
        return None
        
    except Exception as e:
        if logger:
            logger.error(f"NewsAPI exception for {symbol}: {str(e)}")
        return None

def _yahoo_rss_news(symbol: str, logger=None) -> Optional[Dict[str, Any]]:
    """Fallback: Get news from Yahoo Finance RSS (no API key needed)."""
    try:
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
        
        if logger:
            logger.info(f"Trying Yahoo RSS for {symbol}")
        
        from urllib.request import urlopen, Request
        req = Request(url, headers={"User-Agent": "ci-digest/1.0"})
        with urlopen(req, timeout=10.0) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        
        # Simple RSS parsing
        import re
        items = re.findall(r'<item>(.*?)</item>', raw, re.DOTALL)
        
        for item in items[:3]:  # Check first 3 items
            title_match = re.search(r'<title>(.*?)</title>', item)
            link_match = re.search(r'<link>(.*?)</link>', item)
            pubdate_match = re.search(r'<pubDate>(.*?)</pubDate>', item)
            
            if title_match:
                title = title_match.group(1).strip()
                # Clean CDATA
                title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                
                url = link_match.group(1) if link_match else None
                when = pubdate_match.group(1) if pubdate_match else None
                
                if logger:
                    logger.info(f"Yahoo RSS found for {symbol}: {title[:50]}...")
                
                return {
                    "title": title,
                    "url": url,
                    "when": when,
                    "source": "Yahoo Finance",
                    "description": ""
                }
        
        return None
        
    except Exception as e:
        if logger:
            logger.warning(f"Yahoo RSS failed for {symbol}: {str(e)}")
        return None

# ----------------------- Prices -----------------------

def _alpha_daily(symbol: str, logger=None) -> Tuple[List[str], List[float]]:
    """Daily prices via Alpha Vantage (equities/commodities). Returns (dates, closes)."""
    if not ALPHA_KEY:
        if logger:
            logger.warning("Alpha Vantage API key not configured, trying Stooq fallback")
        return _stooq_daily(symbol, logger)
    
    try:
        from urllib.parse import urlencode
        qs = urlencode({
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "compact",
            "apikey": ALPHA_KEY,
        })
        url = f"https://www.alphavantage.co/query?{qs}"
        
        if logger:
            logger.info(f"Fetching prices for {symbol} from Alpha Vantage")
        
        data = _http_get_json(url, timeout=30.0, logger=logger)
        
        if not data:
            if logger:
                logger.warning(f"Alpha Vantage returned no data for {symbol}, trying Stooq")
            return _stooq_daily(symbol, logger)
        
        # Check for rate limit or error
        if "Note" in data or "Information" in data:
            if logger:
                logger.warning(f"Alpha Vantage rate limit for {symbol}: {data.get('Note', data.get('Information', ''))}")
            return _stooq_daily(symbol, logger)
        
        ts = data.get("Time Series (Daily)")
        if not isinstance(ts, dict):
            if logger:
                logger.warning(f"Alpha Vantage unexpected format for {symbol}, trying Stooq")
            return _stooq_daily(symbol, logger)
        
        keys = sorted(ts.keys())
        dates: List[str] = []
        closes: List[float] = []
        
        for k in keys[-120:]:
            row = ts.get(k) or {}
            ac = row.get("5. adjusted close") or row.get("4. close")
            try:
                price = float(str(ac).replace(",", ""))
                dates.append(k)
                closes.append(price)
            except Exception:
                continue
        
        if logger and len(closes) > 0:
            logger.info(f"Alpha Vantage success for {symbol}: {len(closes)} prices, latest={closes[-1]:.2f}")
        
        return dates, closes
        
    except Exception as e:
        if logger:
            logger.error(f"Alpha Vantage exception for {symbol}: {str(e)}, trying Stooq")
        return _stooq_daily(symbol, logger)

def _coingecko_price(symbol: str, id_hint: Optional[str], logger=None) -> Optional[Dict[str, Any]]:
    """Minimal CoinGecko price call via market data endpoint (public)."""
    try:
        if not id_hint:
            id_hint = COINGECKO_IDS.get(symbol)
        if not id_hint:
            if logger:
                logger.warning(f"No CoinGecko ID for {symbol}")
            return None
        
        url = f"https://api.coingecko.com/api/v3/coins/{id_hint}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false"
        
        if logger:
            logger.info(f"Fetching crypto data for {symbol} from CoinGecko")
        
        data = _http_get_json(url, timeout=20.0, logger=logger)
        
        if not data:
            if logger:
                logger.warning(f"CoinGecko returned no data for {symbol}")
            return None
        
        m = data.get("market_data") or {}
        price = (m.get("current_price") or {}).get("usd")
        pct_1d = (m.get("price_change_percentage_24h"))
        pct_1w = (m.get("price_change_percentage_7d"))
        pct_1m = (m.get("price_change_percentage_30d"))
        pct_ytd = (m.get("price_change_percentage_ytd"))
        low_52w = (m.get("low_52w") or {}).get("usd")  # may be missing
        high_52w = (m.get("high_52w") or {}).get("usd")
        
        if logger and price:
            logger.info(f"CoinGecko success for {symbol}: price=${price:.2f}, 1d={pct_1d:.1f}%")
        
        return {"price": price, "pct_1d": pct_1d, "pct_1w": pct_1w, "pct_1m": pct_1m, "pct_ytd": pct_ytd,
                "low_52w": low_52w, "high_52w": high_52w}
    except Exception as e:
        if logger:
            logger.error(f"CoinGecko exception for {symbol}: {str(e)}")
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
    logger.info("=== Starting NextGen digest build ===")
    logger.info(f"Environment: NEWSAPI_KEY={'set' if NEWSAPI_KEY else 'not set'}, ALPHA_KEY={'set' if ALPHA_KEY else 'not set'}")
    
    assets = _load_watchlist()  # PRESERVES ORDER
    logger.info(f"Loaded {len(assets)} assets from watchlist")
    
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
        logger.info(f"Engine news not available (this is okay): {e}")
        # Continue without engine news - we'll use NewsAPI/other sources

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    for i, a in enumerate(assets):
        sym = a["symbol"]
        name = a["name"]
        cat  = a["category"]
        
        logger.info(f"Processing {i+1}/{len(assets)}: {sym} ({cat})")

        # --------- Headline (prefer engine; otherwise NewsAPI/Yahoo/CoinGecko) ----------
        headline = None; h_url = None; h_source = None; h_when = None; desc = ""
        
        m = engine_news.get(sym)
        if m and m.get("title"):
            headline = m["title"]; h_url = m.get("url"); h_source = m.get("source")
            h_when = m.get("when"); desc = m.get("description") or ""
            logger.info(f"  Using engine news for {sym}")
        else:
            # Try NewsAPI first
            if NEWSAPI_KEY:
                r = _news_headline_via_newsapi(sym, name, logger)
                if r and r.get("title"):
                    headline = r["title"]; h_url = r.get("url"); h_source = r.get("source"); 
                    h_when = r.get("when"); desc = r.get("description") or ""
                    logger.info(f"  Using NewsAPI news for {sym}")
            
            # Fallback to Yahoo RSS if no NewsAPI result
            if not headline:
                r = _yahoo_rss_news(sym, logger)
                if r and r.get("title"):
                    headline = r["title"]; h_url = r.get("url"); h_source = r.get("source")
                    h_when = r.get("when"); desc = r.get("description") or ""
                    logger.info(f"  Using Yahoo RSS news for {sym}")

        # Enforce 7-day cutoff on articles (skip if older)
        if h_when:
            pub_dt = _parse_iso(h_when)
            if pub_dt and pub_dt < seven_days_ago:
                logger.info(f"  News for {sym} is too old (>7 days), skipping")
                headline = None; h_url = None; h_source = None; h_when = None; desc = ""

        # --------- Pricing ----------
        price = None; pct_1d = pct_1w = pct_1m = pct_ytd = None
        low_52w = high_52w = None
        
        if cat in ("equity", "etf_index", "commodity"):
            dt, cl = _alpha_daily(sym, logger)
            if cl:
                price = cl[-1]
                if len(cl) >= 2: 
                    pct_1d = ((cl[-1]/cl[-2])-1.0)*100.0
                if len(cl) >= 6: 
                    pct_1w = ((cl[-1]/cl[-6])-1.0)*100.0
                if len(cl) >= 22: 
                    pct_1m = ((cl[-1]/cl[-22])-1.0)*100.0
                # crude YTD estimate (first trading day this year)
                ytd_idx = max(0, len(cl)-1-130)  # fallback
                if cl and ytd_idx < len(cl):
                    pct_ytd = ((cl[-1]/cl[ytd_idx])-1.0)*100.0
                if len(cl) >= 252:
                    low_52w, high_52w = min(cl[-252:]), max(cl[-252:])
                else:
                    low_52w, high_52w = min(cl), max(cl) if cl else (None, None)
                
                logger.info(f"  Price data for {sym}: ${price:.2f}, 1d={pct_1d:.1f}%" if pct_1d else f"  Price data for {sym}: ${price:.2f}")
            else:
                logger.warning(f"  No price data for {sym}")
                failed += 1
                
        elif cat == "crypto":
            cg = _coingecko_price(sym, a.get("coingecko_id"), logger)
            if cg and cg.get("price") is not None:
                price = cg["price"]; pct_1d = cg.get("pct_1d"); pct_1w = cg.get("pct_1w"); 
                pct_1m = cg.get("pct_1m"); pct_ytd = cg.get("pct_ytd")
                low_52w = cg.get("low_52w"); high_52w = cg.get("high_52w")
            else:
                logger.warning(f"  No crypto data for {sym}")
                failed += 1

        if pct_1d is not None:
            if pct_1d >= 0: up += 1
            else: down += 1

        # Calculate range percentage for the 52-week range bar
        range_pct = 50.0  # default
        if price and low_52w and high_52w and high_52w > low_52w:
            range_pct = ((price - low_52w) / (high_52w - low_52w)) * 100.0

        enriched.append({
            **a,
            "price": price,
            "pct_1d": pct_1d, "pct_1w": pct_1w, "pct_1m": pct_1m, "pct_ytd": pct_ytd,
            "low_52w": low_52w, "high_52w": high_52w, "range_pct": range_pct,
            "headline": headline, "news_url": h_url, "source": h_source, "when": h_when, "description": desc,
        })

    logger.info(f"=== Data collection complete: {len(enriched)} assets, {up} up, {down} down, {failed} failed ===")

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
    
    logger.info(f"Found {len(heroes_breaking)} breaking news items")

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
            logger.info(f"Found {len(chosen)} hero news items for section {sec}")

    # ----------------- Summary + render -----------------

    now_c = _ct_now()
    summary = {
        "as_of_ct": now_c,
        "up_count": up, "down_count": down,
        "heroes_breaking": heroes_breaking,
        "heroes_by_section": heroes_by_section,
        "data_quality": {
            "successful_entities": len(enriched) - failed,
            "failed_entities": failed,
            "total_entities": len(assets),
        },
    }

    logger.info("=== Rendering email HTML ===")
    html = render_email(summary, enriched)
    logger.info(f"=== HTML generated: {len(html)} characters ===")
    
    return html
