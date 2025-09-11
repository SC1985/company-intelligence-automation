"""
Specific implementation details for render_email.py
Insert these functions into the existing EmailRenderer class
"""

def _determine_article_category(self, article):
    """Determine which section a hero article belongs to"""
    # Combine title and description for keyword matching
    text = f"{article.get('title', '')} {article.get('description', '')}".lower()
    
    # Also check if article has associated symbols
    symbols = article.get('symbols', [])
    if isinstance(symbols, str):
        symbols = [symbols]
    
    # Load watchlist to check symbol associations
    symbol_to_class = {}
    for asset in self.watchlist:
        if 'symbol' in asset:
            symbol_to_class[asset['symbol']] = asset.get('asset_class', 'equity')
    
    # Check symbols first (most accurate)
    for symbol in symbols:
        if symbol in symbol_to_class:
            return symbol_to_class[symbol]
    
    # Fallback to keyword matching
    # Crypto keywords (check first as most specific)
    if any(kw in text for kw in ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 
                                  'cryptocurrency', 'blockchain', 'defi', 'xrp', 
                                  'ripple', 'digital asset', 'altcoin']):
        return 'crypto'
    
    # Commodity keywords
    if any(kw in text for kw in ['gold', 'silver', 'oil', 'crude', 'commodity',
                                  'copper', 'natural gas', 'precious metal', 
                                  'gld', 'slv', 'uso', 'metals', 'energy']):
        return 'commodity'
    
    # ETF/Index keywords
    if any(kw in text for kw in ['etf', 'index', 'spy', 'qqq', 'iwm', 's&p',
                                  'nasdaq', 'russell', 'dow jones', 'exchange traded',
                                  'fund', 'indices']):
        return 'etf'
    
    # Default to equity
    return 'equity'

def _render_section(self, title, heroes, assets, asset_class):
    """Render a complete section with heroes and cards"""
    if not assets and not heroes:
        return ''
    
    # Get color for this asset class
    colors = {
        'etf': '#10B981',      # Green
        'equity': '#3B82F6',   # Blue  
        'commodity': '#F59E0B', # Amber
        'crypto': '#8B5CF6'    # Purple
    }
    color = colors.get(asset_class, '#3B82F6')
    
    # Section container
    html = f'''
    <div style="margin-top: 40px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
                <td>
                    <h2 style="color: {color}; font-size: 24px; font-weight: bold; 
                               margin: 0 0 20px 0; padding-bottom: 10px; 
                               border-bottom: 3px solid {color};">
                        {title}
                    </h2>
                </td>
            </tr>
        </table>
    '''
    
    # Add hero articles for this section
    if heroes:
        for hero in heroes[:3]:  # Max 3 heroes per section
            html += self._render_hero(hero)  # Use existing hero rendering
    
    # Add asset cards
    if assets:
        for asset_data in assets:
            # Add asset_class to data for card rendering
            asset_data['asset_class'] = asset_class
            
            # For equities, ensure industry is included
            if asset_class == 'equity':
                # Find industry from watchlist
                for w in self.watchlist:
                    if w.get('symbol') == asset_data.get('symbol'):
                        if 'industry' in w:
                            asset_data['industry'] = w['industry']
                        break
            
            # Use modified card builder
            html += self._build_enhanced_card(asset_data, color)
    
    html += '</div>'
    return html

def _build_enhanced_card(self, company_data, border_color):
    """Enhanced version of _build_card with asset-specific styling"""
    symbol = company_data.get('symbol', '')
    name = company_data.get('name', '')
    asset_class = company_data.get('asset_class', 'equity')
    
    # Start card with custom border color
    card_html = f'''
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 20px;">
        <tr>
            <td>
                <div style="border: 2px solid {border_color}; border-radius: 12px; 
                           padding: 20px; background-color: #ffffff;">
    '''
    
    # Header with industry tag for equities
    if asset_class == 'equity' and 'industry' in company_data:
        card_html += f'''
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
                <td align="left">
                    <h3 style="margin: 0; font-size: 20px; color: #1F2937;">
                        {symbol} - {name}
                    </h3>
                </td>
                <td align="right">
                    <span style="background-color: {border_color}22; 
                                color: {border_color}; 
                                padding: 4px 10px; 
                                border-radius: 4px; 
                                font-size: 12px; 
                                font-weight: 600;">
                        {company_data['industry']}
                    </span>
                </td>
            </tr>
        </table>
        '''
    else:
        card_html += f'''
        <h3 style="margin: 0 0 15px 0; font-size: 20px; color: #1F2937;">
            {symbol} - {name}
        </h3>
        '''
    
    # Continue with existing card content
    # (Price, change, performance chips, volume, range bar, news, etc.)
    # This part uses your existing _build_card logic
    
    # Close card
    card_html += '''
                </div>
            </td>
        </tr>
    </table>
    '''
    
    return card_html

def _render_breaking_news(self, breaking_articles):
    """Render the breaking news section at the top"""
    if not breaking_articles:
        return ''
    
    html = '''
    <div style="margin-top: 30px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
                <td>
                    <h2 style="color: #DC2626; font-size: 26px; font-weight: bold; 
                               margin: 0 0 20px 0; padding-bottom: 10px; 
                               border-bottom: 3px solid #DC2626;">
                        🔴 Breaking News
                    </h2>
                </td>
            </tr>
        </table>
    '''
    
    # Render 1-2 breaking news articles
    for article in breaking_articles[:2]:
        html += self._render_hero(article)  # Use existing hero rendering
    
    html += '</div>'
    return html

def generate_email_html(self, digest_data):
    """Main function to generate the new layout"""
    self.data = digest_data
    self.watchlist = self._load_watchlist()
    
    # Start email
    html = self._generate_header()
    html += self._generate_preview_text()
    
    # Categorize heroes
    all_heroes = digest_data.get('top_articles', [])[:20]  # Get more heroes
    categorized = self._categorize_heroes(all_heroes)
    
    # Group companies by asset class
    companies_by_class = {
        'etf': [],
        'equity': [],
        'commodity': [],
        'crypto': []
    }
    
    for company in digest_data.get('companies', []):
        # Find asset class from watchlist
        asset_class = 'equity'  # default
        for w in self.watchlist:
            if w.get('symbol') == company.get('symbol'):
                asset_class = w.get('asset_class', 'equity')
                break
        companies_by_class[asset_class].append(company)
    
    # Render sections in order
    
    # 1. Breaking News
    if categorized['breaking']:
        html += self._render_breaking_news(categorized['breaking'])
    
    # 2. ETFs & Indices
    if companies_by_class['etf'] or categorized['etf']:
        html += self._render_section(
            '📊 ETFs & Indices',
            categorized['etf'],
            companies_by_class['etf'],
            'etf'
        )
    
    # 3. Equities
    if companies_by_class['equity'] or categorized['equity']:
        html += self._render_section(
            '📈 Equities',
            categorized['equity'],
            companies_by_class['equity'],
            'equity'
        )
    
    # 4. Commodities
    if companies_by_class['commodity'] or categorized['commodity']:
        html += self._render_section(
            '🏗️ Commodities',
            categorized['commodity'],
            companies_by_class['commodity'],
            'commodity'
        )
    
    # 5. Digital Assets
    if companies_by_class['crypto'] or categorized['crypto']:
        html += self._render_section(
            '🔐 Digital Assets',
            categorized['crypto'],
            companies_by_class['crypto'],
            'crypto'
        )
    
    # 6. Top Movers (keep existing)
    html += self._generate_top_movers(digest_data)
    
    # Footer
    html += self._generate_footer()
    
    return html
