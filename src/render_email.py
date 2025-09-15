from __future__ import annotations

from datetime import datetime, timezone, timedelta
from html import escape
from typing import Dict, List, Optional, Any, Iterable

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

# Use Central Time for "As of" timestamp
CENTRAL_TZ = ZoneInfo("America/Chicago") if ZoneInfo else None

# ---------------------------------------------------------------------------
# Helpers for parsing and formatting dates
# ---------------------------------------------------------------------------

def _parse_to_dt(value: Any) -> Optional[datetime]:
    """Parse a value into an aware datetime (UTC) if possible."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value or '').strip()
    if not s:
        return None
    # Epoch seconds or milliseconds
    if s.isdigit():
        try:
            iv = int(s)
            if iv > 10_000_000_000:  # milliseconds
                iv //= 1000
            return datetime.fromtimestamp(iv, tz=timezone.utc)
        except Exception:
            return None
    # ISO 8601
    try:
        s2 = s[:-1] + '+00:00' if s.endswith('Z') else s
        dt = datetime.fromisoformat(s2)
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    # RFC 2822
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(s)
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _fmt_ct(value: Any, force_time: Optional[bool] = None, tz_suffix_policy: str = 'auto') -> str:
    """Format a datetime-like value into US Central time.

    - If force_time is True, always include the time component.
    - If force_time is False, never include the time component.
    - If force_time is None (default), include the time component only
      if the datetime has a non-zero time portion.
    - tz_suffix_policy controls whether "CST" is appended: it can be
      'always', 'auto', or 'never'.
    """
    dt = _parse_to_dt(value) or value
    if not isinstance(dt, datetime):
        return str(value)
    try:
        dtc = dt.astimezone(CENTRAL_TZ) if CENTRAL_TZ else dt
    except Exception:
        dtc = dt
    has_time = not (dtc.hour == 0 and dtc.minute == 0 and dtc.second == 0)
    show_time = force_time if force_time is not None else has_time
    out = dtc.strftime('%m/%d/%Y %H:%M') if show_time else dtc.strftime('%m/%d/%Y')
    if tz_suffix_policy == 'always':
        return out + ' CST'
    if tz_suffix_policy == 'auto' and show_time:
        return out + ' CST'
    return out

# ---------------------------------------------------------------------------
# Utility helpers for rendering values
# ---------------------------------------------------------------------------

def _safe_float(x: Any, default: Optional[float] = None) -> Optional[float]:
    """Safely convert a value to float, returning default on failure or NaN."""
    try:
        v = float(x)
        if v != v or abs(v) > 1e10:
            return default
        return v
    except Exception:
        return default


def _chip(label: str, value: Any) -> str:
    """Render a colored chip for a change percentage or value - MODERATE PADDING."""
    v = _safe_float(value, None)
    if v is None:
        bg, color, sign, txt = '#6B7280', '#FFFFFF', '', '--'
    else:
        if v >= 0:
            bg, color, sign = '#10B981', '#FFFFFF', '▲'
        else:
            bg, color, sign = '#EF4444', '#FFFFFF', '▼'
        txt = f'{abs(v):.1f}%'
    # Moderate padding for good readability
    return (
        '<span style="background:' + bg + ';color:' + color + ';padding:4px 8px;'
        'border-radius:10px;font-size:12px;font-weight:700;display:inline-block;'
        'margin:2px 3px;white-space:nowrap;width:70px;text-align:center;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">'
        + escape(label) + ' ' + sign + txt + '</span>'
    )


def _chip_row(chip1: str, chip2: str) -> str:
    """Create a row with two chips side by side."""
    return '<div style="margin:2px 0;">' + chip1 + chip2 + '</div>'


def _index_pill(value: Any, prefix: str = '') -> str:
    """Render a colored pill for index changes - compact version."""
    v = _safe_float(value, None)
    if v is None:
        bg, color, sign, txt = '#6B7280', '#FFFFFF', '', '--'
    else:
        if v >= 0:
            bg, color, sign = '#10B981', '#FFFFFF', '▲'
        else:
            bg, color, sign = '#EF4444', '#FFFFFF', '▼'
        txt = f'{abs(v):.1f}%'
    
    return (
        '<span style="background:' + bg + ';color:' + color + ';padding:3px 7px;'
        'border-radius:8px;font-size:11px;font-weight:600;display:inline-block;'
        'margin:2px;white-space:nowrap;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">'
        + prefix + sign + txt + '</span>'
    )


# ---------------------------------------------------------------------------
# NEW: Daily Focus Section
# ---------------------------------------------------------------------------

def _get_daily_focus(assets: List[Dict[str, Any]], today: datetime = None) -> Optional[Dict[str, Any]]:
    """Determine the most important event for today."""
    if today is None:
        today = datetime.now(timezone.utc)
    
    focus_items = []
    
    # Check for earnings (would need earnings dates in asset data)
    for asset in assets:
        if asset.get('earnings_date'):
            earnings_dt = _parse_to_dt(asset['earnings_date'])
            if earnings_dt and earnings_dt.date() == today.date():
                focus_items.append({
                    'priority': 10,
                    'icon': '📊',
                    'title': f"{asset['symbol']} Earnings Today",
                    'detail': f"Reports {asset.get('earnings_timing', 'after close')}",
                    'action': 'Review analyst expectations'
                })
    
    # Check for major economic events (hardcoded for now, could be API-driven)
    economic_events = {
        # Format: 'YYYY-MM-DD': [events]
        '2025-01-15': {
            'icon': '📈',
            'title': 'CPI Inflation Data',
            'detail': '8:30 AM ET • Forecast: +0.3% MoM',
            'action': 'Watch commodity & growth stock positions',
            'priority': 8
        },
        '2025-01-29': {
            'icon': '🏛️',
            'title': 'FOMC Rate Decision',
            'detail': '2:00 PM ET • Expected: No Change',
            'action': 'Prepare for volatility in rate-sensitive sectors',
            'priority': 9
        },
    }
    
    today_str = today.strftime('%Y-%m-%d')
    if today_str in economic_events:
        focus_items.append(economic_events[today_str])
    
    # Pick highest priority item
    if focus_items:
        return max(focus_items, key=lambda x: x['priority'])
    
    # Default focus if nothing special today
    if not focus_items:
        # Market sentiment focus
        return {
            'icon': '📈',
            'title': 'Market Positioning',
            'detail': f"{today.strftime('%A')} Trading Session",
            'action': 'Monitor momentum indicators for entry points'
        }
    
    return None


def _render_daily_focus(focus: Dict[str, Any]) -> str:
    """Render the daily focus section."""
    if not focus:
        return ''
    
    return f'''
    <div style="background:linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%);
                border:2px solid #F59E0B;border-radius:12px;padding:14px;margin:12px 0;">
        <div style="font-size:11px;font-weight:700;color:#92400E;margin-bottom:6px;">
            📍 TODAY'S FOCUS
        </div>
        <div style="font-size:16px;font-weight:700;color:#111827;margin-bottom:4px;">
            {focus['icon']} {escape(focus['title'])}
        </div>
        <div style="font-size:13px;color:#451A03;margin-bottom:6px;">
            {escape(focus['detail'])}
        </div>
        <div style="font-size:12px;color:#78350F;font-style:italic;">
            <strong>Action:</strong> {escape(focus['action'])}
        </div>
    </div>
    '''


# ---------------------------------------------------------------------------
# NEW: Economic Calendar
# ---------------------------------------------------------------------------

def _get_economic_calendar(today: datetime = None) -> List[Dict[str, Any]]:
    """Get today's economic events. In production, this would call an API."""
    if today is None:
        today = datetime.now(timezone.utc)
    
    # Hardcoded calendar - in production, fetch from API
    calendar = {
        '2025-01-15': [
            {'time': '08:30', 'event': 'Core CPI', 'impact': 'High', 'forecast': '+0.3%', 'affects': ['commodity', 'crypto']},
            {'time': '08:30', 'event': 'Retail Sales', 'impact': 'Medium', 'forecast': '+0.5%', 'affects': ['equity']},
            {'time': '14:00', 'event': 'Beige Book', 'impact': 'Low', 'affects': ['equity']},
        ],
        '2025-01-16': [
            {'time': '08:30', 'event': 'Initial Jobless Claims', 'impact': 'Medium', 'forecast': '215K', 'affects': ['equity']},
            {'time': '08:30', 'event': 'Housing Starts', 'impact': 'Low', 'forecast': '1.35M', 'affects': ['commodity']},
        ],
        '2025-01-29': [
            {'time': '14:00', 'event': 'FOMC Decision', 'impact': 'High', 'forecast': '5.25-5.50%', 'affects': ['equity', 'crypto']},
            {'time': '14:30', 'event': 'Powell Press Conference', 'impact': 'High', 'affects': ['equity', 'crypto']},
        ],
    }
    
    today_str = today.strftime('%Y-%m-%d')
    return calendar.get(today_str, [])


