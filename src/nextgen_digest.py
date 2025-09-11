#!/usr/bin/env python3
"""
Investment Edge Daily Digest Generator
Fetches market data and news for tracked assets
"""

import json
import os
import sys
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import yfinance as yf
import pytz

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API Keys from environment
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')
ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')
MARKETAUX_API_KEY = os.getenv('MARKETAUX_API_KEY')
COINGECKO_API_KEY = os.getenv('COINGECKO_API_KEY')

# Create session with retry strategy
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

def filter_old_articles(articles: List[Dict], days: int = 7) -> List[Dict]:
    """Filter out articles older than specified days"""
    if not articles:
        return articles
    
    cutoff_date = datetime.now(pytz.UTC) - timedelta(days=days)
    filtered = []
    
    for article in articles:
        try:
            # Try different date field names
            pub_date = None
            for date_field in ['published_at', 'publishedAt', 'published', 'date', 'datetime']:
                if date_field in article:
                    pub_date = article[date_field]
                    break
            
            if pub_date:
                # Parse date based on type
                if isinstance(pub_date, str):
                    # Remove timezone info and parse
                    if 'T' in pub_date:
                        # ISO format
                        pub_date = pub_date.replace('Z', '+00:00')
                        article_date = datetime.fromisoformat(pub_date)
                    else:
                        # Try other formats
                        article_date = datetime.strptime(pub_date[:19], '%Y-%m-%d %H:%M:%S')
                    
                    # Make timezone aware if not already
                    if article_date.tzinfo is None:
                        article_date = pytz.UTC.localize(article_date)
                else:
                    article_date = pub_date
                
                # Compare dates
                if article_date > cutoff_date:
                    filtered.append(article)
            else:
                # If no date, include it (better safe than sorry)
                filtered.append(article)
                
        except Exception as e:
            # If date parsing fails, include the article
            logger.debug(f"Could not parse date for article: {e}")
            filtered.append(article)
    
    return filtered

def fetch_polygon_news(symbol: str) -> List[Dict]:
    """Fetch news from Polygon.io"""
    if not POLYGON_API_KEY:
        return []
    
    try:
        url = f"https://api.polygon.io/v2/reference/news"
        params = {
            'ticker': symbol,
            'limit': 10,
            'apiKey': POLYGON_API_KEY
        }
        
        response = session.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            articles = data.get('results', [])
            # Apply date filter
            return filter_old_articles(articles)
        else:
            logger.warning(f"Polygon API error for {symbol}: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Error fetching Polygon news for {symbol}: {str(e)}")
        return []

def fetch_marketaux_news(symbol: str) -> List[Dict]:
    """Fetch news from MarketAux API"""
    if not MARKETAUX_API_KEY:
        return []
    
    try:
        url = "https://api.marketaux.com/v1/news/all"
        params = {
            'symbols': symbol,
            'filter_entities': 'true',
            'limit': 10,
            'api_token': MARKETAUX_API_KEY
        }
        
        response = session.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            articles = data.get('data', [])
            # Apply date filter
            return filter_old_articles(articles)
        else:
            logger.warning(f"MarketAux API error for {symbol}: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Error fetching MarketAux news for {symbol}: {str(e)}")
        return []

def fetch_finnhub_news(symbol: str) -> List[Dict]:
    """Fetch news from Finnhub"""
    if not FINNHUB_API_KEY:
        return []
    
    try:
        # Calculate date range (last 7 days)
        to_date = datetime.now()
        from_date = to_date - timedelta(days=7)
        
        url = "https://finnhub.io/api/v1/company-news"
        params = {
            'symbol': symbol,
            'from': from_date.strftime('%Y-%m-%d'),
            'to': to_date.strftime('%Y-%m-%d'),
            'token': FINNHUB_API_KEY
        }
        
        response = session.get(url, params=params, timeout=10)
        if response.status_code == 200:
            articles = response.json()
            # Finnhub already respects date range, but apply filter anyway
            return filter_old_articles(articles)
        else:
            logger.warning(f"Finnhub API error for {symbol}: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Error fetching Finnhub news for {symbol}: {str(e)}")
        return []

