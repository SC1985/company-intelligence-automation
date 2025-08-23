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
    except Exception as e:
        # Fallback to minimal dataset if file loading fails
        import logging
        logging.getLogger("ci-entrypoint").warning(f"Failed to load companies.json: {e}, using minimal fallback")
        return [
            {"symbol": "AAPL", "name": "Apple Inc.", "asset_class": "equity"},
            {"symbol": "TSLA", "name": "Tesla Inc.", "asset_class": "equity"},
            {"symbol": "BTC-USD", "name": "Bitcoin", "asset_class": "crypto", "coingecko_id": "bitcoin"}
        ]

# -------------------- HTTP helpers with retry logic --------------------

def _http_get_with_retry(url: str, timeout: float = 25.0, headers: Optional[Dict[str,str]] = None, retries: int = 3) -> Optional[bytes]:
    """HTTP GET with exponential backoff retry logic."""
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError
    
    hdrs = {"User-Agent": "ci-digest/1.0 (+https://example.local)"}
    if headers:
        hdrs.update(headers)
    
    for attempt in range(retries):
        try:
            req = Request(url, headers=hdrs)
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (URLError, HTTPError, Exception) as e:
            if attempt == retries - 1:
                # Log final failure
                try:
                    import logging
                    logging.getLogger("ci-entrypoint").warning(f"HTTP request failed after {retries} attempts: {url} - {e}")
                except:
                    pass
                return None
            else:
                # Exponential backoff: 1s, 2s, 4s
                sleep_time = 2 ** attempt
                time.sleep(sleep_time)
    return None

def _http_get(url: str, timeout: float = 25.0, headers: Optional[Dict[str,str]] = None) -> Optional[bytes]:
    return _http_get_with_retry(url, timeout, headers, retries=2)

def _http_get_json(url: str, timeout: float = 25.0, headers: Optional[Dict[str,str]] = None) -> Optional[Dict[str, Any]]:
    raw = _http_get(url, timeout=timeout, headers=headers)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception as e:
        try:
            import logging
            logging.getLogger("ci-entrypoint").warning(f"JSON decode failed for {url}: {e}")
        except:
            pass
        return None

# -------------------- History helpers (equities) with validation --------------------

def _validate_price_series(dates: List[datetime], prices: List[float]) -> Tuple[List[datetime], List[float]]:
    """Validate and clean price series data."""
    if not dates or not prices or len(dates) != len(prices):
        return [], []
    
    # Filter out invalid data points
    valid_pairs = []
    for d, p in zip(dates, prices):
        try:
            if isinstance(d, datetime) and isinstance(p, (int, float)) and p > 0:
                valid_pairs.append((d, float(p)))
        except:
            continue
    
    if len(valid_pairs) < 5:  # Need minimum 5 data points
        return [], []
    
    # Sort by date and remove duplicates
    valid_pairs.sort(key=lambda x: x[0])
    seen_dates = set()
    cleaned = []
    for d, p in valid_pairs:
        date_key = d.date()
        if date_key not in seen_dates:
            seen_dates.add(date_key)
            cleaned.append((d, p))
    
    dates_clean, prices_clean = zip(*cleaned) if cleaned else ([], [])
    return list(dates_clean), list(prices_clean)

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
                    if c > 0:  # Validate positive price
                        dt.append(d); cl.append(c)
                except Exception:
                    continue
            
            # Validate series
            dt, cl = _validate_price_series(dt, cl)
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
        raw = _http_get(url, timeout=25)
        if not raw:
            return [], []
        
        data = json.loads(raw.decode("utf-8"))
        
        # Check for API limit error
        if "Error Message" in data or "Note" in data:
            return [], []
        
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
                d = datetime.fromisoformat(k)
                c = float(str(ac).replace(",", ""))
                if c > 0:  # Validate positive price
                    dt.append(d); cl.append(c)
            except Exception:
                continue
        
        # Validate series before sleeping (don't sleep if data is bad)
        dt, cl = _validate_price_series(dt, cl)
        if cl: 
            time.sleep(12)  # free-tier pacing only if we got data
        return dt, cl
    except Exception as e:
        try:
            import logging
            logging.getLogger("ci-entrypoint").warning(f"Alpha Vantage equity fetch failed for {symbol}: {e}")
        except:
            pass
        return [], []

