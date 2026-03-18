# Alpha Engine System Audit — 2026-03-18

## Objective

Full system audit across all 5 modules (Research, Predictor, Executor, Backtester, Dashboard). This document contains **only open items** — completed work is archived in `alpha-engine-audit-260317.md`.

Alpha = Portfolio Return - SPY Return

---

## Summary

| Category | Open Items |
|----------|-----------|
| Critical/High findings | 1 (H4 — ensemble) |
| Research gaps | 16 |
| Predictor gaps | 8 |
| Executor gaps | 17 |
| Backtester gaps | 10 |
| Dashboard gaps | 14 |
| Optimization opportunities | 10 |
| Deployment/functional items | 1 (D7 — monitor only) |

---

## Open Findings

### Severity: HIGH

| # | Module | Finding | Impact |
|---|--------|---------|--------|
| H4 | Predictor | Single GBM model — no ensemble, no model diversity | Leaves 10-20% IC improvement on table. Deferred to Phase 4 (model evolution). |

---

## Module-by-Module Open Gaps

### 1. Research (`~/Development/alpha-engine-research`)

#### Scoring System (Current)

```
final_score = news_score * w_news + research_score * w_research + macro_shift
macro_shift = (sector_modifier - 1.0) / 0.30 * 10.0  → range [-10, +10]
long_term_score = news_lt * 0.50 + research_lt * 0.50 + macro_shift
```

#### Data Source Gaps

| Data Source | Alpha Impact | Cost |
|-------------|-------------|------|
| Short interest & borrow rates | MEDIUM — crowded trade risk flag | Free (finviz scrape) |
| Leading indicators (ISM PMI, jobless claims) | MEDIUM — leads equity drawdowns 3-6 months | Free (FRED) |
| Credit spreads (HY-Treasury OAS) | MEDIUM — risk-on/off indicator | Free (FRED) |
| Equity breadth (advance/decline, % above 50d MA) | MEDIUM — confirms/contradicts SPY price | Free (finviz scrape) |
| 13F institutional holdings changes | LOW — quarterly lag reduces timeliness | Free (SEC EDGAR) |

#### LLM Agent Gaps

1. **Market regime definition is subjective** — macro agent uses bull/neutral/caution/bear labels with no quantitative thresholds. Different runs may classify the same data differently.
   - Fix: Define regimes mathematically (e.g., Bull: VIX < 15 AND SPY 30d return > 0; Bear: VIX > 25 OR SPY 30d return < -5%).

2. **News sentiment quantification is keyword-only** — recurring themes use word frequency, not semantic analysis. "China tariffs" (bearish) and "China market expansion" (bullish) are indistinguishable.
   - Fix: Add sentiment scoring (VADER or TextBlob) before passing to news agent, or use LLM-based theme sentiment.

3. **Prior report length unbounded** — if accumulated thesis is 5000 words, agent's output budget is consumed by context. No cap on prior_report size.
   - Fix: Truncate prior_report to most recent 500 words or last 3 months.

4. **Consistency check uses regex, not semantics** — `check_consistency()` in aggregator.py uses keyword matching. "Bullish but headwinds may resurface" gets bullish_hits=1, bearish_hits=1, classified as consistent (requires bullish > bearish).
   - Fix: Use LLM-based consistency check or require dominance ratio > 2:1.

#### Scanner Pipeline Gaps

1. **No volatility screen** — high-volatility stocks pass if volume threshold met.
2. **No debt/balance sheet filter** — near-default companies can pass scanner.
3. **No sector concentration limit in candidates** — all 60 candidates could be Technology.
4. **Deep value path weak** — only checks RSI < 35 + single analyst "Buy" rating.
5. **No sub-sector (industry group) analysis** — semiconductors and SaaS treated identically as "Technology."

#### Thesis Management

1. Stale thesis detection exists (`stale_days` counter) but is never surfaced in output — no visual "STALE" badge.
2. No forced thesis refresh trigger — stale theses accumulate without action.
3. No archive expiration — 6-month-old wrong theses remain in archive indefinitely.

#### Survivorship Bias

1. Wikipedia S&P constituents are current-only — delisted stocks disappear from universe.
2. No tracking of stocks removed from S&P 500/400 and their subsequent performance.
3. Price floor ($10) creates look-ahead bias — recovered penny stocks included only after recovery.

---

### 2. Predictor (`~/Development/alpha-engine-predictor`)

#### Model Architecture (Current)

