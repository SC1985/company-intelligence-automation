# src/render_email.py
# Renders the email with:
# - Top Breaking News (1–2)
# - Section order: ETFs & Indices, Equities, Commodities, Digital Assets
# - Up to 3 section-specific heroes before cards
# - Solid industry tag on each card
# - Section left borders (unchanged) + card full borders:
#     ETFs & Indices: #70d5b3
#     Commodities:    #f9c56d
#     Equities/Digital: keep existing palette
# - No Top Movers section
# - Keep mobile-friendly paddings minimal (do not increase)

from __future__ import annotations
from typing import Dict, List, Any, Iterable, Optional
from datetime import datetime, timezone
from html import escape

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

CENTRAL_TZ = ZoneInfo("America/Chicago") if ZoneInfo else None

def _parse_to_dt(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip()
    if not s:
        return None
    # epoch seconds/millis
    if s.isdigit():
        try:
            iv = int(s); 
            if iv > 10_000_000_000: iv //= 1000
            return datetime.fromtimestamp(iv, tz=timezone.utc)
        except Exception:
            pass
    try:
        s2 = s[:-1] + "+00:00" if s.endswith("Z") else s
        dt = datetime.fromisoformat(s2)
        if dt and dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(s)
        if dt and dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def _fmt_ct(value, force_time: Optional[bool] = None, tz_suffix_policy="auto") -> str:
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
    if tz_suffix_policy == "always": return out + " CST"
    if tz_suffix_policy == "auto" and show_time: return out + " CST"
    return out

def _safe_float(x, default=None):
    if x is None: return default
    try:
        v = float(x)
        if v != v or abs(v) > 1e10: return default
        return v
    except Exception:
        return default

SECTION_NAMES: Dict[str, str] = {
    "etf_index": "ETFs & Indices",
    "equity":    "Equities",
    "commodity": "Commodities",
    "crypto":    "Digital Assets",
}

# Section (left) border & card palettes
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

def _chip(label: str, value):
    v = _safe_float(value, None)
    if v is None:
        bg, color, sign, txt = "#6B7280", "#FFFFFF", "", "--"
    else:
        if v >= 0: bg, color, sign = "#10B981", "#FFFFFF", "▲"
        else:      bg, color, sign = "#EF4444", "#FFFFFF", "▼"
        txt = f"{abs(v):.1f}%"
    return (f'<span style="background:{bg};color:{color};padding:5px 12px;'
            f'border-radius:12px;font-size:12px;font-weight:700;display:inline-block;'
            f'margin:2px 6px 4px 0;white-space:nowrap;'
            f'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">'
            f'{escape(label)} {sign} {txt}</span>')

def _range_bar(pos: float, low: float, high: float) -> str:
    # simple neutral bar; green fill width = pos
    try:
        p = max(0.0, min(100.0, float(pos)))
    except Exception:
        p = 50.0
    return (f'<div style="height:6px;border-radius:3px;background:#E5E7EB;position:relative;margin:10px 0;">'
            f'<div style="width:{p:.1f}%;height:6px;border-radius:3px;background:#10B981;"></div></div>')

def _button(label: str, url: str, secondary=False) -> str:
    bg = "#4B5563" if not secondary else "#9CA3AF"
    color = "#FFFFFF"
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" style="display:inline-block;margin-right:8px;margin-bottom:4px;">'
            f'<tr><td style="background:{bg};color:{color};border-radius:10px;font-size:13px;font-weight:600;padding:10px 16px;'
            f'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;"><a href="{escape(url or "#")}" target="_blank"'
            f' style="color:{color};text-decoration:none;display:block;">{escape(label)} →</a></td></tr></table>')

