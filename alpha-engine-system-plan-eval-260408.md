# Alpha Engine: System Evaluation Audit

**Date:** 2026-04-08
**Purpose:** Map the existing evaluation infrastructure, define the optimized weekly evaluation, and identify gaps.

---

## Executive Summary

The system already has a **comprehensive evaluation framework** in the backtester — far more than most algorithmic trading systems. The backtester produces a ~25-section weekly report covering signal quality, attribution, pipeline lift, veto analysis, entry triggers, exit timing, position sizing, risk guard effectiveness, and auto-optimization across all modules. The key gaps are not in *what metrics exist* but in:

1. **Data maturity** — many optimizers are gated behind sample thresholds (30-200 rows) and won't activate for weeks/months
2. **Component-level grading** — no unified scorecard that assigns A/B/C/D/F grades per component
3. **Sector analyst vs CIO separation** — evaluation tables exist but aren't surfaced as explicit grades
4. **Precision/recall/F1 framing** — most metrics use accuracy + alpha, not full classification metrics
5. **Dashboard surfacing** — the backtester computes everything but the dashboard only shows a subset

---

## 1. Research Module Evaluation

### 1A. Sector Analyst Grading

**What they do:** 6 sector teams each screen their sector's quant top-10, add fundamental analysis, and recommend 2-3 picks.

**Existing evaluation infrastructure:**

| Component | Status | Location | Detail |
|-----------|--------|----------|--------|
| Team selection lift (picks vs sector avg) | IMPLEMENTED | `end_to_end.py` | avg return of team picks vs all same-sector stocks |
| Team lift vs quant baseline (picks vs quant top-10) | IMPLEMENTED | `pipeline_optimizer.py` | measures whether qual/peer review adds value over quant screening |
| Per-team scorecard | IMPLEMENTED | `reporter.py` Phase 4 | n_picks, lift, assessment (outperforming/neutral/underperforming) |
| Auto slot adjustment | IMPLEMENTED | `pipeline_optimizer.py` | teams with lift < -0.5% for 8 weeks get -1 slot |
| Team quant candidates table | IMPLEMENTED | `team_candidates` in research.db | quant top-10 per sector persisted with quant_rank, qual_score, team_recommended flag |
| Sector ETF-relative precision | PARTIALLY | `end_to_end.py` | uses universe_returns, but not explicitly sector-ETF-relative |

**What's missing for optimized grading:**

| Gap | Impact | Effort |
|-----|--------|--------|
| No explicit precision/recall/F1 per team | Can't distinguish "picks few but all win" from "picks many, most win" | LOW — compute from existing team_candidates + universe_returns |
| No sector-ETF-relative measurement (XLK, XLV, etc.) | Team could look good because whole sector did well | MEDIUM — need to pull sector ETF returns and normalize |
| No "best stock in sector that was NOT picked" metric | Can't measure opportunity cost (what did we miss?) | MEDIUM — requires universe_returns for all sector stocks |
| No grade letter (A-F) or numeric grade (0-100) | Results are lift percentages, not intuitive grades | LOW — wrap existing metrics in a grading function |

**Optimized sector analyst grade formula:**

```
Sector Analyst Grade = weighted average of:
  (0.40) Selection Precision: % of team picks that beat sector ETF at 10d
  (0.30) Selection Lift: avg alpha of team picks vs sector population (normalized to 0-100)
  (0.20) Opportunity Capture: % of sector's top-5 performers that were in team picks
  (0.10) Consistency: % of last 8 weeks with positive lift

Grade bands: A (80-100), B (65-79), C (50-64), D (35-49), F (<35)
```

### 1B. CIO Grading

**What they do:** CIO receives all sector team recommendations (~12-18), evaluates against macro context and portfolio fit, and promotes ~3-8 to BUY/ENTER.

**Existing evaluation infrastructure:**

| Component | Status | Location | Detail |
|-----------|--------|----------|--------|
| CIO selection lift (ADVANCE vs all recommendations) | IMPLEMENTED | `end_to_end.py` | avg return of ADVANCE picks vs all recommendations |
| CIO vs ranking baseline | IMPLEMENTED | `pipeline_optimizer.py` | ADVANCE picks vs deterministic top-N-by-score |
| CIO rejection accuracy | IMPLEMENTED | `end_to_end.py` | avg return of REJECT stocks (should be lower) |
| CIO fallback recommendation | IMPLEMENTED | `pipeline_optimizer.py` | recommends deterministic mode if CIO underperforms for 8 weeks |
| CIO decision logging | IMPLEMENTED | `cio_evaluations` in research.db | ADVANCE/REJECT/DEADLOCK with conviction, rank, rationale |
| Tracking returns of REJECTED candidates | IMPLEMENTED | `score_performance` expanded to track all CIO-evaluated candidates |

