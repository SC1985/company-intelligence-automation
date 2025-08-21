from datetime import datetime
from html import escape

# ---------- helpers (chips, heat, buttons) ----------

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
        mag = min(abs(pct) / 5.0, 1.0)  # scale intensity
        c = (
            f"rgba(52,211,153,{0.25+0.75*mag:.2f})" if pct >= 0
            else f"rgba(248,113,113,{0.25+0.75*mag:.2f})"
        )
    return (
        '<span style="display:inline-block;width:10px;height:10px;'
        f'border-radius:2px;background:{c};margin-right:4px;"></span>'
    )

def _button(label: str, url: str):
    safe_label = escape(label)
    safe_url = url or "#"
    # email-safe button (inline styles only)
    return (
        f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer" '
        'style="display:inline-block;padding:8px 12px;margin-right:8px;'
        'background:#1f2937;color:#ffffff;text-decoration:none;border-radius:6px;'
        'font-size:13px;border:1px solid #374151;">'
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

# ---------- 52-week range (v5 mobile-robust via TD widths + nested tables) ----------

def _range_bar(range_pct, low52, high52):
    """
    Bulletproof mobile rendering:
    - Outer table width=100% (+ inline width) so it occupies the full card.
    - Three TDs use percentage widths (left/marker/right) that sum to 100.
    - Each TD contains an inner 100%-width table to force expansion in Gmail/Outlook mobile.
    - Uses bgcolor + height attributes (these have better support than CSS alone).
    """
    try:
        pos = float(range_pct) if range_pct is not None else 50.0
    except Exception:
        pos = 50.0
    if pos < 0: pos = 0.0
    if pos > 100: pos = 100.0

    marker_pct = 1.6  # ~5 px on 320px, ~10 px on 600px
    # Center the marker around pos; keep within [0,100]
    left = max(0.0, min(100.0 - marker_pct, pos - marker_pct / 2.0))
    right = max(0.0, 100.0 - marker_pct - left)

    # Guard tiny extremes so clients don't collapse to 0
    if left == 0.0:
        left = 0.2; right = max(0.0, 100.0 - marker_pct - left)
    if right == 0.0:
        right = 0.2; left = max(0.0, 100.0 - marker_pct - right)

    # Status subtitle
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

# ---------- main renderer ----------

def render_email(summary, companies, catalysts=None):
    asof = summary.get("as_of_ct", datetime.now().strftime("%b %d, %Y %H:%M CT"))
    up = summary.get("up_count", 0)
    down = summary.get("down_count", 0)
    movers_up = summary.get("top_winners", [])
    movers_down = summary.get("top_losers", [])
    catalysts = catalysts or summary.get("catalysts") or []

    # Heat strip
    heat = "".join(_heat_square(c.get("pct_1d")) for c in companies)

    # Map ticker -> news url for mover chips
    news_map = {c.get("ticker"): (c.get("news_url") or f"https://finance.yahoo.com/quote/{c.get('ticker')}/news") for c in companies}

    # Build mover chips
    winners_html = "".join(
        _mover_chip(m.get("ticker",""), float(m.get("pct",0) or 0), news_map.get(m.get("ticker"), "#"))
        for m in movers_up if m.get("ticker")
    )
    losers_html = "".join(
        _mover_chip(m.get("ticker",""), float(m.get("pct",0) or 0), news_map.get(m.get("ticker"), "#"))
        for m in movers_down if m.get("ticker")
    )

    # Build company card HTMLs (individual cards)
    card_html = []
    for c in companies:
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
        next_event = c.get("next_event")
        volx = c.get("vol_x_avg")
        news_url = c.get("news_url") or f"https://finance.yahoo.com/quote/{t}/news"
        pr_url = c.get("pr_url") or f"https://finance.yahoo.com/quote/{t}/press-releases"

        chips = "".join([_chip("1D", p1d), _chip("1W", p1w), _chip("1M", p1m), _chip("YTD", pytd)])

        bullets = []
        if headline:
            stamp = f" ({source}, {when})" if source and when else (f" ({source})" if source else (f" ({when})" if when else ""))
            bullets.append(f"{headline}{stamp}")
        if next_event:
            bullets.append(f"Next: {next_event}")
        if volx is not None:
            try:
                bullets.append(f"Volume: {float(volx):.2f}× 30-day avg")
            except Exception:
                pass
        bullets_html = "".join(f"<li>{escape(b)}</li>" for b in bullets)

        ctas = _button("Latest News", news_url) + _button("Press Releases", pr_url)

        range_html = _range_bar(range_pct, float(low52 or 0.0), float(high52 or 0.0))

        card = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:0 0 12px;background:#111;border:1px solid #2a2a2a;border-radius:8px;">
  <tr>
    <td style="padding:12px 14px;">
      <div style="font-weight:700;font-size:16px;line-height:1.3;color:#fff;">{escape(str(name))} <span style="color:#9aa0a6;">({escape(str(t))})</span></div>
      <div style="margin-top:2px;font-size:14px;color:#e5e7eb;">${price:.2f}</div>
      <div style="margin-top:8px;">{chips}</div>

      <div style="margin-top:10px;">{ctas}</div>

      <div style="margin-top:12px;">
        {range_html}
      </div>

      <ul style="margin:10px 0 0 16px;padding:0;color:#e5e7eb;font-size:13px;line-height:1.4;">
        {bullets_html}
      </ul>
    </td>
  </tr>
</table>
"""
        card_html.append(card)

    # Build 2-column grid: pair cards into rows with gutters
    rows = []
    for i in range(0, len(card_html), 2):
        left = card_html[i]
        right = card_html[i+1] if i+1 < len(card_html) else '<div style="height:0;"></div>'
        row = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
  <tr>
    <td class="stack-col" width="50%" style="vertical-align:top;padding-right:6px;">{left}</td>
    <td class="stack-col" width="50%" style="vertical-align:top;padding-left:6px;">{right}</td>
  </tr>
</table>
"""
        rows.append(row)

    # Upcoming catalysts module (if provided)
    catalysts_html = ""
    if catalysts:
        items_html = "".join(
            f'<div style="font-size:13px;color:#e5e7eb;margin:4px 0;">{escape(c.get("date_str",""))} • <strong>{escape(c.get("ticker",""))}</strong> • {escape(c.get("label",""))}</div>'
            for c in catalysts[:8]
        )
        catalysts_html = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;background:#111;border:1px solid #2a2a2a;border-radius:8px;">
  <tr><td style="padding:12px 14px;">
    <div style="font-weight:700;color:#fff;margin-bottom:6px;">Next 7 days</div>
    {items_html}
  </td></tr>
</table>
"""

    # ---------- full email ----------
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

        <!-- Header band -->
        <tr><td style="padding:12px 14px;background:#111;border:1px solid #2a2a2a;border-radius:8px;">
          <div style="font-weight:700;font-size:18px;color:#fff;">Weekly Company Intelligence Digest</div>
          <div style="font-size:13px;color:#9aa0a6;margin-top:2px;">{len(companies)} companies • {up} ↑ / {down} ↓ • Data as of {asof}</div>
          <div style="margin-top:8px;">{heat}</div>
        </td></tr>

        <!-- Top movers strip -->
        <tr><td style="padding:12px 14px 0;">
          <div style="margin:12px 0 6px;color:#e5e7eb;font-weight:700;">Top movers</div>
          <div>{winners_html}{losers_html}</div>
        </td></tr>

        <!-- 2-column company grid -->
        <tr><td style="padding-top:8px;">
          {''.join(rows)}
        </td></tr>

        <!-- Upcoming catalysts -->
        {f'<tr><td style="padding-top:8px;">{catalysts_html}</td></tr>' if catalysts_html else ''}

        <tr><td style="padding:16px 14px;color:#9aa0a6;font-size:12px;text-align:center;">
          Sources: price close & ranges; curated headlines. Times shown are Central Time.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return html
