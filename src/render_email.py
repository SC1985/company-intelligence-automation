
from datetime import datetime, timezone
from html import escape
from email.utils import parsedate_to_datetime
import math
import re
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
    # Epoch seconds / ms
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
    # RFC2822
    try:
        dt = parsedate_to_datetime(s)
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    # Date-only fallback
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


def _safe_float(x, default=None):
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except Exception:
        return default


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


def _button(label: str, url: str, size="md"):
    fz = "13px" if size == "md" else "11px"
    safe_label = escape(label)
    href = escape(url or "#")
    return (f'<a href="{href}" target="_blank" rel="noopener noreferrer" '
            f'style="background:#1f2937;color:#ffffff;text-decoration:none;'
            f'border-radius:6px;font-size:{fz};border:1px solid #374151;'
            f'line-height:1;white-space:nowrap;padding:6px 10px;display:inline-block;margin-right:4px;">'
            f'{safe_label} →</a>')


def _range_bar(pos: float, low: float, high: float):
    """Table-based 52-week bar with a visible marker cell (6px)."""
    pct = _safe_float(pos, 50.0)
    pct = max(0.0, min(100.0, pct))
    marker_w = 6  # px
    track_h = 6
    left_pct = pct
    right_pct = max(0.0, 100.0 - pct)
    track = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
        f'<tr height="{track_h}" style="height:{track_h}px;line-height:0;font-size:0;">'
        f'<td width="{left_pct:.1f}%" style="width:{left_pct:.1f}%;background:#2a2a2a;height:{track_h}px;line-height:0;font-size:0;">&nbsp;</td>'
        f'<td width="{marker_w}" style="width:{marker_w}px;background:#3b82f6;height:{track_h}px;line-height:0;font-size:0;">&nbsp;</td>'
        f'<td width="{right_pct:.1f}%" style="width:{right_pct:.1f}%;background:#2a2a2a;height:{track_h}px;line-height:0;font-size:0;">&nbsp;</td>'
        f'</tr></table>'
    )
    caption = (f'<div style="font-size:12px;color:#9aa0a6;margin-top:4px;">'
               f'Low ${_safe_float(low,0.0):.2f} • High ${_safe_float(high,0.0):.2f}</div>')
    return (f'<div style="font-size:12px;color:#9aa0a6;margin-bottom:4px;">52-week range</div>'
            + track + caption)


def _belongs_to_company(headline: str, c: dict) -> bool:
    if not headline or not c:
        return False
    t = str(c.get("ticker") or "").upper()
    name = str(c.get("name") or "")
    h = str(headline)
    if t and re.search(rf'\\b{re.escape(t)}\\b', h, re.I):
        return True
    if name and re.search(rf'\\b{re.escape(name)}\\b', h, re.I):
        return True
    return False


def _nowrap_metrics(text: str) -> str:
    """Prevent splits like 'm/m 2.3%' across lines."""
    import re as _re
    if not text:
        return text
    pattern = _re.compile(r'(?i)\\b([myq]/[myq]\\s*:?\\s*[+\\-]?\\d+(?:\\.\\d+)?%?)')
    def repl(m):
        return f'<span style="white-space:nowrap">{m.group(0)}</span>'
    return pattern.sub(repl, text or "")


