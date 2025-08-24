# src/render_email.py
# Enhanced UI-focused renderer for the Intelligence Digest email.
# Improvements: Better spacing, enhanced mobile responsiveness, improved preview text extraction,
# better dark mode consistency, enhanced visual hierarchy

from datetime import datetime, timezone
from html import escape
from email.utils import parsedate_to_datetime
import re

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

CENTRAL_TZ = ZoneInfo("America/Chicago") if ZoneInfo else None


# ---------- Enhanced time helpers ----------

def _parse_to_dt(value):
    """Enhanced datetime parsing with better error handling."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip()
    if not s:
        return None
    
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
    iso_patterns = [
        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z',
        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.\d+Z',
        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2})',
    ]
    
    for pattern in iso_patterns:
        match = re.search(pattern, s)
        if match:
            try:
                dt_str = match.group(1)
                if s.endswith('Z'):
                    dt_str += '+00:00'
                dt = datetime.fromisoformat(dt_str)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    
    # Standard ISO format
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


def _fmt_ct(value, force_time=None, tz_suffix_policy="auto"):
    """Enhanced Central Time formatting with better error handling."""
    dt = _parse_to_dt(value) or value
    if not isinstance(dt, datetime):
        return str(value)
    
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
    if tz_suffix_policy == "never":
        return out
    return out


# ---------- Enhanced visual helpers ----------

def _safe_float(x, default=None):
    """Enhanced float conversion with better validation."""
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
    """Enhanced performance chip with better styling and accessibility."""
    v = _safe_float(value, None)
    
    if v is None:
        bg = "#2a2a2a"
        color = "#9aa0a6" 
        sign = ""
        txt = "--"
        border = "1px solid #404040"
    else:
        if v >= 0:
            bg = "#065f46"  # Darker green for better contrast
            color = "#10b981"  # Bright green text
            sign = "▲"
        else:
            bg = "#7f1d1d"  # Darker red for better contrast  
            color = "#ef4444"  # Bright red text
            sign = "▼"
        txt = f"{abs(v):.1f}%"
        border = f"1px solid {color}40"  # Semi-transparent border
    
    safe_label = escape(label)
    
    return (f'<span style="background:{bg};color:{color};border:{border};'
            f'padding:4px 10px;border-radius:6px;font-size:12px;font-weight:600;'
            f'margin-right:8px;margin-bottom:4px;display:inline-block;'
            f'box-shadow:0 1px 3px rgba(0,0,0,0.2);white-space:nowrap;"'
            f'aria-label="{safe_label} {txt}">'
            f'{safe_label} {sign} {txt}</span>')


def _button(label: str, url: str, style="primary"):
    """Enhanced button with multiple styles and better accessibility."""
    safe_label = escape(label)
    href = escape(url or "#")
    
    if style == "primary":
        bg = "#1f2937"
        color = "#ffffff"
        border = "1px solid #374151"
        hover_bg = "#374151"
    else:  # secondary
        bg = "transparent"
        color = "#9aa0a6"
        border = "1px solid #374151"
        hover_bg = "#1f2937"
    
    return (f'<a href="{href}" target="_blank" rel="noopener noreferrer" '
            f'style="background:{bg};color:{color};text-decoration:none;'
            f'border:{border};border-radius:6px;font-size:12px;font-weight:500;'
            f'line-height:1.2;white-space:nowrap;padding:8px 12px;display:inline-block;'
            f'margin:2px 6px 2px 0;transition:all 0.2s;text-align:center;'
            f'min-width:60px;" '
            f'onmouseover="this.style.background=\'{hover_bg}\'" '
            f'onmouseout="this.style.background=\'{bg}\'" '
            f'aria-label="View {safe_label} for this asset">'
            f'{safe_label} →</a>')


def _range_bar(pos: float, low: float, high: float):
    """Enhanced 52-week range bar with better visual design."""
    pct = max(0.0, min(100.0, _safe_float(pos, 0.0)))
    left = f"{pct:.1f}%"
    right = f"{100 - pct:.1f}%"
    
    low_v = _safe_float(low, 0.0) or 0.0
    high_v = _safe_float(high, 0.0) or 0.0
    current_v = _safe_float(pos, 0.0) or 0.0
    
    # Determine marker color based on position
    if pct < 25:
        marker_color = "#ef4444"  # Red for low range
    elif pct > 75:  
        marker_color = "#10b981"  # Green for high range
    else:
        marker_color = "#3b82f6"  # Blue for mid range
    
    track_bg = "#1f2937"  # Darker background
    track_border = "1px solid #374151"
    
    track = (
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        f'style="border-collapse:collapse;border:{track_border};border-radius:3px;'
        f'background:{track_bg};height:8px;overflow:hidden;"><tr>'
        f'<td width="{left}" style="width:{left};background:{track_bg};height:8px;padding:0;">&nbsp;</td>'
        f'<td width="8px" style="width:8px;background:{marker_color};height:8px;padding:0;">&nbsp;</td>'
        f'<td width="{right}" style="width:{right};background:{track_bg};height:8px;padding:0;">&nbsp;</td>'
        f'</tr></table>'
    )
    
    caption = (f'<div style="font-size:11px;color:#9aa0a6;margin-top:5px;'
               f'display:flex;justify-content:space-between;align-items:center;">'
               f'<span>Low ${low_v:.2f}</span>'
               f'<span style="color:{marker_color};font-weight:600;">${current_v:.2f}</span>'
               f'<span>High ${high_v:.2f}</span></div>')
    
    return (f'<div style="margin:12px 0 8px 0;">'
            f'<div style="font-size:11px;color:#9aa0a6;margin-bottom:6px;font-weight:500;">52-week range</div>'
            + track + caption + '</div>')


def _belongs_to_company(c: dict, headline: str) -> bool:
    """Enhanced company-headline matching with better tokenization."""
    if not c or not headline:
        return False
    
    name = str(c.get("name") or "").lower()
    ticker = str(c.get("ticker") or c.get("symbol") or "").lower()
    
    # Enhanced tokenization
    base_tokens = set()
    if name:
        # Split on various separators and filter short words
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
    
    # Fuzzy matching for abbreviated names
    if ticker and len(ticker) >= 3:
        # Look for ticker in parentheses or after colon
        if re.search(rf'[(\s:]{re.escape(ticker)}[\s)\.,]', h_lower):
            return True
    
    return False


# ---------- Enhanced hero content parsing ----------

def _strip_tags(html: str) -> str:
    """Enhanced HTML tag stripping with better whitespace handling."""
    if not html:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove common HTML entities
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    
    return text.strip()


def _first_paragraph(hero: dict, title: str = "") -> str:
    """
    Enhanced paragraph extraction with better content prioritization.
    """
    if not hero:
        return ""
    
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


def _select_hero(summary: dict, companies: list, cryptos: list):
    """Enhanced hero selection with better scoring."""
    # Check for explicit hero in summary
    hero = None
    if isinstance(summary, dict):
        hero_candidates = [
            summary.get("hero"),
            summary.get("market_hero"),
            summary.get("market"),
            summary.get("lead_story")
        ]
        
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
        
        # Boost for reputable sources
        source = entity.get("source", "")
        if source:
            reputable_sources = ["Reuters", "Bloomberg", "Wall Street Journal", "Financial Times", 
                               "MarketWatch", "CNBC", "Associated Press"]
            if any(rep in source for rep in reputable_sources):
                score += 10
        
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


def _render_hero(hero: dict) -> str:
    """Enhanced hero rendering with better visual hierarchy."""
    if not hero:
        return ""
    
    title = (hero.get("title") or "").strip()
    if not title:
        return ""
    
    url = hero.get("url") or "#"
    source = hero.get("source") or ""
    when = _fmt_ct(hero.get("when"), force_time=False, tz_suffix_policy="never") if hero.get("when") else ""
    
    # Enhanced paragraph extraction
    para = _first_paragraph(hero, title=title)
    
    # Truncate paragraph if too long
    if para and len(para) > 300:
        # Find a good breaking point
        sentences = re.split(r'[.!?]\s+', para)
        truncated = ""
        for sentence in sentences:
            if len(truncated + sentence) <= 250:
                truncated += sentence + ". "
            else:
                break
        para = truncated.strip()
    
    # Enhanced body HTML with better typography
    body_html = ""
    if para:
        body_html = f'''
        <div style="margin-top:12px;font-size:14px;line-height:1.6;
                   color:#d1d5db;max-height:120px;overflow:hidden;
                   text-overflow:ellipsis;font-weight:400;">
            {escape(para)}
        </div>'''
    
    # Enhanced metadata line
    meta_parts = []
    if source:
        meta_parts.append(f'<span style="font-weight:500;color:#9ca3af;">{escape(source)}</span>')
    if when:
        meta_parts.append(f'<span style="color:#6b7280;">{escape(when)}</span>')
    
    meta_html = ""
    if meta_parts:
        meta_html = f'''
        <div style="margin-top:12px;font-size:12px;border-top:1px solid #374151;
                   padding-top:8px;display:flex;gap:12px;flex-wrap:wrap;">
            {" • ".join(meta_parts)}
        </div>'''
    
    # Enhanced hero container with better visual design
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;background:linear-gradient(135deg, #1f2937 0%, #111827 100%);
              border:1px solid #374151;border-radius:12px;margin:16px 0;
              box-shadow:0 4px 12px rgba(0,0,0,0.3);overflow:hidden;">
  <tr>
    <td style="padding:20px 24px;">
      <div style="font-weight:700;font-size:24px;line-height:1.3;color:#ffffff;
                 margin-bottom:4px;">
        <a href="{escape(url)}" style="color:inherit;text-decoration:none;
           border-bottom:2px solid transparent;transition:border-color 0.2s;"
           onmouseover="this.style.borderBottomColor='#3b82f6'"
           onmouseout="this.style.borderBottomColor='transparent'">
          {escape(title)}
        </a>
      </div>
      {body_html}
      {meta_html}
    </td>
  </tr>
</table>
"""


