# src/render_email.py
# Enhanced visual design with PROPER dark mode handling - keeping original design but fixing color inversion
# FIXED: Dark mode uses light backgrounds that invert to dark, Mobile layout identical to desktop

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
    """Enhanced performance chip with proper dark mode color handling."""
    v = _safe_float(value, None)
    
    if v is None:
        # Neutral chip - works in both modes
        bg = "#4B5563"  
        color = "#FFFFFF"
        sign = ""
        txt = "--"
    else:
        if v >= 0:
            # Green chip
            bg = "#059669"   
            color = "#FFFFFF" 
            sign = "▲"
        else:
            # Red chip
            bg = "#DC2626"   
            color = "#FFFFFF"
            sign = "▼"
        txt = f"{abs(v):.1f}%"
    
    safe_label = escape(label)
    
    return (f'<span class="perf-chip" style="background:{bg};color:{color};'
            f'padding:5px 12px;border-radius:12px;font-size:12px;font-weight:700;'
            f'margin:2px 6px 4px 0;display:inline-block;'
            f'box-shadow:0 2px 6px rgba(0,0,0,0.3);white-space:nowrap;'
            f'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;"'
            f'>{safe_label} {sign} {txt}</span>')


def _button(label: str, url: str, style="primary"):
    """Enhanced button with proper dark mode handling."""
    safe_label = escape(label)
    href = escape(url or "#")
    
    if style == "primary":
        bg = "#374151"
        color = "#FFFFFF"
    else:  # secondary
        bg = "#6B7280"
        color = "#FFFFFF"
    
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" style="display:inline-block;margin-right:8px;margin-bottom:4px;">'
            f'<tr><td class="btn-cell" style="background:{bg};color:{color};'
            f'border-radius:10px;font-size:13px;font-weight:600;padding:10px 16px;'
            f'box-shadow:0 3px 8px rgba(0,0,0,0.2);'
            f'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">'
            f'<a href="{href}" target="_blank" rel="noopener noreferrer" '
            f'style="color:{color};text-decoration:none;display:block;">'
            f'{safe_label} →</a></td></tr></table>')


def _range_bar(pos: float, low: float, high: float):
    """Enhanced 52-week range bar with mobile optimization."""
    pct = max(0.0, min(100.0, _safe_float(pos, 0.0)))
    left = f"{pct:.1f}%"
    right = f"{100 - pct:.1f}%"
    
    low_v = _safe_float(low, 0.0) or 0.0
    high_v = _safe_float(high, 0.0) or 0.0
    current_v = _safe_float(pos, 0.0) or 0.0
    
    # Color based on position
    if pct < 25:
        marker_color = "#DC2626"  # Red
        marker_label = "Low"
    elif pct > 75:  
        marker_color = "#059669"  # Green
        marker_label = "High"
    else:
        marker_color = "#2563EB"  # Blue
        marker_label = "Mid"
    
    track_bg = "#374151"
    
    # Mobile-friendly track
    track = (
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        f'style="border-collapse:collapse;border-radius:8px;'
        f'background:{track_bg};height:10px;overflow:hidden;'
        f'min-width:200px;box-shadow:inset 0 1px 2px rgba(0,0,0,0.2);">'
        f'<tr>'
        f'<td style="width:{left};background:{track_bg};height:10px;padding:0;">&nbsp;</td>'
        f'<td style="width:10px;background:{marker_color};height:10px;padding:0;">&nbsp;</td>'
        f'<td style="width:{right};background:{track_bg};height:10px;padding:0;">&nbsp;</td>'
        f'</tr></table>'
    )
    
    # Mobile-friendly caption
    caption = (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:6px;">'
               f'<tr>'
               f'<td class="range-text" style="font-size:11px;color:#9CA3AF;text-align:left;font-weight:500;">Low ${low_v:.2f}</td>'
               f'<td class="range-text" style="font-size:12px;color:{marker_color};font-weight:700;text-align:center;">'
               f'${current_v:.2f}</td>'
               f'<td class="range-text" style="font-size:11px;color:#9CA3AF;text-align:right;font-weight:500;">High ${high_v:.2f}</td>'
               f'</tr></table>')
    
    return (f'<div style="margin:14px 0 10px 0;">'
            f'<div class="range-title" style="font-size:12px;color:#D1D5DB;margin-bottom:6px;font-weight:600;">'
            f'52-Week Range</div>'
            + track + caption + '</div>')


