# Alpha Engine System Audit — 2026-03-17

## Objective

Full system audit across all 5 modules (Research, Predictor, Executor, Backtester, Dashboard) to identify remaining gaps and optimization opportunities for long-term alpha generation.

Alpha = Portfolio Return - SPY Return

---

## Remediation Summary (2026-03-17)

All 7 CRITICAL and 10 of 11 HIGH findings have been resolved. H4 (single GBM model / ensemble) is deferred to Phase 4 model evolution work.

| Severity | Total | Fixed | Open | Fix Rate |
|----------|-------|-------|------|----------|
| CRITICAL | 7 | 7 | 0 | 100% |
| HIGH | 11 | 10 | 1 | 91% |
| **Total** | **18** | **17** | **1** | **94%** |

**Remaining open:** H4 (3-model ensemble — deferred, multi-week project)

**Repos updated:** alpha-engine (executor), alpha-engine-backtester, alpha-engine-predictor, alpha-engine-research, alpha-engine-dashboard

---

## Progress Since Last Audit (2026-03-14)

### Completed Items

| # | Item | Status |
|---|------|--------|
| 1 | Predictor veto gate activated | Done |
| 2 | ATR trailing stops in executor | Done |
| 3 | Time-based exit decay | Done |
| 4 | Graduated drawdown response | Done |
| 5 | Strategy layer architecture | Done |
| 6 | Backtester strategy sweep integration | Done |
| 7 | SimulatedIBKRClient rewrite (NAV tracking, entry_date, partial sell) | Done |
| 8 | Config override parameter for backtester → executor | Done |
| 9 | OHLCV capture in backtester build_matrix | Done |

### Still Open from Prior Audit

| # | Item | Prior Status |
|---|------|-------------|
| 6 | Entry momentum confirmation gate | Open |
| 8 | ATR-based position sizing | Open |
| 9 | SHAP feature importance monitoring | Open |
| 10 | Confidence-weighted sizing from Predictor | Open |
| 11 | PEAD signal integration | Open |
| 12 | 3-model ensemble | Open |
| 13 | Insider trading scanner | Open |
| 14 | HMM regime detection | Open |

---

## Critical Findings (All Modules)

### Severity: CRITICAL

| # | Module | Finding | Impact | Status |
|---|--------|---------|--------|--------|
| C1 | Executor | **No order fill confirmation** — `place_market_order()` returns after 1s sleep without waiting for fill status | Position tracking stale, slippage untracked, NAV inaccurate | **FIXED 2026-03-17** — polls up to 30s for fill, extracts fill_price/filled_shares/fill_time from trade.fills |
| C2 | Executor | **Order rejection not checked before logging trade** — if IB rejects order, fake trade logged to DB | Alpha/P&L calculations corrupted | **FIXED 2026-03-17** — ENTER/EXIT/REDUCE blocks check order status; Rejected/Timeout skip trade log |
| C3 | Executor | **No partial fill handling** — code assumes immediate full fill | Accounting errors compound over time | **FIXED 2026-03-17** — PartialFill status detected; filled_shares tracked independently of requested shares |
| C4 | Backtester | **Zero transaction costs in VectorBT simulation** — `fees=0.0` | Reported Sharpe overstated by ~0.3-0.5 annualized | **FIXED 2026-03-17** — fees=0.001 (10 bps) default, configurable via simulation_fees |
| C5 | Backtester | **No out-of-sample validation for optimizer** — weights applied from in-sample correlations only | Bad optimizations can propagate to live trading | **FIXED 2026-03-17** — weight optimizer: 70/30 train/test split, <20% degradation gate. Executor optimizer: holdout validation on last 30% of dates, Sharpe >= 50% of train |
| C6 | Backtester | **No rollback mechanism** — once params written to S3, no automatic revert if performance degrades | Overfitted params persist indefinitely | **FIXED 2026-03-17** — optimizer/rollback.py: save_previous() before every S3 write, rollback_all() via --rollback CLI flag |
| C7 | Predictor | **Misleading docstring** — `gbm_scorer.py:15` claims "early stopping on val IC" but early stopping is actually on MSE; IC is computed post-hoc for promotion gating. Design is sound (two-stage: optimize MSE → validate IC), but documentation is wrong | Low functional impact; docstring fix needed | **FIXED 2026-03-17** — docstring corrected to "Early stopping on validation MSE; IC evaluated post-hoc as a promotion gate" |

### Severity: HIGH