**What's missing for optimized grading:**

| Gap | Impact | Effort |
|-----|--------|--------|
| No precision/recall framing | "Of the best stocks available, how many did CIO pick?" is recall; "of picks, how many were good?" is precision | LOW — compute from existing cio_evaluations + universe_returns |
| No portfolio-fit evaluation | CIO adds diversification value but this isn't measured vs pure-alpha ranking | MEDIUM — need Sharpe comparison: CIO portfolio vs top-N portfolio |
| No grade letter/numeric | Results are lift values, not grades | LOW |

**Optimized CIO grade formula:**

```
CIO Grade = weighted average of:
  (0.35) Selection Precision: % of ADVANCE picks that beat SPY at 10d
  (0.25) Selection Recall: % of top-5 performers (from all recommendations) that CIO advanced
  (0.20) Rejection Accuracy: % of REJECT picks that underperformed SPY
  (0.10) CIO Lift vs Ranking: excess return over deterministic top-N baseline
  (0.10) Portfolio Diversification: HHI improvement vs pure-score-ranking portfolio

Grade bands: A (80-100), B (65-79), C (50-64), D (35-49), F (<35)
```

### 1C. Scanner Grading

**Existing evaluation:**

| Component | Status | Location |
|-----------|--------|----------|
| Filter lift (passing vs all 900) | IMPLEMENTED | `end_to_end.py` |
| Filter leakage (% of rejected stocks that beat SPY) | IMPLEMENTED | `pipeline_optimizer.py` |
| Per-gate breakdown (which filter rejected each stock) | IMPLEMENTED | `scanner_evaluations` table |
| Full universe logging (all 900 with pass/fail) | IMPLEMENTED | `scanner_evaluations` table |
| Auto-threshold relaxation | IMPLEMENTED | `pipeline_optimizer.py` |

**Scanner is well-covered.** Main gap: no explicit grade, just lift metrics.

### 1D. Macro Agent Grading

**Existing evaluation:**

| Component | Status | Location |
|-----------|--------|----------|
| Macro shift A/B (accuracy with vs without macro) | IMPLEMENTED | `macro_eval.py` |
| Macro lift assessment (helps/hurts/neutral) | IMPLEMENTED | `reporter.py` |
| Promoted/demoted stock counts | IMPLEMENTED | `macro_eval.py` |

**Gap:** No per-sector modifier accuracy (did overweighting Tech help this week?). Would need sector-level returns vs modifier direction comparison.

### 1E. Composite Scoring Grading

**Existing evaluation:**

| Component | Status | Location |
|-----------|--------|----------|
| Score calibration monotonicity (higher score = higher alpha?) | IMPLEMENTED | `alpha_distribution.py` |
| Score bucket accuracy (60-70, 70-80, 80-90, 90+) | IMPLEMENTED | `signal_quality.py` |
| Sub-score attribution (quant vs qual correlation) | IMPLEMENTED | `attribution.py` with FDR correction |
| Weight auto-optimization | IMPLEMENTED | `weight_optimizer.py` |
| Boost parameter attribution | IMPLEMENTED | `research_optimizer.py` (deferred until 200 samples) |

**Well-covered.** Gap: no interaction effects (quant*qual), only univariate correlations.

---

## 2. Predictor Module Evaluation

### 2A. GBM Model Quality

**Existing evaluation:**

| Component | Status | Location |
|-----------|--------|----------|
| Information Coefficient (IC) | IMPLEMENTED | `metrics/latest.json`, `gbm_scorer.py` |
| IC IR (IC / std) | IMPLEMENTED | walk-forward report |
| Hit rate (30d rolling) | IMPLEMENTED | `metrics/latest.json` |
| Walk-forward validation (5 folds, IC per fold) | IMPLEMENTED | `train_handler.py` |
| IC gate for model promotion | IMPLEMENTED | IC > 0.05 required |
| Feature importance (SHAP/gain) | IMPLEMENTED | `feature_importance.json` |
| Feature drift detection (z-score > 3.0) | IMPLEMENTED | `monitoring/drift_detector.py` |
| Prediction clustering detection | IMPLEMENTED | `signal_generator.py` |
| Confidence calibration | IMPLEMENTED | `model/calibrator.py` (Platt/isotonic) |

