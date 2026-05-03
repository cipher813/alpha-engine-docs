# README Template — Per-Module Public Repo

Canonical README structure for every public alpha-engine repo. Apply consistently — recruiters skimming the org page should see seven cards that visibly belong together.

> Per the presentation-revamp plan §1.1. Companion: [`OVERVIEW_TEMPLATE.md`](OVERVIEW_TEMPLATE.md) for the comprehensive per-repo code tour.

---

## Zones of responsibility — what lives where

Module READMEs are **module-only content**. System-level content lives in `alpha-engine-docs/README.md`; live performance and detailed prose live on `nousergon.ai`. The same fact should not appear in two places — instead, link to the canonical home.

| Content | `alpha-engine-docs` | This module's repo | `nousergon.ai` |
|---|:---:|:---:|:---:|
| System architecture diagram (all 6 modules) | ✅ canonical | ❌ — link out | ✅ /architecture |
| Saturday + weekday Step Function pipelines | ✅ canonical | ❌ — link out | ✅ /architecture |
| Phase trajectory (Phase 1/2/3/4 status) | ✅ canonical | ❌ — banner badge only | ✅ home page |
| 4-capability narrative ("What this is") | ✅ canonical | ❌ | ✅ home page |
| Modules table (all 6 modules described) | ✅ canonical | ❌ — sister-repos minimal links only | ✅ home page |
| Autonomous feedback loop (cross-module) | ✅ canonical | ❌ — link out | ✅ /architecture |
| Headline metrics, live alpha curve | ❌ — link only | ❌ | ✅ canonical (/metrics) |
| Public retros / postmortems | ❌ — link only | ❌ — link out | ✅ canonical (/retros) |
| Blog posts | ❌ — link only | ❌ | ✅ canonical (/blog) |
| **Module's role + Today + Where it's headed** | ✅ row in modules table | ✅ canonical (in this README) | ✅ /Docs page |
| Module-internal architecture diagram | ❌ | ✅ canonical | ✅ /Docs page |
| Module's key files annotated | ❌ | ✅ canonical (here + OVERVIEW.md) | ❌ |
| Quick start / running locally | ❌ | ✅ canonical | ❌ |
| Module's deployment + schedule | ❌ | ✅ canonical | ❌ |
| Module's configuration | ❌ | ✅ canonical | ❌ |
| Module's failure modes + retros | ❌ — covered in docs cross-cutting | ✅ canonical | ✅ /retros |
| Brand banner (one-line disambiguation) | ✅ verbatim | ✅ verbatim | ✅ implicit |
| License (MIT) | ✅ | ✅ | (footer) |

**Rule of thumb:** if a recruiter who's already read `alpha-engine-docs/README.md` and `nousergon.ai` would learn nothing new from a section in your module README, drop or compress that section. Each surface should answer the *next* question the prior one prompted.

