# Alpha Engine Documentation

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Central documentation index for the [Nous Ergon](https://nousergon.ai) autonomous trading system.

**[Website](https://nousergon.ai)** | **[Blog](https://nousergon.ai/blog)** | **[System Overview](https://github.com/cipher813/alpha-engine#readme)**

## System Overview

Architecture diagram and canonical S3 layout live in the [system README](https://github.com/cipher813/alpha-engine#system-architecture). Six modules run on AWS, connected through a shared S3 bucket, orchestrated by Step Functions.

## Modules

| Module | GitHub | Website Docs | Role |
|--------|--------|--------------|------|
| Research | [alpha-engine-research](https://github.com/cipher813/alpha-engine-research) | [Docs](https://nousergon.ai) | 6 LLM sector teams + CIO → composite scores → signals.json |
| Predictor | [alpha-engine-predictor](https://github.com/cipher813/alpha-engine-predictor) | [Docs](https://nousergon.ai) | Meta-model (4 GBMs + ridge) → 5d alpha predictions + veto gate |
| Executor | [alpha-engine](https://github.com/cipher813/alpha-engine) | [Docs](https://nousergon.ai) | Risk rules, position sizing, technical entry triggers, trailing stops |
| Backtester | [alpha-engine-backtester](https://github.com/cipher813/alpha-engine-backtester) | [Docs](https://nousergon.ai) | Weekly evaluation (grades, P/R/F1) + 6 autonomous optimizers |
| Dashboard | [alpha-engine-dashboard](https://github.com/cipher813/alpha-engine-dashboard) | [Docs](https://nousergon.ai) | Streamlit monitoring: portfolio, signals, system report card |
| Data | [alpha-engine-data](https://github.com/cipher813/alpha-engine-data) | [Docs](https://nousergon.ai) | Centralized data: ArcticDB prices, macro, alternative data |

## Blog Posts

| # | Title | Date | Topic |
|---|-------|------|-------|
| 1 | [Building an Autonomous Alpha Engine with AI](https://nousergon.ai/blog/building-autonomous-alpha-engine) | 2026-03-15 | System overview, 3-layer architecture |
| 2 | [Multi-Agent Research: How 6 LLM Teams Analyze 900 Stocks](https://nousergon.ai/blog/multi-agent-research) | 2026-03-27 | ReAct agents, RAG, sector specialization |

## System Audits

| Date | Audit | Focus |
|------|-------|-------|
| 2026-04-08 | [System Audit](alpha-engine-system-audit-260408.md) | Full state assessment, 704 tests, 94% maturity |
| 2026-04-08 | [System Docs](alpha-engine-system-docs-260408.md) | Comprehensive technical reference (1,508 lines) |
| 2026-04-08 | [Evaluation Plan](alpha-engine-system-plan-eval-260408.md) | Component grading methodology |
| 2026-04-08 | [Comms Plan](alpha-engine-comms-plan-260408.md) | Documentation restructure plan |
| 2026-04-04 | [System Audit](alpha-engine-system-audit-260404.md) | Post-hardening baseline |

## Operational Docs

- [Deployment Runbooks](RUNBOOKS.md)
- [Live Trading Checklist](LIVE_TRADING_CHECKLIST.md)

## License

MIT — see [LICENSE](LICENSE).
