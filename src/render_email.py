"""
Mobile-first HTML renderer for the Weekly Company & Markets Digest.

Input: a `companies` list of dicts where each item may include:
  - symbol (str), name (str)
  - last (float) latest price (or None)
  - pct_1d, pct_1w, pct_1m, pct_ytd (float|None)  # chips
  - wk52_low, wk52_high, wk52_pos (float|None)    # optional 52-week bar
  - news_url, press_url (str|None)                # optional CTAs
  - error (str|None)                              # optional data status

Output: HTML string (inline CSS, table-based layout for email clients)
"""

from datetime import datetime

def _fmt_pct(x):
    if x is None:
        return None
    try:
        # keep sign; 2 decimals
        return f"{x:+.2f}%"
    except Exception:
        return None

def _fmt_price(x):
    if x is None:
        return "—"
    try:
        # No currency symbol to avoid locale issues inside email clients
        if x >= 1000:
            return f"{x:,.2f}"
        if x >= 1:
            return f"{x:.2f}"
        return f"{x:.6f}".rstrip("0").rstrip(".")
    except Exception:
        return "—"

def _chip(label, val):
    """Return a chip span for a percent value, or empty string if None."""
    pct = _fmt_pct(val)
    if pct is None:
        return ""
    # green for positive, red for negative/zero
    color = "#087443" if val > 0 else "#B42318"
    arrow = "▲" if val > 0 else "▼"
    return (
        f'<span style="display:inline-block;padding:2px 6px;margin-right:6px;'
        f'border-radius:12px;font-size:12px;line-height:16px;'
        f'background:#F2F4F7;color:{color};font-weight:600">'
        f'{label} {arrow} {pct}</span>'
    )

def _chips_row(item):
    parts = [
        _chip("1D", item.get("pct_1d")),
        _chip("1W", item.get("pct_1w")),
        _chip("1M", item.get("pct_1m")),
        _chip("YTD", item.get("pct_ytd")),
    ]
    # filter out blanks to avoid awkward gaps when values are None
    parts = [p for p in parts if p]
    return "".join(parts) if parts else ""

def _wk52_bar(item):
    """Optional 52-week range bar; render only when enough data provided."""
    lo = item.get("wk52_low")
    hi = item.get("wk52_high")
    pos = item.get("wk52_pos")  # 0..1 where 1 is the high
    if lo is None or hi is None or pos is None:
        return ""

    # Constrain marker position
    try:
        pos = max(0.0, min(1.0, float(pos)))
    except Exception:
        pos = 0.0

    # Render a simple table-safe bar
    track_w = 220
    marker_x = int(pos * track_w)

    return f"""
    <div style="margin-top:8px;font-size:12px;color:#475467">
      <div style="position:relative;width:{track_w}px;height:6px;background:#E4E7EC;border-radius:3px;">
        <div style="position:absolute;left:{marker_x-3}px;top:-2px;width:6px;height:10px;background:#344054;border-radius:2px;"></div>
      </div>
      <div style="display:flex;justify-content:space-between;width:{track_w}px;">
        <span>52W Low {_fmt_price(lo)}</span>
        <span>52W High {_fmt_price(hi)}</span>
      </div>
    </div>
    """

def _ctas(item):
    news = item.get("news_url")
    press = item.get("press_url")
    btn_style = (
        "display:inline-block;padding:6px 10px;margin-right:8px;"
        "border:1px solid #D0D5DD;border-radius:6px;font-size:12px;"
        "text-decoration:none;color:#344054;background:#FFFFFF"
    )
    html = []
    if news:
        html.append(f'<a href="{news}" style="{btn_style}">News</a>')
    if press:
        html.append(f'<a href="{press}" style="{btn_style}">Press</a>')
    return "".join(html)

def _error_badge(msg):
    if not msg:
        return ""
    return (
        '<div style="margin-top:8px;font-size:12px;color:#B42318;'
        'background:#FEF3F2;border:1px solid #FEE4E2;border-radius:6px;'
        'padding:6px 8px;display:inline-block;">'
        f'⚠︎ {msg}'
        '</div>'
    )

def _card(item):
    name = item.get("name") or item.get("symbol") or "—"
    symbol = item.get("symbol") or ""
    last = _fmt_price(item.get("last"))
    chips = _chips_row(item)
    bar = _wk52_bar(item)
    ctas = _ctas(item)
    err = _error_badge(item.get("error"))

    return f"""
    <td style="vertical-align:top;padding:8px 8px 12px 8px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #E4E7EC;border-radius:12px">
        <tr>
          <td style="padding:12px 12px 6px 12px">
            <div style="font-size:14px;color:#667085">{symbol}</div>
            <div style="font-size:16px;font-weight:700;color:#101828;line-height:22px">{name}</div>
            <div style="margin-top:4px;font-size:14px;color:#101828">Last: {last}</div>
            <div style="margin-top:8px">{chips}</div>
            {bar}
            <div style="margin-top:10px">{ctas}</div>
            {err}
          </td>
        </tr>
      </table>
    </td>
    """

def render(companies):
    """
    Render the full email HTML.
    - Two-column desktop via table, single-column mobile stacking (100% width).
    - Gracefully omits chips if values are None (e.g., missing YTD).
    """
    # Build rows of two cards
    tds = []
    for item in companies:
        tds.append(_card(item))
    # group into rows of 2
    rows = []
    for i in range(0, len(tds), 2):
        chunk = tds[i:i+2]
        if len(chunk) == 1:
            chunk.append('<td style="padding:8px"></td>')
        rows.append("<tr>" + "".join(chunk) + "</tr>")

    now_ct = datetime.now().strftime("%-m/%-d/%Y %-I:%M %p CST")  # per spec, show CST label
    header = (
        '<div style="font-size:14px;color:#475467;margin-bottom:8px">'
        f'Data as of {now_ct}'
        '</div>'
    )

    # Outer shell
    html = f"""\
<!DOCTYPE html>
<html>
  <body style="margin:0;padding:0;background:#F9FAFB">
    <center>
      <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:680px;margin:0 auto;background:#FFFFFF">
        <tr>
          <td style="padding:16px 16px 8px 16px">
            <div style="font-size:20px;font-weight:800;color:#101828">Company & Markets Digest</div>
            {header}
          </td>
        </tr>
        <tr>
          <td style="padding:0 8px 16px 8px">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              {''.join(rows)}
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding:12px 16px 24px 16px;color:#667085;font-size:12px;border-top:1px solid #E4E7EC">
            You’re receiving this because you opted in to the weekly digest.
          </td>
        </tr>
      </table>
    </center>
  </body>
</html>
"""
    return html
