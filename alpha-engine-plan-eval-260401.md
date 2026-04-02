# Alpha Engine: Evaluation Strategy by Module

**Date:** 2026-04-01
**Purpose:** Document how each module's decisions are currently evaluated, identify gaps, and outline the optimal evaluation strategy for a system that learns and improves over time.

---

## 1. Research: Weekly Stock Picks (~25 BUY signals)

### What decisions are we evaluating?
- Which stocks get scored 60+ (BUY threshold)
- The composite score itself (0-100) — does a higher score correlate with higher alpha?
- Sub-score weights (quant vs. qual) — which components are predictive?
- Sector macro multipliers — do they add or subtract value?

### Current evaluation

**Signal accuracy** (`signal_quality.py`):
- Tracks every BUY signal in `score_performance` table with forward prices at 10d and 30d
- Computes `beat_spy_10d` and `beat_spy_30d` (binary: did the pick outperform SPY?)
- Reports accuracy rates with Wilson 95% confidence intervals
- Stratifies accuracy by score bucket (60-70, 70-80, 80-90, 90+) with Benjamini-Hochberg FDR correction
- **Minimum 30 samples** before results are reported

**Attribution** (`attribution.py`):
- Pearson correlation between each sub-score (quant, qual) and beat_spy outcomes
- FDR-corrected p-values across all correlations
- Requires 100+ samples for "reliable" results (roughly week 8+)

**Regime analysis** (`regime_analysis.py`):
- Splits accuracy by market regime (bull/neutral/bear/caution)

**Auto-optimization** (`weight_optimizer.py`):
- Uses quant/qual correlation deltas to adjust scoring weights
- 70/30 train/test split; requires test correlation degradation < 20%
- Guardrails: max 10% weight change per cycle, min 3% meaningful change, blend factor scales with sample size
- Writes to `config/scoring_weights.json` on S3 (Research reads at cold-start)

### Gaps in current evaluation

1. **3-week blind spot on launch.** 30-sample minimum means no signal quality feedback for ~3 weeks. If early signals are bad, we don't know until it's too late.
2. **No win/loss distribution.** We know % beat SPY but not the magnitude distribution — are our winners +2% and losers -10%? Average alpha is tracked but the distribution shape matters.
3. **No per-signal attribution.** We can't answer: "This specific pick scored 82 because of high quant — did the quant component actually drive the outcome?" Only aggregate correlations.
4. **No interaction effects.** Quant and qual are analyzed independently. A stock with high quant + low qual may behave differently than the reverse — we don't capture this.
5. **Macro multiplier not evaluated.** The sector macro shift is applied but never validated — does it improve or hurt accuracy?
6. **Research boost optimization deferred.** Signal boost params (short interest, institutional) frozen for ~6 months (200+ samples). No learning loop on these during the critical early period.
7. **No false negative tracking.** We evaluate stocks we scored BUY. We don't evaluate stocks we scored HOLD/SELL that went on to beat SPY — our misses.

### Optimal evaluation strategy

**Short-term (now, with limited data):**
- **Reduce blind spot:** Track cumulative accuracy from day 1 with a "directional" confidence tier (even with N < 30, show the running tally with a "low confidence" flag rather than hiding it entirely).
- **Track alpha magnitude distribution:** Beyond beat_spy binary, bucket realized alpha into ranges (-5%+, -2-0%, 0-2%, 2-5%, 5%+). This reveals whether we're generating small consistent alpha or volatile guesses.
- **Score calibration curve:** For each score bucket, plot predicted attractiveness vs. realized alpha. A well-calibrated system should show monotonically increasing alpha with score.

**Medium-term (50+ samples):**
- **Macro multiplier A/B evaluation:** Compute accuracy with and without macro shift applied. If accuracy is equal or worse with the shift, disable it.
- **Per-signal post-mortem table:** For every BUY signal, log: score, sub-scores, macro shift, prediction, actual 5d/10d/30d return, SPY return, and whether the stock was ultimately traded. This becomes the master evaluation dataset.
- **Score threshold optimization:** The backtester already does this (`score_analysis.py`) but the results should feed directly into Research's `min_score` parameter via S3 config.
- **False negative sampling:** Each week, randomly sample 10 stocks scored below BUY threshold and track their forward returns. If HOLD/SELL stocks consistently beat SPY, the scoring model has a systematic bias.

**Long-term (200+ samples):**
- **Multivariate attribution:** Replace univariate Pearson correlations with a small regression model (sub-scores + macro + regime as features, beat_spy as target). This captures interaction effects.
- **Decay analysis:** Do signals degrade over time? If week-1 accuracy is 65% but week-4 is 50%, signals have a shelf life and the system should weight recency.
- **Scanner funnel analysis:** Track conversion rates through the 5-stage scanner pipeline. If Stage 3 (Sonnet ranking) is eliminating stocks that would have been winners, the ranking prompt or criteria need adjustment.

---

## 2. Predictor: Daily Veto Decisions

### What decisions are we evaluating?
- Should a BUY signal be vetoed today because the GBM model predicts short-term downside?
- At what confidence threshold should vetoes trigger?
- Is the GBM model's directional prediction accurate?

### Current evaluation

**Veto effectiveness** (`veto_analysis.py`):
- Sweeps confidence thresholds (0.50 to 0.80 in 0.05 steps)
- For each threshold, computes:
  - Precision: % of vetoes where stock actually underperformed
  - Missed alpha: total return foregone from incorrectly vetoing winners
  - Composite score: `precision - 0.30 * missed_alpha` (balancing accuracy vs. cost)
- Cost sensitivity analysis across multiple cost weights (0.15, 0.30, 0.50, 0.70)
- Guardrails: min 10 DOWN predictions, lift >= 5% above base rate, min 0.10 threshold change

**Predictor metrics** (`predictor_backtest.py`):
- `hit_rate_30d_rolling`: % of predictions directionally correct at 5d
- `ic_30d`: Information coefficient (Pearson correlation: net signal vs. actual return)
- `ic_ir_30d`: IC / std(IC) — consistency of predictive power
- Written to `predictor/metrics/latest.json`

**Auto-optimization:**
- Writes best veto threshold to `config/predictor_params.json` on S3
- Predictor Lambda reads at cold-start

### Gaps in current evaluation

1. **Veto evaluated on 10d window, model predicts 5d.** The evaluation horizon doesn't match the prediction horizon. A correct 5d DOWN prediction could look wrong at 10d if the stock recovers.
2. **No UP prediction evaluation.** We only evaluate DOWN predictions (vetoes). UP predictions are never validated — we don't know if the model's bullish signals add value beyond the research score.
3. **No confidence calibration.** If the model says 75% confidence DOWN, is it actually right ~75% of the time? Calibration curves are missing.
4. **No sector/regime breakdown.** Veto quality may vary by sector (works well in tech, poorly in healthcare) or by regime (overly cautious in bull markets). Not tracked.
5. **No realized-trade linkage.** Veto analysis uses theoretical beat_spy outcomes, not actual trade PnL. A veto that would have saved us from a -8% loss is more valuable than one that prevented a -0.5% loss. Magnitude matters.
6. **Cost weight is fixed.** The 0.30 penalty for missed alpha is a hardcoded assumption, not learned from data.

### Optimal evaluation strategy