def fetch_stock_data(asset: Dict) -> Optional[Dict]:
    """Fetch stock/ETF/commodity data using yfinance"""
    symbol = asset['symbol']
    
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Get current data
        current_price = info.get('regularMarketPrice') or info.get('currentPrice') or info.get('price')
        if not current_price:
            hist = ticker.history(period="1d")
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
        
        # Get historical data for calculations
        hist_1d = ticker.history(period="2d")
        hist_1w = ticker.history(period="1wk")
        hist_1m = ticker.history(period="1mo")
        hist_ytd = ticker.history(period="ytd")
        hist_52w = ticker.history(period="1y")
        
        # Calculate performance metrics
        def calc_performance(hist):
            if not hist.empty and len(hist) > 1:
                return ((hist['Close'].iloc[-1] / hist['Close'].iloc[0]) - 1) * 100
            return 0
        
        # Compile data
        data = {
            'symbol': symbol,
            'name': asset.get('name', info.get('longName', symbol)),
            'asset_class': asset.get('asset_class', 'equity'),
            'current_price': current_price,
            'previous_close': info.get('previousClose'),
            'change': current_price - info.get('previousClose', current_price) if info.get('previousClose') else 0,
            'change_percent': ((current_price / info.get('previousClose', current_price)) - 1) * 100 if info.get('previousClose') else 0,
            'volume': info.get('volume', 0),
            'average_volume': info.get('averageDailyVolume10Day', info.get('averageVolume', 0)),
            'market_cap': info.get('marketCap'),
            'week_52_high': info.get('fiftyTwoWeekHigh'),
            'week_52_low': info.get('fiftyTwoWeekLow'),
            'performance': {
                '1d': calc_performance(hist_1d),
                '1w': calc_performance(hist_1w),
                '1m': calc_performance(hist_1m),
                'ytd': calc_performance(hist_ytd)
            },
            'timestamp': datetime.now().isoformat()
        }
        
        # Add industry for equities
        if 'industry' in asset:
            data['industry'] = asset['industry']
        
        # Add asset-specific fields
        if asset.get('asset_class') == 'etf':
            data['etf_type'] = asset.get('etf_type')
        elif asset.get('asset_class') == 'commodity':
            data['commodity_type'] = asset.get('commodity_type')
        
        # Fetch news
        news = []
        news.extend(fetch_polygon_news(symbol))
        news.extend(fetch_marketaux_news(symbol))
        news.extend(fetch_finnhub_news(symbol))
        
        # Deduplicate and sort news
        seen_titles = set()
        unique_news = []
        for article in news:
            title = article.get('title', article.get('headline', ''))
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_news.append(article)
        
        # Sort by date (newest first)
        unique_news.sort(key=lambda x: x.get('published_at', x.get('datetime', '')), reverse=True)
        data['news'] = unique_news[:10]  # Limit to 10 most recent
        
        # Check alert thresholds
        alerts = []
        thresholds = asset.get('alert_thresholds', {})
        
        if abs(data['change_percent']) >= thresholds.get('price_change_percent', 999):
            alerts.append({
                'type': 'price_change',
                'message': f"{symbol} moved {data['change_percent']:.1f}%"
            })
        
        if data['volume'] > data['average_volume'] * thresholds.get('volume_spike_multiplier', 999):
            alerts.append({
                'type': 'volume_spike',
                'message': f"{symbol} volume {data['volume'] / data['average_volume']:.1f}x average"
            })
        
        data['alerts'] = alerts
        
        return data
        
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {str(e)}")
        return None