| # | Module | Finding | Impact | Status |
|---|--------|---------|--------|--------|
| H1 | Executor | No market hours validation — orders can be placed pre/post-market | Poor fills, unexpected execution | **FIXED 2026-03-17** — new market_hours.py blocks live orders outside NYSE 9:30-16:00 ET weekdays |
| H2 | Executor | Race condition between `get_positions()` and order placement | Order rejected but trade logged anyway | **FIXED 2026-03-17** — resolved by C1-C3 (order status checked before log_trade) |
| H3 | Executor | Contract qualification can crash `place_market_order()` (no try/except on line 103) | Unhandled exception kills executor run | **FIXED 2026-03-17** — qualifyContracts() wrapped in try/except, returns Rejected status on failure |
| H4 | Predictor | Single GBM model — no ensemble, no model diversity | Leaves 10-20% IC improvement on table | Open — deferred to Phase 4 (model evolution) |
| H5 | Predictor | Veto threshold hardcoded, not regime-adaptive | Too permissive in bear markets, too restrictive in bull | **FIXED 2026-03-17** — get_veto_threshold() now regime-adaptive: bear -0.10, caution -0.05, bull +0.05, clamped [0.40, 0.90] |
| H6 | Predictor | Label thresholds (±1%) fixed regardless of volatility regime | 2018 low-vol vs 2022 high-vol treated identically | **FIXED 2026-03-17** — label_generator supports adaptive_thresholds mode: rolling percentile-based UP/DOWN (63-day window). Opt-in via config |
| H7 | Research | Technical weight (0.40) in config is never applied to final_score | Config misleading; technical score generated but discarded from composite | **FIXED 2026-03-17** — removed technical weight from universe.yaml; rebalanced to news: 0.50, research: 0.50. Technical analysis is handled by Predictor/Executor only |
| H8 | Research | Silent exception swallowing across all fetchers (price, macro, news, analyst) | Debugging impossible; failures invisible | **FIXED 2026-03-17** — all bare except handlers in news_fetcher (4), macro_fetcher (5), price_fetcher (2) now log via logger.warning/debug |
| H9 | Backtester | No statistical significance tests — correlations reported without p-values | False positives drive weight optimization (~30-50% FPR with 20+ tests) | **FIXED 2026-03-17** — attribution.py uses scipy.stats.pearsonr for p-values; signal_quality.py adds Wilson score 95% CIs on all accuracy metrics; non-significant correlations flagged |
| H10 | Backtester | Sharpe ratio as sole optimization target — ignores drawdown risk | Fragile parameter sets promoted (one big win masks many losses) | **FIXED 2026-03-17** — executor optimizer ranks by combined score: Sharpe - drawdown_penalty_weight * max_drawdown (configurable, default 0.5) |
| H11 | Dashboard | No execution slippage monitoring anywhere in system | Can't measure actual vs expected fill quality | **FIXED 2026-03-17** — new pages/8_Slippage.py: mean/median/P95 slippage, distribution histogram, by-action/by-regime breakdowns, daily time series, worst events table |

---

## Module-by-Module Findings

### 1. Research (`~/Development/alpha-engine-research`)

#### Scoring System (Current)

```
final_score = news_score * w_news + research_score * w_research + macro_shift
macro_shift = (sector_modifier - 1.0) / 0.30 * 10.0  → range [-10, +10]
long_term_score = news_lt * 0.50 + research_lt * 0.50 + macro_shift
```

~~Note: Despite `technical: 0.40` in universe.yaml, technical score is NOT included in the composite. It's computed separately for the scanner filter only.~~
**UPDATE 2026-03-17:** Technical weight removed from universe.yaml. Config now reflects reality: news: 0.50, research: 0.50. Technical analysis is handled by Predictor (GBM) and Executor (ATR/time exits).

#### Gaps Identified

**Data Source Gaps:**

| Data Source | Status | Alpha Impact | Cost |
|-------------|--------|-------------|------|
| Options put/call ratio & IV skew | Missing | HIGH — validates/contradicts analyst sentiment | Free (yfinance options chain) |
| Earnings revision trends (week-over-week EPS consensus) | Missing | HIGH — "revisions up" is strong bullish signal | Free (diff FMP weekly) |
| SEC Form 4 insider transactions | Missing | MEDIUM — cluster buying is 6-12 month signal | Free (EdgarTools) |
| Short interest & borrow rates | Missing | MEDIUM — crowded trade risk flag | Free (finviz scrape) |
| Leading indicators (ISM PMI, jobless claims) | Missing | MEDIUM — leads equity drawdowns 3-6 months | Free (FRED) |
| Credit spreads (HY-Treasury OAS) | Missing | MEDIUM — risk-on/off indicator | Free (FRED) |
| Equity breadth (advance/decline, % above 50d MA) | Missing | MEDIUM — confirms/contradicts SPY price | Free (finviz scrape) |
| 13F institutional holdings changes | Missing | LOW — quarterly lag reduces timeliness | Free (SEC EDGAR) |

**LLM Agent Gaps:**

1. **Market regime definition is subjective** — macro agent uses bull/neutral/caution/bear labels with no quantitative thresholds. Different runs may classify the same data differently.
   - Fix: Define regimes mathematically (e.g., Bull: VIX < 15 AND SPY 30d return > 0; Bear: VIX > 25 OR SPY 30d return < -5%).

