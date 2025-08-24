# src/render_email.py
# UI-focused renderer for the Intelligence Digest email.
# REVERTED: Back to original visual design that works properly
# KEPT: Only the core improvements (better parsing, error handling)

from datetime import datetime, timezone
from html import escape
from email.utils import parsedate_to_datetime
import re

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

CENTRAL_TZ = ZoneInfo("America/Chicago") if ZoneInfo else None


# ---------- time helpers ----------

def _parse_to_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip()
    if not s:
        return None
    # epoch seconds / ms
    if s.isdigit():
        try:
            iv = int(s)
            if iv > 10_000_000_000:
                iv //= 1000
            return datetime.fromtimestamp(iv, tz=timezone.utc)
        except Exception:
            pass
    # ISO 8601
    try:
        s2 = s[:-1] + "+00:00" if s.endswith("Z") else s
        dt = datetime.fromisoformat(s2)
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    # RFC 2822
    try:
        dt = parsedate_to_datetime(s)
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    # date-only fallback
    try:
        if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
            return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        pass
    return None


def _fmt_ct(value, force_time=None, tz_suffix_policy="auto"):
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
    if tz_suffix_policy == "never":
        return out
    return out


# ---------- misc helpers ----------

def _safe_float(x, default=None):
    try:
        return float(x)
    except Exception:
        return default


def _chip(label: str, value):
    v = _safe_float(value, None)
    if v is None:
        bg = "#2a2a2a"; color = "#9aa0a6"; sign = ""; txt = "--"
    else:
        bg = "#34d399" if v >= 0 else "#f87171"
        color = "#111"
        sign = "▲" if v >= 0 else "▼"
        txt = f"{v:+.1f}%"
    safe_label = escape(label)
    # ORIGINAL spacing restored
    return (f'<span style="background:{bg};color:{color};padding:3px 8px;'
            f'border-radius:6px;font-size:12px;margin-right:8px;margin-bottom:3px;'
            f'display:inline-block;font-weight:600;box-shadow:0 1px 3px rgba(0,0,0,0.1);">'
            f'{safe_label} {sign} {txt}</span>')


def _button(label: str, url: str):
    safe_label = escape(label)
    href = escape(url or "#")
    # ORIGINAL button design restored
    return (f'<a href="{href}" target="_blank" rel="noopener noreferrer" '
            f'style="background:#1f2937;color:#ffffff;text-decoration:none;'
            f'border-radius:6px;font-size:13px;border:1px solid #374151;'
            f'line-height:1;white-space:nowrap;padding:6px 10px;display:inline-block;'
            f'margin-right:6px;">{safe_label} →</a>')


def _range_bar(pos: float, low: float, high: float):
    pct = max(0.0, min(100.0, _safe_float(pos, 0.0)))
    left = f"{pct:.1f}%"
    right = f"{100 - pct:.1f}%"
    low_v = _safe_float(low, 0.0) or 0.0
    high_v = _safe_float(high, 0.0) or 0.0
    # ORIGINAL table-based design restored
    track = (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        'style="border-collapse:collapse;"><tr height="6">'
        f'<td width="{left}" style="width:{left};background:#2a2a2a;height:6px;">&nbsp;</td>'
        '<td width="6" style="width:6px;background:#3b82f6;height:6px;">&nbsp;</td>'
        f'<td width="{right}" style="width:{right};background:#2a2a2a;height:6px;">&nbsp;</td>'
        '</tr></table>'
    )
    caption = (f'<div style="font-size:12px;color:#9aa0a6;margin-top:4px;">'
               f'Low ${low_v:.2f} • High ${high_v:.2f}</div>')
    return (f'<div style="font-size:12px;color:#9aa0a6;margin-bottom:4px;">52-week range</div>'
            + track + caption)


def _belongs_to_company(c: dict, headline: str) -> bool:
    if not c or not headline:
        return False
    name = str(c.get("name") or "").lower()
    ticker = str(c.get("ticker") or c.get("symbol") or "").lower()
    base_tokens = set()
    if name:
        for tok in re.split(r"[\s&,\.-]+", name):
            if len(tok) > 2:
                base_tokens.add(tok)
    if ticker:
        base_tokens.add(ticker)
    h = headline.lower()
    return any(tok and tok in h for tok in base_tokens)


# ---------- hero parsing ----------

def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()