def _build_card(c):
    try:
        name = c.get("name") or c.get("ticker")
        t = c.get("ticker")
        price = _safe_float(c.get("price"), 0.0) or 0.0
        p1d, p1w, p1m, pytd = c.get("pct_1d"), c.get("pct_1w"), c.get("pct_1m"), c.get("pct_ytd")
        low52 = _safe_float(c.get("low_52w"), 0.0) or 0.0
        high52 = _safe_float(c.get("high_52w"), 0.0) or 0.0
        rp = c.get("range_pct")
        try:
            range_pct = float(rp) if rp is not None else 50.0
            if math.isnan(range_pct) or math.isinf(range_pct):
                range_pct = 50.0
        except Exception:
            range_pct = 50.0
        headline = c.get("headline") or ""
        source = c.get("source")
        when = c.get("when")
        # Date-only in bullets (no timestamp)
        when_fmt = _fmt_ct(when, force_time=False, tz_suffix_policy="never") if when else None

        next_event = c.get("next_event")
        volx = c.get("vol_x_avg")
        news_url = c.get("news_url") or (f"https://finance.yahoo.com/quote/{t}/news" if t else "#")
        pr_url = c.get("pr_url") or (f"https://finance.yahoo.com/quote/{t}/press-releases" if t else "#")

        # chips on two lines: 1D+1W / 1M+YTD
        chips_line1 = "".join([_chip("1D", p1d), _chip("1W", p1w)])
        chips_line2 = "".join([_chip("1M", p1m), _chip("YTD", pytd)])
        chips = f'<div>{chips_line1}</div><div style="margin-top:4px;">{chips_line2}</div>'

        bullets = []
        if headline and _belongs_to_company(headline, c):
            if source and when_fmt:
                bullets.append(f"★ {headline} ({source}, {when_fmt})")
            elif source:
                bullets.append(f"★ {headline} ({source})")
            elif when_fmt:
                bullets.append(f"★ {headline} ({when_fmt})")
            else:
                bullets.append(f"★ {headline}")
        else:
            if name:
                bullets.append(f"★ Latest {name} coverage — see News")
        if next_event:
            ne_txt = _fmt_ct(next_event, force_time=False, tz_suffix_policy="never") if isinstance(next_event, (str, datetime)) else str(next_event)
            bullets.append(f"Next: {ne_txt}")
        if volx is not None:
            try:
                bullets.append(f"Volume: {float(volx):.2f}× 30-day avg")
            except Exception:
                pass

        # Build bullets HTML; first one clamped to 5 lines and flush-left, no default list indent
        bullets_html = ""
        for i, b in enumerate(bullets):
            if i == 0:
                bullets_html += (
                  '<li class="brief-bullet" '
                  'style="list-style-type:none;margin-left:0;padding-left:0;text-indent:0;'
                  'display:-webkit-box;-webkit-box-orient:vertical;'
                  '-webkit-line-clamp:5;overflow:hidden;text-overflow:ellipsis;'
                  'line-height:1.4;max-height:calc(1.4em * 5);">'
                  + _nowrap_metrics(escape(b)) + "</li>"
                )
            else:
                bullets_html += '<li style="margin-left:0;padding-left:0;list-style-position:inside;">' + _nowrap_metrics(escape(b)) + "</li>"

        range_html = _range_bar(range_pct, float(low52 or 0.0), float(high52 or 0.0))
        ctas = _button("News", news_url, size="md") + _button("Press", pr_url, size="md")

        price_fmt = f"${price:.4f}" if (t and str(t).endswith("-USD")) else f"${price:.2f}"
        return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;margin:0 0 6px;background:#111;
              border:1px solid #2a2a2a;border-radius:8px;max-height:300px;" class="ci-card" >
  <tr>
    <td class="ci-card-body" style="padding:12px 14px;max-height:300px;vertical-align:top;overflow:hidden;" >
      <div style="font-weight:700;font-size:16px;line-height:1.3;color:#fff;">
        {escape(str(name or ''))} <span style="color:#9aa0a6;">({escape(str(t or ''))})</span>
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
    except Exception:
        # Fail-safe card to prevent whole build from breaking (e.g., bad data for a single company)
        fallback_name = escape(str(c.get("name") or c.get("ticker") or "Company"))
        return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;margin:0 0 6px;background:#111;
              border:1px solid #2a2a2a;border-radius:8px;max-height:300px;" class="ci-card" >
  <tr>
    <td class="ci-card-body" style="padding:12px 14px;max-height:300px;vertical-align:top;overflow:hidden;" >
      <div style="font-weight:700;font-size:16px;line-height:1.3;color:#fff;">{fallback_name}</div>
      <div style="margin-top:8px;color:#9aa0a6;font-size:13px;">Data temporarily unavailable.</div>
    </td>
  </tr>
</table>
"""


def _grid(cards):
    """Two-column grid with 6px gutter via column padding (desktop); stacks on mobile."""
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
    """Large bordered container that wraps a section (Stocks/ETFs or Digital Assets)."""
    safe_title = escape(title)
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


def _pick_hero_item(companies):
    """Pick a hero headline from companies using market-related keywords, else newest by time."""
    if not companies:
        return None
    kw = re.compile(r'\\b(market|stocks?|equities|indices|index|dow|nasdaq|s&p|s\\&p|fed|fomc|inflation|cpi|ppi|jobs?|economy|treasury|yields?|rates?)\\b', re.I)
    best = None; best_score = -1
    for c in companies:
        h = c.get("headline") or ""
        if not h:
            continue
        score = 0
        if kw.search(h):
            score += 100
        # recency
        dt = _parse_to_dt(c.get("when"))
        if dt:
            score += int(dt.timestamp() // 60) % 100  # tie-breaker
        if score > best_score:
            best = (score, c, h, c.get("when"))
            best_score = score
    return best


def _hero_block(headline: str, source: str, when, url: str, excerpt: str = None):
    when_txt = _fmt_ct(when, force_time=False, tz_suffix_policy="never") if when else ""
    safe_h = escape(headline or "")
    safe_src = escape(source or "") if source else ""
    href = escape(url or "#")
    ex = excerpt or ""
    # Build excerpt block (show more: ~10 lines)
    excerpt_html = ""
    if ex:
        excerpt_html = ('<div style="font-size:14px;line-height:1.5;color:#e5e7eb;'
                        'display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:10;'
                        'overflow:hidden;text-overflow:ellipsis;max-height:calc(1.5em * 10);margin-top:6px;">' + escape(ex) + '</div>')
    meta_html = ""
    if safe_src or when_txt:
        parts = []
        if safe_src: parts.append(safe_src)
        if when_txt: parts.append(escape(when_txt))
        meta_html = "<div style=\\"margin-top:8px;font-size:12px;color:#9aa0a6;\\">" + " • ".join(parts) + "</div>"
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:14px 0;">
  <tr>
    <td style="padding:14px;background:#0f172a;border:1px solid #2a2a2a;border-radius:10px;">
      <div style="font-weight:700;font-size:20px;line-height:1.3;color:#e5e7eb;margin:0 0 8px 0;">Market Update</div>
      <div style="font-size:18px;line-height:1.35;color:#ffffff;">{safe_h}</div>
      {excerpt_html}
      {meta_html}
      <div style="margin-top:10px;">{_button("Read article", href, size="md")}</div>
    </td>
  </tr>
</table>
"""


