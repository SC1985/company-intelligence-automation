#!/usr/bin/env python3
"""
Investment Edge Email Renderer - Complete Implementation
Renders the newsletter with new layout and categorized sections
"""

from datetime import datetime
from typing import Dict, List, Any

def render_email(data: Dict) -> str:
    """Main function to render the complete email HTML"""
    
    # Extract data
    assets = data.get('assets', [])
    categorized_heroes = data.get('categorized_heroes', {})
    top_movers = data.get('top_movers', [])
    
    # Group assets by class
    assets_by_class = {
        'etf': [],
        'equity': [],
        'commodity': [],
        'crypto': []
    }
    
    for asset in assets:
        asset_class = asset.get('asset_class', 'equity').lower()
        if asset_class in assets_by_class:
            assets_by_class[asset_class].append(asset)
    
    # Build the email sections in the new order
    html_parts = []
    
    # 1. Email header
    html_parts.append(_render_header())
    
    # 2. Breaking News Section (1-2 articles from any category)
    if categorized_heroes.get('breaking'):
        html_parts.append(_render_breaking_news_section(categorized_heroes['breaking']))
    
    # 3. ETFs & Indices Section
    if assets_by_class['etf'] or categorized_heroes.get('etf'):
        html_parts.append(_render_etf_section(
            assets_by_class['etf'], 
            categorized_heroes.get('etf', [])
        ))
    
    # 4. Equities Section
    if assets_by_class['equity'] or categorized_heroes.get('equity'):
        html_parts.append(_render_equity_section(
            assets_by_class['equity'],
            categorized_heroes.get('equity', [])
        ))
    
    # 5. Commodities Section
    if assets_by_class['commodity'] or categorized_heroes.get('commodity'):
        html_parts.append(_render_commodity_section(
            assets_by_class['commodity'],
            categorized_heroes.get('commodity', [])
        ))
    
    # 6. Digital Assets Section
    if assets_by_class['crypto'] or categorized_heroes.get('crypto'):
        html_parts.append(_render_crypto_section(
            assets_by_class['crypto'],
            categorized_heroes.get('crypto', [])
        ))
    
    # 7. Top Movers Section
    if top_movers:
        html_parts.append(_render_top_movers(top_movers))
    
    # 8. Footer
    html_parts.append(_render_footer())
    
    # Combine all parts
    return _wrap_in_email_template(''.join(html_parts))

def _wrap_in_email_template(content: str) -> str:
    """Wrap content in email HTML template"""
    
    # Extract first hero headline for preview
    hero_headline = ""
    if "font-size:22px" in content and "<a" in content:
        import re
        match = re.search(r'<a[^>]*>(.*?)</a>', content)
        if match:
            hero_headline = match.group(1)[:100]
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Investment Edge - Daily Intelligence</title>
    <!--[if mso]>
    <noscript>
        <xml>
            <o:OfficeDocumentSettings>
                <o:PixelsPerInch>96</o:PixelsPerInch>
            </o:OfficeDocumentSettings>
        </xml>
    </noscript>
    <![endif]-->
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <!-- Hero headline for subject line extraction -->
    <!-- HERO_HEADLINE:{hero_headline} -->
    
    <!-- Preview text -->
    <div style="display:none;font-size:1px;color:#f3f4f6;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">
        {hero_headline if hero_headline else "Today's Investment Edge: Market insights, portfolio updates & strategic opportunities"}
    </div>
    
    <!-- Main container -->
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f3f4f6;">
        <tr>
            <td align="center" style="padding: 20px 0;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 8px; overflow: hidden;">
                    <tr>
                        <td style="padding: 0;">
                            {content}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""
    
    return html

def _render_header() -> str:
    """Render email header"""
    current_date = datetime.now().strftime("%B %d, %Y")
    current_time = datetime.now().strftime("%I:%M %p")
    
    return f"""
    <!-- Header -->
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
        <tr>
            <td style="padding: 32px 24px; text-align: center;">
                <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">
                    ⚡ Investment Edge
                </h1>
                <p style="margin: 8px 0 0; color: #e0e7ff; font-size: 14px;">
                    Daily Intelligence • {current_date} • {current_time}
                </p>
            </td>
        </tr>
    </table>
    
    <!-- Content container -->
    <div style="padding: 24px;">
    """

def _render_footer() -> str:
    """Render email footer"""
    return """
    </div>
    
    <!-- Footer -->
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #1f2937; margin-top: 32px;">
        <tr>
            <td style="padding: 24px; text-align: center;">
                <p style="margin: 0; color: #9ca3af; font-size: 12px;">
                    Investment Edge • Powered by Advanced Market Intelligence
                </p>
                <p style="margin: 8px 0 0; color: #6b7280; font-size: 11px;">
                    This email contains financial information for educational purposes only.
                    Not investment advice.
                </p>
            </td>
        </tr>
    </table>
    """

