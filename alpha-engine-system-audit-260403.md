# Alpha Engine System Audit — 2026-04-03

**Scope:** Post-implementation audit after completing all 4 phases of the optimization roadmap in a single session.
**Purpose:** Verify system integrity and Saturday pipeline readiness.

---

## 1. Changes Made Today

### Phase 1: Critical Gaps
| Change | Repo | Files |
|--------|------|-------|
| Prediction quality circuit breaker | alpha-engine | `signal_generator.py`, `position_sizer.py` |
| Health checker bug fix + missing checks | alpha-engine-data | `health_checker.py` |
| GBM inference feature store read | alpha-engine-predictor | `inference/stages/run_inference.py` |
| Data repo test infrastructure | alpha-engine-data | `conftest.py`, `pyproject.toml`, 3 test files |
| Executor circuit breaker tests | alpha-engine | `tests/test_signal_generator.py` |

### Phase 2: High-Value Improvements
| Change | Repo | Files |
|--------|------|-------|
| GitHub Actions CI | All 6 repos | `.github/workflows/ci.yml` |
| Experiment tracking (git hash + hyperparams + JSONL history) | alpha-engine-predictor | `training/train_handler.py` |
| Structured JSON logging | alpha-engine | `executor/log_config.py`, `main.py`, `daemon.py`, `eod_reconcile.py` |
| Execution quality monitoring | alpha-engine | `executor/eod_reconcile.py` |

### Phase 3: Production Hardening
| Change | Repo | Files |
|--------|------|-------|
| trades.db WAL mode + mid-day backup | alpha-engine | `trade_logger.py`, `daemon.py` |
| pip-audit in CI | All 6 repos | `.github/workflows/ci.yml` |
| Emergency shutdown | alpha-engine | `emergency_shutdown.py`, `ibkr.py` |
| Drift detection | alpha-engine-predictor | `monitoring/drift_detector.py`, `train_handler.py` |
| Integration tests (contract validation) | alpha-engine-data | `tests/integration/test_data_contract_validation.py` |
| Live trading readiness checklist | alpha-engine-docs | `LIVE_TRADING_CHECKLIST.md` |
| Runbooks (10 failure modes) | alpha-engine-docs | `RUNBOOKS.md` |

### Phase 4: Scale & Polish
| Change | Repo | Files |
|--------|------|-------|
| Post-trade analysis | alpha-engine-backtester | `analysis/post_trade.py` |
| Monte Carlo validation | alpha-engine-backtester | `analysis/monte_carlo.py` |
| Shadow model opportunity note | alpha-engine-predictor | `README.md` |
| Real-time data opportunity note | alpha-engine | `CLAUDE.md` |
| Survivorship bias research | alpha-engine-docs | `survivorship-bias-research.md` |

### Step Function Updates
| Change | File |
|--------|------|
| Saturday: SaturdayHealthCheck + WaitForSaturdayHealthCheck (non-blocking) | `step_function.json` |
| Daily: HealthCheck + WaitForHealthCheck (non-blocking) | `step_function_daily.json` |

---

## 2. Code Audit Results

### alpha-engine (executor) — PASS
- `signal_generator.py`: Circuit breaker correctly integrated. Won't false-positive on normal predictions (needs >80% same direction OR stdev<0.01 confidence clustering). Falls back gracefully to research-only by emptying predictions dict.
- `position_sizer.py`: Bounds clamping on `prediction_confidence` and `p_up` correctly guards against None (checks `is not None` before clamping).
- `daemon.py`: Mid-day backup uses `_ET` (pytz) consistently, not ZoneInfo. `db_path` and `config["signals_bucket"]` are in scope. `global _midday_backup_done` declared correctly.
- `trade_logger.py`: WAL PRAGMA is before `executescript()`. Correct ordering.
- `eod_reconcile.py`: Execution quality SQL references valid columns (trigger_type, slippage_vs_signal, execution_latency_ms, signal_price, fill_price). `json` and `boto3` both imported.
- `log_config.py`: Imports work correctly from all three entry points (main, daemon, eod).
- `emergency_shutdown.py`: Paper account safety check (account ID must start with "D") is correct. Uses clientId=3 to avoid conflicts.
- `ibkr.py`: `cancel_all_orders()` and `get_open_orders()` properly indented inside IBKRClient class.

