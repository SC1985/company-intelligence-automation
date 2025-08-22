
from datetime import datetime, timezone
from html import escape
from email.utils import parsedate_to_datetime
import re
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

CENTRAL_TZ = ZoneInfo("America/Chicago") if ZoneInfo else None


# -----------------------------
# Date / time helpers
# -----------------------------
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


# -----------------------------
# UI atoms
# -----------------------------
def _coerce_float(x, default=0.0):
    try:
        return float(x)
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
    return (f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer" '
            f'style="background:#1f2937;color:#ffffff;text-decoration:none;'
            f'border-radius:6px;font-size:{fz};border:1px solid #374151;'
            f'line-height:1;white-space:nowrap;padding:6px 10px;display:inline-block;margin-right:4px;">'
            f'{safe_label} →</a>')


def _range_bar(pos: float, low: float, high: float):
    """Email-safe 52-week range bar with a 6px marker; table-only layout for Outlook."""
    try:
        pct = float(pos or 0.0)
    except Exception:
        pct = 0.0
    pct = max(0.0, min(100.0, pct))

    low = _coerce_float(low, 0.0)
    high = _coerce_float(high, 0.0)

    left_pct = pct
    right_pct = max(0.0, 100.0 - left_pct)
    marker_w = 6  # px

    track = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;table-layout:fixed;">'
        f'<tr style="height:6px;line-height:6px;font-size:0;">'
        f'<td width="{left_pct:.1f}%" style="width:{left_pct:.1f}%;background:#2a2a2a;height:6px;">&nbsp;</td>'
        f'<td width="{marker_w}" style="width:{marker_w}px;background:#3b82f6;height:6px;">&nbsp;</td>'
        f'<td width="{right_pct:.1f}%" style="width:{right_pct:.1f}%;background:#2a2a2a;height:6px;">&nbsp;</td>'
        f'</tr></table>'
    )
    caption = (f'<div style="font-size:12px;color:#9aa0a6;margin-top:4px;">'
               f'Low ${low:.2f} • High ${high:.2f}</div>')
    return (f'<div style="font-size:12px;color:#9aa0a6;margin-bottom:4px;">52-week range</div>'
            + track + caption)


def _belongs_to_company(headline: str, name: str, ticker: str) -> bool:
    """Heuristic: keep headlines that mention the ticker or meaningful parts of the company name."""
    s = (headline or "").lower()
    if not s:
        return False
    if str(ticker or "").lower() in s:
        return True
    # Tokenize company name; ignore common/short tokens
    name_tokens = [t for t in re.split(r"[^a-z0-9]+", (name or "").lower()) if len(t) >= 3]
    stop = {"inc", "corp", "llc", "the", "company", "limited", "plc", "holding", "holdings"}
    for t in name_tokens:
        if t in stop:
            continue
        if t and t in s:
            return True
    return False


def _nowrap_metrics(text: str) -> str:
    """Wrap tokens like m/m, y/y, q/q + value in a no-wrap span to prevent mid-token breaks."""
    if not text:
        return text
    pattern = re.compile(r"(?i)\\b([myq]/[myq]\\s*:?\\s*[+\\-]?\\d+(?:\\.\\d+)?%?)")
    def repl(m):
        return f'<span style="white-space:nowrap">{m.group(0)}</span>'
    return pattern.sub(repl, text)