2. **News sentiment quantification is keyword-only** — recurring themes use word frequency, not semantic analysis. "China tariffs" (bearish) and "China market expansion" (bullish) are indistinguishable.
   - Fix: Add sentiment scoring (VADER or TextBlob) before passing to news agent, or use LLM-based theme sentiment.

3. **Prior report length unbounded** — if accumulated thesis is 5000 words, agent's output budget is consumed by context. No cap on prior_report size.
   - Fix: Truncate prior_report to most recent 500 words or last 3 months.

4. **Consistency check uses regex, not semantics** — `check_consistency()` in aggregator.py uses keyword matching. "Bullish but headwinds may resurface" gets bullish_hits=1, bearish_hits=1, classified as consistent (requires bullish > bearish).
   - Fix: Use LLM-based consistency check or require dominance ratio > 2:1.

**Scanner Pipeline Gaps:**

1. **No volatility screen** — high-volatility stocks pass if volume threshold met.
2. **No debt/balance sheet filter** — near-default companies can pass scanner.
3. **No sector concentration limit in candidates** — all 60 candidates could be Technology.
4. **Deep value path weak** — only checks RSI < 35 + single analyst "Buy" rating.
5. **No sub-sector (industry group) analysis** — semiconductors and SaaS treated identically as "Technology."

**Thesis Management:**

1. Stale thesis detection exists (`stale_days` counter) but is never surfaced in output — no visual "STALE" badge.
2. No forced thesis refresh trigger — stale theses accumulate without action.
3. No archive expiration — 6-month-old wrong theses remain in archive indefinitely.

**Survivorship Bias:**

1. Wikipedia S&P constituents are current-only — delisted stocks disappear from universe.
2. No tracking of stocks removed from S&P 500/400 and their subsequent performance.
3. Price floor ($10) creates look-ahead bias — recovered penny stocks included only after recovery.

---

### 2. Predictor (`~/Development/alpha-engine-predictor`)

#### Model Architecture (Current)

- **Model**: Single LightGBM regression
- **Objective**: MSE (mean squared error)
- **Target**: 5-day sector-neutral alpha (stock return - sector ETF return)
- **Features**: 24 GBM features (34 total, 5 macro-only excluded from GBM)
- **Training**: Walk-forward expanding window, 2000 estimators, early stopping at 50 rounds
- **IC Gate**: test_ic >= 0.03, IC IR >= 0.3 for weight promotion
- **Latest Performance**: test IC ~0.046, IC IR ~0.421

#### Gaps Identified

**Model Architecture Gaps:**

1. ~~**MSE training with IC promotion gate (LOW — docstring issue, not architectural flaw)** — The docstring at `gbm_scorer.py:15` incorrectly claims "early stopping on val IC" — this should be corrected.~~ **FIXED 2026-03-17** — docstring corrected. Design is sound: MSE learns accurate magnitude predictions, IC gating validates ranking quality. Switching to `objective='lambdarank'` could still improve IC by directly optimizing ranking, but it's an optimization opportunity, not a critical misalignment.

2. **Single model, no ensemble** — No model diversity. Literature shows 3-model stacking (LightGBM + XGBoost + CatBoost with logistic regression meta-learner) typically improves accuracy 10-15%.

3. **No temporal ensemble** — Only predicts 5-day returns. Training on 3, 5, 7, 10-day horizons and blending captures multi-horizon alpha and reduces label noise sensitivity.

4. **Inactive MLP alternative** — `model/predictor.py` contains a DirectionPredictor MLP (v1.2.0) but it's not used in the GBM training pipeline. Dead code that could be activated for ensemble.

**Feature Engineering Gaps:**

| Feature Category | Current | Missing |
|-----------------|---------|---------|
| Momentum | 7+ variants (RSI, MACD, momentum_5d/20d, price_accel) | VWAP divergence, buying/selling pressure |
| Volume | rel_volume_ratio, volume_trend, obv_slope | Volume profile, VWAP distance |
| Volatility | atr_14_pct, realized_vol_20d, vol_ratio_10_60 | Options-implied vol, IV rank |
| Cross-asset | sector_vs_spy_5d | Beta vs sector, correlation vs peers, breadth |
| Macro | VIX, yields, gold/oil momentum | Credit spreads, PMI, real rates |
| Regime interactions | 5 interaction terms (v1.5) | Yield curve × sector sensitivity |
| Fundamental | None | Earnings surprise, analyst revisions |

5. **Macro features have zero cross-sectional power** — VIX, yields, gold/oil momentum are identical for all tickers on a given date. They only help GBM learn regime-dependent splits but contribute nothing to cross-sectional ranking. The v1.5 interaction terms (mom5d_x_vix, etc.) partially address this but more cross-asset features needed.

**Training Pipeline Gaps:**

6. **Walk-forward fold generation mixes calendar and trading days** — `WF_TEST_WINDOW_DAYS` is in calendar days but folds are generated by unique trading dates. Holiday clusters create misaligned expectations.

