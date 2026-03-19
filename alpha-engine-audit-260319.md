# Alpha Engine System Audit — 2026-03-19

## Objective

Open issues across all 5 modules, prioritized by milestone:

1. **M1 — Reliability** — No crashes, no silent failures. The system runs every trading day without intervention.
2. **M2 — Alpha Readiness** — All components are correctly wired, risk rules are sound, signals are fresh, and the feedback loop is working. The system is *capable* of generating alpha.
3. **M3 — Maximize Alpha** — Feature engineering, model architecture, execution strategy, and parameter optimization to sustain and grow alpha.

Once M1 and M2 are solid, M3 becomes the ongoing focus.

---

## What's Been Closed Since Last Audit (2026-03-18a)

| Item | Module | Fix |
|------|--------|-----|
| P0-10 | Executor | EOD S3 signal/prediction load now returns warnings instead of silent `{}` |
| P0-11 | Executor | ATR stop fallback — 10% fixed stop when price history insufficient |
| D-1 through D-16 | Dashboard | All 14 dashboard audit gaps addressed (S3 error tracking, health escalation, backtester/executor failure detection, veto display, position P&L, sector rotation, model drift, drawdown recovery, schema hardening) |
| D-5 | Dashboard | Schema mismatch fixed (`score` → `composite_score` alias in loader) |
| D-17 | Dashboard | Nginx HTTP → HTTPS redirect added |
| — | Predictor | Dual-model inference (MSE + lambdarank side by side), direction thresholds widened to ±2%, both models always uploaded to S3 |
| — | Predictor | `hit_rate_30d_rolling=null` TypeError fixed |
| — | Executor | Position sectors enriched from signals.json in EOD reconciliation |
| — | Dashboard | Public site deployed at nousergon.ai |

---

## M1 — Reliability

These items can cause the system to stop running, crash mid-execution, or produce no output for a trading day.

### CRITICAL

| # | Module | Issue | File | Impact |
|---|--------|-------|------|--------|
| M1-1 | Research | No S3 retry/backoff — single transient error aborts entire pipeline | `archive/manager.py:45-68` | No signals.json → predictor + executor have no input |
| M1-2 | Research | signals.json write has no error handling — S3 put failure → executor reads stale signals | `archive/manager.py:375-381` | Executor trades on yesterday's stale signals |
| M1-3 | Executor | No IB Gateway reconnect — connection created once, no recovery on Gateway restart | `executor/main.py:244-250` | Mid-execution crash, lost orders, unrecorded positions |
| M1-4 | Executor | ibkr.disconnect() missing in error paths — resource leak on repeated failures | `executor/main.py:202-215` | Zombie connections accumulate |
| M1-5 | Executor | current_price can be None → TypeError in position sizer | `executor/position_sizer.py:89-102` | Order crashes if price fetch returns None |
| M1-6 | Predictor | No Lambda timeout protection — 900s limit with no soft timeout or checkpoint | `inference/daily_predict.py` (main) | yfinance batch hangs → Lambda times out → no predictions |
| M1-7 | Research | No config validation at startup — missing ANTHROPIC_API_KEY discovered mid-graph | `lambda/handler.py:106-130` | Entire Lambda run wasted before first LLM call fails |

### HIGH

| # | Module | Issue | File | Impact |
|---|--------|-------|------|--------|
| M1-8 | Research | Price fetch failure returns {} — scanner runs with no price data, returns 0 candidates | `data/fetchers/price_fetcher.py:75-85` | Graph continues with empty universe |
| M1-9 | Research | All fetcher failures silent — news, analyst, macro, insider return empty on any error | Multiple fetchers | Agents receive no data, produce generic theses |
| M1-10 | Predictor | GBM feature count not validated at inference — feature list mismatch crashes Lambda | `inference/daily_predict.py:1900-2010` | Full inference failure on config/model drift |
| M1-11 | Research | JSON parse failure in load_thesis_json returns None silently | `archive/manager.py:291-293` | Thesis data lost without notification |
| M1-12 | Research | Schema migration uses bare `except: pass` — masks real DDL errors | `archive/manager.py:252-254` | Database corruption goes unnoticed |
| M1-13 | Research | No token limit enforcement before agent calls | `config.py:97-98` | Agent call exceeds token limit, fails mid-run |
| M1-14 | Research | deploy.sh ACCOUNT_ID extraction can fail → invalid ECR repo | `infrastructure/deploy.sh:29-31` | Broken deployment |
| M1-15 | Predictor | Stale price data not flagged in predictions output | `inference/daily_predict.py:600-800` | Predictions based on stale prices look fresh |
| M1-16 | Predictor | Daily closes vs slim cache circular dependency — both fail → silent skip | `inference/daily_predict.py`, `training/train_handler.py` | Missing data with no error |