### 2B. Veto Gate Effectiveness

**Existing evaluation:**

| Component | Status | Location |
|-----------|--------|----------|
| Veto precision per threshold | IMPLEMENTED | `veto_analysis.py` |
| Missed alpha per threshold | IMPLEMENTED | `veto_analysis.py` |
| Lift over base rate | IMPLEMENTED | `veto_analysis.py` (min 5pp gate) |
| Cost sensitivity analysis | IMPLEMENTED | `veto_analysis.py` (multi cost-weight sweep) |
| Dollar value of veto system | IMPLEMENTED | `veto_value.py` |
| Regime-adaptive threshold adjustment | IMPLEMENTED | `write_output.py` |
| Auto-threshold promotion to S3 | IMPLEMENTED | `veto_analysis.py` → `config/predictor_params.json` |

### 2C. Predictor Sizing Signal

**Existing evaluation:**

| Component | Status | Location |
|-----------|--------|----------|
| Rank IC of p_up vs actual 5d return | IMPLEMENTED | `predictor_sizing_optimizer.py` |
| Rolling weekly IC | IMPLEMENTED | 6/8 positive weeks required |
| p_up sizing recommendation | IMPLEMENTED | auto-enable if rank IC >= 0.05 |

**What's missing for optimized grading:**

| Gap | Impact | Effort |
|-----|--------|--------|
| No explicit precision/recall for UP/DOWN predictions | "Of stocks predicted UP, how many actually went up?" is precision; "Of stocks that went up, how many were predicted UP?" is recall | LOW — compute from predictor_outcomes |
| No per-sector model accuracy | Model may work for Tech but not Healthcare | MEDIUM — stratify predictor_outcomes by sector |
| No confusion matrix | Can't see UP→DOWN misclassification vs UP→FLAT | LOW — compute from predictor_outcomes |

**Optimized predictor grade formula:**

```
Predictor Grade = weighted average of:
  (0.30) Directional Accuracy: % correct UP/DOWN predictions at 5d
  (0.25) Information Coefficient: rank correlation of p_up vs actual 5d return
  (0.20) Veto Precision: % of vetoed stocks that actually underperformed
  (0.15) Calibration Quality: 1 - ECE (expected calibration error)
  (0.10) Stability: % of walk-forward folds with positive IC

Grade bands: A (80-100), B (65-79), C (50-64), D (35-49), F (<35)
```

---

## 3. Executor Module Evaluation

### 3A. Entry Trigger Grading

**Existing evaluation:**

| Component | Status | Location |
|-----------|--------|----------|
| Per-trigger slippage vs signal price | IMPLEMENTED | `trigger_scorecard.py` |
| Per-trigger slippage vs market open | IMPLEMENTED | `trigger_scorecard.py` |
| Per-trigger avg alpha | IMPLEMENTED | `trigger_scorecard.py` |
| Per-trigger win rate | IMPLEMENTED | `trigger_scorecard.py` |
| Auto-disable underperforming triggers | IMPLEMENTED | `trigger_optimizer.py` (50 trades + alpha < -0.5% or win rate < 40%) |
| Execution quality JSON (daily) | IMPLEMENTED | `eod_reconcile.py` → `trades/execution_quality/{date}.json` |

**Well-covered.** Gap: no grade, just per-trigger metrics.

### 3B. Risk Guard Grading

**Existing evaluation:**

| Component | Status | Location |
|-----------|--------|----------|
| Shadow book (blocked vs traded returns) | IMPLEMENTED | `shadow_book.py` |
| Guard lift metric | IMPLEMENTED | `shadow_book.py` |
| Assessment (too_tight / appropriate / too_loose) | IMPLEMENTED | `shadow_book.py` |
| Block reason breakdown | IMPLEMENTED | `shadow_book.py` |

### 3C. Exit Rule Grading

**Existing evaluation:**

| Component | Status | Location |
|-----------|--------|----------|
| MFE/MAE analysis | IMPLEMENTED | `exit_timing.py` |
| Capture ratio (realized / MFE) | IMPLEMENTED | `exit_timing.py` |
| By exit type breakdown | IMPLEMENTED | `exit_timing.py` (ATR, time_decay, profit_take, stop_loss) |
| Diagnosis (exits_too_early / well_timed / could_improve) | IMPLEMENTED | `exit_timing.py` |