- **Model**: Single LightGBM regression
- **Objective**: MSE (mean squared error)
- **Target**: 5-day sector-neutral alpha (stock return - sector ETF return)
- **Features**: 36 GBM features (41 total, 5 macro-only excluded from GBM)
- **Training**: Walk-forward expanding window, 2000 estimators, early stopping at 50 rounds
- **IC Gate**: test_ic >= 0.03, IC IR >= 0.3 for weight promotion
- **Latest Performance**: test IC ~0.046, IC IR ~0.421

#### Open Gaps

**Model Architecture:**

1. **Single model, no ensemble** — No model diversity. Literature shows 3-model stacking (LightGBM + XGBoost + CatBoost with logistic regression meta-learner) typically improves accuracy 10-15%.

2. **No temporal ensemble** — Only predicts 5-day returns. Training on 3, 5, 7, 10-day horizons and blending captures multi-horizon alpha and reduces label noise sensitivity.

3. **Inactive MLP alternative** — `model/predictor.py` contains a DirectionPredictor MLP (v1.2.0) but it's not used in the GBM training pipeline. Dead code that could be activated for ensemble.

**Feature Engineering:**

| Feature Category | Current | Missing |
|-----------------|---------|---------|
| Momentum | 7+ variants (RSI, MACD, momentum_5d/20d, price_accel) | VWAP divergence, buying/selling pressure |
| Volume | rel_volume_ratio, volume_trend, obv_slope | Volume profile, VWAP distance |
| Cross-asset | sector_vs_spy_5d | Beta vs sector, correlation vs peers, breadth |
| Macro | VIX, yields, gold/oil momentum | Credit spreads, PMI, real rates |
| Regime interactions | 5 interaction terms (v1.5) | Yield curve × sector sensitivity |

4. **Macro features have zero cross-sectional power** — VIX, yields, gold/oil momentum are identical for all tickers on a given date. The v1.5 interaction terms partially address this but more cross-asset features needed.

**Training Pipeline:**

5. **Walk-forward fold generation mixes calendar and trading days** — `WF_TEST_WINDOW_DAYS` is in calendar days but folds are generated by unique trading dates. Holiday clusters create misaligned expectations.

6. **Single-split fallback is weak** — if walk-forward fails (<3 folds), trains on 70/15/15 single split. Single-split IC is unreliable for model promotion.

7. **No cross-validation for feature selection** — features are manually curated across 5 generations. No automated feature selection or pruning based on incremental IC contribution.

**Monitoring:**

8. **No per-feature IC tracking** — only aggregate IC monitored. Individual feature predictive power could degrade silently.

**Label Construction:**

9. **Label winsorization at ±15%** clips legitimate earnings gap alpha — stocks that gap 20% on earnings are clipped to 15%, reducing the model's ability to learn from extreme events.

---

### 3. Executor (`~/Development/alpha-engine`)

#### Open Gaps

**Execution Quality:**

1. **No connection heartbeat** — IB Gateway connection created once at startup. If Gateway restarts mid-execution, executor crashes with no recovery.

**Risk Management:**

2. **No volatility-adjusted position sizing** — position sizes don't scale with VIX or realized volatility. High-vol environments get same sizing as low-vol.

3. **No cross-ticker correlation monitoring** — hidden concentration risk when multiple correlated positions are held (e.g., MSFT + AAPL + GOOGL all correlated >0.8).

4. **No profit-taking mechanism** — positions that gain 25%+ have no trim mechanism. Only exits: ATR stop, time decay, Research signal.

5. **Graduated drawdown only adjusts NEW entry sizing, not existing positions** — during -5% drawdown, new entries sized at 25% but existing positions untouched. No forced exits on lowest-conviction holdings during drawdown.

6. **No minimum position size check** — floor() share calculation can produce micro-positions (<$500) that aren't worth tracking.

**Exit Strategy:**

7. **No sector-relative exit** — if stock drops -15% but sector drops -20%, stock is outperforming. Current ATR stop is absolute price-based only.

8. **No momentum-based exit** — no exit trigger when 20-day momentum flips negative or RSI drops below 30.

9. **No portfolio-level heat map exit** — when portfolio drawdown exceeds threshold, no mechanism to force-exit lowest-conviction positions to raise cash.

10. **REDUCE always sells exactly 50%** — no configuration for partial reduction amounts (e.g., 33% or 25%).

**Signal Integration:**

11. **No signal staleness discount** — a 5-day-old signal is treated identically to today's signal. No score reduction for signal age.

12. **No earnings date awareness** — positions hold through earnings with no volatility adjustment or risk reduction. *Partial: executor now logs a warning when entering within 2 days of earnings, but no sizing adjustment yet.*

13. **S3 param load failure is silent** — if backtester-optimized params can't be read from S3, executor runs with defaults and logs at DEBUG level (not WARNING).