### MEDIUM

| # | Module | Issue | File | Impact |
|---|--------|-------|------|--------|
| M1-17 | Research | flow-doctor init failure silently ignored | `lambda/handler.py:46` | No observability when flow-doctor breaks |
| M1-18 | Research | .env parsing hand-rolled — quotes in values not handled | `infrastructure/deploy.sh:116-119` | Deployment failure on certain env vars |
| M1-19 | Research | Dependencies not pinned — langgraph, yfinance, edgartools break on update | `requirements.txt` | Random breakage on next deploy |
| M1-20 | Executor | Migration swallows all exceptions, not just "column exists" | `executor/trade_logger.py:72-77` | Database migration errors hidden |
| M1-21 | Executor | Market hours gate at end — wastes CPU if pre-market | `executor/main.py:237-240` | Unnecessary resource usage |
| M1-22 | Executor | Secrets in crontab (GMAIL_APP_PASSWORD inline) | `infrastructure/add-cron.sh:40-44` | Credential exposure in process list |
| M1-23 | Executor | First-day NAV returns None — EOD email may not handle | `executor/eod_reconcile.py:223-229` | EOD email crash on first trading day |
| M1-24 | Predictor | No per-ticker fetch timeout — single hang blocks entire batch | `inference/daily_predict.py:1700-1800` | Slow inference |
| M1-25 | Backtester | Generic `except Exception` throughout — silent failures | Multiple files | Backtester errors go unnoticed |

### Cross-Module

| # | Issue | Impact |
|---|-------|--------|
| M1-26 | No centralized alerting — each module fails independently with no notification to others | Research fails → Predictor/Executor run on stale data without knowing |
| M1-27 | Inconsistent error handling — no retry pattern standardized across modules | Same transient errors handled differently everywhere |
| M1-28 | No test suites in 4 of 5 modules (only Research has unit tests) | Regressions undetected |

### Recommended Fix Order

| Fix | Effort | Items |
|-----|--------|-------|
| S3 retry/backoff (3 attempts, exponential) across all modules | 0.5 day | M1-1, M1-2 |
| IB Gateway heartbeat + reconnect before each order block | 1 day | M1-3, M1-4 |
| Config validation at Lambda cold-start (check all required env vars) | 0.5 day | M1-7 |
| Predictor soft timeout (flush results at 13 min) + feature count validation | 0.5 day | M1-6, M1-10 |
| Validate current_price is not None before position sizing | 0.5 hr | M1-5 |
| Cross-module health status JSON on S3 | 2 days | M1-26 |
| Pin dependency versions | 0.5 day | M1-19 |

**Total M1 effort: ~6 days**

---

## M2 — Alpha Readiness

These items affect signal quality, position sizing correctness, and risk management — the core alpha generation loop.

### CRITICAL — Trading Logic Correctness

| # | Module | Issue | File | Impact |
|---|--------|-------|------|--------|
| M2-1 | Executor | Graduated drawdown tier matching may be incorrect — loop iterates shallowest-first, last match wins; depends on config sort order | `executor/risk_guard.py:48-65` | Wrong sizing multiplier during moderate drawdowns |
| M2-2 | Executor | Peak NAV initialization masks first-day drawdown — returns current NAV as peak when trades table empty | `executor/ibkr.py:223-234` | Graduated drawdown response disabled on day 1 |
| M2-3 | Predictor | Forward-fill macro features create subtle lookahead bias — VIX/yields filled across holidays | `data/feature_engineer.py:311-394` | IC inflated during backtest, model overconfident |

### HIGH — Signal Quality & Risk Management

| # | Module | Issue | File | Impact |
|---|--------|-------|------|--------|
| M2-4 | Backtester | Forward-fill masks price gaps — 20-day gaps filled with stale prices, compounding in simulation | `loaders/price_loader.py:204-205` | Backtester overstates signal accuracy and Sharpe |
| M2-5 | Executor | S3 signal fallback too permissive — uses up to 5-day-old signals | `executor/signal_reader.py:36-70` | Trading on completely stale market context |
| M2-6 | Executor | No signal staleness discount — 5-day-old signal treated same as today's | README acknowledged | Over-allocating to stale, potentially invalidated signals |
| M2-7 | Executor | No ticker validation — malformed tickers pass through to IB orders | `executor/main.py:314-327` | Failed orders, wasted API calls |
| M2-8 | Predictor | Purge gap logic assumes date-sorted arrays — no validation | `training/train_handler.py:357-622` | Forward-looking bias if data is mis-sorted |
| M2-9 | Backtester | No global FDR correction — 20-30 tests per run, 30-50% false positive rate | Multiple analysis files | Optimizer acts on noise, not signal |
| M2-10 | Backtester | Data staleness not enforced — warning logged but simulation proceeds on stale data | `loaders/price_loader.py:207-217` | Simulation results unreliable |