7. **Single-split fallback is weak** — if walk-forward fails (<3 folds), trains on 70/15/15 single split. Single-split IC is unreliable for model promotion.

8. **No cross-validation for feature selection** — features are manually curated across 5 generations. No automated feature selection or pruning based on incremental IC contribution.

**Monitoring Gaps:**

9. **No feature importance drift monitoring** — top 10 features logged in training emails but no week-over-week comparison or alerting when feature rankings shift dramatically.

10. **No per-feature IC tracking** — only aggregate IC monitored. Individual feature predictive power could degrade silently.

11. **Gain-based feature importance is biased** — high-variance features (VIX, momentum) score high even if noisy. SHAP TreeExplainer would give more reliable incremental importance.

**Label Construction Gaps:**

12. ~~**Fixed ±1% direction thresholds** — not adaptive to volatility regime. In 2018 (low vol), ±1% was achievable; in 2022 (high vol), ±1% is too easy. Better: percentile-based thresholds (e.g., top/bottom quartile of cross-sectional returns).~~ **FIXED 2026-03-17** — label_generator supports adaptive_thresholds mode with rolling percentile-based thresholds. Opt-in via config.

13. **Label winsorization at ±15%** clips legitimate earnings gap alpha — stocks that gap 20% on earnings are clipped to 15%, reducing the model's ability to learn from extreme events.

---

### 3. Executor (`~/Development/alpha-engine`)

#### Trading Loop (Current)

```
Read signals.json → Connect IB Gateway → Fetch NAV/positions →
Process strategy exits (ATR stops, time decay) →
Merge with Research exits → Process ENTER signals →
Risk guard → Position sizer → Market orders →
Backup trades.db to S3
```

#### Gaps Identified

**Execution Quality Gaps (CRITICAL):**

1. ~~**No fill confirmation polling** — `place_market_order()` sleeps 1 second and returns. No check for "Filled", "Rejected", "Cancelled" status. If IB Gateway disconnects mid-order, executor proceeds as if order filled.~~ **FIXED 2026-03-17**

2. ~~**No slippage tracking** — `price_at_order` (current market price when order placed) captured but `actual_fill_price` from IB trade object never captured. Slippage is invisible.~~ **FIXED 2026-03-17** — fill_price, filled_shares, fill_time now captured and logged

3. ~~**Order rejection not validated** — `order_result` may have `status="Rejected"` but code proceeds to `log_trade()` regardless. Creates phantom trades in DB.~~ **FIXED 2026-03-17**

4. **No connection heartbeat** — IB Gateway connection created once at startup. If Gateway restarts mid-execution, executor crashes with no recovery. *Open*

**Risk Management Gaps:**

5. ~~**No market hours gate** — orders can be placed pre-market or after-hours with no validation. Pre-market fills at poor prices.~~ **FIXED 2026-03-17** — market_hours.py blocks live orders outside NYSE 9:30-16:00 ET

6. **No volatility-adjusted position sizing** — position sizes don't scale with VIX or realized volatility. High-vol environments get same sizing as low-vol.

7. **No cross-ticker correlation monitoring** — hidden concentration risk when multiple correlated positions are held (e.g., MSFT + AAPL + GOOGL all correlated >0.8).

8. **No profit-taking mechanism** — positions that gain 25%+ have no trim mechanism. Only exits: ATR stop, time decay, Research signal.

9. **Graduated drawdown only adjusts NEW entry sizing, not existing positions** — during -5% drawdown, new entries sized at 25% but existing positions untouched. No forced exits on lowest-conviction holdings during drawdown.

10. **No minimum position size check** — floor() share calculation can produce micro-positions (<$500) that aren't worth tracking.

**Exit Strategy Gaps:**

11. **No sector-relative exit** — if stock drops -15% but sector drops -20%, stock is outperforming. Current ATR stop is absolute price-based only.

12. **No momentum-based exit** — no exit trigger when 20-day momentum flips negative or RSI drops below 30.

13. **No portfolio-level heat map exit** — when portfolio drawdown exceeds threshold, no mechanism to force-exit lowest-conviction positions to raise cash.

14. **REDUCE always sells exactly 50%** — no configuration for partial reduction amounts (e.g., 33% or 25%).

**Signal Integration Gaps:**

15. **No signal staleness discount** — a 5-day-old signal is treated identically to today's signal. No score reduction for signal age.

16. **No earnings date awareness** — positions hold through earnings with no volatility adjustment or risk reduction.

17. **S3 param load failure is silent** — if backtester-optimized params can't be read from S3, executor runs with defaults and logs at DEBUG level (not WARNING).

**EOD Reconciliation Gaps:**

18. **SPY return fetched via yfinance every EOD run** — not cached, rate-limiting risk.
19. **No alpha attribution by sector** — EOD email shows total alpha but not sector breakdown.
20. **No trade execution latency tracking** — time from signal to fill not measured.

---

### 4. Backtester (`~/Development/alpha-engine-backtester`)

#### Capabilities (Current)