# ---------- Enhanced card and grid system ----------

def _build_card(c):
    """Enhanced card building with better visual design and data validation."""
    name = c.get("name") or c.get("ticker") or c.get("symbol") or "Unknown"
    ticker = str(c.get("ticker") or c.get("symbol") or "")
    is_crypto = ticker.endswith("-USD") or (str(c.get("asset_class") or "").lower() == "crypto")

    # Enhanced price formatting
    price_v = _safe_float(c.get("price"), None)
    if price_v is None:
        price_fmt = '<span style="color:#6b7280;">--</span>'
    else:
        if is_crypto:
            if price_v >= 1000:
                price_fmt = f'<span style="color:#ffffff;font-weight:600;">${price_v:,.0f}</span>'
            elif price_v >= 1:
                price_fmt = f'<span style="color:#ffffff;font-weight:600;">${price_v:,.2f}</span>'
            else:
                price_fmt = f'<span style="color:#ffffff;font-weight:600;">${price_v:.4f}</span>'
        else:
            price_fmt = f'<span style="color:#ffffff;font-weight:600;">${price_v:,.2f}</span>'

    # Enhanced chip layout with better spacing
    chips_line1 = _chip("1D", c.get("pct_1d")) + _chip("1W", c.get("pct_1w"))
    chips_line2 = _chip("1M", c.get("pct_1m")) + _chip("YTD", c.get("pct_ytd"))
    
    chips = f'''
    <div style="line-height:1.4;margin:10px 0;">
        <div style="margin-bottom:6px;">{chips_line1}</div>
        <div>{chips_line2}</div>
    </div>'''

    # Enhanced news bullet with better formatting
    bullets = []
    headline = c.get("headline")
    source = c.get("source")
    when_fmt = _fmt_ct(c.get("when"), force_time=False, tz_suffix_policy="never") if c.get("when") else None

    if headline and _belongs_to_company(c, headline):
        # Truncate long headlines
        display_headline = headline[:120] + "..." if len(headline) > 120 else headline
        
        if source and when_fmt:
            bullets.append(f"★ {display_headline} <span style='color:#6b7280;'>({source}, {when_fmt})</span>")
        elif source:
            bullets.append(f"★ {display_headline} <span style='color:#6b7280;'>({source})</span>")
        elif when_fmt:
            bullets.append(f"★ {display_headline} <span style='color:#6b7280;'>({when_fmt})</span>")
        else:
            bullets.append(f"★ {display_headline}")
    else:
        company_name = name.replace(" Inc.", "").replace(" Corporation", "").strip()
        bullets.append(f'★ <span style="color:#9ca3af;">Latest {company_name} coverage — see News</span>')

    # Additional context bullets
    next_event = c.get("next_event")
    if next_event:
        event_date = _fmt_ct(next_event, force_time=False, tz_suffix_policy="never")
        if event_date:
            bullets.append(f'<span style="color:#9ca3af;">📅 Next: {event_date}</span>')

    vol_multiplier = _safe_float(c.get("vol_x_avg"), None)
    if vol_multiplier is not None and vol_multiplier > 1.5:  # Only show significant volume
        bullets.append(f'<span style="color:#f59e0b;">📊 Volume: {vol_multiplier:.1f}× avg</span>')

    # Enhanced bullets HTML
    bullets_html = ""
    for i, bullet in enumerate(bullets):
        if i == 0:  # Main news item
            bullets_html += f'''
            <li style="list-style-type:none;margin:0 0 8px 0;padding:0;
                      display:-webkit-box;-webkit-box-orient:vertical;
                      -webkit-line-clamp:3;overflow:hidden;text-overflow:ellipsis;
                      line-height:1.4;max-height:calc(1.4em * 3);color:#e5e7eb;">
                {bullet}
            </li>'''
        else:  # Secondary items
            bullets_html += f'''
            <li style="list-style-type:none;margin:0 0 4px 0;padding:0;
                      font-size:12px;line-height:1.3;color:#9ca3af;">
                {bullet}
            </li>'''

    # Enhanced range bar
    range_html = _range_bar(
        _safe_float(c.get("range_pct"), 50.0),
        _safe_float(c.get("low_52w"), 0.0),
        _safe_float(c.get("high_52w"), 0.0)
    )

    # Enhanced action buttons
    news_url = c.get("news_url") or f"https://finance.yahoo.com/quote/{escape(ticker)}/news"
    pr_url = c.get("pr_url") or f"https://finance.yahoo.com/quote/{escape(ticker)}/press-releases"
    
    ctas = f'''
    <div style="margin-top:12px;border-top:1px solid #374151;padding-top:10px;">
        {_button("News", news_url, "primary")}
        {_button("Press", pr_url, "secondary")}
    </div>'''

    # Enhanced card with better visual hierarchy
    return f"""
<div style="background:linear-gradient(135deg, #1f2937 0%, #111827 100%);
           border:1px solid #374151;border-radius:10px;
           margin:0 0 12px;box-shadow:0 2px 8px rgba(0,0,0,0.3);
           overflow:hidden;transition:transform 0.2s;">
  <div style="padding:16px 18px;max-height:320px;overflow:hidden;">
    <!-- Header -->
    <div style="margin-bottom:8px;">
      <div style="font-weight:700;font-size:16px;line-height:1.3;color:#ffffff;
                 margin-bottom:2px;">
        {escape(str(name))}
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:12px;color:#9ca3af;font-weight:500;">({escape(ticker)})</span>
        <div style="font-size:14px;">{price_fmt}</div>
      </div>
    </div>
    
    <!-- Performance chips -->
    {chips}
    
    <!-- 52-week range -->
    {range_html}
    
    <!-- News and events -->
    <ul style="margin:12px 0 0 0;padding:0;list-style:none;">
      {bullets_html}
    </ul>
    
    <!-- Action buttons -->
    {ctas}
  </div>
</div>
"""


