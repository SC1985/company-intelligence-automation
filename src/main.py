#!/usr/bin/env python3
"""
Company Intelligence Automation - The Executive Engine
Design philosophy: Elegant orchestration of market intelligence
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

# Production-grade logging architecture
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class CompanyIntelligenceEngine:
    """The design vision made manifest - orchestrating intelligence with precision."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.companies = [
            {"symbol": "AAPL", "name": "Apple Inc.", "sector": "Technology"},
            {"symbol": "MSFT", "name": "Microsoft Corporation", "sector": "Technology"},
            {"symbol": "GOOGL", "name": "Alphabet Inc.", "sector": "Technology"},
            {"symbol": "AMZN", "name": "Amazon.com Inc.", "sector": "Technology"},
            {"symbol": "TSLA", "name": "Tesla Inc.", "sector": "Automotive"}
        ]
    
    async def orchestrate_intelligence_symphony(self):
        """The main execution - where data becomes insight, insight becomes power."""
        self.logger.info("🚀 INTELLIGENCE ENGINE ACTIVATION - Design Vision Deployed")
        
        try:
            # PHASE 1: Market Intelligence Collection
            market_data = await self._harvest_market_intelligence()
            
            # PHASE 2: News Intelligence Synthesis  
            news_data = await self._synthesize_news_intelligence()
            
            # PHASE 3: Executive Report Generation
            executive_report = self._architect_executive_report(market_data, news_data)
            
            # PHASE 4: Intelligent Distribution
            await self._deploy_intelligence_distribution(executive_report)
            
            self.logger.info("✅ INTELLIGENCE SYMPHONY COMPLETE - Design Excellence Achieved")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Symphony Disruption: {e}")
            await self._emergency_notification(str(e))
            return False
    
    async def _harvest_market_intelligence(self):
        """Market data collection with design precision."""
        alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        market_intelligence = {}
        
        self.logger.info("📊 Harvesting Market Intelligence Streams")
        
        for company in self.companies:
            symbol = company['symbol']
            
            try:
                if alpha_vantage_key:
                    url = "https://www.alphavantage.co/query"
                    params = {
                        'function': 'GLOBAL_QUOTE',
                        'symbol': symbol,
                        'apikey': alpha_vantage_key
                    }
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, params=params) as response:
                            if response.status == 200:
                                data = await response.json()
                                if 'Global Quote' in data:
                                    quote = data['Global Quote']
                                    market_intelligence[symbol] = {
                                        'price': quote.get('05. price', 'N/A'),
                                        'change': quote.get('09. change', 'N/A'),
                                        'change_percent': quote.get('10. change percent', 'N/A'),
                                        'volume': quote.get('06. volume', 'N/A'),
                                        'previous_close': quote.get('08. previous close', 'N/A')
                                    }
                                    self.logger.info(f"✅ Market data secured for {symbol}")
                
                # API rate limiting respect - design elegance
                await asyncio.sleep(12)
                
            except Exception as e:
                self.logger.warning(f"Market disruption for {symbol}: {e}")
                market_intelligence[symbol] = {'status': 'disrupted', 'error': str(e)}
        
        return market_intelligence
    
    async def _synthesize_news_intelligence(self):
        """News intelligence with sentiment architecture mastery."""
        newsapi_key = os.getenv('NEWSAPI_KEY')
        news_intelligence = {}
        
        self.logger.info("📰 Synthesizing News Intelligence Matrix")
        
        for company in self.companies:
            symbol = company['symbol']
            company_name = company['name']
            articles = []
            
            try:
                # NewsAPI Intelligence Stream
                if newsapi_key:
                    url = "https://newsapi.org/v2/everything"
                    params = {
                        'q': f'"{company_name}"',
                        'language': 'en',
                        'sortBy': 'relevancy',
                        'pageSize': 8,
                        'apiKey': newsapi_key
                    }
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, params=params) as response:
                            if response.status == 200:
                                data = await response.json()
                                if data.get('status') == 'ok':
                                    articles.extend(data.get('articles', []))
                
                # RSS Intelligence Enhancement
                try:
                    rss_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}"
                    feed = feedparser.parse(rss_url)
                    for entry in feed.entries[:3]:
                        articles.append({
                            'title': entry.get('title', ''),
                            'description': entry.get('summary', ''),
                            'url': entry.get('link', ''),
                            'publishedAt': entry.get('published', ''),
                            'source': {'name': 'Yahoo Finance RSS'}
                        })
                except:
                    pass
                
                # Sentiment Analysis Engine
                sentiment = self._architect_sentiment_analysis(articles)
                
                news_intelligence[symbol] = {
                    'article_count': len(articles),
                    'top_articles': articles[:4],
                    'sentiment': sentiment,
                    'intelligence_quality': 'premium' if len(articles) > 3 else 'standard'
                }
                
                self.logger.info(f"✅ News intelligence matrix complete for {symbol}")
                
            except Exception as e:
                self.logger.warning(f"News synthesis disruption for {symbol}: {e}")
                news_intelligence[symbol] = {'status': 'limited', 'error': str(e)}
        
        return news_intelligence
    
    def _architect_sentiment_analysis(self, articles):
        """Sentiment analysis with linguistic design excellence."""
        if not articles:
            return {'score': 0, 'classification': 'neutral', 'confidence': 0}
        
        # Linguistic sentiment architecture
        bullish_signals = [
            'growth', 'profit', 'beat', 'strong', 'bullish', 'upgrade', 'buy', 
            'surge', 'record', 'outperform', 'positive', 'gains', 'momentum'
        ]
        bearish_signals = [
            'loss', 'decline', 'miss', 'weak', 'bearish', 'downgrade', 'sell',
            'crash', 'lawsuit', 'concerns', 'risks', 'challenges', 'pressure'
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
            
            if avg_sentiment > 0.3:
                classification = 'bullish'
            elif avg_sentiment < -0.3:
                classification = 'bearish'
            else:
                classification = 'neutral'
            
            confidence = min(abs(avg_sentiment) * 1.5, 1.0)
            
            return {
                'score': round(avg_sentiment, 3),
                'classification': classification,
                'confidence': round(confidence, 3),
                'signals_analyzed': len(sentiment_scores)
            }
        
        return {'score': 0, 'classification': 'neutral', 'confidence': 0, 'signals_analyzed': 0}
    
    def _architect_executive_report(self, market_data, news_data):
        """Executive report generation - design thinking at its apex."""
        
        timestamp = datetime.now().strftime("%B %d, %Y")
        current_time = datetime.now().strftime("%I:%M %p EST")
        
        # Intelligence synthesis and alert generation
        total_companies = len(self.companies)
        active_alerts = []
        bullish_count = 0
        bearish_count = 0
        
        for company in self.companies:
            symbol = company['symbol']
            
            # Price movement alert architecture
            market_info = market_data.get(symbol, {})
            change_percent = market_info.get('change_percent', '')
            
            if change_percent and change_percent != 'N/A':
                try:
                    change_val = float(change_percent.replace('%', ''))
                    if abs(change_val) > 3:
                        alert_intensity = "🔥 MAJOR" if abs(change_val) > 8 else "⚡ SIGNIFICANT"
                        active_alerts.append(f"{alert_intensity} price movement in {symbol}: {change_percent}")
                except:
                    pass
            
            # Sentiment alert synthesis
            sentiment_info = news_data.get(symbol, {}).get('sentiment', {})
            classification = sentiment_info.get('classification', 'neutral')
            confidence = sentiment_info.get('confidence', 0)
            
            if classification == 'bullish':
                bullish_count += 1
            elif classification == 'bearish':
                bearish_count += 1
                
            if classification == 'bearish' and confidence > 0.6:
                active_alerts.append(f"🚨 BEARISH sentiment detected in {symbol} (confidence: {confidence:.0%})")
        
        # Market sentiment overview
        if bullish_count > bearish_count:
            market_mood = "🟢 BULLISH"
            mood_color = "#10b981"
        elif bearish_count > bullish_count:
            market_mood = "🔴 BEARISH"
            mood_color = "#ef4444"
        else:
            market_mood = "🟡 NEUTRAL"
            mood_color = "#f59e0b"
        
        # Executive report HTML architecture
        html_report = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Executive Intelligence Brief</title>
            <style>
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', sans-serif; 
                    margin: 0; padding: 0; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); 
                    line-height: 1.6; 
                }}
                .container {{ 
                    max-width: 900px; margin: 20px auto; background: white; 
                    border-radius: 16px; overflow: hidden; 
                    box-shadow: 0 20px 60px rgba(0,0,0,0.15); 
                }}
                .header {{ 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    color: white; padding: 40px 30px; text-align: center; 
                }}
                .header h1 {{ 
                    margin: 0; font-size: 2.8em; font-weight: 200; 
                    text-shadow: 0 2px 4px rgba(0,0,0,0.3); 
                }}
                .header p {{ 
                    margin: 15px 0 0 0; font-size: 1.2em; opacity: 0.9; 
                    font-weight: 300; 
                }}
                .executive-summary {{ 
                    background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); 
                    padding: 30px; border-bottom: 1px solid #e2e8f0; 
                }}
                .metrics-grid {{ 
                    display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                    gap: 25px; margin: 25px 0; 
                }}
                .metric {{ 
                    background: white; padding: 25px; border-radius: 12px; text-align: center; 
                    box-shadow: 0 4px 20px rgba(0,0,0,0.08); 
                    border-left: 5px solid #667eea; 
                }}
                .metric h3 {{ 
                    font-size: 2.5em; margin: 0; color: #2d3748; font-weight: 700; 
                }}
                .metric p {{ 
                    margin: 8px 0 0 0; color: #718096; font-size: 0.95em; 
                    text-transform: uppercase; letter-spacing: 1px; font-weight: 500; 
                }}
                .company-grid {{ 
                    display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); 
                    gap: 20px; padding: 30px; 
                }}
                .company-card {{ 
                    background: white; border-radius: 12px; padding: 25px; 
                    box-shadow: 0 4px 20px rgba(0,0,0,0.08); 
                    border: 1px solid #e2e8f0; transition: all 0.3s ease; 
                }}
                .company-header {{ 
                    display: flex; justify-content: space-between; align-items: center; 
                    margin-bottom: 20px; 
                }}
                .company-name {{ 
                    font-size: 1.4em; font-weight: 700; color: #2d3748; 
                }}
                .price-display {{ 
                    text-align: right; 
                }}
                .stock-price {{ 
                    font-size: 1.8em; font-weight: 700; 
                }}
                .price-change {{ 
                    font-size: 1em; font-weight: 600; margin-left: 8px; 
                }}
                .bullish {{ color: #10b981; }}
                .bearish {{ color: #ef4444; }}
                .neutral {{ color: #718096; }}
                .company-metrics {{ 
                    display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; 
                }}
                .metric-item {{ 
                    background: #f8fafc; padding: 15px; border-radius: 8px; 
                }}
                .metric-label {{ 
                    font-size: 0.85em; color: #718096; margin-bottom: 5px; 
                    text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; 
                }}
                .metric-value {{ 
                    font-size: 1.1em; font-weight: 700; color: #2d3748; 
                }}
                .sentiment-badge {{ 
                    display: inline-block; padding: 8px 16px; border-radius: 20px; 
                    font-size: 0.85em; font-weight: 700; text-transform: uppercase; 
                    letter-spacing: 0.5px; 
                }}
                .sentiment-bullish {{ background: #c6f6d5; color: #22543d; }}
                .sentiment-bearish {{ background: #fed7d7; color: #742a2a; }}
                .sentiment-neutral {{ background: #e2e8f0; color: #2d3748; }}
                .alerts-section {{ 
                    background: #fffbeb; border-left: 5px solid #f59e0b; 
                    padding: 25px 30px; margin: 0; 
                }}
                .alert-item {{ 
                    background: white; padding: 15px; border-radius: 8px; 
                    margin: 10px 0; border-left: 4px solid #f59e0b; 
                    box-shadow: 0 2px 8px rgba(0,0,0,0.05); 
                }}
                .footer {{ 
                    background: #2d3748; color: white; padding: 30px; text-align: center; 
                }}
                .footer p {{ margin: 0; opacity: 0.8; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 EXECUTIVE INTELLIGENCE BRIEF</h1>
                    <p>Strategic Market Intelligence • {timestamp} • {current_time}</p>
                </div>
                
                <div class="executive-summary">
                    <h2 style="margin: 0 0 20px 0; color: #2d3748; font-size: 1.8em;">🎯 EXECUTIVE DASHBOARD</h2>
                    <div class="metrics-grid">
                        <div class="metric">
                            <h3>{total_companies}</h3>
                            <p>Portfolio Companies</p>
                        </div>
                        <div class="metric">
                            <h3>{len(active_alerts)}</h3>
                            <p>Active Signals</p>
                        </div>
                        <div class="metric">
                            <h3 style="color: {mood_color};">{market_mood}</h3>
                            <p>Market Sentiment</p>
                        </div>
                        <div class="metric">
                            <h3>{bullish_count}/{bearish_count}</h3>
                            <p>Bull/Bear Ratio</p>
                        </div>
                    </div>
                </div>
        """
        
        # Company intelligence cards
        html_report += '<div class="company-grid">'
        
        for company in self.companies:
            symbol = company['symbol']
            company_name = company['name']
            
            market_info = market_data.get(symbol, {})
            news_info = news_data.get(symbol, {})
            sentiment_info = news_info.get('sentiment', {})
            
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
            
            # Price change styling
            price_class = 'neutral'
            if change_percent and change_percent != 'N/A':
                try:
                    change_val = float(str(change_percent).replace('%', ''))
                    price_class = 'bullish' if change_val > 0 else 'bearish' if change_val < 0 else 'neutral'
                except:
                    pass
            
            # Sentiment styling
            sentiment_class = sentiment_info.get('classification', 'neutral')
            sentiment_display = sentiment_class.upper()
            sentiment_css = f"sentiment-{sentiment_class}"
            
            article_count = news_info.get('article_count', 0)
            
            html_report += f"""
                <div class="company-card">
                    <div class="company-header">
                        <div class="company-name">{symbol}</div>
                        <div class="price-display">
                            <div class="stock-price {price_class}">${price}</div>
                            <div class="price-change {price_class}">({change_percent})</div>
                        </div>
                    </div>
                    <div style="color: #718096; margin-bottom: 15px; font-weight: 500;">{company_name}</div>
                    
                    <div class="company-metrics">
                        <div class="metric-item">
                            <div class="metric-label">Volume</div>
                            <div class="metric-value">{volume}</div>
                        </div>
                        <div class="metric-item">
                            <div class="metric-label">News Articles</div>
                            <div class="metric-value">{article_count}</div>
                        </div>
                    </div>
                    
                    <div style="margin-top: 15px;">
                        <span class="sentiment-badge {sentiment_css}">{sentiment_display} SENTIMENT</span>
                    </div>
                </div>
            """
        
        html_report += '</div>'
        
        # Active alerts section
        if active_alerts:
            html_report += f"""
                <div class="alerts-section">
                    <h2 style="margin: 0 0 20px 0; color: #92400e; font-size: 1.6em;">⚡ ACTIVE MARKET SIGNALS</h2>
            """
            for alert in active_alerts:
                html_report += f'<div class="alert-item">{alert}</div>'
            html_report += '</div>'
        else:
            html_report += """
                <div style="background: #f0fff4; border-left: 5px solid #10b981; padding: 25px 30px;">
                    <h2 style="margin: 0; color: #22543d; font-size: 1.6em;">✅ ALL SYSTEMS NOMINAL</h2>
                    <p style="margin: 10px 0 0 0; color: #22543d;">No significant alerts detected. Portfolio operating within normal parameters.</p>
                </div>
            """
        
        # Footer
        html_report += f"""
                <div class="footer">
                    <p><strong>🚀 COMPANY INTELLIGENCE AUTOMATION</strong></p>
                    <p style="margin-top: 15px;">
                        Engineered with Design Excellence • Generated {datetime.now().strftime('%Y-%m-%d at %H:%M UTC')}<br>
                        Next Intelligence Brief: {(datetime.now().replace(day=datetime.now().day + 7) if datetime.now().day <= 24 else datetime.now().replace(month=datetime.now().month + 1, day=1)).strftime('%B %d, %Y')}<br>
                        Monitoring {total_companies} companies across {len(set(c['sector'] for c in self.companies))} sectors
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_report
    
    async def _deploy_intelligence_distribution(self, html_report):
        """Intelligent distribution with design precision."""
        self.logger.info("📧 Deploying Intelligence Distribution Architecture")
        
        sender_email = os.getenv('SENDER_EMAIL')
        sender_password = os.getenv('SENDER_PASSWORD')
        recipients = [email.strip() for email in os.getenv('RECIPIENT_EMAILS', '').split(',') if email.strip()]
        
        if not all([sender_email, sender_password, recipients]):
            raise Exception("Distribution architecture incomplete - verify email configuration")
        
        # Message architecture
        msg = MIMEMultipart('alternative')
        msg['From'] = sender_email
        msg['To'] = ', '.join(recipients)
        
        # Dynamic subject line with intelligence
        alert_count = html_report.count('MAJOR') + html_report.count('SIGNIFICANT') + html_report.count('BEARISH sentiment')
        subject_prefix = "🔥" if alert_count > 3 else "📊"
        alert_suffix = f" ({alert_count} signals)" if alert_count > 0 else ""
        
        msg['Subject'] = f"{subject_prefix} Executive Intelligence Brief - {datetime.now().strftime('%B %d, %Y')}{alert_suffix}"
        
        # Attach HTML masterpiece
        html_part = MIMEText(html_report, 'html', 'utf-8')
        msg.attach(html_part)
        
        # SMTP deployment with design resilience
        try:
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
            
            self.logger.info(f"✅ Intelligence successfully distributed to {len(recipients)} executive(s)")
            
        except Exception as e:
            self.logger.error(f"Distribution disruption: {e}")
            raise
    
    async def _emergency_notification(self, error_message):
        """Emergency notification system - design reliability architecture."""
        try:
            admin_emails = [email.strip() for email in os.getenv('ADMIN_EMAILS', os.getenv('SENDER_EMAIL', '')).split(',') if email.strip()]
            
            if admin_emails and admin_emails[0]:
                emergency_report = f"""
                <html>
                <body style="font-family: sans-serif; padding: 20px;">
                    <div style="background: #fee2e2; border: 2px solid #ef4444; border-radius: 8px; padding: 20px;">
                        <h2 style="color: #dc2626;">🚨 INTELLIGENCE SYSTEM ALERT</h2>
                        <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                        <p><strong>Error:</strong> {error_message}</p>
                        <p><strong>System:</strong> Company Intelligence Automation</p>
                        <p>The intelligence gathering system encountered a disruption. Please review the error and system configuration.</p>
                    </div>
                </body>
                </html>
                """
                
                msg = MIMEMultipart()
                msg['From'] = os.getenv('SENDER_EMAIL')
                msg['To'] = admin_emails[0]
                msg['Subject'] = f"🚨 Intelligence System Alert - {datetime.now().strftime('%Y-%m-%d')}"
                msg.attach(MIMEText(emergency_report, 'html'))
                
                with smtplib.SMTP('smtp.gmail.com', 587) as server:
                    server.starttls()
                    server.login(os.getenv('SENDER_EMAIL'), os.getenv('SENDER_PASSWORD'))
                    server.send_message(msg)
                
        except Exception as e:
            self.logger.error(f"Emergency notification failed: {e}")

# EXECUTION ORCHESTRATION
async def main():
    """The main execution symphony - design vision in motion."""
    engine = CompanyIntelligenceEngine()
    success = await engine.orchestrate_intelligence_symphony()
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