def _belongs_to_company(c: dict, headline: str) -> bool:
    """Enhanced company-headline matching with better tokenization."""
    if not c or not headline:
        return False
    
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
    """Enhanced paragraph extraction with better content prioritization."""
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
    
    # Enhanced body HTML with better typography
    body_html = ""
    if para:
        body_html = f'''
        <tr><td class="hero-body" style="padding-top:14px;font-size:15px;line-height:1.6;
                     color:#D1D5DB;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">
            {escape(para)}
        </td></tr>'''
    
    # Enhanced metadata line
    meta_parts = []
    if source:
        meta_parts.append(f'<span style="font-weight:600;color:#A78BFA;">{escape(source)}</span>')
    if when:
        meta_parts.append(f'<span style="color:#9CA3AF;">{escape(when)}</span>')
    
    meta_html = ""
    if meta_parts:
        meta_html = f'''
        <tr><td class="hero-meta" style="padding-top:14px;font-size:13px;
                     border-top:1px solid rgba(255,255,255,0.1);
                     padding-top:12px;color:#9CA3AF;">
            {" • ".join(meta_parts)}
        </td></tr>'''
    
    # Enhanced hero container with gradient
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       class="hero-container" style="border-collapse:collapse;
              background:linear-gradient(135deg, #1F2937 0%, #111827 100%);
              border-radius:16px;margin:20px 0;
              box-shadow:0 8px 20px rgba(0,0,0,0.5);color:#FFFFFF;">
  <tr>
    <td style="padding:28px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr><td class="hero-title" style="font-weight:700;font-size:26px;line-height:1.3;color:#FFFFFF;
                     font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">
          <a href="{escape(url)}" style="color:#FFFFFF;text-decoration:none;">
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


# ---------- Enhanced card system ----------

def _build_card(c):
    """Enhanced card building with better visual design."""
    name = c.get("name") or c.get("ticker") or c.get("symbol") or "Unknown"
    ticker = str(c.get("ticker") or c.get("symbol") or "")
    is_crypto = ticker.endswith("-USD") or (str(c.get("asset_class") or "").lower() == "crypto")

    # Enhanced price formatting
    price_v = _safe_float(c.get("price"), None)
    if price_v is None:
        price_fmt = '<span class="price-text" style="color:#9CA3AF;">--</span>'
    else:
        if is_crypto:
            if price_v >= 1000:
                price_fmt = f'<span class="price-text" style="color:#FFFFFF;font-weight:700;">${price_v:,.0f}</span>'
            elif price_v >= 1:
                price_fmt = f'<span class="price-text" style="color:#FFFFFF;font-weight:700;">${price_v:,.2f}</span>'
            else:
                price_fmt = f'<span class="price-text" style="color:#FFFFFF;font-weight:700;">${price_v:.4f}</span>'
        else:
            price_fmt = f'<span class="price-text" style="color:#FFFFFF;font-weight:700;">${price_v:,.2f}</span>'

    # Enhanced chip layout - SAME AS DESKTOP ON MOBILE
    chips_line1 = _chip("1D", c.get("pct_1d")) + _chip("1W", c.get("pct_1w"))
    chips_line2 = _chip("1M", c.get("pct_1m")) + _chip("YTD", c.get("pct_ytd"))
    
    chips = f'''
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:12px 0;">
        <tr><td style="line-height:1.6;padding-bottom:6px;">{chips_line1}</td></tr>
        <tr><td style="line-height:1.6;">{chips_line2}</td></tr>
    </table>'''

    # Enhanced news bullet with better formatting
    bullets = []
    headline = c.get("headline")
    source = c.get("source")
    when_fmt = _fmt_ct(c.get("when"), force_time=False, tz_suffix_policy="never") if c.get("when") else None

    if headline and _belongs_to_company(c, headline):
        # Truncate long headlines
        display_headline = headline[:100] + "..." if len(headline) > 100 else headline
        
        if source and when_fmt:
            bullets.append(f"★ {display_headline} <span style='color:#9CA3AF;'>({source}, {when_fmt})</span>")
        elif source:
            bullets.append(f"★ {display_headline} <span style='color:#9CA3AF;'>({source})</span>")
        elif when_fmt:
            bullets.append(f"★ {display_headline} <span style='color:#9CA3AF;'>({when_fmt})</span>")
        else:
            bullets.append(f"★ {display_headline}")
    else:
        company_name = name.replace(" Inc.", "").replace(" Corporation", "").strip()
        bullets.append(f'★ <span style="color:#9CA3AF;">Latest {company_name} coverage — see News</span>')

    # Additional context bullets
    next_event = c.get("next_event")
    if next_event:
        event_date = _fmt_ct(next_event, force_time=False, tz_suffix_policy="never")
        if event_date:
            bullets.append(f'<span style="color:#A78BFA;">📅 Next: {event_date}</span>')

    vol_multiplier = _safe_float(c.get("vol_x_avg"), None)
    if vol_multiplier is not None and vol_multiplier > 1.5:  # Only show significant volume
        bullets.append(f'<span style="color:#F59E0B;">📊 Volume: {vol_multiplier:.1f}× avg</span>')

    # Enhanced bullets HTML in table format
    bullets_html = ""
    for i, bullet in enumerate(bullets):
        if i == 0:  # Main news item
            bullets_html += f'''
            <tr><td class="bullet-text" style="padding-bottom:10px;
                          display:-webkit-box;-webkit-box-orient:vertical;
                          -webkit-line-clamp:3;overflow:hidden;text-overflow:ellipsis;
                          line-height:1.5;color:#E5E7EB;font-size:14px;font-weight:500;">
                {bullet}
            </td></tr>'''
        else:  # Secondary items
            bullets_html += f'''
            <tr><td class="bullet-text" style="padding-bottom:6px;font-size:12px;line-height:1.4;color:#9CA3AF;">
                {bullet}
            </td></tr>'''

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
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="border-top:1px solid rgba(255,255,255,0.1);padding-top:14px;">
            {_button("News", news_url, "primary")}
            {_button("Press", pr_url, "secondary")}
        </td></tr>
    </table>'''

    # Enhanced card - SAME DESIGN, PROPER DARK MODE HANDLING
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       class="card-container" style="border-collapse:collapse;margin:0 0 12px;
              background:linear-gradient(135deg, #1F2937 0%, #111827 100%);
              border-radius:14px;
              box-shadow:0 6px 16px rgba(0,0,0,0.4);overflow:hidden;">
  <tr>
    <td class="ci-card-inner" style="padding:20px 22px;max-height:360px;overflow:hidden;vertical-align:top;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <!-- Header -->
        <tr><td>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
            <tr><td class="card-title" style="font-weight:700;font-size:17px;line-height:1.3;color:#FFFFFF;
                         font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;
                         padding-bottom:4px;">{escape(str(name))}</td></tr>
            <tr><td>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td class="ticker-text" style="font-size:13px;color:#D1D5DB;font-weight:600;">({escape(ticker)})</td>
                  <td style="text-align:right;font-size:16px;">{price_fmt}</td>
                </tr>
              </table>
            </td></tr>
          </table>
        </td></tr>
        
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
  </tr>
</table>
"""


def _grid(cards):
    """ORIGINAL two-column grid that works perfectly - SAME ON MOBILE."""
    if not cards:
        return ""
    
    rows = []
    for i in range(0, len(cards), 2):
        left = cards[i]
        right = cards[i + 1] if i + 1 < len(cards) else ""
        
        if right:
            row = f'''
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
    <td class="stack-col" width="100%" style="vertical-align:top;max-width:50%;">{left}</td>
  </tr>
</table>'''
        
        rows.append(row)
    
    return "".join(rows)


def _section_container(title: str, inner_html: str):
    """Enhanced section container with NO DIVIDER LINE."""
    safe_title = escape(title)
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       class="section-container" style="border-collapse:collapse;background:#0F172A;
              border-radius:16px;margin:24px 0;box-shadow:0 6px 16px rgba(0,0,0,0.4);">
  <tr>
    <td style="padding:28px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr><td class="section-title" style="font-weight:700;font-size:32px;color:#FFFFFF;
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
    """Enhanced email rendering with PROPER dark mode CSS handling."""
    
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
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               class="market-summary" style="border-collapse:collapse;background:#1F2937;
                      border-radius:12px;margin:14px 0;
                      box-shadow:0 4px 10px rgba(0,0,0,0.2);">
          <tr><td style="padding:16px 20px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="font-size:18px;">{market_emoji}</td>
                <td class="market-text" style="color:#F3F4F6;font-weight:700;padding-left:10px;font-size:16px;">{market_sentiment} Session</td>
                <td class="market-text" style="color:#D1D5DB;font-size:14px;text-align:right;font-weight:500;">
                  {up_count} up • {down_count} down
                </td>
              </tr>
            </table>
          </td></tr>
        </table>'''

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
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               class="quality-note" style="border-collapse:collapse;margin-top:14px;padding:12px 16px;
                      background:rgba(185,28,28,0.1);border-radius:10px;
                      box-shadow:0 2px 6px rgba(185,28,28,0.1);">
          <tr><td style="color:#FCA5A5;font-size:13px;font-weight:600;">
            ⚠️ {failed_count} of {total_entities} assets had data issues
          </td></tr>
        </table>'''

    # Enhanced email preview
    email_preview = _generate_enhanced_preview()

    # PROPER dark mode CSS - uses light backgrounds for dark mode so they invert correctly
    css = """
<style>
/* Default (light mode and email clients) */
body { background: #0b0c10; color: #e5e7eb; }
.email-body { background: #0b0c10; color: #e5e7eb; }

/* DARK MODE OVERRIDES - Use LIGHT backgrounds so they invert to dark */
@media (prefers-color-scheme: dark) {
  /* Main backgrounds become light (will invert to dark) */
  .hero-container { background: #E5E7EB !important; }
  .card-container { background: #F3F4F6 !important; }
  .section-container { background: #F9FAFB !important; }
  .market-summary { background: #E5E7EB !important; }
  
  /* Text becomes dark (will invert to light) */
  .hero-title, .card-title, .section-title { color: #1F2937 !important; }
  .hero-body, .hero-meta { color: #4B5563 !important; }
  .price-text, .ticker-text, .bullet-text { color: #1F2937 !important; }
  .range-title, .range-text { color: #4B5563 !important; }
  .market-text { color: #1F2937 !important; }
  
  /* Performance chips - light backgrounds (will invert) */
  .perf-chip { background: #D1D5DB !important; color: #1F2937 !important; }
  
  /* Buttons - light backgrounds (will invert) */
  .btn-cell { background: #9CA3AF !important; color: #1F2937 !important; }
}

/* Mobile responsiveness - IDENTICAL TO DESKTOP LAYOUT */
@media only screen and (max-width: 640px) {
  .stack-col { 
    display: block !important; 
    width: 100% !important; 
    max-width: 100% !important; 
    padding-left: 0 !important; 
    padding-right: 0 !important; 
  }
  .ci-card-inner { 
    max-height: none !important; 
    overflow: visible !important;
  }
  .responsive-title {
    font-size: 36px !important;
  }
}

/* Very small screens */
@media only screen and (max-width: 480px) {
  .responsive-title {
    font-size: 32px !important;
  }
  .ci-card-inner {
    padding: 18px 20px !important;
  }
}
</style>
"""

    # Enhanced HTML structure
    html = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="light dark">
    <meta name="supported-color-schemes" content="light dark">
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
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
      <tr>
        <td align="center" style="padding:20px 12px;background:#0b0c10;">
          <table role="presentation" width="640" cellpadding="0" cellspacing="0" 
                 style="border-collapse:collapse;width:640px;max-width:100%;">
            <tr>
              <td style="background:linear-gradient(135deg, #1F2937 0%, #111827 100%);
                         border-radius:16px;
                         padding:32px;box-shadow:0 8px 20px rgba(0,0,0,0.5);">
                
                <!-- Header -->
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                  <tr><td style="text-align:center;">
                    <div class="responsive-title" style="font-weight:700;font-size:48px;color:#FFFFFF;
                                                        margin:0 0 10px 0;letter-spacing:-0.5px;
                                                        font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">
                      Intelligence Digest
                    </div>
                    {f'<div style="color:#D1D5DB;margin-bottom:16px;font-size:14px;font-weight:500;">📊 Data as of {escape(as_of)}</div>' if as_of else ''}
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
                       style="border-top:1px solid rgba(255,255,255,0.1);margin-top:28px;">
                  <tr><td style="text-align:center;padding:24px 16px;color:#D1D5DB;font-size:13px;">
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
  </body>
</html>"""

    return html