def _get_equity_series(symbol: str, alpha_key: Optional[str]) -> Tuple[str, List[datetime], List[float]]:
    dt, cl = _fetch_stooq(symbol)
    if len(cl) >= 30: 
        return "stooq", dt, cl
    dt, cl = _fetch_alpha_vantage_equity(symbol, alpha_key)
    if len(cl) >= 30: 
        return "alphavantage", dt, cl
    return "none", [], []

# -------------------- History helpers (crypto) with validation --------------------

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
            if p > 0:  # Validate positive price
                dt.append(d); cl.append(p)
        except Exception:
            continue
    return _validate_price_series(dt, cl)

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
        raw = _http_get(url, timeout=25)
        if not raw:
            return [], []
        
        data = json.loads(raw.decode("utf-8"))
        
        # Check for API errors
        if "Error Message" in data or "Note" in data:
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
                d = datetime.fromisoformat(k)
                c = float(str(close).replace(",", ""))
                if c > 0:  # Validate positive price
                    dt.append(d); cl.append(c)
            except Exception:
                continue
        
        # Validate before sleeping
        dt, cl = _validate_price_series(dt, cl)
        if cl:
            time.sleep(12)
        return dt, cl
    except Exception as e:
        try:
            import logging
            logging.getLogger("ci-entrypoint").warning(f"Alpha Vantage crypto fetch failed for {symbol_usd}: {e}")
        except:
            pass
        return [], []

# -------------------- Enhanced news helpers --------------------

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

