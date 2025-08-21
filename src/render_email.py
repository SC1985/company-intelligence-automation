
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
    # ISO 8601 (handle trailing Z)
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
    # Fallback date-only YYYY-MM-DD
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
        suffix = ""
        if tz_suffix_policy == "always":
            suffix = " CST"
        elif tz_suffix_policy == "auto" and show_time:
            suffix = " CST"
        return out + suffix
    return str(value)

def _chip(label: str, value):
    try:
        v = float(value) if value is not None else None
    except Exception:
        v = None
    if v is None:
        bg = "#2a2a2a"; color = "#9aa0a6"; sign = ""; txt = f"{label} —"
    else:
        pos = v >= 0
        bg = "#113d24" if pos else "#401a1a"
        color = "#34d399" if pos else "#f87171"
        sign = "▲" if pos else "▼"
        txt = f"{label} {'+' if pos else ''}{v:.2f}%"
    return (
        '<span style="display:inline-block;padding:2px 8px;margin-right:6px;'
        f'border-radius:12px;background:{bg};color:{color};font-size:12px;">'
        f'{sign} {txt}</span>'
    )

def _heat_square(pct):
    if pct is None:
        c = "#2a2a2a"
    else:
        mag = min(abs(pct) / 5.0, 1.0)
        c = (
            f"rgba(52,211,153,{0.25+0.75*mag:.2f})" if pct >= 0
            else f"rgba(248,113,113,{0.25+0.75*mag:.2f})"
        )
    return (
        '<span style="display:inline-block;width:10px;height:10px;'
        f'border-radius:2px;background:{c};margin-right:4px;"></span>'
    )

def _button(label: str, url: str, size="md"):
    safe_label = escape(label)
    safe_url = url or "#"
    pad = "8px 12px"; fz = "13px"
    return (
        f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer" '
        f'style="display:inline-block;padding:{pad};margin-right:6px;'
        'background:#1f2937;color:#ffffff;text-decoration:none;border-radius:6px;'
        f'font-size:{fz};border:1px solid #374151;line-height:1;white-space:nowrap;">'
        f'{safe_label} →</a>'
    )

def _mover_chip(ticker: str, pct: float, href: str):
    sign = "▲" if pct >= 0 else "▼"
    color = "#34d399" if pct >= 0 else "#f87171"
    return (
        f'<a href="{href}" target="_blank" rel="noopener noreferrer" '
        'style="display:inline-block;margin:0 8px 8px 0;padding:6px 10px;'
        'border:1px solid #374151;border-radius:999px;background:#111;'
        f'color:{color};font-size:12px;text-decoration:none;">'
        f'{sign} {escape(ticker)} {pct:+.2f}%</a>'
    )

def _range_bar(range_pct, low52, high52):
    try:
        pos = float(range_pct) if range_pct is not None else 50.0
    except Exception:
        pos = 50.0
    if pos < 0: pos = 0.0
    if pos > 100: pos = 100.0

    marker_pct = 1.6
    left = max(0.0, min(100.0 - marker_pct, pos - marker_pct / 2.0))
    right = max(0.0, 100.0 - marker_pct - left)

    if left == 0.0:
        left = 0.2; right = max(0.0, 100.0 - marker_pct - left)
    if right == 0.0:
        right = 0.2; left = max(0.0, 100.0 - marker_pct - right)

    if pos >= 90.0:
        status = '<span style="color:#e5e7eb;font-weight:600;">Near 1‑year high</span>'
    elif pos <= 10.0:
        status = '<span style="color:#e5e7eb;font-weight:600;">Near 1‑year low</span>'
    else:
        status = f'<span style="color:#e5e7eb;">At {pos:.0f}% of 52‑week range</span>'

    track = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;min-width:100%;">
  <tr>
    <td width="{left:.2f}%" valign="middle" bgcolor="#2a2a2a" style="background:#2a2a2a;line-height:0;font-size:0;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr><td height="8" style="line-height:0;font-size:0;">&nbsp;</td></tr>
      </table>
    </td>
    <td width="{marker_pct:.2f}%" valign="middle" bgcolor="#e5e7eb" style="background:#e5e7eb;line-height:0;font-size:0;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr><td height="12" style="line-height:0;font-size:0;">&nbsp;</td></tr>
      </table>
    </td>
    <td width="{right:.2f}%" valign="middle" bgcolor="#2a2a2a" style="background:#2a2a2a;line-height:0;font-size:0;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr><td height="8" style="line-height:0;font-size:0;">&nbsp;</td></tr>
      </table>
    </td>
  </tr>