### MEDIUM — Alpha Optimization Gaps

| # | Module | Issue | File | Impact |
|---|--------|-------|------|--------|
| M2-11 | Executor | No volatility-adjusted sizing — same size in high-vol and low-vol environments | README acknowledged | Over-exposed in volatile markets |
| M2-12 | Executor | No cross-ticker correlation monitoring — hidden concentration risk | README acknowledged | Correlated positions amplify drawdowns |
| M2-13 | Executor | No profit-taking mechanism — winners never trimmed | README acknowledged | Capital locked in mature positions |
| M2-14 | Executor | REDUCE always 50% — no configurable partial reduction | `executor/main.py:565` | Inflexible exit sizing |
| M2-15 | Executor | No sector-relative exits — ATR stop is absolute, not market-relative | README acknowledged | Exits on market-wide dips, not stock-specific weakness |
| M2-16 | Research | Market regime subjective — LLM macro agent uses no quantitative thresholds | README acknowledged | Same data → different regime on different runs |
| M2-17 | Research | Prior report length unbounded — long theses consume agent token budget | `config.py:111` | Agent output quality degrades for tracked tickers |
| M2-18 | Research | No sector concentration limit in scanner — all candidates could be one sector | README acknowledged | Concentrated portfolio risk |
| M2-19 | Research | No volatility screen in scanner — high-vol stocks pass | README acknowledged | Noisy candidates reduce signal quality |
| M2-20 | Research | No debt/balance sheet filter — near-default companies pass | README acknowledged | Credit risk unscreened |
| M2-21 | Research | Wikipedia survivorship bias — delisted stocks vanish from historical universe | `data/fetchers/price_fetcher.py:106-205` | Backtests overstate returns |
| M2-22 | Executor | No minimum position size check — micro-positions possible | README acknowledged | Rounding errors, commission drag |
| M2-23 | Predictor | GBM mode mismatch risk — MSE vs lambdarank not validated at load | `training/train_handler.py:640-750` | Wrong model type used silently |
| M2-24 | Predictor | No hit-rate gate in training promotion — only IC and IC IR checked | `training/train_handler.py:630-750` | Model with poor directional accuracy promoted |
| M2-25 | Backtester | MIN_SAMPLES = 30 — below recommended 50 for statistical conclusions | `analysis/signal_quality.py:23` | Premature statistical conclusions |
| M2-26 | Backtester | No auto-rollback on downstream degradation — bad params persist 1 week | System-wide | Bad optimizer output damages alpha for a full week |
| M2-27 | Backtester | No alerting when params change — silent S3 writes | `optimizer/weight_optimizer.py:439-444` | Param changes invisible to operator |
| M2-28 | Backtester | No slippage simulation — 100% fill at exact price assumed | `vectorbt_bridge.py:66-67` | Simulation overstates returns |

### Recommended Fix Order

| Fix | Effort | Items |
|-----|--------|-------|
| Fix graduated drawdown tier matching — sort tiers or reverse loop | 0.5 hr | M2-1 |
| Initialize peak NAV from starting capital, not current NAV | 0.5 hr | M2-2 |
| Reduce S3 signal fallback to 2 trading days | 0.5 hr | M2-5 |
| Add date-sort assertion in walk-forward training | 0.5 hr | M2-8 |
| Fix macro feature forward-fill — drop NaN rows instead of ffill | 1 day | M2-3 |
| Add global BH FDR correction across backtester modules | 1 day | M2-9 |
| Enforce backtester staleness gate — block sim on stale prices | 0.5 day | M2-4, M2-10 |
| Add ticker validation before IB orders | 0.5 hr | M2-7 |
| Quantitative regime thresholds (VIX + SPY momentum rules) | 1 day | M2-16 |

**Total M2 effort: ~6 days for highest-impact items**

---

## M3 — Maximize Alpha

These are optimization opportunities to pursue once M1 and M2 are solid.

### Model Architecture (Predictor)