- Signal quality analysis (accuracy at 10d/30d, by score bucket, by regime, by conviction)
- Sub-score attribution (correlate news/research with outperformance)
- Weight optimization (blended correlation → suggested weights, with guardrails)
- Executor parameter sweep (grid search optimized on Sharpe)
- VectorBT portfolio simulation (Sharpe, max drawdown, Calmar, win rate, alpha)
- Predictor veto threshold analysis (auto-tune veto confidence)

#### Gaps Identified

**Statistical Rigor Gaps (HIGH):**

1. ~~**No p-values or significance tests** — all correlations reported as point estimates without p-values. A correlation of 0.15 on 50 samples has p≈0.27 (not significant) but is reported as if meaningful.~~ **FIXED 2026-03-17** — attribution.py uses scipy.stats.pearsonr; non-significant (p>0.05) flagged

2. **No multiple testing correction** — across ~20-30 test statistics per run (accuracy at multiple thresholds, attribution correlations, veto precision), no Bonferroni or Benjamini-Hochberg correction. Expected false positive rate: 30-50%. *Open*

3. ~~**No confidence intervals** — accuracy reported as "58%" without Wilson score interval. On 10 samples, 95% CI is [33%, 77%] — statistically indistinguishable from coin flip.~~ **FIXED 2026-03-17** — Wilson score 95% CIs on all accuracy metrics via _wilson_ci()

4. **MIN_SAMPLES = 10 is too low** — 10 samples is dangerously small for any statistical conclusion. Should be ≥30 minimum. *Open*

5. **Score bucket analysis reports buckets with <20 samples** — small buckets are unreliable but displayed without caveat. *Open*

**Simulation Realism Gaps (CRITICAL):**

6. ~~**Zero transaction costs** — `fees=0.0` in VectorBT. With 50-100 trades/month, this overstates Sharpe by ~0.3-0.5 annualized.~~ **FIXED 2026-03-17** — fees=0.001 (10 bps) default

7. **No slippage simulation** — orders fill at close price on signal date. Real execution fills at next-day open with market impact. *Open*

8. **No fill simulation** — assumes 100% fill rate at exact price. Large orders in illiquid names have significant market impact. *Open*

**Optimization Integrity Gaps (HIGH):**

9. ~~**No cross-validation in weight optimizer** — correlations computed on full in-sample data. No train/test split to validate that weight recommendations generalize.~~ **FIXED 2026-03-17** — 70/30 chronological split, <20% degradation gate

10. ~~**No out-of-sample validation for executor optimizer** — parameter sweep runs on historical data; best params applied without holdout validation.~~ **FIXED 2026-03-17** — holdout validation on last 30% of dates, Sharpe >= 50% of train required

11. **No recommendation stability tracking** — each week's recommendation is independent. System can flip-flop between contradictory recommendations (week 1: news=0.60; week 2: news=0.40) without detection. *Open*

12. ~~**No rollback mechanism** — once weights written to S3, no automatic revert. Previous params not stored.~~ **FIXED 2026-03-17** — save_previous() before every S3 write; --rollback CLI flag

13. **Aggressive blending masks data** — blend factor is 20% data-driven, 80% current. With 200+ samples and strong signal, this is overly conservative. Blend factor should scale with sample size.

14. **Baseline selection in executor optimizer can be misleading** — "closest combo" in sweep grid used as baseline. If closest combo happened to be terrible, improvement % is inflated.

**Veto Analysis Gaps:**

15. **Precision metric noisy on small samples** — if 1 DOWN prediction occurred and was correct, precision=100% (n=1). Sample size not factored into recommendation.

16. **No base rate accounting** — if 80% of BUY signals beat SPY anyway, a veto gate with 30% precision is barely better than random.

17. **Missed alpha not risk-weighted** — sums absolute returns of vetoed winners without volatility adjustment.

18. **Cost penalty weight (0.30) is arbitrary** — no justification or sensitivity analysis. Changing to 0.50 could flip the recommendation entirely.

**Data Quality Gaps:**

19. **Forward/backward fill masks price gaps** — if a ticker has 20-day gap (delisted temporarily), ffill repeats stale prices. Position sizing and alpha computed on fake data.

20. **No data freshness validation** — prices from S3 not checked for trading day validity (weekends, holidays).

---

### 5. Dashboard (`~/Development/alpha-engine-dashboard`)

#### Coverage (Current)

7 pages: Home (system health), Portfolio (NAV vs SPY, drawdown, positions), Signals (daily table), Signal Quality (accuracy trends), Research (thesis timeline), Backtester (param sweep heatmap), Predictor (hit rate, IC, calibration).

#### Gaps Identified

**Missing Critical Views:**

1. **No sector allocation visualization** — can't see portfolio concentration by sector. Essential for monitoring 25% sector limit.

2. **No veto status display** — executor has veto gate but dashboard can't show which ENTER signals are currently blocked by predictor.