</table>
"""
    caption = (
        f'<div style="font-size:12px;color:#9aa0a6;margin-top:4px;">'
        f'{status} • Low ${low52:.2f} • High ${high52:.2f}'
        '</div>'
    )

    return (
        '<div style="font-size:12px;color:#9aa0a6;margin-bottom:4px;">52-week range</div>'
        + track + caption
    )

def render_email(summary, companies, catalysts=None, cryptos=None):
    asof = _fmt_ct(summary.get("as_of_ct") or datetime.now(), force_time=True, tz_suffix_policy="always")

    up = summary.get("up_count", 0)
    down = summary.get("down_count", 0)
    movers_up = summary.get("top_winners", [])
    movers_down = summary.get("top_losers", [])
    catalysts = catalysts or summary.get("catalysts") or []
    cryptos = cryptos or []

    heat = "".join(_heat_square(c.get("pct_1d")) for c in companies)
    news_map = {c.get("ticker"): (c.get("news_url") or f"https://finance.yahoo.com/quote/{c.get('ticker')}/news") for c in companies}

    winners_html = "".join(
        _mover_chip(m.get("ticker",""), float(m.get("pct",0) or 0), news_map.get(m.get("ticker"), "#"))
        for m in movers_up if m.get("ticker")
    )
    losers_html = "".join(
        _mover_chip(m.get("ticker",""), float(m.get("pct",0) or 0), news_map.get(m.get("ticker"), "#"))
        for m in movers_down if m.get("ticker")
    )

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
        when_fmt = _fmt_ct(when, force_time=None, tz_suffix_policy="auto") if when else None

        next_event = c.get("next_event")
        volx = c.get("vol_x_avg")
        news_url = c.get("news_url") or f"https://finance.yahoo.com/quote/{t}/news"
        pr_url = c.get("pr_url") or f"https://finance.yahoo.com/quote/{t}/press-releases"

        chips = "".join([_chip("1D", p1d), _chip("1W", p1w), _chip("1M", p1m), _chip("YTD", pytd)])

        bullets = []
        if headline:
            if source and when_fmt:
                bullets.append(f"{headline} ({source}, {when_fmt})")
            elif source:
                bullets.append(f"{headline} ({source})")
            elif when_fmt:
                bullets.append(f"{headline} ({when_fmt})")
            else:
                bullets.append(f"{headline}")
        if next_event:
            ne_txt = _fmt_ct(next_event, force_time=False, tz_suffix_policy="never") if isinstance(next_event, (str, datetime)) else str(next_event)
            bullets.append(f"Next: {ne_txt}")
        if volx is not None:
            try:
                bullets.append(f"Volume: {float(volx):.2f}× 30-day avg")
            except Exception:
                pass
        bullets_html = "".join(f"<li>{escape(b)}</li>" for b in bullets)

        range_html = _range_bar(range_pct, float(low52 or 0.0), float(high52 or 0.0))
        ctas = _button("News", news_url, size="md") + _button("Press", pr_url, size="md")

        price_fmt = f"${price:.4f}" if str(t).endswith("-USD") else f"${price:.2f}"
        return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:0 0 12px;background:#111;border:1px solid #2a2a2a;border-radius:8px;">
  <tr>
    <td style="padding:12px 14px;">
      <div style="font-weight:700;font-size:16px;line-height:1.3;color:#fff;">{escape(str(name))} <span style="color:#9aa0a6;">({escape(str(t))})</span></div>
      <div style="margin-top:2px;font-size:14px;color:#e5e7eb;">{price_fmt}</div>
      <div style="margin-top:8px;">{chips}</div>
      <div style="margin-top:12px;">{range_html}</div>
      <ul style="margin:10px 0 0 16px;padding:0;color:#e5e7eb;font-size:13px;line-height:1.4;">
        {bullets_html}
      </ul>
      <div style="margin-top:10px;">{ctas}</div>
    </td>
  </tr>
</table>
"""

    def _grid(cards):
        rows = []
        for i in range(0, len(cards), 2):
            left = cards[i]
            if i+1 < len(cards):
                right = cards[i+1]
                row = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
  <tr>
    <td class="stack-col" width="50%" style="vertical-align:top;">{left}</td>
    <td class="spacer" width="12" style="width:12px;font-size:0;line-height:0;">&nbsp;</td>
    <td class="stack-col" width="50%" style="vertical-align:top;">{right}</td>
  </tr>