**Specifically do NOT duplicate from `alpha-engine-docs`:**
- The Phase trajectory table (use the Phase 2 badge instead)
- The full Modules table with all 6 module descriptions (use a minimal Sister Repos links table)
- The full system architecture mermaid (use a hero diagram that highlights *this* module's role only)
- The Saturday/weekday SF pipeline flowcharts (link out)
- The autonomous feedback loop table (link out)

---

## Section order (locked)

1. **H1 title** — repo name (`alpha-engine-<module>`)
2. **Brand banner** — copy from [`../branding/brand_banner.md`](../branding/brand_banner.md)
3. **Badge bar** — copy from [`../branding/badge_bar.md`](../branding/badge_bar.md)
4. **One-line module statement** — what this module does in one sentence
5. **Hero diagram** — mermaid showing this module's role in the larger system, this module highlighted
6. **What this does** (3–5 bullets) — concrete capabilities
7. **Phase 2 measurement contribution** — what this module *measures* and why that matters for Phase 3 alpha tuning
8. **Architecture** — module-internal mermaid diagram
9. **Key files to read** — 5–7 annotated links (summary; comprehensive list lives in `OVERVIEW.md`)
10. **How it runs** — deployment target, trigger, schedule
11. **Configuration** — what's local, what's in `alpha-engine-config` (private)
12. **Failure modes + retros** — links to public retros that touched this module
13. **Sister repos** — table linking all 6 module repos with one-line roles
14. **License + contact** — MIT, link to LICENSE, contact for inquiries

---

## Boilerplate (copy-paste, fill in `<>` placeholders)

```markdown
# alpha-engine-<module>

> Part of [**Nous Ergon**](https://nousergon.ai) — Autonomous Multi-Agent Trading System. Repo and S3 names use the underlying project name `alpha-engine`.

[![Part of Nous Ergon](https://img.shields.io/badge/Part_of-Nous_Ergon-1a73e8?style=flat-square)](https://nousergon.ai)
[![CI](https://img.shields.io/github/actions/workflow/status/cipher813/alpha-engine-<module>/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/cipher813/alpha-engine-<module>/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/dynamic/json?url=https://raw.githubusercontent.com/cipher813/alpha-engine-<module>/main/.github/badges/tests.json&query=$.message&label=tests&style=flat-square&color=brightgreen)](https://github.com/cipher813/alpha-engine-<module>/actions)
[![Python](https://img.shields.io/badge/python-3.13+-blue?style=flat-square)](https://www.python.org/)
<!-- 2-3 stack badges per branding/badge_bar.md -->
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)
[![Phase 2 · Reliability](https://img.shields.io/badge/Phase_2-Reliability-e9c46a?style=flat-square)](https://github.com/cipher813/alpha-engine-docs#phase-trajectory)

<ONE-LINE MODULE STATEMENT — what this module does in one sentence.>

## System role

```mermaid
flowchart LR
    Data[alpha-engine-data] --> Research[alpha-engine-research]
    Research --> Predictor[alpha-engine-predictor]
    Predictor --> Executor[alpha-engine]
    Executor --> Backtester[alpha-engine-backtester]
    Backtester -.config feedback.-> Research
    Backtester -.config feedback.-> Predictor
    Backtester -.config feedback.-> Executor
    Dashboard[alpha-engine-dashboard] -.read-only.-> Data & Research & Predictor & Executor & Backtester

    classDef highlight fill:#1a73e8,color:#fff,stroke:#0e1117,stroke-width:2px
    class <THIS_MODULE> highlight
```

## What this does

- <Bullet 1 — concrete capability>
- <Bullet 2>
- <Bullet 3>
- <Bullet 4 (optional)>
- <Bullet 5 (optional)>

## Phase 2 measurement contribution

This module's role in Phase 2 (Reliability Buildout): <what it measures, what telemetry it emits, why that matters for Phase 3 alpha tuning>.

> Phase 2 thesis: before you can systematically generate alpha, you need to systematically measure every component. This module's measurements are part of that substrate. Phase 3 (parameter tuning toward alpha) operates on this foundation.

## Architecture

```mermaid
<MODULE-INTERNAL DIAGRAM — state machine, data flow, or component graph>
```

<1-paragraph design-rationale note explaining a key trade-off taken — interviewers love this.>

## Key files

If you only read 5–7 files, read these. Comprehensive code tour in [OVERVIEW.md](OVERVIEW.md).

| File | What it does |
|---|---|
| [`<file1>`](<path>) | <One-line purpose> |
| [`<file2>`](<path>) | <One-line purpose> |
| [`<file3>`](<path>) | <One-line purpose> |
| [`<file4>`](<path>) | <One-line purpose> |
| [`<file5>`](<path>) | <One-line purpose> |

## How it runs

- **Deployment target:** <Lambda / EC2 / EC2 spot / always-on EC2>
- **Trigger:** <Step Function step / EventBridge / systemd / SSM RunCommand>
- **Schedule:** <cron / on-event / on-boot>
- **Local run:** <command>

## Configuration

`config.yaml` is gitignored. Real values live in the private [`alpha-engine-config`](https://github.com/cipher813/alpha-engine-config) repo (proprietary scoring weights, prompts, model parameters). Local development copies `config.yaml.example`.

Environment variables: see [`config.yaml.example`](config.yaml.example).

## Failure modes + retros

This module has been through <N> production incidents. Public postmortems on the [Nous Ergon retros page](https://nousergon.ai/retros):
- <Date — incident summary> → <link>
- <Date — incident summary> → <link>

Phase 2 receipt: every incident closes with a systemic fix, not a workaround.

## Sister repos

| Module | Repo | Role |
|---|---|---|
| Data | [`alpha-engine-data`](https://github.com/cipher813/alpha-engine-data) | Centralized data + feature store |
| Research | [`alpha-engine-research`](https://github.com/cipher813/alpha-engine-research) | Multi-agent investment research |
| Predictor | [`alpha-engine-predictor`](https://github.com/cipher813/alpha-engine-predictor) | Stacked meta-ensemble (L1 GBMs + L2 Ridge) |
| Executor | [`alpha-engine`](https://github.com/cipher813/alpha-engine) | Risk-gated sizing + intraday execution |
| Backtester | [`alpha-engine-backtester`](https://github.com/cipher813/alpha-engine-backtester) | Signal quality + autonomous param optimization |
| Dashboard | [`alpha-engine-dashboard`](https://github.com/cipher813/alpha-engine-dashboard) | Read-only Streamlit monitoring |
| Docs | [`alpha-engine-docs`](https://github.com/cipher813/alpha-engine-docs) | System overview + this template |

## License

MIT — see [LICENSE](LICENSE).

## Contact

This is a portfolio project — issues + PRs not actively monitored. For inquiries: see contact on [nousergon.ai](https://nousergon.ai).
```

---

## Notes on applying this template

- **Don't paraphrase the brand banner** — copy verbatim from `../branding/brand_banner.md`
- **Don't reorder the section order** — recruiters reading multiple repos benefit from visual consistency
- **The hero mermaid diagram is the same across all 6 module repos** — only the highlighted module changes. Copy-paste, change the `class` line.
- **Mermaid renders natively on GitHub** — no external tooling needed
- **Phase 2 measurement contribution paragraph** is mandatory — it ties the repo back to the central narrative
- **For repos with substantial private config dependencies** (e.g., `alpha-engine-research` with prompt loaders), make the proprietary boundary explicit in the Configuration section