def _first_paragraph(hero: dict, title: str = "") -> str:
    """
    Return the first meaningful paragraph from hero content.
    IMPROVED: Better content extraction while keeping original structure.
    """
    if not hero:
        return ""
    title_norm = (title or "").strip().lower()

    # IMPROVED: Better field checking but same output format
    html_keys = ("body_html", "content_html", "html", "article_html", "summary_html", "description_html")
    for key in html_keys:
        html = hero.get(key)
        if html:
            # First non-trivial <p>
            paras = re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.I | re.S)
            for p in paras:
                txt = _strip_tags(p)
                if txt and len(txt) > 20 and txt.strip().lower() != title_norm:
                    return txt
            # Fallback: plain text from HTML
            txt = _strip_tags(html)
            for part in re.split(r"\r?\n\r?\n+|\n{2,}", txt):
                part = part.strip()
                if part and part.lower() != title_norm:
                    return part

    # Structured arrays
    paras_list = hero.get("paragraphs") or hero.get("content_paragraphs")
    if isinstance(paras_list, (list, tuple)):
        for p in paras_list:
            txt = _strip_tags(str(p))
            if txt and len(txt) > 20 and txt.strip().lower() != title_norm:
                return txt

    # Text fallbacks - IMPROVED: Include 'body' field
    text_keys = (
        "first_paragraph", "firstParagraph", "lede", "lead", "dek",
        "abstract", "description", "summary", "excerpt", "content", "body",
        "snippet", "preview", "preview_text"
    )
    for key in text_keys:
        val = hero.get(key)
        if val:
            text = _strip_tags(str(val))
            if not text:
                continue
            blocks = re.split(r"\r?\n\r?\n+|\n{2,}", text)
            for part in blocks:
                part = part.strip()
                if part and part.lower() != title_norm and len(part) > 10:
                    return part
            # Also try first sentence
            m = re.search(r"(.+?[\.!?])(\s|$)", text)
            if m:
                cand = m.group(1).strip()
                if cand and cand.lower() != title_norm and len(cand) > 10:
                    return cand

    return ""


def _select_hero(summary: dict, companies: list, cryptos: list):
    hero = None
    if isinstance(summary, dict):
        cand = summary.get("hero") or summary.get("market_hero") or summary.get("market")
        if isinstance(cand, dict) and (cand.get("title") or cand.get("body") or cand.get("content")
                                       or cand.get("body_html") or cand.get("content_html")
                                       or cand.get("first_paragraph") or cand.get("description")
                                       or cand.get("summary")):
            hero = cand
    if hero:
        return hero
    # Fallback: scan broad-market signals from entities
    keywords = ("market", "stocks", "equities", "indices", "index", "s&p", "nasdaq", "dow",
                "fed", "federal reserve", "inflation", "cpi", "jobs", "rates", "treasury", "yields")
    all_entities = (companies or []) + (cryptos or [])
    for c in all_entities:
        hl = str(c.get("headline") or "")
        if hl and any(k in hl.lower() for k in keywords):
            return {
                "title": hl,
                "url": c.get("news_url") or "",
                "source": c.get("source") or "",
                "when": c.get("when"),
                "body": c.get("description") or c.get("story") or c.get("summary") or "",
                "description": c.get("description") or c.get("story") or c.get("summary") or ""
            }
    return None


def _render_hero(hero: dict) -> str:
    if not hero:
        return ""
    title = (hero.get("title") or "").strip()
    if not title:
        return ""
    url = hero.get("url") or "#"
    source = hero.get("source") or ""
    when = _fmt_ct(hero.get("when"), force_time=False, tz_suffix_policy="never") if hero.get("when") else ""

    # IMPROVED: Better paragraph extraction but same visual output
    para = _first_paragraph(hero, title=title)
    if para and para.strip().lower() == title.strip().lower():
        para = ""

    # Body HTML: same color as the headline - ORIGINAL design restored
    body_html = (
        f'<div style="margin-top:8px;font-size:14px;line-height:1.5;'
        f'display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:24;'
        f'overflow:hidden;text-overflow:ellipsis;max-height:calc(1.5em * 24);'
        f'color:inherit;">{escape(para)}</div>'
        if para else ""
    )

    # ORIGINAL hero design restored - explicit fg/bg to avoid dark-mode inversion surprises
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


# ---------- card/grid/sections - ORIGINAL design restored ----------

