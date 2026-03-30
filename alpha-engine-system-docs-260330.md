# Alpha Engine System Documentation — 2026-03-30

Comprehensive technical documentation covering all 5 modules: architecture, assumptions, stack, key packages, APIs, data schemas, and internal logic.

---

## Table of Contents

1. [Research Module](#1-research-module)
2. [Predictor Module](#2-predictor-module)
3. [Executor Module](#3-executor-module)
4. [Backtester Module](#4-backtester-module)
5. [Dashboard Module](#5-dashboard-module)

---

# 1. Research Module

**Repo:** `~/Development/alpha-engine-research`
**Runtime:** AWS Lambda (container image, Python 3.12)
**Schedule:** Weekly Saturday 06:00 UTC (EventBridge)

## 1.1 Overview

AI-powered investment research pipeline that maintains a rotating portfolio of 20-25 stocks from the S&P 500/400 (~900 stock universe). Uses LangGraph to orchestrate 6 parallel sector teams (each with Quant + Qual analysts) plus a Macro Economist, followed by a CIO investment committee review.

**Execution Flow:**
```
Handler (gate checks, idempotency)
  → fetch_data (load universe, prices, technicals, macro, prior theses)
  → [parallel] 6 Sector Teams + Macro Economist + Exit Evaluator
  → merge_results (fan-in)
  → score_aggregator (composite scoring)
  → cio_node (IC review: ADVANCE/HOLD/REJECT)
  → population_entry_handler (rotation logic)
  → consolidator (email markdown)
  → archive_writer (SQLite + S3)
  → email_sender (Gmail SMTP / SES)
```

## 1.2 Key Assumptions

- **S&P 500/400 universe loaded from Wikipedia** — survivorship bias acknowledged (current-only). Falls back to baked-in `data/constituents_cache.csv` if Wikipedia unavailable.
- **At least 80% of requested tickers must return price data** — enforced via `PriceFetchError` at `price_fetcher.py:123-127`. Below 80%, run fails fast.
- **All stocks have sector assignments** — fallback: `sector_map.get(ticker, "Unknown")` with default modifier 1.0.
- **Lambda SQLite is pre-3.24** — no window functions, no UPSERT. Uses UPDATE-then-INSERT pattern.
- **FMP free tier: 250 requests/day** — budget-aware with S3-persisted daily counter. Returns empty dict when exhausted.
- **Idempotency gate** — handler checks if `signals/{date}/signals.json` already exists. Skips if present unless `force=True`.
- **Population bounds are advisory** — target_size=25, min=20, max=30, but not hard-enforced.
- **Tenure protection prevents excessive churn** — challengers must beat incumbents by score delta scaled by tenure.

## 1.3 Stack & Key Packages

| Package | Version | Purpose |
|---------|---------|---------|
| langgraph | latest | State machine orchestration (6 parallel sector teams + macro) |
| anthropic | latest | LLM API (Haiku for per-stock, Sonnet for synthesis) |
| yfinance | >=0.2.30 | 3-month OHLCV for technical analysis |
| pandas | >=2.0 | DataFrames, technical indicators |
| exchange-calendars | >=4.5 | NYSE trading day calculations (staleness, tenure) |
| boto3 | >=1.26 | S3 read/write, SES email fallback |
| requests-ratelimiter | latest | yfinance rate limiting (2 req/5s) |

**LLM Models:**
- Per-stock agents: `claude-3-5-haiku-20241022` (~$0.10/2000 tokens)
- Strategic agents (CIO, Macro): `claude-3-5-sonnet-20241022` (~$3/2000 tokens)
- Token limits configurable via `universe.yaml`

## 1.4 External APIs

| API | Key Required | Rate Limit | Usage |
|-----|-------------|------------|-------|
| Anthropic Claude | ANTHROPIC_API_KEY | Per-plan | LLM agents (Haiku + Sonnet) |
| yfinance | No | 2 req/5s | 3-month OHLCV, 1-min intraday (alerts) |
| FMP | FMP_API_KEY | 250/day | Analyst consensus, price targets, EPS revisions |
| FRED | FRED_API_KEY | Unlimited (free) | Fed funds rate, treasury yields |
| EDGAR | EDGAR_IDENTITY (email) | ~3s/request | Form 4 insider filings |
| News RSS | No | None | Per-stock news sentiment |

## 1.5 Scoring System

### Technical Score (0-100) — Deterministic, No LLM

| Component | Weight | Logic |
|-----------|--------|-------|
| RSI(14) | 25% | Regime-aware thresholds: Bull VIX<15 → 80/30, Caution/Bear → 70/40, Neutral → 70/30 |
| MACD Signal | 20% | Bullish cross above zero=100, below zero=70; bearish cross=0-30 |
| Price vs MA50 | 20% | >5% above=80-100, at MA=50, >5% below=0-30 |
| Price vs MA200 | 20% | Same scale as MA50 |
| 20d Momentum | 15% | Percentile rank within S&P 500 |

Optional predictor enhancement: if GBM confidence >= 0.65, add `(p_up - p_down) * 10 * confidence` (capped +-10).

### Composite Score (0-100) — From LLM Agents

```
weighted_base = quant_score * w_quant + qual_score * w_qual    (default 0.50/0.50)
macro_shift   = (sector_modifier - 1.0) / 0.30 * 10           (range [-10, +10])
total_boost   = short_interest + institutional + PEAD + revisions + options + insider  (capped +-10)
final_score   = clamp(weighted_base + macro_shift + total_boost, [0, 100])
```

**Boost Sub-Scores:**
- Short Interest: SI > 20% → +2pts, SI > 40% → +4pts
- Institutional: 3+ funds adding → +3pts
- PEAD: EPS surprise days 1-20 post-earnings → +-5pts
- Revision: EPS revision streak → +-3pts
- Options: Put/call ratio + IV rank → +-3pts
- Insider: Form 4 buys → +-2pts

**Rating Thresholds:** BUY >= 55 | HOLD 40-55 | SELL < 40

**Conviction:** rising (2+ consecutive increases) | stable | declining (2+ decreases)

**Staleness:** Flagged if >= 5 trading days without >= 3pt score change.

## 1.6 Population Management

**Sector Allocation:**
- Overweight (modifier >= 1.05): 3 stocks min
- Market-weight (0.95-1.05): 2 stocks per sector
- Underweight (modifier <= 0.95): 1 stock min

**Rotation Rules:**
- Tenure tiers: 0-3d → +12pts to rotate, 3-10d → +8pts, 10-30d → +5pts, >30d → +3pts
- Weak picks: scored < 60 for 5+ runs override tenure protection
- Bounds: min 10% rotation (fresh ideas), max 40% (continuity)
- Exit triggers: score < 45 (immediate) or score < 40 (thesis collapse)

## 1.7 Database Schema (SQLite: research.db)

### investment_thesis
Primary score tracking — one row per (symbol, date, run_time).

| Column | Type | Description |
|--------|------|-------------|
| symbol | TEXT | Ticker |
| date | TEXT | YYYY-MM-DD |
| rating | TEXT | BUY/HOLD/SELL |
| score | REAL | Composite 0-100 |
| technical_score | REAL | Technical component |
| news_score | REAL | Quant sub-score |
| research_score | REAL | Qual sub-score |
| macro_modifier | REAL | Sector modifier applied |
| conviction | TEXT | rising/stable/declining |
| signal | TEXT | ENTER/HOLD/EXIT/REDUCE |
| score_velocity_5d | REAL | Score change rate |
| price_target_upside | REAL | % upside to price target |
| predicted_direction | TEXT | GBM prediction (if available) |
| prediction_confidence | REAL | GBM confidence |

### score_performance
Backtester input — tracks forward returns of scored signals.

| Column | Type | Description |
|--------|------|-------------|
| symbol | TEXT | Ticker |
| score_date | TEXT | Date scored |
| score | REAL | Score at signal |
| price_on_date | REAL | Entry price |
| return_10d / return_30d | REAL | Forward returns |
| spy_10d_return / spy_30d_return | REAL | SPY benchmark |
| beat_spy_10d / beat_spy_30d | INTEGER | 1 if stock beat SPY |

### macro_snapshots
Weekly macro state capture.

| Column | Type | Description |
|--------|------|-------------|
| date | TEXT | YYYY-MM-DD |
| market_regime | TEXT | bull/neutral/bear/caution |
| vix | REAL | VIX close |
| fed_funds_rate | REAL | Current fed funds |
| treasury_2yr / treasury_10yr | REAL | Yields |
| yield_curve_slope | REAL | 10yr - 2yr spread |
| sector_modifiers | TEXT | JSON: {sector: float} |
| sector_ratings | TEXT | JSON: {sector: rating_dict} |

### Other Tables
- **population**: Active holdings (symbol, sector, score, entry_date)
- **population_history**: Rotation audit trail (ENTRY/EXIT events)
- **active_candidates**: 3 rotating scanner slots
- **candidate_tenures**: Scanner slot audit trail
- **scanner_appearances**: Daily scan results
- **technical_scores**: Daily technical snapshot per ticker
- **stock_archive**: Analysis history per ticker
- **thesis_history**: Detailed per-run thesis (bull/bear case, catalysts, risks)
- **analyst_resources**: Tool tracking for evals (yfinance/fmp/edgar/news usage)
- **memory_episodes**: Lessons from failed signals (Phase 2)
- **memory_semantic**: Cross-agent observations (Phase 3)
- **predictor_outcomes**: GBM accuracy tracking

Schema versioned at v7 with migration tracking via `schema_version` table.

## 1.8 signals.json Output Schema

```json
{
  "date": "2026-03-30",
  "run_time": "2026-03-30T12:34:56Z",
  "signals": {
    "AAPL": {
      "ticker": "AAPL",
      "sector": "Technology",
      "signal": "ENTER",
      "rating": "BUY",
      "score": 75.3,
      "conviction": "rising",
      "bull_case": "...",
      "catalysts": ["Product event"],
      "price_target_upside": 12.5
    }
  },
  "population": [
    {"ticker": "AAPL", "sector": "Technology", "entry_date": "2026-03-23", "score": 75.3}
  ],
  "rotations": {
    "entries": [{"ticker": "AAPL", "score": 75.3, "reason": "CIO advance"}],
    "exits": [{"ticker": "XYZ", "score": 38.0, "reason": "Thesis collapse"}]
  },
  "macro": {
    "market_regime": "neutral",
    "sector_modifiers": {"Technology": 1.05},
    "sector_ratings": {"Technology": "overweight"}
  }
}
```

## 1.9 S3 Paths

| Path | Direction | Description |
|------|-----------|-------------|
| `signals/{date}/signals.json` | Write | Primary output — executor/predictor input |
| `archive/{category}/{ticker}/` | Write | Per-ticker theses (never overwritten) |
| `archive/macro/` | Write | Macro environment reports |
| `consolidated/{date}/morning.md` | Write | Email content |
| `research.db` | Write | SQLite database (overwrites) |
| `backups/research_{date}.db` | Write | Dated backup |
| `health/research.json` | Write | Health status |
| `config/research_params.json` | Read | Backtester-optimized params |
| `config/scoring_weights.json` | Read | Backtester-optimized weights |
| `predictor/predictions/latest.json` | Read | GBM predictions |

## 1.10 Price Alerts Lambda

Separate Lambda triggered every 30 min during market hours (9:30am-4:00pm ET).
- Detects moves >= 5% from prior close using yfinance 1-min bars
- 60-minute cooldown per ticker (in-memory, resets on cold start)
- Sends email alert via SES

## 1.11 Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| ANTHROPIC_API_KEY | Yes | Claude API |
| FMP_API_KEY | Yes | Financial Modeling Prep |
| FRED_API_KEY | Yes | Federal Reserve data |
| AWS_REGION | Yes | S3, SES |
| S3_BUCKET | Yes | Data store |
| GMAIL_APP_PASSWORD | Optional | Email primary path |
| EMAIL_SENDER | Optional | From address |
| EMAIL_RECIPIENTS | Optional | To addresses |
| EDGAR_IDENTITY | Optional | SEC User-Agent |

---

# 2. Predictor Module

**Repo:** `~/Development/alpha-engine-predictor`
**Runtime:** AWS Lambda (container image, Python 3.12, 3GB memory)
**Schedule:** Training weekly Saturday 07:00 UTC; Inference daily 6:15 AM PT

## 2.1 Overview

LightGBM gradient boosting model that predicts 5-day market-relative alpha for ~900 S&P 500/400 stocks. Produces directional predictions (UP/FLAT/DOWN) with confidence scores. High-confidence DOWN predictions trigger veto gate, overriding BUY signals in the executor.

**Two Flows:**
1. **Weekly Training:** Download 10y price cache → refresh stale parquets → build feature arrays → walk-forward validation → train GBM → evaluate IC gate → promote if passes → write slim cache for inference
2. **Daily Inference:** Load GBM weights from S3 → fetch prices (slim cache + daily delta) → compute features with cross-sectional rank normalization → batch predict → write predictions JSON → send morning briefing email

## 2.2 Key Assumptions

- **Sector-neutral labels:** `alpha = stock_5d_return - sector_etf_5d_return`. Removes sector beta.
- **No lookahead bias:** Time-based train/val/test splits with 5-day purge gaps.
- **Cross-sectional rank normalization:** Features ranked per-date across all tickers to prevent look-ahead bias. Requires >= 2 tickers per date.
- **Macro features excluded from GBM:** VIX, yields, gold, oil removed from training (correct practice — these are cross-sectional constants).
- **Alternative data defaults to neutral (0.0)** when unavailable — model treats missing data as neutral signal.
- **SPY.parquet must exist in price cache** — if missing, `return_vs_spy_5d` defaults to 0.0.
- **Minimum 265 rows of price history** per ticker — skipped silently if shorter.
- **Historical data rewritten weekly** with new split/dividend adjustments (yfinance auto_adjust=True).
- **Lambda /tmp limited to 512MB** — model weights ~30-50MB combined.

## 2.3 Stack & Key Packages

| Package | Purpose |
|---------|---------|
| lightgbm >= 4.0 | Gradient boosting (MSE + LambdaRank objectives) |
| pandas >= 2.0 | DataFrames, feature computation |
| numpy < 2 | Numerical arrays |
| yfinance >= 0.2.30 | Price fetching (10y full, 2y slim, daily delta) |
| pyarrow >= 14.0 | Parquet I/O (vectorized) |
| boto3 >= 1.26 | S3 model weights, predictions, cache |
| scipy >= 1.10 | Statistics (quantiles, correlations) — training only |
| optuna >= 3.5 | Hyperparameter tuning — training only |

## 2.4 Feature Engineering: 49 Features (36 GBM-Eligible)

### v1.0-v1.1: Price + Momentum (10 features)
| Feature | Formula |
|---------|---------|
| rsi_14 | Wilder's RSI(14), EWM com=13 |
| macd_cross | +1 bullish / -1 bearish / 0 no cross in 3d |
| macd_above_zero | 1.0 if MACD line > 0 |
| macd_line_last | Raw MACD line value |
| price_vs_ma50 | (close - ma50) / ma50 |
| price_vs_ma200 | (close - ma200) / ma200 |
| momentum_20d | (close / close.shift(20)) - 1 |
| momentum_5d | (close / close.shift(5)) - 1 |
| avg_volume_20d | 20d rolling mean volume / global mean |
| rel_volume_ratio | Current volume / 20d rolling mean |

### v1.1-v1.2: Market Context (7 features)
| Feature | Formula |
|---------|---------|
| dist_from_52w_high | (close - 252d max) / 252d max |
| dist_from_52w_low | (close - 252d min) / 252d min |
| return_vs_spy_5d | 5d momentum(stock) - 5d momentum(SPY) |
| sector_vs_spy_5d | 5d return(sector ETF) - 5d return(SPY) |
| vix_level | VIX close / 20.0 (excluded from GBM) |
| vol_ratio_10_60 | 10d realized vol / 60d realized vol |
| bollinger_pct | (close - lower_bb) / (upper_bb - lower_bb) |

### v1.3: Macro Regime (4 features, excluded from GBM)
yield_10y, yield_curve_slope, gold_mom_5d, oil_mom_5d

### v1.4: Technical Advanced (10 features)
price_accel, ema_cross_8_21, atr_14_pct, realized_vol_20d, volume_trend, obv_slope_10d, rsi_slope_5d, volume_price_div

### v1.5: Regime Interactions (5 features, cross-sectional)
mom5d_x_vix, rsi_x_vix, sector_x_trend, atr_x_vix, vol_trend_x_vix

### v2.0: Alternative Data (7 features)
| Feature | Source | Description |
|---------|--------|-------------|
| earnings_surprise_pct | FMP / yfinance | Most recent EPS surprise % (O10 PEAD) |
| days_since_earnings | FMP / yfinance | Recency, capped at 90d (O10) |
| eps_revision_4w | FMP | 4-week cumulative revision % (O11) |
| revision_streak | FMP | Consecutive same-direction weeks (O11) |
| put_call_ratio | yfinance / S3 cache | Log-transformed put/call OI ratio (O12) |
| iv_rank | yfinance / S3 cache | IV percentile rank 0-1 (O12) |
| iv_vs_rv | yfinance / S3 cache | Implied / realized vol ratio (O12) |

### v3.0: Fundamental (8 features, excluded from GBM until backtester validates)
pe_ratio, pb_ratio, debt_to_equity, revenue_growth_yoy, fcf_yield, gross_margin, roe, current_ratio

**GBM uses 36 features:** All v1.0-v1.5 + O10-O12 alternative (29 + 7), minus macro (5).

## 2.5 GBM Model

**Hyperparameters:**
```yaml
n_estimators: 1000
early_stopping_rounds: 30
objective: regression (MSE)
num_leaves: 127
min_child_samples: 50
max_depth: 5
learning_rate: 0.05
feature_fraction: 0.8
bagging_fraction: 0.8
lambda_l1: 0.10
lambda_l2: 0.05
```

**Label Construction:**
```
forward_return_5d = stock_return_5d - sector_etf_return_5d
UP:   forward_return > +2% (default threshold)
DOWN: forward_return < -2%
FLAT: in between
Labels clipped to +-25% (handles gaps, splits)
```

**Training Pipeline:**
1. Build arrays: 36 features, forward_return_5d labels
2. Time-based 70/15/15 split with 5-day purge gaps
3. Train with early stopping on validation set
4. Compute test IC (Pearson correlation of predicted vs actual)
5. Walk-forward validation: 15 expanding-window folds, 6-month test windows
   - Gates: median IC >= 0.01, 60%+ folds positive
6. Upload if IC >= 0.02 (production gate)

**Ensemble Mode (optional):**
- Both MSE and LambdaRank objectives
- LambdaRank: y converted to relevance grades (0-4 quintiles)
- Blend predictions at inference time

## 2.6 Veto Gate

```
IF predicted_direction == "DOWN" AND prediction_confidence >= veto_threshold:
    Override BUY → HOLD (block entry)
```

**Threshold Management:**
- Base: `MIN_CONFIDENCE = 0.60` from config
- Override: `config/predictor_params.json` on S3 (tuned by backtester)
- Regime adjustment (optional): bear -0.10, caution -0.05, neutral 0, bull +0.05
- Clamped to [0.40, 0.90]

## 2.7 Price Cache System

| Cache Type | S3 Path | History | Refresh | Purpose |
|-----------|---------|---------|---------|---------|
| Full | `predictor/price_cache/{ticker}.parquet` | 10 years | Weekly (training) | Training data, full rewrite |
| Slim | `predictor/price_cache_slim/{ticker}.parquet` | 2 years | After weekly training | Inference Lambda input |
| Daily | `predictor/daily_closes/{date}.parquet` | 1 day | Daily (after close) | Delta for slim cache |

**Inference Price Flow:** Load slim cache → load daily_closes → splice → compute features → predict.

## 2.8 predictions.json Output Schema

```json
{
  "date": "2026-03-30",
  "model_version": "gbm_v1.0",
  "model_hit_rate_30d": 0.55,
  "n_predictions": 450,
  "predictions": [
    {
      "ticker": "AAPL",
      "predicted_direction": "UP",
      "predicted_alpha": 0.0245,
      "prediction_confidence": 0.78,
      "combined_rank": 6,
      "watchlist_source": "tracked",
      "sector": "Information Technology"
    }
  ]
}
```

## 2.9 Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| AWS_REGION | Yes | S3, SES |
| S3_BUCKET | Yes | Price cache, weights, predictions |
| EMAIL_SENDER | Optional | Morning briefing |
| EMAIL_RECIPIENTS | Optional | Briefing recipients |
| GMAIL_APP_PASSWORD | Optional | Gmail SMTP primary |
| XDG_CACHE_HOME | Auto (/tmp) | yfinance cache dir |

---

# 3. Executor Module

**Repo:** `~/Development/alpha-engine`
**Runtime:** EC2 t3.small (trading instance)
**Schedule:** EC2 start 6:20 AM PT (EventBridge), main.py on boot, daemon.py on boot, EOD 1:20 PM PT, EC2 stop 1:30 PM PT

## 3.1 Overview

Two-phase order execution system. **Phase 1 (Morning Batch):** Reads signals from S3, applies risk rules and position sizing, writes order book. Places NO orders. **Phase 2 (Intraday Daemon):** Sole order executor — uses technical triggers for entries, executes exits immediately at market open.

**Boot Sequence (systemd):**
```
boot-pull.service → git pull
ibgateway.service → Docker IB Gateway
alpha-engine-morning.service → main.py (order book planner)
alpha-engine-daemon.service → daemon.py (order executor)
alpha-engine-eod.timer → 1:20 PM PT (EOD reconcile)
```

## 3.2 Key Assumptions

- **Paper account only** — daemon safety check: account ID must start with "D". Hard exit if connected to live account.
- **IB Gateway on port 4002** — main.py uses clientId=1, daemon uses clientId=2.
- **Delayed market data (15-min)** — free IB data via `reqMarketDataType(3)`.
- **Signals from most recent trading day** — falls back up to 5 calendar days (skips weekends).
- **All exits pass risk guard** — reducing exposure is never blocked.
- **Order book is JSON on disk** — atomic POSIX rename for writes, no file-level locking.
- **ATR required for trailing stops** — if ATR unavailable, position entered without stop (known gap).
- **Single-threaded execution** — daemon polls every 60 seconds sequentially.

## 3.3 Stack & Key Packages

| Package | Purpose |
|---------|---------|
| ib_insync ~= 0.9.86 | IB Gateway client (positions, orders, prices) |
| boto3 ~= 1.34 | S3 signals, trades backup |
| yfinance ~= 0.2.54 | SPY close for daily alpha, historical OHLCV for technicals |
| pandas ~= 2.2 | DataFrames, CSV exports |
| anthropic ~= 0.40 | Haiku for EOD position rationale narratives |
| exchange-calendars ~= 4.5 | Market calendar (optional) |

## 3.4 Risk Guard — All Rules

| Rule | Threshold | Effect |
|------|-----------|--------|
| Score minimum | score >= 57 | Block entry |
| Conviction gate | conviction in [rising, stable] | Block declining |
| Graduated drawdown | 0-3%: 1.0x, 3-5%: 0.5x, 5-8%: 0.25x, >8%: HALT | Scale sizing / circuit breaker |
| Max single position | 8% NAV (2.5% in bear) | Cap position size |
| Bear sector block | bear regime + underweight sector | Block entry |
| Sector exposure | <= 25% per sector | Cap sector weight |
| Total equity | <= 90% in equities | Keep 10% cash |
| Cross-ticker correlation | mean Pearson corr <= 0.80 (60d rolling) | Block correlated entries |

## 3.5 Position Sizing Formula

```
base_weight     = 1 / n_enter_today
sector_adj      = OW:1.10 / MW:1.00 / UW:0.75
conviction_adj  = 0.50 if declining, else 1.00
upside_adj      = 0.50 if upside < 5%, else 1.00
dd_multiplier   = from drawdown tier (1.00 / 0.50 / 0.25 / 0.00)
atr_adj         = min(1.5, max(0.5, target_risk_pct / atr_pct))
confidence_adj  = 0.70 + 0.60 * prediction_confidence  → [0.70, 1.30]
staleness_adj   = max(0.70, 1.0 - 0.03 * signal_age_days)
earnings_adj    = 0.50 if days_to_earnings <= 5, else 1.00

raw_weight     = base * sector * conviction * upside * dd * atr * confidence * staleness * earnings
position_weight = min(raw_weight, max_position_pct)
dollar_size    = NAV * position_weight
shares         = floor(dollar_size / current_price)
```

## 3.6 Entry Triggers (Intraday, OR Logic)

| Trigger | Default | Fires When |
|---------|---------|------------|
| Pullback | 2% | (day_high - current) / day_high >= 2% |
| VWAP Discount | 0.5% | (vwap - current) / vwap >= 0.5% |
| Support Bounce | 1% | 0 <= (current - support) / support <= 1% |
| Time Expiry | 3:30 PM ET | Current time >= 15:30 ET |

Support level: minimum low over past 20 days (computed once at morning batch, not updated intraday).

## 3.7 Exit Management

### Phase 0: Urgent Exits (market open)
- Research EXIT/REDUCE/COVER signals executed immediately
- Short-sell prevention: validates position exists before selling

### Phase 1+2: Intraday Exits (daemon monitoring)

| Rule | Default | Action |
|------|---------|--------|
| ATR Trailing Stop | highest_high - ATR * 2.0 | EXIT |
| Profit Taking | gain >= 8% | REDUCE 50% |
| Intraday Collapse | (day_high - current) / day_high >= 5% | EXIT |
| Time-Based Tightening | After 3 days held, ATR multiple → 1.5 | Tighten stop |

### Strategy Layer Exits (morning batch)

| Rule | Default | Action |
|------|---------|--------|
| ATR Trailing Stop | highest_high - ATR(14) * multiplier | EXIT |
| Time Decay | 10 days held (if Research = HOLD) | EXIT |
| Profit Taking | unrealized gain >= 25% | REDUCE |
| Momentum Exit | 20d momentum < -15% AND RSI < 30 | EXIT |
| Sector-Relative Veto | stock outperforms sector ETF by 5%+ | VETO the ATR exit |

## 3.8 Order Book Schema

```json
{
  "date": "2026-03-30",
  "approved_entries": [{
    "ticker": "AAPL", "signal": "ENTER", "shares": 100,
    "current_price": 230.50, "position_pct": 0.075,
    "atr_value": 4.25,
    "triggers": {"pullback_pct": 0.02, "vwap_discount": 0.005, "support_level": 228.00},
    "research_score": 75, "research_conviction": "rising",
    "predicted_direction": "UP", "prediction_confidence": 0.72,
    "status": "pending"
  }],
  "urgent_exits": [{
    "ticker": "TSLA", "signal": "EXIT", "shares": 50,
    "reason": "research_signal", "status": "pending"
  }],
  "active_stops": [{
    "ticker": "AAPL", "entry_price": 230.50, "current_stop": 225.00,
    "trail_atr": 4.25, "atr_multiple": 2.0, "high_water": 235.00,
    "entry_date": "2026-03-30", "shares": 100
  }]
}
```

## 3.9 Trade Logger (SQLite: trades.db)

### trades table

| Column | Type | Description |
|--------|------|-------------|
| trade_id | TEXT PK | UUID |
| date | TEXT | Trade date |
| ticker | TEXT | Symbol |
| action | TEXT | ENTER/EXIT/REDUCE/COVER |
| shares | INTEGER | Quantity |
| fill_price | REAL | Execution price |
| research_score | REAL | Signal score at order |
| research_conviction | TEXT | Conviction at order |
| predicted_direction | TEXT | GBM prediction |
| prediction_confidence | REAL | GBM confidence |
| entry_trade_id | TEXT | FK to entry (for EXIT/REDUCE) |
| realized_pnl | REAL | (fill - entry) * shares |
| realized_alpha_pct | REAL | Return - SPY return during hold |
| days_held | INTEGER | Trading days between entry and exit |
| trigger_type | TEXT | pullback/vwap/support/time_expiry |
| slippage_vs_signal | REAL | Fill price vs signal price |

### eod_pnl table

| Column | Type | Description |
|--------|------|-------------|
| date | TEXT PK | Trading date |
| portfolio_nav | REAL | End-of-day NAV |
| daily_return_pct | REAL | Portfolio daily return |
| spy_return_pct | REAL | SPY daily return |
| daily_alpha_pct | REAL | Portfolio - SPY |
| positions_snapshot | TEXT | JSON of current holdings |

## 3.10 EOD Reconciliation (1:20 PM PT)

1. Fetch NAV and positions from IB Gateway
2. Compute daily return vs SPY
3. Sector attribution: weight * contribution per sector
4. Roundtrip statistics (win rate, avg alpha, avg days held)
5. Position narratives via Haiku LLM (fallback to templates)
6. Send EOD email (SES)
7. Backup trades.db to S3 (dated + latest)
8. Export CSV: trades_full.csv, eod_pnl.csv

## 3.11 Config (risk.yaml)

```yaml
max_position_pct: 0.08          # Per-position cap
max_sector_pct: 0.25            # Per-sector cap
max_equity_pct: 0.90            # Total equity cap
bear_max_position_pct: 0.025    # Bear regime cap
drawdown_circuit_breaker: 0.08  # -8% NAV halt
min_score_to_enter: 57          # Entry gate

strategy:
  exit_manager:
    atr_period: 14
    atr_multiplier: 3.0
    time_decay_reduce_days: 5
    time_decay_exit_days: 10
  graduated_drawdown:
    tiers:
      - [-0.03, 1.00]    # 0-3%: full sizing
      - [-0.05, 0.50]    # 3-5%: half
      - [-0.08, 0.25]    # 5-8%: quarter

intraday:
  poll_interval_sec: 60
  entry_triggers:
    pullback_pct: 0.02
    vwap_discount_pct: 0.005
    support_pct: 0.01
    expiry_time: "15:30"
  exit_rules:
    trailing_stop_atr_multiple: 2.0
    profit_take_pct: 0.08
    collapse_pct: 0.05
```

---

# 4. Backtester Module

**Repo:** `~/Development/alpha-engine-backtester`
**Runtime:** AWS EC2 spot instance (c5.large, ~$0.01/week)
**Schedule:** Weekly Saturday 08:00 UTC, launched from always-on EC2

## 4.1 Overview

Closes the feedback loop by validating signal quality, optimizing parameters, and auto-writing 4 S3 config files that all downstream modules read on cold-start:

1. `config/scoring_weights.json` → Research (quant/qual balance)
2. `config/executor_params.json` → Executor (risk/strategy params)
3. `config/predictor_params.json` → Predictor (veto threshold)
4. `config/research_params.json` → Research (signal boost params, deferred until 200+ samples)

**Pipeline Modes:**

| Mode | Purpose |
|------|---------|
| signal-quality | Accuracy metrics, regime analysis, attribution, weight optimization |
| simulate | Replay signals through executor, VectorBT portfolio simulation |
| param-sweep | 60-trial random search over 6 executor params |
| predictor-backtest | 10y synthetic signals via GBM, portfolio simulation |
| all | All modes sequentially |

## 4.2 Key Assumptions

- **Score performance backfill via yfinance** — if yfinance fails, accuracy metrics computed on incomplete data.
- **VectorBT treats NaN prices as 0 return** — tickers with gaps beyond 5-day forward-fill may show artificial gains.
- **60 random trials ≈ 95% confidence** of finding top-5% param combo from 1,728-point grid.
- **Holdout validation uses last 30% of dates** — requires sufficient history for meaningful test.
- **Attribution uses Pearson correlation** — assumes linear relationship between sub-scores and outcomes.
- **BH FDR correction** — conservative but may pass weak correlations with only 50 rows.
- **Spot instance is one-time** — if interrupted, waits until next weekly run (no retry).
- **Weight optimizer blends toward current** — at 100 samples only 20% data-driven, 80% current weights.

## 4.3 Stack & Key Packages

| Package | Purpose |
|---------|---------|
| vectorbt 0.26.1 | Portfolio simulation (Sharpe, drawdown, alpha) |
| pandas >= 2.0 | DataFrames, SQL joins, time series |
| lightgbm >= 4.0 | GBM scorer (imported for predictor backtest) |
| yfinance >= 0.2.54 | Price fallback, OHLCV download |
| pyarrow >= 14.0 | Parquet I/O for predictor cache |
| boto3 >= 1.34 | S3 client |
| scipy >= 1.10 | Statistics (Wilson CI, Pearson correlation) |

## 4.4 Signal Quality Analysis

**Metrics:**
- 10d/30d accuracy: % of BUY signals beating SPY over forward window
- Wilson Score CI (95%): binomial proportion confidence interval
- Average alpha: mean(signal_return - SPY_return) per horizon

**Stratification:**
- Score buckets: [60-70), [70-80), [80-90), [90-100]
- Market regime: bull/neutral/bear/caution (from macro_snapshots)
- BH FDR correction across all bucket/regime p-values

**Activation:** Requires >= 30 rows with beat_spy_10d populated.

## 4.5 Attribution Analysis

Correlates sub-scores (quant, qual) with outperformance outcomes:
1. Load sub-scores from signals.json merged with score_performance
2. Compute Pearson r for each (sub-score, target) pair
3. Apply BH FDR correction (alpha=0.05)
4. Rank sub-scores by absolute correlation
5. Feed into weight optimizer

**Data requirement:** >= 50 populated rows (Week 8+ for robustness).

## 4.6 Weight Optimizer

**Algorithm:**
1. Correlate each sub-score with beat_spy_10d/30d on 70% train set
2. Derive pure weights: `pure[s] = weighted_r[s] / sum(weighted_r)`
3. Blend toward current: `suggested[s] = current * (1-blend) + pure * blend`
4. Blend ramps with sample size: 100 samples → 20%, 500 → 50%
5. OOS validation on 30% test set: degradation must be < 20%
6. Stability check: compare with prior 3 weeks of weight history

**Guardrails (all must pass):**
- Confidence >= "medium" (>= 50 samples)
- No single weight changes by > 10%
- At least one weight changes by >= 3%
- OOS validation passes
- Previous config backed up before overwrite

## 4.7 Executor Optimizer

**6 Parameters Swept (1,728 grid):**

| Parameter | Values | Impact |
|-----------|--------|--------|
| min_score | [65, 70, 75, 80] | Entry gate (most impactful) |
| max_position_pct | [0.05, 0.10, 0.15] | Per-position cap |
| atr_multiplier | [2.0, 2.5, 3.0, 4.0] | Stop distance |
| time_decay_reduce_days | [5, 7, 10] | When to reduce |
| time_decay_exit_days | [10, 15, 20] | When to force-exit |
| profit_take_pct | [0.15, 0.20, 0.25, 0.30] | Profit-taking threshold |

**Ranking:** `score = sharpe_ratio - 0.5 * abs(max_drawdown)`

**Gates:**
- Improvement >= 10% over baseline Sharpe
- Best combo has >= 50 total trades
- Holdout Sharpe / train Sharpe >= 50%

## 4.8 Veto Analysis

Sweeps predictor confidence thresholds [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
1. Filter to DOWN predictions only
2. For each threshold: compute precision, lift, missed alpha
3. Score: `precision - 0.30 * (missed_alpha / max_missed_alpha)`
4. Select threshold with max score

**Gates:** >= 10 veto decisions per threshold, >= 30 predictions total, lift >= 5% above base rate.

## 4.9 Synthetic Predictor Backtest (10-Year)

1. Load OHLCV cache (10y full or 2y slim from S3)
2. Compute 29 technical features per ticker (skip if < 265 rows)
3. Download GBM model from S3
4. Batch inference: stack features → single LightGBM predict call per date
5. Build synthetic signals (top 20 per day by alpha score)
6. Build price matrix (forward-fill 5 days, back-fill leading NaNs)
7. Run executor simulation → VectorBT portfolio
8. Param sweep (60 trials) on synthetic signals

## 4.10 S3 Paths

**Read:**
| Path | Purpose |
|------|---------|
| `signals/{date}/signals.json` | Signal dates + sub-scores |
| `research.db` | Score performance, macro snapshots |
| `predictor/predictions/{date}.json` | Veto analysis |
| `predictor/price_cache/*.parquet` | 10y cache (full backtest) |
| `predictor/price_cache_slim/*.parquet` | 2y cache (inference) |
| `predictor/weights/gbm_latest.txt` | GBM model |
| `config/scoring_weights.json` | Current weights baseline |
| `config/executor_params.json` | Current executor params |
| `config/predictor_params.json` | Current veto threshold |

**Write (auto-update on success):**
| Path | Source |
|------|--------|
| `config/scoring_weights.json` | Weight optimizer |
| `config/executor_params.json` | Executor optimizer |
| `config/predictor_params.json` | Veto analysis |
| `config/*_previous.json` | Backup before overwrite |
| `config/*_history/{date}.json` | Dated archive |
| `backtest/{date}/report.md` | Weekly report |
| `backtest/{date}/metrics.json` | Summary stats |
| `backtest/{date}/signal_quality.csv` | Accuracy by bucket |
| `predictor/metrics/latest.json` | Rolling model metrics |

## 4.11 Spot Instance Infrastructure

```bash
# spot_backtest.sh lifecycle:
1. Launch c5.large spot (~$0.03/hr)
2. Bootstrap: Python 3.12, clone 3 repos, install deps, SCP configs
3. Download slim cache from S3 (~25MB)
4. Run: python backtest.py --mode all --upload
5. Self-terminate on completion (cleanup trap)

# Cron on always-on EC2:
0 8 * * 6  bash infrastructure/spot_backtest.sh >> /var/log/backtester.log
```

---

# 5. Dashboard Module

**Repo:** `~/Development/alpha-engine-dashboard`
**Runtime:** EC2 t3.micro (1GB RAM + 1GB swap)
**Stack:** Streamlit + Plotly + Pandas
**Access:** SSH tunnel (port 8501) or Cloudflare Access

## 5.1 Overview

Read-only monitoring dashboard with 9+ pages. Never writes to S3 or databases. All data flows inbound from Research (signals, research.db), Executor (trades, eod_pnl), and Predictor (predictions, metrics).

## 5.2 Key Assumptions

- **EC2 IAM role provides S3 access** — no hardcoded credentials.
- **1GB RAM constraint** — mitigated by 1GB swap, 300MB memory limit per Streamlit service, dual-instance approach.
- **SQLite research.db cached for session lifetime** — `@st.cache_resource` with no TTL. May stale if network hiccup closes connection.
- **Percentage scale auto-detection** — "if mean > 1.0 assume percent" can misfire on near-zero returns.
- **S3 errors return None uniformly** — all failure types (timeout, permission, missing) look identical to pages.

## 5.3 Stack & Key Packages

| Package | Purpose |
|---------|---------|
| streamlit >= 1.32 | Web UI, multi-page routing, caching |
| pandas >= 2.0 | DataFrame ops, CSV/JSON parsing |
| plotly >= 5.18 | Interactive charts (bar, line, scatter, heatmap, pie) |
| boto3 >= 1.34 | S3 data loading |
| pyyaml >= 6.0 | Config parsing |

## 5.4 Pages & Data Sources

### Home (app.py)
System health snapshot. Shows pipeline activity (research population, predictor vetoes, risk guard decisions, trades), current holdings with unrealized P&L, alpha chart, market context.

**Data:** eod_pnl.csv, trades_full.csv, signals.json, predictions/latest.json, order_book_summary.json, population/latest.json, macro_snapshots table.

### 1_Portfolio
NAV vs SPY cumulative return (shaded outperformance), drawdown chart with circuit breaker threshold, current positions, sector allocation donut with concentration warnings (>25% red, >20% amber), sector rotation stacked area.

**Data:** eod_pnl.csv, trades_full.csv, signals.json.

### 2_Signals
Signal universe table with filters (sector, signal type, min score). Ticker detail expander with sub-score visualization. Veto status display (VETOED if DOWN + confidence >= threshold).

**Data:** signals.json, predictions.json, predictor_params.json, macro_snapshots.

### 3_Signal_Quality
Rolling 4-week accuracy trends (10d/30d), accuracy by score bucket with Wilson CI, accuracy by market regime, alpha by regime, scoring weight history.

**Data:** score_performance table, macro_snapshots, eod_pnl.csv, scoring_weights_history/.

### 4_Research
Per-ticker score history with sub-score lines and signal markers. Investment thesis display. Symbol selector (top 10 by recent score).

**Data:** investment_thesis table, score_performance table.

### 5_Backtester
Parameter sweep heatmap (min_score vs max_position_pct, color by Sharpe), signal quality by bucket, sub-score attribution, weight recommendations, raw report markdown.

**Data:** backtest/{date}/metrics.json, param_sweep.csv, signal_quality.csv, attribution.json, report.md.

### 6_Trade_Log
Paginated trade audit trail (25/page) with filters (date, action, regime, sector, score). Outcome join showing beat_spy_10d/30d. CSV export.

**Data:** trades_full.csv, score_performance table.

### 7_Predictor
Model health badge (green >= 52%, amber 48-52%, red < 48%), 30d/90d rolling hit rate drift chart, mode history, today's predictions with signal disagreement analysis.

**Data:** predictor/metrics/latest.json, predictor_outcomes table, mode_history.json, predictions/latest.json.

### 8_Slippage
Execution quality analysis: fill price vs order price in basis points. Distribution histogram, time series by action type, breakdown by action/regime/sector.

**Data:** trades_full.csv (fill_price, price_at_order columns).

### 9_Data_Inventory
Data pipeline health checks: module status cards, data volume growth, SQLite table counts, S3 object counts, staleness alerts, gap detection.

**Data:** health/{module}.json, data_manifest/{module}/, SQLite row counts, S3 ListObjects.

## 5.5 Caching Strategy

| Data Type | TTL | Decorator |
|-----------|-----|-----------|
| Signals | 15 min | `@st.cache_data(ttl=900)` |
| Trades | 15 min | `@st.cache_data(ttl=900)` |
| Research | 1 hour | `@st.cache_data(ttl=3600)` |
| Backtest | 1 hour | `@st.cache_data(ttl=3600)` |
| DB connection | Session lifetime | `@st.cache_resource` |
| Predictions | Not cached | Refreshes every load |

## 5.6 S3 Paths Read

| Path | TTL | Usage |
|------|-----|-------|
| `signals/{date}/signals.json` | 15min | Signals, Home, Portfolio pages |
| `trades/eod_pnl.csv` | 15min | Home, Portfolio, Signal Quality |
| `trades/trades_full.csv` | 15min | Home, Trade Log, Slippage |
| `predictor/predictions/{date}.json` | None | Signals, Predictor pages |
| `predictor/metrics/latest.json` | None | Predictor page |
| `population/latest.json` | 1hr | Home page |
| `config/scoring_weights.json` | 1hr | Signal Quality page |
| `config/predictor_params.json` | None | Signals page (veto threshold) |
| `backtest/{date}/*` | 1hr | Backtester page |
| `health/{module}.json` | None | Data Inventory |
| `research.db` | Session | Multiple pages (SQLite queries) |

## 5.7 Memory Optimization

- 1GB swap file prevents OOM kills
- systemd `MemoryMax=300M` per Streamlit service (if configured)
- Dual-instance: port 8501 (private, all pages) + port 8502 (public, portfolio only)
- TTL caching prevents stale data accumulation (most data expires within 15 min - 1 hr)
- Trade log pagination (25 rows/page) but entire CSV loaded into memory

## 5.8 Deployment

```ini
# /etc/systemd/system/dashboard.service
[Service]
ExecStart=streamlit run app.py --server.port=8501 --server.address=127.0.0.1 --server.headless=true
Restart=always
RestartSec=10
```

Access via SSH tunnel: `ssh -L 8501:localhost:8501 -N ec2-user@<EC2-IP>`

---

# Cross-Module Data Flow Summary

```
                    SATURDAY
                    ========
Research Lambda (06:00 UTC)
  → signals/{date}/signals.json  ─────────────────┐
  → research.db (S3)                               │
  → archive/{category}/{ticker}/                   │
                                                    │
Predictor Training (07:00 UTC)                     │
  → predictor/weights/gbm_latest.txt               │
  → predictor/price_cache_slim/*.parquet            │
                                                    │
Backtester (08:00 UTC, spot instance)              │
  ← signals.json, research.db, predictions,        │
    price_cache, current configs                    │
  → config/scoring_weights.json ──→ Research       │
  → config/executor_params.json ──→ Executor       │
  → config/predictor_params.json ─→ Predictor      │
  → backtest/{date}/* ────────────→ Dashboard      │
                                                    │
                    WEEKDAYS                        │
                    ========                        │
Predictor Inference (6:15 AM PT)                   │
  ← signals.json, slim cache, daily_closes         │
  → predictor/predictions/{date}.json ─────────┐   │
                                                │   │
Executor Morning (6:25 AM PT)                   │   │
  ← signals.json ──────────────────────────────┤───┘
  ← predictions.json ──────────────────────────┘
  → order_book.json (local)

Executor Daemon (6:30 AM - 4:15 PM ET)
  → trades.db (local)
  → trades/trades_full.csv (S3)

Executor EOD (1:20 PM PT)
  → trades/eod_pnl.csv (S3)
  → trades.db backup (S3)

Dashboard (always-on)
  ← All S3 paths above (read-only)
  ← research.db (read-only)
```
