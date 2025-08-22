from datetime import datetime, timezone
from html import escape
from email.utils import parsedate_to_datetime
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

CENTRAL_TZ = ZoneInfo("America/Chicago") if ZoneInfo else None


def _parse_to_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit():
        try:
            iv = int(s)
            if iv > 10_000_000_000:
                iv //= 1000
            return datetime.fromtimestamp(iv, tz=timezone.utc)
        except Exception:
            pass
    try:
        s2 = s[:-1] + "+00:00" if s.endswith("Z") else s
        dt = datetime.fromisoformat(s2)
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    try:
        dt = parsedate_to_datetime(s)
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    try:
        if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
            return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        pass
    return None


def _fmt_ct(value, force_time=None, tz_suffix_policy="auto"):
    dt = _parse_to_dt(value) or value
    if isinstance(dt, datetime):
        try:
            dtc = dt.astimezone(CENTRAL_TZ) if CENTRAL_TZ else dt
        except Exception:
            dtc = dt
        has_time = not (dtc.hour == 0 and dtc.minute == 0 and dtc.second == 0)
        show_time = force_time if force_time is not None else has_time
        if show_time:
            out = dtc.strftime("%m/%d/%Y %H:%M")
        else:
            out = dtc.strftime("%m/%d/%Y")
        if tz_suffix_policy == "always":
            return out + " CST"
        elif tz_suffix_policy == "auto" and show_time:
            return out + " CST"
        elif tz_suffix_policy == "never":
            return out
        return out
    return str(value)


def _chip(label: str, value):
    try:
        v = float(value) if value is not None else None
    except Exception:
        v = None
    if v is None:
        bg = "#2a2a2a"; color = "#9aa0a6"; sign = ""; txt = "--"
    else:
        bg = "#34d399" if v >= 0 else "#f87171"
        color = "#111"
        sign = "▲" if v >= 0 else "▼"
        txt = f"{v:+.1f}%"
    safe_label = escape(label)
    return (f'<span style="background:{bg};color:{color};padding:2px 6px;'
            f'border-radius:6px;font-size:12px;margin-right:4px;">{safe_label} {sign} {txt}</span>')


def _button(label: str, url: str):
    safe_label = escape(label)
    return (f'<a href="{escape(url)}" target="_blank" '
            f'style="background:#1f2937;color:#fff;text-decoration:none;'
            f'border-radius:6px;font-size:13px;border:1px solid #374151;'
            f'line-height:1;white-space:nowrap;padding:6px 10px;display:inline-block;margin-right:4px;">'
            f'{safe_label} →</a>')


def _range_bar(pos: float, low: float, high: float):
    pct = max(0.0, min(100.0, float(pos or 0)))
    left = f'{pct:.1f}%'
    right = f'{100 - pct:.1f}%'
    track = (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">'
             f'<tr height="6">'
             f'<td width="{left}" style="width:{left};background:#2a2a2a;height:6px;">&nbsp;</td>'
             f'<td width="6" style="width:6px;background:#3b82f6;height:6px;">&nbsp;</td>'
             f'<td width="{right}" style="width:{right};background:#2a2a2a;height:6px;">&nbsp;</td>'
             f'</tr></table>')
    caption = (f'<div style="font-size:12px;color:#9aa0a6;margin-top:4px;">'
               f'Low ${float(low or 0):.2f} • High ${float(high or 0):.2f}</div>')
    return (f'<div style="font-size:12px;color:#9aa0a6;margin-bottom:4px;">52-week range</div>'
            + track + caption)


def _build_card(c):
    name = c.get("name") or c.get("ticker")
    t = c.get("ticker")
    price = c.get("price") or 0.0
    chips = "".join([
        _chip("1D", c.get("pct_1d")),
        _chip("1W", c.get("pct_1w")),
        "<br/>",
        _chip("1M", c.get("pct_1m")),
        _chip("YTD", c.get("pct_ytd"))
    ])

    headline = c.get("headline")
    source = c.get("source")
    when_fmt = _fmt_ct(c.get("when"), force_time=False, tz_suffix_policy="never") if c.get("when") else None
    bullets = []
    if headline:
        if source and when_fmt:
            bullets.append(f"★ {headline} ({source}, {when_fmt})")
        elif source:
            bullets.append(f"★ {headline} ({source})")
        elif when_fmt:
            bullets.append(f"★ {headline} ({when_fmt})")
        else:
            bullets.append(f"★ {headline}")

    bullets_html = ""
    for i, b in enumerate(bullets):
        if i == 0:
            bullets_html += (
              '<li style="list-style-type:none;margin-left:0;padding-left:0;text-indent:0;'
              'display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:5;'
              'overflow:hidden;text-overflow:ellipsis;line-height:1.4;max-height:calc(1.4em * 5);">'
              + escape(b) + "</li>"
            )
        else:
            bullets_html += "<li>" + escape(b) + "</li>"

    range_html = _range_bar(c.get("range_pct") or 50.0, c.get("low_52w"), c.get("high_52w"))
    ctas = _button("News", c.get("news_url") or "#") + _button("Press", c.get("pr_url") or "#")
    price_fmt = f"${float(price):.2f}" if price else "--"

    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;margin:0 0 6px;background:#111;
              border:1px solid #2a2a2a;border-radius:8px;max-height:300px;"
       class="ci-card">
  <tr>
    <td class="ci-card-inner" style="padding:12px 14px;max-height:300px;overflow:hidden;vertical-align:top;">
      <div style="font-weight:700;font-size:16px;line-height:1.3;color:#fff;">
        {escape(str(name))} <span style="color:#9aa0a6;">({escape(str(t))})</span>
      </div>
      <div style="margin-top:2px;font-size:14px;color:#e5e7eb;">{price_fmt}</div>
      <div style="margin-top:8px;">{chips}</div>
      <div style="margin-top:12px;">{range_html}</div>
      <ul style="margin:10px 0 0 0;padding:0;color:#e5e7eb;font-size:13px;line-height:1.4;">
        {bullets_html}
      </ul>
      <div style="margin-top:10px;">{ctas}</div>
    </td>
  </tr>
