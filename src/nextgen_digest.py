# src/nextgen_digest.py
from datetime import datetime
from typing import Dict, Any, List, Optional

from render_email import render_email

def _pct_change(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    try:
        if curr is None or prev is None or prev == 0:
            return None
        return (curr / prev - 1.0) * 100.0
    except Exception:
        return None

def _nearest(closes: List[float], offset: int) -> Optional[float]:
    if not closes:
        return None
    idx = len(closes) + offset
    if 0 <= idx < len(closes):
        return closes[idx]
    return None

def _ytd_ref(dates: List[datetime], closes: List[float]) -> Optional[float]:
    if not dates or not closes:
        return None
    target_year = dates[-1].year - 1
    for i in range(len(dates) - 1, -1, -1):
        if dates[i].year == target_year:
            return closes[i]
        if dates[i].year < target_year:
            break
    return None

def _pos_in_range(price, low, high) -> float:
    try:
        price, low, high = float(price), float(low), float(high)
        if high <= low:
            return 50.0
        return max(0.0, min(100.0, (price - low) / (high - low) * 100.0))
    except Exception:
        return 50.0

def _first_url_from_item(a: Dict[str, Any], ticker: str) -> Optional[str]:
    # Try common fields first
    for k in ("url", "link", "article_url", "story_url", "source_url", "canonicalUrl"):
        v = a.get(k)
        if isinstance(v, str) and v.startswith(("http://", "https://")):
            return v
    # Some APIs nest url under 'source' or 'meta'
    for k in ("source", "meta"):
        obj = a.get(k)
        if isinstance(obj, dict):
            v = obj.get("url") or obj.get("link")
            if isinstance(v, str) and v.startswith(("http://", "https://")):
                return v
    # Fallback to Yahoo Finance news tab for the symbol
    return f"https://finance.yahoo.com/quote/{ticker}/news"

def _coalesce_news_map(news: Any) -> Dict[str, Dict[str, Optional[str]]]:
    """
    Return {TICKER: {'title': str|None, 'source': str|None, 'when': str|None, 'url': str|None}}
    Accepts:
      - dict keyed by ticker with 'top_articles' or 'articles'
      - dict with 'items' list where each entry has a 'ticker'/'symbol'
    """
    out: Dict[str, Dict[str, Optional[str]]] = {}
    if isinstance(news, dict):
        # Case A: keyed by ticker
        keyed = True
        for k, v in news.items():
            if isinstance(v, (list, dict)):
                t = str(k).upper()
                arts = []
                if isinstance(v, dict):
                    arts = v.get("top_articles") or v.get("articles") or v.get("items") or []
                elif isinstance(v, list):
                    arts = v
                if isinstance(arts, list) and arts:
                    a = arts[0]
                    title = a.get("title") or a.get("headline")
                    src = a.get("source")
                    if isinstance(src, dict):
                        src = src.get("name") or src.get("id") or src.get("domain")
                    when = a.get("publishedAt") or a.get("published_at") or a.get("time")
                    url = _first_url_from_item(a, t)
                    out[t] = {"title": title, "source": src if isinstance(src, str) else None, "when": when, "url": url}
        # Case B: flat list under 'items'
        items = news.get("items") or news.get("results") or []
        if isinstance(items, list):
            for a in items:
                t = a.get("ticker") or a.get("symbol") or (a.get("company", {}) or {}).get("ticker")
                if not t:
                    continue
                t = str(t).upper()
                if t in out:
                    continue
                title = a.get("title") or a.get("headline")
                src = a.get("source") or a.get("domain")
                if isinstance(src, dict):
                    src = src.get("name") or src.get("id") or src.get("domain")
                when = a.get("publishedAt") or a.get("published_at") or a.get("time")
                url = _first_url_from_item(a, t)
                out[t] = {"title": title, "source": src if isinstance(src, str) else None, "when": when, "url": url}
    return out

async def build_nextgen_html(logger) -> str:
    # Use the project engine
    from main import StrategicIntelligenceEngine
    engine = StrategicIntelligenceEngine()

    logger.info("NextGen: collecting market/news from engine")
    market = await engine._harvest_constellation_data()
    news = await engine._synthesize_strategic_news()
    news_map = _coalesce_news_map(news)

    companies: List[Dict[str, Any]] = []
    up = down = 0
    winners: List[Dict[str, Any]] = []
    losers: List[Dict[str, Any]] = []

    if isinstance(market, dict):
        for ticker, item in market.items():
            t = str(ticker).upper()
            meta = item.get("position_data") or item.get("meta") or {}
            name = meta.get("name") or meta.get("companyName") or t

            # Spot & timeseries (support multiple shapes)
            price = item.get("price")
            try:
                price = float(price) if price is not None else None
            except Exception:
                price = None

            closes = [float(x) for x in item.get("closes", [])] if isinstance(item.get("closes"), list) else []
            dates = item.get("dates", []) or []
            latest = closes[-1] if closes else price

            d1 = _nearest(closes, -2) if closes else None
            w1 = _nearest(closes, -6) if closes else None
            m1 = _nearest(closes, -22) if closes else None
            ytd = _ytd_ref(dates, closes) if isinstance(dates, list) and dates and closes else None

            p1d = _pct_change(latest, d1) if d1 is not None else None
            p1w = _pct_change(latest, w1) if w1 is not None else None
            p1m = _pct_change(latest, m1) if m1 is not None else None
            pytd = _pct_change(latest, ytd) if ytd is not None else None

            if p1d is not None:
                if p1d >= 0: up += 1
                else: down += 1
                winners.append({"ticker": t, "pct": p1d})
                losers.append({"ticker": t, "pct": p1d})

            # 52w markers—use provided bounds if present; else neutral
            low52 = item.get("low_52w"); high52 = item.get("high_52w")
            try:
                low52 = float(low52) if low52 is not None else 0.0
                high52 = float(high52) if high52 is not None else 0.0
            except Exception:
                low52, high52 = 0.0, 0.0

            def _range_pos(px, lo, hi):
                try:
                    return _pos_in_range(px if px is not None else 0.0, lo, hi)
                except Exception:
                    return 50.0

            range_pct = _range_pos(latest, low52, high52)

            # News URL + PR URL for CTAs
            nm = news_map.get(t, {})
            news_url = nm.get("url") or f"https://finance.yahoo.com/quote/{t}/news"
            pr_url = f"https://finance.yahoo.com/quote/{t}/press-releases"

            companies.append({
                "name": name, "ticker": t, "price": latest or 0.0,
                "pct_1d": p1d, "pct_1w": p1w, "pct_1m": p1m, "pct_ytd": pytd,
                "low_52w": low52 or 0.0, "high_52w": high52 or 0.0,
                "range_pct": range_pct,
                "headline": nm.get("title"), "source": nm.get("source"), "when": nm.get("when"),
                "next_event": meta.get("earningsDate") or meta.get("nextEvent"),
                "vol_x_avg": item.get("volume_x_30d") or item.get("volXAvg"),
                "news_url": news_url, "pr_url": pr_url,
            })

    winners = sorted([m for m in winners if m["pct"] is not None], key=lambda x: x["pct"], reverse=True)[:3]
    losers = sorted([m for m in losers if m["pct"] is not None], key=lambda x: x["pct"])[:3]

    summary = {
        "as_of_ct": datetime.now().strftime("%b %d, %Y %H:%M CT"),
        "up_count": up, "down_count": down,
        "top_winners": winners, "top_losers": losers
    }

    html = render_email(summary, companies)
    return html