**EOD Reconciliation:**

14. **SPY return fetched via yfinance every EOD run** — not cached, rate-limiting risk.
15. **No alpha attribution by sector** — EOD email shows total alpha but not sector breakdown.
16. **No trade execution latency tracking** — time from signal to fill not measured.

---

### 4. Backtester (`~/Development/alpha-engine-backtester`)

#### Open Gaps

**Statistical Rigor:**

1. **No multiple testing correction** — across ~20-30 test statistics per run, no Bonferroni or Benjamini-Hochberg correction. Expected false positive rate: 30-50%.

**Simulation Realism:**

2. **No slippage simulation** — orders fill at close price on signal date. Real execution fills at next-day open with market impact.

3. **No fill simulation** — assumes 100% fill rate at exact price. Large orders in illiquid names have significant market impact.

**Optimization Integrity:**

4. **No recommendation stability tracking** — each week's recommendation is independent. System can flip-flop between contradictory recommendations (week 1: news=0.60; week 2: news=0.40) without detection.

5. **Aggressive blending masks data** — blend factor is 20% data-driven, 80% current. With 200+ samples and strong signal, this is overly conservative. Blend factor should scale with sample size.

6. **Baseline selection in executor optimizer can be misleading** — "closest combo" in sweep grid used as baseline. If closest combo happened to be terrible, improvement % is inflated.

**Veto Analysis:**

7. **Precision metric noisy on small samples** — if 1 DOWN prediction occurred and was correct, precision=100% (n=1). Sample size not factored into recommendation.

8. **No base rate accounting** — if 80% of BUY signals beat SPY anyway, a veto gate with 30% precision is barely better than random.

9. **Missed alpha not risk-weighted** — sums absolute returns of vetoed winners without volatility adjustment.

10. **Cost penalty weight (0.30) is arbitrary** — no justification or sensitivity analysis. Changing to 0.50 could flip the recommendation entirely.

**Data Quality:**

11. **Forward/backward fill masks price gaps** — if a ticker has 20-day gap (delisted temporarily), ffill repeats stale prices. Position sizing and alpha computed on fake data.

12. **No data freshness validation** — prices from S3 not checked for trading day validity (weekends, holidays).

---

### 5. Dashboard (`~/Development/alpha-engine-dashboard`)

#### Open Gaps

**Missing Critical Views:**

1. **No sector allocation visualization** — can't see portfolio concentration by sector. Essential for monitoring 25% sector limit.

2. **No veto status display** — executor has veto gate but dashboard can't show which ENTER signals are currently blocked by predictor.

3. **No correlation/concentration analysis** — can't see if holdings are clustered in correlated stocks.

4. **No position-level P&L** — can't see entry price, unrealized P&L, days held for each position.

**Missing Analysis Views:**

5. **No model drift tracking** — predictor page shows 30-day rolling hit rate but no long-term trend (6-month degradation chart).

6. **No regime-specific alpha tracking** — can't see portfolio alpha in bull vs bear markets.

7. **No win rate confidence intervals** — accuracy by score bucket shown without sample sizes or confidence bands.

8. **No sector rotation tracking over time** — can't see how sector allocations have shifted.

9. **No drawdown recovery speed analysis** — can't measure how quickly portfolio recovers from drawdowns.

**System Health:**

10. **Health checks lack historical context** — "Yesterday's signals present" is yellow badge but should be red after 48 hours.

11. **Backtester health only checks recency** — doesn't check if backtest FAILED, only if it ran recently.

12. **No executor failure detection** — IB Gateway health only checks eod_pnl entry exists, not whether executor actually processed trades.

**Data Loading:**

13. **Silent failures in S3 loader** — `_s3_get_object()` returns None on ANY exception without logging. Network errors, permission denials, and missing keys all look the same.

14. **Fragile schema assumptions** — hardcoded SQL and JSON field names throughout. Schema drift from upstream modules breaks pages silently.

---

## Open Optimization Opportunities

### Tier 1: Highest ROI (1-3 days each)

| # | Opportunity | Module | Expected Impact | Effort |
|---|------------|--------|----------------|--------|
| O1 | **Experiment with ranking loss** (lambdarank/NDCG) — current MSE+IC gate is sound but ranking loss may improve IC | Predictor | +5-10% IC improvement (uncertain) | 2 days |
| O3 | **Entry momentum confirmation gate** — 5d momentum > 0, price above 20d MA | Executor | Reduces bad entries 15-25% | 1 day |
| O4 | **Confidence-weighted sizing** — map p_up to continuous multiplier instead of binary veto | Executor | Better use of predictor signal | 1 day |
| O5 | **ATR-based position sizing** — `risk_per_trade / ATR` for volatility-aware sizing | Executor | Prevents single-stock blowups in volatile names | 1 day |

