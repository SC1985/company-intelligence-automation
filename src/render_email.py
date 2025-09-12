from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Dict, List, Optional, Any, Iterable

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

CENTRAL_TZ = ZoneInfo("America/Chicago") if ZoneInfo else None

def _parse_to_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value or "").strip()
    if not s:
        return None
    if s.isdigit():
        try:
            iv = int(s)
            if iv > 10_000_000_000:
                iv //= 1000
            return datetime.fromtimestamp(iv, tz=timezone.utc)
        except Exception:
            return None
    try:
        s2 = s[:-1] + "+00:00" if s.endswith("Z") else s
        dt = datetime.fromisoformat(s2)
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(s)
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def _fmt_ct(value: Any, force_time: Optional[bool] = None, tz_suffix_policy: str = "auto") -> str:
    dt = _parse_to_dt(value) or value
    if not isinstance(dt, datetime):
        return str(value)
    try:
        dtc = dt.astimezone(CENTRAL_TZ) if CENTRAL_TZ else dt
    except Exception:
        dtc = dt
    has_time = not (dtc.hour == 0 and dtc.minute == 0 and dtc.second == 0)
    show_time = force_time if force_time is not None else has_time
    out = dtc.strftime("%m/%d/%Y %H:%M") if show_time else dtc.strftime("%m/%d/%Y")
    if tz_suffix_policy == "always":
        return out + " CST"
    if tz_suffix_policy == "auto" and show_time:
        return out + " CST"
    return out

def _safe_float(x: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        v = float(x)
        if v != v or abs(v) > 1e10:
            return default
        return v
    except Exception:
        return default

def _chip(label: str, value: Any) -> str:
    v = _safe_float(value, None)
    if v is None:
        bg, color, sign, txt = "#6B7280", "#FFFFFF", "", "--"
    else:
        if v >= 0:
            bg, color, sign = "#10B981", "#FFFFFF", "▲"
        else:
            bg, color, sign = "#EF4444", "#FFFFFF", "▼"
        txt = f"{abs(v):.1f}%"
    return (
        '<span style="background:' + bg + ';color:' + color + ';padding:5px 12px;'
        'border-radius:12px;font-size:12px;font-weight:700;display:inline-block;'
        'margin:2px 6px 4px 0;white-space:nowrap;'
        "font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">"
        + escape(label) + " " + sign + " " + txt + "</span>"
    )

SECTION_NAMES: Dict[str, str] = {
    "etf_index": "ETFs & Indices",
    "equity":    "Equities",
    "commodity": "Commodities",
    "crypto":    "Digital Assets",
}

SECTION_STYLES: Dict[str, Dict[str, str]] = {
    "equity": {
        "border": "#3B82F6", "bg": "#FAFBFC", "shadow": "rgba(59,130,246,0.06)",
        "card_border": "#93C5FD", "card_bg": "#93C5FD", "card_shadow": "rgba(147,197,253,0.15)",
        "tag_bg": "#111827", "tag_color": "#FFFFFF",
    },
    "crypto": {
        "border": "#8B5CF6", "bg": "#FAFAFC", "shadow": "rgba(139,92,246,0.06)",
        "card_border": "#C4B5FD", "card_bg": "#C4B5FD", "card_shadow": "rgba(196,181,253,0.15)",
        "tag_bg": "#111827", "tag_color": "#FFFFFF",
    },
    "etf_index": {
        "border": "#10B981", "bg": "#F0FDF4", "shadow": "rgba(16,185,129,0.06)",
        "card_border": "#70d5b3", "card_bg": "#70d5b3", "card_shadow": "rgba(112,213,179,0.15)",
        "tag_bg": "#111827", "tag_color": "#FFFFFF",
    },
    "commodity": {
        "border": "#F59E0B", "bg": "#FFFBEB", "shadow": "rgba(245,158,11,0.06)",
        "card_border": "#f9c56d", "card_bg": "#f9c56d", "card_shadow": "rgba(249,197,109,0.15)",
        "tag_bg": "#111827", "tag_color": "#FFFFFF",
    },
}

def _range_bar(pos: float, low: float, high: float) -> str:
    try:
        p = max(0.0, min(100.0, float(pos)))
    except Exception:
        p = 50.0
    return (
        '<div style="height:6px;border-radius:3px;background:#E5E7EB;position:relative;margin:10px 0;">'
        f'<div style="width:{p:.1f}%;height:6px;border-radius:3px;background:#10B981;"></div></div>'
    )

def _button(label: str, url: str, secondary: bool = False) -> str:
    bg = "#4B5563" if not secondary else "#9CA3AF"
    color = "#FFFFFF"
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        'style="display:inline-block;margin-right:8px;margin-bottom:4px;">'
        '<tr><td style="background:' + bg + ';color:' + color + ';border-radius:10px;'
        'font-size:13px;font-weight:600;padding:10px 16px;'
        "font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">"
        '<a href="' + escape(url or "#") + '" target="_blank" rel="noopener noreferrer" '
        'style="color:' + color + ';text-decoration:none;display:block;">'
        + escape(label) + ' →</a></td></tr></table>'
    )

