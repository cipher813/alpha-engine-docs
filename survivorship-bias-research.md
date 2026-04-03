# Survivorship Bias Mitigation — Research Memo

**Date:** 2026-04-03
**Status:** Research complete, implementation deferred

## Problem

The backtester and predictor train on currently-listed S&P 500/400 stocks only. Stocks that were delisted, acquired, or dropped from the index are excluded from historical analysis. This biases results upward — the current constituents are "survivors" that by definition didn't fail during the backtest period.

## Impact Assessment

For a 5-day horizon strategy, survivorship bias is less severe than for long-only buy-and-hold strategies, because:
- Delisted stocks typically decline over months, not days
- The weekly signal refresh naturally rotates away from deteriorating stocks
- Sector-neutral alpha labels partially control for broad market effects

However, the 10-year backtester synthetic backtest (`predictor-backtest` mode) is meaningfully affected — it trains and evaluates on 10 years of history using only today's constituents.

## Free Data Sources for Historical Constituents

### Wikipedia S&P 500 Changes Table
- URL: `https://en.wikipedia.org/wiki/List_of_S%26P_500_companies`
- The page has a "Selected changes to the list" table with date, ticker added, ticker removed
- Goes back ~10 years with good coverage
- **Already accessible:** `alpha-engine-data/collectors/constituents.py` scrapes this page for current constituents — extending to the changes table is straightforward
- **Limitation:** S&P 500 only, not S&P 400 (mid-cap)

### yfinance Delisted Ticker Data
- yfinance can fetch OHLCV for delisted tickers if the symbol is known
- Returns partial history with adjusted prices
- Some tickers return empty data or errors
- **Limitation:** Ticker symbols may be reused (e.g., old TWTR became X)

### SEC EDGAR
- CIK-based lookup can identify historical filings for delisted companies
- Useful for fundamental data but not OHLCV prices

## Recommended Implementation

### Phase 1: Historical constituent list (low effort)
1. Scrape the Wikipedia S&P 500 changes table (additions and deletions since 2015)
2. Build `historical_constituents.json` mapping `{date: [ticker_list]}` by replaying changes backward from today's list
3. Store in S3 at `market_data/historical_constituents.json`
4. Backtester reads this file and uses point-in-time constituent lists for each backtest date

### Phase 2: Delisted ticker prices (medium effort)
1. For each removed ticker from Phase 1, attempt yfinance download
2. Store available OHLCV in `predictor/price_cache/{ticker}.parquet` (same format as current)
3. Tag these tickers as `delisted: true` in metadata
4. Predictor training includes them in walk-forward windows where they were active

### Phase 3: Point-in-time labels (higher effort)
1. When computing sector-neutral labels, use the sector ETF that was correct at the time (sectors change)
2. Use point-in-time constituent lists to define the cross-sectional universe for rank normalization

## Decision

Start with Phase 1 (Wikipedia scraping) when the backtester has enough sample history to make survivorship bias the binding constraint on backtest credibility. Current priority is accumulating paper trading track record.

## Files to Modify (When Implementing)

- `alpha-engine-data/collectors/constituents.py` — add `scrape_sp500_changes()` function
- `alpha-engine-backtester/loaders/signal_loader.py` — read `historical_constituents.json`
- `alpha-engine-backtester/synthetic/predictor_backtest.py` — use point-in-time constituent lists
- `alpha-engine-predictor/training/train_handler.py` — include delisted tickers in training data