### Tier 2: Medium Effort, High Payoff (3-7 days each)

| # | Opportunity | Module | Expected Impact | Effort |
|---|------------|--------|----------------|--------|
| O9 | **3-model stacking ensemble** — LightGBM + XGBoost + CatBoost with linear meta-learner | Predictor | +10-15% accuracy improvement | 5 days |

### Tier 3: Larger Projects, High Payoff (1-3 weeks)

| # | Opportunity | Module | Expected Impact | Effort |
|---|------------|--------|----------------|--------|
| O17 | **Temporal ensemble** — train GBM on 3, 5, 7, 10-day horizons, blend predictions | Predictor | Captures multi-horizon alpha, reduces label noise | 1 week |
| O18 | **HMM regime detection** — 3-state Gaussian HMM on SPY returns + vol, output probabilities as features | Predictor | Better regime transition detection | 1 week |
| O19 | **Meta-labeling** — secondary model predicts BUY signal profitability, maps to continuous sizing | Predictor + Executor | Replaces binary veto with nuanced sizing | 1 week |
| O20 | **Credit spread + leading indicator integration** — HY-Treasury OAS, ISM PMI, jobless claims from FRED | Research + Predictor | Leads equity drawdowns 3-6 months | 1 week |
| O21 | **Cross-ticker correlation monitoring** — pairwise correlation of holdings, concentration alert | Executor + Dashboard | Detects hidden concentration risk | 1 week |
| O22 | **Purged combinatorial cross-validation (CPCV)** — replace single train/test split with multiple overlapping paths | Predictor | Prevents information leakage, more robust IC estimates | 1 week |
| O23 | **Profit-taking + portfolio heat map exits** — trim at +25%, force-exit lowest conviction during drawdown | Executor | Capital recycling, drawdown management | 1 week |

---

## Deep Dive: Alpha Optimization Strategy

### 1. Predictor Ensemble Architecture (O9, O17)

```
                    ┌─────────────┐
                    │  Features    │
                    │  (36 GBM +  │
                    │   new ones) │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼───┐ ┌─────▼─────┐
        │ LightGBM  │ │XGBoost│ │ CatBoost  │
        │(lambdarank│ │ (MSE) │ │ (ordered) │
        │  loss)    │ │       │ │           │
        └─────┬─────┘ └───┬───┘ └─────┬─────┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────▼──────┐
                    │ Linear Meta │
                    │  Learner    │
                    │ (IC-optimiz)│
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼───┐ ┌─────▼─────┐
        │  5-day    │ │ 3-day │ │  10-day   │
        │  horizon  │ │horizon│ │  horizon  │
        └─────┬─────┘ └───┬───┘ └─────┬─────┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────▼──────┐
                    │  Temporal   │
                    │   Blend    │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Final      │
                    │  Prediction │
                    └─────────────┘
```

**Implementation phases:**
1. Phase 1: Experiment with lambdarank loss (O1)
2. Phase 2: Add XGBoost + CatBoost, linear combiner (O9)
3. Phase 3: Add temporal ensemble across horizons (O17)

### 2. Position Sizing Innovation (O4, O5, O19)

Current sizing: `1/n_entries * sector_adj * conviction_adj * upside_adj * drawdown_adj`

Proposed layered sizing:

```
Layer 1: Base weight = 1 / n_entries (current)
Layer 2: ATR-adjusted = base * (target_risk / (ATR_14 * price))
Layer 3: Confidence-weighted = atr_adjusted * confidence_multiplier(p_up)
          p_up 0.50-0.55 → 0.25x
          p_up 0.55-0.65 → 0.50x
          p_up 0.65-0.75 → 0.75x
          p_up 0.75+      → 1.00x
Layer 4: Drawdown tier (current graduated response)
Layer 5: Cap at max_position_pct
```

### 3. Remaining Backtester Statistical Rigor

1. **Benjamini-Hochberg FDR correction** — with 20+ tests per run, apply FDR at α=0.05 to control false discovery rate.
2. **Recommendation stability tracking** — maintain 4-week rolling history. Flag as "unstable" if recommendation direction reverses.

### 4. Regime-Adaptive System (O18)

Current regime detection is LLM-subjective. Supplement with quantitative detection:

**Layer 1: Simple Regime Filter (immediate)**
```python
regime = "bull" if sma_20(spy_returns) > 0 else "bear"
```