def _render_heroes(heroes: Iterable[Dict[str, Any]]) -> str:
    out_parts: List[str] = []
    for i, h in enumerate(heroes):
        title = (h.get("title") or "").strip()
        if not title:
            continue
        url = h.get("url") or "#"
        src = h.get("source") or ""
        when = _fmt_ct(h.get("when"), force_time=False, tz_suffix_policy="never") if h.get("when") else ""
        desc = (h.get("description") or "").strip()
        label = "● BREAKING" if i == 0 else "● ALSO BREAKING"
        if len(desc) > 180:
            import re
            sentences = re.split(r'[.!?]\s+', desc)
            truncated = ""
            for s in sentences:
                if len(truncated + s) <= 160:
                    truncated += s + ". "
                else:
                    break
            desc = truncated.strip() if truncated else (desc[:177] + "…")
        meta_bits = [b for b in [src, when] if b]
        meta = " • ".join(meta_bits)
        card = (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="border-collapse:separate;margin:0 0 12px;">'
            '<tr><td style="border:1px solid #E5E7EB;border-radius:12px;overflow:hidden;">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FFFFFF;">'
            '<tr><td style="padding:18px 16px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">'
            '<div style="font-size:12px;color:#6B7280;font-weight:700;margin-bottom:6px;">' + label + '</div>'
            '<a href="' + escape(url) + '" style="text-decoration:none;color:#111827;">'
            '<div style="font-size:20px;font-weight:800;line-height:1.2;margin-bottom:8px;">'
            + escape(title) + '</div></a>'
            + ('<div style="font-size:14px;color:#374151;margin-bottom:8px;line-height:1.5;">'
               + escape(desc) + '</div>' if desc else '')
            + ('<div style="font-size:12px;color:#6B7280;">' + escape(meta) + '</div>' if meta else '')
            + '</td></tr></table></td></tr></table>'
        )
        out_parts.append(card)
    return "".join(out_parts)

def _industry_pill(text: Optional[str], section: str) -> str:
    if not text:
        return ""
    style = SECTION_STYLES.get(section, SECTION_STYLES["equity"])
    return (
        '<span style="background:' + style["tag_bg"] + ';color:' + style["tag_color"] + ';'
        'border-radius:999px;padding:3px 10px;font-size:11px;font-weight:700;'
        'margin-right:8px;display:inline-block;">' + escape(text) + '</span>'
    )

def _card_shell(inner: str, section: str) -> str:
    style = SECTION_STYLES.get(section, SECTION_STYLES["equity"])
    return (
        '<div style="border:1px solid ' + style["card_border"] + ';border-radius:14px;margin:0 0 12px;'
        'box-shadow:0 2px 8px ' + style["card_shadow"] + ';background:' + style["card_bg"] + ';">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:separate;margin:0;background:#FFFFFF;border-radius:13px;overflow:hidden;">'
        + inner + '</table></div>'
    )

def _build_asset_card(c: Dict[str, Any]) -> str:
    section = (c.get("category") or "equity").lower()
    ticker = str(c.get("ticker") or c.get("symbol") or "")
    name = c.get("name") or ticker or "Unknown"
    price_v = _safe_float(c.get("price"), None)
    if price_v is None:
        price_fmt = '<span style="color:#9CA3AF;">--</span>'
    else:
        price_fmt = '<span style="color:#111827;font-weight:700;">${:,.2f}</span>'.format(price_v)
    chips = _chip("1D", c.get("pct_1d")) + _chip("1W", c.get("pct_1w")) + _chip("1M", c.get("pct_1m")) + _chip("YTD", c.get("pct_ytd"))
    range_html = _range_bar(c.get("range_pct") or 50.0, c.get("low_52w") or 0.0, c.get("high_52w") or 0.0)
    bullets_html = ""
    headline = c.get("headline")
    source = c.get("source")
    when_fmt = _fmt_ct(c.get("when"), force_time=False, tz_suffix_policy="never") if c.get("when") else None
    if headline:
        main = headline if len(headline) <= 100 else (headline[:100] + "…")
        meta = " • ".join([x for x in [source, when_fmt] if x])
        bullets_html = (
            '<tr><td style="padding-bottom:10px;line-height:1.5;color:#374151;'
            'font-size:14px;font-weight:500;">★ ' + escape(main) + ((' (' + escape(meta) + ')') if meta else '') + '</td></tr>'
        )
    pill = _industry_pill(c.get("industry"), section)
    inner = (
        '<tr><td style="padding:20px 22px;max-height:420px;overflow:hidden;vertical-align:top;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td style="font-weight:700;font-size:17px;line-height:1.3;color:#111827;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;padding-bottom:4px;">'
        + pill + escape(name) + '</td></tr>'
        '<tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td style="font-size:13px;color:#6B7280;font-weight:600;">(' + escape(ticker) + ')</td>'
        '<td style="text-align:right;font-size:16px;">' + price_fmt + '</td></tr></table></td></tr>'
        '<tr><td style="margin:12px 0;">' + chips + '</td></tr>'
        '<tr><td>' + range_html + '</td></tr>'
        + bullets_html +
        '<tr><td style="border-top:1px solid #E5E7EB;padding-top:14px;">'
        + _button("News", c.get("news_url") or f"https://finance.yahoo.com/quote/{escape(ticker)}/news")
        + _button("Press", c.get("pr_url") or f"https://finance.yahoo.com/quote/{escape(ticker)}/press-releases", secondary=True)
        + '</td></tr>'
        '</table></td></tr>'
    )
    return _card_shell(inner, section)