</table>
"""

import re

def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()

def _first_paragraph(hero: dict) -> str:
    """
    Return the first meaningful paragraph from hero content.
    Prefers HTML body fields; falls back to plain text fields.
    """
    if not hero:
        return ""

    # Prefer HTML-ish fields
    for key in ("body_html", "content_html", "html", "article_html"):
        html = hero.get(key)
        if html:
            # First <p> with actual text
            paras = re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.I | re.S)
            for p in paras:
                txt = _strip_tags(p)
                if txt and len(txt) > 20:
                    return txt
            # Fallback: strip tags and take first non-empty block
            txt = _strip_tags(html)
            for part in re.split(r"\r?\n\r?\n+", txt):
                part = part.strip()
                if part:
                    return part

    # Plain text fields
    for key in ("body", "content", "excerpt", "summary"):
        val = hero.get(key)
        if val:
            text = str(val).strip()
            for part in re.split(r"\r?\n\r?\n+", text):
                part = part.strip()
                if part:
                    return part

    return ""

def _render_hero(hero: dict) -> str:
    if not hero:
        return ""
    title = (hero.get("title") or "").strip()
    url = hero.get("url") or "#"
    source = hero.get("source") or ""
    when = _fmt_ct(hero.get("when"), force_time=False, tz_suffix_policy="never") if hero.get("when") else ""

    # First paragraph (not the headline)
    para = _first_paragraph(hero)

    # Avoid duplication if a feed sent the title as the first "paragraph"
    if para and title and para.strip().lower() == title.strip().lower():
        para = ""

    # Body HTML: same color as the headline (inherit)
    body_html = (
        f'<div style="margin-top:8px;font-size:14px;line-height:1.5;'
        f'display:-webkit-box;-webkit-box-orient:vertical;'
        f'-webkit-line-clamp:24;overflow:hidden;text-overflow:ellipsis;'
        f'max-height:calc(1.5em * 24);color:inherit;">{escape(para)}</div>'
        if para else ""
    )

    # Container forces explicit fg/bg to avoid “reversed” dark-mode rendering.
    # Link inherits the headline color so body and headline match visually.
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;background:#111827;border:1px solid #2a2a2a;
              border-radius:10px;margin:14px 0;color:#ffffff;">
  <tr>
    <td style="padding:16px;">
      <div style="font-weight:700;font-size:22px;color:#ffffff;">
        <a href="{escape(url)}" style="color:inherit;text-decoration:none;">{escape(title)}</a>
      </div>
      {body_html}
      <div style="margin-top:6px;font-size:12px;color:#9aa0a6;">
        {escape(source)} {escape(when)}
      </div>
    </td>
  </tr>
</table>
"""


def render_email(summary, companies, cryptos=None):
    as_of = _fmt_ct(summary.get("as_of_ct"), force_time=True, tz_suffix_policy="always")
    hero_html = _render_hero(summary.get("hero")) if summary else ""
    cards_html = "".join(_build_card(c) for c in companies)

    html = f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <meta name="color-scheme" content="light dark">
    <meta name="supported-color-schemes" content="light dark">
    <style>
      @media only screen and (max-width: 620px) {{
        .ci-card-inner {{ max-height:none !important; overflow:visible !important; }}
      }}
    </style>
  </head>
  <body style="margin:0;background:#0b0c10;color:#e5e7eb;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
      <tr><td align="center" style="padding:22px 12px;">
        <table role="presentation" width="620" style="width:620px;max-width:100%;">
          <tr><td style="padding:16px;background:#111827;border:1px solid #2a2a2a;border-radius:10px;">
            <div style="font-weight:700;font-size:54px;color:#fff;">Intelligence Digest</div>
            <div style="color:#9aa0a6;margin-top:6px;font-size:13px;">Data as of {escape(as_of)}</div>
            <div style="margin-top:12px;border-top:1px solid #2a2a2a;height:1px;line-height:1px;font-size:0;">&nbsp;</div>
            {hero_html}
            {cards_html}
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""
    return html