**Short-term:**
- **Match evaluation to prediction horizon.** Add `beat_spy_5d` to `score_performance` table and evaluate vetoes against 5d outcomes (matching the GBM's actual prediction target).
- **Confidence calibration plot.** For each 10% confidence bucket (50-60%, 60-70%, etc.), compute actual accuracy. Overlay predicted vs. actual on a calibration curve. This immediately reveals if the model is overconfident or underconfident.
- **Veto value in dollars.** For each correct veto, compute the loss avoided (position_size * negative_return). For each incorrect veto, compute the alpha foregone. Net veto value = losses_avoided - alpha_foregone. This is the true ROI of the veto system.

**Medium-term:**
- **UP prediction evaluation.** Track: when model predicts UP with high confidence, do those stocks outperform the average BUY signal? If so, UP predictions could be used for position sizing (bigger positions on high-confidence UP).
- **Sector-specific thresholds.** If veto precision varies by sector, allow per-sector confidence thresholds. The optimizer already sweeps thresholds — extend to per-sector sweeps.
- **Regime-aware veto gating.** In strong bull regimes, vetoes may cost more alpha than they save. Track veto value by regime and consider relaxing thresholds in bull markets.

**Long-term:**
- **Learn the cost weight.** Replace the fixed 0.30 cost penalty with a learned parameter. Use historical data: what cost weight would have maximized realized portfolio alpha? This closes the loop between veto decisions and portfolio outcomes.
- **Veto → trade feedback loop.** When a veto fires, log it as a "shadow trade" — track what would have happened if we'd entered. Compare vetoed outcomes vs. traded outcomes over time. This is the gold-standard evaluation: did vetoing actually improve realized alpha?
- **Multi-model veto ensemble.** If a single GBM is noisy, require 2-of-3 models to agree on DOWN before vetoing. Track ensemble vs. single-model precision.

---

## 3. Executor: Order Book Build + Daemon Trading

### What decisions are we evaluating?
- **Position sizing:** Did equal-weight + adjustments produce better risk-adjusted returns than alternatives?
- **Risk guard decisions:** Were blocked entries actually bad? Were allowed entries actually good?
- **Entry trigger timing:** Did pullback/VWAP/support triggers get better fills than market-open?
- **Exit rules:** Did ATR trailing stops, time decay, and profit-takes exit at good times?
- **Overall portfolio construction:** Did the combined system produce alpha?

### Current evaluation

**Portfolio simulation** (`vectorbt_bridge.py`):
- VectorBT portfolio replay on historical orders
- Metrics: total_return, sharpe_ratio, max_drawdown, calmar_ratio, win_rate, total_alpha

**Parameter optimization** (`param_sweep.py` + `executor_optimizer.py`):
- 60-trial random search over 6 parameters (min_score, max_position_pct, atr_multiplier, time_decay_reduce_days, time_decay_exit_days, profit_take_pct)
- Ranked by Sharpe ratio
- 70/30 holdout validation (holdout Sharpe must be >= 50% of train Sharpe and > 0)
- Guardrails: min 5 valid combos, min 50 trades, min 10% Sharpe improvement
- Writes to `config/executor_params.json`

**Live trade tracking** (`trade_logger.py` + `eod_reconcile.py`):
- Per-trade: fill price, slippage vs. signal price, trigger type, execution latency, realized PnL
- Daily: NAV, daily return, SPY return, daily alpha, positions snapshot
- Roundtrip stats: avg return, avg alpha, avg hold days, win rate vs. SPY
- Sector attribution: position weight and contribution by sector

### Gaps in current evaluation

1. **No entry trigger comparison.** The daemon uses 4 trigger types (pullback, VWAP, support, time expiry). We log which trigger fired but never analyze: "Did pullback entries outperform time-expiry entries?" This is critical — if one trigger consistently gets better fills, we should weight it more.
2. **No risk guard post-mortem.** When the risk guard blocks an entry, we don't track what would have happened. Were blocked entries actually bad? If the risk guard blocks 30% of entries and those would have been profitable, the guard is too conservative.
3. **No exit timing evaluation.** We know realized PnL per trade but don't evaluate: "If we'd held 2 more days, would the outcome have been better?" No comparison of actual exit vs. optimal exit.
4. **Backtester doesn't model execution realism.** Assumes fills at signal price with optional fixed slippage. No market impact, partial fills, or IB latency modeling. Backtested Sharpe of 1.5 might be 0.8 in reality.
5. **Parameter sweep excludes critical params.** Drawdown circuit breaker, sector limits, and equity limits are excluded as "too dangerous to auto-tune." But these are some of the most impactful parameters.
6. **No position sizing attribution.** We can't answer: "How much alpha came from sizing adjustments (conviction, upside, sector) vs. equal-weight baseline?" If adjustments don't help, simplify.
7. **No A/B or canary deployment.** New params are applied immediately. No way to validate that optimized params actually outperform current params in live trading.

### Optimal evaluation strategy

**Short-term:**
- **Entry trigger scorecard.** For each trigger type, compute: avg slippage vs. signal price, avg slippage vs. market-open price, and avg realized alpha of trades entered via that trigger. Weekly report. This immediately shows which triggers earn their complexity.
- **Risk guard shadow book.** When the risk guard blocks an entry, log it as a "blocked trade" with the same forward-price tracking as score_performance. Weekly report: "Of N blocked entries, X% would have been profitable." If blocked entries win more than traded entries, the guard needs loosening.
- **Exit timing analysis.** For each completed trade, compute: max favorable excursion (MFE) and max adverse excursion (MAE) during the hold period. If MFE >> realized return consistently, exits are too early. If MAE is close to stop level, stops are appropriately placed.

**Medium-term:**
- **Position sizing A/B.** Run backtester with two configs: (a) current sizing (equal-weight + adjustments) and (b) pure equal-weight. If equal-weight Sharpe is comparable, remove sizing complexity. If adjustments add Sharpe, quantify the contribution.
- **Realistic slippage model.** Replace fixed slippage_bps with a model trained on live trade data: `actual_slippage = f(market_cap, volume, order_size, volatility, trigger_type)`. Feed this back into the backtester for more accurate simulation.
- **Expand parameter sweep carefully.** Add drawdown_circuit_breaker to the sweep grid, but with tight bounds (only 3-4 values near the current setting). This captures its interaction with other params without allowing dangerous extremes.

**Long-term:**
- **Alpha decomposition.** For each trade, decompose realized alpha into: (a) signal alpha (would we have made money at signal price?), (b) entry timing alpha (did the trigger improve on signal price?), (c) exit timing alpha (did the exit rule capture more than buy-and-hold?), (d) sizing alpha (did the size adjustment help?). This tells us exactly where alpha comes from and where it leaks.
- **Canary deployment.** Run optimized params on a subset of positions (e.g., 2 of 10 entries) while keeping current params on the rest. Compare realized alpha after 4 weeks. Only promote new params if canary outperforms.
- **Execution quality monitor.** Track slippage trend over time. If slippage is increasing (our orders are getting front-run, or we're trading less liquid names), alert before it erodes alpha.

---

## 4. Cross-Module Evaluation — Full-Universe, Decision-Boundary Framework

### Core principle

Every decision in the pipeline narrows a population. Each decision-maker is evaluated against the population it received — not the final output. This isolates where value is created or destroyed.

```
S&P 900 universe
  ↓ Scanner filter
~50-70 quant candidates
  ↓ Sector teams (×6, parallel)
~12-18 sector recommendations (2-3 per team)
  ↓ CIO promotion
~5-8 BUY signals (ENTER for open slots)
  + ~17 existing HOLD positions = ~25 population
  ↓ Predictor veto gate
~20 approved for entry
  ↓ Executor risk guard + sizing + triggers
~15 traded positions
  ↓ Exit rules
Realized PnL
```

Six decision boundaries. Six evaluations. Each one answers: **"Did this step improve on what it was given?"**

---

### 4.1 Scanner Filter: 900 → 50-70

**Decision:** Which stocks pass the quant filter (tech_score >= 60, liquidity, volatility gates)?

**Evaluation:** Do filter-passing stocks outperform filter-failing stocks?

| Metric | Numerator | Denominator |
|--------|-----------|-------------|
| Filter lift | avg 5d return of 50-70 passing stocks | avg 5d return of full 900 |
| Filter leakage | count of filter-rejected stocks that beat SPY by >5% | total filter-rejected |
| Filter precision | count of filter-passing stocks that beat SPY | total filter-passing |

**Data required:**
- Forward returns (5d, 10d) for all 900 stocks — **new `universe_returns` table**
- Scanner pass/fail flag for all 900 — **expand `scanner_appearances` to log all 900** (currently only logs ~60 that pass)
- Add columns: `liquidity_pass`, `volatility_gate_pass`, `quant_filter_pass`

**Data already available:**
- Price cache: 922 parquets in predictor (full S&P 500 + 400 OHLCV)
- Tech scores computed in scanner for all candidates before filtering

**Cost to add:** 1 polygon.io grouped-daily API call per evaluation date (returns all tickers in one response). ~47K DB rows/year (~20-30MB). Negligible.

**What we learn:** If filter leakage is high (many good stocks rejected), the quant filter is too restrictive. If filter lift is near zero, the filter isn't adding value and we're just shrinking the universe for computational convenience.

**Self-adjustment (longer-term):** If specific filter gates (e.g., ATR% <= 8%) consistently reject winners, auto-relax the threshold. Log filter gate pass/fail per stock so we can attribute rejections to specific gates.

---

### 4.2 Sector Teams: 50-70 → 12-18

**Decision:** Each sector team screens its sector's candidates (quant top 10 → qual top 5 → peer review → 2-3 picks). Six teams run in parallel.

**Evaluation:** Each team is measured against its own sector population.

| Metric | What it measures |
|--------|-----------------|
| **Team selection lift** | avg return of team's 2-3 picks vs. avg return of all stocks in that sector from the 900 |
| **Team precision** | % of team picks that beat their sector ETF (not SPY — sector-relative) |
| **Team hit rate vs. quant candidates** | avg return of team picks vs. avg return of team's 10 quant candidates (did qual/peer review add value over quant alone?) |
| **Team consistency** | rolling 8-week selection lift — is the team reliably picking winners or getting lucky? |

**Per-team scorecard example:**

```
Technology Team — Week of 2026-03-29
  Sector universe: 142 stocks    Avg 5d return: +1.2%
  Quant top 10:                  Avg 5d return: +2.1%    Quant filter lift: +0.9%
  Team picks (3): NVDA, CRM, NOW Avg 5d return: +3.8%    Team selection lift: +2.6%
  Picks that beat XLK: 2/3 (67%)
  
Consumer Team — Week of 2026-03-29
  Sector universe: 168 stocks    Avg 5d return: +0.5%
  Quant top 10:                  Avg 5d return: +0.8%    Quant filter lift: +0.3%
  Team picks (2): COST, ABNB     Avg 5d return: -0.2%    Team selection lift: -0.7%
  Picks that beat XLY: 0/2 (0%)
```

**Data required:**
- Sector classification for all 900 stocks (already in scanner data)
- Sector ETF returns (XLK, XLV, XLF, XLI, XLY, XLU — 6 price lookups)
- Team recommendation records — **already logged in `thesis_history` table** (author="sector_team", includes ticker, score, conviction)
- Quant top-10 per team — need to persist this intermediate output (currently in-memory only)

**Data pipeline change:**
1. Log quant analyst's top-10 list per team per run in `scanner_appearances` or a new `team_quant_candidates` table. This is the key missing link — without it we can't evaluate whether qual/peer review adds value over quant screening alone.
2. Weekly batch: for each team, compute avg return of team picks vs. avg return of all same-sector stocks from the 900.

**What we learn:**
- Which teams consistently pick winners within their sector (keep investing in their prompts/tools)
- Which teams underperform their sector's random baseline (their analysis is noise or anti-predictive)
- Whether qual + peer review adds value over quant screening alone (if quant top-10 performs as well as the final 2-3, the LLM layers are expensive noise)

**Self-adjustment (longer-term):** If a team consistently underperforms its sector, reduce its slot allocation (fewer picks). If qual/peer review doesn't add lift over quant alone, consider simplifying the team pipeline to quant-only with CIO review.

---

### 4.3 CIO Promotion: 12-18 → ~5-8 ENTER signals

**Decision:** CIO sees all sector-recommended candidates + macro context + current population + open slots. Decides which to ADVANCE (promote to BUY/ENTER) and which to REJECT.

**Evaluation:** Did the CIO select the best stocks from what the sector teams recommended?

| Metric | What it measures |
|--------|-----------------|
| **CIO selection lift** | avg return of ADVANCE stocks vs. avg return of all 12-18 sector recommendations |
| **CIO rejection accuracy** | avg return of REJECT stocks — should be lower than ADVANCE stocks |
| **CIO vs. score-ranking baseline** | if CIO had just taken the top N by combined quant+qual score (no LLM judgment), would that have done better? |
| **Portfolio fit value** | did CIO's diversification/macro considerations improve risk-adjusted returns vs. pure score ranking? |

**Data required:**
- CIO decisions per candidate — **already logged in `thesis_history`** (author="cio", decision="ADVANCE" or "REJECT")
- Forward returns for all 12-18 sector recommendations (subset of score_performance, already tracked if they're scored)
- The counterfactual: what would the top N by score have been? Compute from the same thesis_history records

**What's missing:**
- REJECT candidates don't get tracked in `score_performance` today — only ADVANCE/BUY stocks do. Need to expand to track returns for all 12-18 recommendations, not just promoted ones.

**Data pipeline change:**
1. Expand `score_performance` tracking to include all CIO-evaluated candidates (ADVANCE + REJECT), with a new column `cio_decision` (ADVANCE/REJECT/DEADLOCK). This is the critical change — without it, we can't evaluate whether rejections were correct.

**What we learn:**
- Whether the CIO's LLM judgment adds value beyond mechanical score ranking
- Whether the CIO is too conservative (rejecting stocks that outperform) or too aggressive (advancing stocks that underperform)
- Whether portfolio fit / macro considerations help risk-adjusted returns

**Self-adjustment (longer-term):** If CIO consistently underperforms the score-ranking baseline, consider replacing the LLM CIO with a deterministic promotion rule (top N by score + sector diversification constraint). Cheaper and more predictable.

---

### 4.4 Predictor: full active portfolio (~25 stocks) → veto/approve

**Decision:** Daily GBM inference classifies each stock in the active portfolio as UP/DOWN with confidence. DOWN + high confidence → veto (HOLD override on BUY signal).

**Population:** The full active portfolio — both new ENTER picks and continuing HOLD positions (~17-20 stocks carried from prior weeks). The predictor runs inference on all of them daily via `population/latest.json`.

**Evaluation:** Weight the actual returns of all portfolio stocks against the predictor's classifications. The predictor adds value if its UP/DOWN separation correlates with actual returns *within the active portfolio*.

| Metric | What it measures |
|--------|-----------------|
| **Predictor lift** | avg return of UP-predicted stocks vs. avg return of all ~25 portfolio stocks |
| **Veto accuracy** | avg return of vetoed stocks — should be negative/low |
| **Rank IC** | rank correlation between prediction_confidence and realized_5d_return across all portfolio stocks |
| **Net veto value ($)** | losses avoided by correct vetoes minus alpha foregone by incorrect vetoes |
| **Confidence calibration** | at each confidence level (50-60%, 60-70%, etc.), does actual accuracy match? |
| **HOLD stock prediction quality** | does the model separate winners/losers within continuing positions, or only within new entries? |

**Evaluation framework — returns weighted against predictions:**

For each daily prediction set, compute across the full active portfolio:
```
All ~25 portfolio stocks:  avg 5d return = baseline
  New entries (ENTER):     avg 5d return = ?     (subset: fresh picks)
  Continuing (HOLD):       avg 5d return = ?     (subset: carried positions)
UP predicted (high):       avg 5d return = ?     (should be > baseline)
UP predicted (low):        avg 5d return = ?     (should be ≈ baseline)
DOWN predicted (vetoed):   avg 5d return = ?     (should be < baseline)
```

If the ordering isn't `UP_high > UP_low > DOWN`, the model doesn't separate within this population and is adding noise. Breaking this out by ENTER vs. HOLD reveals whether the predictor works better on fresh picks (where momentum signals are strong) vs. continuing positions (where signals may have decayed).

**Continuous signal evaluation:** Beyond binary UP/DOWN, use `p_up` as a continuous signal. Compute weighted portfolio return where position size ∝ p_up. Compare to equal-weight. If the continuous signal outperforms, it can inform position sizing (not just veto gating).

**Data required:**
- `predictor_outcomes` (existing) — covers all population stocks, has predictions + backfilled actual 5d returns
- `universe_returns` (new) — forward returns for all 900 stocks, joined by (ticker, date) to get returns for the ~25 portfolio stocks regardless of rating
- `population_history` (existing) — identifies which stocks were in the active portfolio each week (ENTER + HOLD)
- No dependency on `score_performance` (which misses HOLD-rated stocks)

**What we learn:**
- Whether the predictor separates winners from losers *within the already-filtered research picks* (harder than separating across random stocks)
- Whether confidence levels are well-calibrated
- The dollar value of the veto system
- Whether UP predictions are useful for sizing (not just DOWN for vetoing)

**Self-adjustment (longer-term):**
- Auto-tune veto threshold (already implemented via `veto_analysis.py`)
- If rank IC is consistently positive, feed `p_up` into position sizing (predictor-informed sizing)
- If rank IC is zero or negative, disable the predictor entirely — it's adding cost and latency with no signal

---

### 4.5 Executor: full active portfolio (~25 stocks) → traded positions

**Decision:** Risk guard filters, position sizer allocates, entry triggers time entries, exit rules close positions.

**Population:** The full active portfolio — same set as the predictor. The executor manages both new entries (from ENTER signals) and continuing positions (HOLD stocks with active stop-losses, time decay, etc.). Both must be evaluated.

**Evaluation:** Weight executor actions against the raw performance of all portfolio stocks. The executor adds value if its timing, sizing, and exits beat a naive "buy all at signal price, hold to period end" baseline.

| Metric | What it measures |
|--------|-----------------|
| **Execution lift** | actual portfolio return vs. naive equal-weight buy-and-hold of all portfolio stocks |
| **Entry timing alpha** | avg (signal_price - fill_price) / signal_price across new entries |
| **Exit timing alpha** | avg (exit_price - hold-to-period-end price) across all exits (including HOLD stock exits) |
| **Sizing alpha** | portfolio-weighted return vs. equal-weight return |
| **Risk guard accuracy** | return of blocked entries vs. return of allowed entries |
| **HOLD management quality** | for continuing positions: did stop-losses and exits fire at the right times? Compare executor-managed HOLD returns to raw buy-and-hold returns |

**Baseline construction:**

For each week, construct the "no-executor" portfolio:
- Take all ~25 active portfolio stocks (ENTER + HOLD)
- Equal-weight at Monday's close price
- Hold for the target period (or use the same hold duration as actual trades)
- Compute return from `universe_returns`

Compare to actual portfolio return. The difference is the executor's total value-add. This captures both entry decisions (new buys) AND position management decisions (stop-losses, exits on HOLD stocks).

**Decomposition:**
```
Signal return:       buy at signal price, hold N days         (research + predictor value)
+ Entry timing:      actual fill vs. signal price             (trigger value)
+ Exit timing:       actual exit vs. hold-to-end              (exit rule value)
+ Sizing effect:     weighted return vs. equal-weight          (sizer value)
+ Risk guard effect: excluded stocks' return                   (guard value)
= Realized return                                             (total system value)
```

**Per-component scorecards:**

**Entry triggers:**
| Trigger | Avg fill improvement vs. open | # fires | Avg realized alpha |
|---------|-------------------------------|---------|-------------------|
| Pullback | -0.8% | 45 | +2.1% |
| VWAP discount | -0.5% | 32 | +1.8% |
| Support bounce | -1.2% | 12 | +3.4% |
| Time expiry (3:30) | +0.1% | 28 | +0.9% |

If time expiry consistently produces worse fills and lower alpha, consider tightening the expiry or dropping it.

**Exit rules:**
| Exit type | Avg return at exit | Avg return if held to period end | Exit lift |
|-----------|-------------------|--------------------------------|-----------|
| ATR trail | +4.2% | +5.1% | -0.9% |
| Profit take | +12.8% | +9.3% | +3.5% |
| Time decay | +1.1% | +0.8% | +0.3% |
| Collapse | -3.2% | -6.1% | +2.9% |

**Risk guard shadow book:**
Track every blocked entry as a "shadow position." After the hold period, compute what would have happened. If blocked entries outperform traded entries, the guard is too tight.

**What we learn:**
- Whether the executor as a whole adds or subtracts alpha vs. naive execution
- Which specific components (triggers, exits, sizing, guard) contribute positively
- Which components should be simplified or removed

**Self-adjustment (longer-term):**
- Disable triggers with consistently negative entry timing alpha
- Adjust exit thresholds based on MFE/MAE analysis (are we exiting too early or too late?)
- If sizing alpha is near zero, simplify to equal-weight
- If risk guard shadow book shows blocked entries outperforming, auto-relax constraints

---

### 4.6 Full-Pipeline Attribution Table

All six decision boundaries in a single weekly output. Every stock in the universe gets a row; columns are progressively populated as the stock advances through the pipeline.

| Field | Source | Population |
|-------|--------|------------|
| ticker, date, sector | Scanner | All 900 |
| tech_score, scan_path, quant_filter_pass | Scanner | All 900 |
| liquidity_pass, volatility_gate_pass | Scanner | All 900 |
| return_5d, return_10d, beat_spy_5d, beat_spy_10d | Price data | All 900 |
| sector_etf_return_5d, beat_sector_5d | Price data | All 900 |
| team_quant_rank (within sector) | Sector team | ~60 quant candidates |
| team_recommended | Sector team | ~12-18 picks |
| quant_score, qual_score, team_conviction | Sector team | ~12-18 picks |
| cio_decision (ADVANCE/REJECT/DEADLOCK) | CIO | ~12-18 picks |
| research_score, macro_shift, rating | Research | ~25 active portfolio |
| portfolio_status (ENTER/HOLD) | Population | ~25 active portfolio (new entries + continuing positions) |
| predicted_direction, confidence, p_up, p_down | Predictor | ~25 active portfolio (ENTER + HOLD) |
| veto_applied | Predictor | ~25 active portfolio |
| risk_guard_blocked, block_reason | Executor | ~20 approved |
| position_size, trigger_type, fill_price, slippage | Executor | ~15 traded |
| realized_return, realized_alpha, hold_days, exit_type | Executor | ~15 traded |

**Implementation:** `analysis/end_to_end.py` in the backtester, run weekly. Joins:
- `universe_returns` table (900 stocks — new, provides forward returns for ALL stocks)
- `scanner_evaluations` table (900 stocks — new, scanner pass/fail)
- `team_candidates` table (60 stocks — new, quant top-10 per team)
- `cio_evaluations` table (12-18 stocks — new, CIO decisions)
- `population_history` table (~25 stocks — existing, identifies active portfolio ENTER + HOLD)
- `predictor_outcomes` table (~25 stocks — existing, predictions + actual 5d returns)
- `trades` table (~15 stocks — existing, execution data)
- `executor_shadow_book` table (~5-10 stocks — new, blocked entries)

Output: `backtest/{date}/e2e_attribution.csv` on S3 + lift summary in weekly email.

---

### 4.7 Pipeline Value Chain Summary

```
Decision             Population     Baseline comparison                    Key metric
──────────────────── ────────────── ────────────────────────────────────── ───────────────────
Scanner filter       900 → 50-70   Passing vs. full 900 avg return        Filter lift
Sector teams (×6)    50-70 → 12-18 Team picks vs. own sector avg          Team selection lift
CIO promotion        12-18 → ~5-8  ADVANCE vs. all 12-18 recs            CIO lift
Predictor veto       ~25 → ~20     UP-predicted vs. all picks return      Predictor lift
Executor trading     ~20 → ~15     Traded return vs. naive buy-and-hold   Execution lift
──────────────────── ────────────── ────────────────────────────────────── ───────────────────
Full pipeline        900 → ~15     Traded return vs. equal-weight 900     Total system alpha
```

Each row is independently measurable. If any step shows zero or negative lift over 8+ weeks, it is a candidate for simplification. The system learns by:

1. **Tracking lift per decision boundary** — weekly, automated
2. **Flagging underperformance** — if any component's 8-week rolling lift is negative, alert in the weekly email
3. **Auto-adjustment (longer-term)** — components that consistently underperform get simplified:
   - Scanner filter too tight → relax thresholds
   - Sector team underperforms → reduce slot allocation or simplify to quant-only
   - CIO underperforms score ranking → replace with deterministic rule
   - Predictor doesn't separate → disable veto gate
   - Executor timing subtracts value → simplify to market-open fills
4. **Promotion of what works** — components that consistently outperform get more influence:
   - Strong sector team → more slots
   - Predictor IC is positive → use p_up for sizing, not just veto
   - Specific trigger outperforms → weight it more in entry logic

---

## 5. Priority Roadmap

See Phase 1–5 tables in Section 7 below.

---

## 6. Data Model

### Design principles

1. **Module-segmented tables** — each module owns its evaluation data. Research stores the broadest population (900). Predictor and executor only store research-picked stocks, since their decisions only apply within that set.
2. **Join on `(ticker, eval_date)`** — all tables use this composite key so you can join any downstream table to any upstream table. `eval_date` is the signal/prediction date (Monday), not the forward-return observation date.
3. **Don't duplicate existing tables** — `predictor_outcomes`, `trades`, `eod_pnl`, `score_performance` already exist with rich schemas. New tables fill gaps, not replace what's there.
4. **Backtester is the sole writer** — evaluation tables are populated weekly by the backtester, which reads production data from S3 and fills in forward returns. Production modules don't write evaluation data.

### What already exists (no changes needed)

**Critical coverage question:** Do existing tables track the full active portfolio — both new ENTER picks and continuing HOLD positions — or only a subset? This matters because predictor and executor evaluation must cover all stocks the system is actively managing, not just fresh entries.

#### Coverage gap: `score_performance` misses HOLD stocks

`score_performance` seeds only `rating == "BUY"` stocks from `signals.json`. But `score_to_rating()` maps scores as: >= 70 → BUY, 40-70 → HOLD, < 40 → SELL. A stock enters the population as BUY (score 75), gets a `score_performance` row that week. Next week its score drifts to 65 → `rating = "HOLD"` → **no new row**, even though the predictor still scores it daily and the executor still holds the position.

This means `score_performance` is unreliable as the baseline for predictor/executor evaluation. It captures new entries well but loses continuing positions.

#### What each table actually covers

| Table | DB | Rows/week | Population coverage | Gap |
|-------|-----|-----------|--------------------|----|
| `score_performance` | research.db | ~5-8 new | **Only BUY-rated stocks** each week. Misses HOLD positions (score 40-70) that are still in the active portfolio. | Does not cover full portfolio. |
| `predictor_outcomes` | research.db | ~25 | **All stocks the predictor scored** — seeded from `predictions/{date}.json`. In watchlist mode this is the full population (ENTER + HOLD). Actual 5d returns backfilled via yfinance. | **Covers full portfolio.** Best existing source for forward returns independent of executor actions. |
| `trades` | trades.db | ~15-30 | **Only stocks with actual orders placed** — entries, exits, reduces. Blocked/untriggered stocks have no rows. | Only covers traded subset. |
| `eod_pnl` | trades.db | 5 | Portfolio-level daily. Not per-stock. | No per-stock granularity. |
| `scanner_appearances` | research.db | ~60 | Scanner candidates that passed the quant filter. | Needs expansion to all 900. |
| `thesis_history` | research.db | ~30 | CIO decisions with author, conviction, score. | Adequate for CIO eval. |
| `population` / `population_history` | research.db | ~25 / varies | Current portfolio membership and entry/exit events. Rewritten each run. | Membership is tracked, but no forward returns. |

#### How this shapes the evaluation data model

The predictor and executor evaluation population is the **full active portfolio** — the ~25 stocks in the `population` table on any given week, regardless of their current rating. This includes:
- ~5-8 new ENTER stocks (just promoted by CIO, rating = BUY)
- ~17-20 continuing HOLD positions (may have drifted below BUY threshold)

**`predictor_outcomes`** already covers this full set because the predictor runs inference on all population stocks and the backtester seeds from the prediction JSONs. Forward 5d returns are backfilled independently of trading.

**`score_performance`** does NOT reliably cover this set. Two options to fix:
1. **Expand seeding** — change `_seed_score_performance()` to include all population stocks (not just `rating == "BUY"`). Risk: changes semantics of an existing table used by signal quality analysis.
2. **Use `universe_returns` instead** — the new table (Section 6) tracks forward returns for all 900 stocks. The ~25 portfolio stocks are a subset. Just join `population_history` to `universe_returns` on (ticker, date). **This is the cleaner approach** — no need to change existing table semantics.

#### Recommended evaluation joins

- **Predictor evaluation:** `predictor_outcomes` JOIN `universe_returns` ON (ticker, date). Both cover the full portfolio. Gives us predictions + actual returns for all ~25 active positions regardless of rating or trading status.
- **Executor evaluation:** `trades` JOIN `universe_returns` ON (ticker, date). Compare realized PnL to raw forward returns. For stocks in the portfolio but NOT in `trades` (blocked or untriggered), `universe_returns` still has their actual performance — this is the shadow book baseline even before building the explicit `executor_shadow_book` table.
- **Risk guard evaluation:** Stocks in `population_history` (portfolio membership) but NOT in `trades` (no order placed) → join to `universe_returns` for their actual performance. If these "untreated" stocks outperform traded stocks, the executor is being too selective.

### New tables needed

#### `universe_returns` — Research module, full population (research.db)

The population baseline. Every stock in the S&P 900 universe, every evaluation week, with forward returns and sector classification. This is the table that makes everything else meaningful — without it, we can't measure selection lift.

```sql
CREATE TABLE universe_returns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    eval_date TEXT NOT NULL,           -- signal week (Monday)
    sector TEXT,                        -- GICS sector
    close_price REAL,                   -- price on eval_date
    return_5d REAL,                     -- 5-trading-day forward return (%)
    return_10d REAL,                    -- 10-trading-day forward return (%)
    spy_return_5d REAL,                 -- SPY return over same 5d window
    spy_return_10d REAL,                -- SPY return over same 10d window
    beat_spy_5d INTEGER,                -- 1 if return_5d > spy_return_5d
    beat_spy_10d INTEGER,               -- 1 if return_10d > spy_return_10d
    sector_etf_return_5d REAL,          -- sector ETF return over 5d (XLK, XLV, etc.)
    beat_sector_5d INTEGER,             -- 1 if return_5d > sector_etf_return_5d
    UNIQUE(ticker, eval_date)
);
```

**Writer:** Backtester (weekly, batch polygon.io call for all 900 tickers).
**Rows/week:** ~900. **Rows/year:** ~47K. **Size:** ~20-30MB/year.

**Joins to:** everything. This is the denominator for all lift calculations.

#### `scanner_evaluations` — Research module, scanner decision boundary (research.db)

Expands on `scanner_appearances` to track all 900 stocks through the quant filter, not just the ~60 that pass. Records *why* each stock passed or failed.

```sql
CREATE TABLE scanner_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    eval_date TEXT NOT NULL,
    sector TEXT,
    tech_score REAL,                    -- technical score (0-100)
    scan_path TEXT,                      -- momentum | deep_value | failed
    quant_filter_pass INTEGER,           -- 1 if passed quant filter
    liquidity_pass INTEGER,              -- 1 if passed liquidity gate
    volatility_pass INTEGER,             -- 1 if passed volatility gate
    balance_sheet_pass INTEGER,          -- 1 if passed balance sheet gate
    filter_fail_reason TEXT,             -- which gate failed (NULL if passed)
    UNIQUE(ticker, eval_date)
);
```

**Writer:** Research module (in `scanner.py`, log all 900 before filtering).
**Rows/week:** ~900. **Joins to:** `universe_returns` on `(ticker, eval_date)`.

**Note:** This could also be an expansion of the existing `scanner_appearances` table (add the pass/fail columns and log all 900 instead of ~60). Either approach works — new table is cleaner, expanding existing is less migration work.

#### `team_candidates` — Research module, sector team decision boundary (research.db)

Logs the quant analyst's top-10 per team — the intermediate step between scanner output and team recommendations. Currently in-memory only.

```sql
CREATE TABLE team_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    eval_date TEXT NOT NULL,
    team_id TEXT NOT NULL,               -- technology, healthcare, etc.
    quant_rank INTEGER,                  -- rank within team's quant top-10
    quant_score REAL,                    -- quant analyst's score
    qual_score REAL,                     -- qual analyst's score (NULL if not reviewed)
    team_recommended INTEGER DEFAULT 0,  -- 1 if made final team picks (2-3 per team)
    UNIQUE(ticker, eval_date, team_id)
);
```

**Writer:** Research module (in sector team node, after quant screening).
**Rows/week:** ~60 (10 per team × 6 teams). **Joins to:** `universe_returns`, `scanner_evaluations`.

#### `cio_evaluations` — Research module, CIO decision boundary (research.db)

Tracks every CIO decision — ADVANCE, REJECT, and DEADLOCK — so we can compare promoted vs. rejected candidates. `thesis_history` already has some of this but mixes CIO decisions with other author types and doesn't cleanly separate the evaluation signal.

```sql
CREATE TABLE cio_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    eval_date TEXT NOT NULL,
    team_id TEXT,                         -- which team recommended
    combined_score REAL,                  -- quant + qual composite
    macro_shift REAL,                     -- macro modifier applied
    final_score REAL,                     -- score after macro
    cio_decision TEXT NOT NULL,           -- ADVANCE | REJECT | DEADLOCK
    cio_conviction INTEGER,              -- CIO's conviction (0-100)
    cio_rank INTEGER,                    -- CIO's ranking among candidates
    UNIQUE(ticker, eval_date)
);
```

**Writer:** Research module (in CIO node, log all candidates evaluated).
**Rows/week:** ~12-18. **Joins to:** `universe_returns`, `team_candidates`, `score_performance`.

**Note:** Expanding `score_performance` to include CIO REJECT candidates (adding a `cio_decision` column) is an alternative. But `score_performance` is tightly coupled to the backtester's accuracy analysis — adding non-BUY stocks there could break existing queries. A separate table is safer.

#### `executor_shadow_book` — Executor module, risk guard decision boundary (trades.db)

Tracks entries blocked by the risk guard, with the same forward-return tracking as traded positions. This is the "what would have happened" table.

```sql
CREATE TABLE executor_shadow_book (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    eval_date TEXT NOT NULL,
    block_reason TEXT NOT NULL,           -- max_position | max_sector | drawdown_halt | min_score | etc.
    intended_position_pct REAL,          -- what position size would have been
    research_score REAL,
    predicted_direction TEXT,
    prediction_confidence REAL,
    price_at_block REAL,                 -- price when blocked
    return_5d REAL,                      -- forward return (filled by backtester)
    return_10d REAL,
    beat_spy_5d INTEGER,
    UNIQUE(ticker, eval_date)
);
```

**Writer:** Executor module (in `risk_guard.py`, log every block). Backtester backfills forward returns.
**Rows/week:** ~5-10. **Joins to:** `universe_returns`, `predictor_outcomes`, `trades`.

### Join map

```
universe_returns (900/week)          ← population baseline for everything
  │
  ├── scanner_evaluations (900/week) ← filter pass/fail per stock
  │     │
  │     └── team_candidates (60/week) ← quant top-10 per team
  │           │
  │           └── cio_evaluations (12-18/week) ← CIO advance/reject
  │                 │
  │                 └── score_performance (25/week, existing) ← BUY pick returns
  │                       │
  │                       ├── predictor_outcomes (25/week, existing) ← prediction vs. actual
  │                       │
  │                       ├── executor_shadow_book (5-10/week, new) ← blocked entries
  │                       │
  │                       └── trades (15-30/week, existing) ← executed trades
  │
  ALL JOIN ON (ticker, eval_date)
```

Every downstream table is a strict subset of the one above it. You can always join down to up to compare "what happened to stocks at this stage vs. stocks that didn't make it this far."

### Example evaluation queries

**Research selection lift (picks vs. population):**
```sql
SELECT
    'population' AS cohort, AVG(u.return_5d) AS avg_return, COUNT(*) AS n
FROM universe_returns u WHERE u.eval_date = '2026-03-31'
UNION ALL
SELECT
    'picks', AVG(u.return_5d), COUNT(*)
FROM universe_returns u
JOIN score_performance sp ON u.ticker = sp.symbol AND u.eval_date = sp.score_date
WHERE u.eval_date = '2026-03-31';
```

**Sector team lift (team picks vs. sector avg):**
```sql
SELECT
    tc.team_id,
    AVG(CASE WHEN tc.team_recommended = 1 THEN u.return_5d END) AS pick_avg,
    AVG(u.return_5d) AS sector_avg,
    AVG(CASE WHEN tc.team_recommended = 1 THEN u.return_5d END) - AVG(u.return_5d) AS team_lift
FROM team_candidates tc
JOIN universe_returns u ON tc.ticker = u.ticker AND tc.eval_date = u.eval_date
GROUP BY tc.team_id;
```

**CIO lift (ADVANCE vs. REJECT):**
```sql
SELECT
    ce.cio_decision,
    AVG(u.return_5d) AS avg_return,
    COUNT(*) AS n
FROM cio_evaluations ce
JOIN universe_returns u ON ce.ticker = u.ticker AND ce.eval_date = u.eval_date
GROUP BY ce.cio_decision;
```

**Predictor separation within picks:**
```sql
SELECT
    CASE
        WHEN po.predicted_direction = 'UP' AND po.prediction_confidence > 0.65 THEN 'favored'
        WHEN po.predicted_direction = 'DOWN' AND po.prediction_confidence > 0.60 THEN 'vetoed'
        ELSE 'neutral'
    END AS bucket,
    AVG(po.actual_5d_return) AS avg_return,
    COUNT(*) AS n
FROM predictor_outcomes po
WHERE po.prediction_date = '2026-03-31'
GROUP BY bucket;
```

**Risk guard accuracy (blocked vs. traded):**
```sql
SELECT 'blocked' AS cohort, AVG(return_5d) AS avg_return, COUNT(*) AS n
FROM executor_shadow_book WHERE eval_date = '2026-03-31'
UNION ALL
SELECT 'traded', AVG(realized_return_pct), COUNT(*)
FROM trades WHERE date = '2026-03-31' AND action = 'ENTER';
```

### Storage summary

| Table | DB | Rows/week | Module | New? |
|-------|-----|-----------|--------|------|
| `universe_returns` | research.db | 900 | Research | **New** |
| `scanner_evaluations` | research.db | 900 | Research | **New** |
| `team_candidates` | research.db | 60 | Research | **New** |
| `cio_evaluations` | research.db | 12-18 | Research | **New** |
| `score_performance` | research.db | 25 | Research | Existing (add `beat_spy_5d`) |
| `predictor_outcomes` | research.db | 25 | Predictor | Existing (sufficient) |
| `executor_shadow_book` | trades.db | 5-10 | Executor | **New** |
| `trades` | trades.db | 15-30 | Executor | Existing (sufficient) |
| `eod_pnl` | trades.db | 5 | Executor | Existing (sufficient) |

Total new DB growth: ~100K rows/year (~50MB). Negligible for SQLite.

---

### Phase 1: Data foundation (prerequisite for everything else)

| Priority | Item | Table | Module to change | Effort | Status |
|----------|------|-------|------------------|--------|--------|
| 1a | Create `universe_returns` table + weekly batch fill | `universe_returns` | Backtester | Medium | **DONE** (2026-04-02) — `analysis/universe_returns.py`, uses `get_grouped_daily()`, wired into signal quality pipeline |
| 1b | Create `scanner_evaluations` table, log all 900 in scanner | `scanner_evaluations` | Research (`scanner.py`) | Low | **DONE** (2026-04-01) — schema in `archive/schema.py` migration v8, write in `archive/manager.py`, scanner populates for all 900 tickers |
| 1c | Create `team_candidates` table, log quant top-10 per team | `team_candidates` | Research (sector team node) | Low | **DONE** (2026-04-01) — schema in `archive/schema.py`, write in `archive/manager.py`, persisted from `research_graph.py` |
| 1d | Create `cio_evaluations` table, log all CIO decisions | `cio_evaluations` | Research (CIO node) | Low | **DONE** (2026-04-01) — schema in `archive/schema.py`, captures ADVANCE/REJECT/DEADLOCK with scores, macro shift, conviction, rationale |
| 1e | Add `beat_spy_5d` column to `score_performance` | `score_performance` | Backtester (backfill logic) | Low | **DONE** (2026-04-02) — `_ensure_5d_columns()` migration + 5d backfill in `_backfill_score_performance_returns`, reporter/signal_quality/regime/score_analysis all updated |
| 1f | Create `executor_shadow_book`, log risk guard blocks | `executor_shadow_book` | Executor (`risk_guard.py`) | Low | **DONE** (2026-04-01) — schema in `trade_logger.py`, logged from `main.py` when risk guard blocks an entry |
| 1g | Build `analysis/end_to_end.py` with lift queries | — | Backtester | Medium | **DONE** (2026-04-02) — `analysis/end_to_end.py`, computes lift at all 5 decision boundaries, attribution table builder, wired into report |

**Progress:** 7 of 7 items complete. Phase 1 data foundation is fully implemented.

**Why this is first:** Without full-population tracking, every evaluation measures in a vacuum. Items 1b-1f are small schema + logging changes in existing code (each module logs what it already computes). Item 1a requires the polygon.io batch endpoint for 900 tickers. Item 1g ties it all together into the weekly evaluation report.

### Phase 2: Lift metrics at each decision boundary

| Priority | Item | Baseline comparison | What it answers | Status |
|----------|------|---------------------|-----------------|--------|
| 2a | Scanner filter lift | Passing vs. full 900 | Does the quant filter select outperformers? | **DONE** (2026-04-02) — `_scanner_lift()` in `end_to_end.py`, passing avg vs universe avg |
| 2b | Sector team lift (per team) | Team picks vs. own sector avg from 900 | Does each team beat its sector? | **DONE** (2026-04-02) — `_team_lift()` now compares picks against full sector avg from `universe_returns` (not just quant candidates) |
| 2c | Quant vs. qual+peer lift | Team picks vs. quant top-10 | Does LLM analysis add value over quant alone? | **DONE** (2026-04-02) — `_team_lift()` also computes `lift_vs_quant` (picks vs quant candidates avg) per team |
| 2d | CIO lift | ADVANCE vs. all 12-18 sector recs | Does CIO pick the best of what teams recommended? | **DONE** (2026-04-02) — `_cio_lift()` with ADVANCE/REJECT avg split |
| 2e | CIO vs. score-ranking baseline | CIO picks vs. top-N-by-score | Does LLM judgment beat mechanical ranking? | **DONE** (2026-04-02) — `_cio_vs_ranking_lift()` compares CIO picks vs counterfactual top-N by final_score per date, with overlap tracking |
| 2f | Predictor lift | UP-predicted vs. all picks | Does the model separate within picked stocks? | **DONE** (2026-04-02) — `_predictor_lift()` with UP/DOWN/ALL split |
| 2g | Execution lift | Traded returns vs. naive buy-and-hold of approved picks | Does execution add value? | **DONE** (2026-04-02) — `_executor_lift()` using shadow book for approved baseline |

**Key insight:** 2b and 2d are the highest-signal evaluations for research. If sector teams can't beat their sector average, the LLM analysis isn't working. If the CIO can't beat score-ranking, replace it with a rule.

**Status:** All 7 items implemented in `end_to_end.py`. Lift metrics are computed automatically by the backtester on each weekly run. Results will become statistically meaningful after 4+ weeks of `universe_returns` data accumulation.

### Phase 3: Component-level diagnostics

| Priority | Item | Module | Effort | What it answers | Status |
|----------|------|--------|--------|-----------------|--------|
| 3a | Entry trigger scorecard | Executor | Low | Which triggers get better fills? | **DONE** (2026-04-02) — `analysis/trigger_scorecard.py`, computes per-trigger slippage vs signal/open, realized alpha, win rate. Wired into reporter + backtest.py |
| 3b | Risk guard shadow book analysis | Executor | Low | Is the guard too conservative? | **DONE** (2026-04-02) — `analysis/shadow_book.py`, compares blocked vs traded forward returns via universe_returns, breakdown by block reason, guard assessment. Wired into reporter + backtest.py |
| 3c | Exit timing analysis (MFE/MAE) | Executor | Medium | Are exits well-timed? | **DONE** (2026-04-02) — `analysis/exit_timing.py`, computes MFE/MAE per roundtrip trade via yfinance, capture ratio, by-exit-type breakdown, diagnosis. Wired into reporter + backtest.py |
| 3d | Confidence calibration curve | Predictor | Low | Is the model well-calibrated? | **DONE** — `model/calibrator.py` implements Platt scaling + isotonic regression with ECE metric, integrated into inference pipeline |
| 3e | Net veto value in dollars | Predictor | Medium | True ROI of the veto system | **DONE** (2026-04-02) — `analysis/veto_value.py`, computes dollar losses avoided vs alpha foregone per veto, by-confidence breakdown, net veto value. Wired into reporter + backtest.py |
| 3f | Macro multiplier A/B | Research | Medium | Does the macro shift help or hurt? | **DONE** (2026-04-02) — `analysis/macro_eval.py`, A/B comparison of accuracy/alpha with vs without macro shift, macro impact on BUY status, shift statistics. Wired into reporter + backtest.py |
| 3g | Alpha magnitude distribution | Research | Low | Beyond binary beat_spy | **DONE** (2026-04-02) — `analysis/alpha_distribution.py`, buckets alpha into 6 ranges across 5d/10d/30d, plus score calibration curve (monotonicity check). Wired into reporter + backtest.py |

### Phase 4: Self-adjustment mechanisms

| Priority | Item | Module | Effort | What it answers | Status |
|----------|------|--------|--------|-----------------|--------|
| 4a | Auto-relax scanner filter if leakage is high | Research | Medium | Adaptive quant filter thresholds | **DONE** (2026-04-02) — `optimizer/scanner_optimizer.py` in backtester: analyzes filter leakage from scanner_evaluations + universe_returns, writes relaxed thresholds to `config/scanner_params.json`. Research `config.py` reads via `get_scanner_params()`, scanner uses dynamic thresholds. Min-data gate: 8 weeks. |
| 4b | Sector team slot allocation based on rolling lift | Research | Medium | More picks from better teams | **DONE** (2026-04-02) — `optimizer/pipeline_optimizer.py` in backtester: analyzes team lift from end_to_end, recommends slot changes, writes to `config/team_slots.json`. Min-data gate: 8 weeks. |
| 4c | CIO → deterministic fallback if lift is zero | Research | Medium | Simplify when LLM doesn't help | **DONE** (2026-04-02) — `optimizer/pipeline_optimizer.py` in backtester: compares CIO lift vs score-ranking baseline, writes `cio_mode` to `config/research_params.json` if underperforming. Min-data gate: 8 weeks. |
| 4d | Predictor p_up → position sizing if IC positive | Predictor | Medium | Use predictions beyond veto | **DONE** (2026-04-02) — `optimizer/predictor_sizing_optimizer.py` in backtester: computes rank IC, writes `use_p_up_sizing` to executor_params.json. Executor `position_sizer.py` blends p_up into sizing. Min-data gate: 30 predictions. |
| 4e | Disable underperforming triggers | Executor | Low | Simplify execution | **DONE** (2026-04-02) — `optimizer/trigger_optimizer.py` in backtester: analyzes trigger scorecard, writes `disabled_triggers` list to executor_params.json. Executor `entry_triggers.py` skips disabled triggers. Min-data gate: 50 trades per trigger. |
| 4f | Position sizing A/B vs. equal-weight | Executor | Medium | Does sizing earn its complexity? | **DONE** (2026-04-02) — `analysis/sizing_ab.py` in backtester: runs twin VectorBT simulation (current sizing vs equal-weight), compares Sharpe/alpha. Report-only, no config write. Min-data gate: 50 trades. |

### Phase 5: System maturity

| Priority | Item | Module | Effort | What it answers | Status |
|----------|------|--------|--------|-----------------|--------|
| 5a | Alpha decomposition (entry/exit/sizing/guard) | Executor | High | Where exactly does alpha come from and leak? | **Not started** |
| 5b | Realistic slippage model from live trade data | Executor | High | More accurate backtests | **Not started** |
| 5c | Canary deployment for param changes | Cross-module | High | Safe parameter promotion | **Not started** |
| 5d | Cross-module feedback (executor liquidity → research) | Cross-module | High | Closed-loop learning | **Not started** |
| 5e | Signal decay analysis | Research | Medium | Do signals have a shelf life? | **Not started** |

**Implementation note:** Phase 1 is pure data plumbing — no new algorithms, just logging what's already computed. Phase 2 is arithmetic on the Phase 1 data. Phase 3 can run in parallel with Phase 2. Phase 4 is where the system starts adjusting itself. Phase 5 is maturity work requiring 8+ weeks of data.

---

## 8. Progress Summary (updated 2026-04-02)

### Completed (29 items)
| Item | Module | Date | Notes |
|------|--------|------|-------|
| 1a | Backtester | 2026-04-02 | `universe_returns` table + `analysis/universe_returns.py` — uses polygon.io `get_grouped_daily()` for all ~900 tickers, computes 5d/10d forward returns, SPY/sector ETF benchmarks |
| 1b | Research | 2026-04-01 | `scanner_evaluations` — all 900 tickers logged per run |
| 1c | Research | 2026-04-01 | `team_candidates` — quant top-10 per team persisted |
| 1d | Research | 2026-04-01 | `cio_evaluations` — ADVANCE/REJECT/DEADLOCK with full context |
| 1e | Backtester | 2026-04-02 | `beat_spy_5d` column + `_ensure_5d_columns()` migration + 5d backfill loop. All analysis modules (signal_quality, regime, score, reporter) updated for 3-horizon (5d/10d/30d) output |
| 1f | Executor | 2026-04-01 | `executor_shadow_book` — risk guard blocks logged with enriched context |
| 1g | Backtester | 2026-04-02 | `analysis/end_to_end.py` — computes lift at all 5 decision boundaries (scanner, team, CIO, predictor, executor). Attribution table builder for CSV export. Wired into weekly report |
| 2a | Backtester | 2026-04-02 | Scanner filter lift — `_scanner_lift()` in `end_to_end.py`, passing avg vs universe avg |
| 2b | Backtester | 2026-04-02 | Sector team lift — `_team_lift()` compares picks against full sector avg from universe_returns |
| 2c | Backtester | 2026-04-02 | Quant vs qual+peer lift — `_team_lift()` computes `lift_vs_quant` per team |
| 2d | Backtester | 2026-04-02 | CIO lift — `_cio_lift()` with ADVANCE/REJECT avg split |
| 2e | Backtester | 2026-04-02 | CIO vs score-ranking baseline — `_cio_vs_ranking_lift()`, counterfactual top-N by score with overlap tracking |
| 2f | Backtester | 2026-04-02 | Predictor lift — `_predictor_lift()` with UP/DOWN/ALL split |
| 2g | Backtester | 2026-04-02 | Execution lift — `_executor_lift()` using shadow book for approved baseline |
| 3a | Backtester | 2026-04-02 | `analysis/trigger_scorecard.py` — per-trigger slippage vs signal/open, realized alpha, win rate. Categorizes pullback/VWAP/support/time_expiry. Wired into reporter + backtest.py |
| 3b | Backtester | 2026-04-02 | `analysis/shadow_book.py` — compares blocked vs traded forward returns via universe_returns join, breakdown by block reason, guard tightness assessment. Wired into reporter + backtest.py |
| 3c | Backtester | 2026-04-02 | `analysis/exit_timing.py` — MFE/MAE per roundtrip trade via yfinance, capture ratio (realized/MFE), by-exit-type breakdown, diagnosis (too_early/well_timed/could_improve). Wired into reporter + backtest.py |
| 3d | Predictor | Pre-plan | Platt calibrator + isotonic regression with ECE, integrated into inference |
| 3e | Backtester | 2026-04-02 | `analysis/veto_value.py` — dollar losses avoided vs alpha foregone per DOWN prediction, by-confidence breakdown, net veto value. Uses shadow book for position sizing. Wired into reporter + backtest.py |
| 3f | Backtester | 2026-04-02 | `analysis/macro_eval.py` — A/B comparison of accuracy/alpha with vs without macro shift using cio_evaluations + universe_returns, macro impact on BUY status changes, shift statistics. Wired into reporter + backtest.py |
| 3g | Backtester | 2026-04-02 | `analysis/alpha_distribution.py` — alpha bucketed into 6 ranges across 5d/10d/30d horizons, score calibration curve with monotonicity check. Wired into reporter + backtest.py |
| 4a | Backtester + Research | 2026-04-02 | `optimizer/scanner_optimizer.py` — analyzes filter leakage from scanner_evaluations + universe_returns, writes to `config/scanner_params.json`. Research `config.py` adds `get_scanner_params()`, scanner uses S3-configurable thresholds. Min-data gate: 8 weeks |
| 4b | Backtester | 2026-04-02 | `optimizer/pipeline_optimizer.py` — analyzes team lift, recommends slot changes, writes to `config/team_slots.json`. Min-data gate: 8 weeks |
| 4c | Backtester | 2026-04-02 | `optimizer/pipeline_optimizer.py` — compares CIO lift vs score-ranking baseline, writes `cio_mode` flag to `config/research_params.json`. Min-data gate: 8 weeks |
| 4d | Backtester + Executor | 2026-04-02 | `optimizer/predictor_sizing_optimizer.py` — computes rank IC, writes `use_p_up_sizing` to executor_params.json. Executor `position_sizer.py` blends p_up into sizing when enabled. Min-data gate: 30 predictions |
| 4e | Backtester + Executor | 2026-04-02 | `optimizer/trigger_optimizer.py` — analyzes trigger scorecard, writes `disabled_triggers` to executor_params.json. Executor `entry_triggers.py` skips disabled triggers. Min-data gate: 50 trades per trigger |
| 4f | Backtester | 2026-04-02 | `analysis/sizing_ab.py` — twin VectorBT simulation (current sizing vs equal-weight), compares Sharpe/alpha. Report-only. Min-data gate: 50 trades |
| — | Dashboard | 2026-04-02 | `pages/9_Data_Inventory.py` expanded with 5 new eval tables + 6 Phase 4 optimizer maturity rows with progress bars |
| — | Dashboard | 2026-04-02 | `pages/10_Evaluation.py` — new page with lift waterfall chart, Phase 3 component diagnostic tabs, Phase 4 self-adjustment status panel with live S3 config display |

### Phases 1–4 complete — next steps
**Phases 1, 2, 3, and 4 are fully implemented.** The data foundation, lift metrics, component diagnostics, and self-adjustment mechanisms are all in place. All Phase 4 optimizers have min-data gates that keep them dormant until sufficient data accumulates — they will activate automatically.

**Dashboard tracking:** The Data Inventory page now shows progress bars for all Phase 4 optimizers (scanner auto-relax: 8 weeks, team slots: 8 weeks, CIO fallback: 8 weeks, p_up sizing: 30 predictions, trigger optimizer: 200 trades, sizing A/B: 50 trades). The new Evaluation page visualizes lift metrics, component diagnostics, and current self-adjustment state.

Next priorities:

1. **Data accumulation** — All Phase 4 mechanisms are built but dormant. They activate automatically once min-data gates are met. Monitor via Dashboard Data Inventory page.
2. **Phase 5: System maturity** — alpha decomposition (5a), realistic slippage model (5b), canary deployment (5c), cross-module feedback (5d), signal decay analysis (5e). All require 8+ weeks of live trading data.