def _render_breaking_news_section(articles: List[Dict]) -> str:
    """Render the breaking news section"""
    if not articles:
        return ''
    
    return f"""
    <div style="margin-bottom: 32px;">
        <h2 style="color: #1f2937; font-size: 24px; font-weight: 700; margin: 0 0 16px 0;">
            📰 Breaking News
        </h2>
        {_render_heroes(articles)}
    </div>
    """

def _render_etf_section(etfs: List[Dict], hero_articles: List[Dict]) -> str:
    """Render ETFs & Indices section with green theme"""
    if not etfs and not hero_articles:
        return ''
    
    html = ["""
    <div style="margin-bottom: 32px;">
        <h2 style="color: #1f2937; font-size: 24px; font-weight: 700; margin: 0 0 16px 0;">
            📊 ETFs & Indices
        </h2>
    """]
    
    if hero_articles:
        html.append(_render_heroes(hero_articles))
    
    if etfs:
        for etf in etfs:
            html.append(_build_card(etf, border_color='#10b981'))
    
    html.append('</div>')
    return ''.join(html)

def _render_equity_section(equities: List[Dict], hero_articles: List[Dict]) -> str:
    """Render Equities section with blue theme and industry tags"""
    if not equities and not hero_articles:
        return ''
    
    html = ["""
    <div style="margin-bottom: 32px;">
        <h2 style="color: #1f2937; font-size: 24px; font-weight: 700; margin: 0 0 16px 0;">
            📈 Equities
        </h2>
    """]
    
    if hero_articles:
        html.append(_render_heroes(hero_articles))
    
    if equities:
        for equity in equities:
            html.append(_build_equity_card_with_industry(equity))
    
    html.append('</div>')
    return ''.join(html)

def _render_commodity_section(commodities: List[Dict], hero_articles: List[Dict]) -> str:
    """Render Commodities section with gold theme"""
    if not commodities and not hero_articles:
        return ''
    
    html = ["""
    <div style="margin-bottom: 32px;">
        <h2 style="color: #1f2937; font-size: 24px; font-weight: 700; margin: 0 0 16px 0;">
            🏆 Commodities
        </h2>
    """]
    
    if hero_articles:
        html.append(_render_heroes(hero_articles))
    
    if commodities:
        for commodity in commodities:
            html.append(_build_card(commodity, border_color='#f59e0b'))
    
    html.append('</div>')
    return ''.join(html)

def _render_crypto_section(cryptos: List[Dict], hero_articles: List[Dict]) -> str:
    """Render Digital Assets section with purple theme"""
    if not cryptos and not hero_articles:
        return ''
    
    html = ["""
    <div style="margin-bottom: 32px;">
        <h2 style="color: #1f2937; font-size: 24px; font-weight: 700; margin: 0 0 16px 0;">
            🪙 Digital Assets
        </h2>
    """]
    
    if hero_articles:
        html.append(_render_heroes(hero_articles))
    
    if cryptos:
        for crypto in cryptos:
            html.append(_build_crypto_card(crypto))
    
    html.append('</div>')
    return ''.join(html)

def _render_heroes(articles: List[Dict]) -> str:
    """Render hero articles"""
    if not articles:
        return ''
    
    html = []
    for article in articles[:3]:  # Max 3 hero articles per section
        title = article.get('title', 'Untitled')
        description = article.get('description', '')
        url = article.get('url', '#')
        source = article.get('source', 'News')
        
        # Truncate if too long
        if len(title) > 100:
            title = title[:97] + '...'
        if len(description) > 200:
            description = description[:197] + '...'
        
        html.append(f"""
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" 
               style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%); 
                      border-radius: 8px; margin-bottom: 16px; overflow: hidden;">
            <tr>
                <td style="padding: 16px;">
                    <div style="font-weight: 700; font-size: 18px; margin-bottom: 8px;">
                        <a href="{url}" style="color: #ffffff; text-decoration: none;">
                            {title}
                        </a>
                    </div>
                    {f'<div style="color: #d1d5db; font-size: 14px; line-height: 1.5; margin-bottom: 8px;">{description}</div>' if description else ''}
                    <div style="color: #9ca3af; font-size: 12px;">
                        <span style="font-weight: 500;">{source}</span>
                    </div>
                </td>
            </tr>
        </table>
        """)
    
    return ''.join(html)

