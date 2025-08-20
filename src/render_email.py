# src/render_email.py
from datetime import datetime
from html import escape

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

def render_email(summary, companies):
    asof = summary.get("as_of_ct", datetime.now().strftime("%b %d, %Y %H:%M CT"))
    up = summary.get("up_count", 0)
    down = summary.get("down_count", 0)
    movers_up = summary.get("top_winners", [])
    movers_down = summary.get("top_losers", [])

    heat = "".join(_heat_square(c.get("pct_1d")) for c in companies)

    cards = []
    for c in companies:
        name = c.get("name") or c.get("ticker")
        t = c.get("ticker")
        price = c.get("price") or 0.0
        p1d, p1w, p1m, pytd = c.get("pct_1d"), c.get("pct_1w"), c.get("pct_1m"), c.get("pct_ytd")
        low52, high52 = c.get("low_52w") or 0.0, c.get("high_52w") or 0.0
        range_pct = c.get("range_pct") or 50.0
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

        # CTA area (replaces the sparkline)
        ctas = _button("Latest News", news_url) + _button("Press Releases", pr_url)

        card = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:0 0 12px;background:#111;border:1px solid #2a2a2a;border-radius:8px;">
  <tr>
    <td style="padding:12px 14px;">
      <div style="font-weight:700;font-size:16px;line-height:1.3;color:#fff;">{escape(str(name))} <span style="color:#9aa0a6;">({escape(str(t))})</span></div>
      <div style="margin-top:2px;font-size:14px;color:#e5e7eb;">${price:.2f}</div>
      <div style="margin-top:8px;">{chips}</div>

      <div style="margin-top:10px;">{ctas}</div>

      <div style="margin-top:12px;">
        <div style="font-size:12px;color:#9aa0a6;margin-bottom:4px;">52-week range</div>
        <div style="position:relative;height:6px;background:#2a2a2a;border-radius:4px;">
          <div style="position:absolute;left:{range_pct:.2f}%;top:-4px;width:2px;height:14px;background:#e5e7eb;"></div>
        </div>
        <div style="font-size:12px;color:#9aa0a6;margin-top:4px;">Low ${low52:.2f} • High ${high52:.2f}</div>
      </div>

      <ul style="margin:10px 0 0 16px;padding:0;color:#e5e7eb;font-size:13px;line-height:1.4;">
        {bullets_html}
      </ul>
    </td>
  </tr>
</table>
"""
        cards.append(card)

    winners_html = "".join(
        f'<div style="margin-right:12px;"><strong style="color:#34d399;">▲ {escape(str(m.get("ticker")))}</strong> {m.get("pct",0):+.2f}%</div>'
        for m in movers_up
    )
    losers_html = "".join(
        f'<div style="margin-right:12px;"><strong style="color:#f87171;">▼ {escape(str(m.get("ticker")))}</strong> {m.get("pct",0):+.2f}%</div>'
        for m in movers_down
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="color-scheme" content="dark light">
  <meta name="supported-color-schemes" content="dark light">
  <title>Weekly Company Intelligence Digest</title>
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

        <tr><td style="padding:12px 0;">
          <table role="presentation" width="100%">
            <tr>
              <td style="padding:0 14px;">
                <div style="font-weight:700;color:#e5e7eb;margin-bottom:6px;">Top movers</div>
                <div style="display:flex;flex-wrap:wrap;color:#e5e7eb;">
                  {winners_html}{losers_html}
                </div>
              </td>
            </tr>
          </table>
        </td></tr>

        <tr><td style="padding-top:8px;">
          {''.join(cards)}
        </td></tr>

        <tr><td style="padding:16px 14px;color:#9aa0a6;font-size:12px;text-align:center;">
          Sources: price close & ranges; curated headlines. Times shown are Central Time.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return html
