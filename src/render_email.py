# src/render_email.py
# Investment Edge - Enhanced Company and Crypto Cards
# Fixed: Using hybrid color scheme that works in both dark and light modes
# Fixed: Increased width of company modules on mobile only
# Enhanced: Added momentum indicators, volume analysis, and crypto-specific metrics

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
    """Performance chip with hybrid colors that work in both modes."""
    v = _safe_float(value, None)
    
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
    
    return (f'<span class="chip" style="background:{bg};color:{color};'
            f'padding:5px 12px;border-radius:12px;font-size:12px;font-weight:700;'
            f'margin:2px 6px 4px 0;display:inline-block;'
            f'box-shadow:0 2px 6px rgba(0,0,0,0.15);white-space:nowrap;'
            f'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;"'
            f'>{safe_label} {sign} {txt}</span>')


def _button(label: str, url: str, style="primary"):
    """Button with hybrid colors."""
    safe_label = escape(label)
    href = escape(url or "#")
    
    if style == "primary":
        bg = "#4B5563"
        color = "#FFFFFF"
    else:  # secondary
        bg = "#9CA3AF"
        color = "#FFFFFF"
    
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" style="display:inline-block;margin-right:8px;margin-bottom:4px;">'
            f'<tr><td class="btn" style="background:{bg};color:{color};'
            f'border-radius:10px;font-size:13px;font-weight:600;padding:10px 16px;'
            f'box-shadow:0 2px 6px rgba(0,0,0,0.15);'
            f'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">'
            f'<a href="{href}" target="_blank" rel="noopener noreferrer" '
            f'style="color:{color};text-decoration:none;display:block;">'
            f'{safe_label} →</a></td></tr></table>')


def _range_bar(pos: float, low: float, high: float):
    """52-week range bar with hybrid colors."""
    pct = max(0.0, min(100.0, _safe_float(pos, 0.0)))
    left = f"{pct:.1f}%"
    right = f"{100 - pct:.1f}%"
    
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
               f'<td class="range-label" style="font-size:11px;color:#6B7280;text-align:left;font-weight:500;">Low ${low_v:.2f}</td>'
               f'<td class="range-current" style="font-size:12px;color:{marker_color};font-weight:700;text-align:center;">'
               f'${current_v:.2f}</td>'
               f'<td class="range-label" style="font-size:11px;color:#6B7280;text-align:right;font-weight:500;">High ${high_v:.2f}</td>'
               f'</tr></table>')
    
    return (f'<div style="margin:14px 0 10px 0;">'
            f'<div class="range-title" style="font-size:12px;color:#374151;margin-bottom:6px;font-weight:600;">'
            f'52-Week Range</div>'
            + track + caption + '</div>')