def _build_equity_card_with_industry(data: Dict) -> str:
    """Build equity card with industry tag"""
    card_html = _build_card(data, border_color='#3b82f6')
    
    # Add industry tag if present
    if data.get('industry'):
        industry_tag = f"""
        <span style="display: inline-block; background-color: #eef2ff; color: #4f46e5; 
                     padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;
                     margin-left: 8px;">
            {data['industry']}
        </span>
        """
        # Insert after symbol
        card_html = card_html.replace('</h3>', f'{industry_tag}</h3>', 1)
    
    return card_html

def _build_card(data: Dict, border_color: str = '#3b82f6') -> str:
    """Build asset card with specified border color"""
    symbol = data.get('symbol', 'N/A')
    name = data.get('name', '')
    price = data.get('price', 0)
    change = data.get('change', 0)
    change_percent = data.get('change_percent', 0)
    volume = data.get('volume', 0)
    
    # Determine colors
    change_color = '#10b981' if change >= 0 else '#ef4444'
    change_symbol = '+' if change >= 0 else ''
    arrow = '▲' if change >= 0 else '▼'
    
    # Format volume
    if volume > 1000000:
        volume_str = f"{volume/1000000:.1f}M"
    elif volume > 1000:
        volume_str = f"{volume/1000:.0f}K"
    else:
        volume_str = str(volume)
    
    # Get news bullets
    news_html = ""
    news_items = data.get('news', [])[:2]  # Max 2 news items
    if news_items:
        news_bullets = []
        for news in news_items:
            title = news.get('title', '')
            if title and len(title) > 80:
                title = title[:77] + '...'
            if title:
                news_bullets.append(f"""
                <div style="margin: 4px 0; padding-left: 16px; position: relative;">
                    <span style="position: absolute; left: 0; color: {border_color};">•</span>
                    <span style="color: #6b7280; font-size: 13px;">{title}</span>
                </div>
                """)
        if news_bullets:
            news_html = f"""
            <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #e5e7eb;">
                <div style="font-size: 12px; font-weight: 600; color: #6b7280; margin-bottom: 8px;">
                    Latest News
                </div>
                {''.join(news_bullets)}
            </div>
            """
    
    return f"""
    <div style="background: white; border-radius: 8px; padding: 20px; margin-bottom: 16px;
                border-left: 4px solid {border_color}; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        
        <!-- Header with price -->
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
            <div>
                <h3 style="margin: 0; color: #1f2937; font-size: 18px; font-weight: 600;">
                    {symbol}
                </h3>
                <div style="color: #6b7280; font-size: 13px; margin-top: 2px;">
                    {name}
                </div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 24px; font-weight: 700; color: #1f2937;">
                    ${price:.2f}
                </div>
                <div style="font-size: 14px; color: {change_color}; font-weight: 600;">
                    {arrow} {change_symbol}{change:.2f} ({change_symbol}{change_percent:.2f}%)
                </div>
            </div>
        </div>
        
        <!-- Volume indicator -->
        <div style="margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 12px; color: #6b7280;">Volume:</span>
                <span style="font-size: 13px; font-weight: 600; color: #374151;">{volume_str}</span>
            </div>
        </div>
        
        <!-- Performance chips -->
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <span style="display: inline-block; padding: 4px 8px; background-color: #f3f4f6; 
                         border-radius: 4px; font-size: 11px; color: #4b5563;">
                1D: {change_symbol}{change_percent:.1f}%
            </span>
            <span style="display: inline-block; padding: 4px 8px; background-color: #f3f4f6; 
                         border-radius: 4px; font-size: 11px; color: #4b5563;">
                Vol: {volume_str}
            </span>
        </div>
        
        {news_html}
    </div>
    """