def _render_heroes(heroes: Iterable[Dict[str, Any]]) -> str:
    out = []
    for i, h in enumerate(heroes):
        title = (h.get("title") or "").strip()
        if not title: 
            continue
        url = h.get("url") or "#"
        src = h.get("source") or ""
        when = _fmt_ct(h.get("when"), force_time=False, tz_suffix_policy="never") if h.get("when") else ""
        desc = (h.get("description") or "").strip()
        # Labeling
        label = "● BREAKING" if i == 0 else "● ALSO BREAKING"
        # Body truncation
        if len(desc) > 180:
            # try sentence boundary first
            import re
            sentences = re.split(r'[.!?]\s+', desc)
            truncated = ""
            for s in sentences:
                if len(truncated + s) <= 160:
                    truncated += s + ". "
                else:
                    break
            desc = truncated.strip() if truncated else (desc[:177] + "...")
        meta_bits = [b for b in [src, when] if b]
        meta = " • ".join(meta_bits)
        out.append(
            f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate;margin:0 0 12px;">
<tr><td style="border:1px solid #E5E7EB;border-radius:12px;overflow:hidden;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FFFFFF;">
    <tr><td style="padding:18px 16px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">
      <div style="font-size:12px;color:#6B7280;font-weight:700;margin-bottom:6px;">{label}</div>
      <a href="{escape(url)}" style="text-decoration:none;color:#111827;"><div style="font-size:20px;font-weight:800;line-height:1.2;margin-bottom:8px;">{escape(title)}</div></a>
      {f'<div style="font-size:14px;color:#374151;margin-bottom:8px;line-height:1.5;">{escape(desc)}</div>' if desc else ''}
      {f'<div style="font-size:12px;color:#6B7280;">{escape(meta)}</div>' if meta else ''}
    </td></tr>
  </table>
</td></tr></table>'''
        )
    return "".join(out)

def _tag_pill(text: Optional[str], section: str) -> str:
    if not text: 
        return ""
    style = SECTION_STYLES.get(section, SECTION_STYLES["equity"])
    return (f'<span style="background:{style["tag_bg"]};color:{style["tag_color"]};'
            f'border-radius:999px;padding:3px 10px;font-size:11px;font-weight:700;'
            f'margin-right:8px;display:inline-block;">{escape(text)}</span>')

def _build_card_common(c: Dict[str, Any], section: str) -> str:
    style = SECTION_STYLES.get(section, SECTION_STYLES["equity"])
    name  = c.get("name") or c.get("ticker") or "Unknown"
    tkr   = c.get("ticker") or c.get("symbol") or ""
    price_v = _safe_float(c.get("price"), None)
    if price_v is None:
        price_fmt = '<span style="color:#9CA3AF;">--</span>'
    else:
        # general formatter
        price_fmt = f'<span style="color:#111827;font-weight:700;">${price_v:,.2f}</span>'

    chips = (_chip("1D", c.get("pct_1d")) + _chip("1W", c.get("pct_1w")) +
             " " + _chip("1M", c.get("pct_1m")) + _chip("YTD", c.get("pct_ytd")))

    range_html = _range_bar(_safe_float(c.get("range_pct"), 50.0) or 50.0,
                            _safe_float(c.get("low_52w"), 0.0) or 0.0,
                            _safe_float(c.get("high_52w"), 0.0) or 0.0)

    bullets = []
    headline = c.get("headline")
    when_fmt = _fmt_ct(c.get("when"), force_time=False, tz_suffix_policy="never") if c.get("when") else None
    src = c.get("source")
    if headline:
        display = headline if len(headline) <= 100 else (headline[:100] + "...")
        if src and when_fmt: bullets.append(f'★ {escape(display)} <span style="color:#6B7280;">({escape(src)}, {escape(when_fmt)})</span>')
        elif src:            bullets.append(f'★ {escape(display)} <span style="color:#6B7280;">({escape(src)})</span>')
        elif when_fmt:       bullets.append(f'★ {escape(display)} <span style="color:#6B7280;">({escape(when_fmt)})</span>')
        else:                bullets.append(f'★ {escape(display)}')
    news_url = c.get("news_url") or f"https://finance.yahoo.com/quote/{escape(tkr)}/news"
    pr_url   = c.get("pr_url")   or f"https://finance.yahoo.com/quote/{escape(tkr)}/press-releases"

    bullets_html = "".join([
        f'<tr><td style="padding-bottom:8px;font-size:14px;line-height:1.5;color:#374151;">{b}</td></tr>'
        for b in bullets[:2]
    ])

    tag_html = _tag_pill(c.get("industry"), section)

    return f'''
<div style="border:1px solid {style["card_border"]};border-radius:14px;margin:0 0 12px;box-shadow:0 2px 8px {style["card_shadow"]};background:{style["card_bg"]};">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate;margin:0;background:#FFFFFF;border-radius:13px;overflow:hidden;">
    <tr><td style="padding:20px 22px;vertical-align:top;">
      <table role="presentation" width="100%" cellpadding="
