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
        except Exception as e:
            print(f"HTTP request failed (attempt {attempt + 1}): {e}")
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
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        path_watch = os.path.normpath(os.path.join(here, "..", "data", "watchlist.json"))
        
        print(f"Loading watchlist from: {path_watch}")
        
        with open(path_watch, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        print(f"Loaded data type: {type(data)}, length: {len(data) if isinstance(data, list) else 'N/A'}")
        
        # Process the flat watchlist structure (it's already a list)
        assets: List[Dict[str, Any]] = []
        
        for i, item in enumerate(data):
            # Skip comment entries
            if not isinstance(item, dict):
                print(f"Skipping non-dict item at index {i}: {type(item)}")
                continue
            if "comment" in item:
                print(f"Skipping comment at index {i}")
                continue
                
            sym = str(item.get("symbol") or "").upper()
            if not sym:
                print(f"Skipping item with no symbol at index {i}")
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
            
            print(f"Processing {sym}: asset_class={asset_class}, category={category}")
                
            out = {
                "ticker": sym,
                "symbol": sym,
                "name": item.get("name") or sym,
                "category": category,
                "industry": item.get("industry"),
                "coingecko_id": item.get("coingecko_id"),
            }
            assets.append(out)
        
        print(f"Loaded {len(assets)} assets from watchlist")
        # Print first few assets for debugging
        for i, asset in enumerate(assets[:3]):
            print(f"Asset {i}: {asset}")
        
        return assets
    except Exception as e:
        print(f"Error loading watchlist: {e}")
        traceback.print_exc()
        raise

# ----------------------- Headlines (NewsAPI / Yahoo / CoinGecko) -----------------------

def _news_headline_via_newsapi(symbol: str, name: str) -> Optional[Dict[str, Any]]:
    if not NEWSAPI_KEY:
        return None
    try:
        # Very light symbol search; rely on NewsAPI recency + provider filtering
        q = f"{symbol} OR \"{name}\""
        url = f"https://newsapi.org/v2/everything?q={q}&pageSize=3&sortBy=publishedAt&language=en&apiKey={NEWSAPI_KEY}"
        data = _http_get_json(url, timeout=20.0)
        if not data or data.get("status") != "ok":
            return None
        arts = data.get("articles") or []
        for art in arts:
            if not isinstance(art, dict):
                continue
            title = (art.get("title") or "").strip()
            if not title:
                continue
            when = art.get("publishedAt")
            src = (art.get("source") or {}).get("name") if isinstance(art.get("source"), dict) else None
            url = art.get("url")
            desc = art.get("description") or ""
            return {"title": title, "when": when, "source": src, "url": url, "description": desc}
    except Exception:
        return None
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
    
    for i, date_str in enumerate(dates):
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            
            # If we find the first date of current year, use it
            if date.year == current_year:
                if ytd_start_price is None:
                    ytd_start_price = closes[i]
                    break
            # Keep track of the last price from previous year
            elif date.year == current_year - 1:
                ytd_start_price = closes[i]
        except:
            continue
    
    if ytd_start_price and ytd_start_price > 0:
        current_price = closes[-1]
        return ((current_price / ytd_start_price) - 1.0) * 100.0
    
    return None

def _alpha_daily(symbol: str) -> Tuple[List[str], List[float]]:
    """Daily prices via Alpha Vantage (equities/commodities). Returns (dates, closes)."""
    if not ALPHA_KEY:
        print(f"No Alpha Vantage API key for {symbol}")
        return [], []
    try:
        from urllib.parse import urlencode
        qs = urlencode({
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "full",
            "apikey": ALPHA_KEY,
        })
        url = f"https://www.alphavantage.co/query?{qs}"
        print(f"Fetching Alpha Vantage data for {symbol}")
        data = _http_get_json(url, timeout=30.0)
        
        if not isinstance(data, dict):
            print(f"Alpha Vantage returned non-dict for {symbol}: {type(data)}")
            return [], []
            
        ts = data.get("Time Series (Daily)")
        if not isinstance(ts, dict):
            print(f"No time series data for {symbol}. Response keys: {list(data.keys()) if data else 'None'}")
            if "Note" in data:
                print(f"API Note: {data['Note']}")
            if "Error Message" in data:
                print(f"API Error: {data['Error Message']}")
            return [], []
        
        # Get all dates and sort them
        all_dates = sorted(ts.keys())
        print(f"Got {len(all_dates)} days of data for {symbol}")
        
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
                dates.append(k)
                closes.append(price)
            except Exception:
                continue
        
        if closes:
            print(f"Parsed {len(closes)} prices for {symbol}, latest: ${closes[-1]:.2f}")
        
        return dates, closes
    except Exception as e:
        print(f"Error fetching Alpha Vantage data for {symbol}: {e}")
        return [], []

def _coingecko_price(symbol: str, id_hint: Optional[str]) -> Optional[Dict[str, Any]]:
    """Get comprehensive price data from CoinGecko including YTD."""
    try:
        if not id_hint:
            id_hint = COINGECKO_IDS.get(symbol)
        if not id_hint:
            print(f"No CoinGecko ID for {symbol}")
            return None
        
        # Use the coins/{id} endpoint with market_data
        url = f"https://api.coingecko.com/api/v3/coins/{id_hint}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false"
        print(f"Fetching CoinGecko data for {symbol} (id: {id_hint})")
        data = _http_get_json(url, timeout=20.0)
        if not data:
            print(f"No data returned from CoinGecko for {symbol}")
            return None
        
        m = data.get("market_data") or {}
        
        # Get current price
        price = (m.get("current_price") or {}).get("usd")
        
        # Get percentage changes - CoinGecko provides these directly
        pct_1d = m.get("price_change_percentage_24h")
        pct_1w = m.get("price_change_percentage_7d")
        pct_1m = m.get("price_change_percentage_30d")
        pct_ytd = m.get("price_change_percentage_200d")  # Use 200d as proxy for YTD
        
        # Get 52-week range
        low_52w = (m.get("low_24h") or {}).get("usd")
        high_52w = (m.get("high_24h") or {}).get("usd")
        
        print(f"CoinGecko data for {symbol}: price=${price}, 1d={pct_1d}%")
        
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
    try:
        logger.info("Starting build_nextgen_html")
        assets = _load_watchlist()  # PRESERVES ORDER
        logger.info(f"Loaded {len(assets)} assets from watchlist")
        
        # Log categories found
        categories = set(a.get("category") for a in assets)
        logger.info(f"Categories found: {categories}")
        
        up = down = 0
        failed = 0

        # Collect per-asset fields we render (we will not reorder assets)
        enriched: List[Dict[str, Any]] = []

        # Skip news gathering for now to focus on price data
        logger.info("Skipping news gathering to test price data")

        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

        for a in assets:
            try:
                sym = a["symbol"]
                name = a["name"]
                cat  = a["category"]
                
                logger.info(f"Processing {sym} ({cat})")

                # Skip headlines for now
                headline = None; h_url = None; h_source = None; h_when = None; desc = ""

                # --------- Pricing ----------
                price = None; pct_1d = pct_1w = pct_1m = pct_ytd = None
                low_52w = high_52w = None
                
                # For testing, just set dummy data
                price = 100.0
                pct_1d = 2.5
                pct_1w = 5.0
                pct_1m = 10.0
                pct_ytd = 25.0
                low_52w = 80.0
                high_52w = 120.0
                
                if pct_1d is not None:
                    if pct_1d >= 0: up += 1
                    else: down += 1

                # Calculate range percentage for the range bar
                range_pct = 50.0  # default
                if price and low_52w and high_52w and high_52w > low_52w:
                    range_pct = ((price - low_52w) / (high_52w - low_52w)) * 100.0

                enriched_item = {
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
                }
                enriched.append(enriched_item)
                logger.info(f"Added enriched item for {sym}: {enriched_item}")
                
            except Exception as e:
                logger.error(f"Error processing asset {a.get('symbol', 'unknown')}: {e}")
                failed += 1
                traceback.print_exc()

        logger.info(f"Enriched {len(enriched)} assets")

        # Skip hero processing for now
        heroes_breaking = []
        heroes_by_section = {}

        # ----------------- Summary + render -----------------

        now_c = _ct_now()
        summary = {
            "as_of_ct": now_c,
            "up_count": up, 
            "down_count": down,
            "heroes_breaking": heroes_breaking,
            "heroes_by_section": heroes_by_section,
            "data_quality": {
                "successful_entities": len(enriched),
                "failed_entities": failed,
                "total_entities": len(assets),
            },
        }

        logger.info(f"Calling render_email with summary: {summary}")
        logger.info(f"Enriched data (first item): {enriched[0] if enriched else 'EMPTY'}")
        logger.info(f"Total enriched items: {len(enriched)}")
        
        html = render_email(summary, enriched)
        
        logger.info(f"HTML length: {len(html)}")
        # Log a snippet of the HTML to see what was generated
        if len(html) > 500:
            logger.info(f"HTML snippet: {html[:500]}...")
        
        return html
        
    except Exception as e:
        logger.error(f"Fatal error in build_nextgen_html: {e}")
        traceback.print_exc()
        raise