def _build_card(c):
    name = c.get("name") or c.get("ticker") or c.get("symbol")
    t = c.get("ticker") or c.get("symbol") or ""
    sym = str(t)
    is_crypto = sym.endswith("-USD") or (str(c.get("asset_class") or "").lower() == "crypto")

    price_v = _safe_float(c.get("price"), None)
    if price_v is None:
        price_fmt = "--"
    else:
        price_fmt = f"${price_v:.4f}" if is_crypto else f"${price_v:.2f}"

    # ORIGINAL chip layout restored
    chips = (
        '<div style="line-height:1.8;">' +
        _chip("1D", c.get("pct_1d")) +
        _chip("1W", c.get("pct_1w")) +
        "<br/>" +
        _chip("1M", c.get("pct_1m")) +
        _chip("YTD", c.get("pct_ytd")) +
        '</div>'
    )

    # bullets: first is news; keep scoped to the company
    bullets = []
    headline = c.get("headline")
    source = c.get("source")
    when_fmt = _fmt_ct(c.get("when"), force_time=False, tz_suffix_policy="never") if c.get("when") else None

    if headline and _belongs_to_company(c, headline):
        if source and when_fmt:
            bullets.append(f"★ {headline} ({source}, {when_fmt})")
        elif source:
            bullets.append(f"★ {headline} ({source})")
        elif when_fmt:
            bullets.append(f"★ {headline} ({when_fmt})")
        else:
            bullets.append(f"★ {headline}")
    else:
        co_name = (c.get("name") or sym or "Company").strip()
        bullets.append(f"★ Latest {co_name} coverage — see News")

    next_event = c.get("next_event")
    if next_event:
        ne_txt = _fmt_ct(next_event, force_time=False, tz_suffix_policy="never")
        if ne_txt:
            bullets.append(f"Next: {ne_txt}")

    volx = _safe_float(c.get("vol_x_avg"), None)
    if volx is not None:
        bullets.append(f"Volume: {volx:.2f}× 30-day avg")

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
            bullets_html += '<li style="margin-left:0;padding-left:0;list-style-position:inside;">' + escape(b) + "</li>"

    range_html = _range_bar(_safe_float(c.get("range_pct"), 50.0),
                            _safe_float(c.get("low_52w"), 0.0),
                            _safe_float(c.get("high_52w"), 0.0))

    news_url = c.get("news_url") or (f"https://finance.yahoo.com/quote/{escape(sym)}/news" if sym else "#")
    pr_url = c.get("pr_url") or (f"https://finance.yahoo.com/quote/{escape(sym)}/press-releases" if sym else "#")
    ctas = _button("News", news_url) + _button("Press", pr_url)

    # ORIGINAL table-based card design restored
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;margin:0 0 6px;background:#111827;
              border:1px solid #2a2a2a;mso-border-alt:1px solid #2a2a2a;
              border-radius:8px;">
  <tr>
    <td class="ci-card-inner" style="padding:12px 14px;max-height:300px;overflow:hidden;vertical-align:top;">
      <div style="font-weight:700;font-size:16px;line-height:1.3;color:#ffffff;">
        {escape(str(name))} <span style="color:#9aa0a6;">({escape(sym)})</span>
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


def _grid(cards):
    """ORIGINAL two-column grid restored (desktop) with 6px gutter via column padding; stacks on mobile."""
    rows = []
    for i in range(0, len(cards), 2):
        left = cards[i]
        right = cards[i + 1] if i + 1 < len(cards) else ""
        if right:
            row = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
  <tr>
    <td class="stack-col" width="50%" style="vertical-align:top;padding-right:6px;">{left}</td>
    <td class="stack-col" width="50%" style="vertical-align:top;padding-left:6px;">{right}</td>
  </tr>
</table>
"""
        else:
            row = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
  <tr>
    <td class="stack-col" width="100%" style="vertical-align:top;">{left}</td>
  </tr>
</table>
"""
        rows.append(row)
    return "".join(rows)


def _section_container(title: str, inner_html: str):
    safe_title = escape(title)
    # ORIGINAL section design restored
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#0b0c10"
       style="border-collapse:collapse;background:#0b0c10;border:1px solid #2a2a2a;
              mso-border-alt:1px solid #2a2a2a;border-radius:10px;margin:14px 0 0 0;">
  <tr>
    <td style="padding:16px;">
      <div style="font-weight:700;font-size:32px;color:#e5e7eb;margin:0 0 10px 0;">{safe_title}</div>
      {inner_html}
    </td>
  </tr>