def _grid(cards: List[str]) -> str:
    if not cards:
        return ""
    rows: List[str] = []
    for i in range(0, len(cards), 2):
        left = cards[i]
        right = cards[i + 1] if i + 1 < len(cards) else ""
        if right:
            rows.append(
                '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                'style="border-collapse:collapse;margin-bottom:8px;">'
                '<tr><td class="stack-col" width="50%" style="vertical-align:top;padding-right:8px;">' + left + '</td>'
                '<td class="stack-col" width="50%" style="vertical-align:top;padding-left:8px;">' + right + '</td></tr></table>'
            )
        else:
            rows.append(
                '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                'style="border-collapse:collapse;margin-bottom:8px;">'
                '<tr><td class="stack-col" style="vertical-align:top;margin:0 auto;">' + left + '</td></tr></table>'
            )
    return "".join(rows)

def _section_container(title: str, inner_html: str, section_type: str) -> str:
    style = SECTION_STYLES.get(section_type, SECTION_STYLES["equity"])
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;background:' + style["bg"] + ';'
        'border-left:4px solid ' + style["border"] + ';border-radius:16px;margin:24px 0;'
        'box-shadow:0 1px 6px ' + style["shadow"] + ';"><tr><td style="padding:28px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td class="section-title" style="font-weight:700;font-size:28px;color:#111827;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:0 0 16px 0;">'
        + escape(title) + '</td></tr><tr><td>' + inner_html + '</td></tr></table>'
        '</td></tr></table>'
    )

def render_email(summary: Dict[str, Any], assets: List[Dict[str, Any]]) -> str:
    by_section: Dict[str, List[Dict[str, Any]]] = {"etf_index": [], "equity": [], "commodity": [], "crypto": []}
    for a in assets:
        sec = (a.get("category") or "equity").lower()
        if sec not in by_section:
            by_section[sec] = []
        by_section[sec].append(a)

    breaking_html = _render_heroes(summary.get("heroes_breaking", []) or [])

    section_html_parts: List[str] = []
    for sec in ["etf_index", "equity", "commodity", "crypto"]:
        if not by_section.get(sec):
            continue
        sec_heroes = (summary.get("heroes_by_section", {}).get(sec) or [])[:3]
        sec_html = _render_heroes(sec_heroes) + _grid([_build_asset_card(x) for x in by_section[sec]])
        section_html_parts.append(_section_container(SECTION_NAMES.get(sec, sec.title()), sec_html, sec))

    as_of = _fmt_ct(summary.get("as_of_ct"), force_time=True, tz_suffix_policy="always")

    css = (
        "<style>"
        "@media only screen and (max-width: 640px) {"
        ".stack-col{display:block!important;width:100%!important;max-width:100%!important;padding:0!important;margin-bottom:16px}"
        ".section-title{font-size:36px!important;line-height:1.2!important}"
        ".chip{font-size:15px!important;padding:8px 16px!important;margin:3px 8px 5px 0!important}"
        ".section-container td{padding:20px 8px!important}"
        ".outer-padding{padding:8px 2px!important}"
        ".main-container{padding:16px 8px!important;background:#FFFFFF!important}"
        "}"
        "</style>"
    )

    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        + css + '<title>Daily Intelligence Digest</title></head>'
        '<body style="margin:0;padding:0;background:#F9FAFB;"><center style="width:100%;background:#F9FAFB;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" width="600" '
        'style="margin:0 auto;background:#FFFFFF;border-radius:16px;overflow:hidden;">'
        '<tr><td style="padding:24px 24px 12px 24px;text-align:left;">'
        '<div style="font-size:28px;font-weight:700;color:#111827;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">Daily Intelligence Digest</div>'
        '<div style="font-size:14px;color:#6B7280;margin-top:4px;">As of ' + escape(as_of) + '</div>'
        '</td></tr>'
        '<tr><td style="padding:0 24px;">' + breaking_html + '</td></tr>'
        '<tr><td style="padding:0 24px;">' + "".join(section_html_parts) + '</td></tr>'
        '<tr><td style="padding:24px;color:#6B7280;font-size:12px;text-align:center;">You are receiving this digest based on your watchlist.</td></tr>'
        '</table></center></body></html>'
    )