def _render_economic_calendar(events: List[Dict[str, Any]], assets: List[Dict[str, Any]]) -> str:
    """Render the economic calendar section."""
    if not events:
        return ''
    
    html = '''
    <div style="background:#F0F9FF;border:1px solid #0284C7;border-radius:12px;padding:12px;margin:12px 0;">
        <div style="font-size:11px;font-weight:700;color:#075985;margin-bottom:8px;">
            📅 ECONOMIC CALENDAR
        </div>
    '''
    
    for event in events[:3]:  # Show top 3 events
        impact_color = '#DC2626' if event['impact'] == 'High' else '#F59E0B' if event['impact'] == 'Medium' else '#6B7280'
        
        # Find affected holdings
        affected_symbols = []
        if 'affects' in event:
            for category in event['affects']:
                affected_symbols.extend([
                    a['symbol'] for a in assets 
                    if a.get('category') == category
                ])
        
        html += f'''
        <div style="margin:8px 0;padding:8px;background:white;border-radius:8px;border-left:3px solid {impact_color};">
            <div style="font-size:13px;">
                <span style="color:{impact_color};font-weight:700;">{escape(event['time'])} ET</span>
                <span style="font-weight:600;color:#111827;"> • {escape(event['event'])}</span>
                {f' • {escape(event.get("forecast", ""))}' if event.get('forecast') else ''}
            </div>
            {f'<div style="font-size:11px;color:#6B7280;margin-top:2px;">Impact: {", ".join(affected_symbols[:5])}</div>' if affected_symbols else ''}
        </div>
        '''
    
    html += '</div>'
    return html