def calculate_momentum_score(pct_1d, pct_1w, pct_1m):
    """Calculate momentum score based on multiple timeframes."""
    score = 0
    if pct_1d and pct_1d > 0: score += 1
    if pct_1w and pct_1w > 0: score += 2
    if pct_1m and pct_1m > 0: score += 3
    
    if score >= 5:
        return "Strong Momentum 💪", "#10B981"
    elif score >= 3:
        return "Building Strength 📈", "#3B82F6"
    elif score <= 1:
        return "Losing Steam 📉", "#EF4444"
    else:
        return "Neutral Trend ➡️", "#6B7280"


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
    """Enhanced hero selection prioritizing breaking news with fallback."""
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
                # Validate hero has meaningful content - check description first
                if (cand.get("description") or cand.get("body") or 
                    cand.get("content") or cand.get("first_paragraph")):
                    hero = cand
                    break
    
    if hero:
        return hero
    
    # Enhanced fallback: prioritize BREAKING NEWS, with backup options
    all_entities = (companies or []) + (cryptos or [])
    
    breaking_candidates = []  # For breaking news
    general_candidates = []   # For backup articles
    
    # Breaking news keywords (higher priority)
    breaking_keywords = {
        "urgent": ["breaking", "just in", "alert", "exclusive", "developing"],
        "major_event": ["announces", "launches", "unveils", "reveals", "reports", "surges", "plunges", "crashes", "soars"],
        "earnings": ["earnings", "revenue", "profit", "beat", "miss", "guidance"],
        "deals": ["acquisition", "merger", "buyout", "partnership", "deal"],
        "regulatory": ["sec", "fda", "approval", "investigation", "lawsuit", "ruling"]
    }
    
    # General interest keywords for backup
    general_keywords = {
        "analysis": ["analysis", "outlook", "forecast", "prediction", "expects"],
        "market": ["market", "stocks", "trading", "investors", "wall street"],
        "sector": ["tech", "technology", "ai", "crypto", "energy", "healthcare"],
        "guidance": ["strategy", "plans", "future", "roadmap", "vision"]
    }
    
    # Lower priority commentary keywords
    commentary_keywords = ["could", "might", "may", "what to expect", "preview", "review"]
    
    for entity in all_entities:
        headline = entity.get("headline", "")
        if not headline:
            continue
        
        breaking_score = 0
        general_score = 0
        headline_lower = headline.lower()
        
        # Score for breaking news
        for category, keywords in breaking_keywords.items():
            for keyword in keywords:
                if keyword in headline_lower:
                    if category == "urgent":
                        breaking_score += 25
                    elif category == "major_event":
                        breaking_score += 20
                    elif category == "earnings":
                        breaking_score += 18
                    elif category == "deals":
                        breaking_score += 18
                    else:
                        breaking_score += 15
        
        # Score for general interest (backup)
        for category, keywords in general_keywords.items():
            for keyword in keywords:
                if keyword in headline_lower:
                    if category == "analysis":
                        general_score += 8
                    elif category == "market":
                        general_score += 10
                    elif category == "sector":
                        general_score += 9
                    else:
                        general_score += 7
        
        # Penalize pure commentary for breaking news
        for keyword in commentary_keywords:
            if keyword in headline_lower:
                breaking_score -= 10
                # But don't penalize as much for general articles
                general_score -= 3
        
        # Boost for recency (applies to both)
        recency_boost = 0
        if entity.get("when"):
            try:
                pub_date = _parse_to_dt(entity.get("when"))
                if pub_date:
                    hours_ago = (datetime.now(timezone.utc) - pub_date).total_seconds() / 3600
                    if hours_ago < 2:
                        recency_boost = 20  # Very recent
                    elif hours_ago < 6:
                        recency_boost = 15
                    elif hours_ago < 12:
                        recency_boost = 10
                    elif hours_ago < 24:
                        recency_boost = 5
            except:
                pass
        
        breaking_score += recency_boost
        general_score += recency_boost
        
        # Boost for quality content
        description = entity.get("description", "")
        if description and len(description) > 50:
            breaking_score += 5
            general_score += 5
        
        # Include company name for context
        entity["company_name"] = entity.get("name", "")
        
        # Add to appropriate candidate list
        if breaking_score > 15:  # Higher threshold for breaking news
            breaking_candidates.append((breaking_score, entity))
        
        if general_score > 5:  # Lower threshold for general articles
            general_candidates.append((general_score, entity))
    
    # First try breaking news candidates
    if breaking_candidates:
        breaking_candidates.sort(reverse=True, key=lambda x: x[0])
        _, best_breaking = breaking_candidates[0]
        
        return {
            "title": best_breaking.get("headline"),
            "url": best_breaking.get("news_url", ""),
            "source": best_breaking.get("source", ""),
            "when": best_breaking.get("when"),
            "body": best_breaking.get("description", ""),
            "description": best_breaking.get("description", ""),
            "company_name": best_breaking.get("company_name", ""),
            "is_breaking": True  # Flag to indicate this is breaking news
        }
    
    # Fallback to best general article
    if general_candidates:
        general_candidates.sort(reverse=True, key=lambda x: x[0])
        _, best_general = general_candidates[0]
        
        return {
            "title": best_general.get("headline"),
            "url": best_general.get("news_url", ""),
            "source": best_general.get("source", ""),
            "when": best_general.get("when"),
            "body": best_general.get("description", ""),
            "description": best_general.get("description", ""),
            "company_name": best_general.get("company_name", ""),
            "is_breaking": False  # Flag to indicate this is not breaking news
        }
    
    return None


def _select_mover_story(companies: list, cryptos: list):
    """Select the biggest mover for the second story."""
    all_entities = (companies or []) + (cryptos or [])
    
    # Find the biggest absolute mover with a headline
    best_mover = None
    best_move = 0
    
    for entity in all_entities:
        # Get 1-day percentage change
        pct_1d = entity.get("pct_1d")
        if pct_1d is None:
            continue
            
        abs_move = abs(pct_1d)
        
        # Must have a headline to be a story
        headline = entity.get("headline", "")
        if not headline:
            continue
            
        # Track the biggest mover
        if abs_move > best_move:
            best_move = abs_move
            best_mover = entity
    
    if best_mover and best_move > 0.5:  # At least 0.5% move
        # Format the mover story
        name = best_mover.get("name", "")
        ticker = best_mover.get("ticker", "")
        pct = best_mover.get("pct_1d", 0)
        direction = "up" if pct > 0 else "down"
        arrow = "📈" if pct > 0 else "📉"
        
        return {
            "title": f"{arrow} {name} {direction} {abs(pct):.1f}% - {best_mover.get('headline', '')}",
            "url": best_mover.get("news_url", ""),
            "source": best_mover.get("source", ""),
            "when": best_mover.get("when"),
            "description": best_mover.get("description", ""),
            "ticker": ticker,
            "pct_change": pct,
            "price": best_mover.get("price")
        }
    
    return None