### alpha-engine-predictor — PASS
- `run_inference.py`: GBM feature store uses `precomputed_gbm` (distinct from meta inference's `precomputed`). No variable collision. Inline fallback preserved. Logging metrics correct.
- `train_handler.py`: `_code_commit` captured before training, in scope at summary write. JSONL history append has correct nested try/except. Feature stats export writes mean/std arrays for drift detection.
- `monitoring/drift_detector.py`: Imports are standard library + boto3 + numpy + pandas. No exotic dependencies.

### alpha-engine-data — PASS
- `health_checker.py`: SNS bug fixed (dead `boto3.client("s3")` removed). New checks for `price_cache_slim` and `daily_closes` use correct S3 key patterns. Variable `today_str_dc` is distinct from `today_str`.
- Step Function JSONs: Both validate as correct JSON. All states have valid Next/End. All Catch blocks point to valid states. No orphaned states. Health checks are non-blocking (Catch → continue pipeline).

---

## 3. Test Results

| Repo | Tests | Result |
|------|-------|--------|
| alpha-engine | 131 | **131 passed** |
| alpha-engine-data | 29 | **29 passed** |
| alpha-engine-predictor | 135 | **135 passed, 18 warnings** (sklearn matmul warnings in calibrator tests — pre-existing, harmless) |
| alpha-engine-backtester | 63 | **59 passed, 4 failed** (pre-existing — see below) |

### Pre-existing backtester failures (NOT caused by today's changes)
- `test_price_loader.py::TestBuildMatrix::test_ffill_limited_to_5_days` — forward-fill assertion mismatch
- `test_veto_analysis.py` (3 tests) — S3 AccessDenied in test that attempts live S3 listing; assertion mismatch on "no_predictions" vs "no_down_predictions"

These failures exist on the current main branch and are unrelated to Phase 4 changes (post_trade.py and monte_carlo.py are new modules not imported by any existing tests).

---

## 4. Saturday Pipeline Readiness

### Pipeline Flow
```
DataPhase1 (EC2 SSM) → WaitForDataPhase1 → CheckDataPhase1Status
  → RAGIngestion (EC2 SSM) → WaitForRAGIngestion → CheckRAGStatus
  → Research (Lambda) → CheckResearchStatus
  → DataPhase2 (Lambda)
  → PredictorTraining (EC2 spot) → WaitForPredictorTraining → CheckPredictorStatus
  → Backtester (EC2 spot) → WaitForBacktester → CheckBacktesterStatus
  → SaturdayHealthCheck (EC2 SSM) → WaitForSaturdayHealthCheck   [NEW]
  → NotifyComplete (SNS)
```

### Verification Checklist

| Check | Status | Notes |
|-------|--------|-------|
| Step Function JSON valid | PASS | Both Saturday and daily parse correctly |
| Health check non-blocking | PASS | Catch → NotifyComplete (Saturday) / StartExecutorEC2 (daily) |
| Health checker EC2-compatible | PASS | Only needs boto3 (installed) + standard library |
| Feature store compute in pipeline | N/A | Not in Saturday pipeline — daily pipeline computes features. Saturday training uses price cache directly. GBM inference has inline fallback. |
| SNS alerts configured | PASS | Default topic ARN hardcoded, `SNS_TOPIC_ARN` env var override |
| Predictor training changes safe | PASS | Git hash capture, feature stats export, JSONL history are all non-blocking with try/except |

### Deployment Required Before Saturday

**IMPORTANT: Step Function definitions are local JSON files. They must be deployed to AWS before the Saturday run picks up the health check changes.**

To deploy:
1. Copy `step_function.json` content → AWS Step Functions console → alpha-engine-saturday-pipeline → Edit → paste → Save
2. Copy `step_function_daily.json` content → AWS Step Functions console → alpha-engine-weekday-pipeline → Edit → paste → Save

Alternatively, use AWS CLI:
```bash
export PATH="/opt/homebrew/bin:$PATH"
aws stepfunctions update-state-machine \
  --state-machine-arn arn:aws:states:us-east-1:711398986525:stateMachine:alpha-engine-saturday-pipeline \
  --definition file://alpha-engine-data/infrastructure/step_function.json \
  --query "updateDate" --output text

aws stepfunctions update-state-machine \
  --state-machine-arn arn:aws:states:us-east-1:711398986525:stateMachine:alpha-engine-weekday-pipeline \
  --definition file://alpha-engine-data/infrastructure/step_function_daily.json \
  --query "updateDate" --output text
```

### Commits Required Before Saturday

All changes are uncommitted. Each repo needs:
1. `git add` the specific files (not `git add .` — avoid committing local artifacts)
2. `git commit`
3. `git push origin main`
4. EC2 deployment: `ae "cd ~/alpha-engine && git pull"` (trading instance pulls on boot)
5. Micro instance: `aem "cd ~/alpha-engine-data && git pull"`

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Health checker fails on Saturday (boto3 import, S3 access) | Low | None — non-blocking, pipeline continues | Catch → NotifyComplete |
| Circuit breaker false positive on real predictions | Very Low | Medium — one day of research-only trading | 80% threshold is very conservative; validated against test data |
| GBM feature store empty on daily inference | Medium (first run) | None — falls back to inline compute with warning | Inline fallback preserved; monitor logs for "GBM features: N from store, M from inline" |
| WAL mode incompatible with EC2 SQLite version | Very Low | Low — WAL is supported since SQLite 3.7.0 (2010) | EC2 Amazon Linux has SQLite 3.40+ |
| Structured logging breaks log parsing | Low | Low — only activates with ALPHA_ENGINE_JSON_LOGS=1 env var | Default is text mode (unchanged behavior). Must explicitly enable JSON on EC2. |
| Daemon mid-day backup fails | Low | None — try/except, logs warning, continues trading | Backup is non-blocking |

---

## 6. Items Not Deployed to Production Yet

These changes are implemented locally but need commit + push + EC2 pull before they take effect:

1. **Circuit breaker** — protects against degenerate predictions (executor)
2. **Health check scheduling** — Step Function updates (needs AWS console/CLI deploy)
3. **WAL mode** — protects trades.db against corruption (executor)
4. **Mid-day backup** — noon ET backup of trades.db (daemon)
5. **Structured logging** — JSON logging when ALPHA_ENGINE_JSON_LOGS=1 (executor)
6. **Execution quality** — daily slippage analysis written to S3 (executor EOD)
7. **GBM feature store read** — inference reads from store first (predictor)
8. **Experiment tracking** — git hash + hyperparams + JSONL history (predictor training)
9. **Drift detection** — feature + prediction drift module (predictor, not yet scheduled)
10. **Emergency shutdown** — new script (executor, manual use)

---

## 7. Post-Deploy Monitoring

After Saturday pipeline completes, verify:

1. **Health check ran:** Check Step Function execution graph for SaturdayHealthCheck step (green = passed, orange = failed but continued)
2. **SNS alert:** If any checks were stale, an SNS email should arrive
3. **Training summary:** Check `s3://alpha-engine-research/predictor/metrics/training_summary_latest.json` for new `code_commit` and `hyperparameters` fields
4. **Training history:** Check `s3://alpha-engine-research/predictor/training_logs/history.jsonl` exists with at least one line
5. **Feature stats:** Check `s3://alpha-engine-research/predictor/metrics/training_feature_stats.json` exists (needed for drift detection)

On Monday morning (first daily pipeline after deploy):
6. **GBM feature store:** Check inference logs for `GBM feature store: loaded N pre-computed tickers`
7. **Circuit breaker:** Check executor logs — should NOT trigger on normal predictions
8. **Execution quality:** After EOD, check `s3://alpha-engine-research/trades/execution_quality/{date}.json` exists
9. **WAL mode:** On trading instance, verify `PRAGMA journal_mode` returns `wal`:
   ```bash
   ae "sqlite3 ~/alpha-engine/trades.db 'PRAGMA journal_mode;'"
   ```