# ---------------------------------------------------------------------------
# NEW: Momentum Indicators
# ---------------------------------------------------------------------------

def _render_momentum_badge(momentum: Dict[str, Any]) -> str:
    """Render momentum indicators as a badge."""
    if not momentum:
        return ''
    
    html = '<div style="margin:8px 0;padding:6px;background:#F3F4F6;border-radius:8px;">'
    
    # Momentum streak
    if 'momentum' in momentum:
        color = momentum.get('momentum_color', '#6B7280')
        html += f'''
        <span style="background:{color};color:white;padding:3px 8px;border-radius:6px;
                     font-size:11px;font-weight:600;margin-right:6px;">
            {escape(momentum['momentum'])}
        </span>
        '''
    
    # RSI indicator
    if 'rsi_signal' in momentum and momentum['rsi_signal']:
        html += f'''
        <span style="background:#FEF3C7;color:#92400E;padding:3px 8px;border-radius:6px;
                     font-size:11px;font-weight:600;margin-right:6px;">
            RSI: {momentum.get('rsi', 'N/A')} {escape(momentum['rsi_signal'])}
        </span>
        '''
    
    # Volume alert
    if 'volume_alert' in momentum:
        html += f'''
        <span style="background:#DBEAFE;color:#1E40AF;padding:3px 8px;border-radius:6px;
                     font-size:11px;font-weight:600;">
            {escape(momentum['volume_alert'])}
        </span>
        '''
    
    html += '</div>'
    return html


# Mapping of category codes to human-readable names
SECTION_NAMES: Dict[str, str] = {
    'etf_index': 'Market Indices',
    'equity':    'Equities',
    'commodity': 'Commodities',
    'crypto':    'Digital Assets',
}

# Index symbol to abbreviation mapping
INDEX_ABBREVIATIONS: Dict[str, str] = {
    '^DJI': 'DOW',
    '^GSPC': 'S&P',
    '^IXIC': 'NAS',
    '^RUT': 'R2K',
}

# Color and style definitions for each section and card - UPDATED FOR CONSISTENT BACKGROUNDS
SECTION_STYLES: Dict[str, Dict[str, str]] = {
    'equity': {
        'border': '#3B82F6', 'bg': '#FFFFFF', 'shadow': 'rgba(59,130,246,0.06)',
        'card_border': '#93C5FD', 'card_bg': '#93C5FD', 'card_shadow': 'rgba(147,197,253,0.15)',
        'tag_bg': '#111827', 'tag_color': '#FFFFFF',
    },
    'crypto': {
        'border': '#8B5CF6', 'bg': '#FFFFFF', 'shadow': 'rgba(139,92,246,0.06)',
        'card_border': '#C4B5FD', 'card_bg': '#C4B5FD', 'card_shadow': 'rgba(196,181,253,0.15)',
        'tag_bg': '#111827', 'tag_color': '#FFFFFF',
    },
    'etf_index': {
        'border': '#10B981', 'bg': '#FFFFFF', 'shadow': 'rgba(16,185,129,0.06)',
        'card_border': '#70d5b3', 'card_bg': '#70d5b3', 'card_shadow': 'rgba(112,213,179,0.15)',
        'tag_bg': '#111827', 'tag_color': '#FFFFFF',
    },
    'commodity': {
        'border': '#F59E0B', 'bg': '#FFFFFF', 'shadow': 'rgba(245,158,11,0.06)',
        'card_border': '#f9c56d', 'card_bg': '#f9c56d', 'card_shadow': 'rgba(249,197,109,0.15)',
        'tag_bg': '#111827', 'tag_color': '#FFFFFF',
    },
}