def fetch_crypto_data(asset: Dict) -> Optional[Dict]:
    """Fetch cryptocurrency data"""
    symbol = asset['symbol']
    coingecko_id = asset.get('coingecko_id')
    
    try:
        # Try CoinGecko first
        if coingecko_id and COINGECKO_API_KEY:
            url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}"
            params = {
                'localization': 'false',
                'tickers': 'false',
                'market_data': 'true',
                'community_data': 'false',
                'developer_data': 'false'
            }
            headers = {'x-cg-demo-api-key': COINGECKO_API_KEY}
            
            response = session.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                cg_data = response.json()
                market_data = cg_data.get('market_data', {})
                
                current_price = market_data.get('current_price', {}).get('usd', 0)
                
                data = {
                    'symbol': symbol,
                    'name': asset.get('name', cg_data.get('name', symbol)),
                    'asset_class': 'crypto',
                    'current_price': current_price,
                    'change_24h': market_data.get('price_change_24h', 0),
                    'change_percent_24h': market_data.get('price_change_percentage_24h', 0),
                    'change_percent_7d': market_data.get('price_change_percentage_7d', 0),
                    'change_percent_30d': market_data.get('price_change_percentage_30d', 0),
                    'market_cap': market_data.get('market_cap', {}).get('usd', 0),
                    'volume_24h': market_data.get('total_volume', {}).get('usd', 0),
                    'high_24h': market_data.get('high_24h', {}).get('usd', 0),
                    'low_24h': market_data.get('low_24h', {}).get('usd', 0),
                    'ath': market_data.get('ath', {}).get('usd', 0),
                    'atl': market_data.get('atl', {}).get('usd', 0),
                    'performance': {
                        '1d': market_data.get('price_change_percentage_24h', 0),
                        '1w': market_data.get('price_change_percentage_7d', 0),
                        '1m': market_data.get('price_change_percentage_30d', 0),
                        'ytd': market_data.get('price_change_percentage_1y', 0)
                    },
                    'timestamp': datetime.now().isoformat()
                }
                
                # Fetch crypto news
                news = []
                clean_symbol = symbol.replace('-USD', '')
                news.extend(fetch_polygon_news(clean_symbol))
                news.extend(fetch_marketaux_news(clean_symbol))
                
                # Deduplicate news
                seen_titles = set()
                unique_news = []
                for article in news:
                    title = article.get('title', article.get('headline', ''))
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        unique_news.append(article)
                
                data['news'] = unique_news[:10]
                
                # Check alerts
                alerts = []
                thresholds = asset.get('alert_thresholds', {})
                if abs(data['change_percent_24h']) >= thresholds.get('price_change_percent', 999):
                    alerts.append({
                        'type': 'price_change',
                        'message': f"{symbol} moved {data['change_percent_24h']:.1f}% in 24h"
                    })
                
                data['alerts'] = alerts
                
                return data
        
        # Fallback to yfinance for crypto
        return fetch_stock_data(asset)
        
    except Exception as e:
        logger.error(f"Error fetching crypto data for {symbol}: {str(e)}")
        # Try yfinance as fallback
        return fetch_stock_data(asset)

def fetch_all_data(watchlist: List[Dict]) -> List[Dict]:
    """Fetch data for all assets in watchlist"""
    all_data = []
    
    for asset in watchlist:
        # Skip comment entries
        if 'comment' in asset:
            continue
        
        logger.info(f"Fetching data for {asset['symbol']}...")
        
        asset_class = asset.get('asset_class', 'equity').lower()
        
        if asset_class == 'crypto':
            data = fetch_crypto_data(asset)
        else:
            # Use stock fetching for equities, ETFs, and commodities
            data = fetch_stock_data(asset)
        
        if data:
            # Ensure asset class is in data
            data['asset_class'] = asset_class
            
            # Add priority for ranking
            data['priority'] = asset.get('priority', 'medium')
            
            # Add investment thesis if available
            if 'investment_thesis' in asset:
                data['investment_thesis'] = asset['investment_thesis']
            
            all_data.append(data)
            time.sleep(0.5)  # Rate limiting
        else:
            logger.warning(f"No data retrieved for {asset['symbol']}")
    
    return all_data

