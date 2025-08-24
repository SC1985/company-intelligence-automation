# src/render_email.py
# Fixed: Removed inline color styles to allow proper dark/light mode switching

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
    """Performance chip using only CSS classes for colors."""
    v = _safe_float(value, None)
    
    if v is None:
        sign = ""
        txt = "--"
        chip_class = "chip chip-neutral"
    else:
        if v >= 0:
            sign = "▲"
            chip_class = "chip chip-positive"
        else:
            sign = "▼"
            chip_class = "chip chip-negative"
        txt = f"{abs(v):.1f}%"
    
    safe_label = escape(label)
    
    # No color inline styles - all handled by CSS
    return (f'<span class="{chip_class}">{safe_label} {sign} {txt}</span>')


def _button(label: str, url: str, style="primary"):
    """Button using only CSS classes for colors."""
    safe_label = escape(label)
    href = escape(url or "#")
    
    btn_class = f"btn btn-{style}"
    
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" class="btn-wrapper">'
            f'<tr><td class="{btn_class}">'
            f'<a href="{href}" target="_blank" rel="noopener noreferrer" class="btn-link">'
            f'{safe_label} →</a></td></tr></table>')


def _range_bar(pos: float, low: float, high: float):
    """52-week range bar using only CSS classes for colors."""
    pct = max(0.0, min(100.0, _safe_float(pos, 0.0)))
    left = f"{pct:.1f}%"
    right = f"{100 - pct:.1f}%"
    
    low_v = _safe_float(low, 0.0) or 0.0
    high_v = _safe_float(high, 0.0) or 0.0
    current_v = low_v + (high_v - low_v) * (pct / 100.0) if high_v > low_v else low_v
    
    # Position-based marker
    if pct < 25:
        marker_class = "marker-low"
    elif pct > 75:  
        marker_class = "marker-high"
    else:
        marker_class = "marker-mid"
    
    # Track without inline colors
    track = (
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" class="range-track-table">'
        f'<tr>'
        f'<td class="range-track" style="width:{left};">&nbsp;</td>'
        f'<td class="range-marker {marker_class}" style="width:10px;">&nbsp;</td>'
        f'<td class="range-track" style="width:{right};">&nbsp;</td>'
        f'</tr></table>'
    )
    
    # Caption without inline colors
    caption = (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" class="range-caption">'
               f'<tr>'
               f'<td class="range-label range-low">Low ${low_v:.2f}</td>'
               f'<td class="range-current {marker_class}-text">${current_v:.2f}</td>'
               f'<td class="range-label range-high">High ${high_v:.2f}</td>'
               f'</tr></table>')
    
    return (f'<div class="range-container">'
            f'<div class="range-title">52-Week Range</div>'
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
    """Hero rendering using only CSS classes for colors."""
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
    
    # Body HTML without inline colors
    body_html = ""
    if para:
        body_html = f'''
        <tr><td class="hero-body">{escape(para)}</td></tr>'''
    
    # Metadata without inline colors
    meta_parts = []
    if source:
        meta_parts.append(f'<span class="hero-source">{escape(source)}</span>')
    if when:
        meta_parts.append(f'<span class="hero-date">{escape(when)}</span>')
    
    meta_html = ""
    if meta_parts:
        meta_html = f'''
        <tr><td class="hero-meta">{" • ".join(meta_parts)}</td></tr>'''
    
    # Hero container without inline colors
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="hero-container">
  <tr>
    <td class="hero-inner">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr><td class="hero-title">
          <a href="{escape(url)}" class="hero-link">{escape(title)}</a>
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
    """Card building using only CSS classes for colors."""
    name = c.get("name") or c.get("ticker") or c.get("symbol") or "Unknown"
    ticker = str(c.get("ticker") or c.get("symbol") or "")
    is_crypto = ticker.endswith("-USD") or (str(c.get("asset_class") or "").lower() == "crypto")

    # Price formatting without inline colors
    price_v = _safe_float(c.get("price"), None)
    if price_v is None:
        price_fmt = '<span class="price-null">--</span>'
    else:
        if is_crypto:
            if price_v >= 1000:
                price_fmt = f'<span class="price-text">${price_v:,.0f}</span>'
            elif price_v >= 1:
                price_fmt = f'<span class="price-text">${price_v:,.2f}</span>'
            else:
                price_fmt = f'<span class="price-text">${price_v:.4f}</span>'
        else:
            price_fmt = f'<span class="price-text">${price_v:,.2f}</span>'

    # Performance chips
    chips_line1 = _chip("1D", c.get("pct_1d")) + _chip("1W", c.get("pct_1w"))
    chips_line2 = _chip("1M", c.get("pct_1m")) + _chip("YTD", c.get("pct_ytd"))
    
    chips = f'''
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="chips-table">
        <tr><td class="chips-row">{chips_line1}</td></tr>
        <tr><td class="chips-row">{chips_line2}</td></tr>
    </table>'''

    # News bullets without inline colors
    bullets = []
    headline = c.get("headline")
    source = c.get("source")
    when_fmt = _fmt_ct(c.get("when"), force_time=False, tz_suffix_policy="never") if c.get("when") else None

    if headline and _belongs_to_company(c, headline):
        # Truncate long headlines
        display_headline = headline[:100] + "..." if len(headline) > 100 else headline
        
        if source and when_fmt:
            bullets.append(f"★ {display_headline} <span class='news-meta'>({source}, {when_fmt})</span>")
        elif source:
            bullets.append(f"★ {display_headline} <span class='news-meta'>({source})</span>")
        elif when_fmt:
            bullets.append(f"★ {display_headline} <span class='news-meta'>({when_fmt})</span>")
        else:
            bullets.append(f"★ {display_headline}")
    else:
        company_name = name.replace(" Inc.", "").replace(" Corporation", "").strip()
        bullets.append(f'★ <span class="news-placeholder">Latest {company_name} coverage — see News</span>')

    # Additional context bullets
    next_event = c.get("next_event")
    if next_event:
        event_date = _fmt_ct(next_event, force_time=False, tz_suffix_policy="never")
        if event_date:
            bullets.append(f'<span class="event-info">📅 Next: {event_date}</span>')

    vol_multiplier = _safe_float(c.get("vol_x_avg"), None)
    if vol_multiplier is not None and vol_multiplier > 1.5:  # Only show significant volume
        bullets.append(f'<span class="volume-info">📊 Volume: {vol_multiplier:.1f}× avg</span>')

    # Bullets HTML without inline colors
    bullets_html = ""
    for i, bullet in enumerate(bullets):
        if i == 0:  # Main news item
            bullets_html += f'''
            <tr><td class="bullet-main">{bullet}</td></tr>'''
        else:  # Secondary items
            bullets_html += f'''
            <tr><td class="bullet-secondary">{bullet}</td></tr>'''

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
        <tr><td class="card-actions">
            {_button("News", news_url, "primary")}
            {_button("Press", pr_url, "secondary")}
        </td></tr>
    </table>'''

    # Card without inline colors
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="card-container">
  <tr>
    <td class="card-inner">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <!-- Header -->
        <tr><td>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
            <tr><td class="card-title">{escape(str(name))}</td></tr>
            <tr><td>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td class="ticker-text">({escape(ticker)})</td>
                  <td class="price-cell">{price_fmt}</td>
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
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="bullets-table">
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
    """Two-column grid that becomes single column on mobile."""
    if not cards:
        return ""
    
    rows = []
    for i in range(0, len(cards), 2):
        left = cards[i]
        right = cards[i + 1] if i + 1 < len(cards) else ""
        
        if right:
            row = f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="grid-table">
  <tr>
    <td class="grid-col grid-col-left">{left}</td>
    <td class="grid-col grid-col-right">{right}</td>
  </tr>
</table>'''
        else:
            row = f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="grid-table">
  <tr>
    <td class="grid-col-single">{left}</td>
  </tr>
</table>'''
        
        rows.append(row)
    
    return "".join(rows)


def _section_container(title: str, inner_html: str):
    """Section container using only CSS classes for colors."""
    safe_title = escape(title)
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="section-container">
  <tr>
    <td class="section-inner">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr><td class="section-title">{safe_title}</td></tr>
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


# ---------- Main renderer with proper CSS-only theming ----------

def render_email(summary, companies, cryptos=None):
    """Email rendering with CSS-only dark/light mode switching."""
    
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
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="market-summary">
          <tr><td class="market-summary-inner">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td class="market-emoji">{market_emoji}</td>
                <td class="market-text-primary">{market_sentiment} Session</td>
                <td class="market-text-secondary">{up_count} up • {down_count} down</td>
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
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="quality-note">
          <tr><td class="quality-text">⚠️ {failed_count} of {total_entities} assets had data issues</td></tr>
        </table>'''

    # Enhanced email preview
    email_preview = _generate_enhanced_preview()

    # Complete CSS with NO inline color styles
    css = """
<style>
/* === CORE STRUCTURE === */
* { margin: 0; padding: 0; }
body { margin: 0; padding: 0; width: 100% !important; min-width: 100%; }
table { border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt; }
td { border-collapse: collapse; }
img { border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }
a { text-decoration: none; }

/* === DEFAULT DARK THEME === */
body, .email-body { 
  background: #0b0c10 !important; 
  color: #e5e7eb !important;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
}

.main-wrapper { background: #0b0c10 !important; }
.main-container { 
  background: linear-gradient(135deg, #1F2937 0%, #111827 100%) !important;
  border-radius: 16px !important;
  padding: 32px !important;
  box-shadow: 0 8px 20px rgba(0,0,0,0.5) !important;
}

/* Header */
.header-title {
  font-weight: 700 !important;
  font-size: 48px !important;
  color: #FFFFFF !important;
  margin: 0 0 10px 0 !important;
  letter-spacing: -0.5px !important;
  text-align: center !important;
}

.header-subtitle {
  color: #D1D5DB !important;
  margin-bottom: 16px !important;
  font-size: 14px !important;
  font-weight: 500 !important;
  text-align: center !important;
}

/* Market Summary */
.market-summary {
  border-collapse: collapse !important;
  background: #1F2937 !important;
  border-radius: 12px !important;
  margin: 14px 0 !important;
  box-shadow: 0 4px 10px rgba(0,0,0,0.2) !important;
}

.market-summary-inner {
  padding: 16px 20px !important;
}

.market-emoji { 
  font-size: 18px !important;
  padding-right: 10px !important;
}

.market-text-primary { 
  color: #F3F4F6 !important;
  font-weight: 700 !important;
  padding-left: 10px !important;
  font-size: 16px !important;
}

.market-text-secondary { 
  color: #D1D5DB !important;
  font-size: 14px !important;
  text-align: right !important;
  font-weight: 500 !important;
}

/* Hero Section */
.hero-container {
  border-collapse: collapse !important;
  background: linear-gradient(135deg, #1F2937 0%, #111827 100%) !important;
  border-radius: 16px !important;
  margin: 20px 0 !important;
  box-shadow: 0 8px 20px rgba(0,0,0,0.5) !important;
}

.hero-inner { padding: 28px !important; }

.hero-title {
  font-weight: 700 !important;
  font-size: 26px !important;
  line-height: 1.3 !important;
  color: #FFFFFF !important;
}

.hero-link { 
  color: #FFFFFF !important;
  text-decoration: none !important;
}

.hero-body {
  padding-top: 14px !important;
  font-size: 15px !important;
  line-height: 1.6 !important;
  color: #D1D5DB !important;
}

.hero-meta {
  padding-top: 14px !important;
  font-size: 13px !important;
  border-top: 1px solid rgba(255,255,255,0.1) !important;
  padding-top: 12px !important;
  color: #9CA3AF !important;
}

.hero-source { 
  font-weight: 600 !important;
  color: #A78BFA !important;
}

.hero-date { color: #9CA3AF !important; }

/* Cards */
.card-container {
  border-collapse: collapse !important;
  margin: 0 0 12px !important;
  background: linear-gradient(135deg, #1F2937 0%, #111827 100%) !important;
  border-radius: 14px !important;
  box-shadow: 0 6px 16px rgba(0,0,0,0.4) !important;
  overflow: hidden !important;
}

.card-inner {
  padding: 20px 22px !important;
  max-height: 360px !important;
  overflow: hidden !important;
  vertical-align: top !important;
}

.card-title {
  font-weight: 700 !important;
  font-size: 17px !important;
  line-height: 1.3 !important;
  color: #FFFFFF !important;
  padding-bottom: 4px !important;
}

.ticker-text {
  font-size: 13px !important;
  color: #D1D5DB !important;
  font-weight: 600 !important;
}

.price-cell {
  text-align: right !important;
  font-size: 16px !important;
}

.price-text {
  color: #FFFFFF !important;
  font-weight: 700 !important;
}

.price-null { color: #9CA3AF !important; }

/* Performance Chips */
.chip {
  padding: 5px 12px !important;
  border-radius: 12px !important;
  font-size: 12px !important;
  font-weight: 700 !important;
  margin: 2px 6px 4px 0 !important;
  display: inline-block !important;
  box-shadow: 0 2px 6px rgba(0,0,0,0.3) !important;
  white-space: nowrap !important;
}

.chip-neutral { 
  background: #4B5563 !important;
  color: #FFFFFF !important;
}

.chip-positive { 
  background: #059669 !important;
  color: #FFFFFF !important;
}

.chip-negative { 
  background: #DC2626 !important;
  color: #FFFFFF !important;
}

.chips-table { margin: 12px 0 !important; }
.chips-row { 
  line-height: 1.6 !important;
  padding-bottom: 6px !important;
}

/* Range Bar */
.range-container { margin: 14px 0 10px 0 !important; }

.range-title {
  font-size: 12px !important;
  color: #D1D5DB !important;
  margin-bottom: 6px !important;
  font-weight: 600 !important;
}

.range-track-table {
  border-collapse: collapse !important;
  border-radius: 8px !important;
  height: 10px !important;
  overflow: hidden !important;
  min-width: 200px !important;
  box-shadow: inset 0 1px 2px rgba(0,0,0,0.2) !important;
}

.range-track {
  background: #374151 !important;
  height: 10px !important;
  padding: 0 !important;
}

.range-marker {
  height: 10px !important;
  padding: 0 !important;
}

.marker-low { background: #DC2626 !important; }
.marker-high { background: #059669 !important; }
.marker-mid { background: #2563EB !important; }

.range-caption { margin-top: 6px !important; }

.range-label {
  font-size: 11px !important;
  color: #9CA3AF !important;
  font-weight: 500 !important;
}

.range-low { text-align: left !important; }
.range-high { text-align: right !important; }

.range-current {
  font-size: 12px !important;
  font-weight: 700 !important;
  text-align: center !important;
  color: #FFFFFF !important;
}

.marker-low-text { color: #DC2626 !important; }
.marker-high-text { color: #059669 !important; }
.marker-mid-text { color: #2563EB !important; }

/* News Bullets */
.bullets-table { margin-top: 10px !important; }

.bullet-main {
  padding-bottom: 10px !important;
  display: -webkit-box !important;
  -webkit-box-orient: vertical !important;
  -webkit-line-clamp: 3 !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  line-height: 1.5 !important;
  color: #E5E7EB !important;
  font-size: 14px !important;
  font-weight: 500 !important;
}

.bullet-secondary {
  padding-bottom: 6px !important;
  font-size: 12px !important;
  line-height: 1.4 !important;
  color: #9CA3AF !important;
}

.news-meta { color: #9CA3AF !important; }
.news-placeholder { color: #9CA3AF !important; }
.event-info { color: #A78BFA !important; }
.volume-info { color: #F59E0B !important; }

/* Buttons */
.btn-wrapper {
  display: inline-block !important;
  margin-right: 8px !important;
  margin-bottom: 4px !important;
}

.btn {
  border-radius: 10px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  padding: 10px 16px !important;
  box-shadow: 0 3px 8px rgba(0,0,0,0.2) !important;
}

.btn-primary { background: #374151 !important; }
.btn-secondary { background: #6B7280 !important; }

.btn-link {
  color: #FFFFFF !important;
  text-decoration: none !important;
  display: block !important;
}

.card-actions {
  border-top: 1px solid rgba(255,255,255,0.1) !important;
  padding-top: 14px !important;
}

/* Sections */
.section-container {
  border-collapse: collapse !important;
  background: #0F172A !important;
  border-radius: 16px !important;
  margin: 24px 0 !important;
  box-shadow: 0 6px 16px rgba(0,0,0,0.4) !important;
}

.section-inner { padding: 28px !important; }

.section-title {
  font-weight: 700 !important;
  font-size: 32px !important;
  color: #FFFFFF !important;
  margin: 0 0 20px 0 !important;
  padding-bottom: 16px !important;
}

/* Grid */
.grid-table {
  border-collapse: collapse !important;
  margin-bottom: 8px !important;
}

.grid-col {
  width: 50% !important;
  vertical-align: top !important;
}

.grid-col-left { padding-right: 8px !important; }
.grid-col-right { padding-left: 8px !important; }

.grid-col-single {
  vertical-align: top !important;
  max-width: 320px !important;
  margin: 0 auto !important;
}

/* Quality Note */
.quality-note {
  border-collapse: collapse !important;
  margin-top: 14px !important;
  padding: 12px 16px !important;
  background: rgba(185,28,28,0.1) !important;
  border-radius: 10px !important;
  box-shadow: 0 2px 6px rgba(185,28,28,0.1) !important;
}

.quality-text {
  color: #FCA5A5 !important;
  font-size: 13px !important;
  font-weight: 600 !important;
}

/* Footer */
.footer-border {
  border-top: 1px solid rgba(255,255,255,0.1) !important;
  margin-top: 28px !important;
}

.footer-content {
  text-align: center !important;
  padding: 24px 16px !important;
  color: #D1D5DB !important;
  font-size: 13px !important;
}

.footer-primary {
  margin-bottom: 8px !important;
  font-weight: 500 !important;
}

.footer-secondary {
  color: #9CA3AF !important;
  font-weight: 400 !important;
}

/* === LIGHT MODE OVERRIDES === */
@media (prefers-color-scheme: light) {
  body, .email-body { 
    background: #FFFFFF !important; 
    color: #111827 !important;
  }
  
  .main-wrapper { background: #FFFFFF !important; }
  .main-container { 
    background: linear-gradient(135deg, #F3F4F6 0%, #E5E7EB 100%) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
  }
  
  /* Header - Light */
  .header-title { color: #111827 !important; }
  .header-subtitle { color: #4B5563 !important; }
  
  /* Market Summary - Light */
  .market-summary { 
    background: #F3F4F6 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
  }
  .market-text-primary { color: #111827 !important; }
  .market-text-secondary { color: #4B5563 !important; }
  
  /* Hero - Light */
  .hero-container { 
    background: linear-gradient(135deg, #F3F4F6 0%, #E5E7EB 100%) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
  }
  .hero-title { color: #111827 !important; }
  .hero-link { color: #111827 !important; }
  .hero-body { color: #374151 !important; }
  .hero-meta { 
    color: #6B7280 !important;
    border-top: 1px solid rgba(0,0,0,0.1) !important;
  }
  .hero-source { color: #7C3AED !important; }
  .hero-date { color: #6B7280 !important; }
  
  /* Cards - Light */
  .card-container { 
    background: linear-gradient(135deg, #FFFFFF 0%, #F9FAFB 100%) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
  }
  .card-title { color: #111827 !important; }
  .ticker-text { color: #4B5563 !important; }
  .price-text { color: #111827 !important; }
  .price-null { color: #9CA3AF !important; }
  
  /* Performance Chips - Light */
  .chip-neutral { 
    background: #9CA3AF !important;
    color: #FFFFFF !important;
  }
  .chip-positive { 
    background: #10B981 !important;
    color: #FFFFFF !important;
  }
  .chip-negative { 
    background: #EF4444 !important;
    color: #FFFFFF !important;
  }
  
  /* Range Bar - Light */
  .range-title { color: #374151 !important; }
  .range-track { background: #E5E7EB !important; }
  .range-label { color: #6B7280 !important; }
  .range-current { color: #111827 !important; }
  .marker-low { background: #EF4444 !important; }
  .marker-high { background: #10B981 !important; }
  .marker-mid { background: #3B82F6 !important; }
  .marker-low-text { color: #EF4444 !important; }
  .marker-high-text { color: #10B981 !important; }
  .marker-mid-text { color: #3B82F6 !important; }
  
  /* News Bullets - Light */
  .bullet-main { color: #111827 !important; }
  .bullet-secondary { color: #6B7280 !important; }
  .news-meta { color: #6B7280 !important; }
  .news-placeholder { color: #6B7280 !important; }
  .event-info { color: #7C3AED !important; }
  .volume-info { color: #F59E0B !important; }
  
  /* Buttons - Light */
  .btn-primary { background: #4B5563 !important; }
  .btn-secondary { background: #9CA3AF !important; }
  .btn-link { color: #FFFFFF !important; }
  
  .card-actions { 
    border-top: 1px solid rgba(0,0,0,0.1) !important;
  }
  
  /* Sections - Light */
  .section-container { 
    background: #F9FAFB !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;
  }
  .section-title { color: #111827 !important; }
  
  /* Quality Note - Light */
  .quality-note { 
    background: rgba(239,68,68,0.1) !important;
  }
  .quality-text { color: #DC2626 !important; }
  
  /* Footer - Light */
  .footer-border { 
    border-top: 1px solid rgba(0,0,0,0.1) !important;
  }
  .footer-content { color: #4B5563 !important; }
  .footer-secondary { color: #6B7280 !important; }
}

/* === MOBILE RESPONSIVENESS === */
@media only screen and (max-width: 640px) {
  .header-title { font-size: 36px !important; }
  
  .grid-col { 
    display: block !important; 
    width: 100% !important; 
    max-width: 100% !important; 
    padding-left: 0 !important; 
    padding-right: 0 !important;
    padding-bottom: 12px !important;
  }
  
  .card-container {
    max-width: 400px !important;
    margin: 0 auto 12px auto !important;
  }
  
  .card-inner {
    max-height: none !important;
    overflow: visible !important;
  }
  
  .section-title { font-size: 28px !important; }
  .hero-title { font-size: 22px !important; }
}

@media only screen and (max-width: 480px) {
  .header-title { font-size: 32px !important; }
  .section-title { font-size: 24px !important; }
  .hero-title { font-size: 20px !important; }
  
  .card-container { max-width: 100% !important; }
  .card-inner { padding: 16px 18px !important; }
  .main-container { padding: 24px !important; }
}
</style>
"""

    # HTML structure with NO inline color styles
    html = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="dark light">
    <meta name="supported-color-schemes" content="dark light">
    <meta name="description" content="{escape(email_preview)}">
    <meta name="format-detection" content="telephone=no, date=no, address=no, email=no">
    <title>Intelligence Digest</title>
    {css}
  </head>
  <body class="email-body">
    
    <!-- Hidden preview text -->
    <div style="display:none;font-size:1px;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;mso-hide:all;">
      {escape(email_preview)}
    </div>
    
    <!-- Main container -->
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" class="main-wrapper">
      <tr>
        <td align="center" style="padding:20px 12px;">
          <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:640px;max-width:100%;">
            <tr>
              <td class="main-container">
                
                <!-- Header -->
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                  <tr><td>
                    <div class="header-title">Intelligence Digest</div>
                    {f'<div class="header-subtitle">📊 Data as of {escape(as_of)}</div>' if as_of else ''}
                    {market_summary}
                    {quality_note}
                  </td></tr>
                </table>

                <!-- Hero section -->
                {hero_html}

                <!-- Content sections -->
                {''.join(sections)}

                <!-- Footer -->
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="footer-border">
                  <tr><td class="footer-content">
                    <div class="footer-primary">
                      You're receiving this because you subscribed to Intelligence Digest
                    </div>
                    <div class="footer-secondary">
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
