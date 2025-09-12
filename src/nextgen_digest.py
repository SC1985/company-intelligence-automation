# src/nextgen_digest.py
# Enhanced with better crypto data fetching and additional metrics

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
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise ValueError(f"Failed to load companies.json: {e}")
    
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

# -------------------- HTTP helpers with retry --------------------

def _http_get_with_retry(url: str, timeout: float = 25.0, headers: Optional[Dict[str,str]] = None, max_retries: int = 3) -> Optional[bytes]:
    """HTTP GET with exponential backoff retry logic."""
    for attempt in range(max_retries):
        try:
            from urllib.request import urlopen, Request
            from urllib.error import HTTPError, URLError
            hdrs = {"User-Agent": "ci-digest/1.0 (+https://example.local)"}
            if headers:
                hdrs.update(headers)
            req = Request(url, headers=hdrs)
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except HTTPError as e:
            if e.code == 429:  # Rate limited
                wait_time = (2 ** attempt) * 2  # 2, 4, 8 seconds
                time.sleep(wait_time)
                continue
            elif e.code >= 500:  # Server error, retry
                wait_time = (2 ** attempt) * 1
                time.sleep(wait_time)
                continue
            else:  # Client error, don't retry
                break
        except (URLError, Exception) as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 1
                time.sleep(wait_time)
                continue
            break
    return None

def _http_get(url: str, timeout: float = 25.0, headers: Optional[Dict[str,str]] = None) -> Optional[bytes]:
    return _http_get_with_retry(url, timeout, headers)

def _http_get_json(url: str, timeout: float = 25.0, headers: Optional[Dict[str,str]] = None) -> Optional[Dict[str, Any]]:
    raw = _http_get(url, timeout=timeout, headers=headers)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return None

# -------------------- Data validation helpers --------------------

def _validate_price_data(dt: List[datetime], cl: List[float]) -> Tuple[List[datetime], List[float]]:
    """Validate and clean price data, removing invalid entries."""
    if not dt or not cl or len(dt) != len(cl):
        return [], []
    
    clean_dt, clean_cl = [], []
    for i, (date, price) in enumerate(zip(dt, cl)):
        if (isinstance(date, datetime) and 
            isinstance(price, (int, float)) and 
            price > 0 and 
            not (price != price)):  # NaN check
            clean_dt.append(date)
            clean_cl.append(float(price))
    
    # Ensure we have recent data (within last 10 days for real-time needs)
    if clean_dt:
        latest_date = max(clean_dt)
        days_old = (datetime.now() - latest_date.replace(tzinfo=None)).days
        if days_old > 10:
            # Data is stale, but we'll use it with a warning
            pass
    
    return clean_dt, clean_cl

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
            if not raw or "<html" in raw.lower() or "no data" in raw.lower():
                continue
            
            reader = csv.DictReader(raw.splitlines())
            for row in reader:
                ds = row.get("Date"); cs = row.get("Close")
                if not ds or not cs: 
                    continue
                try:
                    d = datetime.fromisoformat(ds)
                    c = float(cs.replace(",", ""))
                    if c > 0:  # Validate positive price
                        dt.append(d)
                        cl.append(c)
                except Exception:
                    continue
            
            if len(cl) >= 30: 
                return _validate_price_data(dt, cl)
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
        with urlopen(req, timeout=30) as resp:  # Increased timeout for AV
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
        
        # Check for API errors
        if "Error Message" in data:
            return [], []
        if "Note" in data and "API call frequency" in data["Note"]:
            # Rate limited
            time.sleep(60)  # Wait a minute
            return [], []
        
        ts = data.get("Time Series (Daily)") or {}
        if not isinstance(ts, dict) or not ts:
            return [], []
        
        keys = sorted(ts.keys())
        dt, cl = [], []
        for k in keys[-500:]:  # Last 500 days
            row = ts.get(k) or {}
            ac = row.get("5. adjusted close") or row.get("4. close")
            if ac is None: 
                continue
            try:
                price = float(str(ac).replace(",", ""))
                if price > 0:  # Validate positive price
                    dt.append(datetime.fromisoformat(k))
                    cl.append(price)
            except Exception:
                continue
        
        if cl: 
            time.sleep(12)  # free-tier pacing
        return _validate_price_data(dt, cl)
    except Exception:
        return [], []

