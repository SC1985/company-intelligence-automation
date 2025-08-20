from datetime import datetime
from typing import Dict, Any, List

from render_email import render_email
from chartgen import sparkline_png_base64
from history_provider import compute_metrics

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

    companies: List[Dict[str, Any]] = []
    up = down = 0
    movers = []

    if isinstance(market, dict):
        for ticker, item in market.items():
            t = ticker.upper()
            meta = item.get("position_data") or item.get("meta") or {}
            name = meta.get("name") or meta.get("companyName") or t

            # Pull robust history-driven metrics (yfinance -> stooq)
            m = compute_metrics(t)
            if m.get("pct_1d") is not None:
                if m["pct_1d"] >= 0: up += 1
                else: down += 1
                movers.append({"ticker": t, "pct": m["pct_1d"]})

            spark_b64 = sparkline_png_base64(m.get("closes", [])[-21:])

            h = news_map.get(t, {})

            companies.append({
                "name": name, "ticker": t, "price": m.get("price", 0.0),
                "pct_1d": m.get("pct_1d"), "pct_1w": m.get("pct_1w"),
                "pct_1m": m.get("pct_1m"), "pct_ytd": m.get("pct_ytd"),
                "low_52w": m.get("low_52w", 0.0), "high_52w": m.get("high_52w", 0.0),
                "range_pct": m.get("range_pct", 50.0), "spark_b64": spark_b64,
                "headline": h.get("title"), "source": h.get("source"), "when": h.get("when"),
                "next_event": meta.get("earningsDate") or meta.get("nextEvent"),
                "vol_x_avg": None
            })

            logger.info(f"{t}: history provider={m.get('provider')} bars={m.get('bars')}")

    winners = sorted([m for m in movers if m["pct"] is not None], key=lambda x: x["pct"], reverse=True)[:3]
    losers  = sorted([m for m in movers if m["pct"] is not None], key=lambda x: x["pct"])[:3]

    summary = {
        "as_of_ct": datetime.now().strftime("%b %d, %Y %H:%M CT"),
        "up_count": up, "down_count": down,
        "top_winners": winners, "top_losers": losers
    }

    html = render_email(summary, companies)
    return html
