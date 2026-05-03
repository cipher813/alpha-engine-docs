# Nous Ergon — Alpha Engine

> Part of [**Nous Ergon**](https://nousergon.ai) — Autonomous Multi-Agent Trading System. Repo and S3 names use the underlying project name `alpha-engine`.

[![Part of Nous Ergon](https://img.shields.io/badge/Part_of-Nous_Ergon-1a73e8?style=flat-square)](https://nousergon.ai)
[![Changelog](https://img.shields.io/github/actions/workflow/status/cipher813/alpha-engine-docs/aggregate-changelog-weekly.yml?branch=main&style=flat-square&label=changelog)](https://github.com/cipher813/alpha-engine-docs/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)
[![Phase 2 · Reliability](https://img.shields.io/badge/Phase_2-Reliability-e9c46a?style=flat-square)](#phase-trajectory)

System-overview entry point. Detailed module documentation, blog posts, the live dashboard, and metrics validation live on the public site.

**[nousergon.ai](https://nousergon.ai)** · **[Blog](https://nousergon.ai/blog)** · **[Modules](#modules)** · **[Architecture](#system-architecture)**

---

## What this is

A multi-agent orchestration system that researches, decides, and acts — and measures and tunes itself in the process. Equities trading is the substrate: a domain where decisions are unambiguous, outcomes are continuously verifiable, and agentic behavior is observable end-to-end.

Four capabilities define the system:

- **Multi-agent orchestration** — six LangGraph sector teams, a CIO, and a macro economist scan the S&P 500+400 (~900 stocks) weekly. Each sector team runs a quant ReAct → qual ReAct → peer review flow before submitting 2–3 recommendations. The CIO gates new entrants per a configurable cap. Outputs at key stages are evaluated by a rubric-based LLM-as-judge layer.
- **Stacked meta-ensemble prediction** — three specialized Layer-1 models (LightGBM momentum, LightGBM volatility, and a research-score calibrator) feed a Layer-2 Ridge meta-learner alongside research-context and raw macro features. Predictions flow into a downstream risk-gated executor.
- **Autonomous self-improvement** — a backtester evaluates the system's own outputs each week, runs parameter sweeps, and writes four optimized configs back to S3. Research, predictor, and executor read those configs on cold-start; the system retunes itself weekly without manual intervention.
- **End-to-end measurement substrate** — signals are persisted to `research.db` and `signals.json`, predictions to `predictions/{date}.json`, fills to a SQLite trade log backed up to S3, and daily P&L to `eod_pnl.csv`. The presentation layer is a view, not a measurement layer; numbers source from existing module outputs.

The substrate is equities; the pattern is general. The orchestration, measurement, and learning loops apply anywhere multi-agent collaboration and durable instrumentation matter.

## Phase trajectory

| Phase | Focus | Status |
|---|---|---|
| **Phase 1** | Build the system end-to-end | ✅ Complete — 6 repos, full pipeline running |
| **Phase 2** | Reliability + measurement buildout | 🟡 **Current** — incident retros, SF hardening, observability, autonomous feedback loop |
| **Phase 3** | Parameter tuning toward alpha | ⏳ Next — backtester→config feedback loop already wired |
| **Phase 4** | Live capital | ⏳ Gated on Phase 3 sustained outperformance |

The presentation layer leads with reliability and measurement, not returns. Long-term alpha — portfolio return minus SPY, risk-adjusted — is the metric Phase 3 is engineered to inflect.

## Modules

| Module | Repo | Today | Where it's headed |
|---|---|---|---|
| **Data** | [`alpha-engine-data`](https://github.com/cipher813/alpha-engine-data) | ~50 features × ~900 tickers × 10y in ArcticDB; weekly refresh | Broader alternative-data, options-derived, and sentiment coverage; drift-monitored per feature group; sub-daily refresh where signal warrants it |
| **Research** | [`alpha-engine-research`](https://github.com/cipher813/alpha-engine-research) | 6 sector teams + CIO + macro economist; weekly scan; rubric-based LLM-as-judge on key stages | Higher-cadence research (toward daily); broader judge rubric coverage with two-tier orchestration; conviction-driven mid-week rebalancing |
| **Predictor** | [`alpha-engine-predictor`](https://github.com/cipher813/alpha-engine-predictor) | Layer-1 LightGBM momentum + LightGBM volatility + research-score calibrator → Layer-2 Ridge meta-learner; 21 features in production inference | Research-score calibrator promoted from lookup table to a GBM; regime model returns as a real model once it clears its named baseline; broader feature breadth in inference toward the ~50-feature store universe |
| **Executor** | [`alpha-engine`](https://github.com/cipher813/alpha-engine) | Risk-gated paper trading via IB Gateway; 4 entry-trigger types; ATR trailing stops | Live capital (Phase 4); portfolio-level risk overlays beyond per-position gates; tax-aware position management |
| **Backtester** | [`alpha-engine-backtester`](https://github.com/cipher813/alpha-engine-backtester) | Weekly evaluator + autonomous optimizers writing 4 configs to S3 (scoring weights, executor params, predictor veto, research params) | Deeper attribution showing which signal sources actually drive returns; regime-conditional config sets; more frequent retuning cadence as data accrues |
| **Dashboard** | [`alpha-engine-dashboard`](https://github.com/cipher813/alpha-engine-dashboard) | Read-only Streamlit; portfolio, signals, predictor, retros — powers nousergon.ai (public) and dashboard.nousergon.ai (private, Cloudflare Access) | Signal lifecycle view; feedback-loop visualization; feature store + RAG inventory; `/metrics` validation page |

Plus a private [`alpha-engine-config`](https://github.com/cipher813/alpha-engine-config) repo holding proprietary scoring weights, agent prompts, model parameters, and other tuned values. Disclosure boundary: architecture and approach are public; specific weights / prompts / thresholds are private.

## System architecture

```mermaid
flowchart LR
    subgraph WEEKLY[Saturday Step Function]
        Data1[Data: prices · macro · universe · feature store]
        RAG[RAG Ingestion]
        Research[Research: 6 sector teams + CIO]
        Data2[Data: alternative data]
        Train[Predictor Training: L1 momentum + vol GBMs + research calibrator + L2 Ridge]
        Backtest[Backtester: evaluator + optimizers]
    end

    subgraph DAILY[Weekday Step Function]
        DailyData[Daily Data: closes · macro refresh · feature compute]
        Inference[Predictor Inference]
        Plan[Executor Planner]
        Daemon[Executor Daemon]
        EOD[EOD Reconcile]
    end

    Data1 --> RAG --> Research --> Data2 --> Train --> Backtest
    Backtest -.config auto-apply.-> Research
    Backtest -.config auto-apply.-> Train
    Backtest -.config auto-apply.-> Plan

    DailyData --> Inference --> Plan --> Daemon --> EOD

    Research --> Inference
    EOD --> Backtest

    Dashboard[Dashboard: nousergon.ai + dashboard.nousergon.ai]
    Data1 -.read-only.-> Dashboard
    Research -.read-only.-> Dashboard
    Inference -.read-only.-> Dashboard
    EOD -.read-only.-> Dashboard
    Backtest -.read-only.-> Dashboard
```

### Saturday pipeline — `alpha-engine-saturday-pipeline`

EventBridge `cron(0 0 ? * SAT *)` — Sat 00:00 UTC (Fri 5–8 PM PT).

```mermaid
flowchart LR
    Trigger((Sat<br/>00:00 UTC)) --> P1
    P1[DataPhase1<br/>EC2 SSM<br/>30 min] --> RAG
    RAG[RAGIngestion<br/>EC2 SSM<br/>30 min] --> R
    R[Research<br/>Lambda<br/>15 min] --> P2
    P2[DataPhase2<br/>Lambda<br/>10 min] --> Train
    Train[PredictorTraining<br/>EC2 spot<br/>90 min] --> BT
    BT[Backtester<br/>EC2 spot<br/>120 min] --> Notify((SNS))
```

### Weekday pipeline — `alpha-engine-weekday-pipeline`

EventBridge `cron(5 13 ? * MON-FRI *)` — 6:05 AM PT.

```mermaid
flowchart LR
    Trigger((6:05 AM PT)) --> DD
    DD[DailyData<br/>EC2 SSM] --> Inf
    Inf[PredictorInference<br/>Lambda] --> Start
    Start[StartExecutorEC2] --> EX
    EX[Executor Planner<br/>6:25 AM PT] --> DM
    DM[Executor Daemon<br/>6:30 AM PT] --> Reconcile
    Reconcile[EOD Reconcile<br/>1:20 PM PT] --> Stop((Stop EC2<br/>1:30 PM PT))
```

### Autonomous feedback loop

The backtester is the system's learning mechanism. Each week it analyzes signal accuracy, runs param sweeps, and auto-applies optimized configs to S3 for downstream modules to read on cold-start.

| Config | Read by | Optimizer |
|---|---|---|
| `config/scoring_weights.json` | Research | Weight optimizer (data-driven scoring weight recommendations) |
| `config/executor_params.json` | Executor | 60-trial random search over 6 risk params, ranked by Sharpe |
| `config/predictor_params.json` | Predictor | Veto threshold auto-tune |
| `config/research_params.json` | Research | Signal boost params (deferred until 200+ samples) |

Fully autonomous, no manual intervention required. This is the substrate Phase 3 alpha tuning operates on.

## License

MIT — see [LICENSE](LICENSE).
