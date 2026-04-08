# Alpha Engine System Documentation — 2026-04-08

Comprehensive technical documentation covering all 6 modules: architecture, assumptions, stack, key packages, APIs, data schemas, and internal logic.

> Updated 2026-04-08. Changes since prior version (2026-04-03): ArcticDB migration, private config repo, EOD Step Function, SSM secrets, VWAP trigger fix, graduated time expiry, predictor feedback loop, evaluation framework.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Research Module](#1-research-module)
3. [Predictor Module](#2-predictor-module)
4. [Executor Module](#3-executor-module)
5. [Backtester Module](#4-backtester-module)
6. [Dashboard Module](#5-dashboard-module)
7. [Data Module](#6-data-module)
8. [Cross-Module Data Flow](#cross-module-data-flow-summary)

---

# System Architecture

Six modules run on AWS (Lambda + EC2), connected through a shared S3 bucket (`alpha-engine-research`). Orchestrated by **two AWS Step Functions** — one for the weekly Saturday pipeline and one for the daily weekday pipeline. Both are triggered by EventBridge rules and enforce sequential execution with timeout guards.

All legacy EventBridge/cron triggers were removed on 2026-04-02. Only two independent triggers remain: `alpha-engine-stop-trading` (weekday 1:30 PM PT) and `alpha-research-alerts` (every 30 min M-F).

## Orchestration: Step Functions

```
WEEKLY (Saturday) — Step Function: alpha-engine-saturday-pipeline
  EventBridge: cron(0 0 ? * SAT *)  →  Sat 00:00 UTC (Fri 5-8 PM PT)
  ┌─ DataPhase1 (EC2 SSM, 30 min)       → prices, macro, constituents, universe returns
  ├─ FeatureStoreCompute (EC2 SSM)       → 54 features for 903 tickers (~20s)
  ├─ RAGIngestion (EC2 SSM, 30 min)      → SEC filings, 8-Ks, earnings, theses → research KB
  ├─ Research (Lambda, 15 min)           → signals/{date}/signals.json
  ├─ DataPhase2 (Lambda, 10 min)         → alternative data for promoted tickers
  ├─ PredictorTraining (EC2 spot, 90 min)→ meta-model retrain + slim cache update
  ├─ DriftDetection (EC2 SSM, non-blocking) → feature drift z-scores, prediction clustering
  ├─ Backtester (EC2 spot, 120 min)      → signal quality + param optimization → S3 configs
  └─ NotifyComplete (SNS)                → success email

DAILY (weekdays) — Step Function: alpha-engine-weekday-pipeline
  EventBridge: cron(5 13 ? * MON-FRI *)  →  6:05 AM PT
  ┌─ CheckTradingDay (Lambda)            → NYSE holiday check (trading_calendar.py, holidays through 2030)
  ├─ DailyData (EC2 SSM)                → predictor/daily_closes/{date}.parquet + macro
  ├─ FeatureStoreCompute (EC2 SSM)       → pre-compute 54 features for inference
  ├─ PredictorInference (Lambda)         → predictor/predictions/{date}.json + morning email
  └─ StartExecutorEC2 (EC2 API)          → trading instance boots
  ~6:25 AM PT      Executor (EC2)        → order book planner (systemd, on boot)
  ~6:30 AM PT      Daemon (EC2)          → intraday order executor (systemd, on boot)

EOD (weekdays) — Step Function: alpha-engine-eod-pipeline
  EventBridge: cron(20 20 ? * MON-FRI *)  →  1:20 PM PT
  ┌─ EODReconcile (EC2 SSM)              → NAV / alpha / positions report
  └─ StopTradingEC2 (EC2 API)            → trading instance shuts down

  Independent (not in Step Function):
    Every 30 min     Research alerts (Lambda) → intraday price alert emails

ALWAYS-ON:
  Dashboard (EC2 micro)  → Streamlit read-only monitoring
```

## Dependencies

- DataPhase1 runs first in both pipelines — daily collects today's OHLCV + macro, weekly refreshes full price cache
- FeatureStoreCompute runs after data collection, before any consumer (Research, Predictor)
- Research and Predictor Training are **independent** — no data flows between them. They run sequentially in the Step Function to spread API load, not because of a data dependency.
- Backtester depends on both Research (signal history) and Predictor Training (model weights)
- Daily: CheckTradingDay → DailyData → FeatureStoreCompute → PredictorInference → StartExecutorEC2
- NYSE holiday check short-circuits the entire daily pipeline on non-trading days

## EC2 Infrastructure

| Instance | Type | Runtime | Purpose |
|----------|------|---------|---------|
| Micro | t3.micro (1GB + 1GB swap) | 24/7 | Dashboard, data collection (SSM), feature store compute, backtester spot launcher |
| Trading | t3.small | Market hours only | IB Gateway (Docker), executor, daemon, EOD reconcile |

**Trading instance boot sequence (systemd, no cron):**
```
boot-pull.service → git pull latest code
ibgateway.service → Docker IB Gateway (TOTP 2FA)
alpha-engine-morning.service → main.py (order book planner)
alpha-engine-daemon.service → daemon.py (order executor)
alpha-engine-eod.timer → 1:20 PM PT (EOD reconcile)
alpha-engine-daemon.timer → 9:29 AM ET (safety-net re-trigger)
```

The `boot-pull.service` ensures the trading instance always runs the latest committed code without manual SSH deployment.

---

# 1. Research Module

**Repo:** `~/Development/alpha-engine-research`
**Runtime:** AWS Lambda (container image, Python 3.12)
**Schedule:** Weekly Saturday via Step Function (after DataPhase1 + FeatureStoreCompute + RAGIngestion)

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
  "date": "2026-04-03",
  "run_time": "2026-04-03T12:34:56Z",
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

## 1.12 RAG / Vector Database

Research agents use retrieval-augmented generation (RAG) to ground LLM analysis in real SEC filings, earnings transcripts, and historical theses. The RAG system uses a hosted vector database for semantic search.

### Vector Store: Neon PostgreSQL + pgvector

| Component | Detail |
|-----------|--------|
| **Database** | Neon PostgreSQL (free tier, 0.5 GB) with `pgvector` extension |
| **Embedding model** | Voyage `voyage-3-lite` (1024 dimensions) |
| **Index** | HNSW on `rag.chunks.embedding` (cosine similarity) |
| **Connection** | Pooled via Neon's built-in pgbouncer; short-lived connections per query |
| **Cost** | ~$0.10/mo Voyage embeddings; Neon free tier |

### Schema

**`rag.documents`** — One row per ingested document:
- `id` (UUID PK), `ticker`, `sector`, `doc_type` (10-K, 10-Q, 8-K, earnings_transcript, thesis)
- `source` (sec_edgar, finnhub, alpha_engine), `filed_date`, `title`, `url`
- Unique constraint: `(ticker, doc_type, filed_date, source)` — prevents duplicate ingestion

**`rag.chunks`** — Embedded text chunks (~400 tokens each):
- `id` (UUID PK), `document_id` (FK → documents), `chunk_index`, `content`, `section_label`
- `embedding` vector(1024) — Voyage voyage-3-lite embedding
- HNSW index for cosine similarity search

### Ingestion Pipelines (weekly, in alpha-engine-data)

| Pipeline | Source | Data | Lookback |
|----------|--------|------|----------|
| SEC 10-K/10-Q | EDGAR API | Risk Factors, MD&A, Business, Market Risk sections | 2 years |
| 8-K Material Events | EDGAR API | Items 1.01, 2.01, 2.02, 2.05, 4.01, 5.02, 7.01, 8.01 | 1 year |
| Earnings Transcripts | Finnhub API | Prepared remarks + Q&A (speaker-labeled) | Latest 8 per ticker |
| Thesis History | S3 signals.json | Research-generated thesis summaries | 14 days |
| Filing Change Detection | RAG DB (internal) | Consecutive filing similarity scores (Lazy Prices signal) | All pairs |

Ingestion runs for the current population (~24 tickers) via `--from-signals`. Full-universe ingestion (900 tickers) is deferred pending Neon paid tier ($19/mo for >0.5 GB storage).

### Research Agent Consumption

Qualitative analysts query RAG via the `@tool query_filings()` tool:
```python
from rag.retrieval import retrieve
results = retrieve(
    query="What are the key risk factors for semiconductor supply chain?",
    tickers=["MU", "NVDA"],
    doc_types=["10-K", "earnings_transcript"],
    min_date=date(2025, 1, 1),
    top_k=10,
)
# Returns: list of RetrievalResult(content, ticker, doc_type, filed_date, section_label, similarity)
```

Metadata pre-filtering (ticker, doc_type, date range) runs before vector similarity search, keeping query latency under 200ms.

---

# 2. Predictor Module

**Repo:** `~/Development/alpha-engine-predictor`
**Runtime:** AWS Lambda (container image via Docker + ECR, Python 3.12, 3GB memory)
**Schedule:** Training weekly Saturday (EC2 spot c5.xlarge); Inference daily via Step Function

## 2.1 Overview

**Meta-model v3.0** (deployed 2026-04-01) — a stacked ensemble that predicts 5-day market-relative alpha for ~900 S&P 500/400 stocks. Replaces the prior single-GBM approach with a two-layer architecture of specialized models plus a ridge meta-learner.

**Design Rationale:** The single GBM on 38 technical features had IC of 0.008-0.015 (marginal). Technical features are crowded signals — every quant fund trades them. The research pipeline's LLM-generated signals are the system's actual alpha source. The meta-model architecture lets each model specialize in its signal type and uses the meta-learner to weight them appropriately.

**Two Flows:**
1. **Weekly Training (EC2 spot, c5.xlarge, ~$0.06/hr):** Download 10y price cache from S3 → refresh stale parquets → train all Layer 1 models → train ridge meta-model → walk-forward validation (14 folds) → promote if IC gate passes → write slim cache for inference
2. **Daily Inference (Lambda, ~84 seconds):** Load all 5 model weights from S3 → read pre-computed features from feature store (S3) with inline fallback → run Layer 1 → run meta-model → apply research signal adjustment → write predictions JSON → send morning briefing email

## 2.2 Meta-Model Architecture (v3.0)

### Layer 1: Specialized Models

| Model | Type | Features | Signal | IC |
|-------|------|----------|--------|----|
| Momentum GBM | LightGBM | 6 momentum features | Price trend direction | ~0.01 (near-zero; used as contrarian signal) |
| Volatility GBM | LightGBM | 6 volatility features | Realized vol prediction | ~0.32 (strongest signal) |
| Regime Predictor | Logistic regression | Market-level features | Bull/neutral/bear probs | 59% accuracy |
| Research Calibrator | Lookup table (v0) | Research score buckets | Hit rate by score range | Scores 65-75: 75% hit rate |

### Layer 2: Ridge Meta-Model

- **Input:** 8 META_FEATURES — `research_calibrator_prob`, `momentum_score`, `expected_move`, `regime_bull`, `regime_bear`, `research_composite_score`, `research_conviction`, `sector_macro_modifier`
- **Output:** Predicted 5-day alpha (continuous)
- **IC:** ~0.04 (4x improvement over single GBM)
- **Key insight:** Meta-model uses momentum as a contrarian signal (negative coefficient -0.29), confirming that raw momentum is crowded

### Post-Meta-Model Adjustments

1. **Research signal adjustment:** +/-0.5% alpha adjustment based on research calibrator probability and conviction level
2. **Confidence rescaling:** META_ALPHA_CLIP floor of 2% prevents noise amplification on near-zero predictions
3. **Momentum fallback:** When momentum GBM IC < 0.02, uses direct weighted average of raw features instead of GBM output

### Signal Loading

Inference searches backward 7 days for the most recent `signals.json` (research runs weekly on Saturday, not daily). This ensures weekday inference always finds the current week's research signals.

## 2.3 Key Assumptions

- **Sector-neutral labels:** `alpha = stock_5d_return - sector_etf_5d_return`. Removes sector beta.
- **No lookahead bias:** Time-based train/val/test splits with 5-day purge gaps.
- **Cross-sectional rank normalization:** Features ranked per-date across all tickers to prevent look-ahead bias. Requires >= 2 tickers per date.
- **Macro features excluded from GBM:** VIX, yields, gold, oil removed from training (correct practice — these are cross-sectional constants).
- **Alternative data defaults to neutral (0.0)** when unavailable — model treats missing data as neutral signal.
- **SPY.parquet must exist in price cache** — if missing, `return_vs_spy_5d` defaults to 0.0.
- **Minimum 265 rows of price history** per ticker — skipped silently if shorter.
- **Historical data rewritten weekly** with new split/dividend adjustments (yfinance auto_adjust=True).
- **Lambda /tmp limited to 512MB** — model weights ~30-50MB combined.

## 2.4 Stack & Key Packages

| Package | Purpose |
|---------|---------|
| lightgbm >= 4.0 | Gradient boosting (Momentum + Volatility models) |
| scikit-learn >= 1.3 | Ridge regression (meta-model), logistic regression (regime) |
| pandas >= 2.0 | DataFrames, feature computation |
| numpy < 2 | Numerical arrays |
| yfinance >= 0.2.30 | Price fetching (10y full, 2y slim, daily delta) |
| pyarrow >= 14.0 | Parquet I/O (vectorized) |
| boto3 >= 1.26 | S3 model weights, predictions, cache |
| scipy >= 1.10 | Statistics (quantiles, correlations) — training only |
| optuna >= 3.5 | Hyperparameter tuning — training only |

## 2.5 Feature Engineering: 54 Features

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

### v3.0: META_FEATURES (8 features, meta-model input only)
research_calibrator_prob, momentum_score, expected_move, regime_bull, regime_bear, research_composite_score, research_conviction, sector_macro_modifier

**Total: 54 features.** Momentum GBM uses 6, Volatility GBM uses 6, meta-model uses 8 META_FEATURES. Remaining features computed by feature store for future model expansion.

## 2.6 Feature Store

**Custom feature store built into the data layer (alpha-engine-data/features/). Fully migrated from predictor on 2026-04-03.**

### Architecture

The feature store is a batch-oriented, S3-backed system that computes and serves 53 features for ~903 tickers. Features are pre-computed during data collection and served to consumers as dated Parquet snapshots.

```
Data Collection (DailyData / DataPhase1)
  → features/compute.py (53 features × 903 tickers, ~15s)
    → S3: features/{date}/technical.parquet    (26 features)
           features/{date}/macro.parquet        (7 features)
           features/{date}/interaction.parquet   (5 features)
           features/{date}/alternative.parquet   (7 features)
           features/{date}/fundamental.parquet   (8 features)
           features/{date}/schema_version.json
           features/registry.json
```

**Consumers:** Predictor inference reads pre-computed features from S3 as primary path (inline `compute_features()` fallback in degraded mode). Research reads technical indicators for enrichment. Backtester reads historical snapshots for walk-forward validation.

### Why Custom vs Feast/Tecton

| Consideration | Feast/Tecton | Alpha Engine Custom | Decision |
|---------------|-------------|---------------------|----------|
| **Serving pattern** | Online (Redis/DynamoDB) + offline (BigQuery/Redshift) | Batch only (S3 Parquet) | 5-day trading horizon needs daily features, not real-time. S3 Parquet is sufficient. |
| **Infrastructure** | Requires managed infra (Redis, warehouse, registry service) | S3 + pandas only | $0 additional infrastructure. Feast would require a Redis instance ($15+/mo) we don't need. |
| **Feature computation** | Declarative transforms or streaming (Spark/Flink) | 615-line `feature_engineer.py` (pandas) | All 53 features are rolling window calculations (RSI, MACD, moving averages). pandas handles 903 tickers in 8 seconds. No need for Spark. |
| **Consistency** | Guaranteed by framework (point-in-time joins) | Guaranteed by architecture (same code, same data, same date) | Training and inference read the same dated Parquet snapshot. No training/serving skew possible — it's the same file. |
| **Time-travel** | Built-in (entity timestamps) | Date-partitioned snapshots (`features/{date}/`) | Each date has its own directory. Walk-forward training reads historical snapshots directly. |
| **Schema evolution** | Built-in versioning | `schema_version.json` with hash-based change detection | SHA256 hash of feature list + config parameters. Training validates hash consistency across walk-forward windows. |
| **Registry** | Centralized feature catalog service | `features/registry.json` (53 features with metadata) | JSON file on S3 — no separate service to manage. |
| **Backfill** | Complex job orchestration | Run `python -m features.compute --date 2026-03-15` | Single CLI command per date. No orchestration needed. |

**Bottom line:** Feast solves the online/offline serving split and training/serving skew problems. Alpha Engine doesn't have these problems — it's a batch-only system where training and inference read the same Parquet files. The custom approach is ~800 lines of Python total (compute + writer + registry + reader) vs adding Feast as a dependency with all its infrastructure requirements.

### Feature Groups

| Group | Count | Raw Data | Computation | Warmup |
|-------|-------|----------|-------------|--------|
| Technical | 26 | OHLCV prices | RSI, MACD, moving averages, Bollinger, ATR, momentum, volume | 252 days (52-week high/low) |
| Macro | 7 | VIX, yields, gold, oil, market breadth | Normalized levels and slopes | 20 days |
| Interaction | 5 | Technical × Macro cross-products | momentum × VIX, RSI × VIX, ATR × VIX, sector × trend, volume × VIX | Same as components |
| Alternative | 7 | Earnings, EPS revisions, options | Surprise %, revision streak, IV rank, put/call | Cached weekly from DataPhase2 |
| Fundamental | 8 | FMP quarterly financials | P/E, P/B, D/E, revenue growth, FCF yield, gross margin, ROE, current ratio | Cached weekly from DataPhase1 |

All features are **deterministic transforms** — no model weights, no learned parameters, no training-set-dependent scaling. This is why they belong in the data layer, not the model layer.

### Schema Versioning

Each snapshot includes `schema_version.json`:
```json
{
  "schema_version": 1,
  "schema_hash": "a3f7b2c91d4e",
  "n_features": 53,
  "features": ["rsi_14", "macd_cross", ...],
  "date": "2026-04-03"
}
```

The `schema_hash` is a SHA256 of the feature list + computation config. If a feature formula changes (e.g., RSI period from 14 to 20), the hash changes, and training can detect the boundary between feature versions. This prevents training on mixed-version features that would produce unreliable models.

### Data Contracts

JSON Schema contracts in `alpha-engine-data/contracts/` define the expected format of inter-module files (signals.json, predictions.json, executor_params.json). Validation is advisory — log warnings, never hard-fail. See `contracts/__init__.py` for the validator API.

## 2.7 Veto Gate

```
IF predicted_alpha < 0 AND combined_rank in bottom half:
    Override ENTER → HOLD (block entry)
```

**Design change (v3.0):** The veto gate was redesigned for the meta-model. Instead of a simple DOWN direction + confidence threshold, it now uses predicted alpha sign combined with rank position. This is because meta-model confidence values cluster at 0.50-0.51 (the alpha range of ~[-0.01, +0.01] is too narrow for the previous linear confidence mapping). The predictor veto is now the primary entry filter, replacing the legacy technical gates.

**Threshold Management:**
- Base: configurable from `predictor.yaml`
- Override: `config/predictor_params.json` on S3 (tuned by backtester)
- Regime adjustment (optional): bear -0.10, caution -0.05, neutral 0, bull +0.05
- Clamped to [0.40, 0.90]

## 2.8 Price Data (ArcticDB)

As of 2026-04-07, all price data is stored in **ArcticDB** (backed by S3), replacing the prior fragmented Parquet approach. ArcticDB provides a unified, versioned time-series store with deduplication and efficient range queries.

| Library | S3 Prefix | History | Refresh | Purpose |
|---------|-----------|---------|---------|---------|
| `universe` | `arcticdb/universe/` | 10 years | Weekly (DataPhase1) | Training data, 909 tickers |
| `universe_slim` | `arcticdb/universe_slim/` | 2 years | Weekly (post-training) | Inference Lambda input |
| `daily_closes` | `predictor/daily_closes/{date}.parquet` | 1 day | Daily | Delta appended to slim |

**Inference Price Flow:** Load from ArcticDB slim library → load daily_closes delta → splice → compute features (or read from feature store) → predict.

Legacy Parquet paths (`predictor/price_cache/*.parquet`, `price_cache_slim/*.parquet`) still exist on S3 but are no longer the primary read path. Phase 7 deprecation pending 2 weeks clean logs (~2026-04-21).

## 2.9 predictions.json Output Schema

```json
{
  "date": "2026-04-03",
  "model_version": "meta_v3.0",
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
      "sector": "Information Technology",
      "momentum_score": 0.015,
      "expected_move": 0.032,
      "regime_bull": 0.44,
      "research_calibrator_prob": 0.75
    }
  ]
}
```

## 2.10 Deployment

Lambda container image deployed via Docker + ECR using `deploy.sh`:
- Builds Docker image with all dependencies
- Pushes to ECR
- Updates Lambda function code
- Canary verification (invokes with test payload)
- Auto-rollback on canary failure
- Training runs on EC2 spot via `spot_train.sh` (c5.xlarge, ~$0.06/hr)

## 2.11 Environment Variables

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
**Schedule:** EC2 start via Step Function (~6:10 AM PT), main.py on boot, daemon.py on boot, EOD 1:20 PM PT, EC2 stop 1:30 PM PT

## 3.1 Overview

Two-phase order execution system. **Phase 1 (Morning Batch):** Reads signals from S3, applies risk rules and position sizing, writes order book. Places NO orders. **Phase 2 (Intraday Daemon):** Sole order executor — uses technical triggers for entries, executes exits immediately at market open.

**Signal Source:** "population" mode — generates signals from full population + technical scores + GBM predictions. The predictor veto is now the primary entry filter.

**Boot Sequence (systemd):**
```
boot-pull.service → git pull latest code
ibgateway.service → Docker IB Gateway (TOTP 2FA, port 4002)
alpha-engine-morning.service → main.py (order book planner)
alpha-engine-daemon.service → daemon.py (order executor)
alpha-engine-eod.timer → 1:20 PM PT (EOD reconcile)
alpha-engine-daemon.timer → 9:29 AM ET (safety-net re-trigger)
```

## 3.2 Key Assumptions

- **Paper account only** — daemon safety check: account ID must start with "D". Hard exit if connected to live account.
- **IB Gateway on port 4002** — main.py uses clientId=1, daemon uses clientId=2.
- **Delayed market data (15-min)** — free IB data via `reqMarketDataType(3)`.
- **Signals from most recent trading day** — falls back up to 5 calendar days (skips weekends).
- **All exits pass risk guard** — reducing exposure is never blocked.
- **Order book is JSON on disk** — uses `block_reason` key (not `reason`). Atomic POSIX rename for writes, no file-level locking.
- **ATR required for trailing stops** — if ATR unavailable, position entered without stop (known gap).
- **Single-threaded execution** — daemon polls every 60 seconds sequentially.
- **NYSE holiday awareness** — `market_hours.py` uses `trading_calendar.py` with holidays defined through 2030.

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
| Score minimum | score >= 30 (backstop only, backtester auto-tunes via S3) | Block entry |
| Declining conviction | conviction == "declining" | Reduces position size by 0.7x (NOT a hard gate) |
| Predictor veto | negative alpha + bottom-half combined rank | Override ENTER → HOLD (primary entry filter) |
| Graduated drawdown | 0-3%: 1.0x, 3-5%: 0.5x, 5-8%: 0.25x, >8%: HALT | Scale sizing / circuit breaker |
| Max single position | 8% NAV (2.5% in bear) | Cap position size |
| Bear sector block | bear regime + underweight sector | Block entry |
| Sector exposure | <= 25% per sector | Cap sector weight |
| Total equity | <= 90% in equities | Keep 10% cash |
| Cross-ticker correlation | mean Pearson corr <= 0.80 (60d rolling) | Block correlated entries |

**Key change from prior version:** Legacy entry gates disabled — `min_technical_score=0`, `momentum_gate_enabled=false`, `min_score_to_enter=30` (backstop only). The predictor veto gate is now the primary mechanism for filtering entries, replacing the old score-based and conviction-based hard gates.

## 3.5 Position Sizing Formula

```
base_weight     = 1 / n_enter_today
sector_adj      = OW:1.10 / MW:1.00 / UW:0.75
conviction_adj  = 0.70 if declining, else 1.00
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

Note: `conviction_adj = 0.70` for declining conviction is a sizing reduction, not a hard block.

## 3.6 Entry Triggers (Intraday, OR Logic)

| Trigger | Default | Fires When |
|---------|---------|------------|
| Pullback | 2% | (day_high - current) / day_high >= 2% |
| VWAP Discount | 0.5% | (vwap - current) / vwap >= 0.5% (uses previous day's VWAP from daily_closes) |
| Support Bounce | 1% | 0 <= (current - support) / support <= 1% |
| Graduated Expiry | 3-tier | See below |

**Graduated time expiry** (replaces fixed 3:30 PM, added 2026-04-06):

| Window | Time | Condition | Rationale |
|--------|------|-----------|-----------|
| Technical only | Pre-2:00 PM ET | Only pullback/VWAP/support triggers fire | Wait for optimal entry |
| Graduated | 2:00-3:30 PM ET | Accept if price <= morning price + 1% | Moderate urgency |
| Time expiry | 3:55 PM ET | Unconditional market order | Ensure fill before close |

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
  "date": "2026-04-03",
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
    "block_reason": "research_signal", "status": "pending"
  }],
  "active_stops": [{
    "ticker": "AAPL", "entry_price": 230.50, "current_stop": 225.00,
    "trail_atr": 4.25, "atr_multiple": 2.0, "high_water": 235.00,
    "entry_date": "2026-04-03", "shares": 100
  }]
}
```

Note: The `block_reason` key (not `reason`) is used in the order book for blocked/rejected entries.

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

## 3.10 EOD Reconciliation (Step Function, 1:20 PM PT)

Orchestrated by `alpha-engine-eod-pipeline` Step Function (replaced systemd timer + EventBridge scheduler on 2026-04-07):

1. Fetch NAV and positions from IB Gateway
2. Compute daily return vs SPY
3. Sector attribution: weight * contribution per sector
4. Roundtrip statistics (win rate, avg alpha, avg days held)
5. Position narratives via Haiku LLM (fallback to templates)
6. Send EOD email (SES)
7. Backup trades.db to S3 (dated + latest)
8. Export CSV: trades_full.csv, eod_pnl.csv
9. Step Function stops trading EC2 instance after reconciliation

## 3.11 Config (risk.yaml)

```yaml
max_position_pct: 0.08          # Per-position cap
max_sector_pct: 0.25            # Per-sector cap
max_equity_pct: 0.90            # Total equity cap
bear_max_position_pct: 0.025    # Bear regime cap
drawdown_circuit_breaker: 0.08  # -8% NAV halt
min_score_to_enter: 30          # Backstop (backtester auto-tunes via S3)

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
**Schedule:** Weekly Saturday via Step Function (after Research + Predictor Training)

## 4.1 Overview

Closes the feedback loop by validating signal quality, optimizing parameters, and auto-writing 4 S3 config files that all downstream modules read on cold-start:

1. `config/scoring_weights.json` → Research (quant/qual balance)
2. `config/executor_params.json` → Executor (risk/strategy params, including `min_score` currently set to 30)
3. `config/predictor_params.json` → Predictor (veto threshold)
4. `config/research_params.json` → Research (signal boost params, deferred until 200+ samples)

This is the system's learning mechanism — fully autonomous, no manual intervention required.

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
- 5d/10d/30d accuracy: % of BUY signals beating SPY over forward window
- Precision (same as accuracy for BUY signals), TP/FP counts
- Wilson Score CI (95%): binomial proportion confidence interval
- Average alpha: mean(signal_return - SPY_return) per horizon

**Stratification:**
- Score buckets: [60-70), [70-80), [80-90), [90-100]
- Market regime: bull/neutral/bear/caution (from macro_snapshots)
- **Sector** (joined from universe_returns): per-sector accuracy at 5d/10d/30d
- Conviction: rising/stable/declining
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
2. For each threshold: compute precision, recall, F1, lift, missed alpha
3. Per-sector veto precision/recall at recommended threshold
4. Score: `precision - 0.30 * (missed_alpha / max_missed_alpha)`
5. Select threshold with max score

**Gates:** >= 10 veto decisions per threshold, >= 30 predictions total, lift >= 5% above base rate.

## 4.9 Evaluation Framework (added 2026-04-08)

### Unified Scorecard (`analysis/grading.py`)
Grades every system component on a 0-100 scale with letter grades (A through F). Module-level grades (Research, Predictor, Executor) roll up from weighted component grades. Overall system grade is a weighted average of module grades. Scorecard appears at the top of the weekly report and is saved as `grading.json` for dashboard display.

### Classification Metrics (`analysis/classification_metrics.py`)
Precision/recall/F1 computed at every decision boundary using `compute_binary_metrics(tp, fp, fn, tn)`. Each pipeline stage defines its own positive class:

| Stage | Selected = | Positive = | Metric Focus |
|-------|-----------|------------|-------------|
| Scanner | Passed quant filter | Beat SPY 5d | Filter effectiveness |
| Sector Team | Team recommended | Beat sector ETF 5d | Team skill |
| CIO | Advanced | Beat SPY 5d | Selection quality |
| Predictor | Predicted UP | Beat SPY 5d | Directional accuracy |
| Veto Gate | Vetoed (predicted DOWN) | Actually underperformed | Veto precision |
| Risk Guard | Entry blocked | Would have lost | Guard accuracy |

### Predictor Confusion Matrix (`analysis/predictor_confusion.py`)
3x3 matrix (UP/FLAT/DOWN predicted vs actual). Actual direction derived from `actual_5d_return` using +/-0.5% thresholds. Per-direction precision, recall, and F1 reveal whether the model confuses flat with directional or reverses direction.

### Grade History (`analysis/grade_history.py`)
Appends weekly grades to `s3://bucket/backtest/grade_history.json` (52-week rolling). Enables trend analysis on the dashboard — is each component improving or degrading over time?

### Structured JSON Output
The backtester saves 7 analysis files alongside the markdown report for dashboard consumption:
`grading.json`, `trigger_scorecard.json`, `shadow_book.json`, `exit_timing.json`, `e2e_lift.json`, `veto_analysis.json`, `confusion_matrix.json`

## 4.10 Synthetic Predictor Backtest (10-Year)

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

# Triggered by Saturday Step Function (previously cron, removed 2026-04-02)
```

---

# 5. Dashboard Module

**Repo:** `~/Development/alpha-engine-dashboard`
**Runtime:** EC2 t3.micro (1GB RAM + 1GB swap)
**Stack:** Streamlit + Plotly + Pandas
**Access:** SSH tunnel (port 8501) or Cloudflare Access

## 5.1 Overview

Read-only monitoring dashboard with 7+ pages. Never writes to S3 or databases. All data flows inbound from Research (signals, research.db), Executor (trades, eod_pnl), and Predictor (predictions, metrics).

## 5.2 Key Assumptions

- **EC2 IAM role provides S3 access** — no hardcoded credentials.
- **1GB RAM constraint** — mitigated by 1GB swap, 300MB memory limit per Streamlit service, dual-instance approach.
- **IB Gateway DISABLED on micro instance** — was consuming 45% RAM, root cause of OOM freezes. IB Gateway runs only on trading instance.
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
System health snapshot. Shows pipeline activity (research population, predictor vetoes, risk guard decisions, trades), current holdings with unrealized P&L, alpha chart, market context. **System Report Card** with module-level grades (Research, Predictor, Executor, Overall) from latest backtest.

**Data:** eod_pnl.csv, trades_full.csv, signals.json, predictions/latest.json, order_book_summary.json, population/latest.json, macro_snapshots table, backtest/{date}/metrics.json (report card).

### 1_Portfolio
NAV vs SPY cumulative return (shaded outperformance), drawdown chart with circuit breaker threshold, current positions, sector allocation donut with concentration warnings (>25% red, >20% amber), sector rotation stacked area.

**Data:** eod_pnl.csv, trades_full.csv, signals.json.

### 2_Signals
Signal universe table with filters (sector, signal type, min score). Ticker detail expander with sub-score visualization. Veto status display (VETOED if predictor flags negative alpha + bottom-half rank).

**Data:** signals.json, predictions.json, predictor_params.json, macro_snapshots.

### 3_Signal_Quality
Rolling 4-week accuracy trends (10d/30d), accuracy by score bucket with Wilson CI, accuracy by market regime, alpha by regime, scoring weight history.

**Data:** score_performance table, macro_snapshots, eod_pnl.csv, scoring_weights_history/.

### 4_Research
Per-ticker score history with sub-score lines and signal markers. Investment thesis display. Symbol selector (top 10 by recent score).

**Data:** investment_thesis table, score_performance table.

### 5_Backtester (Analysis page, Backtester tab)
Parameter sweep heatmap (min_score vs max_position_pct, color by Sharpe), signal quality by bucket, sub-score attribution, weight recommendations, raw report markdown. **System Report Card** with component grade table and sector team grades (precision, recall, lift).

**Data:** backtest/{date}/metrics.json (includes report_card), param_sweep.csv, signal_quality.csv, attribution.json, report.md.

### 6_Execution
Three tabs: **Trade Log** (paginated audit trail with filters and outcome join), **Execution Evaluation** (trigger scorecard, shadow book with P/R/F1, exit timing MFE/MAE), **Slippage Monitor** (fill price vs order price).

**Data:** trades_full.csv, score_performance table, backtest/{date}/trigger_scorecard.json, shadow_book.json, exit_timing.json.

### 7_Predictor
Model health badge (green >= 52%, amber 48-52%, red < 48%), 30d/90d rolling hit rate drift chart, mode history, today's predictions with signal disagreement analysis. Shows meta-model v3.0 predictions including momentum score, expected move, and regime probabilities.

**Data:** predictor/metrics/latest.json, predictor_outcomes table, mode_history.json, predictions/latest.json.

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
- IB Gateway disabled on micro instance (was consuming 45% RAM)
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

# 6. Data Module

**Repo:** `~/Development/alpha-engine-data`
**Runtime:** EC2 micro (Phase 1, SSM) + Lambda (Phase 2)
**Schedule:** Saturday via Step Function (Phase 1 + Phase 2); Daily via Step Function (DailyData)

## 6.1 Overview

Centralized data collection for the Alpha Engine system. Created 2026-04-02 to eliminate redundant API calls — Research, Predictor, and Backtester were independently fetching overlapping market data (~900 tickers fetched 2-3x, redundant FRED/macro calls). This module runs a single upstream job that writes to S3 so downstream modules read from S3 instead.

**Design rationale:** With 6 modules consuming overlapping data, centralizing collection reduces API costs, eliminates rate-limiting issues, and ensures all modules operate on identical data snapshots. The two-phase design (pre-research and post-research) minimizes the data collected for the expensive alternative data APIs, which only need data for the ~30 promoted tickers.

## 6.2 Two-Phase Pipeline

### Phase 1 (before Research — EC2 SSM)
- **Constituents:** S&P 500+400 tickers + GICS sectors from Wikipedia
- **Prices:** 10y OHLCV refresh → ArcticDB `universe` library (909 tickers, replaces Parquet; legacy `predictor/price_cache/*.parquet` still written during Phase 7 transition)
- **Slim cache:** 2y slices → ArcticDB `universe_slim` library (replaces `price_cache_slim/*.parquet`)
- **Macro:** FRED series (fed funds, yields, VIX) + commodity/index prices + market breadth
- **Universe returns:** Full-population forward returns via polygon.io grouped-daily endpoint

### Phase 2 (after Research — Lambda)
- **Alternative data** for promoted tickers (~30): analyst consensus, EPS revisions, options chains, insider filings, institutional 13F, news sentiment
- Sources: FMP, yfinance options, SEC EDGAR

### Daily Collection (weekdays via Step Function)
- `daily_closes/{date}.parquet` — OHLCV for all tickers
- Macro refresh — yields, VIX, commodities for feature computation

## 6.3 Stack & Key Packages

| Package | Purpose |
|---------|---------|
| yfinance >= 0.2.30 | Price data, options chains |
| polygon.io client | Universe returns (grouped-daily) |
| arcticdb >= 4.0 | ArcticDB time-series store (S3-backed) |
| fredapi | FRED macro series |
| boto3 >= 1.26 | S3 writes |
| pandas >= 2.0 | DataFrames, parquet I/O |
| requests | SEC EDGAR, FMP, Wikipedia scraping |

## 6.4 External APIs

| API | Key Required | Usage |
|-----|-------------|-------|
| yfinance | No | 10y OHLCV, options chains |
| polygon.io | POLYGON_API_KEY | Universe returns (grouped-daily) |
| FRED | FRED_API_KEY | Fed funds, treasury yields, VIX |
| FMP | FMP_API_KEY | Analyst consensus, EPS revisions |
| EDGAR | EDGAR_IDENTITY | Insider filings, institutional 13F |
| Wikipedia | No | S&P constituent lists |

## 6.5 S3 Output Paths

```
s3://alpha-engine-research/
├── market_data/
│   ├── weekly/{date}/
│   │   ├── constituents.json         # tickers, sector_map, sector_etf_map
│   │   ├── macro.json                # FRED + market prices + breadth
│   │   ├── manifest.json             # run status, counts, errors
│   │   └── alternative/
│   │       ├── {TICKER}.json         # per-ticker alternative data
│   │       └── manifest.json         # Phase 2 run status
│   └── latest_weekly.json            # pointer to most recent weekly date
├── arcticdb/
│   ├── universe/                     # ArcticDB 10y OHLCV (909 tickers, primary read path)
│   └── universe_slim/                # ArcticDB 2y slices (inference)
├── predictor/
│   ├── price_cache/*.parquet         # Legacy 10y OHLCV (Phase 7 deprecation pending)
│   ├── price_cache/sector_map.json   # ticker → sector ETF mapping
│   └── price_cache_slim/*.parquet    # Legacy 2y slices (Phase 7 deprecation pending)
├── health/
│   ├── data_phase1.json              # Phase 1 completion marker
│   └── data_phase2.json              # Phase 2 completion marker
└── research.db                       # universe_returns table updated by Phase 1
```

## 6.6 Key Files

```
weekly_collector.py                # CLI entry point (--phase 1 / --phase 2)
polygon_client.py                  # polygon.io rate-limited client
collectors/constituents.py         # S&P 500+400 tickers + GICS sectors
collectors/prices.py               # 10y OHLCV refresh for stale parquets
collectors/slim_cache.py           # 2y slice writer
collectors/macro.py                # FRED + commodities + breadth
collectors/universe_returns.py     # Full-population forward returns
collectors/alternative.py          # Per-ticker alternative data
feature_store/compute.py           # Standalone feature computation (54 features, ~20s)
trading_calendar.py                # NYSE holiday detection (through 2030)
config.yaml                        # GITIGNORED
config.yaml.example                # Template
```

## 6.7 Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| FRED_API_KEY | Yes (Phase 1) | FRED macro data |
| POLYGON_API_KEY | Yes (Phase 1) | polygon.io universe returns |
| FMP_API_KEY | Yes (Phase 2) | Financial Modeling Prep |
| EDGAR_IDENTITY | Yes (Phase 2) | SEC EDGAR User-Agent |

---

# Cross-Module Data Flow Summary

```
                    SATURDAY (Step Function)
                    ========================
DataPhase1 (EC2 SSM, 00:00 UTC)
  → predictor/price_cache/*.parquet
  → predictor/price_cache_slim/*.parquet
  → market_data/weekly/{date}/constituents.json
  → market_data/weekly/{date}/macro.json

FeatureStoreCompute (EC2 SSM)
  → predictor/feature_store/{date}/features.parquet (54 features x 903 tickers)

RAGIngestion (EC2 SSM)
  → SEC filings, 8-Ks, earnings → research knowledge base

Research Lambda
  → signals/{date}/signals.json  ─────────────────────┐
  → research.db (S3)                                    │
  → archive/{category}/{ticker}/                        │
                                                        │
DataPhase2 (Lambda)                                     │
  → market_data/weekly/{date}/alternative/{TICKER}.json │
                                                        │
Predictor Training (EC2 spot)                           │
  → predictor/weights/gbm_latest.txt                    │
  → predictor/weights/meta_*.pkl                        │
  → predictor/price_cache_slim/*.parquet                │
                                                        │
Backtester (EC2 spot)                                   │
  ← signals.json, research.db, predictions,             │
    price_cache, current configs                        │
  → config/scoring_weights.json ──→ Research            │
  → config/executor_params.json ──→ Executor            │
  → config/predictor_params.json ─→ Predictor           │
  → backtest/{date}/* ────────────→ Dashboard           │
                                                        │
                    WEEKDAYS (Step Function)             │
                    ===========================         │
CheckTradingDay (Lambda)                                │
  → short-circuit on NYSE holidays                      │
                                                        │
DailyData (EC2 SSM, 6:05 AM PT)                        │
  → predictor/daily_closes/{date}.parquet               │
                                                        │
FeatureStoreCompute (EC2 SSM)                           │
  → predictor/feature_store/{date}/features.parquet     │
                                                        │
Predictor Inference (Lambda)                            │
  ← signals.json (searches back 7 days) ───────────────┘
  ← slim cache, daily_closes, feature store
  → predictor/predictions/{date}.json ─────────────┐
                                                    │
Executor Morning (~6:25 AM PT)                      │
  ← signals.json ──────────────────────────────────┤
  ← predictions.json ──────────────────────────────┘
  → order_book.json (local)

Executor Daemon (6:30 AM - 4:15 PM ET)
  → trades.db (local)
  → trades/trades_full.csv (S3)

Executor EOD (1:20 PM PT)
  → trades/eod_pnl.csv (S3)
  → trades.db backup (S3)

Dashboard (always-on, EC2 micro)
  ← All S3 paths above (read-only)
  ← research.db (read-only)
```

---

# Shared Infrastructure

- **AWS S3 bucket:** `alpha-engine-research` — shared data store for all inter-module communication
- **Step Functions:** Two state machines (`alpha-engine-saturday-pipeline`, `alpha-engine-weekday-pipeline`) triggered by EventBridge rules. All legacy standalone EventBridge/cron triggers removed 2026-04-02.
- **Email:** All modules use Gmail SMTP (primary) + AWS SES (fallback) with same env vars: `EMAIL_SENDER`, `EMAIL_RECIPIENTS`, `GMAIL_APP_PASSWORD`, `AWS_REGION`
- **Broker:** Interactive Brokers paper account via IB Gateway Docker (gnzsnz/ib-gateway-docker with TOTP 2FA) on EC2 trading instance (port 4002). Paper account has dedicated credentials separate from live brokerage. No live account credentials stored on any server. Daemon includes runtime safety check (account ID must start with "D").
- **LLM provider:** Anthropic Claude (Haiku-4-5 for per-ticker agents, Sonnet-4-6 for synthesis/ranking)
- **Databases:** SQLite per-module (research.db, trades.db) backed up to S3
- **Config pattern:** YAML config files (gitignored per-environment) read by centralized `config.py`. S3-hosted config files (`config/*.json`) auto-updated by backtester and read on cold-start by downstream modules.

## Key Metrics

| Metric | What it measures |
|--------|-----------------|
| Total alpha | Portfolio cumulative return - SPY cumulative return |
| Sharpe ratio | Risk-adjusted return (annualized) — primary optimization target |
| Daily alpha | Portfolio daily return - SPY daily return |
| Signal accuracy (10d/30d) | % of BUY signals that beat SPY over configurable windows |
| GBM IC | Information coefficient of predicted vs actual 5d returns |
| Meta-model IC | IC of stacked meta-model output (~0.04, 4x single GBM) |
| Max drawdown | Peak-to-trough portfolio decline (circuit breaker threshold configurable) |

## S3 Layout

```
s3://alpha-engine-research/
├── signals/{date}/signals.json          ← Research output, Predictor+Executor input
├── archive/universe/{TICKER}/           ← Research theses (never overwritten)
├── archive/candidates/{TICKER}/         ← Buy candidate theses
├── archive/macro/                       ← Macro environment reports
├── consolidated/{date}/morning.md       ← Research email content
├── market_data/
│   ├── weekly/{date}/                   ← DataPhase1 + Phase2 output
│   │   ├── constituents.json
│   │   ├── macro.json
│   │   ├── manifest.json
│   │   └── alternative/{TICKER}.json
│   └── latest_weekly.json
├── arcticdb/
│   ├── universe/                        ← ArcticDB 10y OHLCV, 909 tickers (primary)
│   └── universe_slim/                   ← ArcticDB 2y slices for inference
├── predictor/
│   ├── price_cache/*.parquet            ← Legacy 10y OHLCV (Phase 7 deprecation pending)
│   ├── price_cache/sector_map.json      ← Ticker → sector ETF mapping
│   ├── price_cache_slim/*.parquet       ← Legacy 2y slices (Phase 7 deprecation pending)
│   ├── daily_closes/{date}.parquet      ← Daily OHLCV archive (Mon-Fri)
│   ├── feature_store/{date}/            ← Pre-computed features (54 x 903 tickers)
│   ├── weights/gbm_latest.txt           ← Active GBM model (momentum)
│   ├── weights/meta_*.pkl               ← Meta-model weights (ridge, regime, etc.)
│   ├── weights/gbm_{date}.txt           ← Dated backups
│   ├── predictions/{date}.json          ← Daily predictions
│   └── metrics/latest.json              ← Model performance
├── trades/
│   ├── trades_full.csv                  ← Complete trade audit log
│   └── eod_pnl.csv                      ← Daily NAV, return, alpha
├── backtest/{date}/                     ← Weekly backtester outputs (report.md, metrics.json, grading.json, trigger_scorecard.json, shadow_book.json, exit_timing.json, e2e_lift.json, veto_analysis.json, confusion_matrix.json)
├── backtest/grade_history.json          ← 52-week rolling grade history
├── config/scoring_weights.json          ← Auto-updated by backtester → Research
├── config/executor_params.json          ← Auto-updated by backtester → Executor
├── config/predictor_params.json         ← Auto-updated by backtester → Predictor
├── config/research_params.json          ← Auto-updated by backtester → Research (deferred)
├── health/{module}.json                 ← Module completion markers
└── research.db                          ← SQLite (signal history, theses, macro)
```

## EC2 Access

Two instances with dynamic IPs. Shell helpers in `~/.zshrc`:

```bash
ae-trading "command"   # SSH to trading instance
ae-dashboard "command" # SSH to micro instance (dashboard + data)
```

GitHub access on EC2 uses HTTPS + fine-grained PAT stored in `~/.netrc` (not SSH keys). The PAT needs **Contents: read** on each repo.

## Deployment

- **Lambda:** `deploy.sh` builds Docker image, pushes to ECR, updates function code with canary verification and auto-rollback
- **EC2 trading:** `boot-pull.service` auto-pulls on each boot with dry-run validation + auto-rollback; manual deploy via `git push origin main`
- **EC2 micro:** `git push origin main && ae-dashboard "cd ~/alpha-engine-data && git pull"`
- **Rollback:** Lambda via `infrastructure/rollback.sh`; EC2 via `git reset --hard HEAD~1`
- **Config:** Modules search `alpha-engine-config` (private repo, cloned on EC2) first, fall back to local config. Push configs: `push-configs.sh`
- **Secrets:** SSM Parameter Store holds 24 secrets under `/alpha-engine/*`. Push all secrets: `push-secrets.sh`. Lambdas read from SSM at cold-start via `ssm_secrets.py`.

## S3 Contract Safety

When changing any S3 file path or JSON schema that is read by another module:
- **Path changes:** Write to BOTH old and new paths for at least 1 week before removing the old path.
- **Schema changes:** Only ADD fields, never rename or remove. Downstream consumers must handle missing fields gracefully.
- **Breaking changes:** Coordinate across repos. Update consumer first (handle both formats), then producer, then remove old format after 1 week.
