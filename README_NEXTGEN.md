# Investment Edge - Next‑Gen Daily Digest

Daily investor intelligence with enhanced mobile experience and comprehensive market insights:
- Breaking news prioritization with intelligent fallback to market analysis
- Top mover highlighting with live price changes and momentum indicators
- Enhanced company cards with 1D/1W/1M/YTD chips, momentum scores, and volume alerts
- Crypto cards with market cap, volume, ATH tracking, and specialized metrics
- Mobile-optimized with wider cards and premium typography
- Smart subject lines using hero headlines for maximum engagement

## Features
- **Investment Edge Branding**: Professional, action-oriented name replacing "Intelligence Digest"
- **Enhanced Company Cards**: Momentum indicators, volume analysis, earnings dates
- **Crypto-Specific Cards**: Market dominance, ATH distance, 24h volume tracking
- **Smart News Selection**: Multi-source aggregation with intelligent scoring
- **Mobile Excellence**: Responsive design with minimal padding for maximum content

## Install
Place these files at the repo root:
- `.github/workflows/daily-digest.yml` (Investment Edge workflow)
- `src/ci_entrypoint.py` (Entry point with Investment Edge branding)
- `src/nextgen_digest.py` (Enhanced crypto data fetching)
- `src/render_email.py` (Investment Edge renderer with enhanced cards)
- `src/chartgen.py` (Chart generation if needed)

## Schedule
Runs daily at 8am Central Time (CDT/CST adjusted)

## Manual Run
Actions → "Daily Investment Edge" → Run workflow

## Enhanced Metrics
- **Momentum Score**: Multi-timeframe analysis (1D/1W/1M) with visual indicators
- **Volume Analysis**: Highlights unusual trading activity (>1.5x average)
- **Crypto Metrics**: Market cap, 24h volume, ATH distance, market dominance
- **52-Week Range**: Visual range bar with position indicators

## Data Sources
- **Stocks**: Stooq (primary), Alpha Vantage (fallback)
- **Crypto**: CoinGecko enhanced API (comprehensive metrics)
- **News**: NewsAPI, Yahoo RSS, CoinGecko updates, engine synthesis

The workflow sets `NEXTGEN_DIGEST=true`. If anything fails, it falls back automatically.