def _range_bar(pos: float, low: float, high: float) -> str:
    """Render a horizontal bar representing a 52‑week range."""
    try:
        p = max(0.0, min(100.0, float(pos)))
    except Exception:
        p = 50.0
    return (
        '<div style="height:6px;border-radius:3px;background:#E5E7EB;position:relative;margin:8px 0;">'
        + f'<div style="width:{p:.1f}%;height:6px;border-radius:3px;background:#10B981;"></div></div>'
    )


def _button(label: str, url: str, secondary: bool = False) -> str:
    """Render a call-to-action button - MODERATE SIZE."""
    bg = '#4B5563' if not secondary else '#9CA3AF'
    color = '#FFFFFF'
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        'style="display:inline-block;margin-right:6px;margin-bottom:3px;">'
        '<tr><td style="background:' + bg + ';color:' + color + ';border-radius:9px;'
        'font-size:12px;font-weight:600;padding:8px 12px;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">'
        '<a href="' + escape(url or '#') + '" target="_blank" rel="noopener noreferrer" '
        'style="color:' + color + ';text-decoration:none;display:block;">'
        + escape(label) + ' →</a></td></tr></table>'
    )


def _generate_dynamic_header(summary: Dict[str, Any], assets: List[Dict[str, Any]]) -> tuple:
    """Generate a dynamic header based on the day's content."""
    up_count = summary.get('up_count', 0)
    down_count = summary.get('down_count', 0)
    total = up_count + down_count
    
    # Find the biggest mover (excluding indices)
    biggest_mover = None
    biggest_change = 0
    for asset in assets:
        # Skip indices for biggest mover calculation
        if asset.get('category') == 'etf_index':
            continue
        pct = _safe_float(asset.get('pct_1d'), 0)
        if abs(pct) > abs(biggest_change):
            biggest_change = pct
            biggest_mover = asset
    
    # Check for breaking news
    has_breaking = len(summary.get('heroes_breaking', [])) > 0
    
    # Generate dynamic title and subtitle based on market conditions
    if total > 0:
        up_pct = (up_count / total) * 100
        
        if has_breaking:
            title = "📰 Breaking News & Market Update"
            subtitle = f"Critical developments impacting your portfolio"
        elif up_pct >= 70:
            if biggest_change > 10:
                title = "🚀 Portfolio Surge Alert"
                subtitle = f"Strong gains across holdings • {up_count} advancing, {down_count} declining"
            else:
                title = "📈 Markets Trending Higher"
                subtitle = f"Broad strength with {up_count} positions advancing"
        elif up_pct <= 30:
            if biggest_change < -10:
                title = "⚠️ Market Pressure Alert"
                subtitle = f"Significant declines detected • {down_count} falling, {up_count} rising"
            else:
                title = "📉 Risk-Off Session"
                subtitle = f"Defensive positioning with {down_count} positions declining"
        else:
            title = "⚖️ Mixed Market Signals"
            subtitle = f"Balanced movement • {up_count} up, {down_count} down"
        
        # Add biggest mover info if significant
        if biggest_mover and abs(biggest_change) > 5:
            # Use commodity display name if available
            if biggest_mover.get('commodity_display_name'):
                name = biggest_mover.get('commodity_display_name')
            else:
                name = biggest_mover.get('name', 'Unknown')
            ticker = biggest_mover.get('ticker', '')
            if biggest_change > 0:
                subtitle += f" • {name} leads +{abs(biggest_change):.1f}%"
            else:
                subtitle += f" • {name} down {abs(biggest_change):.1f}%"
    else:
        title = "Intelligence Digest"
        subtitle = "Your daily portfolio intelligence report"
    
    return title, subtitle


# ---------------------------------------------------------------------------
# Market Indices Bar (FIXED for proper mobile 2x2 wrapping)
# ---------------------------------------------------------------------------