# -----------------------------
# Company card
# -----------------------------
def _build_card(c):
    name = c.get("name") or c.get("ticker")
    t = c.get("ticker")
    price = _coerce_float(c.get("price"), 0.0)
    p1d, p1w, p1m, pytd = c.get("pct_1d"), c.get("pct_1w"), c.get("pct_1m"), c.get("pct_ytd")
    low52 = _coerce_float(c.get("low_52w"), 0.0)
    high52 = _coerce_float(c.get("high_52w"), 0.0)
    rp = c.get("range_pct")
    try:
        range_pct = float(rp) if rp is not None else 50.0
    except Exception:
        range_pct = 50.0

    headline = c.get("headline")
    source = c.get("source")
    when = c.get("when")
    when_fmt = _fmt_ct(when, force_time=False, tz_suffix_policy="never") if when else None

    next_event = c.get("next_event")
    volx = c.get("vol_x_avg")
    news_url = c.get("news_url") or f"https://finance.yahoo.com/quote/{t}/news"
    pr_url = c.get("pr_url") or f"https://finance.yahoo.com/quote/{t}/press-releases"

    # Metrics chips: two rows
    chips_row1 = "".join([_chip("1D", p1d), _chip("1W", p1w)])
    chips_row2 = "".join([_chip("1M", p1m), _chip("YTD", pytd)])
    chips_html = f'{chips_row1}<br/>{chips_row2}'

    bullets = []
    if headline and _belongs_to_company(headline, name, t):
        if source and when_fmt:
            bullets.append(f"★ {headline} ({source}, {when_fmt})")
        elif source:
            bullets.append(f"★ {headline} ({source})")
        elif when_fmt:
            bullets.append(f"★ {headline} ({when_fmt})")
        else:
            bullets.append(f"★ {headline}")
    else:
        bullets.append(f"★ Latest {name} coverage — see News")

    if next_event:
        ne_txt = _fmt_ct(next_event, force_time=False, tz_suffix_policy="never") if isinstance(next_event, (str, datetime)) else str(next_event)
        bullets.append(f"Next: {ne_txt}")
    if volx is not None:
        try:
            bullets.append(f"Volume: {float(volx):.2f}× 30-day avg")
        except Exception:
            pass

    # Build bullets HTML; first one clamped to 5 lines and flush-left
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

    range_html = _range_bar(range_pct, low52, high52)
    ctas = _button("News", news_url, size="md") + _button("Press", pr_url, size="md")

    price_fmt = f"${price:.4f}" if str(t).endswith("-USD") else f"${price:.2f}"
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;margin:0 0 6px;background:#111;
              border:1px solid #2a2a2a;mso-border-alt:1px solid #2a2a2a;
              border-radius:8px;"
       class="ci-card">
  <tr>
    <td style="padding:12px 14px;vertical-align:top;">
      <div class="ci-card-inner" style="max-height:300px;overflow:hidden;">
        <div style="font-weight:700;font-size:16px;line-height:1.3;color:#fff;">
          {escape(str(name))} <span style="color:#9aa0a6;">({escape(str(t))})</span>
        </div>
        <div style="margin-top:2px;font-size:14px;color:#e5e7eb;">{price_fmt}</div>
        <div style="margin-top:8px;">{chips_html}</div>
        <div style="margin-top:12px;">{range_html}</div>
        <ul style="margin:10px 0 0 0;padding:0;color:#e5e7eb;font-size:13px;line-height:1.4;">
          {bullets_html}
        </ul>
        <div style="margin-top:10px;">{ctas}</div>
      </div>
    </td>
  </tr>