def identify_top_movers(data: List[Dict]) -> List[Dict]:
    """Identify top movers by percentage change"""
    movers = []
    
    for asset in data:
        change_field = 'change_percent' if 'change_percent' in asset else 'change_percent_24h'
        change = asset.get(change_field, 0)
        
        if abs(change) >= 3.0:  # 3% threshold for top movers
            movers.append({
                'symbol': asset['symbol'],
                'name': asset['name'],
                'asset_class': asset.get('asset_class', 'equity'),
                'change': change,
                'price': asset.get('current_price', 0),
                'volume': asset.get('volume', asset.get('volume_24h', 0))
            })
    
    # Sort by absolute change
    movers.sort(key=lambda x: abs(x['change']), reverse=True)
    
    return movers[:5]  # Top 5 movers

def collect_all_news(data: List[Dict]) -> List[Dict]:
    """Collect and score all news articles"""
    all_articles = []
    
    for asset in data:
        for article in asset.get('news', []):
            # Add asset association
            article['associated_symbol'] = asset['symbol']
            article['associated_name'] = asset['name']
            article['asset_class'] = asset.get('asset_class', 'equity')
            
            # Score article based on various factors
            score = 0
            
            # Priority of associated asset
            priority_scores = {'critical': 10, 'high': 7, 'medium': 5, 'speculative': 3}
            score += priority_scores.get(asset.get('priority', 'medium'), 5)
            
            # Recency (assumed already filtered to last 7 days)
            score += 5
            
            # Asset performance correlation
            change = abs(asset.get('change_percent', asset.get('change_percent_24h', 0)))
            if change > 10:
                score += 10
            elif change > 5:
                score += 7
            elif change > 3:
                score += 5
            
            article['score'] = score
            all_articles.append(article)
    
    # Deduplicate by title
    seen_titles = set()
    unique_articles = []
    for article in all_articles:
        title = article.get('title', article.get('headline', ''))
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_articles.append(article)
    
    # Sort by score
    unique_articles.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    return unique_articles

def generate_digest(watchlist: List[Dict]) -> Dict:
    """Generate the complete digest"""
    logger.info("Starting digest generation...")
    
    # Fetch all data
    all_data = fetch_all_data(watchlist)
    
    # Identify top movers
    top_movers = identify_top_movers(all_data)
    
    # Collect and score news
    all_news = collect_all_news(all_data)
    
    # Select top articles for heroes
    top_articles = all_news[:20]  # Get more for categorization
    
    # Generate summary stats
    stats = {
        'total_assets': len(all_data),
        'gainers': len([a for a in all_data if a.get('change_percent', a.get('change_percent_24h', 0)) > 0]),
        'losers': len([a for a in all_data if a.get('change_percent', a.get('change_percent_24h', 0)) < 0]),
        'alerts': sum(len(a.get('alerts', [])) for a in all_data),
        'timestamp': datetime.now().isoformat()
    }
    
    digest = {
        'generated_at': datetime.now().isoformat(),
        'stats': stats,
        'assets': all_data,
        'top_movers': top_movers,
        'top_articles': top_articles,
        'all_news': all_news[:50]  # Keep top 50 for reference
    }
    
    logger.info(f"Digest generated with {len(all_data)} assets and {len(all_news)} news articles")
    
    return digest

def main():
    """Main execution function"""
    try:
        # Load watchlist
        with open('watchlist.json', 'r') as f:
            watchlist = json.load(f)
        
        logger.info(f"Loaded watchlist with {len([w for w in watchlist if 'symbol' in w])} assets")
        
        # Generate digest
        digest = generate_digest(watchlist)
        
        # Save digest
        output_file = 'digest.json'
        with open(output_file, 'w') as f:
            json.dump(digest, f, indent=2)
        
        logger.info(f"Digest saved to {output_file}")
        
        # Also save a simplified version for email rendering
        simple_digest = {
            'generated_at': digest['generated_at'],
            'companies': digest['assets'],  # Keep as 'companies' for compatibility
            'top_movers': digest['top_movers'],
            'top_articles': digest['top_articles'][:20],
            'stats': digest['stats']
        }
        
        with open('daily_digest.json', 'w') as f:
            json.dump(simple_digest, f, indent=2)
        
        logger.info("Daily digest saved successfully")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