def _render_indices_bar(indices: List[Dict[str, Any]]) -> str:
    """Render market indices with individual containers and proper mobile wrapping."""
    if not indices:
        return ''
    
    index_cells = []
    for idx in indices[:4]:  # Limit to 4 indices
        symbol = idx.get('symbol', '')
        abbrev = INDEX_ABBREVIATIONS.get(symbol, symbol)
        
        price_v = _safe_float(idx.get('price'), None)
        if price_v is None:
            price_fmt = '--'
        else:
            # Format with commas
            price_fmt = f'{price_v:,.2f}'
        
        pct_1d = idx.get('pct_1d')
        pct_ytd = idx.get('pct_ytd')
        
        # Create pills for D/D and YTD
        dd_pill = _index_pill(pct_1d)
        ytd_pill = _index_pill(pct_ytd, 'YTD ')
        
        # Build each index with class for mobile targeting
        cell_html = (
            '<div class="index-cell-wrapper" style="display:inline-block;width:23%;vertical-align:top;margin:0 0.5%;">'
            '<div class="index-cell-inner" style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:10px;'
            'padding:8px 4px;text-align:center;box-sizing:border-box;'
            'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">'
            '<div style="font-weight:700;font-size:13px;color:#111827;margin-bottom:4px;">'
            + escape(abbrev) + '</div>'
            '<div style="font-size:14px;color:#111827;font-weight:600;margin-bottom:4px;">'
            + escape(price_fmt) + '</div>'
            '<div style="white-space:nowrap;">' + dd_pill + '</div>'
            '<div style="white-space:nowrap;">' + ytd_pill + '</div>'
            '</div></div>'
        )
        
        index_cells.append(cell_html)
    
    # Create the indices bar with wrapper for mobile control
    indices_bar = (
        '<div class="indices-container" style="text-align:center;margin:12px 0 18px 0;font-size:0;white-space:nowrap;">'
        + ''.join(index_cells) +
        '</div>'
    )
    
    return indices_bar


# ---------------------------------------------------------------------------
# Heroes rendering
# ---------------------------------------------------------------------------

def _render_heroes(heroes: Iterable[Dict[str, Any]]) -> str:
    """Render hero cards for breaking and section news - MODERATE PADDING."""
    out_parts: List[str] = []
    for i, h in enumerate(heroes):
        title = (h.get('title') or '').strip()
        if not title:
            continue
        url = h.get('url') or '#'
        src = h.get('source') or ''
        when = _fmt_ct(h.get('when'), force_time=False, tz_suffix_policy='never') if h.get('when') else ''
        desc = (h.get('description') or '').strip()
        label = '● BREAKING' if i == 0 else '● ALSO BREAKING'
        # Truncate description gracefully
        if len(desc) > 180:
            import re
            sentences = re.split(r'[.!?]\s+', desc)
            truncated = ''
            for s in sentences:
                if len(truncated + s) <= 160:
                    truncated += s + '. '
                else:
                    break
            desc = truncated.strip() if truncated else (desc[:177] + '…')
        meta_bits = [b for b in [src, when] if b]
        meta = ' • '.join(meta_bits)
        # Build card HTML with moderate padding
        card = (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="border-collapse:separate;margin:0 0 10px;">'
            '<tr><td style="border:1px solid #E5E7EB;border-radius:11px;overflow:hidden;">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FFFFFF;">'
            '<tr><td style="padding:14px 12px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">'
            '<div style="font-size:11px;color:#6B7280;font-weight:700;margin-bottom:5px;">' + label + '</div>'
            '<a href="' + escape(url) + '" style="text-decoration:none;color:#111827;">'
            '<div style="font-size:19px;font-weight:800;line-height:1.2;margin-bottom:7px;">'
            + escape(title) + '</div></a>'
            + ('<div style="font-size:13px;color:#374151;margin-bottom:7px;line-height:1.45;">' + escape(desc) + '</div>' if desc else '')
            + ('<div style="font-size:11px;color:#6B7280;">' + escape(meta) + '</div>' if meta else '')
            + '</td></tr></table></td></tr></table>'
        )
        out_parts.append(card)
    return ''.join(out_parts)


# ---------------------------------------------------------------------------
# Card rendering (UPDATED with momentum indicators)
# ---------------------------------------------------------------------------

def _card_shell(inner: str, section: str) -> str:
    """Wrap the inner HTML in a card container with moderate margins."""
    style = SECTION_STYLES.get(section, SECTION_STYLES['equity'])
    return (
        '<div style="border:1px solid ' + style['card_border'] + ';border-radius:13px;margin:0 0 10px;'
        'box-shadow:0 2px 7px ' + style['card_shadow'] + ';background:' + style['card_bg'] + ';">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:separate;margin:0;background:#FFFFFF;border-radius:12px;overflow:hidden;">'
        + inner + '</table></div>'
    )