</table>
"""


def _generate_email_preview() -> str:
    """IMPROVED: Generate optimized email preview text for inbox display."""
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    
    preview_texts = [
        f"Market intelligence at {current_time} • Top movers, sentiment analysis, and strategic signals across your portfolio",
        f"Strategic positions update {current_time} • Performance insights, news highlights, and market momentum indicators",
        f"Portfolio digest {current_time} • Key movements, sector analysis, and breaking news from your strategic holdings",
        f"Intelligence brief {current_time} • Market data, sentiment tracking, and strategic alerts for informed decisions",
        f"Market snapshot {current_time} • Real-time performance, news synthesis, and portfolio momentum analysis"
    ]
    
    # Rotate based on day of year to add variety
    preview_index = now.timetuple().tm_yday % len(preview_texts)
    return preview_texts[preview_index]


# ---------- main - ORIGINAL structure restored ----------

def render_email(summary, companies, cryptos=None):
    # Split into equities vs crypto
    company_cards = []
    crypto_cards = []

    for c in companies or []:
        sym = str(c.get("ticker") or c.get("symbol") or "")
        is_crypto = sym.endswith("-USD") or (str(c.get("asset_class") or "").lower() == "crypto")
        if is_crypto:
            crypto_cards.append(_build_card(c))
        else:
            company_cards.append(_build_card(c))

    # Allow explicit cryptos list to append/override
    if cryptos:
        for cx in cryptos:
            crypto_cards.append(_build_card(cx))

    # Header meta
    as_of = _fmt_ct((summary or {}).get("as_of_ct"), force_time=True, tz_suffix_policy="always") if summary else ""

    # Hero selection + render - IMPROVED extraction but same visual output
    hero_obj = _select_hero(summary or {}, companies or [], cryptos or [])
    hero_html = _render_hero(hero_obj) if hero_obj else ""

    # Sections
    stocks_section = _section_container("Stocks & ETFs", _grid(company_cards)) if company_cards else ""
    crypto_section = _section_container("Digital Assets", _grid(crypto_cards)) if crypto_cards else ""

    # IMPROVED: Generate email preview text but same visual output
    email_preview = _generate_email_preview()

    # ORIGINAL CSS restored - the mobile CSS that actually works
    css = """
@media only screen and (max-width: 620px) {
  .stack-col { display:block !important; width:100% !important; max-width:100% !important; padding-left:0 !important; padding-right:0 !important; }
  .ci-card-inner { max-height:none !important; overflow:visible !important; }
}
"""

    # ORIGINAL HTML structure restored
    html = f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <meta name="color-scheme" content="light dark">
    <meta name="supported-color-schemes" content="light dark">
    <meta name="description" content="{escape(email_preview)}">
    <meta name="format-detection" content="telephone=no">
    <title>Intelligence Digest</title>
    <style>{css}</style>
  </head>
  <body style="margin:0;background:#0b0c10;color:#e5e7eb;">
    <!-- Hidden preview text for inbox display - IMPROVED but same position -->
    <div style="display:none;font-size:1px;color:#0b0c10;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">
      {escape(email_preview)}
    </div>
    
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
      <tr>
        <td align="center" style="padding:22px 12px;">
          <table role="presentation" width="620" cellpadding="0" cellspacing="0" style="border-collapse:collapse;width:620px;max-width:100%;">
            <tr>
              <td style="padding:16px;background:#111827;border:1px solid #2a2a2a;mso-border-alt:1px solid #2a2a2a;border-radius:10px;">
                <div style="font-weight:700;font-size:54px;color:#ffffff;">Intelligence Digest</div>
                {f'<div style="color:#9aa0a6;margin-top:6px;font-size:13px;">Data as of {escape(as_of)}</div>' if as_of else ''}
                <div style="margin-top:12px;border-top:1px solid #2a2a2a;height:1px;line-height:1px;font-size:0;">&nbsp;</div>

                {hero_html}

                {stocks_section}
                {crypto_section}

              </td>
            </tr>
            <tr>
              <td style="padding:16px 14px;color:#9aa0a6;font-size:12px;text-align:center;">
                You're receiving this because you subscribed to Intelligence Digest.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
    return html