</table>
"""
            else:
                row = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
  <tr>
    <td class="stack-col" width="50%" style="vertical-align:top;">{left}</td>
  </tr>
</table>
"""
            rows.append(row)
        return ''.join(rows)

    company_cards = [_build_card(c) for c in companies]
    crypto_cards = [_build_card(x) for x in cryptos] if cryptos else []

    catalysts_html = ""
    if catalysts:
        items_html = []
        for c in catalysts[:8]:
            ds = _fmt_ct(c.get("date_str"), force_time=False, tz_suffix_policy="never") if c.get("date_str") else ""
            items_html.append(
                f'<div style="font-size:13px;color:#e5e7eb;margin:4px 0;">{escape(ds)} • <strong>{escape(c.get("ticker",""))}</strong> • {escape(c.get("label",""))}</div>'
            )
        catalysts_html = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;background:#111;border:1px solid #2a2a2a;border-radius:8px;">
  <tr><td style="padding:12px 14px;">
    <div style="font-weight:700;color:#fff;margin-bottom:6px;">Next 7 days</div>
    {''.join(items_html)}
  </td></tr>
</table>
"""

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="color-scheme" content="dark light">
  <meta name="supported-color-schemes" content="dark light">
  <title>Weekly Company Intelligence Digest</title>
  <style>
    @media only screen and (max-width: 620px) {{
      .stack-col {{ display:block !important; width:100% !important; max-width:100% !important; }}
      .spacer {{ display:none !important; width:0 !important; }}
    }}
  </style>
</head>
<body style="margin:0;background:#0b0b0c;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0b0b0c;">
    <tr><td align="center" style="padding:16px 12px;">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:100%;border-collapse:collapse;">
        <tr><td style="font-size:0;line-height:0;color:#0b0b0c;">
          <span style="display:none;visibility:hidden;opacity:0;color:transparent;height:0;width:0;overflow:hidden;">
            {len(companies)} companies • {up} ↑ / {down} ↓ • Data as of {asof}
          </span>
        </td></tr>

        <tr><td style="padding:12px 14px;background:#111;border:1px solid #2a2a2a;border-radius:8px;">
          <div style="font-weight:700;font-size:18px;color:#fff;">Weekly Company Intelligence Digest</div>
          <div style="font-size:13px;color:#9aa0a6;margin-top:2px;">{len(companies)} companies • {up} ↑ / {down} ↓ • Data as of {asof}</div>
          <div style="margin-top:8px;">{heat}</div>
        </td></tr>

        <tr><td style="padding:12px 14px 0;">
          <div style="margin:12px 0 6px;color:#e5e7eb;font-weight:700;">Top movers</div>
          <div>{winners_html}{losers_html}</div>
        </td></tr>

        <tr><td style="padding-top:8px;">{_grid(company_cards)}</td></tr>

        {f'<tr><td style="padding:12px 0;color:#e5e7eb;font-weight:700;">Digital Assets</td></tr><tr><td>{_grid(crypto_cards)}</td></tr>' if crypto_cards else ''}

        {f'<tr><td style="padding-top:8px;">{catalysts_html}</td></tr>' if catalysts_html else ''}

        <tr><td style="padding:16px 14px;color:#9aa0a6;font-size:12px;text-align:center;">
          Times shown where applicable are Central Time.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return html