def _build_asset_card(c: Dict[str, Any]) -> str:
    """Build a complete HTML card for a given asset - WITH MOMENTUM INDICATORS."""
    section = (c.get('category') or 'equity').lower()
    ticker = str(c.get('ticker') or c.get('symbol') or '')
    name = c.get('name') or ticker or 'Unknown'
    industry = c.get('industry') or ''
    
    price_v = _safe_float(c.get('price'), None)
    
    # Handle commodity-specific display
    if section == 'commodity' and c.get('commodity_unit'):
        unit = c.get('commodity_unit')
        display_name = c.get('commodity_display_name') or name
        
        if price_v is None:
            price_fmt = '<span style="color:#9CA3AF;">--</span>'
        else:
            # Format price with unit (e.g., "$1,850.50/oz" for gold)
            price_fmt = f'<span style="color:#111827;font-weight:700;">${price_v:,.2f}/{unit}</span>'
        
        # Use commodity name instead of ETF name
        name = display_name
        ticker_display = f'({ticker})'  # Just show ETF ticker for reference
    else:
        # Standard price display for stocks/ETFs/crypto
        if price_v is None:
            price_fmt = '<span style="color:#9CA3AF;">--</span>'
        else:
            price_fmt = '<span style="color:#111827;font-weight:700;">${:,.2f}</span>'.format(price_v)
        
        # Build ticker display with industry for equity section
        if section == 'equity' and industry:
            ticker_display = '(' + escape(ticker) + ') ' + escape(industry)
        else:
            ticker_display = '(' + escape(ticker) + ')'
    
    # Create 2x2 chip layout
    chip_1d = _chip('1D', c.get('pct_1d'))
    chip_1w = _chip('1W', c.get('pct_1w'))
    chip_1m = _chip('1M', c.get('pct_1m'))
    chip_ytd = _chip('YTD', c.get('pct_ytd'))
    
    chips_html = (
        '<div style="margin:8px 0;">'
        + _chip_row(chip_1d, chip_1w)
        + _chip_row(chip_1m, chip_ytd)
        + '</div>'
    )
    
    # Add momentum indicators if present
    momentum_html = _render_momentum_badge(c.get('momentum', {}))
    
    range_html = _range_bar(c.get('range_pct') or 50.0, c.get('low_52w') or 0.0, c.get('high_52w') or 0.0)
    bullets_html = ''
    headline = c.get('headline')
    source = c.get('source')
    when_fmt = _fmt_ct(c.get('when'), force_time=False, tz_suffix_policy='never') if c.get('when') else None
    
    if headline:
        display = headline if len(headline) <= 100 else (headline[:100] + '…')
        meta = ' • '.join([x for x in [source, when_fmt] if x])
        bullets_html = (
            '<tr><td style="padding-bottom:8px;line-height:1.45;color:#374151;'
            'font-size:13px;font-weight:500;">★ ' + escape(display) +
            ((' (' + escape(meta) + ')') if meta else '') + '</td></tr>'
        )
    
    # Compose the inner structure with moderate padding
    inner = (
        '<tr><td style="padding:16px 14px;max-height:400px;overflow:hidden;vertical-align:top;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td style="font-weight:700;font-size:16px;line-height:1.25;color:#111827;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;padding-bottom:4px;">'
        + escape(name) + '</td></tr>'
        '<tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        '<td style="font-size:12px;color:#6B7280;font-weight:600;">' + ticker_display + '</td>'
        '<td style="text-align:right;font-size:15px;">' + price_fmt + '</td>'
        '</tr></table></td></tr>'
        '<tr><td>' + chips_html + '</td></tr>'
        + (f'<tr><td>{momentum_html}</td></tr>' if momentum_html else '')
        + '<tr><td>' + range_html + '</td></tr>'
        + bullets_html +
        '<tr><td style="border-top:1px solid #E5E7EB;padding-top:10px;">'
        + _button('News', c.get('news_url') or f'https://finance.yahoo.com/quote/{escape(ticker)}/news')
        + _button('Press', c.get('pr_url') or f'https://finance.yahoo.com/quote/{escape(ticker)}/press-releases', secondary=True)
        + '</td></tr>'
        '</table></td></tr>'
    )
    return _card_shell(inner, section)


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def _grid(cards: List[str]) -> str:
    """Arrange cards into a responsive two-column grid - MODERATE GAP."""
    if not cards:
        return ''
    rows: List[str] = []
    for i in range(0, len(cards), 2):
        left = cards[i]
        right = cards[i + 1] if i + 1 < len(cards) else ''
        if right:
            # Moderate padding between columns
            rows.append(
                '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                'style="border-collapse:collapse;margin-bottom:6px;">'
                '<tr><td class="stack-col" width="50%" style="vertical-align:top;padding-right:5px;">' + left + '</td>'
                '<td class="stack-col" width="50%" style="vertical-align:top;padding-left:5px;">' + right + '</td></tr></table>'
            )
        else:
            rows.append(
                '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                'style="border-collapse:collapse;margin-bottom:6px;">'
                '<tr><td class="stack-col" style="vertical-align:top;margin:0 auto;">' + left + '</td></tr></table>'
            )
    return ''.join(rows)