def render_email(summary, companies, cryptos=None):
    """Builds the full HTML email."""
    # Prepare cards
    company_cards = []
    crypto_cards = []

    # Prefer explicit 'cryptos' list if provided; otherwise split by asset_class / ticker suffix
    for c in companies or []:
        asset_class = str(c.get("asset_class") or "").lower()
        sym = str(c.get("ticker") or "")
        if asset_class == "crypto" or sym.endswith("-USD"):
            crypto_cards.append(_build_card(c))
        else:
            company_cards.append(_build_card(c))

    if cryptos:
        # If separate cryptos list is passed, use it (and ignore any crypto inferred above from companies)
        crypto_cards = [_build_card(c) for c in cryptos or []]

    # Header meta
    as_of = summary.get("as_of_ct") if isinstance(summary, dict) else None
    as_of_txt = _fmt_ct(as_of, force_time=True, tz_suffix_policy="always") if as_of else ""

    # Hero block (from summary['hero'] if present, else heuristically pick)
    hero_html = ""
    hero_data = None
    if isinstance(summary, dict):
        hero_data = summary.get("hero") or summary.get("market_headline")
    if hero_data and isinstance(hero_data, dict) and hero_data.get("headline"):
        hero_html = _hero_block(hero_data.get("headline"), hero_data.get("source"),
                                hero_data.get("when"), hero_data.get("url"),
                                hero_data.get("excerpt") or hero_data.get("summary"))
    else:
        picked = _pick_hero_item(companies)
        if picked:
            _, c0, h0, ts0 = picked
            hero_html = _hero_block(h0, c0.get("source"), c0.get("when"), c0.get("news_url"),
                                    c0.get("summary") or "")

    # Assemble body sections
    stocks_section = _section_container("Stocks & ETFs", _grid(company_cards)) if company_cards else ""
    crypto_section  = _section_container("Digital Assets", _grid(crypto_cards)) if crypto_cards else ""

    html = f"""<!DOCTYPE html>
<html>
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Intelligence Digest</title>
    <style>
      @media only screen and (max-width: 620px) {{
        .stack-col {{ display:block !important; width:100% !important; max-width:100% !important; padding-left:0 !important; padding-right:0 !important; }}
        .spacer {{ display:none !important; width:0 !important; }}
      }}
      /* Card height rules: desktop max 300px; mobile auto */
      .ci-card {{ max-height: 300px; }}
      @media only screen and (max-width: 620px) {{
        .ci-card {{ max-height: none !important; }}
        .ci-card-body {{ max-height: none !important; overflow: visible !important; }}
      }}
      /* Clamp first bullet (news) */
      .brief-bullet {{
        display: -webkit-box;
        -webkit-line-clamp: 5;
        -webkit-box-orient: vertical;
        overflow: hidden;
        text-overflow: ellipsis;
        line-height: 1.4;
        max-height: calc(1.4em * 5);
      }}
    </style>
  </head>
  <body style="margin:0;background:#0b0c10;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
      <tr>
        <td align="center" style="padding:22px 12px;">
          <table role="presentation" width="620" cellpadding="0" cellspacing="0" style="border-collapse:collapse;width:620px;max-width:100%;">
            <tr>
              <td style="padding:16px;background:#111827;border:1px solid #2a2a2a;mso-border-alt:1px solid #2a2a2a;border-radius:10px;">
                <div style="font-weight:700;font-size:54px;color:#fff;">Intelligence Digest</div>
                {f'<div style="color:#9aa0a6;margin-top:6px;font-size:13px;">Data as of {escape(as_of_txt)}</div>' if as_of_txt else ''}
                <div style="margin-top:12px;border-top:1px solid #2a2a2a;height:1px;line-height:1px;font-size:0;">&nbsp;</div>

                {hero_html}

                {stocks_section}
                {crypto_section}

              </td>
            </tr>
            <tr>
              <td style="padding:16px 14px;color:#9aa0a6;font-size:12px;text-align:center;">
                You’re receiving this because you subscribed to Intelligence Digest.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
    return html