### 3D. Position Sizing Grading

**Existing evaluation:**

| Component | Status | Location |
|-----------|--------|----------|
| Current sizing vs equal-weight A/B | IMPLEMENTED | `sizing_ab.py` |
| Sharpe/return/alpha comparison | IMPLEMENTED | `sizing_ab.py` |
| Assessment | IMPLEMENTED | `sizing_ab.py` |

### 3E. Portfolio-Level Grading

**Existing evaluation:**

| Component | Status | Location |
|-----------|--------|----------|
| NAV, daily return, daily alpha | IMPLEMENTED | `eod_reconcile.py` daily |
| Cumulative alpha vs SPY | IMPLEMENTED | `eod_pnl.csv` |
| Sharpe ratio | IMPLEMENTED | `vectorbt_bridge.py` |
| Max drawdown + Calmar ratio | IMPLEMENTED | `vectorbt_bridge.py` |
| Sector attribution | IMPLEMENTED | `eod_reconcile.py` |
| Roundtrip stats (win rate, avg alpha) | IMPLEMENTED | `eod_reconcile.py` |

**What's missing for optimized grading:**

| Gap | Impact | Effort |
|-----|--------|--------|
| No alpha decomposition (signal alpha + entry timing alpha + exit alpha + sizing alpha) | Can't attribute where alpha comes from or leaks | HIGH — requires reconstructing counterfactual returns at each stage |
| No transaction cost attribution | Don't know how much slippage + commissions eat | LOW — data exists in trades table |

---

## 4. Cross-Module (Pipeline) Evaluation

### 4A. End-to-End Lift Chain

**Existing evaluation:**

| Component | Status | Location |
|-----------|--------|----------|
| 5-stage lift waterfall (scanner → teams → CIO → predictor → executor) | IMPLEMENTED | `end_to_end.py` |
| Per-stage population, avg return, baseline, lift | IMPLEMENTED | `end_to_end.py` |
| Dashboard visualization (Pipeline Evaluation tab) | IMPLEMENTED | `pages/3_Analysis.py` Tab 3 |

### 4B. Regression Monitor

**Existing evaluation:**

| Component | Status | Location |
|-----------|--------|----------|
| Auto-rollback verdict (accuracy_drop, sharpe_drop_pct) | IMPLEMENTED | `reporter.py` |
| Twin simulation (current vs proposed params) | IMPLEMENTED | `reporter.py` |

### 4C. Feedback Loop Maturity

**Existing evaluation:**

| Component | Status | Location |
|-----------|--------|----------|
| 11 optimizer thresholds tracked | IMPLEMENTED | `reporter.py` data accumulation section |
| Progress bars toward activation | IMPLEMENTED | `reporter.py` + dashboard System Health page |
| Status per optimizer (active/blocked/collecting/deferred) | IMPLEMENTED | dashboard System Health |

---

## 5. Weekly Report Structure (Already Implemented)

The backtester's `reporter.py` already generates a **25-section weekly report** including:

1. Data accumulation progress
2. Pipeline health (DB status, coverage)
3. Optimizer promotions (what changed this week)
4. Signal quality (accuracy by horizon, bucket, conviction)
5. Score threshold analysis
6. Regime analysis
7. Sub-score attribution (with FDR correction)
8. Alpha distribution + calibration curve
9. End-to-end pipeline lift
10. Macro evaluation (with/without A/B)
11. Trigger optimizer results
12. Predictor sizing evaluation
13. Scanner optimizer
14. Team slot allocation
15. CIO fallback analysis
16. Position sizing A/B
17. Portfolio simulation (VectorBT)
18. Parameter sweep (top 10 by Sharpe)
19. Weight recommendation
20. Veto threshold analysis
21. Executor parameter recommendations
22. Entry trigger scorecard
23. Veto dollar value
24. Shadow book (risk guard)
25. Exit timing (MFE/MAE)

**This is comprehensive.** The report runs weekly on Saturday as part of the Step Function pipeline.

---

## 6. Gap Analysis: Existing vs Optimized

### GAP 1: No Unified Component Scorecard with Grades (PRIORITY: HIGH)

**Current state:** Each component has metrics (lift, accuracy, IC) scattered across report sections. No single view that says "Research: B+, Predictor: A-, Executor: C+."

**Optimized state:** A single "System Report Card" section at the top of the weekly report that grades every component on a 0-100 scale with letter grades.

**Proposed scorecard:**

