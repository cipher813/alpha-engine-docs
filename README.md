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

Plus two supporting repos: a public shared library [`alpha-engine-lib`](https://github.com/cipher813/alpha-engine-lib) (logging, freshness gates, trading-calendar arithmetic, ArcticDB helpers, agent decision capture, LLM cost tracking) used by all 6 modules, and a private [`alpha-engine-config`](https://github.com/cipher813/alpha-engine-config) repo holding proprietary scoring weights, agent prompts, model parameters, and other tuned values. Disclosure boundary: architecture and approach are public; specific weights, prompts, and thresholds are private.

## System architecture

Module-level data flow. Three Step Functions — Saturday, weekday morning, and EOD — orchestrate the modules; per-pipeline orchestration diagrams follow.

```mermaid
flowchart LR
    Data[Data<br/>prices · macro · features<br/>RAG corpus]
    Research[Research<br/>6 sector teams + CIO + macro economist<br/>incl. LLM-as-judge]
    Predictor[Predictor<br/>L1 momentum/vol GBMs + research calibrator<br/>+ L2 Ridge meta-learner]
    Executor[Executor<br/>risk-gated sizing + intraday daemon]
    Backtester[Backtester<br/>eval + parity + 4 config optimizers]
    Dashboard[Dashboard<br/>nousergon.ai + dashboard.nousergon.ai]

    Data --> Research
    Data --> Predictor
    Research --> Predictor
    Research --> Executor
    Predictor --> Executor
    Executor --> Backtester

    Backtester -.config auto-apply.-> Research
    Backtester -.config auto-apply.-> Predictor
    Backtester -.config auto-apply.-> Executor

    Data -.read-only.-> Dashboard
    Research -.read-only.-> Dashboard
    Predictor -.read-only.-> Dashboard
    Executor -.read-only.-> Dashboard
    Backtester -.read-only.-> Dashboard
```

### Saturday pipeline — `alpha-engine-saturday-pipeline`

EventBridge `cron(0 0 ? * SAT *)` — Sat 00:00 UTC (Fri 5–8 PM PT).

```mermaid
flowchart LR
    Trigger((Sat<br/>00:00 UTC)) --> P1
    P1[DataPhase1<br/>EC2 SSM<br/>30 min] --> RAG
    RAG[RAGIngestion<br/>EC2 SSM<br/>30 min] --> R
    R[Research<br/>Lambda · 15 min<br/><i>incl. LLM-as-judge</i>] --> P2
    P2[DataPhase2<br/>Lambda<br/>10 min] --> Train
    Train[PredictorTraining<br/>EC2 spot<br/>90 min] --> BT
    BT[Backtester<br/>EC2 spot · 120 min<br/><i>eval + parity + 4 config optimizers</i>] --> Notify((SNS))
```

### Weekday morning pipeline — `alpha-engine-weekday-pipeline`

EventBridge `cron(5 13 ? * MON-FRI *)` — 6:05 AM PT.

```mermaid
flowchart LR
    Trigger((6:05 AM PT)) --> Inf
    Inf[PredictorInference<br/>Lambda] --> Start
    Start[StartExecutorEC2] --> Boot
    Boot[Trading EC2 boots<br/>systemd] --> Plan
    Plan[Executor Planner<br/>~6:15 AM PT] --> Daemon((Executor Daemon<br/>~6:20 AM PT))
```

The daemon runs through the trading day, executing urgent exits at open and timing entries via intraday triggers (pullback, VWAP, support, time-expiry). Daemon shutdown after close (~1:15 PM PT) triggers the EOD pipeline.

### EOD pipeline — `alpha-engine-eod-pipeline`

Triggered by daemon shutdown — single authoritative path, no redundant cron.

```mermaid
flowchart LR
    Trigger((Daemon shutdown<br/>~1:15 PM PT)) --> Post
    Post[PostMarketData<br/>SSM on ae-trading<br/><i>EOD OHLCV → ArcticDB</i>] --> EOD
    EOD[EODReconcile<br/>NAV · α · positions<br/>trades.db + EOD email] --> Stop((StopTradingInstance))
```

## License

MIT — see [LICENSE](LICENSE).