3. ~~**No execution quality monitoring** — no view of fill prices, slippage, rejection rates.~~ **FIXED 2026-03-17** — pages/8_Slippage.py

4. **No correlation/concentration analysis** — can't see if holdings are clustered in correlated stocks.

5. **No position-level P&L** — can't see entry price, unrealized P&L, days held for each position.

**Missing Analysis Views:**

6. **No model drift tracking** — predictor page shows 30-day rolling hit rate but no long-term trend (6-month degradation chart).

7. **No regime-specific alpha tracking** — can't see portfolio alpha in bull vs bear markets.

8. **No win rate confidence intervals** — accuracy by score bucket shown without sample sizes or confidence bands.

9. **No sector rotation tracking over time** — can't see how sector allocations have shifted.

10. **No drawdown recovery speed analysis** — can't measure how quickly portfolio recovers from drawdowns.

**System Health Gaps:**

11. **Health checks lack historical context** — "Yesterday's signals present" is yellow badge but should be red after 48 hours.

12. **Backtester health only checks recency** — doesn't check if backtest FAILED, only if it ran recently.

13. **No executor failure detection** — IB Gateway health only checks eod_pnl entry exists, not whether executor actually processed trades.

**Data Loading Issues:**

14. **Silent failures in S3 loader** — `_s3_get_object()` returns None on ANY exception without logging. Network errors, permission denials, and missing keys all look the same.

15. **Fragile schema assumptions** — hardcoded SQL and JSON field names throughout. Schema drift from upstream modules breaks pages silently.

---

## Alpha Optimization Opportunities

### Tier 1: Highest ROI (1-3 days each)

| # | Opportunity | Module | Expected Impact | Effort |
|---|------------|--------|----------------|--------|
| O1 | **Experiment with ranking loss** (lambdarank/NDCG) — current MSE+IC gate is sound but ranking loss may improve IC | Predictor | +5-10% IC improvement (uncertain) | 2 days |
| O2 | ~~**Add transaction costs to simulation** (10 bps round-trip)~~ | Backtester | Realistic Sharpe estimates | 0.5 day | **DONE** |
| O3 | **Entry momentum confirmation gate** — 5d momentum > 0, price above 20d MA | Executor | Reduces bad entries 15-25% | 1 day |
| O4 | **Confidence-weighted sizing** — map p_up to continuous multiplier instead of binary veto | Executor | Better use of predictor signal | 1 day |
| O5 | **ATR-based position sizing** — `risk_per_trade / ATR` for volatility-aware sizing | Executor | Prevents single-stock blowups in volatile names | 1 day |
| O6 | **SHAP feature importance monitoring** — add TreeExplainer to weekly retrain | Predictor | Detect feature drift, guide pruning | 1 day |
| O7 | ~~**Add p-values and confidence intervals** to all backtester statistics~~ | Backtester | Prevent false-positive-driven optimization | 1 day | **DONE** |
| O8 | **Raise MIN_SAMPLES to 30**, flag buckets <20 as exploratory | Backtester | More reliable statistical conclusions | 0.5 day |

### Tier 2: Medium Effort, High Payoff (3-7 days each)

| # | Opportunity | Module | Expected Impact | Effort |
|---|------------|--------|----------------|--------|
| O9 | **3-model stacking ensemble** — LightGBM + XGBoost + CatBoost with linear meta-learner | Predictor | +10-15% accuracy improvement | 5 days |
| O10 | **PEAD signal integration** — earnings surprise direction + magnitude as feature and score boost | Research + Predictor | Well-documented alpha source (6.78% quarterly excess in top quintile) | 3 days |
| O11 | **Earnings revision tracking** — weekly diff of FMP EPS consensus, add as predictor feature | Research + Predictor | Strong short-term signal | 2 days |
| O12 | **Options-derived signals** — put/call ratio, IV rank from yfinance options chain | Research + Predictor | Orthogonal to momentum-heavy feature set | 3 days |
| O13 | **Insider trading scanner** — SEC Form 4 cluster buying via EdgarTools | Research | 6-12 month signal, zero data cost | 2 days |
| O14 | ~~**Regime-adaptive label thresholds** — percentile-based UP/DOWN instead of fixed ±1%~~ | Predictor | Better label quality across volatility regimes | 2 days | **DONE** |
| O15 | ~~**Cross-validation in weight optimizer** — 70/30 train/test split, validate before applying~~ | Backtester | Prevents overfitted weight recommendations | 2 days | **DONE** |
| O16 | ~~**Recommendation rollback mechanism** — store previous params, auto-revert on degradation~~ | Backtester | Safety net for auto-optimization | 2 days | **DONE** |

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

The single GBM model is the system's biggest bottleneck for predictive accuracy. Recommended ensemble architecture:

```
                    ┌─────────────┐
                    │  Features    │
                    │  (24 GBM +  │
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
1. Phase 1: Experiment with lambdarank loss (O1) — current MSE+IC gate design is sound, but ranking loss may further improve IC
2. Phase 2: Add XGBoost + CatBoost, train on same data, linear combiner (O9) — +10-15%
3. Phase 3: Add temporal ensemble across horizons (O17) — +5% and robustness

### 2. New Data Signals (O10-O13, O20)

Priority order based on signal strength and implementation cost:

**A. Earnings-Related (Highest Expected Alpha)**

1. **Post-Earnings Announcement Drift (PEAD)** — stocks drift in earnings surprise direction for 5-20 days. Top quintile surprise = 6.78% quarterly excess returns. Implementation: fetch surprise data from yfinance/FMP earnings calendar, add as predictor feature and research score boost.

2. **Earnings Revision Momentum** — rising EPS estimates are strongly predictive. Implementation: weekly diff of FMP consensus, track 4-week revision direction. Feature: `eps_revision_4w` (positive = estimates rising).

**B. Market Microstructure**

3. **Options-Implied Signals** — put/call ratio and IV rank capture positioning that fundamental analysis misses. High put/call ratio (>1.5) on a BUY signal suggests the options market disagrees. Implementation: `yfinance.Ticker(sym).options` chain analysis.

4. **Insider Trading** — cluster buying by 3+ C-level insiders within 30 days is one of the strongest long-term signals. Implementation: EdgarTools Form 4 parsing, score boost when cluster detected.

**C. Macro Enhancement**

5. **Credit Spreads + Leading Indicators** — HY-Treasury OAS widens 3-6 months before equity drawdowns. Combined with ISM PMI and jobless claims, creates a recession probability indicator. Implementation: FRED API (free, 120 calls/min).

### 3. Position Sizing Innovation (O4, O5, O19)

Current sizing: `1/n_entries * sector_adj * conviction_adj * upside_adj * drawdown_adj`

Proposed: layered sizing that extracts more value from the predictor and manages volatility:

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

This extracts continuous value from the predictor (not binary veto) and naturally sizes smaller in volatile names.

### 4. Backtester Statistical Rigor (O7, O8, O15, O16)

The backtester is the system's learning mechanism but currently lacks the statistical rigor to distinguish signal from noise:

**Required additions:**

1. **P-values for all correlations** — `scipy.stats.pearsonr()` returns (r, p). Report both. Flag p > 0.05 as "not significant."

2. **Benjamini-Hochberg FDR correction** — with 20+ tests per run, apply FDR at α=0.05 to control false discovery rate.

3. **Wilson score intervals for accuracy** — replace "accuracy = 58%" with "accuracy = 58% [95% CI: 45%-70%, n=40]".

4. **Cross-validation in optimizer** — split score_performance into 70/30 train/test. Compute correlations on train, validate on test. Only apply weights if test-set performance within 20% of train.

5. **Recommendation stability tracking** — maintain 4-week rolling history of recommendations. Flag as "unstable" if recommendation direction reverses (e.g., news weight goes from 0.55 → 0.45 → 0.55).

6. **Rollback mechanism** — store `previous_params.json` alongside current params in S3. If live performance degrades >15% from backtest Sharpe within 2 weeks, auto-revert.

### 5. Regime-Adaptive System (O14, O18)

Current regime detection is LLM-subjective (macro agent assigns bull/neutral/caution/bear). This should be supplemented with quantitative regime detection:

**Layer 1: Simple Regime Filter (immediate)**
```python
regime = "bull" if sma_20(spy_returns) > 0 else "bear"
```
Near-zero compute cost, applied to label thresholds and position sizing.

**Layer 2: Quantitative Thresholds (replace LLM subjectivity)**
```yaml
regime_thresholds:
  bull: vix < 15 AND spy_30d_return > 0
  neutral: (not bull) AND (not bear) AND (not caution)
  caution: vix > 20 AND spy_30d_return < 0
  bear: vix > 25 OR spy_30d_return < -5%