```
=== ALPHA ENGINE WEEKLY REPORT CARD — 2026-04-08 ===

OVERALL SYSTEM GRADE: B (72/100)
  Cumulative Alpha: +3.2%  |  Sharpe: 1.15  |  Max DD: -4.8%

MODULE GRADES:
  Research ............... B+ (78)
    Scanner .............. A- (82)  Lift: +1.4%, Leakage: 8%
    Technology Team ...... A  (88)  Precision: 71%, Lift: +2.6%
    Healthcare Team ...... B  (73)  Precision: 58%, Lift: +0.8%
    Financials Team ...... C+ (56)  Precision: 44%, Lift: -0.3%
    Industrials Team ..... B- (68)  Precision: 52%, Lift: +0.4%
    Consumer Team ........ D  (42)  Precision: 33%, Lift: -1.1%
    Utilities Team ....... B  (71)  Precision: 55%, Lift: +0.5%
    Macro Agent .......... B  (70)  Accuracy A/B lift: +2.1%
    CIO .................. B+ (76)  Precision: 65%, vs Ranking: +1.8%
    Composite Scoring .... A- (83)  Monotonic: YES, 90+ bucket: 72% acc

  Predictor .............. B  (71)
    GBM Model ............ B  (70)  IC: 0.062, Hit Rate: 54.8%
    Veto Gate ............ B+ (77)  Precision: 68%, Net Value: +$420
    Confidence Calibration C+ (58)  ECE: 0.12

  Executor ............... C+ (59)
    Entry Triggers ....... B- (64)  Avg improvement vs open: -0.3%
    Risk Guard ........... B  (72)  Guard lift: +1.2%, Assessment: appropriate
    Exit Rules ........... C  (53)  Capture ratio: 0.61, Diagnosis: exits_too_early
    Position Sizing ...... C+ (57)  Sizing vs EW Sharpe diff: +0.08
    Portfolio Construction  B- (66)  Daily alpha: +0.04%, Win rate: 54%
```

**Implementation:** Add a `grading.py` module to the backtester that:
1. Takes all analysis results as input
2. Computes a 0-100 grade per component using the formulas defined above
3. Maps to letter grades
4. Returns a structured dict for the reporter
5. Reporter inserts the scorecard as the first section after the header

**Effort:** LOW-MEDIUM (1-2 sessions). All underlying data already exists — this is a presentation/aggregation layer.

### GAP 2: No Precision/Recall/F1 Metrics (PRIORITY: MEDIUM)

**Current state:** Most components use "accuracy" (% that beat SPY) and "lift" (excess return). Standard classification metrics (precision, recall, F1, confusion matrix) are not computed.

**Optimized state:** For each decision-making component, compute:

| Component | Positive Class | Precision | Recall | F1 |
|-----------|---------------|-----------|--------|-----|
| Scanner | Stock beats SPY at 10d | % of passed stocks that beat SPY | % of all SPY-beaters that passed filter | Harmonic mean |
| Sector Team | Stock beats sector ETF at 10d | % of team picks that beat sector ETF | % of sector's top-5 that were picked | Harmonic mean |
| CIO | Stock beats SPY at 10d | % of ADVANCE picks that beat SPY | % of all beaters (from recommendations) that were advanced | Harmonic mean |
| Predictor (UP) | Stock goes up 5d | % of UP predictions correct | % of actual up-moves that were predicted UP | Harmonic mean |
| Predictor (veto) | Stock goes down 5d | % of vetoes correct (precision) | % of actual down-moves that were vetoed (recall) | Harmonic mean |
| Risk Guard | Stock would have lost money | % of blocked entries that would have lost | % of all losers that were blocked | Harmonic mean |

**Implementation:** Add a `classification_metrics.py` utility that computes precision/recall/F1/confusion matrix from boolean arrays. Call it from each existing analysis module.

**Effort:** LOW (half a session). The boolean outcome data (beat_spy, correct_5d, etc.) already exists in the evaluation tables.

### GAP 3: No Per-Sector Model/Signal Accuracy (PRIORITY: MEDIUM)

**Current state:** Predictor accuracy and signal accuracy are computed in aggregate and by score bucket, but not by sector.

**Optimized state:** Add sector dimension to:
- Signal accuracy (does scoring work better for Tech stocks than Healthcare?)
- Predictor hit rate (does the GBM predict Tech better than Financials?)
- Veto precision (are vetoes more reliable in certain sectors?)