def _render_hero(hero: dict) -> str:
    """Hero rendering matching secondary article style."""
    if not hero:
        return ""
    
    title = (hero.get("title") or "").strip()
    if not title:
        return ""
    
    url = hero.get("url") or "#"
    source = hero.get("source") or ""
    when = _fmt_ct(hero.get("when"), force_time=False, tz_suffix_policy="never") if hero.get("when") else ""
    company_name = hero.get("company_name", "")
    is_breaking = hero.get("is_breaking", False)
    
    # Add a label for breaking news vs market analysis - matching TOP MOVER style
    if is_breaking:
        label_html = '''<span style="color:#DC2626;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">● BREAKING NEWS</span><br>'''
    else:
        label_html = '''<span style="color:#6B7280;font-size:12px;font-weight:500;text-transform:uppercase;letter-spacing:0.5px;">MARKET ANALYSIS</span><br>'''
    
    # Description - matching mover story length
    description = (hero.get("description") or hero.get("body") or "").strip()
    if not description:
        description = _first_paragraph(hero, title=title)
    
    if description and len(description) > 200:
        sentences = re.split(r'[.!?]\s+', description)
        truncated = ""
        for sentence in sentences:
            if len(truncated + sentence) <= 180:
                truncated += sentence + ". "
            else:
                break
        description = truncated.strip() if truncated else description[:197] + "..."
    
    # Body HTML - matching mover story style
    body_html = ""
    if description:
        body_html = f'''
        <tr><td style="padding-top:12px;font-size:14px;line-height:1.5;
                     color:#374151;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">
            {escape(description)}
        </td></tr>'''
    
    # Metadata - matching mover story style
    meta_parts = []
    if company_name:
        meta_parts.append(f'<span style="font-weight:600;color:#7C3AED;">{escape(company_name)}</span>')
    if source:
        meta_parts.append(f'<span style="color:#6B7280;">{escape(source)}</span>')
    if when:
        meta_parts.append(f'<span style="color:#6B7280;">{escape(when)}</span>')
    
    meta_html = ""
    if meta_parts:
        meta_html = f'''
        <tr><td style="padding-top:12px;font-size:12px;color:#6B7280;">
            {" • ".join(meta_parts)}
        </td></tr>'''
    
    # Container - exactly matching mover story structure
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;
              background:#FFFFFF;
              border:1px solid #E5E7EB;
              border-radius:16px;margin:20px 0;
              box-shadow:0 4px 12px rgba(0,0,0,0.08);">
  <tr>
    <td style="padding:18px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="font-weight:700;font-size:20px;line-height:1.3;color:#111827;
                     font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">
          <a href="{escape(url)}" style="color:#111827;text-decoration:none;">
            {label_html}
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


