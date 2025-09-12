#!/usr/bin/env python3
"""
Complete updates for src/nextgen_digest.py
These are the specific changes needed - integrate these into your existing file
"""

import json
from datetime import datetime, timedelta
import asyncio

# KEY CHANGES TO MAKE IN YOUR EXISTING nextgen_digest.py:

# 1. Update the file loading section
def load_watchlist():
    """Load watchlist from JSON file"""
    with open('watchlist.json', 'r') as f:
        watchlist = json.load(f)
    return watchlist

# 2. Update the fetch_all_data function to handle new asset classes
async def fetch_all_data(watchlist, logger):
    """Fetch data for all assets in watchlist"""
    all_data = []
    
    for asset in watchlist:
        # Skip comment entries
        if 'comment' in asset:
            continue
            
        asset_class = asset.get('asset_class', 'equity').lower()
        
        try:
            if asset_class == 'crypto':
                # Use existing crypto fetching logic
                data = await fetch_crypto_data(asset, logger)
            elif asset_class in ['equity', 'etf', 'commodity']:
                # Use existing stock fetching logic for all these
                data = await fetch_stock_data(asset, logger)
            else:
                logger.warning(f"Unknown asset class: {asset_class}")
                continue
                
            if data:
                # Add asset class to the data
                data['asset_class'] = asset_class
                # Add industry if it exists (for equities)
                if 'industry' in asset:
                    data['industry'] = asset['industry']
                all_data.append(data)
                
        except Exception as e:
            logger.error(f"Error fetching {asset['symbol']}: {str(e)}")
            
    return all_data

# 3. Add date filtering function for articles
def filter_recent_articles(articles, days=7):
    """Filter articles to only include those from the last N days"""
    if not articles:
        return []
    
    cutoff_date = datetime.now() - timedelta(days=days)
    filtered = []
    
    for article in articles:
        try:
            # Try different date fields that might exist
            pub_date = None
            if 'publishedAt' in article:
                pub_date = datetime.fromisoformat(article['publishedAt'].replace('Z', '+00:00'))
            elif 'published_at' in article:
                pub_date = datetime.fromisoformat(article['published_at'].replace('Z', '+00:00'))
            elif 'date' in article:
                pub_date = datetime.fromisoformat(article['date'].replace('Z', '+00:00'))
            
            if pub_date and pub_date > cutoff_date:
                filtered.append(article)
        except Exception:
            # If we can't parse the date, include the article to be safe
            filtered.append(article)
    
    return filtered

# 4. Update the categorize_heroes function
def categorize_heroes(hero_articles, watchlist):
    """Categorize hero articles by asset class"""
    categorized = {
        'breaking': [],  # Top 1-2 breaking news
        'etf': [],
        'equity': [],
        'commodity': [],
        'crypto': []
    }
    
    # Get symbols by asset class for matching
    symbols_by_class = {
        'etf': [],
        'equity': [],
        'commodity': [],
        'crypto': []
    }
    
    for asset in watchlist:
        if 'comment' in asset:
            continue
        asset_class = asset.get('asset_class', 'equity').lower()
        if asset_class in symbols_by_class:
            symbols_by_class[asset_class].append(asset['symbol'].upper())
            # Also add name for matching
            if 'name' in asset:
                symbols_by_class[asset_class].append(asset['name'].upper())
    
    # Categorize each hero article
    for article in hero_articles:
        if not article:
            continue
            
        title = article.get('title', '').upper()
        description = article.get('description', '').upper()
        content = title + ' ' + description
        
        # Check which category this article belongs to
        matched = False
        
        # Check ETFs first (SPY, QQQ, IWM, "INDEX", "ETF")
        etf_keywords = symbols_by_class['etf'] + ['INDEX', 'INDICES', 'ETF', 'S&P', 'NASDAQ', 'RUSSELL']
        for keyword in etf_keywords:
            if keyword in content:
                categorized['etf'].append(article)
                matched = True
                break
        
        # Check commodities
        if not matched:
            commodity_keywords = symbols_by_class['commodity'] + ['GOLD', 'SILVER', 'OIL', 'CRUDE', 'GAS', 'COPPER', 'COMMODITY']
            for keyword in commodity_keywords:
                if keyword in content:
                    categorized['commodity'].append(article)
                    matched = True
                    break
        
        # Check crypto
        if not matched:
            crypto_keywords = symbols_by_class['crypto'] + ['BITCOIN', 'ETHEREUM', 'CRYPTO', 'BLOCKCHAIN', 'DEFI']
            for keyword in crypto_keywords:
                if keyword in content:
                    categorized['crypto'].append(article)
                    matched = True
                    break
        
        # Check equities
        if not matched:
            for symbol in symbols_by_class['equity']:
                if symbol in content:
                    categorized['equity'].append(article)
                    matched = True
                    break
        
        # If no match, it's general breaking news
        if not matched:
            categorized['breaking'].append(article)
    
    # Limit each category
    categorized['breaking'] = categorized['breaking'][:2]  # Max 2 breaking news
    for key in ['etf', 'equity', 'commodity', 'crypto']:
        categorized[key] = categorized[key][:3]  # Max 3 per section
    
    return categorized

# 5. Update the main build function
async def build_nextgen_html(logger):
    """Main function to build the newsletter"""
    try:
        # Load watchlist instead of companies
        watchlist = load_watchlist()
        
        # Fetch all data
        all_data = await fetch_all_data(watchlist, logger)
        
        # Fetch news (existing logic)
        all_news = await fetch_all_news(all_data, logger)
        
        # Filter news to recent articles only (7 days)
        for item in all_data:
            if 'news' in item and item['news']:
                item['news'] = filter_recent_articles(item['news'], days=7)
        
        # Get hero articles (existing logic)
        hero_articles = get_top_hero_articles(all_news, logger)
        
        # Filter hero articles to recent only
        hero_articles = filter_recent_articles(hero_articles, days=7)
        
        # Categorize heroes by section
        categorized_heroes = categorize_heroes(hero_articles, watchlist)
        
        # Calculate top movers (existing logic)
        top_movers = calculate_top_movers(all_data, logger)
        
        # Prepare data for rendering
        digest_data = {
            'timestamp': datetime.now().isoformat(),
            'assets': all_data,  # All asset data
            'categorized_heroes': categorized_heroes,  # Heroes organized by section
            'top_movers': top_movers,
            'watchlist': watchlist  # Pass watchlist for reference
        }
        
        # Render the email
        from render_email import render_email
        html = render_email(digest_data)
        
        return html
        
    except Exception as e:
        logger.error(f"Error building newsletter: {str(e)}")
        raise

# Make sure to update ALL references from 'companies' to 'watchlist' throughout the file
# Update any 'companies.json' references to 'watchlist.json'
