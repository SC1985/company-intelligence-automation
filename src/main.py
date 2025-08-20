#!/usr/bin/env python3
"""
Company Intelligence Automation - Strategic Constellation Engine
Portfolio monitoring across the complete technological transformation spectrum
"""

import asyncio
import os
import json
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import aiohttp
import requests
import feedparser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('intelligence_system.log')
    ]
)

class StrategicIntelligenceEngine:
    """Orchestrating intelligence across your 12-position strategic constellation."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.companies = self._load_strategic_constellation()
        
    def _load_strategic_constellation(self):
        """Load your curated strategic universe."""
        try:
            with open('data/companies.json', 'r') as f:
                companies = json.load(f)
            self.logger.info(f"✅ Strategic constellation loaded: {len(companies)} positions")
            return companies
        except:
            self.logger.warning("⚠️ Using fallback constellation")
            return [
                {"symbol": "AAPL", "name": "Apple Inc.", "sector": "Consumer Technology", "priority": "foundational_core"},
                {"symbol": "MSFT", "name": "Microsoft Corporation", "sector": "Enterprise Technology", "priority": "foundational_core"},
                {"symbol": "GOOGL", "name": "Alphabet Inc.", "sector": "Digital Platform", "priority": "foundational_core"},
                {"symbol": "AMZN", "name": "Amazon.com Inc.", "sector": "E-commerce/Cloud", "priority": "foundational_core"},
                {"symbol": "TSLA", "name": "Tesla Inc.", "sector": "Sustainable Transport", "priority": "growth_anchor"},
                {"symbol": "NVDA", "name": "NVIDIA Corporation", "sector": "AI Infrastructure", "priority": "strategic_growth"},
                {"symbol": "META", "name": "Meta Platforms Inc.", "sector": "Social Platform", "priority": "strategic_growth"},
                {"symbol": "NFLX", "name": "Netflix Inc.", "sector": "Streaming Entertainment", "priority": "growth_anchor"},
                {"symbol": "AMD", "name": "Advanced Micro Devices Inc.", "sector": "Semiconductors", "priority": "competitive_growth"},
                {"symbol": "PLTR", "name": "Palantir Technologies Inc.", "sector": "Data Analytics/AI", "priority": "strategic_growth"},
                {"symbol": "KOPN", "name": "Kopin Corporation", "sector": "AR/VR Technology", "priority": "speculative_innovation"},
                {"symbol": "SKYQ", "name": "Sky Quarry Inc.", "sector": "Industrial Technology", "priority": "speculative_innovation"}
            ]
    
    async def orchestrate_strategic_intelligence(self):
        """Execute the complete intelligence symphony."""
        self.logger.info("🚀 STRATEGIC CONSTELLATION INTELLIGENCE - Activation Sequence")
        
        try:
            # Phase 1: Market Data Collection
            self.logger.info("📊 Phase 1: Market Intelligence Collection")
            market_intelligence = await self._harvest_constellation_data()
            
            # Phase 2: News Intelligence Synthesis
            self.logger.info("📰 Phase 2: News Intelligence Synthesis")
            news_intelligence = await self._synthesize_strategic_news()
            
            # Phase 3: Executive Brief Generation
            self.logger.info("📋 Phase 3: Executive Brief Generation")
            strategic_brief = self._architect_executive_brief(market_intelligence, news_intelligence)
            
            # Phase 4: Intelligence Distribution
            self.logger.info("📧 Phase 4: Intelligence Distribution")
            await self._deploy_strategic_distribution(strategic_brief)
            
            self.logger.info("✅ STRATEGIC CONSTELLATION INTELLIGENCE - Mission Complete")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Intelligence disruption: {e}")
            await self._emergency_alert(str(e))
            return False
    
    async def _harvest_constellation_data(self):
        """Collect market data across your strategic universe."""
        alpha_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        constellation_data = {}
        
        for position in self.companies:
            symbol = position['symbol']
            
            try:
                if alpha_key:
                    url = "https://www.alphavantage.co/query"
                    params = {
                        'function': 'GLOBAL_QUOTE',
                        'symbol': symbol,
                        'apikey': alpha_key
                    }
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, params=params) as response:
                            if response.status == 200:
                                data = await response.json()
                                if 'Global Quote' in data:
                                    quote = data['Global Quote']
                                    constellation_data[symbol] = {
                                        'price': quote.get('05. price', 'N/A'),
                                        'change': quote.get('09. change', 'N/A'),
                                        'change_percent': quote.get('10. change percent', 'N/A'),
                                        'volume': quote.get('06. volume', 'N/A'),
                                        'high': quote.get('03. high', 'N/A'),
                                        'low': quote.get('04. low', 'N/A'),
                                        'position_data': position
                                    }
                                    self.logger.info(f"✅ Market data secured for {symbol}")
                                else:
                                    self.logger.warning(f"⚠️ No quote data for {symbol}")
                                    constellation_data[symbol] = {'status': 'no_data', 'position_data': position}
                
                # Strategic rate limiting
                await asyncio.sleep(12)
                
            except Exception as e:
                self.logger.warning(f"⚠️ Data collection issue for {symbol}: {e}")
                constellation_data[symbol] = {'status': 'limited', 'position_data': position}
        
        return constellation_data
    
    async def _synthesize_strategic_news(self):
        """News intelligence synthesis across strategic positions."""
        newsapi_key = os.getenv('NEWSAPI_KEY')
        news_matrix = {}
        
        for position in self.companies:
            symbol = position['symbol']
            company_name = position['name']
            articles = []
            
            try:
                # NewsAPI Intelligence
                if newsapi_key:
                    url = "https://newsapi.org/v2/everything"
                    params = {
                        'q': f'"{company_name}"',
                        'language': 'en',
                        'sortBy': 'relevancy',
                        'pageSize': 5,
                        'apiKey': newsapi_key
                    }
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, params=params) as response:
                            if response.status == 200:
                                data = await response.json()
                                if data.get('status') == 'ok':
                                    articles.extend(data.get('articles', []))
                
                # Sentiment Analysis
                sentiment = self._analyze_strategic_sentiment(articles)
                
                news_matrix[symbol] = {
                    'article_count': len(articles),
                    'top_articles': articles[:3],
                    'sentiment': sentiment,
                    'priority': position.get('priority', 'standard')
                }
                
                self.logger.info(f"✅ News intelligence complete for {symbol}")
                
            except Exception as e:
                self.logger.warning(f"⚠️ News synthesis limited for {symbol}: {e}")
                news_matrix[symbol] = {'status': 'limited', 'priority': position.get('priority', 'standard')}
        
        return news_matrix
    
    def _analyze_strategic_sentiment(self, articles):
        """Strategic sentiment analysis."""
        if not articles:
            return {'score': 0, 'classification': 'neutral', 'confidence': 0}
        
        bullish_signals = [
            'growth', 'profit', 'beat', 'strong', 'bullish', 'upgrade', 'buy', 'surge', 
            'record', 'outperform', 'breakthrough', 'innovation', 'partnership', 'expansion'
        ]
        
        bearish_signals = [
            'loss', 'decline', 'miss', 'weak', 'bearish', 'downgrade', 'sell', 'crash',
            'lawsuit', 'investigation', 'regulatory', 'competition', 'pressure', 'concerns'
        ]
        
        sentiment_scores = []
        
        for article in articles:
            text = f"{article.get('title', '')} {article.get('description', '')}".lower()
            
            bullish_count = sum(1 for signal in bullish_signals if signal in text)
            bearish_count = sum(1 for signal in bearish_signals if signal in text)
            
            if bullish_count + bearish_count > 0:
                score = (bullish_count - bearish_count) / (bullish_count + bearish_count)
                sentiment_scores.append(score)
        
        if sentiment_scores:
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
            
            if avg_sentiment > 0.25:
                classification = 'bullish'
            elif avg_sentiment < -0.25:
                classification = 'bearish'  
            else:
                classification = 'neutral'
            
            confidence = min(abs(avg_sentiment) * 1.8, 1.0)
            
            return {
                'score': round(avg_sentiment, 3),
                'classification': classification,
                'confidence': round(confidence, 3)
            }
        
        return {'score': 0, 'classification': 'neutral', 'confidence': 0}
    
    def _architect_executive_brief(self, market_data, news_data):
        """Generate executive-grade strategic intelligence brief."""
        
        timestamp = datetime.now().strftime("%B %d, %Y")
        current_time = datetime.now().strftime("%I:%M %p EST")
        
        # Strategic analysis
        total_positions = len(self.companies)
        strategic_alerts = []
        bullish_momentum = 0
        bearish_signals = 0
        
        for position in self.companies:
            symbol = position['symbol']
            market_info = market_data.get(symbol, {})
            news_info = news_data.get(symbol, {})
            
            # Price movement analysis
            change_percent = market_info.get('change_percent', '')
            if change_percent and change_percent != 'N/A':
                try:
                    change_val = float(change_percent.replace('%', ''))
                    if abs(change_val) > 5.0:
                        alert_intensity = "🔥 MAJOR" if abs(change_val) > 8 else "⚡ SIGNIFICANT"
                        strategic_alerts.append(f"{alert_intensity} movement in {symbol}: {change_percent}")
                except:
                    pass
            
            # Sentiment tracking
            sentiment = news_info.get('sentiment', {})
            if sentiment.get('classification') == 'bullish':
                bullish_momentum += 1
            elif sentiment.get('classification') == 'bearish':
                bearish_signals += 1
        
        # Portfolio sentiment
        if bullish_momentum > bearish_signals:
            portfolio_sentiment = "🟢 BULLISH MOMENTUM"
            sentiment_color = "#10b981"
        elif bearish_signals > bullish_momentum:
            portfolio_sentiment = "🔴 BEARISH PRESSURE"
            sentiment_color = "#ef4444"
        else:
            portfolio_sentiment = "🟡 BALANCED"
            sentiment_color = "#f59e0b"
        
        # Generate HTML report
        html_brief = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Strategic Constellation Intelligence Brief</title>
            <style>
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
                    margin: 0; padding: 0; 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    min-height: 100vh; 
                }}
                .container {{ max-width: 1000px; margin: 0 auto; padding: 20px; }}
                .header {{ 
                    background: rgba(255,255,255,0.95); 
                    backdrop-filter: blur(20px); 
                    border-radius: 20px; 
                    padding: 40px; 
                    text-align: center; 
                    margin-bottom: 30px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.1);
                }}
                .header h1 {{ 
                    margin: 0; font-size: 3em; font-weight: 200; 
                    background: linear-gradient(135deg, #667eea, #764ba2); 
                    -webkit-background-clip: text; 
                    -webkit-text-fill-color: transparent; 
                }}
                .dashboard {{ 
                    display: grid; 
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                    gap: 20px; 
                    margin: 30px 0; 
                }}
                .metric-card {{ 
                    background: rgba(255,255,255,0.9); 
                    backdrop-filter: blur(10px); 
                    border-radius: 16px; 
                    padding: 25px; 
                    text-align: center; 
                    box-shadow: 0 10px 30px rgba(0,0,0,0.1); 
                }}
                .metric-card h3 {{ 
                    font-size: 2.5em; margin: 0; 
                    background: linear-gradient(135deg, #667eea, #764ba2); 
                    -webkit-background-clip: text; 
                    -webkit-text-fill-color: transparent; 
                }}
                .positions-grid {{ 
                    display: grid; 
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
                    gap: 20px; 
                    margin: 30px 0; 
                }}
                .position-card {{ 
                    background: rgba(255,255,255,0.95); 
                    backdrop-filter: blur(20px); 
                    border-radius: 16px; 
                    padding: 20px; 
                    box-shadow: 0 10px 30px rgba(0,0,0,0.1); 
                }}
                .bullish {{ color: #10b981; }}
                .bearish {{ color: #ef4444; }}
                .neutral {{ color: #718096; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>STRATEGIC CONSTELLATION</h1>
                    <h2 style="margin: 10px 0; color: #4a5568;">Intelligence Brief</h2>
                    <p style="margin: 0; color: #718096; font-size: 1.1em;">{timestamp} • {current_time}</p>
                </div>
                
                <div class="dashboard">
                    <div class="metric-card">
                        <h3>{total_positions}</h3>
                        <p style="margin: 0; color: #718096; font-weight: 600;">Strategic Positions</p>
                    </div>
                    <div class="metric-card">
                        <h3>{len(strategic_alerts)}</h3>
                        <p style="margin: 0; color: #718096; font-weight: 600;">Active Signals</p>
                    </div>
                    <div class="metric-card">
                        <h3 style="color: {sentiment_color};">{portfolio_sentiment.split()[1]}</h3>
                        <p style="margin: 0; color: #718096; font-weight: 600;">Portfolio Sentiment</p>
                    </div>
                </div>
                
                <div class="positions-grid">
        """
        
        # Add position cards
        for position in self.companies:
            symbol = position['symbol']
            name = position['name']
            sector = position.get('sector', 'Technology')
            
            market_info = market_data.get(symbol, {})
            news_info = news_data.get(symbol, {})
            
            price = market_info.get('price', 'N/A')
            change_percent = market_info.get('change_percent', 'N/A')
            volume = market_info.get('volume', 'N/A')
            
            # Format volume
            if volume != 'N/A' and volume:
                try:
                    vol_num = int(volume)
                    if vol_num > 1000000:
                        volume = f"{vol_num/1000000:.1f}M"
                    elif vol_num > 1000:
                        volume = f"{vol_num/1000:.0f}K"
                except:
                    pass
            
            # Price styling
            price_class = 'neutral'
            if change_percent and change_percent != 'N/A':
                try:
                    change_val = float(str(change_percent).replace('%', ''))
                    price_class = 'bullish' if change_val > 0 else 'bearish' if change_val < 0 else 'neutral'
                except:
                    pass
            
            sentiment = news_info.get('sentiment', {})
            sentiment_class = sentiment.get('classification', 'neutral')
            article_count = news_info.get('article_count', 0)
            
            html_brief += f"""
                <div class="position-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                        <div>
                            <div style="font-size: 1.4em; font-weight: 700; color: #2d3748;">{symbol}</div>
                            <div style="color: #718096; font-size: 0.9em;">{name}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 1.2em; font-weight: 700;" class="{price_class}">${price}</div>
                            <div style="font-size: 0.9em;" class="{price_class}">({change_percent})</div>
                        </div>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 15px 0;">
                        <div style="background: #f7fafc; padding: 10px; border-radius: 6px;">
                            <div style="font-size: 0.8em; color: #718096;">SECTOR</div>
                            <div style="font-weight: 600; color: #2d3748;">{sector}</div>
                        </div>
                        <div style="background: #f7fafc; padding: 10px; border-radius: 6px;">
                            <div style="font-size: 0.8em; color: #718096;">VOLUME</div>
                            <div style="font-weight: 600; color: #2d3748;">{volume}</div>
                        </div>
                        <div style="background: #f7fafc; padding: 10px; border-radius: 6px;">
                            <div style="font-size: 0.8em; color: #718096;">NEWS</div>
                            <div style="font-weight: 600; color: #2d3748;">{article_count} articles</div>
                        </div>
                        <div style="background: #f7fafc; padding: 10px; border-radius: 6px;">
                            <div style="font-size: 0.8em; color: #718096;">SENTIMENT</div>
                            <div style="font-weight: 600;" class="{sentiment_class}">{sentiment_class.upper()}</div>
                        </div>
                    </div>
                </div>
            """
        
        html_brief += '</div>'
        
        # Add alerts if any
        if strategic_alerts:
            html_brief += f"""
                <div style="background: rgba(255,255,255,0.9); backdrop-filter: blur(20px); border-radius: 16px; padding: 30px; margin: 30px 0;">
                    <h2 style="margin: 0 0 20px 0; color: #2d3748;">⚡ STRATEGIC SIGNALS</h2>
            """
            for alert in strategic_alerts:
                html_brief += f'<div style="background: #fef5e7; border-left: 4px solid #f6ad55; padding: 15px; margin: 10px 0; border-radius: 8px;">{alert}</div>'
            html_brief += '</div>'
        
        # Footer
        html_brief += f"""
                <div style="background: rgba(255,255,255,0.9); backdrop-filter: blur(20px); border-radius: 16px; padding: 30px; text-align: center; margin-top: 30px;">
                    <h3 style="margin: 0; color: #2d3748;">🚀 STRATEGIC CONSTELLATION INTELLIGENCE</h3>
                    <p style="margin: 15px 0 0 0; color: #718096;">
                        Generated {datetime.now().strftime('%Y-%m-%d at %H:%M UTC')}<br>
                        Next Brief: Monday at 9:00 AM EST<br>
                        Monitoring {total_positions} strategic positions
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_brief
    
    async def _deploy_strategic_distribution(self, html_brief):
        """Deploy intelligence across your distribution network."""
        sender_email = os.getenv('SENDER_EMAIL')
        sender_password = os.getenv('SENDER_PASSWORD')
        recipients = [email.strip() for email in os.getenv('RECIPIENT_EMAILS', '').split(',') if email.strip()]
        
        # Dynamic subject generation
        alert_count = html_brief.count('MAJOR') + html_brief.count('SIGNIFICANT')
        subject_emoji = "🔥" if alert_count > 2 else "📊"
        alert_suffix = f" - {alert_count} signals" if alert_count > 0 else ""
        
        msg = MIMEMultipart('alternative')
        msg['From'] = sender_email
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = f"{subject_emoji} Strategic Constellation Brief - {datetime.now().strftime('%B %d, %Y')}{alert_suffix}"
        
        msg.attach(MIMEText(html_brief, 'html', 'utf-8'))
        
        try:
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
            
            self.logger.info(f"✅ Strategic intelligence distributed to {len(recipients)} executives")
            
        except Exception as e:
            self.logger.error(f"❌ Distribution error: {e}")
            raise
    
    async def _emergency_alert(self, error_message):
        """Emergency notification protocol."""
        try:
            admin_emails = [email.strip() for email in os.getenv('ADMIN_EMAILS', os.getenv('SENDER_EMAIL', '')).split(',') if email.strip()]
            
            if admin_emails and admin_emails[0]:
                emergency_html = f"""
                <html><body style="font-family: sans-serif; padding: 20px;">
                    <div style="background: #fee2e2; border: 2px solid #ef4444; border-radius: 12px; padding: 25px;">
                        <h2 style="color: #dc2626; margin: 0;">🚨 STRATEGIC INTELLIGENCE ALERT</h2>
                        <p><strong>Error:</strong> {error_message}</p>
                        <p><strong>Time:</strong> {datetime.now().isoformat()}</p>
                    </div>
                </body></html>
                """
                
                msg = MIMEMultipart()
                msg['From'] = os.getenv('SENDER_EMAIL')
                msg['To'] = admin_emails[0]
                msg['Subject'] = f"🚨 Intelligence Alert - {datetime.now().strftime('%Y-%m-%d')}"
                msg.attach(MIMEText(emergency_html, 'html'))
                
                with smtplib.SMTP('smtp.gmail.com', 587) as server:
                    server.starttls()
                    server.login(os.getenv('SENDER_EMAIL'), os.getenv('SENDER_PASSWORD'))
                    server.send_message(msg)
                
        except Exception as e:
            self.logger.error(f"Emergency notification failed: {e}")

async def main():
    """Strategic constellation execution orchestration."""
    engine = StrategicIntelligenceEngine()
    success = await engine.orchestrate_strategic_intelligence()
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
