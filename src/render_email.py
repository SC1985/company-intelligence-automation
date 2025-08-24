# src/render_email.py

# Fixed: Using hybrid color scheme that works in both dark and light modes

# No reliance on prefers-color-scheme which does not work in Gmail

from datetime import datetime, timezone
from html import escape
from email.utils import parsedate_to_datetime
import re

try:
from zoneinfo import ZoneInfo
except Exception:
ZoneInfo = None

CENTRAL_TZ = ZoneInfo(“America/Chicago”) if ZoneInfo else None

# ––––– Enhanced time helpers –––––

def _parse_to_dt(value):
“”“Enhanced datetime parsing with better error handling.”””
if value is None:
return None
if isinstance(value, datetime):
return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
s = str(value).strip()
if not s:
return None

```
# Handle epoch seconds/milliseconds
if s.isdigit():
    try:
        iv = int(s)
        if iv > 10_000_000_000:  # Likely milliseconds
            iv //= 1000
        return datetime.fromtimestamp(iv, tz=timezone.utc)
    except (ValueError, OverflowError):
        pass

# Handle ISO 8601 formats
try:
    s2 = s[:-1] + "+00:00" if s.endswith("Z") else s
    dt = datetime.fromisoformat(s2)
    if dt and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
except ValueError:
    pass

# RFC 2822 format
try:
    dt = parsedate_to_datetime(s)
    if dt and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
except (ValueError, TypeError):
    pass

# Date-only fallback
try:
    if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
        return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
except ValueError:
    pass

return None
```

def _fmt_ct(value, force_time=None, tz_suffix_policy=“auto”):
“”“Enhanced Central Time formatting with better error handling.”””
dt = _parse_to_dt(value) or value
if not isinstance(dt, datetime):
return str(value)

```
try:
    dtc = dt.astimezone(CENTRAL_TZ) if CENTRAL_TZ else dt
except (ValueError, OverflowError):
    dtc = dt

has_time = not (dtc.hour == 0 and dtc.minute == 0 and dtc.second == 0)
show_time = force_time if force_time is not None else has_time

try:
    out = dtc.strftime("%m/%d/%Y %H:%M") if show_time else dtc.strftime("%m/%d/%Y")
except (ValueError, OverflowError):
    return str(value)

if tz_suffix_policy == "always":
    return out + " CST"
if tz_suffix_policy == "auto" and show_time:
    return out + " CST"
return out
```

# ––––– Enhanced visual helpers –––––

def _safe_float(x, default=None):
“”“Enhanced float conversion with better validation.”””
if x is None:
return default
try:
val = float(x)
# Filter out obvious bad data
if val != val:  # NaN check
return default
if abs(val) > 1e10:  # Unreasonably large
return default
return val
except (ValueError, TypeError, OverflowError):
return default

def _chip(label: str, value):
“”“Performance chip with hybrid colors that work in both modes.”””
v = _safe_float(value, None)

```
if v is None:
    # Neutral gray that works in both modes
    bg = "#6B7280"
    color = "#FFFFFF"
    sign = ""
    txt = "--"
else:
    if v >= 0:
        # Green that is visible in both modes
        bg = "#10B981"
        color = "#FFFFFF"
        sign = "▲"
    else:
        # Red that is visible in both modes
        bg = "#EF4444"
        color = "#FFFFFF"
        sign = "▼"
    txt = f"{abs(v):.1f}%"

safe_label = escape(label)

return (f'<span style="background:{bg};color:{color};'
        f'padding:5px 12px;border-radius:12px;font-size:12px;font-weight:700;'
        f'margin:2px 6px 4px 0;display:inline-block;'
        f'box-shadow:0 2px 6px rgba(0,0,0,0.15);white-space:nowrap;'
        f'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;"'
        f'>{safe_label} {sign} {txt}</span>')
```