def _grid(cards):
    """Enhanced responsive grid with better mobile handling."""
    if not cards:
        return ""
    
    rows = []
    for i in range(0, len(cards), 2):
        left = cards[i]
        right = cards[i + 1] if i + 1 < len(cards) else ""
        
        if right:
            row = f'''
<div class="grid-row" style="display:flex;gap:12px;margin-bottom:6px;">
    <div class="grid-col" style="flex:1;min-width:0;">{left}</div>
    <div class="grid-col" style="flex:1;min-width:0;">{right}</div>
</div>'''
        else:
            row = f'''
<div class="grid-row" style="display:flex;margin-bottom:6px;">
    <div class="grid-col" style="flex:1;max-width:50%;">{left}</div>
</div>'''
        
        rows.append(row)
    
    return "".join(rows)


def _section_container(title: str, inner_html: str):
    """Enhanced section container with better visual design."""
    safe_title = escape(title)
    return f"""
<div style="background:#0f172a;border:1px solid #374151;
           border-radius:12px;margin:20px 0;
           box-shadow:0 4px 12px rgba(0,0,0,0.2);overflow:hidden;">
  <div style="padding:20px 24px;">
    <h2 style="font-weight:700;font-size:28px;color:#ffffff;
              margin:0 0 16px 0;border-bottom:2px solid #374151;
              padding-bottom:8px;">{safe_title}</h2>
    {inner_html}
  </div>
</div>
"""


