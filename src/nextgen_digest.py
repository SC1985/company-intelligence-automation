from datetime import datetime
from typing import Dict, Any, List, Optional

from render_email import render_email
from chartgen import sparkline_png_base64

def _pct_change(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    try:
        if curr is None or prev is None or prev == 0:
            return None
        return (curr/prev - 1.0) * 100.0
    except Exception:
        return None

def _nearest(closes: List[float], offset: int) -> Optional[float]:
    if not closes: return None
    idx = len(closes) + offset
    if idx < 0: return None
    return closes[idx] if 0 <= idx < len(closes) else None

def _ytd_ref(dates: List[datetime], closes: List[float]) -> Optional[float]:
    if not dates or not closes: return None
    target_year = dates[-1].year - 1
    for i in range(len(dates)-1, -1, -1):
        if dates[i].year == target_year:
            return closes[i]
        if dates[i].year < target_year:
            break
    return None

def _pos_in_range(price, low, high) -> float:
    try:
        price, low, high = float(price), float(low), float(high)
        if high <= low: return 50.0
        return max(0.0, min(100.0, (price-low)/(high-low)*100.0))
    except Exception:
        return 50.0

def _extract_series(item: Dict[str, Any]):
    dt, cl = [], []
    try:
        if "series" in item and isinstance(item["series"], list):
            from datetime import datetime as _dt
            for row in item["series"][-260:]:
                d = row.get("date") or row.get("time") or row.get("timestamp")
                c = row.get("close") or row.get("price") or row.get("adjusted_close")
                if d and c is not None:
                    try:
                        if isinstance(d, str):
                            d = _dt.fromisoformat(d.replace("Z",""))
                        elif isinstance(d, (int, float)):
                            d = _dt.fromtimestamp(d)
                        dt.append(d); cl.append(float(c))
                    except Exception:
                        continue
        elif "timeseries" in item and isinstance(item["timeseries"], dict):
            from datetime import datetime as _dt
            _d = item["timeseries"].get("date") or item["timeseries"].get("dates")
            _c = item["timeseries"].get("close") or item["timeseries"].get("closes")
            if isinstance(_d, list) and isinstance(_c, list) and len(_d)==len(_c):
                for d, c in zip(_d[-260:], _c[-260:]):
                    try:
                        if isinstance(d, str):
                            d = _dt.fromisoformat(d.replace("Z",""))
                        elif isinstance(d, (int,float)):
                            d = _dt.fromtimestamp(d)
                        dt.append(d); cl.append(float(c))
                    except Exception:
                        continue
    except Exception:
        pass
    return dt, cl

async def build_nextgen_html(logger) -> str:
    from main import StrategicIntelligenceEngine
    engine = StrategicIntelligenceEngine()

    logger.info("NextGen: collecting market/news from engine")
    market = await engine._harvest_constellation_data()
    news = await engine._synthesize_strategic_news()

    news_map = {}
    if isinstance(news, dict):
        items = news.get("items") or news.get("results") or []
        if isinstance(items, list):
            for n in items:
                t = (n.get("ticker") or n.get("symbol") or (n.get("company",{}) or {}).get("ticker"))
                if not t: continue
                t = t.upper()
                if t not in news_map:
                    news_map[t] = {
                        "title": n.get("title") or n.get("headline"),
                        "source": n.get("source") or n.get("domain"),
                        "when": n.get("published_at") or n.get("publishedAt") or n.get("time")
                    }

    companies = []
    up = down = 0
    winners = []; losers = []

    if isinstance(market, dict):
        for ticker, item in market.items():
            t = ticker.upper()
            meta = item.get("meta") or {}
            name = meta.get("name") or meta.get("companyName") or t

            dates, closes = _extract_series(item)
            if not closes:
                closes = [float(x) for x in item.get("closes", [])][-260:]
            latest = closes[-1] if closes else None
            d1 = _nearest(closes, -2)
            w1 = _nearest(closes, -6)
            m1 = _nearest(closes, -22)
            ytd = _ytd_ref(dates, closes) if dates else None

            p1d = _pct_change(latest, d1)
            p1w = _pct_change(latest, w1)
            p1m = _pct_change(latest, m1)
            pytd = _pct_change(latest, ytd)

            if p1d is not None:
                if p1d >= 0: up += 1
                else: down += 1
                winners.append({"ticker": t, "pct": p1d})
                losers.append({"ticker": t, "pct": p1d})

            low52 = min(closes[-252:]) if len(closes) >= 2 else (latest or 0.0)
            high52 = max(closes[-252:]) if len(closes) >= 2 else (latest or 0.0)
            range_pct = _pos_in_range(latest or 0.0, low52, high52)

            spark_series = closes[-21:] if closes else []
            spark_b64 = sparkline_png_base64(spark_series)

            h = news_map.get(t, {})
            companies.append({
                "name": name, "ticker": t, "price": latest or 0.0,
                "pct_1d": p1d, "pct_1w": p1w, "pct_1m": p1m, "pct_ytd": pytd,
                "low_52w": low52 or 0.0, "high_52w": high52 or 0.0,
                "range_pct": range_pct, "spark_b64": spark_b64,
                "headline": h.get("title"), "source": h.get("source"), "when": h.get("when"),
                "next_event": meta.get("nextEvent") or meta.get("earningsDate"),
                "vol_x_avg": item.get("volume_x_30d") or item.get("volXAvg")
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
