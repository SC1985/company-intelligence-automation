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
    path = os.path.normpath(os.path.join(here, "..", "data", "watchlist.json"))
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise ValueError(f"Failed to load watchlist.json: {e}")

    if not isinstance(data, list):
        raise ValueError("watchlist.json must contain a list of entities")

    entities: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        sym = item.get("symbol")
        if not sym:
            continue
        ent = dict(item)
        ent["asset_class"] = item.get("asset_class")
        entities.append(ent)
    return entities

# -------------------- HTTP helpers with retry --------------------

def _http_get_with_retry(
    
    url: str,
    timeout: float = 25.0,
    headers: Optional[Dict[str, str]] = None,
    max_retries: int = 3,
) -> Optional[bytes]:
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
            if e.code >= 500:  # Server error, retry
                wait_time = (2 ** attempt) * 1
                time.sleep(wait_time)
                continue
            # Client error, don't retry
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
@@ -400,51 +404,51 @@ def _enhanced_score_article(ticker: str, article: Dict[str, Any]) -> int:
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
    
    # Company name matching (from watchlist.json)
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
@@ -768,51 +772,51 @@ class APIRateLimiter:

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
        logger.info(f"Loaded {len(entities)} entities from watchlist.json")
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