**Implementation:** Join `score_performance` and `predictor_outcomes` with sector classification, group by sector, compute per-sector accuracy.

**Effort:** LOW (a few hours). Data and sector mapping already exist.

### GAP 4: No Confusion Matrix for Predictor (PRIORITY: LOW)

**Current state:** Predictor tracks hit rate (% correct) but doesn't distinguish UP→DOWN misclassification from UP→FLAT.

**Optimized state:** 3x3 confusion matrix (UP/FLAT/DOWN predicted vs actual), computed weekly. Reveals whether the model confuses flat with directional, or reverses direction.

**Implementation:** Build from `predictor_outcomes` table which has both predicted_direction and actual outcome.

**Effort:** LOW.

### GAP 5: Alpha Decomposition (PRIORITY: LOW, DEFERRED)

**Current state:** Total alpha is tracked but not decomposed into signal alpha + entry timing alpha + exit timing alpha + sizing alpha.

**Optimized state:** Each trade's alpha is attributed to the component that generated it. This is the gold-standard evaluation but requires counterfactual construction.

**Implementation:** For each roundtrip:
- Signal alpha = return if bought at signal price, sold at period end
- Entry timing alpha = (signal price - fill price) / signal price
- Exit timing alpha = (exit price - period-end price) / period-end price
- Sizing alpha = (weighted return - equal-weight return) for this position

**Effort:** HIGH. Requires careful counterfactual construction. Defer until 100+ roundtrips.

### GAP 6: Dashboard Doesn't Surface Full Backtester Report (PRIORITY: MEDIUM)

**Current state:** Dashboard shows signal accuracy trends, predictor metrics, portfolio performance, and some backtester results. But the full 25-section report (especially Phase 4 pipeline evaluation, trigger scorecards, shadow book, exit timing) is only in the markdown report on S3.

**Optimized state:** Dashboard surfaces:
- Report Card scorecard (Gap 1) on home page
- Per-team grades on Analysis page
- Full trigger scorecard on Execution page
- Shadow book results on Execution page
- Exit timing MFE/MAE on Execution page

**Effort:** MEDIUM (2-3 sessions). Data is on S3; need dashboard pages to fetch and display it.

### GAP 7: No Trend Analysis of Grades (PRIORITY: LOW)

**Current state:** Each report is a snapshot. No tracking of how each component's grade changes over time (is the CIO getting better or worse?).

**Optimized state:** Store weekly grades in a `component_grades` table or JSON history. Dashboard shows grade trend lines per component. Enables detecting degradation early.

**Effort:** LOW. Append each week's grades to a JSON file on S3.

---

## 7. Implementation Priority

| Priority | Gap | Description | Effort | Impact |
|----------|-----|-------------|--------|--------|
| P1 | Gap 1 | Unified scorecard with grades | LOW-MED | HIGH — immediate visibility into component health |
| P2 | Gap 2 | Precision/recall/F1 metrics | LOW | MEDIUM — standard ML evaluation framework |
| P2 | Gap 3 | Per-sector accuracy breakdown | LOW | MEDIUM — identifies sector-specific blind spots |
| P2 | Gap 6 | Dashboard surfacing of full report | MEDIUM | MEDIUM — makes evaluation accessible without reading markdown |
| P3 | Gap 4 | Confusion matrix for predictor | LOW | LOW — diagnostic, not actionable weekly |
| P3 | Gap 7 | Grade trend tracking | LOW | LOW — valuable long-term, not urgent |
| P4 | Gap 5 | Alpha decomposition | HIGH | LOW now — needs 100+ roundtrips to be meaningful |

---

## 8. Summary: What Already Works

The system evaluation is **~85% complete**. The backtester already:
- Computes accuracy, lift, and alpha metrics for every decision boundary
- Evaluates all 6 sector teams against their sector population
- Evaluates CIO selection vs ranking baseline
- Evaluates predictor veto precision and dollar value
- Evaluates entry trigger effectiveness
- Evaluates exit timing via MFE/MAE
- Evaluates risk guard via shadow book
- Evaluates position sizing via A/B comparison
- Auto-optimizes scoring weights, executor params, veto thresholds, trigger enables, team slots, CIO mode, and predictor sizing
- Produces a comprehensive weekly markdown report
- Runs automatically every Saturday in the Step Function pipeline

**The main gap is presentation** — converting existing metrics into an intuitive graded scorecard (Gap 1) and surfacing that on the dashboard (Gap 6). The underlying data and analysis infrastructure is mature.