def _section_container(title: str, inner_html: str, section_type: str) -> str:
    """Wrap section content in a container - WHITE BACKGROUND WITH LEFT BORDER."""
    style = SECTION_STYLES.get(section_type, SECTION_STYLES['equity'])
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;background:' + style['bg'] + ';'
        'border-left:4px solid ' + style['border'] + ';border-radius:14px;margin:18px 0;'
        'box-shadow:0 1px 5px ' + style['shadow'] + ';"><tr><td style="padding:20px 14px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td class="section-title" style="font-weight:700;font-size:26px;color:#111827;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:0 0 20px 0;padding-bottom:8px;">'
        + escape(title) + '</td></tr><tr><td>' + inner_html + '</td></tr></table>'
        '</td></tr></table>'
    )


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

def _normalize_inputs(*args: Any, **kwargs: Any) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Normalize inputs for ``render_email`` to support both current and legacy call signatures.

    The newsletter renderer has historically accepted a variety of parameter
    permutations. This helper inspects the positional and keyword arguments and
    produces a canonical ``(summary, assets)`` tuple where ``summary`` is a
    dictionary (empty by default) and ``assets`` is a list of asset
    dictionaries. It aims to be tolerant of misordered or missing inputs so
    that callers using older patterns do not cause attribute errors in the
    renderer.

    The following call patterns are supported:

    1. ``render_email(summary, assets)`` – the modern signature where ``summary``
       is a dict containing metadata (e.g., heroes) and ``assets`` is a list of
       asset dictionaries. Both positional arguments are required.
    2. ``render_email(summary, companies, cryptos=cryptos)`` – an intermediate
       form where ``companies`` and ``cryptos`` are separate lists. These lists
       are concatenated to form the unified ``assets`` list.
    3. ``render_email(companies, cryptos)`` – the oldest signature where the
       first two positional arguments are asset lists and no summary is
       provided. An optional ``summary`` keyword argument can supply the
       summary dict.
    4. ``render_email(companies)`` – an abbreviated form with a single asset
       list and no summary.

    Any additional positional arguments that are lists will be appended to the
    assets collection. The ``summary`` keyword argument, if provided and a
    dictionary, overrides any summary detected from positional arguments.

    Args:
        *args: Positional arguments which may include a summary dict and/or
            one or more lists of asset dictionaries.
        **kwargs: Keyword arguments which may include ``cryptos`` (a list of
            asset dictionaries) and/or ``summary`` (a dict).

    Returns:
        A tuple ``(summary, assets)`` where ``summary`` is a dict and
        ``assets`` is a list.
    """
    summary: Dict[str, Any] = {}
    assets: List[Dict[str, Any]] = []

    # First, check if a summary is supplied via kwargs. If present and valid,
    # this takes precedence over positional detection for summary.
    summary_kw = kwargs.get('summary')
    if isinstance(summary_kw, dict):
        summary = summary_kw

    # Iterate over positional arguments. If an argument is a dict and we
    # haven't already set a summary from kwargs, treat it as the summary. If
    # it's a list, extend the assets list. Other types are ignored.
    for arg in args:
        if isinstance(arg, dict) and not summary:
            summary = arg
        elif isinstance(arg, list):
            assets.extend(list(arg))

    # If a ``cryptos`` keyword is present and is a list, append its contents
    # to the assets list. This supports legacy calls where companies and
    # cryptos were passed separately.
    cryptos_kw = kwargs.get('cryptos')
    if isinstance(cryptos_kw, list):
        assets.extend(list(cryptos_kw))

    # Ensure summary is at least an empty dict
    if not isinstance(summary, dict):
        summary = {}

    return summary, assets


def render_email(*args: Any, **kwargs: Any) -> str:
    """
    Render the full email HTML with dynamic header and clean section styling.

    This function supports both the new signature (`render_email(summary, assets)`) and
    legacy signatures (`render_email(summary, companies, cryptos=cryptos)` and
    `render_email(companies, cryptos, summary=summary)`). It normalizes the
    inputs via `_normalize_inputs` to ensure compatibility across different
    call patterns.

    Arguments:
        *args: Positional arguments for summary and asset lists.
        **kwargs: Keyword arguments which may include `cryptos` or `summary`.

    Returns:
        A string containing the fully rendered HTML email.
    """
    summary, assets = _normalize_inputs(*args, **kwargs)
    
    # Separate indices from other assets
    indices = []
    other_assets = []
    
    for a in assets:
        sec = (a.get('category') or 'equity').lower()
        if sec == 'etf_index':
            indices.append(a)
        else:
            other_assets.append(a)
    
    # Group remaining assets by category (preserving order)
    by_section: Dict[str, List[Dict[str, Any]]] = {'equity': [], 'commodity': [], 'crypto': []}
    for a in other_assets:
        sec = (a.get('category') or 'equity').lower()
        if sec not in by_section:
            by_section[sec] = []
        by_section[sec].append(a)
    
    # Generate dynamic header (using other_assets to exclude indices from calculations)
    header_title, header_subtitle = _generate_dynamic_header(summary, other_assets)
    
    # NEW: Get daily focus and economic calendar
    today = datetime.now(timezone.utc)
    daily_focus = _get_daily_focus(other_assets, today)
    economic_events = _get_economic_calendar(today)
    
    # Render indices bar
    indices_html = _render_indices_bar(indices)
    
    # NEW: Render daily focus section
    daily_focus_html = _render_daily_focus(daily_focus)
    
    # NEW: Render economic calendar
    economic_calendar_html = _render_economic_calendar(economic_events, other_assets)
    
    # Render breaking news heroes (up to 2)
    breaking_html = _render_heroes(summary.get('heroes_breaking', []) or [])
    
    # Render each section: heroes then cards (COMMODITIES MOVED TO END)
    section_html_parts: List[str] = []
    for sec in ['equity', 'crypto', 'commodity']:  # Changed order - commodity last
        if not by_section.get(sec):
            continue
        sec_heroes = (summary.get('heroes_by_section', {}).get(sec) or [])[:3]
        sec_html = _render_heroes(sec_heroes) + _grid([_build_asset_card(x) for x in by_section[sec]])
        section_html_parts.append(_section_container(SECTION_NAMES.get(sec, sec.title()), sec_html, sec))
    
    # Compose final HTML
    as_of = _fmt_ct(summary.get('as_of_ct'), force_time=True, tz_suffix_policy='always')
    
    # Enhanced responsive CSS with PROPERLY FIXED indices 2x2 mobile layout
    css = (
        '<style>'
        '@media only screen and (max-width: 640px) {'
        '.stack-col{display:block!important;width:100%!important;max-width:100%!important;padding:0!important;margin-bottom:12px}'
        '.section-title{font-size:24px!important;line-height:1.15!important}'
        '.chip{font-size:11px!important;padding:3px 6px!important;margin:2px!important}'
        '.section-container td{padding:14px 8px!important}'
        '.outer-padding{padding:8px 4px!important}'
        '.main-container{padding:12px 8px!important;background:#FFFFFF!important}'
        '/* Indices bar mobile 2x2 grid - FORCE WRAPPING */'
        '.indices-container{white-space:normal!important}'
        '.index-cell-wrapper{width:47%!important;display:inline-block!important;vertical-align:top!important;margin:1%!important}'
        '}'
        '</style>'
    )
    
    # Main email with dynamic header and indices bar at top
    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        + css + '<title>' + escape(header_title) + '</title></head>'
        '<body style="margin:0;padding:0;background:#F9FAFB;"><center style="width:100%;background:#F9FAFB;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" width="600" '
        'style="margin:0 auto;background:#FFFFFF;border-radius:14px;overflow:hidden;">'
        '<tr><td style="padding:18px 14px 10px 14px;text-align:left;">'
        '<div style="font-size:27px;font-weight:700;color:#111827;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">' + escape(header_title) + '</div>'
        '<div style="font-size:13px;color:#6B7280;margin-top:3px;">' + escape(header_subtitle) + '</div>'
        '<div style="font-size:11px;color:#9CA3AF;margin-top:6px;">As of ' + escape(as_of) + '</div>'
        '</td></tr>'
        '<tr><td style="padding:0 14px;">' + indices_html + '</td></tr>'
        '<tr><td style="padding:0 14px;">' + daily_focus_html + '</td></tr>'
        '<tr><td style="padding:0 14px;">' + economic_calendar_html + '</td></tr>'
        '<tr><td style="padding:0 14px;">' + breaking_html + '</td></tr>'
        '<tr><td style="padding:0 14px;">' + ''.join(section_html_parts) + '</td></tr>'
        '<tr><td style="padding:16px;color:#6B7280;font-size:11px;text-align:center;">You are receiving this digest based on your watchlist.</td></tr>'
        '</table></center></body></html>'
    )
