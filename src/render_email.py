#!/usr/bin/env python3
"""
Complete updates for src/render_email.py
These are the KEY CHANGES to integrate into your existing render_email.py
"""

def render_email(data):
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
    
    # 1. Email header (keep existing)
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
    
    # 7. Top Movers Section (keep at the end)
    if top_movers:
        html_parts.append(_render_top_movers(top_movers))
    
    # 8. Footer (keep existing)
    html_parts.append(_render_footer())
    
    # Combine all parts
    return _wrap_in_email_template(''.join(html_parts))

def _render_breaking_news_section(articles):
    """Render the breaking news section at the top"""
    if not articles:
        return ''
    
    return f'''
    <div style="margin-bottom: 32px;">
        <h2 style="color: #1F2937; font-size: 24px; font-weight: 700; margin: 0 0 16px 0;">
            📰 Breaking News
        </h2>
        {_render_heroes(articles)}
    </div>
    '''

def _render_etf_section(etfs, hero_articles):
    """Render ETFs & Indices section with green theme"""
    if not etfs and not hero_articles:
        return ''
    
    section_html = []
    section_html.append('''
    <div style="margin-bottom: 32px;">
        <h2 style="color: #1F2937; font-size: 24px; font-weight: 700; margin: 0 0 16px 0;">
            📊 ETFs & Indices
        </h2>
    ''')
    
    # Add hero articles for this section
    if hero_articles:
        section_html.append(_render_heroes(hero_articles))
    
    # Add ETF cards with green borders
    if etfs:
        for etf in etfs:
            section_html.append(_build_card(etf, border_color='#10B981'))  # Green
    
    section_html.append('</div>')
    return ''.join(section_html)

def _render_equity_section(equities, hero_articles):
    """Render Equities section with blue theme and industry tags"""
    if not equities and not hero_articles:
        return ''
    
    section_html = []
    section_html.append('''
    <div style="margin-bottom: 32px;">
        <h2 style="color: #1F2937; font-size: 24px; font-weight: 700; margin: 0 0 16px 0;">
            📈 Equities
        </h2>
    ''')
    
    # Add hero articles for this section
    if hero_articles:
        section_html.append(_render_heroes(hero_articles))
    
    # Add equity cards with blue borders and industry tags
    if equities:
        for equity in equities:
            section_html.append(_build_equity_card_with_industry(equity))
    
    section_html.append('</div>')
    return ''.join(section_html)

def _render_commodity_section(commodities, hero_articles):
    """Render Commodities section with gold/amber theme"""
    if not commodities and not hero_articles:
        return ''
    
    section_html = []
    section_html.append('''
    <div style="margin-bottom: 32px;">
        <h2 style="color: #1F2937; font-size: 24px; font-weight: 700; margin: 0 0 16px 0;">
            🏆 Commodities
        </h2>
    ''')
    
    # Add hero articles for this section
    if hero_articles:
        section_html.append(_render_heroes(hero_articles))
    
    # Add commodity cards with gold borders
    if commodities:
        for commodity in commodities:
            section_html.append(_build_card(commodity, border_color='#F59E0B'))  # Gold/Amber
    
    section_html.append('</div>')
    return ''.join(section_html)

def _render_crypto_section(cryptos, hero_articles):
    """Render Digital Assets section with purple theme"""
    if not cryptos and not hero_articles:
        return ''
    
    section_html = []
    section_html.append('''
    <div style="margin-bottom: 32px;">
        <h2 style="color: #1F2937; font-size: 24px; font-weight: 700; margin: 0 0 16px 0;">
            🪙 Digital Assets
        </h2>
    ''')
    
    # Add hero articles for this section
    if hero_articles:
        section_html.append(_render_heroes(hero_articles))
    
    # Add crypto cards with purple borders
    if cryptos:
        for crypto in cryptos:
            section_html.append(_build_card(crypto, border_color='#8B5CF6'))  # Purple
    
    section_html.append('</div>')
    return ''.join(section_html)

def _build_equity_card_with_industry(data):
    """Build equity card with industry tag - extends existing _build_card"""
    # Get the base card HTML using existing function
    card_html = _build_card(data, border_color='#3B82F6')  # Blue for equities
    
    # If there's an industry, add the tag
    if 'industry' in data:
        industry_tag = f'''
        <span style="display: inline-block; background-color: #EEF2FF; color: #4F46E5; 
                     padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;
                     margin-left: 8px;">
            {data['industry']}
        </span>
        '''
        
        # Insert the industry tag after the symbol in the card header
        # This assumes your existing _build_card has a structure we can modify
        # You'll need to adjust based on your actual card structure
        card_html = card_html.replace('</h3>', f'{industry_tag}</h3>', 1)
    
    return card_html

def _build_card(data, border_color='#3B82F6'):
    """
    YOUR EXISTING _build_card FUNCTION
    Just update to accept border_color parameter and use it
    
    Example modification:
    - Change border-left: 4px solid #3B82F6 
    - To: border-left: 4px solid {border_color}
    """
    # This is a placeholder - use your existing _build_card logic
    # Just add the border_color parameter and apply it
    symbol = data.get('symbol', 'N/A')
    name = data.get('name', '')
    price = data.get('price', 0)
    change = data.get('change', 0)
    change_percent = data.get('change_percent', 0)
    
    # Determine color for change
    change_color = '#10B981' if change >= 0 else '#EF4444'
    change_symbol = '+' if change >= 0 else ''
    
    return f'''
    <div style="background: white; border-radius: 8px; padding: 20px; margin-bottom: 16px;
                border-left: 4px solid {border_color}; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <h3 style="margin: 0; color: #1F2937; font-size: 18px; font-weight: 600;">
                {symbol} <span style="color: #6B7280; font-weight: 400; font-size: 14px;">{name}</span>
            </h3>
            <div style="text-align: right;">
                <div style="font-size: 24px; font-weight: 700; color: #1F2937;">${price:.2f}</div>
                <div style="font-size: 14px; color: {change_color}; font-weight: 600;">
                    {change_symbol}{change:.2f} ({change_symbol}{change_percent:.2f}%)
                </div>
            </div>
        </div>
        
        <!-- Add your existing card content here: momentum, volume, range, news, etc. -->
        <!-- This is just the basic structure - use your existing complete card layout -->
        
    </div>
    '''

def _render_heroes(articles):
    """
    YOUR EXISTING _render_heroes FUNCTION
    Keep this exactly as is - no changes needed
    """
    # Use your existing hero rendering logic
    pass

# Additional helper functions remain the same
# Just ensure all references to 'companies' are updated to 'watchlist' or 'assets'
