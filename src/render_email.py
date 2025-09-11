#!/usr/bin/env python3
"""
Investment Edge Email Renderer
Generates beautiful HTML emails from digest data
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailRenderer:
    """Renders digest data into HTML email"""
    
    def __init__(self):
        self.watchlist = self._load_watchlist()
        self.asset_class_map = self._build_asset_class_map()
    
    def _load_watchlist(self) -> List[Dict]:
        """Load watchlist configuration"""
        try:
            with open('watchlist.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading watchlist: {e}")
            return []
    
    def _build_asset_class_map(self) -> Dict[str, Dict]:
        """Build symbol to asset class mapping"""
        mapping = {}
        for asset in self.watchlist:
            if 'symbol' in asset:
                mapping[asset['symbol']] = {
                    'asset_class': asset.get('asset_class', 'equity'),
                    'industry': asset.get('industry'),
                    'priority': asset.get('priority', 'medium')
                }
        return mapping
    
    def _get_section_color(self, asset_class: str) -> str:
        """Get color scheme for asset class"""
        colors = {
            'etf': '#10B981',      # Green
            'equity': '#3B82F6',   # Blue
            'commodity': '#F59E0B', # Amber
            'crypto': '#8B5CF6'    # Purple
        }
        return colors.get(asset_class, '#3B82F6')
    
    def _determine_article_category(self, article: Dict) -> str:
        """Determine which section an article belongs to"""
        # Check associated symbol first
        symbol = article.get('associated_symbol')
        if symbol and symbol in self.asset_class_map:
            return self.asset_class_map[symbol]['asset_class']
        
        # Check text content
        text = f"{article.get('title', '')} {article.get('description', '')}".lower()
        
        # Crypto keywords
        crypto_keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency',
                          'blockchain', 'defi', 'xrp', 'ripple', 'digital asset', 'altcoin']
        if any(kw in text for kw in crypto_keywords):
            return 'crypto'
        
        # Commodity keywords
        commodity_keywords = ['gold', 'silver', 'oil', 'crude', 'commodity', 'copper',
                            'natural gas', 'precious metal', 'gld', 'slv', 'uso']
        if any(kw in text for kw in commodity_keywords):
            return 'commodity'
        
        # ETF keywords
        etf_keywords = ['etf', 'index', 'spy', 'qqq', 'iwm', 's&p 500', 'nasdaq',
                       'russell', 'dow jones', 'exchange traded fund']
        if any(kw in text for kw in etf_keywords):
            return 'etf'
        
        # Default to equity
        return 'equity'
    
    def _categorize_heroes(self, articles: List[Dict]) -> Dict[str, List]:
        """Categorize hero articles by asset class"""
        categorized = {
            'breaking': [],
            'etf': [],
            'equity': [],
            'commodity': [],
            'crypto': []
        }
        
        # Categorize all articles
        for article in articles:
            category = self._determine_article_category(article)
            categorized[category].append(article)
        
        # Select top 1-2 for breaking news
        all_scored = []
        for cat in ['etf', 'equity', 'commodity', 'crypto']:
            all_scored.extend(categorized[cat])
        
        # Sort by score/importance
        all_scored.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        if all_scored:
            # Take top 1-2 for breaking
            categorized['breaking'] = all_scored[:2]
            
            # Remove breaking articles from their original categories
            for article in categorized['breaking']:
                for cat in ['etf', 'equity', 'commodity', 'crypto']:
                    if article in categorized[cat]:
                        categorized[cat].remove(article)
        
        # Limit each section to 2-3 articles
        for cat in ['etf', 'equity', 'commodity', 'crypto']:
            categorized[cat] = categorized[cat][:3]
        
        return categorized
    
    def _generate_header(self) -> str:
        """Generate email header"""
        return '''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Investment Edge Daily Digest</title>
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
            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f3f4f6;">
                <tr>
                    <td align="center" style="padding: 20px 0;">
                        <table width="600" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden;">
                            <tr>
                                <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                                    <h1 style="margin: 0; color: #ffffff; font-size: 32px; font-weight: bold;">Investment Edge</h1>
                                    <p style="margin: 10px 0 0 0; color: #e0e7ff; font-size: 16px;">Daily Market Intelligence</p>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 30px;">
        '''
    
    def _generate_preview_text(self, top_article: Optional[Dict] = None) -> str:
        """Generate preview text for email"""
        if top_article:
            preview = top_article.get('title', 'Today\'s market update')[:90]
        else:
            preview = "Your daily investment intelligence digest"
        
        return f'''
        <div style="display: none; max-height: 0; overflow: hidden; mso-hide: all;">
            {preview}
        </div>
        '''
    
    def _render_hero(self, article: Dict) -> str:
        """Render a hero article"""
        title = article.get('title', article.get('headline', 'Market Update'))
        description = article.get('description', article.get('summary', ''))
        url = article.get('url', article.get('article_url', '#'))
        source = article.get('publisher', {}).get('name', '') if isinstance(article.get('publisher'), dict) else article.get('source', 'News')
        
        # Truncate description if too long
        if len(description) > 200:
            description = description[:197] + '...'
        
        return f'''
        <div style="margin-bottom: 25px; padding: 20px; background-color: #f9fafb; border-radius: 8px; border-left: 4px solid #4f46e5;">
            <h3 style="margin: 0 0 10px 0; font-size: 20px; line-height: 1.3;">
                <a href="{url}" style="color: #1f2937; text-decoration: none;">{title}</a>
            </h3>
            <p style="margin: 0 0 10px 0; color: #6b7280; font-size: 14px; line-height: 1.5;">{description}</p>
            <p style="margin: 0; font-size: 12px; color: #9ca3af;">Source: {source}</p>
        </div>
        '''
    
    def _build_card(self, asset_data: Dict, border_color: str) -> str:
        """Build asset card with appropriate styling"""
        symbol = asset_data.get('symbol', 'N/A')
        name = asset_data.get('name', 'Unknown')
        price = asset_data.get('current_price', 0)
        change = asset_data.get('change', asset_data.get('change_24h', 0))
        change_pct = asset_data.get('change_percent', asset_data.get('change_percent_24h', 0))
        volume = asset_data.get('volume', asset_data.get('volume_24h', 0))
        avg_volume = asset_data.get('average_volume', volume)
        
        # Determine if positive or negative
        change_color = '#10b981' if change_pct >= 0 else '#ef4444'
        change_symbol = '+' if change_pct >= 0 else ''
        
        # Performance chips
        perf = asset_data.get('performance', {})
        
        # Start card
        card_html = f'''
        <div style="border: 2px solid {border_color}; border-radius: 12px; padding: 20px; margin-bottom: 20px; background-color: #ffffff;">
        '''
        
        # Header with industry tag for equities
        if asset_data.get('asset_class') == 'equity' and 'industry' in asset_data:
            card_html += f'''
            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 15px;">
                <tr>
                    <td align="left">
                        <h3 style="margin: 0; font-size: 22px; color: #1f2937;">{symbol}</h3>
                        <p style="margin: 5px 0 0 0; color: #6b7280; font-size: 14px;">{name}</p>
                    </td>
                    <td align="right">
                        <span style="background-color: {border_color}22; color: {border_color}; padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: 600;">
                            {asset_data['industry']}
                        </span>
                    </td>
                </tr>
            </table>
            '''
        else:
            card_html += f'''
            <h3 style="margin: 0; font-size: 22px; color: #1f2937;">{symbol}</h3>
            <p style="margin: 5px 0 15px 0; color: #6b7280; font-size: 14px;">{name}</p>
            '''
        
        # Price and change
        card_html += f'''
        <div style="margin-bottom: 20px;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                    <td align="left">
                        <span style="font-size: 28px; font-weight: bold; color: #1f2937;">${price:,.2f}</span>
                    </td>
                    <td align="right">
                        <span style="font-size: 18px; font-weight: bold; color: {change_color};">
                            {change_symbol}{change_pct:.2f}%
                        </span>
                        <br>
                        <span style="font-size: 14px; color: {change_color};">
                            {change_symbol}${abs(change):,.2f}
                        </span>
                    </td>
                </tr>
            </table>
        </div>
        '''
        
        # Performance chips
        card_html += '''
        <div style="margin-bottom: 20px;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
        '''
        
        for period, label in [('1d', '1D'), ('1w', '1W'), ('1m', '1M'), ('ytd', 'YTD')]:
            perf_value = perf.get(period, 0)
            perf_color = '#10b981' if perf_value >= 0 else '#ef4444'
            perf_symbol = '+' if perf_value >= 0 else ''
            
            card_html += f'''
                    <td align="center" style="padding: 0 5px;">
                        <div style="background-color: {perf_color}11; border: 1px solid {perf_color}44; border-radius: 6px; padding: 8px; text-align: center;">
                            <div style="font-size: 11px; color: #6b7280; margin-bottom: 2px;">{label}</div>
                            <div style="font-size: 13px; font-weight: bold; color: {perf_color};">
                                {perf_symbol}{perf_value:.1f}%
                            </div>
                        </div>
                    </td>
            '''
        
        card_html += '''
                </tr>
            </table>
        </div>
        '''
        
        # Volume indicator
        if volume and avg_volume:
            volume_ratio = volume / avg_volume if avg_volume > 0 else 1
            volume_text = "High" if volume_ratio > 1.5 else "Normal" if volume_ratio > 0.5 else "Low"
            volume_color = "#ef4444" if volume_ratio > 2 else "#f59e0b" if volume_ratio > 1.5 else "#10b981"
            
            card_html += f'''
            <div style="margin-bottom: 20px;">
                <div style="font-size: 12px; color: #6b7280; margin-bottom: 5px;">Volume: {volume:,.0f}</div>
                <div style="background-color: #e5e7eb; border-radius: 4px; height: 8px; overflow: hidden;">
                    <div style="background-color: {volume_color}; height: 100%; width: {min(volume_ratio * 50, 100):.0f}%;"></div>
                </div>
                <div style="font-size: 11px; color: {volume_color}; margin-top: 3px;">
                    {volume_text} ({volume_ratio:.1f}x avg)
                </div>
            </div>
            '''
        
        # 52-week range
        high_52w = asset_data.get('week_52_high')
        low_52w = asset_data.get('week_52_low')
        if high_52w and low_52w and high_52w > low_52w:
            range_pct = ((price - low_52w) / (high_52w - low_52w)) * 100
            
            card_html += f'''
            <div style="margin-bottom: 20px;">
                <div style="font-size: 12px; color: #6b7280; margin-bottom: 5px;">52 Week Range</div>
                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td style="font-size: 11px; color: #9ca3af;">${low_52w:.2f}</td>
                        <td style="padding: 0 10px;">
                            <div style="background-color: #e5e7eb; border-radius: 4px; height: 6px; position: relative;">
                                <div style="background-color: #6366f1; height: 100%; width: {range_pct:.0f}%; border-radius: 4px;"></div>
                                <div style="position: absolute; top: -2px; left: {range_pct:.0f}%; margin-left: -5px; width: 10px; height: 10px; background-color: #4f46e5; border-radius: 50%;"></div>
                            </div>
                        </td>
                        <td align="right" style="font-size: 11px; color: #9ca3af;">${high_52w:.2f}</td>
                    </tr>
                </table>
            </div>
            '''
        
        # Latest news
        news = asset_data.get('news', [])[:3]
        if news:
            card_html += '''
            <div style="border-top: 1px solid #e5e7eb; padding-top: 15px;">
                <h4 style="margin: 0 0 10px 0; font-size: 14px; color: #6b7280;">Latest News</h4>
            '''
            
            for article in news:
                title = article.get('title', article.get('headline', ''))[:80]
                url = article.get('url', article.get('article_url', '#'))
                
                card_html += f'''
                <div style="margin-bottom: 8px;">
                    <a href="{url}" style="color: #4f46e5; text-decoration: none; font-size: 13px; line-height: 1.4;">
                        • {title}
                    </a>
                </div>
                '''
            
            card_html += '</div>'
        
        # Investment thesis
        if 'investment_thesis' in asset_data:
            card_html += f'''
            <div style="margin-top: 15px; padding: 10px; background-color: #f3f4f6; border-radius: 6px;">
                <p style="margin: 0; font-size: 12px; color: #6b7280; font-style: italic;">
                    {asset_data['investment_thesis']}
                </p>
            </div>
            '''
        
        card_html += '</div>'
        
        return card_html
    
    def _render_section(self, title: str, icon: str, heroes: List[Dict], 
                       assets: List[Dict], asset_class: str) -> str:
        """Render a complete section"""
        if not assets and not heroes:
            return ''
        
        color = self._get_section_color(asset_class)
        
        section_html = f'''
        <div style="margin-top: 40px;">
            <h2 style="color: {color}; font-size: 26px; font-weight: bold; margin: 0 0 20px 0; padding-bottom: 10px; border-bottom: 3px solid {color};">
                {icon} {title}
            </h2>
        '''
        
        # Add hero articles
        for hero in heroes:
            section_html += self._render_hero(hero)
        
        # Add asset cards
        for asset in assets:
            section_html += self._build_card(asset, color)
        
        section_html += '</div>'
        
        return section_html
    
    def _render_breaking_news(self, articles: List[Dict]) -> str:
        """Render breaking news section"""
        if not articles:
            return ''
        
        html = '''
        <div style="margin-top: 30px;">
            <h2 style="color: #dc2626; font-size: 26px; font-weight: bold; margin: 0 0 20px 0; padding-bottom: 10px; border-bottom: 3px solid #dc2626;">
                🔴 Breaking News
            </h2>
        '''
        
        for article in articles[:2]:
            html += self._render_hero(article)
        
        html += '</div>'
        
        return html
    
    def _render_top_movers(self, movers: List[Dict]) -> str:
        """Render top movers section"""
        if not movers:
            return ''
        
        html = '''
        <div style="margin-top: 40px; padding: 20px; background-color: #fef3c7; border-radius: 8px;">
            <h2 style="margin: 0 0 20px 0; color: #92400e; font-size: 22px;">
                🔥 Top Movers
            </h2>
            <table width="100%" cellpadding="8" cellspacing="0" border="0">
        '''
        
        for mover in movers[:5]:
            change_color = '#10b981' if mover['change'] >= 0 else '#ef4444'
            change_symbol = '+' if mover['change'] >= 0 else ''
            
            html += f'''
                <tr>
                    <td style="font-weight: bold; color: #1f2937;">{mover['symbol']}</td>
                    <td style="color: #6b7280; font-size: 14px;">{mover['name']}</td>
                    <td align="right" style="font-weight: bold; color: {change_color};">
                        {change_symbol}{mover['change']:.2f}%
                    </td>
                </tr>
            '''
        
        html += '''
            </table>
        </div>
        '''
        
        return html
    
    def _generate_footer(self) -> str:
        """Generate email footer"""
        return '''
                                </td>
                            </tr>
                            <tr>
                                <td style="background-color: #1f2937; padding: 30px; text-align: center;">
                                    <p style="margin: 0 0 10px 0; color: #9ca3af; font-size: 14px;">
                                        Investment Edge Daily Digest
                                    </p>
                                    <p style="margin: 0; color: #6b7280; font-size: 12px;">
                                        This is an automated digest. Always do your own research before making investment decisions.
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        '''
    
    def generate_email(self, digest_data: Dict) -> str:
        """Generate complete email HTML"""
        # Start email
        html = self._generate_header()
        
        # Add preview text
        top_articles = digest_data.get('top_articles', [])
        if top_articles:
            html += self._generate_preview_text(top_articles[0])
        
        # Categorize heroes
        categorized_heroes = self._categorize_heroes(top_articles)
        
        # Group assets by class
        assets_by_class = {
            'etf': [],
            'equity': [],
            'commodity': [],
            'crypto': []
        }
        
        for asset in digest_data.get('companies', []):
            symbol = asset.get('symbol')
            if symbol in self.asset_class_map:
                asset_class = self.asset_class_map[symbol]['asset_class']
                # Add metadata to asset
                asset['asset_class'] = asset_class
                if 'industry' in self.asset_class_map[symbol]:
                    asset['industry'] = self.asset_class_map[symbol]['industry']
                assets_by_class[asset_class].append(asset)
            else:
                # Default to equity if not found
                assets_by_class['equity'].append(asset)
        
        # Render sections in order
        
        # 1. Breaking News
        if categorized_heroes['breaking']:
            html += self._render_breaking_news(categorized_heroes['breaking'])
        
        # 2. ETFs & Indices
        if assets_by_class['etf'] or categorized_heroes['etf']:
            html += self._render_section(
                'ETFs & Indices',
                '📊',
                categorized_heroes['etf'],
                assets_by_class['etf'],
                'etf'
            )
        
        # 3. Equities
        if assets_by_class['equity'] or categorized_heroes['equity']:
            html += self._render_section(
                'Equities',
                '📈',
                categorized_heroes['equity'],
                assets_by_class['equity'],
                'equity'
            )
        
        # 4. Commodities
        if assets_by_class['commodity'] or categorized_heroes['commodity']:
            html += self._render_section(
                'Commodities',
                '🏗️',
                categorized_heroes['commodity'],
                assets_by_class['commodity'],
                'commodity'
            )
        
        # 5. Digital Assets
        if assets_by_class['crypto'] or categorized_heroes['crypto']:
            html += self._render_section(
                'Digital Assets',
                '🔐',
                categorized_heroes['crypto'],
                assets_by_class['crypto'],
                'crypto'
            )
        
        # 6. Top Movers
        top_movers = digest_data.get('top_movers', [])
        if top_movers:
            html += self._render_top_movers(top_movers)
        
        # Footer
        html += self._generate_footer()
        
        return html

def main():
    """Main execution for testing"""
    try:
        # Load digest data
        with open('daily_digest.json', 'r') as f:
            digest_data = json.load(f)
        
        # Generate email
        renderer = EmailRenderer()
        html_content = renderer.generate_email(digest_data)
        
        # Save HTML
        with open('email_output.html', 'w') as f:
            f.write(html_content)
        
        logger.info("Email HTML generated successfully")
        
        # Also generate subject line
        subject = "Investment Edge: "
        if digest_data.get('top_articles'):
            subject += digest_data['top_articles'][0].get('title', 'Daily Market Update')[:50]
        else:
            subject += "Daily Market Update"
        
        logger.info(f"Subject: {subject}")
        
        return html_content
        
    except Exception as e:
        logger.error(f"Error generating email: {str(e)}")
        return None

if __name__ == "__main__":
    main()