def _generate_enhanced_preview() -> str:
    """Generate compelling preview text optimized for inbox engagement."""
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    day_name = now.strftime("%A")
    
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


# ---------- Enhanced main renderer ----------

def render_email(summary, companies, cryptos=None):
    """Enhanced email rendering with better organization and visual design."""
    
    # Enhanced entity processing
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

    # Enhanced header metadata
    summary = summary or {}
    as_of = _fmt_ct(summary.get("as_of_ct"), force_time=True, tz_suffix_policy="always")
    
    # Enhanced data quality indicators
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
        <div style="background:#1f2937;border:1px solid #374151;border-radius:8px;
                   padding:12px 16px;margin:12px 0;display:flex;
                   justify-content:space-between;align-items:center;">
            <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-size:16px;">{market_emoji}</span>
                <span style="color:#e5e7eb;font-weight:600;">{market_sentiment} Session</span>
            </div>
            <div style="color:#9ca3af;font-size:13px;">
                {up_count} up • {down_count} down
            </div>
        </div>'''

    # Enhanced hero selection and rendering
    hero_obj = _select_hero(summary, companies or [], cryptos or [])
    hero_html = _render_hero(hero_obj) if hero_obj else ""

    # Enhanced sections with conditional rendering
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
        <div style="margin-top:8px;padding:8px 12px;background:#7f1d1d20;
                   border:1px solid #7f1d1d;border-radius:6px;">
            <div style="color:#f87171;font-size:12px;">
                ⚠️ {failed_count} of {total_entities} assets had data issues
            </div>
        </div>'''

    # Enhanced email preview
    email_preview = _generate_enhanced_preview()

    # Enhanced responsive CSS
    css = """
<style>
@media only screen and (max-width: 640px) {
  .grid-row { flex-direction:column !important; gap:8px !important; }
  .grid-col { flex:none !important; max-width:100% !important; }
  h2 { font-size:24px !important; }
  .hero-title { font-size:20px !important; }
}
@media only screen and (max-width: 480px) {
  .container { padding:12px !important; }
  .section-padding { padding:16px !important; }
  .card-padding { padding:14px !important; }
}
/* Dark mode enforcement */
@media (prefers-color-scheme: dark) {
  .email-body { background:#0b0c10 !important; color:#e5e7eb !important; }
}
</style>
"""

    # Enhanced HTML structure
    html = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="dark">
    <meta name="supported-color-schemes" content="dark">
    <meta name="description" content="{escape(email_preview)}">
    <meta name="format-detection" content="telephone=no, date=no, address=no, email=no">
    <title>Intelligence Digest</title>
    {css}
  </head>
  <body class="email-body" style="margin:0;padding:0;background:#0b0c10;color:#e5e7eb;
                                   font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    
    <!-- Hidden preview text -->
    <div style="display:none;font-size:1px;color:#0b0c10;line-height:1px;
               max-height:0px;max-width:0px;opacity:0;overflow:hidden;mso-hide:all;">
      {escape(email_preview)}
    </div>
    
    <!-- Main container -->
    <div style="width:100%;background:#0b0c10;padding:20px 0;">
      <div class="container" style="max-width:640px;margin:0 auto;padding:0 16px;">
        
        <!-- Header -->
        <div style="background:linear-gradient(135deg, #1f2937 0%, #111827 100%);
                   border:1px solid #374151;border-radius:12px;
                   padding:24px;margin-bottom:16px;text-align:center;
                   box-shadow:0 4px 12px rgba(0,0,0,0.3);">
          <h1 style="font-weight:700;font-size:42px;color:#ffffff;margin:0 0 8px 0;
                    letter-spacing:-0.5px;">Intelligence Digest</h1>
          {f'<div style="color:#9ca3af;margin-bottom:12px;font-size:13px;">📊 Data as of {escape(as_of)}</div>' if as_of else ''}
          {market_summary}
          {quality_note}
        </div>

        <!-- Hero section -->
        {hero_html}

        <!-- Content sections -->
        {''.join(sections)}

        <!-- Footer -->
        <div style="text-align:center;padding:20px 16px;color:#6b7280;font-size:12px;
                   border-top:1px solid #374151;margin-top:24px;">
          <div style="margin-bottom:8px;">
            You're receiving this because you subscribed to Intelligence Digest
          </div>
          <div style="color:#4b5563;">
            Engineered with precision • Delivered with speed ⚡
          </div>
        </div>

      </div>
    </div>
  </body>
</html>"""

    return html