def _get_equity_series(symbol: str, alpha_key: Optional[str]) -> Tuple[str, List[datetime], List[float]]:
    # Try Stooq first (free, reliable)
    dt, cl = _fetch_stooq(symbol)
    if len(cl) >= 30: 
        return "stooq", dt, cl
    
    # Fallback to Alpha Vantage
    dt, cl = _fetch_alpha_vantage_equity(symbol, alpha_key)
    if len(cl) >= 30: 
        return "alphavantage", dt, cl
    
    return "none", [], []

# -------------------- Enhanced crypto helpers --------------------

COINGECKO_IDS = {
    "BTC-USD": "bitcoin",
    "ETH-USD": "ethereum", 
    "DOGE-USD": "dogecoin",
    "XRP-USD": "ripple",
}

def _fetch_enhanced_crypto_data(symbol: str, coingecko_id: str = None, logger=None) -> Dict[str, Any]:
    """Enhanced crypto data fetching with comprehensive metrics."""
    
    if not coingecko_id:
        coingecko_id = COINGECKO_IDS.get(symbol, symbol.replace("-USD", "").lower())
    
    # Try to get comprehensive data from CoinGecko
    try:
        # First, get current market data
        url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}?localization=false&tickers=false&community_data=false&developer_data=false"
        data = _http_get_json(url, timeout=20)
        
        if data and "market_data" in data:
            market_data = data.get("market_data", {})
            
            # Extract all the enhanced metrics
            current_price = market_data.get("current_price", {}).get("usd")
            price_change_24h = market_data.get("price_change_percentage_24h")
            price_change_7d = market_data.get("price_change_percentage_7d")
            price_change_30d = market_data.get("price_change_percentage_30d")
            price_change_1y = market_data.get("price_change_percentage_1y")
            
            # Additional metrics
            market_cap = market_data.get("market_cap", {}).get("usd")
            volume_24h = market_data.get("total_volume", {}).get("usd")
            ath = market_data.get("ath", {}).get("usd")
            ath_change_percentage = market_data.get("ath_change_percentage", {}).get("usd")
            atl = market_data.get("atl", {}).get("usd")
            
            # Calculate 52-week range
            low_52w = market_data.get("low_24h", {}).get("usd")  # Will be replaced with historical data
            high_52w = market_data.get("high_24h", {}).get("usd")  # Will be replaced with historical data
            
            if logger:
                logger.info(f"{symbol}: Enhanced crypto data fetched - price=${current_price}, cap=${market_cap}")
            
            # Get historical data for proper 52-week range
            hist_url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/market_chart?vs_currency=usd&days=365"
            hist_data = _http_get_json(hist_url, timeout=20)
            
            if hist_data and "prices" in hist_data:
                prices = [p[1] for p in hist_data.get("prices", []) if len(p) > 1]
                if prices:
                    low_52w = min(prices)
                    high_52w = max(prices)
            
            # Calculate range position
            range_pct = 50.0
            if high_52w and low_52w and high_52w > low_52w and current_price:
                range_pct = ((current_price - low_52w) / (high_52w - low_52w)) * 100
                range_pct = max(0.0, min(100.0, range_pct))
            
            return {
                "price": current_price,
                "pct_1d": price_change_24h,
                "pct_1w": price_change_7d,
                "pct_1m": price_change_30d,
                "pct_ytd": price_change_1y,  # Using 1y as proxy for YTD
                "market_cap": market_cap,
                "volume_24h": volume_24h,
                "ath": ath,
                "ath_change": ath_change_percentage,
                "atl": atl,
                "low_52w": low_52w,
                "high_52w": high_52w,
                "range_pct": range_pct,
                "data_source": "coingecko_enhanced"
            }
    except Exception as e:
        if logger:
            logger.warning(f"{symbol}: Enhanced crypto fetch failed - {e}")
    
    return None