| # | Opportunity | Expected Impact | Effort |
|---|------------|----------------|--------|
| M3-1 | 3-model stacking ensemble — LightGBM + XGBoost + CatBoost with linear meta-learner | +10-15% accuracy | 5 days |
| M3-2 | Temporal ensemble — train on 3, 5, 7, 10-day horizons, blend predictions | Multi-horizon alpha | 1 week |
| M3-3 | HMM regime detection — 3-state Gaussian HMM on SPY returns + vol as features | Better regime transitions | 1 week |
| M3-4 | Meta-labeling — secondary model predicts BUY signal profitability → continuous sizing | Replace binary veto | 1 week |

### Feature Engineering (Predictor)

| # | Opportunity | Expected Impact | Effort |
|---|------------|----------------|--------|
| M3-5 | VWAP divergence + buying/selling pressure — volume-weighted price features | Orthogonal to momentum | 2 days |
| M3-6 | Beta vs sector + peer correlation — cross-asset features | Cross-sectional power | 2 days |
| M3-7 | Credit spreads + leading indicators from FRED — HY OAS, ISM PMI, jobless claims | Leads drawdowns 3-6 months | 1 week |
| M3-8 | Yield curve x sector sensitivity interactions — macro-sector feature crosses | Sector-aware regime features | 2 days |

### Signal Quality (Research)

| # | Opportunity | Expected Impact | Effort |
|---|------------|----------------|--------|
| M3-9 | Short interest + borrow rates — crowded trade risk flag | Risk flag for crowded trades | 1 day |
| M3-10 | Equity breadth — advance/decline, % above 50d MA | Confirms/contradicts SPY price | 1 day |
| M3-11 | Sub-sector analysis — distinguish semiconductors from SaaS within Technology | Finer sector allocation | 2 days |

### Execution Strategy (Executor)

| # | Opportunity | Expected Impact | Effort |
|---|------------|----------------|--------|
| M3-12 | Entry momentum confirmation gate — 5d momentum > 0, price > 20d MA | Reduces bad entries 15-25% | 1 day |
| M3-13 | Confidence-weighted sizing — map p_up to continuous multiplier | Better use of predictor signal | 1 day |
| M3-14 | ATR-based position sizing — risk_per_trade / ATR for vol-aware sizing | Prevent blowups in volatile names | 1 day |
| M3-15 | Profit-taking + portfolio heat map exits — trim at +25%, force-exit lowest conviction in drawdown | Capital recycling | 1 week |
| M3-16 | Momentum-based exits — exit when 20d momentum flips negative or RSI < 30 | Faster loss cutting | 1 day |
| M3-17 | Portfolio-level correlation monitoring — alert when pairwise correlation > 0.8 | Detect hidden concentration | 1 week |

### Backtester Statistical Rigor

| # | Opportunity | Expected Impact | Effort |
|---|------------|----------------|--------|
| M3-18 | Slippage simulation — volume-based fill rejection (>5% daily volume) | Realistic simulation | 2 days |
| M3-19 | Recommendation stability tracking — flag if direction reverses week-over-week | Prevent flip-flopping | 1 day |
| M3-20 | Auto-rollback feedback loop — revert params if portfolio alpha turns negative 2 consecutive days | Safety net for auto-optimization | 2 days |
| M3-21 | Purged combinatorial cross-validation (CPCV) — replace single train/test with overlapping paths | Robust IC estimates | 1 week |

---

## Key Metrics to Track

| Metric | Status | Notes |
|--------|--------|-------|
| Total alpha | Tracked | EOD email + public dashboard |
| Sharpe ratio | Tracked | Backtester |
| Daily alpha | Tracked | eod_pnl.csv |
| Signal accuracy (10d/30d) | Tracked | Backtester (needs more data) |
| GBM IC | Tracked | Training + inference metrics |
| Max drawdown | Tracked | EOD + dashboard |
| Pipeline success rate | **NOT TRACKED** | % of trading days all modules complete |
| Signal freshness | **NOT TRACKED** | Age of signals used by executor |
| Prediction coverage | **NOT TRACKED** | % of universe with valid predictions |
| Feature completeness | **NOT TRACKED** | % of tickers with all features computed |

---

## Summary

| Milestone | Open Items | Estimated Effort |
|-----------|-----------|-----------------|
| M1 — Reliability | 28 items (7 critical, 9 high, 9 medium, 3 cross-module) | ~6 days |
| M2 — Alpha Readiness | 28 items (3 critical, 7 high, 18 medium) | ~6 days |
| M3 — Maximize Alpha | 21 opportunities | Ongoing |

**Next action:** Start M1 critical items — S3 retry/backoff, IB Gateway reconnect, config validation, and predictor timeout protection.

---

## References

- Previous audit: `alpha-engine-docs/alpha-engine-audit-260318a.md`
- System architecture: `~/Development/CLAUDE.md`
- Individual READMEs in each repo