</table>
"""


# -----------------------------
# Grid + Sections
# -----------------------------
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
            # Single card row (last odd item)
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


# -----------------------------
# Hero (Market Update)
# -----------------------------
def _select_hero(summary, companies):
    """Pick a hero article: prefer summary['hero'], else infer a market-wide item from company headlines."""
    hero = None
    if isinstance(summary, dict):
        if isinstance(summary.get("hero"), dict):
            hero = dict(summary["hero"])
        else:
            # Support flattened keys: hero_title, hero_url, hero_excerpt, hero_source, hero_when
            ht, hu = summary.get("hero_title"), summary.get("hero_url")
            if ht and hu:
                hero = {
                    "title": ht, "url": hu,
                    "excerpt": summary.get("hero_excerpt") or summary.get("hero_snippet"),
                    "source": summary.get("hero_source"),
                    "when": summary.get("hero_when"),
                }
    if not hero:
        # Infer from company headlines with broad-market keywords
        keywords = ("market", "stocks", "equities", "indexes", "indices", "nasdaq", "s&p", "dow", "fed", "inflation", "cpi", "jobs")
        best = None
        for c in companies or []:
            h = (c.get("headline") or "").strip()
            if not h:
                continue
            lower = h.lower()
            if any(k in lower for k in keywords):
                # Prefer the most recent
                when = c.get("when")
                dt = _parse_to_dt(when) if when else None
                cand = {"title": h, "url": c.get("news_url") or "", "source": c.get("source"), "when": when, "excerpt": c.get("excerpt") or c.get("summary")}
                if not best:
                    best = (dt, cand)
                else:
                    prev_dt, _ = best
                    if dt and (not prev_dt or dt > prev_dt):
                        best = (dt, cand)
        hero = best[1] if best else None
    # Sanity: must have title and url to render
    if not hero or not hero.get("title") or not hero.get("url"):
        return None
    return hero


def _render_hero(summary, companies):
    hero = _select_hero(summary, companies)
    if not hero:
        return ""  # quietly omit if none
    title = escape(str(hero.get("title", "")))
    url = escape(str(hero.get("url", "")))
    src = escape(str(hero.get("source") or "")) if hero.get("source") else ""
    when = hero.get("when")
    when_txt = _fmt_ct(when, force_time=False, tz_suffix_policy="never") if when else ""
    # Prefer explicit excerpt, else reuse title as a placeholder (so we always render something)
    excerpt = hero.get("excerpt") or ""
    excerpt = escape(str(excerpt)) if excerpt else title

    meta = " • ".join([p for p in [src, when_txt] if p])
    meta_html = f'<div style="color:#9aa0a6;font-size:12px;margin-top:6px;">{meta}</div>' if meta else ""

    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;background:#0f172a;border:1px solid #2a2a2a;
              mso-border-alt:1px solid #2a2a2a;border-radius:10px;margin:14px 0 0 0;">
  <tr>
    <td style="padding:16px;">
      <div style="font-weight:700;font-size:18px;letter-spacing:0.2px;color:#93c5fd;">Market Update</div>
      <a href="{url}" target="_blank" rel="noopener noreferrer"
         style="display:block;margin-top:6px;text-decoration:none;">
        <div style="font-weight:700;font-size:20px;line-height:1.35;color:#e5e7eb;">{title}</div>
      </a>
      <div style="margin-top:8px;font-size:14px;line-height:1.5;
                  display:-webkit-box;-webkit-box-orient:vertical;
                  -webkit-line-clamp:18;overflow:hidden;text-overflow:ellipsis;
                  max-height:calc(1.5em * 18);">
        {excerpt}
      </div>
      {meta_html}
      <div style="margin-top:10px;">{_button("Read article", hero.get("url") or "#", size="md")}</div>
    </td>
  </tr>
</table>
"""


# -----------------------------
# Main render
# -----------------------------
def render_email(summary, companies, cryptos=None):
    """Builds the full HTML email."""
    # Prepare cards
    company_cards = []
    crypto_cards = []

    for c in companies or []:
        asset_class = str(c.get("asset_class") or "").lower()
        sym = str(c.get("ticker") or "")
        if asset_class == "crypto" or sym.endswith("-USD"):
            crypto_cards.append(_build_card(c))
        else:
            company_cards.append(_build_card(c))

    if cryptos:
        crypto_cards = [_build_card(c) for c in cryptos or []]

    as_of = summary.get("as_of_ct") if isinstance(summary, dict) else None
    as_of_txt = _fmt_ct(as_of, force_time=True, tz_suffix_policy="always") if as_of else ""

    stocks_section = _section_container("Stocks & ETFs", _grid(company_cards)) if company_cards else ""
    crypto_section  = _section_container("Digital Assets", _grid(crypto_cards)) if crypto_cards else ""

    hero_html = _render_hero(summary, companies)

    html = f"""<!DOCTYPE html>
<html>
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Intelligence Digest</title>
    <style>
      @media only screen and (max-width: 620px) {{
        .stack-col {{ display:block !important; width:100% !important; max-width:100% !important; padding-left:0 !important; padding-right:0 !important; }}
      }}
      /* Desktop cards cap; mobile grows naturally */
      .ci-card-inner {{ max-height:300px; overflow:hidden; }}
      @media only screen and (max-width: 620px) {{
        .ci-card-inner {{ max-height:none !important; overflow:visible !important; }}
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