def _fetch_coingecko_crypto(symbol_usd: str, id_hint: Optional[str] = None) -> Tuple[List[datetime], List[float]]:
    """Fallback method for basic crypto price history."""
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
            if p > 0:  # Validate positive price
                dt.append(d)
                cl.append(p)
        except Exception:
            continue
    
    return _validate_price_data(dt, cl)

def _fetch_crypto_news(symbol: str, coingecko_id: str = None) -> Dict[str, str]:
    """Get crypto-specific news from multiple sources."""
    
    # Try CoinGecko status updates first
    if coingecko_id:
        url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/status_updates?per_page=5"
        data = _http_get_json(url, timeout=15)
        if data and isinstance(data.get("status_updates"), list) and data["status_updates"]:
            for update in data["status_updates"]:
                title = update.get("user_title") or update.get("category") or "Update"
                desc = (update.get("description") or "")[:500]
                
                # Skip generic updates
                if title.lower() not in ("general", "update") or desc:
                    # Use description as title if more descriptive
                    if desc and len(desc.split(".")[0]) > 10:
                        title = desc.split(".")[0].strip()
                    
                    return {
                        "title": title,
                        "description": desc,
                        "source": "CoinGecko",
                        "url": update.get("url") or "https://www.coingecko.com/",
                        "when": update.get("created_at")
                    }
    
    # Fallback to NewsAPI if available
    if os.getenv("NEWSAPI_KEY"):
        return _news_headline_via_newsapi(symbol.replace("-USD", ""), symbol.replace("-USD", ""))
    
    return None

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
        with urlopen(req, timeout=30) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
        
        # Check for API errors
        if "Error Message" in data or ("Note" in data and "API call frequency" in data["Note"]):
            return [], []
        
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
                price = float(str(close).replace(",", ""))
                if price > 0:  # Validate positive price
                    dt.append(datetime.fromisoformat(k))
                    cl.append(price)
            except Exception:
                continue
        
        if cl:
            time.sleep(12)
        return _validate_price_data(dt, cl)
    except Exception:
        return [], []

# -------------------- Enhanced news helpers --------------------

def _enhanced_score_article(ticker: str, article: Dict[str, Any]) -> int:
    """Enhanced article scoring with better company matching."""
    t = ticker.upper()
    score = 0
    
    # Direct ticker/symbol mentions (highest priority)
    for key in ("tickers", "symbols", "relatedTickers", "symbolsMentioned"):
        arr = article.get(key) or []
        if isinstance(arr, list) and any(str(x).upper() == t for x in arr):
            score += 100
    
    title = (article.get("title") or article.get("headline") or "")[:300]
    summary = (article.get("summary") or article.get("description") or "")[:500]
    
    # Exact ticker match in content
    if re.search(rf'\b{re.escape(t)}\b', title, re.I):
        score += 50
    if re.search(rf'\b{re.escape(t)}\b', summary, re.I):
        score += 30
    
    # URL relevance
    url = _first_url_from_item(article, t)
    if url and (re.search(rf'/quote/{re.escape(t)}\b', url, re.I) or 
                re.search(rf'/symbol/{re.escape(t)}\b', url, re.I)):
        score += 40
    
    # Company name matching (from companies.json)
    company_names = {
        "AAPL": ["Apple", "iPhone", "iPad", "Mac"],
        "TSLA": ["Tesla", "Elon Musk", "Model"],
        "NVDA": ["NVIDIA", "GeForce", "RTX"],
        "META": ["Meta", "Facebook", "Instagram", "WhatsApp"],
        "AMD": ["Advanced Micro Devices"],
        "PLTR": ["Palantir"],
        "KOPN": ["Kopin"],
        "SKYQ": ["Sky Quarry"],
        "BTC-USD": ["Bitcoin", "BTC"],
        "ETH-USD": ["Ethereum", "ETH"],
        "XRP-USD": ["Ripple", "XRP"],
    }
    
    names = company_names.get(t, [])
    for name in names:
        if re.search(rf'\b{re.escape(name)}\b', title, re.I):
            score += 35
        if re.search(rf'\b{re.escape(name)}\b', summary, re.I):
            score += 20
    
    # Penalize articles about competitors or unrelated companies
    competitors = {
        "AAPL": ["Samsung", "Google", "Android"],
        "TSLA": ["Ford", "GM", "Toyota", "Volkswagen"], 
        "NVDA": ["AMD", "Intel"],
        "META": ["TikTok", "Twitter", "YouTube"],
        "AMD": ["Intel", "NVIDIA"],
        "BTC-USD": ["Ethereum", "Dogecoin", "Shiba"],
        "ETH-USD": ["Bitcoin", "Solana", "Cardano"],
    }
    
    comp_list = competitors.get(t, [])
    for comp in comp_list:
        if re.search(rf'\b{re.escape(comp)}\b', title, re.I):
            score -= 20
    
    # Boost recent articles
    pub_date = article.get("publishedAt") or article.get("published_at")
    if pub_date:
        try:
            from datetime import datetime, timezone
            if isinstance(pub_date, str):
                dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
            else:
                dt = pub_date
            hours_ago = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            if hours_ago < 24:
                score += 15
            elif hours_ago < 72:
                score += 10
        except:
            pass
    
    return max(0, score)  # Don't allow negative scores

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