def _enhanced_score_article_for_ticker(t: str, a: Dict[str, Any]) -> int:
    """Enhanced article scoring with better relevance detection."""
    t = t.upper()
    score = 0
    
    # Direct ticker mentions in metadata (highest confidence)
    for key in ("tickers", "symbols", "relatedTickers", "symbolsMentioned"):
        arr = a.get(key) or []
        if isinstance(arr, list) and any(str(x).upper() == t for x in arr):
            score += 150
    
    title = (a.get("title") or a.get("headline") or "")[:300]
    summary = (a.get("summary") or a.get("description") or "")[:500]
    
    # Title mentions (high confidence)
    if re.search(rf'\b{re.escape(t)}\b', title, re.I):
        score += 60
        # Bonus for title prominence
        if title.upper().startswith(t):
            score += 20
    
    # Summary mentions (medium confidence) 
    if re.search(rf'\b{re.escape(t)}\b', summary, re.I):
        score += 25
        
    # URL pattern matching
    url = _first_url_from_item(a, t)
    if url and re.search(rf'/quote/{re.escape(t)}\b', url, re.I):
        score += 30
    if url and re.search(rf'/\b{re.escape(t)}\b', url, re.I):
        score += 15
    
    # Recency bonus (prefer recent articles)
    pub_date = a.get("publishedAt") or a.get("published_at") or a.get("time")
    if pub_date:
        try:
            from dateutil import parser
            pub_dt = parser.parse(str(pub_date))
            hours_old = (datetime.now(timezone.utc) - pub_dt.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            if hours_old < 24:
                score += 10  # Recent news bonus
            elif hours_old > 168:  # >1 week old
                score -= 20
        except:
            pass
    
    # Penalize articles mentioning competing tickers prominently in title
    competing_tickers = {"AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "AMD", "INTC"} - {t}
    competitor_mentions = sum(1 for comp in competing_tickers if re.search(rf'\b{comp}\b', title, re.I))
    if competitor_mentions > 0:
        score -= 20 * competitor_mentions
    
    # Penalize generic market news unless ticker is specifically mentioned
    generic_terms = ["market", "stocks", "dow", "s&p", "nasdaq", "fed", "inflation"]
    if any(term in title.lower() for term in generic_terms) and not re.search(rf'\b{re.escape(t)}\b', title, re.I):
        score -= 30
    
    return max(0, score)  # Don't return negative scores

def _pick_best_for_ticker(t: str, arts: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    best = None; best_score = -1
    for a in arts:
        s = _enhanced_score_article_for_ticker(t, a)
        if s > best_score:
            best, best_score = a, s
    if best and best_score >= 10:  # Raised minimum threshold
        title = best.get("title") or best.get("headline")
        src = best.get("source")
        if isinstance(src, dict): src = src.get("name") or src.get("id") or src.get("domain")
        when = best.get("publishedAt") or best.get("published_at") or best.get("time")
        url = _first_url_from_item(best, t)
        description = best.get("description") or best.get("summary") or ""
        
        # Clean description
        if description:
            description = re.sub(r'<[^>]+>', '', description).strip()
            if len(description) > 200:
                description = description[:197] + "..."
        
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
    
    # Build better search query
    query_parts = []
    if name and len(name) > 3:
        # Use company name in quotes for exact match
        query_parts.append(f'"{name}"')
    query_parts.append(ticker)
    
    q = " OR ".join(query_parts)
    qs = urlencode({
        "q": q, 
        "pageSize": 10,  # Get more articles to choose from
        "sortBy": "publishedAt", 
        "language": "en", 
        "apiKey": key
    })
    url = f"https://newsapi.org/v2/everything?{qs}"
    data = _http_get_json(url, timeout=20)
    if not data or data.get("status") != "ok":
        return None
    
    # Score and pick best article
    articles = data.get("articles") or []
    best_article = None
    best_score = -1
    
    for a in articles:
        score = _enhanced_score_article_for_ticker(ticker, {
            "title": a.get("title"),
            "description": a.get("description"),
            "url": a.get("url"),
            "publishedAt": a.get("publishedAt"),
            "source": a.get("source")
        })
        if score > best_score:
            best_score = score
            best_article = a
    
    if best_article and best_score >= 10:
        title = best_article.get("title")
        link = best_article.get("url")
        src = (best_article.get("source") or {}).get("name")
        when = best_article.get("publishedAt")
        description = best_article.get("description") or ""
        
        # Clean description
        if description:
            description = re.sub(r'<[^>]+>', '', description).strip()
            if len(description) > 200:
                description = description[:197] + "..."
        
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
        
        # Score multiple items and pick best
        best_item = None
        best_score = -1
        
        for item in items[:5]:  # Check top 5
            title = item.findtext("title") or ""
            score = _enhanced_score_article_for_ticker(ticker, {
                "title": title,
                "description": item.findtext("description") or ""
            })
            if score > best_score:
                best_score = score
                best_item = item
        
        if best_item and best_score >= 10:
            title = best_item.findtext("title")
            link = best_item.findtext("link")
            pub = best_item.findtext("pubDate")
            description = best_item.findtext("description") or ""
            
            # Clean up HTML tags
            if description:
                description = re.sub(r'<[^>]+>', '', description).strip()
                if len(description) > 200:
                    description = description[:197] + "..."
            
            return {
                "title": title, 
                "url": link, 
                "source": "Yahoo Finance", 
                "when": pub,
                "description": description
            }
    except Exception as e:
        try:
            import logging
            logging.getLogger("ci-entrypoint").warning(f"Yahoo RSS parsing failed for {ticker}: {e}")
        except:
            pass
    return None

def _news_headline_for_crypto_coingecko(coingecko_id: str) -> Optional[Dict[str, str]]:
    if not coingecko_id:
        return None
    url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/status_updates?per_page=5"
    data = _http_get_json(url, timeout=15)
    if not data or not isinstance(data.get("status_updates"), list) or not data["status_updates"]:
        return None
    
    # Pick most recent relevant update
    updates = data["status_updates"]
    for u in updates:
        title = u.get("category") or "Update"
        desc = u.get("description") or ""
        src = (u.get("project") or {}).get("name") or "CoinGecko"
        when = u.get("created_at")
        link = u.get("article_url") or (u.get("project") or {}).get("homepage") or "https://www.coingecko.com/"
        
        # Improve title from description if generic
        if title.lower() in ("general", "milestone", "release", "update") and desc:
            sentences = desc.strip().split(".")
            if sentences and len(sentences[0]) > 10:
                title = sentences[0].strip()
        
        # Validate content quality
        if len(title) > 5 and len(desc) > 20:
            if len(desc) > 200:
                desc = desc[:197] + "..."
            
            return {
                "title": title, 
                "url": link, 
                "source": src, 
                "when": when,
                "description": desc
            }
    return None

# -------------------- Math helpers with validation --------------------

def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Safely convert value to float with validation."""
    try:
        if value is None:
            return default
        f = float(value)
        if not (-1e10 < f < 1e10):  # Sanity check for reasonable values
            return default
        return f
    except (ValueError, TypeError, OverflowError):
        return default

def _pct(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    try:
        curr = _safe_float(curr)
        prev = _safe_float(prev)
        if curr is None or prev is None or prev == 0:
            return None
        pct = (curr/prev - 1.0) * 100.0
        # Sanity check: reject impossible percentage changes
        if not (-99.9 <= pct <= 10000):  # -99.9% to +10000% seems reasonable
            return None
        return pct
    except Exception:
        return None

def _pos_in_range(price, low, high) -> float:
    try:
        price = _safe_float(price, 0)
        low = _safe_float(low, 0)
        high = _safe_float(high, 0)
        if price is None or low is None or high is None:
            return 50.0
        if high <= low: 
            return 50.0
        pos = max(0.0, min(100.0, (price - low)/(high - low)*100.0))
        return pos
    except Exception:
        return 50.0

def _nearest(series: List[float], k_back: int) -> Optional[float]:
    if not series or k_back < 0:
        return None
    idx = len(series) - 1 - k_back
    if 0 <= idx < len(series):
        return _safe_float(series[idx])
    return None

# -------------------- Main builder with better error handling --------------------

async def build_nextgen_html(logger) -> str:
    """Build NextGen HTML with comprehensive error handling and data validation."""
    
    # Enhanced logging
    start_time = time.time()
    logger.info("=== NextGen Digest Build Started ===")
    
    try:
        # Try engine-provided news with fallback
        news_map_from_engine: Dict[str, Dict[str, Optional[str]]] = {}
        try:
            from main import StrategicIntelligenceEngine
            engine = StrategicIntelligenceEngine()
            logger.info("NextGen: fetching news via engine")
            news = await engine._synthesize_strategic_news()
            news_map_from_engine = _coalesce_news_map(news)
            logger.info(f"Engine provided news for {len(news_map_from_engine)} entities")
        except Exception as e:
            logger.warning(f"Engine news fetch failed: {e}, continuing with direct news fetch")
            news_map_from_engine = {}

        alpha_key = os.getenv("ALPHA_VANTAGE_API_KEY") or None
        newsapi_key_present = bool(os.getenv("NEWSAPI_KEY"))
        
        try:
            entities = _load_entities()
            logger.info(f"Loaded {len(entities)} entities")
        except Exception as e:
            logger.error(f"Failed to load entities: {e}")
            raise

        companies: List[Dict[str, Any]] = []
        cryptos: List[Dict[str, Any]] = []
        up = down = 0
        movers: List[Dict[str, Any]] = []
        failed_entities = []

        def _news_url_for(t: str) -> str:
            return f"https://finance.yahoo.com/quote/{t}/news"

        # Improved pacing with logging
        last_call_ts = 0.0
        api_call_count = 0
        def _pace_with_logging(min_interval=1.5, call_type="API"):
            nonlocal last_call_ts, api_call_count
            now = time.time()
            delta = now - last_call_ts
            if delta < min_interval:
                sleep_time = min_interval - delta
                logger.debug(f"Pacing {call_type}: sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
            last_call_ts = time.time()
            api_call_count += 1

        for entity_idx, e in enumerate(entities):
            sym = str(e.get("symbol") or "").upper()
            if not sym:
                logger.warning(f"Entity {entity_idx} has no symbol, skipping")
                continue
            
            name = e.get("name") or sym
            is_crypto = (e.get("asset_class","").lower() == "crypto") or sym.endswith("-USD")
            
            logger.info(f"Processing {entity_idx+1}/{len(entities)}: {sym} ({name})")

            # ----- Enhanced headline selection -----
            headline = None; h_source = None; h_when = None; h_url = _news_url_for(sym)
            description = ""
            news_attempts = 0
            
            try:
                # 1) Engine news (cached)
                m = news_map_from_engine.get(sym)
                if m and m.get("title"):
                    headline = m.get("title")
                    h_source = m.get("source") 
                    h_when = m.get("when")
                    h_url = m.get("url") or h_url
                    description = m.get("description") or ""
                    logger.debug(f"Using engine news for {sym}")
                else:
                    # 2) NewsAPI (with retry logic)
                    if newsapi_key_present and not headline:
                        _pace_with_logging(0.8, "NewsAPI")
                        news_attempts += 1
                        r = _news_headline_via_newsapi(sym, name)
                        if r and r.get("title"):
                            headline = r["title"]
                            h_source = r.get("source")
                            h_when = r.get("when")
                            h_url = r.get("url", h_url)
                            description = r.get("description") or ""
                            logger.debug(f"Using NewsAPI result for {sym}")
                    
                    # 3) Yahoo RSS fallback
                    if not headline:
                        _pace_with_logging(0.8, "Yahoo RSS")
                        news_attempts += 1
                        r = _news_headline_via_yahoo_rss(sym)
                        if r and r.get("title"):
                            headline = r["title"]
                            h_source = r.get("source")
                            h_when = r.get("when")
                            h_url = r.get("url", h_url)
                            description = r.get("description") or ""
                            logger.debug(f"Using Yahoo RSS result for {sym}")
                    
                    # 4) Crypto-specific: CoinGecko
                    if not headline and is_crypto:
                        _pace_with_logging(0.8, "CoinGecko news")
                        news_attempts += 1
                        r = _news_headline_for_crypto_coingecko(e.get("coingecko_id") or COINGECKO_IDS.get(sym))
                        if r and r.get("title"):
                            headline = r["title"]
                            h_source = r.get("source")
                            h_when = r.get("when")
                            h_url = r.get("url", h_url)
                            description = r.get("description") or ""
                            logger.debug(f"Using CoinGecko news for {sym}")
                
                if not headline:
                    logger.warning(f"No news found for {sym} after {news_attempts} attempts")
            
            except Exception as e:
                logger.warning(f"News fetch failed for {sym}: {e}")

            # ----- Price data processing with validation -----
            if is_crypto:
                try:
                    # Crypto price fetching with fallbacks
                    _pace_with_logging(1.5, "CoinGecko price")
                    dt, cl = _fetch_coingecko_crypto(sym, id_hint=e.get("coingecko_id"))
                    provider = "coingecko" if cl else None
                    
                    if not cl and alpha_key:
                        _pace_with_logging(12.0, "Alpha Vantage crypto")
                        dt, cl = _fetch_alpha_vantage_crypto(sym, alpha_key)
                        provider = "alphavantage" if cl else None

                    if cl and len(cl) >= 5:  # Minimum data requirement
                        latest = cl[-1]
                        d1 = _nearest(cl, 1)
                        w1 = _nearest(cl, 7) 
                        m1 = _nearest(cl, 30)
                        
                        # 52-week range (or available range)
                        window = cl[-365:] if len(cl) >= 365 else cl
                        if len(window) >= 5:
                            low52, high52 = min(window), max(window)
                            range_pct = _pos_in_range(latest, low52, high52)
                        else:
                            low52 = high52 = latest
                            range_pct = 50.0
                        
                        # YTD calculation with validation
                        pytd = None
                        if dt and len(dt) > 30:  # Need sufficient history
                            try:
                                last_year = dt[-1].year - 1
                                for i in range(len(dt)-1, max(0, len(dt)-400), -1):  # Look back max 400 days
                                    if dt[i].year == last_year:
                                        pytd = _pct(latest, cl[i])
                                        break
                            except Exception as e:
                                logger.debug(f"YTD calculation failed for {sym}: {e}")

                        crypto_data = {
                            "name": name, "ticker": sym, "price": latest,
                            "pct_1d": _pct(latest, d1), "pct_1w": _pct(latest, w1),
                            "pct_1m": _pct(latest, m1), "pct_ytd": pytd,
                            "low_52w": low52, "high_52w": high52, "range_pct": range_pct,
                            "headline": headline, "source": h_source, "when": h_when,
                            "description": description,
                            "next_event": None, "vol_x_avg": None,
                            "news_url": h_url,
                            "pr_url": {
                                "BTC-USD":"https://bitcoin.org/en/press",
                                "ETH-USD":"https://blog.ethereum.org",
                                "DOGE-USD":"https://dogecoin.com/",
                                "XRP-USD":"https://ripple.com/insights/"
                            }.get(sym, h_url),
                        }
                        
                        cryptos.append(crypto_data)
                        logger.info(f"{sym}: crypto success via {provider}, bars={len(cl)}, price=${latest:.6f}")
                        
                    else:
                        # Crypto placeholder
                        cryptos.append({
                            "name": name, "ticker": sym, "price": 0.0,
                            "pct_1d": None, "pct_1w": None, "pct_1m": None, "pct_ytd": None,
                            "low_52w": 0.0, "high_52w": 0.0, "range_pct": 50.0,
                            "headline": headline, "source": h_source, "when": h_when,
                            "description": description,
                            "next_event": None, "vol_x_avg": None,
                            "news_url": h_url, "pr_url": h_url,
                        })
                        logger.warning(f"{sym}: crypto data unavailable, using placeholder")
                        failed_entities.append(f"{sym} (crypto data)")
                        
                except Exception as e:
                    logger.error(f"Crypto processing failed for {sym}: {e}")
                    failed_entities.append(f"{sym} (crypto error)")
                continue

            # ----- Equity processing -----
            try:
                src, dt, cl = _get_equity_series(sym, alpha_key)
                if not cl or len(cl) < 5:
                    logger.warning(f"{sym}: insufficient equity data, skipping")
                    failed_entities.append(f"{sym} (equity data)")
                    continue
                
                # Validated price calculations
                latest = cl[-1]
                d1 = _nearest(cl, 1) if len(cl) >= 2 else None
                w1 = _nearest(cl, 5) if len(cl) >= 6 else None  # ~1 week of trading days
                m1 = _nearest(cl, 22) if len(cl) >= 23 else None  # ~1 month of trading days
                
                # 52-week range (or 1-year trading days)
                window = cl[-252:] if len(cl) >= 252 else cl
                if len(window) >= 5:
                    low52, high52 = min(window), max(window)
                    range_pct = _pos_in_range(latest, low52, high52)
                else:
                    low52 = high52 = latest
                    range_pct = 50.0

                # Percentage calculations with validation
                p1d, p1w, p1m = _pct(latest, d1), _pct(latest, w1), _pct(latest, m1)
                
                # Track movers
                if p1d is not None:
                    if p1d >= 0: 
                        up += 1
                    else: 
                        down += 1
                    movers.append({"ticker": sym, "pct": p1d})

                # YTD calculation for equities
                pytd = None
                if dt and len(dt) > 50:  # Need sufficient history
                    try:
                        last_year = dt[-1].year - 1
                        for i in range(len(dt)-1, max(0, len(dt)-300), -1):
                            if dt[i].year == last_year:
                                pytd = _pct(latest, cl[i])
                                break
                    except Exception as e:
                        logger.debug(f"Equity YTD calculation failed for {sym}: {e}")
                
                company_data = {
                    "name": name, "ticker": sym, "price": latest,
                    "pct_1d": p1d, "pct_1w": p1w, "pct_1m": p1m, "pct_ytd": pytd,
                    "low_52w": low52, "high_52w": high52, "range_pct": range_pct,
                    "headline": headline, "source": h_source, "when": h_when,
                    "description": description,
                    "next_event": None, "vol_x_avg": None,
                    "news_url": h_url, 
                    "pr_url": f"https://finance.yahoo.com/quote/{sym}/press-releases",
                }
                
                companies.append(company_data)
                logger.info(f"{sym}: equity success via {src}, bars={len(cl)}, price=${latest:.2f}, 1D={p1d:.1f}%" if p1d else f"{sym}: equity success via {src}, bars={len(cl)}, price=${latest:.2f}")
                
            except Exception as e:
                logger.error(f"Equity processing failed for {sym}: {e}")
                failed_entities.append(f"{sym} (equity error)")

        # ----- Summary generation -----
        total_entities = len(companies) + len(cryptos)
        logger.info(f"Processing complete: {total_entities} entities processed ({len(companies)} equities, {len(cryptos)} crypto)")
        logger.info(f"Market status: {up} up, {down} down")
        logger.info(f"API calls made: {api_call_count}")
        
        if failed_entities:
            logger.warning(f"Failed entities: {', '.join(failed_entities)}")

        # Top movers with validation
        winners = sorted([m for m in movers if m["pct"] is not None and m["pct"] > 0], 
                        key=lambda x: x["pct"], reverse=True)[:3]
        losers = sorted([m for m in movers if m["pct"] is not None and m["pct"] < 0], 
                       key=lambda x: x["pct"])[:3]

        now_c = datetime.now(tz=CENTRAL_TZ) if CENTRAL_TZ else datetime.now()
        summary = {
            "as_of_ct": now_c,
            "up_count": up, 
            "down_count": down,
            "top_winners": winners, 
            "top_losers": losers,
            "catalysts": [],
            "build_stats": {
                "entities_processed": total_entities,
                "api_calls": api_call_count,
                "failed_entities": len(failed_entities),
                "processing_time_seconds": round(time.time() - start_time, 1)
            }
        }

        # Generate HTML with error handling
        try:
            html = render_email(summary, companies, cryptos=cryptos)
            if not html or len(html) < 1000:  # Basic validation
                raise ValueError("Generated HTML appears invalid or too short")
            
            logger.info(f"=== Build completed successfully in {summary['build_stats']['processing_time_seconds']}s ===")
            logger.info(f"HTML length: {len(html)} characters")
            return html
            
        except Exception as e:
            logger.error(f"Email rendering failed: {e}")
            raise

    except Exception as e:
        logger.error(f"NextGen build failed: {e}")
        # Try to generate a minimal fallback HTML
        try:
            fallback_html = f"""
            <!DOCTYPE html><html><body style="margin:0;background:#0b0c10;color:#e5e7eb;padding:20px;">
            <h1>Intelligence Digest</h1>
            <p>Build failed: {str(e)}</p>
            <p>Please check logs and try again.</p>
            </body></html>
            """
            logger.warning("Generated fallback HTML due to build failure")
            return fallback_html
        except:
            # Last resort
            raise RuntimeError(f"NextGen digest build failed completely: {e}")