```

**Layer 3: HMM Probabilistic (O18, higher effort)**
- 3-state Gaussian HMM on [SPY daily returns, rolling 20d volatility]
- Outputs regime probabilities (e.g., P(bull)=0.7, P(neutral)=0.25, P(bear)=0.05)
- Feed probabilities as predictor features
- 85.8% persistence in bull state → stable signals

---

## Recommended Implementation Roadmap

### Phase 1: Foundation Fixes (Week 1-2)

| # | Item | Module | Effort | Priority | Status |
|---|------|--------|--------|----------|--------|
| 1 | Fix order fill confirmation + rejection handling | Executor | 1 day | CRITICAL | **DONE 2026-03-17** |
| 2 | Add transaction costs to VectorBT (10 bps) | Backtester | 0.5 day | CRITICAL | **DONE 2026-03-17** |
| 3 | Experiment with lambdarank loss (optimization opportunity, current MSE+IC gate design is sound) | Predictor | 2 days | MEDIUM | Open |
| 4 | Add p-values + CI to backtester statistics | Backtester | 1 day | HIGH | **DONE 2026-03-17** |
| 5 | Raise MIN_SAMPLES to 30 | Backtester | 0.5 day | HIGH | Open |
| 6 | Add market hours gate | Executor | 0.5 day | HIGH | **DONE 2026-03-17** |
| 7 | Fix silent exception swallowing in fetchers | Research | 1 day | HIGH | **DONE 2026-03-17** |

### Phase 2: Alpha Extraction (Week 3-4)

| # | Item | Module | Effort | Priority | Status |
|---|------|--------|--------|----------|--------|
| 8 | Entry momentum confirmation gate | Executor | 1 day | HIGH | Open |
| 9 | ATR-based position sizing | Executor | 1 day | HIGH | Open |
| 10 | Confidence-weighted sizing from predictor | Executor | 1 day | HIGH | Open |
| 11 | SHAP feature importance monitoring | Predictor | 1 day | MEDIUM | Open |
| 12 | Cross-validation in weight optimizer | Backtester | 2 days | HIGH | **DONE 2026-03-17** |
| 13 | Recommendation rollback mechanism | Backtester | 1 day | MEDIUM | **DONE 2026-03-17** |

### Phase 3: New Signals (Week 5-8)

| # | Item | Module | Effort | Priority | Status |
|---|------|--------|--------|----------|--------|
| 14 | PEAD signal integration | Research + Predictor | 3 days | HIGH | Open |
| 15 | Earnings revision tracking | Research + Predictor | 2 days | HIGH | Open |
| 16 | Options-derived signals (put/call, IV rank) | Research + Predictor | 3 days | MEDIUM | Open |
| 17 | Insider trading scanner (Form 4) | Research | 2 days | MEDIUM | Open |
| 18 | Regime-adaptive label thresholds | Predictor | 2 days | MEDIUM | **DONE 2026-03-17** |

### Phase 4: Model Evolution (Week 9-12)

| # | Item | Module | Effort | Priority | Status |
|---|------|--------|--------|----------|--------|
| 19 | 3-model stacking ensemble | Predictor | 5 days | HIGH | Open |
| 20 | Temporal ensemble (multi-horizon) | Predictor | 5 days | MEDIUM | Open |
| 21 | HMM regime detection | Predictor | 5 days | MEDIUM | Open |
| 22 | Credit spread + leading indicators | Research + Predictor | 5 days | MEDIUM | Open |
| 23 | Cross-ticker correlation monitoring | Executor + Dashboard | 5 days | MEDIUM | Open |

### Phase 5: Dashboard & Observability (Ongoing)

| # | Item | Module | Effort | Status |
|---|------|--------|--------|--------|
| 24 | Sector allocation visualization | Dashboard | 1 day | Open |
| 25 | Execution quality monitoring page | Dashboard | 2 days | **DONE 2026-03-17** |
| 26 | Position-level P&L view | Dashboard | 1 day | Open |
| 27 | Predictor drift tracking (long-term hit rate trend) | Dashboard | 1 day | Open |
| 28 | Regime-specific alpha analysis | Dashboard | 1 day | Open |
| 29 | Risk report page (concentration, correlation, liquidity) | Dashboard | 3 days | Open |

---

## Expected Impact Summary

| Phase | Expected Sharpe Improvement | Expected Alpha Improvement | Confidence |
|-------|---------------------------|---------------------------|------------|
| Phase 1 (Foundation) | +0.1-0.2 (more realistic measurement + better fills) | Prevents alpha leakage from bad fills | High |
| Phase 2 (Alpha Extraction) | +0.1-0.3 (volatility-aware sizing + momentum filter) | +1-3% annual from reduced bad entries | Medium-High |
| Phase 3 (New Signals) | +0.1-0.2 (orthogonal signal sources) | +2-5% annual from earnings/options alpha | Medium |
| Phase 4 (Model Evolution) | +0.2-0.4 (ensemble + multi-horizon) | +3-7% annual from improved IC | Medium |
| Phase 5 (Observability) | Indirect (faster problem detection) | Prevents silent degradation | High |

**Cumulative estimated impact: +0.5-1.1 Sharpe, +6-15% annual alpha** (with significant uncertainty — these are literature-based estimates, not backtested on this system's data).

---

## Key References

- "Generating Alpha" (arXiv:2601.19504) — Hybrid AI system, CAGR 53.46%, Sharpe 1.68
- "Increase Alpha" (arXiv:2509.16707) — Sharpe 2.54, 3% max drawdown, grid-searched exits
- "Assets Forecasting with Feature Engineering for LightGBM" (arXiv:2501.07580) — Novel GBM features
- "Triple Barrier Labeling for Stock Prediction" (arXiv:2504.02249) — Alternative labeling
- Lopez de Prado, "Advances in Financial Machine Learning" — Meta-labeling, CPCV, purged CV
- JPM Factor Views Q1 2026 — Value leading, growth weakest
- EdgarTools — Free Python library for SEC insider/institutional data
- FRED API — Free macroeconomic data (120 calls/min)