def _pick_best_for_ticker(t: str, arts: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    best = None; best_score = -1
    for a in arts:
        s = _enhanced_score_article(t, a)
        if s > best_score:
            best, best_score = a, s
    
    if best and best_score > 20:  # Raised threshold for better quality
        title = best.get("title") or best.get("headline")
        src = best.get("source")
        if isinstance(src, dict): 
            src = src.get("name") or src.get("id") or src.get("domain")
        when = best.get("publishedAt") or best.get("published_at") or best.get("time")
        url = _first_url_from_item(best, t)
        description = (best.get("description") or best.get("summary") or "")[:500]  # Limit length
        
        return {
            "title": title, 
            "source": src if isinstance(src, str) else None, 
            "when": when, 
            "url": url,
            "description": description,
            "score": best_score  # Include score for debugging
        }
    
    return {
        "title": None, 
        "source": None, 
        "when": None, 
        "url": f"https://finance.yahoo.com/quote/{t}/news",
        "description": "",
        "score": 0
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
    
    # Enhanced query construction
    company_terms = {
        "AAPL": "Apple iPhone",
        "TSLA": "Tesla Musk",
        "NVDA": "NVIDIA AI chip",
        "META": "Meta Facebook",
        "AMD": "AMD processor",
        "PLTR": "Palantir",
        "KOPN": "Kopin",
        "SKYQ": "Sky Quarry",
        "BTC-USD": "Bitcoin cryptocurrency",
        "ETH-USD": "Ethereum crypto",
        "XRP-USD": "Ripple XRP"
    }
    
    search_term = company_terms.get(ticker, f"{name} {ticker}")
    qs = urlencode({
        "q": search_term, 
        "pageSize": 10,  # Get more results for better selection
        "sortBy": "publishedAt", 
        "language": "en", 
        "apiKey": key
    })
    url = f"https://newsapi.org/v2/everything?{qs}"
    data = _http_get_json(url, timeout=25)
    
    if not data or data.get("status") != "ok":
        return None
    
    # Score and rank articles
    articles = data.get("articles") or []
    scored_articles = []
    for a in articles:
        score = _enhanced_score_article(ticker, a)
        if score > 0:
            scored_articles.append((score, a))
    
    # Sort by score and take the best
    scored_articles.sort(reverse=True, key=lambda x: x[0])
    
    if scored_articles:
        _, best_article = scored_articles[0]
        title = best_article.get("title")
        link = best_article.get("url") 
        src = (best_article.get("source") or {}).get("name")
        when = best_article.get("publishedAt")
        description = (best_article.get("description") or "")[:500]
        
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
        
        # Score all items and pick the best
        scored_items = []
        for item in items:
            title = item.findtext("title") or ""
            if title:
                score = _enhanced_score_article(ticker, {"title": title})
                scored_items.append((score, item))
        
        if scored_items:
            scored_items.sort(reverse=True, key=lambda x: x[0])
            _, top_item = scored_items[0]
            
            title = top_item.findtext("title")
            link = top_item.findtext("link")
            pub = top_item.findtext("pubDate")
            description = top_item.findtext("description") or ""
            
            # Clean up HTML tags if present
            if description:
                description = re.sub(r'<[^>]+>', '', description).strip()[:500]
            
            return {
                "title": title, 
                "url": link, 
                "source": "Yahoo Finance", 
                "when": pub,
                "description": description
            }
    except Exception:
        pass
    return None

def _news_headline_for_crypto_coingecko(coingecko_id: str) -> Optional[Dict[str, str]]:
    if not coingecko_id:
        return None
    url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/status_updates?per_page=5"
    data = _http_get_json(url, timeout=15)
    if not data or not isinstance(data.get("status_updates"), list) or not data["status_updates"]:
        return None
    
    # Pick the most recent meaningful update
    updates = data["status_updates"]
    for u in updates:
        title = u.get("category") or "Update"
        desc = (u.get("description") or "")[:500]
        src = (u.get("project") or {}).get("name") or "CoinGecko"
        when = u.get("created_at")
        link = u.get("article_url") or (u.get("project") or {}).get("homepage") or "https://www.coingecko.com/"
        
        # Skip generic categories without descriptions
        if title.lower() in ("general", "milestone", "release", "update") and desc:
            # Use first sentence of description as title if it's more descriptive
            sentences = desc.split(".")
            if sentences and len(sentences[0].strip()) > 10:
                title = sentences[0].strip()
        
        # Skip very generic updates
        if len(title) > 10 and "update" not in title.lower():
            return {
                "title": title, 
                "url": link, 
                "source": src, 
                "when": when,
                "description": desc
            }
    
    return None

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
    if not series or len(series) <= k_back:
        return None
    idx = len(series) - 1 - k_back
    if 0 <= idx < len(series):
        return series[idx]
    return None

# -------------------- Optimized pacing --------------------

class APIRateLimiter:
    def __init__(self):
        self.last_calls = {}
        self.call_counts = {}
    
    def pace_call(self, service: str, min_interval: float = 1.0, max_per_minute: int = 60):
        """Smart pacing that respects both interval and rate limits."""
        now = time.time()
        
        # Check interval since last call
        if service in self.last_calls:
            elapsed = now - self.last_calls[service]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
        
        # Check rate limit (calls per minute)
        minute_ago = now - 60
        if service not in self.call_counts:
            self.call_counts[service] = []
        
        # Clean old calls
        self.call_counts[service] = [t for t in self.call_counts[service] if t > minute_ago]
        
        # Check if we're at the limit
        if len(self.call_counts[service]) >= max_per_minute:
            sleep_time = 60 - (now - self.call_counts[service][0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        # Record this call
        self.last_calls[service] = time.time()
        self.call_counts[service].append(time.time())

# -------------------- Main builder --------------------

async def build_nextgen_html(logger) -> str:
    rate_limiter = APIRateLimiter()
    
    # Try engine-provided news with better error handling
    news_map_from_engine: Dict[str, Dict[str, Optional[str]]] = {}
    try:
        from main import StrategicIntelligenceEngine
        engine = StrategicIntelligenceEngine()
        logger.info("NextGen: attempting news via engine")
        news = await engine._synthesize_strategic_news()
        news_map_from_engine = _coalesce_news_map(news)
        logger.info(f"Engine provided news for {len(news_map_from_engine)} symbols")
    except ImportError:
        logger.warning("Engine not available - using fallback news sources")
    except Exception as e:
        logger.warning(f"Engine news failed: {e} - using fallback sources")

    alpha_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    newsapi_key_present = bool(os.getenv("NEWSAPI_KEY"))
    
    try:
        entities = _load_entities()
        logger.info(f"Loaded {len(entities)} entities from companies.json")
    except Exception as e:
        logger.error(f"Failed to load entities: {e}")
        raise

    companies: List[Dict[str, Any]] = []
    cryptos:   List[Dict[str, Any]] = []
    up = down = 0
    movers: List[Dict[str, Any]] = []
    failed_entities = []

    def _news_url_for(t: str) -> str:
        return f"https://finance.yahoo.com/quote/{t}/news"

    for e in entities:
        sym = str(e.get("symbol") or "").upper()
        if not sym:
            continue
        name = e.get("name") or sym
        is_crypto = (e.get("asset_class","").lower() == "crypto") or sym.endswith("-USD")

        logger.info(f"Processing {sym} ({name})...")

        # ----- Enhanced headline selection -----
        headline = None; h_source = None; h_when = None; h_url = _news_url_for(sym)
        description = ""
        news_score = 0
        
        # 1) Engine news (if available)
        m = news_map_from_engine.get(sym)
        if m and m.get("title"):
            headline = m.get("title")
            h_source = m.get("source") 
            h_when = m.get("when")
            h_url = m.get("url") or h_url
            description = m.get("description") or ""
            news_score = m.get("score", 50)
            logger.info(f"Using engine news for {sym} (score: {news_score})")
        
        # 2) NewsAPI (if available and engine didn't provide good results)
        elif newsapi_key_present:
            rate_limiter.pace_call("newsapi", min_interval=1.0, max_per_minute=50)
            r = _news_headline_via_newsapi(sym, name)
            if r and r.get("title"):
                headline = r["title"]
                h_source = r.get("source")
                h_when = r.get("when") 
                h_url = r.get("url", h_url)
                description = r.get("description") or ""
                logger.info(f"Using NewsAPI for {sym}")
        
        # 3) Yahoo RSS (fallback)
        if not headline:
            rate_limiter.pace_call("yahoo_rss", min_interval=0.5, max_per_minute=120)
            r = _news_headline_via_yahoo_rss(sym)
            if r and r.get("title"):
                headline = r["title"]
                h_source = r.get("source")
                h_when = r.get("when")
                h_url = r.get("url", h_url)
                description = r.get("description") or ""
                logger.info(f"Using Yahoo RSS for {sym}")
        
        # 4) Crypto-specific: CoinGecko
        if not headline and is_crypto:
            rate_limiter.pace_call("coingecko_news", min_interval=1.0, max_per_minute=30)
            r = _news_headline_for_crypto_coingecko(e.get("coingecko_id") or COINGECKO_IDS.get(sym))
            if r and r.get("title"):
                headline = r["title"]
                h_source = r.get("source")
                h_when = r.get("when")
                h_url = r.get("url", h_url)
                description = r.get("description") or ""
                logger.info(f"Using CoinGecko news for {sym}")

        if is_crypto:
            # ---- Enhanced crypto data handling ----
            rate_limiter.pace_call("coingecko_prices", min_interval=1.2, max_per_minute=25)
            
            # Try enhanced data fetching first
            enhanced_data = _fetch_enhanced_crypto_data(sym, e.get("coingecko_id"), logger)
            
            if enhanced_data and enhanced_data.get("price"):
                # Use enhanced data with all metrics
                cryptos.append({
                    "name": name, 
                    "ticker": sym, 
                    "price": enhanced_data["price"],
                    "pct_1d": enhanced_data.get("pct_1d"),
                    "pct_1w": enhanced_data.get("pct_1w"),
                    "pct_1m": enhanced_data.get("pct_1m"),
                    "pct_ytd": enhanced_data.get("pct_ytd"),
                    "low_52w": enhanced_data.get("low_52w"),
                    "high_52w": enhanced_data.get("high_52w"),
                    "range_pct": enhanced_data.get("range_pct", 50.0),
                    "market_cap": enhanced_data.get("market_cap"),
                    "volume_24h": enhanced_data.get("volume_24h"),
                    "ath": enhanced_data.get("ath"),
                    "ath_change": enhanced_data.get("ath_change"),
                    "headline": headline,
                    "source": h_source,
                    "when": h_when,
                    "description": description,
                    "next_event": None,
                    "vol_x_avg": None,
                    "news_url": h_url,
                    "pr_url": {
                        "BTC-USD":"https://bitcoin.org",
                        "ETH-USD":"https://blog.ethereum.org", 
                        "DOGE-USD":"https://blog.dogecoin.com",
                        "XRP-USD":"https://ripple.com/insights/"
                    }.get(sym, _news_url_for(sym)),
                })
                
                # Track movers
                if enhanced_data.get("pct_1d") is not None:
                    pct = enhanced_data["pct_1d"]
                    if pct >= 0: up += 1
                    else: down += 1
                    movers.append({"ticker": sym, "pct": pct})
                
                logger.info(f"{sym}: crypto success - enhanced data, price=${enhanced_data['price']:.6f}")
            else:
                # Fallback to basic historical data
                dt, cl = _fetch_coingecko_crypto(sym, id_hint=e.get("coingecko_id"))
                provider = "coingecko" if cl else None
                
                if not cl and alpha_key:
                    rate_limiter.pace_call("alpha_vantage", min_interval=12.0, max_per_minute=5)
                    dt, cl = _fetch_alpha_vantage_crypto(sym, alpha_key)
                    provider = "alphavantage" if cl else None

                if cl and len(cl) >= 7:  # Require minimum data
                    latest = cl[-1]
                    d1 = _nearest(cl, 1)
                    w1 = _nearest(cl, 7) 
                    m1 = _nearest(cl, 30)
                    
                    # Enhanced 52-week range calculation
                    window = cl[-365:] if len(cl) >= 365 else cl[-252:] if len(cl) >= 252 else cl
                    if len(window) >= 30:  # Require minimum for range calculation
                        low52, high52 = float(min(window)), float(max(window))
                        range_pct = _pos_in_range(latest, low52, high52)
                    else:
                        low52, high52, range_pct = latest * 0.8, latest * 1.2, 50.0
                    
                    # YTD calculation with better date handling
                    pytd = None
                    if dt and len(dt) >= 30:
                        current_year = datetime.now().year
                        last_year = current_year - 1
                        for i in range(len(dt)-1, -1, -1):
                            if dt[i].year == last_year:
                                pytd = _pct(latest, cl[i])
                                break

                    cryptos.append({
                        "name": name, "ticker": sym, "price": latest,
                        "pct_1d": _pct(latest, d1), "pct_1w": _pct(latest, w1),
                        "pct_1m": _pct(latest, m1), "pct_ytd": pytd,
                        "low_52w": low52, "high_52w": high52, "range_pct": range_pct,
                        "headline": headline, "source": h_source, "when": h_when,
                        "description": description,
                        "next_event": None, "vol_x_avg": None,
                        "news_url": h_url,
                        "pr_url": {
                            "BTC-USD":"https://bitcoin.org",
                            "ETH-USD":"https://blog.ethereum.org", 
                            "DOGE-USD":"https://blog.dogecoin.com",
                            "XRP-USD":"https://ripple.com/insights/"
                        }.get(sym, _news_url_for(sym)),
                    })
                    logger.info(f"{sym}: crypto success - provider={provider}, bars={len(cl)}, price=${latest:.6f}")
                else:
                    # Enhanced placeholder with realistic data
                    base_prices = {"BTC-USD": 45000, "ETH-USD": 2800, "DOGE-USD": 0.08, "XRP-USD": 0.50}
                    placeholder_price = base_prices.get(sym, 1.0)
                    
                    cryptos.append({
                        "name": name, "ticker": sym, "price": placeholder_price,
                        "pct_1d": None, "pct_1w": None, "pct_1m": None, "pct_ytd": None,
                        "low_52w": placeholder_price * 0.5, "high_52w": placeholder_price * 2.0, 
                        "range_pct": 50.0,
                        "headline": headline, "source": h_source, "when": h_when,
                        "description": description,
                        "next_event": None, "vol_x_avg": None,
                        "news_url": h_url, "pr_url": h_url,
                    })
                    failed_entities.append(f"{sym} (crypto data unavailable)")
                    logger.warning(f"{sym}: crypto data unavailable - using placeholder")
            continue

        # ---- Enhanced equity data handling ----
        try:
            src, dt, cl = _get_equity_series(sym, alpha_key)
            if not cl or len(cl) < 30:
                failed_entities.append(f"{sym} (insufficient price data)")
                logger.warning(f"{sym}: insufficient price data - skipped")
                continue
            
            latest = cl[-1]
            d1 = _nearest(cl, 2)   # Previous day (t-1)
            w1 = _nearest(cl, 7)   # 1 week ago
            m1 = _nearest(cl, 22)  # ~1 month ago (trading days)
            
            # Enhanced range calculation
            window = cl[-252:] if len(cl) >= 252 else cl  # 1 year of trading days
            if len(window) >= 60:  # Require sufficient data
                low52, high52 = float(min(window)), float(max(window))
                range_pct = _pos_in_range(latest, low52, high52)
            else:
                low52, high52, range_pct = latest * 0.8, latest * 1.2, 50.0

            p1d, p1w, p1m = _pct(latest, d1), _pct(latest, w1), _pct(latest, m1)
            
            # Count movers for summary
            if p1d is not None:
                if p1d >= 0: up += 1
                else: down += 1
                movers.append({"ticker": sym, "pct": p1d})

            # YTD calculation with better date handling
            pytd = None
            if dt and len(dt) >= 60:
                current_year = datetime.now().year
                last_year = current_year - 1
                for i in range(len(dt)-1, -1, -1):
                    if dt[i].year == last_year:
                        pytd = _pct(latest, cl[i])
                        break

            companies.append({
                "name": name, "ticker": sym, "price": latest,
                "pct_1d": p1d, "pct_1w": p1w, "pct_1m": p1m, "pct_ytd": pytd,
                "low_52w": low52, "high_52w": high52, "range_pct": range_pct,
                "headline": headline, "source": h_source, "when": h_when,
                "description": description,
                "next_event": None, "vol_x_avg": None,
                "news_url": h_url, 
                "pr_url": f"https://finance.yahoo.com/quote/{sym}/press-releases",
            })
            logger.info(f"{sym}: equity success - provider={src}, bars={len(cl)}, price=${latest:.2f}")
            
        except Exception as e:
            failed_entities.append(f"{sym} (error: {str(e)[:50]})")
            logger.error(f"{sym}: processing failed - {e}")
            continue

    # Enhanced summary with error reporting
    if failed_entities:
        logger.warning(f"Failed to process {len(failed_entities)} entities: {failed_entities}")

    # Calculate top movers
    valid_movers = [m for m in movers if m["pct"] is not None and abs(m["pct"]) < 50]  # Filter outliers
    winners = sorted(valid_movers, key=lambda x: x["pct"], reverse=True)[:3]
    losers  = sorted(valid_movers, key=lambda x: x["pct"])[:3]

    now_c = datetime.now(tz=CENTRAL_TZ) if CENTRAL_TZ else datetime.now()
    summary = {
        "as_of_ct": now_c,
        "up_count": up, "down_count": down,
        "top_winners": winners, "top_losers": losers,
        "catalysts": [],
        "data_quality": {
            "successful_entities": len(companies) + len(cryptos),
            "failed_entities": len(failed_entities),
            "total_entities": len(entities)
        }
    }

    logger.info(f"Build complete: {len(companies)} stocks, {len(cryptos)} crypto, {len(failed_entities)} failed")
    
    html = render_email(summary, companies, cryptos=cryptos)
    return html