**Layer 2: Quantitative Thresholds**
```yaml
regime_thresholds:
  bull: vix < 15 AND spy_30d_return > 0
  neutral: (not bull) AND (not bear) AND (not caution)
  caution: vix > 20 AND spy_30d_return < 0
  bear: vix > 25 OR spy_30d_return < -5%
```

**Layer 3: HMM Probabilistic (O18)**
- 3-state Gaussian HMM on [SPY daily returns, rolling 20d volatility]
- Outputs regime probabilities as predictor features
- 85.8% persistence in bull state → stable signals

---

## Deployment / Functional Open Items

### Resolved 2026-03-18

- **FMP_API_KEY**: Verified in Research and Predictor Lambda env vars.
- **EDGAR_IDENTITY**: Set in Research Lambda. `insider_fetcher.py` rewritten to use SEC EDGAR REST API directly (no edgartools dependency — eliminated 170MB of transitive deps).
- **Research Lambda**: Migrated from zip to container image deployment (Docker via ECR) to accommodate dependency size. Deploy script (`infrastructure/deploy.sh`) reads env vars from `.env` file automatically.
- **EventBridge schedules**: Restored via `setup-eventbridge.sh` after function recreation.
- **D4 — SHAP in Predictor Lambda**: Training runs on EC2 spot instances via `infrastructure/spot_train.sh`, which installs full `requirements.txt` (includes `shap>=0.42.0`). SHAP is only imported in `training/train_handler.py` (training path). The inference Lambda never imports SHAP. No deployment action needed.
- **F2 — FMP_API_KEY in Predictor inference Lambda**: Verified present in Lambda env vars via CLI (`aws lambda get-function-configuration`). Also added to predictor `.env` for local dev consistency.
- **F3 — Options fetcher optimization**: Predictor now reads Research's S3-cached options data (`archive/options/{date}.json`) before falling back to live yfinance fetch. Saves ~50s on days when Research runs first (Mon). `load_historical_options()` was already implemented in `options_fetcher.py`; wired into `daily_predict.py`.
- **F4 — No backfill of new features**: `feature_engineer.py:508-538` explicitly fills neutral values for all 7 O10-O12 features when data is missing. `dropna(subset=feature_cols)` ensures clean feature vectors. Historical parquets don't need backfill because alternative data is fetched fresh at inference/training time.
- **F5 — Earnings proximity sizing**: `position_sizer.py:95-104` implements full earnings-aware sizing: `earnings_sizing_enabled` defaults to `True`, reduces position size by 50% when `days_to_earnings <= 5`. The log-only warning in `main.py` is a separate notification, not the only behavior.
- **D6 — FRED_API_KEY in Research Lambda**: Key is set in Research `.env`. `infrastructure/deploy.sh` reads all non-LAMBDA_SKIP vars from `.env` and passes them to Lambda via `--environment` flag. Deployed automatically on every `deploy.sh` run.

### Still Open

| # | Item | Module | Notes |
|---|------|--------|-------|
| D7 | **Predictor Lambda container image migration** | Predictor | ZIP deployment is ~153 MB (under 250 MB limit). Container infrastructure (Dockerfile, ECR repo) is prepared as fallback. Monitor package size — no blocker today. |

---

## Expected Remaining Impact

| Category | Expected Sharpe Improvement | Expected Alpha Improvement | Confidence |
|----------|---------------------------|---------------------------|------------|
| Alpha Extraction (O3-O5) | +0.1-0.3 (volatility-aware sizing + momentum filter) | +1-3% annual from reduced bad entries | Medium-High |
| Model Evolution (O9, O17, O18) | +0.2-0.4 (ensemble + multi-horizon) | +3-7% annual from improved IC | Medium |
| Macro Signals (O20) | +0.05-0.1 (leading indicators) | +1-2% annual from drawdown avoidance | Medium |
| Dashboard & Observability | Indirect (faster problem detection) | Prevents silent degradation | High |

---

## Key References

- "Generating Alpha" (arXiv:2601.19504) — Hybrid AI system, CAGR 53.46%, Sharpe 1.68
- "Increase Alpha" (arXiv:2509.16707) — Sharpe 2.54, 3% max drawdown, grid-searched exits
- "Assets Forecasting with Feature Engineering for LightGBM" (arXiv:2501.07580) — Novel GBM features
- "Triple Barrier Labeling for Stock Prediction" (arXiv:2504.02249) — Alternative labeling
- Lopez de Prado, "Advances in Financial Machine Learning" — Meta-labeling, CPCV, purged CV
- JPM Factor Views Q1 2026 — Value leading, growth weakest
- FRED API — Free macroeconomic data (120 calls/min)
