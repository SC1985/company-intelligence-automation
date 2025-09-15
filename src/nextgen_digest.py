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
import random

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
            hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
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

def _http_get_text(url: str, timeout: float = 15.0, logger=None) -> Optional[str]:
    """Get plain text/HTML response."""
    try:
        from urllib.request import urlopen, Request
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        if logger:
            logger.warning(f"HTTP GET text failed: {str(e)}")
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

# Map commodity ETFs to their underlying commodities
COMMODITY_MAP = {
    "GLD": {"name": "Gold", "unit": "oz", "symbol": "GOLD"},
    "SLV": {"name": "Silver", "unit": "oz", "symbol": "SILVER"},
    "USO": {"name": "WTI Crude Oil", "unit": "barrel", "symbol": "WTI"},
    "UNG": {"name": "Natural Gas", "unit": "MMBtu", "symbol": "NATGAS"},
    "CPER": {"name": "Copper", "unit": "lb", "symbol": "COPPER"},
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

# ----------------------- Commodity Price Fetching -----------------------

def _fetch_commodity_prices(logger=None) -> Dict[str, Dict[str, Any]]:
    """Fetch actual commodity spot prices from various sources."""
    prices = {}
    
    # Try fetching from Alpha Vantage if available
    if ALPHA_KEY:
        # Gold and Silver from Alpha Vantage CURRENCY_EXCHANGE_RATE
        for metal, code in [("GOLD", "XAU"), ("SILVER", "XAG")]:
            try:
                url = f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency={code}&to_currency=USD&apikey={ALPHA_KEY}"
                data = _http_get_json(url, logger=logger)
                if data and "Realtime Currency Exchange Rate" in data:
                    rate_data = data["Realtime Currency Exchange Rate"]
                    price = float(rate_data.get("5. Exchange Rate", 0))
                    if price > 0:
                        prices[metal] = {
                            "price": price,
                            "unit": "oz",
                            "name": "Gold" if metal == "GOLD" else "Silver"
                        }
                        if logger:
                            logger.info(f"Got {metal} price from Alpha Vantage: ${price:.2f}/oz")
            except Exception as e:
                if logger:
                    logger.warning(f"Failed to get {metal} from Alpha Vantage: {e}")
    
    # Try fetching from YFinance symbols with ENHANCED percentage calculations
    commodity_symbols = {
        "GOLD": "GC=F",  # Gold futures
        "SILVER": "SI=F",  # Silver futures
        "WTI": "CL=F",  # WTI Crude futures
        "NATGAS": "NG=F",  # Natural Gas futures
        "COPPER": "HG=F",  # Copper futures
    }
    
    try:
        import yfinance as yf
        for commodity, symbol in commodity_symbols.items():
            if commodity not in prices:  # Skip if already have price
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    
                    # Get enough history for all calculations
                    hist = ticker.history(period="1mo")  # Get 1 month for 1W and 1M calculations
                    
                    if not hist.empty:
                        current_price = float(hist['Close'].iloc[-1])
                        
                        # Calculate 1D percentage change
                        pct_1d = 0
                        if len(hist) >= 2:
                            pct_1d = ((hist['Close'].iloc[-1] / hist['Close'].iloc[-2]) - 1) * 100
                        
                        # Calculate 1W percentage change (5 trading days)
                        pct_1w = 0
                        if len(hist) >= 6:
                            pct_1w = ((hist['Close'].iloc[-1] / hist['Close'].iloc[-6]) - 1) * 100
                        
                        # Calculate 1M percentage change (22 trading days)
                        pct_1m = 0
                        if len(hist) >= 22:
                            pct_1m = ((hist['Close'].iloc[-1] / hist['Close'].iloc[-22]) - 1) * 100
                        
                        # Calculate YTD percentage change
                        pct_ytd = 0
                        current_year = datetime.now().year
                        hist_ytd = ticker.history(period="ytd")
                        if not hist_ytd.empty and len(hist_ytd) > 1:
                            # Get first trading day of the year
                            first_price_ytd = hist_ytd['Close'].iloc[0]
                            pct_ytd = ((current_price / first_price_ytd) - 1) * 100
                        
                        # Get 52-week data
                        hist_year = ticker.history(period="1y")
                        low_52w = float(hist_year['Low'].min()) if not hist_year.empty else current_price
                        high_52w = float(hist_year['High'].max()) if not hist_year.empty else current_price
                        
                        prices[commodity] = {
                            "price": current_price,
                            "pct_1d": pct_1d,
                            "pct_1w": pct_1w,
                            "pct_1m": pct_1m,
                            "pct_ytd": pct_ytd,
                            "low_52w": low_52w,
                            "high_52w": high_52w,
                            "unit": COMMODITY_MAP.get(commodity, {}).get("unit", "unit"),
                            "name": COMMODITY_MAP.get(commodity, {}).get("name", commodity)
                        }
                        
                        if logger:
                            logger.info(f"Got {commodity} from yfinance: ${current_price:.2f}, 1D={pct_1d:.1f}%, 1W={pct_1w:.1f}%, 1M={pct_1m:.1f}%, YTD={pct_ytd:.1f}%")
                except Exception as e:
                    if logger:
                        logger.warning(f"Failed to get {commodity} from yfinance: {e}")
    except ImportError:
        if logger:
            logger.warning("yfinance not available for commodity prices")
    
    # Fallback: scrape from public sources (example with gold)
    if "GOLD" not in prices:
        try:
            # This is a simplified example - in production you'd want more robust scraping
            import re
            html = _http_get_text("https://www.kitco.com/market/", logger=logger)
            if html:
                # Look for gold price pattern (this is very fragile and just an example)
                match = re.search(r'Gold.*?\$([0-9,]+\.[0-9]+)', html)
                if match:
                    price_str = match.group(1).replace(',', '')
                    prices["GOLD"] = {
                        "price": float(price_str),
                        "unit": "oz",
                        "name": "Gold",
                        # Set percentages to 0 if we can't calculate them
                        "pct_1d": 0,
                        "pct_1w": 0,
                        "pct_1m": 0,
                        "pct_ytd": 0
                    }
                    if logger:
                        logger.info(f"Scraped GOLD price: ${price_str}/oz")
        except Exception as e:
            if logger:
                logger.warning(f"Failed to scrape gold price: {e}")
    
    return prices

# ----------------------- YFinance Fallback -----------------------

def _yfinance_daily(symbol: str, logger=None) -> Tuple[List[str], List[float]]:
    """Get daily prices using yfinance (already in requirements.txt)."""
    try:
        import yfinance as yf
        
        if logger:
            logger.info(f"Trying yfinance for {symbol}")
        
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="6mo")  # Get 6 months of data
        
        if hist.empty:
            if logger:
                logger.warning(f"yfinance returned no data for {symbol}")
            return [], []
        
        dates = []
        closes = []
        
        for date, row in hist.iterrows():
            dates.append(date.strftime("%Y-%m-%d"))
            closes.append(float(row['Close']))
        
        if logger and len(closes) > 0:
            logger.info(f"yfinance success for {symbol}: {len(closes)} prices, latest=${closes[-1]:.2f}")
        
        return dates, closes
        
    except Exception as e:
        if logger:
            logger.warning(f"yfinance failed for {symbol}: {str(e)}")
        return [], []

