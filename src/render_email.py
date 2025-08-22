
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
    return (f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer" '
            f'style="background:#1f2937;color:#ffffff;text-decoration:none;'
            f'border-radius:6px;font-size:{fz};border:1px solid #374151;'
            f'line-height:1;white-space:nowrap;padding:6px 10px;display:inline-block;margin-right:4px;">'
            f'{safe_label} →</a>')



def _range_bar(pos: float, low: float, high: float):
    """Outlook-safe 52-week range bar using a 3-cell table (no absolute positioning)."""
    try:
        pct = float(pos or 0.0)
    except Exception:
        pct = 50.0
    pct = max(0.0, min(100.0, pct))
    left_pct = pct
    right_pct = 100.0 - pct
    # Track row
    track = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;width:100%;">'
        f'<tr height="6">'
        # left filler
        f'<td width="{left_pct:.1f}%" style="width:{left_pct:.1f}%;background:#2a2a2a;height:6px;line-height:6px;font-size:0;">&nbsp;</td>'
        # marker
        f'<td width="2" style="width:2px;background:#3b82f6;height:6px;line-height:6px;font-size:0;">&nbsp;</td>'
        # right filler
        f'<td width="{right_pct:.1f}%" style="width:{right_pct:.1f}%;background:#2a2a2a;height:6px;line-height:6px;font-size:0;">&nbsp;</td>'
        f'</tr></table>'
    )
    caption = (f'<div style="font-size:12px;color:#9aa0a6;margin-top:4px;">'
               f'Low ${float(low or 0):.2f} • High ${float(high or 0):.2f}</div>')
    return (f'<div style="font-size:12px;color:#9aa0a6;margin-bottom:4px;">52-week range</div>'            + track + caption)

def _nowrap_metrics(text: str) -> str:
    """Wrap tokens like m/m, y/y, q/q with their numeric value in a no-wrap span to prevent mid-token breaks.

    Works on escaped text (we inject HTML tags after escaping).
    """

    import re

    if not text:

        return text

    # Match patterns like 'm/m 2.3%', 'y/y: -10%', 'q/q +1.2%'

    pattern = re.compile(r'(?i)\b([myq]/[myq]\s*:?\s*[+\-]?\d+(?:\.\d+)?%?)')

    def repl(m):

        return f'<span style="white-space:nowrap">{m.group(0)}</span>'

    return pattern.sub(repl, text)



def _build_card(c):
    name = c.get("name") or c.get("ticker")
    t = c.get("ticker")
    price = c.get("price") or 0.0
    p1d, p1w, p1m, pytd = c.get("pct_1d"), c.get("pct_1w"), c.get("pct_1m"), c.get("pct_ytd")
    low52 = c.get("low_52w") if c.get("low_52w") is not None else 0.0
    high52 = c.get("high_52w") if c.get("high_52w") is not None else 0.0
    rp = c.get("range_pct")
    try:
        range_pct = float(rp) if rp is not None else 50.0
    except Exception:
        range_pct = 50.0
    headline = c.get("headline")
    source = c.get("source")
    when = c.get("when")
    # Date-only in bullets (no timestamp)
    when_fmt = _fmt_ct(when, force_time=False, tz_suffix_policy="never") if when else None

    next_event = c.get("next_event")
    volx = c.get("vol_x_avg")
    news_url = c.get("news_url") or f"https://finance.yahoo.com/quote/{t}/news"
    pr_url = c.get("pr_url") or f"https://finance.yahoo.com/quote/{t}/press-releases"

    chips_row1 = _chip("1D", p1d) + _chip("1W", p1w)
    chips_row2 = _chip("1M", p1m) + _chip("YTD", pytd)
    chips = f'<div style="white-space:nowrap;">{chips_row1}</div><div style="margin-top:4px;white-space:nowrap;">{chips_row2}</div>'

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

    price_fmt = f"${price:.4f}" if str(t).endswith("-USD") else f"${price:.2f}"
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;margin:0 0 12px;background:#111;
              border:1px solid #2a2a2a;mso-border-alt:1px solid #2a2a2a;
              border-radius:8px;height:350px;"
       class="ci-card" height="350">
  <tr>
    <td style="padding:12px 14px;height:350px;vertical-align:top;" height="350">
      <div style="font-weight:700;font-size:16px;line-height:1.3;color:#fff;">
        {escape(str(name))} <span style="color:#9aa0a6;">({escape(str(t))})</span>
      </div>
      <div style="margin-top:2px;font-size:14px;color:#e5e7eb;">{price_fmt}</div>
      <div class="chips" style="margin-top:8px;white-space:nowrap;">{chips}</div>
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
        .stack-col {{ display:block !important; width:100% !important; max-width:100% !important; }}
        .spacer {{ display:none !important; width:0 !important; }}
      }}
      /* Fix card height on desktop, auto on mobile */
      .ci-card {{ height: 350px; }}
      @media only screen and (max-width: 620px) {{
        .ci-card {{ height: auto !important; }}
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