def _build_crypto_card(data: Dict) -> str:
    """Build crypto card with purple theme and special metrics"""
    symbol = data.get('symbol', 'N/A')
    name = data.get('name', '')
    price = data.get('price', 0)
    change = data.get('change', 0)
    change_percent = data.get('change_percent', 0)
    market_cap = data.get('market_cap', 0)
    volume = data.get('volume', 0)
    
    # Format large numbers
    if market_cap > 1000000000:
        mcap_str = f"${market_cap/1000000000:.1f}B"
    elif market_cap > 1000000:
        mcap_str = f"${market_cap/1000000:.1f}M"
    else:
        mcap_str = f"${market_cap:,.0f}"
    
    if volume > 1000000000:
        volume_str = f"${volume/1000000000:.1f}B"
    elif volume > 1000000:
        volume_str = f"${volume/1000000:.1f}M"
    else:
        volume_str = f"${volume:,.0f}"
    
    # Colors
    change_color = '#10b981' if change >= 0 else '#ef4444'
    change_symbol = '+' if change >= 0 else ''
    arrow = '▲' if change >= 0 else '▼'
    
    return f"""
    <div style="background: white; border-radius: 8px; padding: 20px; margin-bottom: 16px;
                border-left: 4px solid #8b5cf6; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        
        <!-- Header -->
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
            <div>
                <h3 style="margin: 0; color: #1f2937; font-size: 18px; font-weight: 600;">
                    {symbol} 
                    <span style="display: inline-block; background-color: #f3e8ff; color: #7c3aed; 
                                 padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;
                                 margin-left: 8px;">
                        CRYPTO
                    </span>
                </h3>
                <div style="color: #6b7280; font-size: 13px; margin-top: 2px;">
                    {name}
                </div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 24px; font-weight: 700; color: #1f2937;">
                    ${price:,.2f}
                </div>
                <div style="font-size: 14px; color: {change_color}; font-weight: 600;">
                    {arrow} {change_symbol}{change:.2f} ({change_symbol}{change_percent:.2f}%)
                </div>
            </div>
        </div>
        
        <!-- Crypto metrics -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px;">
            <div>
                <div style="font-size: 11px; color: #9ca3af; margin-bottom: 2px;">Market Cap</div>
                <div style="font-size: 14px; font-weight: 600; color: #374151;">{mcap_str}</div>
            </div>
            <div>
                <div style="font-size: 11px; color: #9ca3af; margin-bottom: 2px;">24h Volume</div>
                <div style="font-size: 14px; font-weight: 600; color: #374151;">{volume_str}</div>
            </div>
        </div>
        
        <!-- Performance indicators -->
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <span style="display: inline-block; padding: 4px 8px; background-color: #f3e8ff; 
                         border-radius: 4px; font-size: 11px; color: #7c3aed; font-weight: 500;">
                24H: {change_symbol}{change_percent:.1f}%
            </span>
            <span style="display: inline-block; padding: 4px 8px; background-color: #f3f4f6; 
                         border-radius: 4px; font-size: 11px; color: #4b5563;">
                MCap: {mcap_str}
            </span>
        </div>
    </div>
    """

def _render_top_movers(movers: List[Dict]) -> str:
    """Render top movers section"""
    if not movers:
        return ''
    
    html = ["""
    <div style="margin-top: 32px; padding: 20px; background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); 
                border-radius: 8px;">
        <h2 style="color: #92400e; font-size: 20px; font-weight: 700; margin: 0 0 16px 0;">
            🚀 Top Movers
        </h2>
        <div style="display: grid; gap: 8px;">
    """]
    
    for mover in movers[:5]:
        symbol = mover.get('symbol', 'N/A')
        name = mover.get('name', '')
        change_percent = mover.get('change_percent', 0)
        price = mover.get('price', 0)
        
        # Colors
        if change_percent >= 0:
            badge_color = '#059669'
            arrow = '▲'
            sign = '+'
        else:
            badge_color = '#dc2626'
            arrow = '▼'
            sign = ''
        
        html.append(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; 
                    padding: 8px; background: white; border-radius: 6px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-weight: 600; color: #1f2937;">{symbol}</span>
                <span style="color: #6b7280; font-size: 13px;">{name[:20]}...</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="color: #374151; font-size: 14px;">${price:.2f}</span>
                <span style="display: inline-block; padding: 2px 6px; background-color: {badge_color}; 
                             color: white; border-radius: 4px; font-size: 12px; font-weight: 600;">
                    {arrow} {sign}{change_percent:.1f}%
                </span>
            </div>
        </div>
        """)
    
    html.append("""
        </div>
    </div>
    """)
    
    return ''.join(html)

# For testing
if __name__ == "__main__":
    # Test data
    test_data = {
        'assets': [
            {
                'symbol': 'NVDA',
                'name': 'NVIDIA Corporation',
                'asset_class': 'equity',
                'industry': 'AI Semiconductors',
                'price': 850.25,
                'change': 12.50,
                'change_percent': 1.49,
                'volume': 45000000,
                'news': [
                    {'title': 'NVIDIA Announces New AI Chip', 'description': 'Revolutionary performance gains...'}
                ]
            }
        ],
        'categorized_heroes': {
            'breaking': [
                {'title': 'Markets Rally on Fed Decision', 'description': 'Stocks surge as Fed holds rates steady...', 'url': '#', 'source': 'Reuters'}
            ]
        },
        'top_movers': [
            {'symbol': 'NVDA', 'name': 'NVIDIA', 'price': 850.25, 'change_percent': 1.49}
        ]
    }
    
    html = render_email(test_data)
    print(f"Generated HTML: {len(html)} characters")
    
    # Save test output
    with open('test_email.html', 'w') as f:
        f.write(html)
    print("Test email saved to test_email.html")