def _button(label: str, url: str, style=“primary”):
“”“Button with hybrid colors.”””
safe_label = escape(label)
href = escape(url or “#”)

```
if style == "primary":
    bg = "#4B5563"
    color = "#FFFFFF"
else:  # secondary
    bg = "#9CA3AF"
    color = "#FFFFFF"

return (f'<table role="presentation" cellpadding="0" cellspacing="0" style="display:inline-block;margin-right:8px;margin-bottom:4px;">'
        f'<tr><td style="background:{bg};color:{color};'
        f'border-radius:10px;font-size:13px;font-weight:600;padding:10px 16px;'
        f'box-shadow:0 2px 6px rgba(0,0,0,0.15);'
        f'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">'
        f'<a href="{href}" target="_blank" rel="noopener noreferrer" '
        f'style="color:{color};text-decoration:none;display:block;">'
        f'{safe_label} →</a></td></tr></table>')
```

def _range_bar(pos: float, low: float, high: float):
“”“52-week range bar with hybrid colors.”””
pct = max(0.0, min(100.0, _safe_float(pos, 0.0)))
left = f”{pct:.1f}%”
right = f”{100 - pct:.1f}%”

```
low_v = _safe_float(low, 0.0) or 0.0
high_v = _safe_float(high, 0.0) or 0.0
current_v = low_v + (high_v - low_v) * (pct / 100.0) if high_v > low_v else low_v

# Position-based marker colors
if pct < 25:
    marker_color = "#EF4444"  # Red
    marker_label = "Low"
elif pct > 75:  
    marker_color = "#10B981"  # Green
    marker_label = "High"
else:
    marker_color = "#3B82F6"  # Blue
    marker_label = "Mid"

# Neutral gray track that works in both modes
track_bg = "#E5E7EB"

# Track
track = (
    f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
    f'style="border-collapse:collapse;border-radius:8px;'
    f'background:{track_bg};height:10px;overflow:hidden;'
    f'min-width:200px;box-shadow:inset 0 1px 2px rgba(0,0,0,0.1);">'
    f'<tr>'
    f'<td style="width:{left};background:{track_bg};height:10px;padding:0;">&nbsp;</td>'
    f'<td style="width:10px;background:{marker_color};height:10px;padding:0;">&nbsp;</td>'
    f'<td style="width:{right};background:{track_bg};height:10px;padding:0;">&nbsp;</td>'
    f'</tr></table>'
)

# Caption
caption = (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:6px;">'
           f'<tr>'
           f'<td style="font-size:11px;color:#6B7280;text-align:left;font-weight:500;">Low ${low_v:.2f}</td>'
           f'<td style="font-size:12px;color:{marker_color};font-weight:700;text-align:center;">'
           f'${current_v:.2f}</td>'
           f'<td style="font-size:11px;color:#6B7280;text-align:right;font-weight:500;">High ${high_v:.2f}</td>'
           f'</tr></table>')

return (f'<div style="margin:14px 0 10px 0;">'
        f'<div style="font-size:12px;color:#374151;margin-bottom:6px;font-weight:600;">'
        f'52-Week Range</div>'
        + track + caption + '</div>')
```

def _belongs_to_company(c: dict, headline: str) -> bool:
“”“Enhanced company-headline matching with better tokenization.”””
if not c or not headline:
return False

```
name = str(c.get("name") or "").lower()
ticker = str(c.get("ticker") or c.get("symbol") or "").lower()

base_tokens = set()
if name:
    tokens = re.split(r"[\s&,\.-]+", name)
    for tok in tokens:
        if len(tok) > 2 and tok not in ("inc", "ltd", "corp", "llc", "the", "and"):
            base_tokens.add(tok)

if ticker and len(ticker) > 1:
    base_tokens.add(ticker)

# Special handling for crypto
if ticker.endswith("-usd"):
    base_name = ticker.replace("-usd", "")
    if len(base_name) > 2:
        base_tokens.add(base_name)

h_lower = headline.lower()

# Check for exact matches with word boundaries
for token in base_tokens:
    if token and re.search(rf'\b{re.escape(token)}\b', h_lower):
        return True

return False
```

# ––––– Enhanced hero content parsing –––––

def _strip_tags(html: str) -> str:
“”“Enhanced HTML tag stripping with better whitespace handling.”””
if not html:
return “”

```
# Remove HTML tags
text = re.sub(r'<[^>]+>', ' ', html)
# Clean up whitespace
text = re.sub(r'\s+', ' ', text)
# Remove common HTML entities
text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')

return text.strip()
```

def _first_paragraph(hero: dict, title: str = “”) -> str:
“”“Enhanced paragraph extraction with better content prioritization.”””
if not hero:
return “”

```
title_words = set(re.findall(r'\w+', (title or "").lower()))

# Priority order of fields to check
content_fields = [
    # HTML content fields (highest priority)
    ("body_html", "content_html", "article_html", "summary_html"),
    # Structured content
    ("paragraphs", "content_paragraphs", "sections"),
    # Text fields
    ("first_paragraph", "lede", "lead", "dek", "abstract"),
    ("description", "summary", "excerpt", "content", "body"),
    ("snippet", "preview", "preview_text", "text")
]

for field_group in content_fields:
    for field in field_group:
        content = hero.get(field)
        if not content:
            continue
        
        # Handle different content types
        if isinstance(content, (list, tuple)):
            for item in content:
                text = _strip_tags(str(item))
                if text and len(text) > 20:
                    # Check for title overlap
                    text_words = set(re.findall(r'\w+', text.lower()))
                    overlap = len(title_words.intersection(text_words))
                    if overlap < len(title_words) * 0.7:  # Less than 70% overlap
                        return text
        else:
            # HTML content
            if field.endswith('_html'):
                # Extract paragraphs from HTML
                paras = re.findall(r'<p[^>]*>(.*?)</p>', str(content), re.I | re.S)
                for para in paras:
                    text = _strip_tags(para)
                    if text and len(text) > 15:
                        text_words = set(re.findall(r'\w+', text.lower()))
                        overlap = len(title_words.intersection(text_words))
                        if overlap < len(title_words) * 0.7:
                            return text
            
            # Plain text content
            text = _strip_tags(str(content))
            if not text or len(text) < 15:
                continue
            
            # Split into sentences/paragraphs
            segments = re.split(r'[.!?]\s+|\n\n+', text)
            for segment in segments:
                segment = segment.strip()
                if len(segment) > 20:
                    segment_words = set(re.findall(r'\w+', segment.lower()))
                    overlap = len(title_words.intersection(segment_words))
                    if overlap < len(title_words) * 0.7:
                        return segment

return ""
```

def _select_hero(summary: dict, companies: list, cryptos: list):
“”“Enhanced hero selection with better scoring.”””
# Check for explicit hero in summary
hero = None
if isinstance(summary, dict):
hero_candidates = [
summary.get(“hero”),
summary.get(“market_hero”),
summary.get(“market”),
summary.get(“lead_story”)
]

```
    for cand in hero_candidates:
        if isinstance(cand, dict) and cand.get("title"):
            # Validate hero has meaningful content
            if (cand.get("body") or cand.get("description") or 
                cand.get("content") or cand.get("first_paragraph")):
                hero = cand
                break

if hero:
    return hero

# Enhanced fallback: find best entity-based hero
all_entities = (companies or []) + (cryptos or [])

# Scoring criteria for hero selection
hero_candidates = []

market_keywords = {
    "broad_market": ["market", "stocks", "equities", "indices", "s&p", "nasdaq", "dow", "trading"],
    "economic": ["fed", "federal reserve", "inflation", "cpi", "jobs", "employment", "rates", "treasury"],
    "sector": ["tech", "technology", "ai", "crypto", "bitcoin", "energy", "healthcare"],
    "events": ["earnings", "guidance", "outlook", "merger", "acquisition", "ipo"]
}

for entity in all_entities:
    headline = entity.get("headline", "")
    if not headline:
        continue
    
    score = 0
    headline_lower = headline.lower()
    
    # Score based on market relevance
    for category, keywords in market_keywords.items():
        for keyword in keywords:
            if keyword in headline_lower:
                if category == "broad_market":
                    score += 15
                elif category == "economic":
                    score += 12
                elif category == "sector":
                    score += 8
                else:
                    score += 5
    
    # Boost for recent content
    if entity.get("when"):
        try:
            pub_date = _parse_to_dt(entity.get("when"))
            if pub_date:
                hours_ago = (datetime.now(timezone.utc) - pub_date).total_seconds() / 3600
                if hours_ago < 12:
                    score += 10
                elif hours_ago < 24:
                    score += 5
        except:
            pass
    
    # Boost for quality content
    description = entity.get("description", "")
    if description and len(description) > 50:
        score += 8
    
    if score > 5:  # Minimum threshold
        hero_candidates.append((score, entity))

# Select the best candidate
if hero_candidates:
    hero_candidates.sort(reverse=True, key=lambda x: x[0])
    _, best_entity = hero_candidates[0]
    
    return {
        "title": best_entity.get("headline"),
        "url": best_entity.get("news_url", ""),
        "source": best_entity.get("source", ""),
        "when": best_entity.get("when"),
        "body": best_entity.get("description", ""),
        "description": best_entity.get("description", "")
    }

return None
```

def _render_hero(hero: dict) -> str:
“”“Hero rendering with hybrid colors.”””
if not hero:
return “”

```
title = (hero.get("title") or "").strip()
if not title:
    return ""

url = hero.get("url") or "#"
source = hero.get("source") or ""
when = _fmt_ct(hero.get("when"), force_time=False, tz_suffix_policy="never") if hero.get("when") else ""

# Enhanced paragraph extraction
para = _first_paragraph(hero, title=title)

# Truncate paragraph if too long
if para and len(para) > 280:
    # Find a good breaking point
    sentences = re.split(r'[.!?]\s+', para)
    truncated = ""
    for sentence in sentences:
        if len(truncated + sentence) <= 220:
            truncated += sentence + ". "
        else:
            break
    para = truncated.strip()

# Body HTML
body_html = ""
if para:
    body_html = f'''
    <tr><td style="padding-top:14px;font-size:15px;line-height:1.6;
                 color:#374151;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">
        {escape(para)}
    </td></tr>'''

# Metadata line
meta_parts = []
if source:
    meta_parts.append(f'<span style="font-weight:600;color:#7C3AED;">{escape(source)}</span>')
if when:
    meta_parts.append(f'<span style="color:#6B7280;">{escape(when)}</span>')

meta_html = ""
if meta_parts:
    meta_html = f'''
    <tr><td style="padding-top:14px;font-size:13px;
                 border-top:1px solid #E5E7EB;
                 padding-top:12px;color:#6B7280;">
        {" • ".join(meta_parts)}
    </td></tr>'''

# Hero container with light background
return f"""
```

<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;
              background:#FFFFFF;
              border:1px solid #E5E7EB;
              border-radius:16px;margin:20px 0;
              box-shadow:0 4px 12px rgba(0,0,0,0.08);">
  <tr>
    <td style="padding:28px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="font-weight:700;font-size:24px;line-height:1.3;color:#111827;
                     font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">
          <a href="{escape(url)}" style="color:#111827;text-decoration:none;">
            {escape(title)}
          </a>
        </td></tr>
        {body_html}
        {meta_html}
      </table>
    </td>
  </tr>
</table>
"""

# ––––– Enhanced card system –––––

def _build_card(c):
“”“Card building with hybrid colors.”””
name = c.get(“name”) or c.get(“ticker”) or c.get(“symbol”) or “Unknown”
ticker = str(c.get(“ticker”) or c.get(“symbol”) or “”)
is_crypto = ticker.endswith(”-USD”) or (str(c.get(“asset_class”) or “”).lower() == “crypto”)

```
# Price formatting
price_v = _safe_float(c.get("price"), None)
if price_v is None:
    price_fmt = '<span style="color:#9CA3AF;">--</span>'
else:
    if is_crypto:
        if price_v >= 1000:
            price_fmt = f'<span style="color:#111827;font-weight:700;">${price_v:,.0f}</span>'
        elif price_v >= 1:
            price_fmt = f'<span style="color:#111827;font-weight:700;">${price_v:,.2f}</span>'
        else:
            price_fmt = f'<span style="color:#111827;font-weight:700;">${price_v:.4f}</span>'
    else:
        price_fmt = f'<span style="color:#111827;font-weight:700;">${price_v:,.2f}</span>'

# Performance chips
chips_line1 = _chip("1D", c.get("pct_1d")) + _chip("1W", c.get("pct_1w"))
chips_line2 = _chip("1M", c.get("pct_1m")) + _chip("YTD", c.get("pct_ytd"))

chips = f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:12px 0;">
    <tr><td style="line-height:1.6;padding-bottom:6px;">{chips_line1}</td></tr>
    <tr><td style="line-height:1.6;">{chips_line2}</td></tr>
</table>'''

# News bullet
bullets = []
headline = c.get("headline")
source = c.get("source")
when_fmt = _fmt_ct(c.get("when"), force_time=False, tz_suffix_policy="never") if c.get("when") else None

if headline and _belongs_to_company(c, headline):
    # Truncate long headlines
    display_headline = headline[:100] + "..." if len(headline) > 100 else headline
    
    if source and when_fmt:
        bullets.append(f'★ {display_headline} <span style="color:#6B7280;">({source}, {when_fmt})</span>')
    elif source:
        bullets.append(f'★ {display_headline} <span style="color:#6B7280;">({source})</span>')
    elif when_fmt:
        bullets.append(f'★ {display_headline} <span style="color:#6B7280;">({when_fmt})</span>')
    else:
        bullets.append(f"★ {display_headline}")
else:
    company_name = name.replace(" Inc.", "").replace(" Corporation", "").strip()
    bullets.append(f'★ <span style="color:#6B7280;">Latest {company_name} coverage — see News</span>')

# Additional context bullets
next_event = c.get("next_event")
if next_event:
    event_date = _fmt_ct(next_event, force_time=False, tz_suffix_policy="never")
    if event_date:
        bullets.append(f'<span style="color:#7C3AED;">📅 Next: {event_date}</span>')

vol_multiplier = _safe_float(c.get("vol_x_avg"), None)
if vol_multiplier is not None and vol_multiplier > 1.5:
    bullets.append(f'<span style="color:#F59E0B;">📊 Volume: {vol_multiplier:.1f}× avg</span>')

# Bullets HTML
bullets_html = ""
for i, bullet in enumerate(bullets):
    if i == 0:  # Main news item
        bullets_html += f'''
        <tr><td style="padding-bottom:10px;
                      display:-webkit-box;-webkit-box-orient:vertical;
                      -webkit-line-clamp:3;overflow:hidden;text-overflow:ellipsis;
                      line-height:1.5;color:#374151;font-size:14px;font-weight:500;">
            {bullet}
        </td></tr>'''
    else:  # Secondary items
        bullets_html += f'''
        <tr><td style="padding-bottom:6px;font-size:12px;line-height:1.4;color:#6B7280;">
            {bullet}
        </td></tr>'''

# Range bar
range_html = _range_bar(
    _safe_float(c.get("range_pct"), 50.0),
    _safe_float(c.get("low_52w"), 0.0),
    _safe_float(c.get("high_52w"), 0.0)
)

# Action buttons
news_url = c.get("news_url") or f"https://finance.yahoo.com/quote/{escape(ticker)}/news"
pr_url = c.get("pr_url") or f"https://finance.yahoo.com/quote/{escape(ticker)}/press-releases"

ctas = f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
    <tr><td style="border-top:1px solid #E5E7EB;padding-top:14px;">
        {_button("News", news_url, "primary")}
        {_button("Press", pr_url, "secondary")}
    </td></tr>
</table>'''

# Card with light background
return f"""
```

<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;margin:0 0 12px;
              background:#FFFFFF;
              border:1px solid #E5E7EB;
              border-radius:14px;
              box-shadow:0 2px 8px rgba(0,0,0,0.06);overflow:hidden;">
  <tr>
    <td style="padding:20px 22px;max-height:360px;overflow:hidden;vertical-align:top;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <!-- Header -->
        <tr><td>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
            <tr><td style="font-weight:700;font-size:17px;line-height:1.3;color:#111827;
                         font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;
                         padding-bottom:4px;">{escape(str(name))}</td></tr>
            <tr><td>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="font-size:13px;color:#6B7280;font-weight:600;">({escape(ticker)})</td>
                  <td style="text-align:right;font-size:16px;">{price_fmt}</td>
                </tr>
              </table>
            </td></tr>
          </table>
        </td></tr>

```
    <!-- Performance chips -->
    <tr><td>{chips}</td></tr>
    
    <!-- 52-week range -->  
    <tr><td>{range_html}</td></tr>
    
    <!-- News and events -->
    <tr><td>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px;">
        {bullets_html}
      </table>
    </td></tr>
    
    <!-- Action buttons -->
    <tr><td>{ctas}</td></tr>
  </table>
</td>
```

  </tr>
</table>
"""

def _grid(cards):
“”“Two-column grid that becomes single column on mobile.”””
if not cards:
return “”

```
rows = []
for i in range(0, len(cards), 2):
    left = cards[i]
    right = cards[i + 1] if i + 1 < len(cards) else ""
    
    if right:
        row = f'''
```

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-bottom:8px;">
  <tr>
    <td class="stack-col" width="50%" style="vertical-align:top;padding-right:8px;">{left}</td>
    <td class="stack-col" width="50%" style="vertical-align:top;padding-left:8px;">{right}</td>
  </tr>
</table>'''
        else:
            row = f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-bottom:8px;">
  <tr>
    <td class="stack-col" style="vertical-align:top;max-width:320px;margin:0 auto;">{left}</td>
  </tr>
</table>'''

```
    rows.append(row)

return "".join(rows)
```

def _section_container(title: str, inner_html: str):
“”“Section container with hybrid colors.”””
safe_title = escape(title)
return f”””

<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;background:#F9FAFB;
              border-radius:16px;margin:24px 0;
              box-shadow:0 2px 8px rgba(0,0,0,0.04);">
  <tr>
    <td style="padding:28px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="font-weight:700;font-size:28px;color:#111827;
                     font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;
                     margin:0 0 20px 0;padding-bottom:16px;">
          {safe_title}
        </td></tr>
        <tr><td>{inner_html}</td></tr>
      </table>
    </td>
  </tr>
</table>
"""

def _generate_enhanced_preview() -> str:
“”“Generate compelling preview text optimized for inbox engagement.”””
now = datetime.now()
current_time = now.strftime(”%H:%M”)
day_name = now.strftime(”%A”)

```
# More engaging preview options
preview_options = [
    f"🔥 {current_time} Market Intelligence: Top movers, breaking news & strategic signals across your portfolio",
    f"⚡ {day_name} Digest: Live performance data, sentiment analysis & key developments in your holdings", 
    f"📈 Strategic Brief {current_time}: Real-time insights, news synthesis & momentum indicators for smart decisions",
    f"🎯 Portfolio Pulse: Market movements, sector analysis & breaking news from your strategic investments",
    f"💡 {current_time} Intelligence: Performance metrics, news highlights & market opportunities at your fingertips"
]

# Add variety based on time of day
hour = now.hour
if 5 <= hour < 12:
    preview_options.append(f"🌅 Morning Intelligence: Pre-market insights & overnight developments in your portfolio")
elif 12 <= hour < 17:
    preview_options.append(f"☀️ Midday Update: Live market pulse & breaking news across your strategic holdings")
elif 17 <= hour < 21:
    preview_options.append(f"🌆 Evening Wrap: Today's performance & after-hours developments in your investments")

# Rotate based on day of year for consistency with variety
index = now.timetuple().tm_yday % len(preview_options)
return preview_options[index]
```

# ––––– Main renderer with hybrid color scheme –––––

def render_email(summary, companies, cryptos=None):
“”“Email rendering with hybrid color scheme that works in both dark and light modes.”””

```
# Entity processing
company_cards = []
crypto_cards = []

# Process companies
for c in companies or []:
    ticker = str(c.get("ticker") or c.get("symbol") or "")
    is_crypto = ticker.endswith("-USD") or (str(c.get("asset_class") or "").lower() == "crypto")
    
    if is_crypto:
        crypto_cards.append(_build_card(c))
    else:
        company_cards.append(_build_card(c))

# Process explicit crypto list
if cryptos:
    for cx in cryptos:
        crypto_cards.append(_build_card(cx))

# Header metadata
summary = summary or {}
as_of = _fmt_ct(summary.get("as_of_ct"), force_time=True, tz_suffix_policy="always")

# Data quality indicators
data_quality = summary.get("data_quality", {})
total_entities = data_quality.get("total_entities", len((companies or [])) + len((cryptos or [])))
successful_entities = data_quality.get("successful_entities", total_entities)

# Market summary stats
up_count = summary.get("up_count", 0)
down_count = summary.get("down_count", 0)

market_summary = ""
if up_count or down_count:
    total = up_count + down_count
    up_pct = (up_count / total * 100) if total > 0 else 0
    
    if up_pct >= 70:
        market_emoji = "🟢"
        market_sentiment = "Strong"
    elif up_pct >= 60:
        market_emoji = "🟡"
        market_sentiment = "Positive"
    elif up_pct >= 40:
        market_emoji = "⚪"
        market_sentiment = "Mixed"
    else:
        market_emoji = "🔴"
        market_sentiment = "Weak"
    
    market_summary = f'''
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse;background:#F3F4F6;
                  border-radius:12px;margin:14px 0;
                  box-shadow:0 2px 6px rgba(0,0,0,0.05);">
      <tr><td style="padding:16px 20px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="font-size:18px;">{market_emoji}</td>
            <td style="color:#111827;font-weight:700;padding-left:10px;font-size:16px;">{market_sentiment} Session</td>
            <td style="color:#6B7280;font-size:14px;text-align:right;font-weight:500;">
              {up_count} up • {down_count} down
            </td>
          </tr>
        </table>
      </td></tr>
    </table>'''

# Hero selection and rendering
hero_obj = _select_hero(summary, companies or [], cryptos or [])
hero_html = _render_hero(hero_obj) if hero_obj else ""

# Sections with conditional rendering
sections = []

if company_cards:
    sections.append(_section_container("Stocks & ETFs", _grid(company_cards)))

if crypto_cards:
    sections.append(_section_container("Digital Assets", _grid(crypto_cards)))

# Data quality footer
quality_note = ""
if total_entities > successful_entities:
    failed_count = total_entities - successful_entities
    quality_note = f'''
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse;margin-top:14px;padding:12px 16px;
                  background:#FEF2F2;border-radius:10px;
                  box-shadow:0 1px 3px rgba(0,0,0,0.05);">
      <tr><td style="color:#DC2626;font-size:13px;font-weight:600;">
        ⚠️ {failed_count} of {total_entities} assets had data issues
      </td></tr>
    </table>'''

# Email preview
email_preview = _generate_enhanced_preview()

# Minimal CSS for mobile responsiveness only
css = """
```

<style>
/* Mobile responsiveness */
@media only screen and (max-width: 640px) {
  .stack-col { 
    display: block !important; 
    width: 100% !important; 
    max-width: 100% !important; 
    padding-left: 0 !important; 
    padding-right: 0 !important;
    padding-bottom: 12px !important;
  }
  
  .responsive-title {
    font-size: 36px !important;
  }
  
  .section-title {
    font-size: 24px !important;
  }
}

@media only screen and (max-width: 480px) {
  .responsive-title {
    font-size: 32px !important;
  }
  
  .section-title {
    font-size: 20px !important;
  }
}
</style>

“””

```
# HTML structure with inline hybrid colors
html = f"""<!DOCTYPE html>
```

<html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="light">
    <meta name="supported-color-schemes" content="light">
    <meta name="description" content="{escape(email_preview)}">
    <meta name="format-detection" content="telephone=no, date=no, address=no, email=no">
    <title>Intelligence Digest</title>
    {css}
  </head>
  <body style="margin:0;padding:0;background:#F7F8FA;color:#111827;
               font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;">

```
<!-- Hidden preview text -->
<div style="display:none;font-size:1px;color:#F7F8FA;line-height:1px;
           max-height:0px;max-width:0px;opacity:0;overflow:hidden;mso-hide:all;">
  {escape(email_preview)}
</div>

<!-- Main container -->
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
  <tr>
    <td align="center" style="padding:20px 12px;background:#F7F8FA;">
      <table role="presentation" width="640" cellpadding="0" cellspacing="0" 
             style="border-collapse:collapse;width:640px;max-width:100%;">
        <tr>
          <td style="background:#FFFFFF;
                     border-radius:16px;
                     padding:32px;box-shadow:0 4px 12px rgba(0,0,0,0.08);">
            
            <!-- Header -->
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr><td style="text-align:center;">
                <div class="responsive-title" style="font-weight:700;font-size:42px;color:#111827;
                                                    margin:0 0 10px 0;letter-spacing:-0.5px;
                                                    font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">
                  Intelligence Digest
                </div>
                {f'<div style="color:#6B7280;margin-bottom:16px;font-size:14px;font-weight:500;">📊 Data as of {escape(as_of)}</div>' if as_of else ''}
                {market_summary}
                {quality_note}
              </td></tr>
            </table>

            <!-- Hero section -->
            {hero_html}

            <!-- Content sections -->
            {''.join(sections)}

            <!-- Footer -->
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                   style="border-top:1px solid #E5E7EB;margin-top:28px;">
              <tr><td style="text-align:center;padding:24px 16px;color:#6B7280;font-size:13px;">
                <div style="margin-bottom:8px;font-weight:500;">
                  You're receiving this because you subscribed to Intelligence Digest
                </div>
                <div style="color:#9CA3AF;font-weight:400;">
                  Engineered with precision • Delivered with speed ⚡
                </div>
              </td></tr>
            </table>

          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
```

  </body>
</html>"""

```
return html
```