def _render_mover_story(mover: dict) -> str:
    """Render the biggest mover as a secondary story."""
    if not mover:
        return ""
    
    title = (mover.get("title") or "").strip()
    if not title:
        return ""
    
    url = mover.get("url") or "#"
    source = mover.get("source") or ""
    when = _fmt_ct(mover.get("when"), force_time=False, tz_suffix_policy="never") if mover.get("when") else ""
    ticker = mover.get("ticker", "")
    pct_change = mover.get("pct_change", 0)
    price = mover.get("price")
    
    # Description
    description = (mover.get("description") or "").strip()
    if description and len(description) > 200:
        sentences = re.split(r'[.!?]\s+', description)
        truncated = ""
        for sentence in sentences:
            if len(truncated + sentence) <= 180:
                truncated += sentence + ". "
            else:
                break
        description = truncated.strip() if truncated else description[:197] + "..."
    
    # Price and change display
    price_display = ""
    if price:
        color = "#10B981" if pct_change > 0 else "#EF4444"
        arrow = "▲" if pct_change > 0 else "▼"
        price_display = f'''
        <span style="font-size:18px;font-weight:700;color:{color};margin-left:12px;">
            {arrow} ${price:.2f} ({pct_change:+.1f}%)
        </span>'''
    
    # Body HTML
    body_html = ""
    if description:
        body_html = f'''
        <tr><td style="padding-top:12px;font-size:14px;line-height:1.5;
                     color:#374151;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">
            {escape(description)}
        </td></tr>'''
    
    # Metadata
    meta_parts = []
    if ticker:
        meta_parts.append(f'<span style="font-weight:600;color:#7C3AED;">{escape(ticker)}</span>')
    if source:
        meta_parts.append(f'<span style="color:#6B7280;">{escape(source)}</span>')
    if when:
        meta_parts.append(f'<span style="color:#6B7280;">{escape(when)}</span>')
    
    meta_html = ""
    if meta_parts:
        meta_html = f'''
        <tr><td style="padding-top:12px;font-size:12px;color:#6B7280;">
            {" • ".join(meta_parts)}
        </td></tr>'''
    
    # Mover story container
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;
              background:#FFFFFF;
              border:1px solid #E5E7EB;
              border-radius:16px;margin:20px 0;
              box-shadow:0 4px 12px rgba(0,0,0,0.08);">
  <tr>
    <td style="padding:18px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="font-weight:700;font-size:20px;line-height:1.3;color:#111827;
                     font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">
          <a href="{escape(url)}" style="color:#111827;text-decoration:none;">
            <span style="color:#6B7280;font-size:12px;font-weight:500;text-transform:uppercase;letter-spacing:0.5px;">TOP MOVER</span><br>
            {escape(title.replace("📈 ", "").replace("📉 ", ""))}
            {price_display}
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
    """Enhanced card building with momentum indicators and volume analysis."""
    name = c.get("name") or c.get("ticker") or c.get("symbol") or "Unknown"
    ticker = str(c.get("ticker") or c.get("symbol") or "")
    is_crypto = ticker.endswith("-USD") or (str(c.get("asset_class") or "").lower() == "crypto")

    # For crypto, use enhanced crypto card builder
    if is_crypto:
        return _build_crypto_card(c)

    # Price formatting for stocks
    price_v = _safe_float(c.get("price"), None)
    if price_v is None:
        price_fmt = '<span style="color:#9CA3AF;">--</span>'
    else:
        price_fmt = f'<span class="price-text" style="color:#111827;font-weight:700;">${price_v:,.2f}</span>'

    # Performance chips
    chips_line1 = _chip("1D", c.get("pct_1d")) + _chip("1W", c.get("pct_1w"))
    chips_line2 = _chip("1M", c.get("pct_1m")) + _chip("YTD", c.get("pct_ytd"))
    
    chips = f'''
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:12px 0;">
        <tr><td style="line-height:1.6;padding-bottom:6px;">{chips_line1}</td></tr>
        <tr><td style="line-height:1.6;">{chips_line2}</td></tr>
    </table>'''

    # Momentum indicator
    momentum_text, momentum_color = calculate_momentum_score(
        c.get("pct_1d"), c.get("pct_1w"), c.get("pct_1m")
    )
    momentum_html = f'''
    <tr><td style="padding-bottom:8px;">
        <span style="color:{momentum_color};font-size:13px;font-weight:600;">
            {momentum_text}
        </span>
    </td></tr>'''

    # Volume indicator
    volume_html = ""
    vol_multiplier = _safe_float(c.get("vol_x_avg"), None)
    if vol_multiplier is not None:
        if vol_multiplier > 2.0:
            volume_html = f'''
            <tr><td style="padding-bottom:8px;">
                <span style="color:#F59E0B;font-size:13px;font-weight:600;">
                    🔥 Volume: {vol_multiplier:.1f}× average
                </span>
            </td></tr>'''
        elif vol_multiplier > 1.5:
            volume_html = f'''
            <tr><td style="padding-bottom:8px;">
                <span style="color:#3B82F6;font-size:13px;font-weight:600;">
                    📊 Volume: {vol_multiplier:.1f}× average
                </span>
            </td></tr>'''

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

    # Earnings date if available
    earnings_date = c.get("earnings_date")
    if earnings_date:
        earnings_fmt = _fmt_ct(earnings_date, force_time=False, tz_suffix_policy="never")
        if earnings_fmt:
            bullets.append(f'<span style="color:#10B981;">📈 Earnings: {earnings_fmt}</span>')

    # Bullets HTML
    bullets_html = ""
    for i, bullet in enumerate(bullets):
        if i == 0:  # Main news item
            bullets_html += f'''
            <tr><td class="bullet-main" style="padding-bottom:10px;
                          display:-webkit-box;-webkit-box-orient:vertical;
                          -webkit-line-clamp:3;overflow:hidden;text-overflow:ellipsis;
                          line-height:1.5;color:#374151;font-size:14px;font-weight:500;">
                {bullet}
            </td></tr>'''
        else:  # Secondary items
            bullets_html += f'''
            <tr><td class="bullet-secondary" style="padding-bottom:6px;font-size:12px;line-height:1.4;color:#6B7280;">
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
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;margin:0 0 12px;
              background:#FFFFFF;
              border:1px solid #E5E7EB;
              border-radius:14px;
              box-shadow:0 2px 8px rgba(0,0,0,0.06);overflow:hidden;">
  <tr>
    <td class="card-inner" style="padding:20px 22px;max-height:420px;overflow:hidden;vertical-align:top;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <!-- Header -->
        <tr><td>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
            <tr><td class="card-title" style="font-weight:700;font-size:17px;line-height:1.3;color:#111827;
                         font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;
                         padding-bottom:4px;">{escape(str(name))}</td></tr>
            <tr><td>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td class="ticker-text" style="font-size:13px;color:#6B7280;font-weight:600;">({escape(ticker)})</td>
                  <td class="price-cell" style="text-align:right;font-size:16px;">{price_fmt}</td>
                </tr>
              </table>
            </td></tr>
          </table>
        </td></tr>
        
        <!-- Performance chips -->
        <tr><td>{chips}</td></tr>
        
        <!-- Momentum and Volume indicators -->
        <tr><td>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
            {momentum_html}
            {volume_html}
          </table>
        </td></tr>
        
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


def _build_crypto_card(c):
    """Enhanced crypto card with specific metrics."""
    name = c.get("name") or c.get("ticker") or c.get("symbol") or "Unknown"
    ticker = str(c.get("ticker") or c.get("symbol") or "")
    
    # Crypto-specific price formatting
    price_v = _safe_float(c.get("price"), None)
    if price_v is None:
        price_fmt = '<span style="color:#9CA3AF;">--</span>'
    else:
        if price_v >= 1000:
            price_fmt = f'<span class="price-text" style="color:#111827;font-weight:700;">${price_v:,.0f}</span>'
        elif price_v >= 1:
            price_fmt = f'<span class="price-text" style="color:#111827;font-weight:700;">${price_v:,.2f}</span>'
        elif price_v >= 0.01:
            price_fmt = f'<span class="price-text" style="color:#111827;font-weight:700;">${price_v:.4f}</span>'
        else:
            price_fmt = f'<span class="price-text" style="color:#111827;font-weight:700;">${price_v:.8f}</span>'

    # Performance chips
    chips_line1 = _chip("1D", c.get("pct_1d")) + _chip("1W", c.get("pct_1w"))
    chips_line2 = _chip("1M", c.get("pct_1m")) + _chip("YTD", c.get("pct_ytd"))
    
    chips = f'''
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:12px 0;">
        <tr><td style="line-height:1.6;padding-bottom:6px;">{chips_line1}</td></tr>
        <tr><td style="line-height:1.6;">{chips_line2}</td></tr>
    </table>'''

    # Momentum indicator
    momentum_text, momentum_color = calculate_momentum_score(
        c.get("pct_1d"), c.get("pct_1w"), c.get("pct_1m")
    )
    momentum_html = f'''
    <tr><td style="padding-bottom:8px;">
        <span style="color:{momentum_color};font-size:13px;font-weight:600;">
            {momentum_text}
        </span>
    </td></tr>'''

    # Market cap and volume indicators
    market_cap = c.get("market_cap")
    volume_24h = c.get("volume_24h")
    
    market_dominance_html = ""
    if ticker == "BTC-USD":
        market_dominance_html = '''
        <tr><td style="padding-bottom:8px;">
            <span style="color:#F59E0B;font-size:13px;font-weight:600;">
                👑 Market Leader
            </span>
        </td></tr>'''
    elif ticker == "ETH-USD":
        market_dominance_html = '''
        <tr><td style="padding-bottom:8px;">
            <span style="color:#8B5CF6;font-size:13px;font-weight:600;">
                ⚡ Smart Contract Leader
            </span>
        </td></tr>'''
    
    # Volume indicator
    volume_html = ""
    if volume_24h:
        if volume_24h > 1_000_000_000:
            volume_html = f'''
            <tr><td style="padding-bottom:8px;">
                <span style="color:#3B82F6;font-size:13px;font-weight:600;">
                    💎 ${volume_24h/1_000_000_000:.1f}B daily volume
                </span>
            </td></tr>'''
        elif volume_24h > 1_000_000:
            volume_html = f'''
            <tr><td style="padding-bottom:8px;">
                <span style="color:#6B7280;font-size:13px;font-weight:600;">
                    💰 ${volume_24h/1_000_000:.1f}M daily volume
                </span>
            </td></tr>'''
    
    # ATH distance indicator
    ath_change = c.get("ath_change")
    ath_html = ""
    if ath_change:
        if ath_change > -10:
            ath_html = f'''
            <tr><td style="padding-bottom:8px;">
                <span style="color:#10B981;font-size:13px;font-weight:600;">
                    🎯 Near ATH ({ath_change:.1f}%)
                </span>
            </td></tr>'''
        elif ath_change < -50:
            ath_html = f'''
            <tr><td style="padding-bottom:8px;">
                <span style="color:#EF4444;font-size:13px;font-weight:600;">
                    📉 {abs(ath_change):.0f}% from ATH
                </span>
            </td></tr>'''

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
        crypto_name = name.replace(" (Crypto)", "").strip()
        bullets.append(f'★ <span style="color:#6B7280;">Latest {crypto_name} updates — see News</span>')

    # Bullets HTML
    bullets_html = ""
    for i, bullet in enumerate(bullets):
        if i == 0:  # Main news item
            bullets_html += f'''
            <tr><td class="bullet-main" style="padding-bottom:10px;
                          display:-webkit-box;-webkit-box-orient:vertical;
                          -webkit-line-clamp:3;overflow:hidden;text-overflow:ellipsis;
                          line-height:1.5;color:#374151;font-size:14px;font-weight:500;">
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
    
    # Crypto-specific URLs
    if ticker == "BTC-USD":
        pr_url = "https://bitcoin.org/en/news"
    elif ticker == "ETH-USD":
        pr_url = "https://blog.ethereum.org"
    elif ticker == "XRP-USD":
        pr_url = "https://ripple.com/insights"
    else:
        pr_url = c.get("pr_url") or news_url
    
    ctas = f'''
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="border-top:1px solid #E5E7EB;padding-top:14px;">
            {_button("News", news_url, "primary")}
            {_button("Updates", pr_url, "secondary")}
        </td></tr>
    </table>'''

    # Card with crypto-specific styling
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;margin:0 0 12px;
              background:linear-gradient(135deg, #FFFFFF 0%, #F9FAFB 100%);
              border:1px solid #E5E7EB;
              border-radius:14px;
              box-shadow:0 2px 8px rgba(0,0,0,0.06);overflow:hidden;">
  <tr>
    <td class="card-inner" style="padding:20px 22px;max-height:420px;overflow:hidden;vertical-align:top;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <!-- Header with crypto icon -->
        <tr><td>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
            <tr><td class="card-title" style="font-weight:700;font-size:17px;line-height:1.3;color:#111827;
                         font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;
                         padding-bottom:4px;">
                <span style="margin-right:6px;">₿</span>{escape(str(name))}
            </td></tr>
            <tr><td>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td class="ticker-text" style="font-size:13px;color:#6B7280;font-weight:600;">({escape(ticker)})</td>
                  <td class="price-cell" style="text-align:right;font-size:16px;">{price_fmt}</td>
                </tr>
              </table>
            </td></tr>
          </table>
        </td></tr>
        
        <!-- Performance chips -->
        <tr><td>{chips}</td></tr>
        
        <!-- Crypto-specific indicators -->
        <tr><td>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
            {momentum_html}
            {market_dominance_html}
            {volume_html}
            {ath_html}
          </table>
        </td></tr>
        
        <!-- 52-week range -->  
        <tr><td>{range_html}</td></tr>
        
        <!-- News -->
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
    """Two-column grid that becomes single column on mobile."""
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
    <td class="stack-col" style="vertical-align:top;margin:0 auto;">{left}</td>
  </tr>
</table>'''
        
        rows.append(row)
    
    return "".join(rows)


def _section_container(title: str, inner_html: str):
    """Section container with hybrid colors."""
    safe_title = escape(title)
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;background:#F9FAFB;
              border-radius:16px;margin:24px 0;
              box-shadow:0 2px 8px rgba(0,0,0,0.04);">
  <tr>
    <td style="padding:28px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr><td class="section-title" style="font-weight:700;font-size:28px;color:#111827;
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


def _generate_enhanced_preview(hero_obj=None, market_summary=None) -> str:
    """Generate compelling preview text from hero article or market summary."""
    
    # First, try to use market summary if available
    if market_summary:
        up_count = market_summary.get("up_count", 0)
        down_count = market_summary.get("down_count", 0)
        
        if up_count or down_count:
            total = up_count + down_count
            up_pct = (up_count / total * 100) if total > 0 else 0
            
            if up_pct >= 70:
                return f"🟢 Strong Session • {up_count} up, {down_count} down"
            elif up_pct >= 60:
                return f"🟡 Positive Session • {up_count} up, {down_count} down"
            elif up_pct >= 40:
                return f"⚪ Mixed Session • {up_count} up, {down_count} down"
            else:
                return f"🔴 Weak Session • {up_count} up, {down_count} down"
    
    # If we have a hero article with description, use that as fallback
    if hero_obj:
        description = hero_obj.get("description") or hero_obj.get("body") or ""
        if description:
            # Clean and truncate for preview
            preview = description.strip()
            # Remove any HTML if present
            preview = re.sub(r'<[^>]+>', '', preview)
            # Clean up whitespace
            preview = re.sub(r'\s+', ' ', preview)
            
            # Truncate intelligently for inbox preview (usually shows ~90-110 chars)
            if len(preview) > 100:
                # Try to cut at sentence boundary
                sentences = re.split(r'[.!?]\s+', preview)
                if sentences and len(sentences[0]) <= 100:
                    return sentences[0] + "."
                # Otherwise cut at word boundary
                preview = preview[:97].rsplit(' ', 1)[0] + "..."
            
            return preview
    
    # Final fallback to market-focused previews
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    day_name = now.strftime("%A")
    
    preview_options = [
        f"Top movers, breaking news & strategic signals across your portfolio at {current_time}",
        f"Live performance data, sentiment analysis & key developments in your holdings", 
        f"Real-time insights, news synthesis & momentum indicators for {day_name}",
        f"Market movements, sector analysis & breaking news from your investments",
        f"Performance metrics, news highlights & market opportunities • {current_time} update"
    ]
    
    # Rotate based on day of year for consistency with variety
    index = now.timetuple().tm_yday % len(preview_options)
    return preview_options[index]


# ---------- Main renderer with Investment Edge branding ----------

def render_email(summary, companies, cryptos=None):
    """Investment Edge email rendering with enhanced cards."""
    
    # Entity processing
    company_cards = []
    crypto_cards = []

    # Process companies
    for c in companies or []:
        ticker = str(c.get("ticker") or c.get("symbol") or "")
        is_crypto = ticker.endswith("-USD") or (str(c.get("asset_class") or "").lower() == "crypto")
        
        if is_crypto:
            crypto_cards.append(_build_crypto_card(c))
        else:
            company_cards.append(_build_card(c))

    # Process explicit crypto list
    if cryptos:
        for cx in cryptos:
            crypto_cards.append(_build_crypto_card(cx))

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
               class="market-summary" style="border-collapse:collapse;background:#F3F4F6;
                      border-radius:12px;margin:14px 0;
                      box-shadow:0 2px 6px rgba(0,0,0,0.05);">
          <tr><td style="padding:16px 20px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td class="market-emoji" style="font-size:18px;">{market_emoji}</td>
                <td class="market-primary" style="color:#111827;font-weight:700;padding-left:10px;font-size:16px;">{market_sentiment} Session</td>
                <td class="market-secondary" style="color:#6B7280;font-size:14px;text-align:right;font-weight:500;">
                  {up_count} up • {down_count} down
                </td>
              </tr>
            </table>
          </td></tr>
        </table>'''

    # Hero selection and rendering
    hero_obj = _select_hero(summary, companies or [], cryptos or [])
    hero_html = _render_hero(hero_obj) if hero_obj else ""
    
    # Biggest mover selection and rendering
    mover_obj = _select_mover_story(companies or [], cryptos or [])
    mover_html = _render_mover_story(mover_obj) if mover_obj else ""
    
    # Extract hero headline for mobile header AND for subject line
    hero_headline = ""
    hero_headline_for_subject = ""
    if hero_obj and hero_obj.get("title"):
        hero_headline = hero_obj.get("title", "").strip()
        hero_headline_for_subject = hero_headline  # Keep full length for subject
        # Truncate if too long for header display
        if len(hero_headline) > 80:
            hero_headline = hero_headline[:77] + "..."

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

    # Email preview - use market summary first, then hero article if available
    email_preview = _generate_enhanced_preview(hero_obj, summary)

    # Minimal CSS for mobile responsiveness only
    css = """
<style>
/* Desktop/default view */
.mobile-title {
  display: none !important;
}
.desktop-title {
  display: block !important;
}

/* Mobile responsiveness with MUCH larger text to match desktop feel */
@media only screen and (max-width: 640px) {
  /* Show/hide titles based on screen size */
  .mobile-title {
    display: block !important;
    font-size: 32px !important;
    line-height: 1.2 !important;
    font-weight: 700;
    color: #111827;
    margin: 0 0 10px 0;
    letter-spacing: -0.5px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }
  .desktop-title {
    display: none !important;
  }
  
  .stack-col { 
    display: block !important; 
    width: 100% !important; 
    max-width: 100% !important; 
    padding-left: 0 !important; 
    padding-right: 0 !important;
    padding-bottom: 16px !important;
  }
  
  /* REDUCED PADDING for wider company modules */
  .outer-padding {
    padding: 8px 2px !important;  /* Much less horizontal padding */
  }
  
  .main-container {
    padding: 16px 8px !important;  /* Less horizontal padding */
  }
  
  .hero-container td {
    padding: 18px 16px !important;  /* Matching mover story padding */
  }
  
  .hero-padding {
    padding: 18px 16px !important;  /* Ensure consistency */
  }
  
  /* Section containers get MUCH less padding for wider cards */
  .section-container td {
    padding: 20px 8px !important;  /* Much less horizontal padding */
  }
  
  .card-inner {
    padding: 18px 16px !important;  /* Slightly less horizontal padding */
  }
  
  .header-subtitle {
    font-size: 17px !important;
  }
  
  .section-title {
    font-size: 36px !important;
    line-height: 1.2 !important;
  }
  
  /* Scale up all text significantly */
  td {
    font-size: 18px !important;
  }
  
  .hero-title {
    font-size: 28px !important;  /* Reduced from 32px to match mover */
    line-height: 1.2 !important;
  }
  
  .hero-body {
    font-size: 16px !important;  /* Reduced to match mover */
    line-height: 1.5 !important;
  }
  
  .card-title {
    font-size: 22px !important;
    line-height: 1.2 !important;
  }
  
  .price-cell {
    font-size: 20px !important;
  }
  
  .price-text {
    font-size: 20px !important;
  }
  
  .ticker-text {
    font-size: 16px !important;
  }
  
  .chip {
    font-size: 15px !important;
    padding: 8px 16px !important;
    margin: 3px 8px 5px 0 !important;
  }
  
  .bullet-main {
    font-size: 18px !important;
    line-height: 1.5 !important;
  }
  
  .bullet-secondary {
    font-size: 16px !important;
    line-height: 1.4 !important;
  }
  
  .btn {
    font-size: 17px !important;
    padding: 14px 22px !important;
  }
  
  /* Range bar text */
  .range-title {
    font-size: 15px !important;
  }
  
  .range-label {
    font-size: 14px !important;
  }
  
  .range-current {
    font-size: 16px !important;
  }
  
  /* Market summary */
  .market-emoji {
    font-size: 22px !important;
  }
  
  .market-primary {
    font-size: 19px !important;
  }
  
  .market-secondary {
    font-size: 16px !important;
  }
  
  /* Footer text */
  .footer-text {
    font-size: 15px !important;
  }
}

@media only screen and (max-width: 480px) {
  /* Mobile title adjustments for smaller screens */
  .mobile-title {
    font-size: 28px !important;
  }
  
  /* Even less padding for smaller screens */
  .outer-padding {
    padding: 6px 0px !important;  /* Almost no horizontal padding */
  }
  
  .main-container {
    padding: 14px 6px !important;  /* Very little horizontal padding */
  }
  
  .section-container td {
    padding: 18px 6px !important;  /* Very little horizontal padding */
  }
  
  .card-inner {
    padding: 16px 14px !important;  /* Less horizontal padding */
  }
  
  .header-subtitle {
    font-size: 16px !important;
  }
  
  .section-title {
    font-size: 32px !important;
  }
  
  .hero-title {
    font-size: 24px !important;  /* Reduced from 28px */
  }
  
  .card-title {
    font-size: 20px !important;
  }
  
  .chip {
    font-size: 14px !important;
    padding: 7px 14px !important;
  }
  
  .btn {
    font-size: 16px !important;
    padding: 12px 20px !important;
  }
}

@media only screen and (max-width: 375px) {
  /* Mobile title for smallest screens */
  .mobile-title {
    font-size: 24px !important;
  }
  
  /* iPhone SE and smaller - maximize width */
  .outer-padding {
    padding: 4px 0px !important;  /* No horizontal padding */
  }
  
  .main-container {
    padding: 12px 4px !important;  /* Minimal horizontal padding */
  }
  
  .section-container td {
    padding: 16px 4px !important;  /* Minimal horizontal padding */
  }
  
  .card-inner {
    padding: 14px 12px !important;  /* Less horizontal padding */
  }
  
  .section-title {
    font-size: 30px !important;
  }
  
  .hero-title {
    font-size: 22px !important;  /* Reduced from 26px */
  }
  
  .card-title {
    font-size: 19px !important;
  }
}
</style>
"""

    # HTML structure with Investment Edge branding
    html = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="light">
    <meta name="supported-color-schemes" content="light">
    <meta name="description" content="{escape(email_preview)}">
    <meta name="format-detection" content="telephone=no, date=no, address=no, email=no">
    <title>Investment Edge</title>
    <!-- HERO_HEADLINE:{escape(hero_headline_for_subject) if hero_headline_for_subject else ''} -->
    {css}
  </head>
  <body style="margin:0;padding:0;background:#F7F8FA;color:#111827;
               font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;">
    
    <!-- Hidden preview text -->
    <div style="display:none;font-size:1px;color:#F7F8FA;line-height:1px;
               max-height:0px;max-width:0px;opacity:0;overflow:hidden;mso-hide:all;">
      {escape(email_preview)}
    </div>
    
    <!-- Main container -->
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
      <tr>
        <td align="center" class="outer-padding" style="padding:12px 8px;background:#F7F8FA;">
          <table role="presentation" width="640" cellpadding="0" cellspacing="0" 
                 style="border-collapse:collapse;width:640px;max-width:100%;">
            <tr>
              <td class="main-container" style="background:#FFFFFF;
                         border-radius:16px;
                         padding:20px;box-shadow:0 4px 12px rgba(0,0,0,0.08);">
                
                <!-- Header -->
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                  <tr><td style="text-align:center;">
                    <div class="responsive-title" style="font-weight:700;font-size:42px;color:#111827;
                                                        margin:0 0 10px 0;letter-spacing:-0.5px;
                                                        font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;">
                      Investment Edge
                    </div>
                    {f'<div class="header-subtitle" style="color:#6B7280;margin-bottom:16px;font-size:14px;font-weight:500;">📊 Data as of {escape(as_of)}</div>' if as_of else ''}
                    {market_summary}
                    {quality_note}
                  </td></tr>
                </table>

                <!-- Hero section -->
                {hero_html}
                
                <!-- Mover story section -->
                {mover_html}

                <!-- Content sections -->
                {''.join(sections)}

                <!-- Footer -->
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-top:1px solid #E5E7EB;margin-top:28px;">
                  <tr><td class="footer-text" style="text-align:center;padding:24px 16px;color:#6B7280;font-size:13px;">
                    <div style="margin-bottom:8px;font-weight:500;">
                      You're receiving this because you subscribed to Investment Edge
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