# ----------------------- Stooq with proper symbol formatting -----------------------

def _stooq_daily(symbol: str, logger=None) -> Tuple[List[str], List[float]]:
    """Get daily prices from Stooq (free, no API key needed)."""
    try:
        # Stooq requires .US suffix for US stocks/ETFs
        stooq_symbol = symbol.lower()
        if not stooq_symbol.endswith('.us'):
            stooq_symbol = stooq_symbol + '.us'
        
        url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
        
        if logger:
            logger.info(f"Trying Stooq for {symbol} as {stooq_symbol}")
        
        from urllib.request import urlopen, Request
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=15.0) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        
        lines = raw.strip().split("\n")
        if len(lines) < 2:
            if logger:
                logger.warning(f"Stooq returned no data for {stooq_symbol}")
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
            logger.info(f"Stooq success for {symbol}: {len(closes)} prices, latest=${closes[-1]:.2f}")
        
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
        # Try both symbol and company name
        q = f'"{symbol}" OR "{name}"'
        url = f"https://newsapi.org/v2/everything?q={q}&pageSize=5&sortBy=publishedAt&language=en&apiKey={NEWSAPI_KEY}"
        
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
            if not title or "[Removed]" in title:
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
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10.0) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        
        # Simple RSS parsing
        import re
        items = re.findall(r'<item>(.*?)</item>', raw, re.DOTALL)
        
        for item in items[:3]:  # Check first 3 items
            title_match = re.search(r'<title>(.*?)</title>', item)
            link_match = re.search(r'<link>(.*?)</link>', item)
            pubdate_match = re.search(r'<pubDate>(.*?)</pubDate>', item)
            desc_match = re.search(r'<description>(.*?)</description>', item)
            
            if title_match:
                title = title_match.group(1).strip()
                # Clean CDATA
                title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                title = title.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                
                url = link_match.group(1) if link_match else None
                when = pubdate_match.group(1) if pubdate_match else None
                desc = desc_match.group(1) if desc_match else ""
                desc = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', desc)
                desc = desc.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                
                if logger:
                    logger.info(f"Yahoo RSS found for {symbol}: {title[:50]}...")
                
                return {
                    "title": title,
                    "url": url,
                    "when": when,
                    "source": "Yahoo Finance",
                    "description": desc[:200] if desc else ""
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
            logger.warning("Alpha Vantage API key not configured, trying yfinance")
        return _yfinance_daily(symbol, logger)
    
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
                logger.warning(f"Alpha Vantage returned no data for {symbol}, trying yfinance")
            return _yfinance_daily(symbol, logger)
        
        # Check for rate limit or error
        if "Note" in data or "Information" in data:
            if logger:
                logger.warning(f"Alpha Vantage rate limit for {symbol}: {data.get('Note', data.get('Information', ''))}, trying yfinance")
            return _yfinance_daily(symbol, logger)
        
        if "Error Message" in data:
            if logger:
                logger.warning(f"Alpha Vantage error for {symbol}: {data.get('Error Message', '')}, trying yfinance")
            return _yfinance_daily(symbol, logger)
        
        ts = data.get("Time Series (Daily)")
        if not isinstance(ts, dict):
            if logger:
                logger.warning(f"Alpha Vantage unexpected format for {symbol}, trying yfinance")
            return _yfinance_daily(symbol, logger)
        
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
            logger.info(f"Alpha Vantage success for {symbol}: {len(closes)} prices, latest=${closes[-1]:.2f}")
        
        if not closes:
            if logger:
                logger.warning(f"Alpha Vantage parsed no prices for {symbol}, trying yfinance")
            return _yfinance_daily(symbol, logger)
        
        return dates, closes
        
    except Exception as e:
        if logger:
            logger.error(f"Alpha Vantage exception for {symbol}: {str(e)}, trying yfinance")
        return _yfinance_daily(symbol, logger)

def _coingecko_price(symbol: str, id_hint: Optional[str], logger=None) -> Optional[Dict[str, Any]]:
    """Enhanced CoinGecko price call with YTD calculation fallback."""
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
        pct_ytd = (m.get("price_change_percentage_1y_in_currency") or {}).get("usd")  # Try 1y as proxy
        
        # If YTD is still None, try to calculate it from price history
        if pct_ytd is None:
            try:
                # Fetch historical price from Jan 1 of current year
                current_year = datetime.now().year
                jan1 = f"01-01-{current_year}"
                hist_url = f"https://api.coingecko.com/api/v3/coins/{id_hint}/history?date={jan1}&localization=false"
                
                if logger:
                    logger.info(f"Fetching YTD baseline for {symbol} from CoinGecko history")
                
                hist_data = _http_get_json(hist_url, timeout=20.0, logger=logger)
                if hist_data and "market_data" in hist_data:
                    jan1_price = (hist_data["market_data"].get("current_price") or {}).get("usd")
                    if jan1_price and price:
                        pct_ytd = ((price / jan1_price) - 1) * 100
                        if logger:
                            logger.info(f"Calculated YTD for {symbol}: {pct_ytd:.1f}%")
            except Exception as e:
                if logger:
                    logger.warning(f"Failed to calculate YTD for {symbol}: {e}")
        
        low_52w = (m.get("low_52w") or {}).get("usd")  # may be missing
        high_52w = (m.get("high_52w") or {}).get("usd")
        
        if logger and price:
            logger.info(f"CoinGecko success for {symbol}: price=${price:.2f}, 1d={pct_1d:.1f}%, YTD={pct_ytd:.1f}%" if pct_ytd else f"CoinGecko success for {symbol}: price=${price:.2f}, 1d={pct_1d:.1f}%")
        
        return {"price": price, "pct_1d": pct_1d, "pct_1w": pct_1w, "pct_1m": pct_1m, "pct_ytd": pct_ytd,
                "low_52w": low_52w, "high_52w": high_52w}
    except Exception as e:
        if logger:
            logger.error(f"CoinGecko exception for {symbol}: {str(e)}")
        return None

# ----------------------- Hero Scoring -----------------------

_BREAKING_KWS = {
    "urgent": ["breaking", "just in", "alert", "exclusive", "developing"],
    "major": ["announces", "launches", "unveils", "reveals", "reports", "surges", "plunges", "soars", "crashes", "jumps", "spikes"],
    "earnings": ["earnings", "revenue", "profit", "beat", "miss", "guidance", "quarterly"],
    "deal": ["acquisition", "merger", "buyout", "partnership", "deal", "buys", "sells"],
    "reg": ["sec", "fda", "approval", "investigation", "lawsuit", "ruling", "regulatory"],
}
_BACKUP_KWS = {
    "analysis": ["analysis", "outlook", "forecast", "expects", "prediction"],
    "market": ["market", "stocks", "trading", "investors", "wall street", "nasdaq", "s&p"],
    "sector": ["tech", "ai", "crypto", "energy", "healthcare", "semiconductor", "bitcoin", "ethereum"],
}

def _score_headline(headline: str, published: Optional[datetime]) -> Tuple[int, int]:
    bl = headline.lower()
    breaking, backup = 0, 0
    
    # Check breaking keywords
    for kw in _BREAKING_KWS["urgent"]:   
        if kw in bl: breaking += 25
    for kw in _BREAKING_KWS["major"]:    
        if kw in bl: breaking += 20
    for kw in _BREAKING_KWS["earnings"]: 
        if kw in bl: breaking += 18
    for kw in _BREAKING_KWS["deal"]:     
        if kw in bl: breaking += 18
    for kw in _BREAKING_KWS["reg"]:      
        if kw in bl: breaking += 15
    
    # Check backup keywords
    for group, kws in _BACKUP_KWS.items():
        for kw in kws:
            if kw in bl:
                backup += 8 if group == "analysis" else 10 if group == "market" else 9
    
    # Recency boost
    if published:
        try:
            hours_ago = (datetime.now(timezone.utc) - published).total_seconds() / 3600
            if hours_ago < 2:   
                breaking += 20
                backup += 20
            elif hours_ago < 6: 
                breaking += 15
                backup += 15
            elif hours_ago < 12:
                breaking += 10
                backup += 10
            elif hours_ago < 24:
                breaking += 5
                backup += 5
        except:
            pass
    
    # Ensure any article with keywords gets at least some score
    if breaking == 0 and backup > 0:
        breaking = backup // 2  # Give it half the backup score as breaking score
    
    return breaking, backup

# ----------------------- Main -----------------------

async def build_nextgen_html(logger) -> str:
    logger.info("=== Starting NextGen digest build ===")
    logger.info(f"Environment: NEWSAPI_KEY={'set' if NEWSAPI_KEY else 'not set'}, ALPHA_KEY={'set' if ALPHA_KEY else 'not set'}")
    
    assets = _load_watchlist()  # PRESERVES ORDER
    logger.info(f"Loaded {len(assets)} assets from watchlist")
    
    # Fetch commodity prices once
    commodity_prices = _fetch_commodity_prices(logger)
    logger.info(f"Fetched {len(commodity_prices)} commodity prices")
    
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
    
    # Collect all news items for later hero selection
    all_news_items = []

    for i, a in enumerate(assets):
        sym = a["symbol"]
        name = a["name"]
        cat  = a["category"]
        
        logger.info(f"Processing {i+1}/{len(assets)}: {sym} ({cat})")

        # --------- Headline (prefer engine; otherwise NewsAPI/Yahoo) ----------
        headline = None; h_url = None; h_source = None; h_when = None; desc = ""
        
        # For commodities, try to get commodity-specific news
        if cat == "commodity" and sym in COMMODITY_MAP:
            commodity_name = COMMODITY_MAP[sym]["name"]
            # Try news for the actual commodity
            r = _news_headline_via_newsapi(commodity_name, commodity_name, logger) if NEWSAPI_KEY else None
            if r and r.get("title"):
                headline = r["title"]; h_url = r.get("url"); h_source = r.get("source")
                h_when = r.get("when"); desc = r.get("description") or ""
                logger.info(f"  Using commodity news for {commodity_name}")
        
        # Standard news fetching
        if not headline:
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
        commodity_unit = None
        commodity_display_name = None
        
        if cat == "commodity" and sym in COMMODITY_MAP:
            # Use actual commodity prices
            commodity_key = COMMODITY_MAP[sym]["symbol"]
            commodity_data = commodity_prices.get(commodity_key, {})
            
            if commodity_data:
                price = commodity_data.get("price")
                pct_1d = commodity_data.get("pct_1d")
                pct_1w = commodity_data.get("pct_1w")
                pct_1m = commodity_data.get("pct_1m")
                pct_ytd = commodity_data.get("pct_ytd")
                low_52w = commodity_data.get("low_52w")
                high_52w = commodity_data.get("high_52w")
                commodity_unit = commodity_data.get("unit", COMMODITY_MAP[sym]["unit"])
                commodity_display_name = COMMODITY_MAP[sym]["name"]
                
                logger.info(f"  Using commodity price for {commodity_display_name}: ${price:.2f}/{commodity_unit}, 1D={pct_1d:.1f}%, 1W={pct_1w:.1f}%, 1M={pct_1m:.1f}%, YTD={pct_ytd:.1f}%" if price and pct_1d is not None else f"  No commodity price for {commodity_display_name}")
            else:
                # Fallback to ETF price if commodity price not available
                dt, cl = _alpha_daily(sym, logger)
                if not cl:
                    dt, cl = _stooq_daily(sym, logger)
                
                if cl:
                    price = cl[-1]
                    # Calculate percentages for ETF fallback
                    if len(cl) >= 2: 
                        pct_1d = ((cl[-1]/cl[-2])-1.0)*100.0
                    if len(cl) >= 6: 
                        pct_1w = ((cl[-1]/cl[-6])-1.0)*100.0
                    if len(cl) >= 22: 
                        pct_1m = ((cl[-1]/cl[-22])-1.0)*100.0
                    
                    # FIXED YTD calculation for ETF fallback
                    current_year = datetime.now().year
                    current_date = datetime.now()
                    
                    # Find the index for the first trading day of the year
                    ytd_idx = None
                    for idx, date_str in enumerate(dt):
                        try:
                            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                            if date_obj.year == current_year:
                                ytd_idx = idx
                                break
                        except:
                            continue
                    
                    if ytd_idx is not None and ytd_idx < len(cl):
                        pct_ytd = ((cl[-1]/cl[ytd_idx])-1.0)*100.0
                    
                    # 52-week range
                    if len(cl) >= 252:
                        low_52w, high_52w = min(cl[-252:]), max(cl[-252:])
                    elif cl:
                        low_52w, high_52w = min(cl), max(cl)
                    
                    logger.info(f"  Fallback to ETF price for {sym}: ${price:.2f}")
                else:
                    logger.warning(f"  No price data for commodity {sym}")
                    failed += 1
                
        elif cat in ("equity", "etf_index"):
            # Try Alpha Vantage first (with yfinance fallback)
            dt, cl = _alpha_daily(sym, logger)
            
            # If still no data, try Stooq as last resort
            if not cl:
                dt, cl = _stooq_daily(sym, logger)
            
            if cl:
                price = cl[-1]
                if len(cl) >= 2: 
                    pct_1d = ((cl[-1]/cl[-2])-1.0)*100.0
                if len(cl) >= 6: 
                    pct_1w = ((cl[-1]/cl[-6])-1.0)*100.0
                if len(cl) >= 22: 
                    pct_1m = ((cl[-1]/cl[-22])-1.0)*100.0
                
                # FIXED YTD calculation
                current_year = datetime.now().year
                
                # Find the index for the first trading day of the year
                ytd_idx = None
                for idx, date_str in enumerate(dt):
                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                        if date_obj.year == current_year:
                            ytd_idx = idx
                            break
                    except:
                        continue
                
                if ytd_idx is not None and ytd_idx < len(cl):
                    pct_ytd = ((cl[-1]/cl[ytd_idx])-1.0)*100.0
                else:
                    # If we don't have data from the start of the year, use the oldest available
                    if cl and len(cl) > 1:
                        pct_ytd = ((cl[-1]/cl[0])-1.0)*100.0
                
                # Calculate 52-week range
                if len(cl) >= 252:
                    low_52w, high_52w = min(cl[-252:]), max(cl[-252:])
                elif cl:
                    low_52w, high_52w = min(cl), max(cl)
                
                logger.info(f"  Price data for {sym}: ${price:.2f}, 1d={pct_1d:.1f}%, YTD={pct_ytd:.1f}%" if pct_1d and pct_ytd else f"  Price data for {sym}: ${price:.2f}")
            else:
                logger.warning(f"  No price data for {sym} from any source")
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

        asset_data = {
            **a,
            "price": price,
            "pct_1d": pct_1d, "pct_1w": pct_1w, "pct_1m": pct_1m, "pct_ytd": pct_ytd,
            "low_52w": low_52w, "high_52w": high_52w, "range_pct": range_pct,
            "headline": headline, "news_url": h_url, "source": h_source, "when": h_when, "description": desc,
            "commodity_unit": commodity_unit,  # Add unit for commodities
            "commodity_display_name": commodity_display_name,  # Add display name
        }
        
        enriched.append(asset_data)
        
        # Collect news item for hero selection
        if headline:
            all_news_items.append({
                "asset": asset_data,
                "title": headline,
                "url": h_url or f"https://finance.yahoo.com/quote/{sym}/news",
                "source": h_source,
                "when": h_when,
                "description": desc,
                "category": cat,
                "symbol": sym
            })

    logger.info(f"=== Data collection complete: {len(enriched)} assets, {up} up, {down} down, {failed} failed ===")
    logger.info(f"=== Total news items collected: {len(all_news_items)} ===")

    # ----------------- Build hero lists -----------------

    # Score ALL news items for breaking potential
    breaking_candidates: List[Tuple[int, Dict[str, Any]]] = []
    section_candidates: Dict[str, List[Tuple[int, Dict[str, Any]]]] = {
        "etf_index": [], "equity": [], "commodity": [], "crypto": []
    }

    for item in all_news_items:
        title = item["title"]
        pub = _parse_iso(item["when"]) if item["when"] else None
        
        # Skip old articles
        if pub and pub < seven_days_ago:
            continue
        
        b_score, g_score = _score_headline(title, pub)
        
        logger.info(f"  Scored '{title[:50]}...': breaking={b_score}, general={g_score}")
        
        # Lower threshold to 10 for breaking news to ensure we get some
        if b_score > 10:
            breaking_candidates.append((b_score, item))
        
        # Add to section candidates
        if g_score > 5:
            sec = item["category"]
            if sec in section_candidates:
                section_candidates[sec].append((g_score, item))

    # Sort and select top breaking news
    breaking_candidates.sort(key=lambda x: x[0], reverse=True)
    heroes_breaking = []
    
    # Take top 2 breaking news items (or whatever we have)
    for score, item in breaking_candidates[:2]:
        heroes_breaking.append({
            "title": item["title"],
            "url": item["url"],
            "source": item["source"],
            "when": item["when"],
            "description": item["description"],
        })
        logger.info(f"Selected breaking news (score={score}): {item['title'][:50]}...")
    
    if not heroes_breaking and all_news_items:
        # If no breaking news qualified, take the 2 most recent articles
        logger.info("No breaking news found, using most recent articles instead")
        sorted_by_date = sorted(all_news_items, 
                               key=lambda x: _parse_iso(x["when"]) if x["when"] else datetime.min.replace(tzinfo=timezone.utc), 
                               reverse=True)
        for item in sorted_by_date[:2]:
            heroes_breaking.append({
                "title": item["title"],
                "url": item["url"],
                "source": item["source"],
                "when": item["when"],
                "description": item["description"],
            })
            logger.info(f"Selected recent news: {item['title'][:50]}...")
    
    logger.info(f"Final breaking news count: {len(heroes_breaking)}")

    # Select section heroes
    heroes_by_section: Dict[str, List[Dict[str, Any]]] = {}
    for sec, candidates in section_candidates.items():
        candidates.sort(key=lambda x: x[0], reverse=True)
        chosen = []
        seen_titles = set()
        
        for score, item in candidates[:5]:  # Check more candidates
            if len(chosen) >= 3:
                break
            
            t = item["title"].strip()
            if not t or t in seen_titles:
                continue
            
            # Don't duplicate breaking news in sections
            if any(h["title"] == t for h in heroes_breaking):
                continue
                
            seen_titles.add(t)
            chosen.append({
                "title": t,
                "url": item["url"],
                "source": item["source"],
                "when": item["when"],
                "description": item["description"],
            })
            logger.info(f"Selected {sec} hero (score={score}): {t[:50]}...")
        
        if chosen:
            heroes_by_section[sec] = chosen
            logger.info(f"Final {sec} hero count: {len(chosen)}")

    # ----------------- Summary + render -----------------

    now_c = _ct_now()
    summary = {
        "as_of_ct": now_c,
        "up_count": up, "down_count": down,
        "heroes_breaking": heroes_breaking,  # This is what the renderer expects
        "heroes_by_section": heroes_by_section,
        "data_quality": {
            "successful_entities": len(enriched) - failed,
            "failed_entities": failed,
            "total_entities": len(assets),
        },
    }

    logger.info(f"=== Summary prepared ===")
    logger.info(f"  Breaking heroes: {len(heroes_breaking)}")
    logger.info(f"  Section heroes: {sum(len(v) for v in heroes_by_section.values())} total")
    
    logger.info("=== Rendering email HTML ===")
    html = render_email(summary, enriched)
    logger.info(f"=== HTML generated: {len(html)} characters ===")
    
    return html
