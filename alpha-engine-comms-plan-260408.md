# Alpha Engine: Communications & Documentation Audit

**Date:** 2026-04-08
**Scope:** 7 public repos, nousergon.ai website (Hugo blog + public Streamlit app), cross-referencing strategy

---

## 1. Current State

### 1A. Repository READMEs

| Repo | Lines | Quality | Has Diagram | Has Quick Start | Has Badges | Has TOC |
|------|-------|---------|-------------|-----------------|------------|---------|
| alpha-engine (executor) | ~470 | Excellent | 3 diagrams | Yes | No | No |
| alpha-engine-research | ~450 | Excellent | Yes | Yes | No | No |
| alpha-engine-predictor | ~365 | Excellent | Yes | Yes | No | No |
| alpha-engine-backtester | ~370 | Excellent | Yes | Yes | No | No |
| alpha-engine-dashboard | ~210 | Good | No | Yes | No | No |
| alpha-engine-data | **Missing** | N/A | N/A | N/A | N/A | N/A |
| alpha-engine-docs | **Missing** | N/A | N/A | N/A | N/A | N/A |

**Strengths:**
- 5 of 7 repos have professional, detailed READMEs
- Consistent "Role in the System" framing across modules
- Cross-references between repos via "Related Modules" sections
- Honest "Opportunities for Improvement" sections
- S3 data contracts and deployment procedures documented

**Weaknesses:**
- No badges (build status, Python version, license)
- No table of contents on 300+ line READMEs
- 2 repos (data, docs) have no README at all
- No CONTRIBUTING.md in any repo
- No CHANGELOG.md in any repo
- Executor README doubles as system overview, creating role confusion
- "Opportunities" sections mix active work with long-term aspirational items
- No standardized template — consistency is emergent, not enforced

### 1B. Supplementary Docs

| Repo | CLAUDE.md | DOCS.md | docs/ folder | LICENSE |
|------|-----------|---------|--------------|--------|
| executor | Yes | Yes | No | MIT |
| research | Yes | Yes | No | MIT |
| predictor | Yes | No | Yes (4 files) | MIT |
| backtester | Yes | Yes | No | MIT |
| dashboard | No | No | Yes (2 files) | MIT |
| data | Yes | No | No | MIT |
| docs | No | No | No | MIT |

CLAUDE.md files are gitignored (internal dev instructions). DOCS.md files exist in 3 repos but serve different purposes. The predictor has the most structured docs/ folder (architecture.md, deployment.md, training.md, inference.md).

### 1C. Website (nousergon.ai)

**Blog (Hugo + PaperMod theme):**
- Post 1 published (2026-03-15): "Building an Autonomous Alpha Engine with AI"
- Post 2 published (2026-03-27): "Multi-Agent Research: How 6 LLM Teams Analyze 900 Stocks"
- 8 additional posts planned (Posts 3-10) on a bi-weekly cadence through July 2026

**Public dashboard (Streamlit):**
- Built but deployment status unclear
- Shows: NAV vs SPY, cumulative alpha, current holdings
- Data scope: read-only from eod_pnl.csv

**Public docs (Streamlit, /Docs page):**
11 polished markdown docs served via a dedicated Docs page with selectbox navigation and deep-linking:

| Doc | Topic | Lines | Quality |
|-----|-------|-------|---------|
| overview.md | System architecture, 5-module pipeline | 65 | Polished |
| data_dictionary.md | All inter-module data schemas (research.db, trades.db, S3 JSON/CSV) | 352 | Polished |
| research.md | Research module overview, scanner, sector teams | 111 | Polished |
| research_architecture.md | LangGraph StateGraph topology, node pipeline | 123 | Polished |
| research_agents.md | ReAct pattern, @tool decorator, reasoning loop | 173 | Polished |
| research_langgraph.md | Why LangGraph, typed state, parallel execution | 188 | Polished |
| research_rag.md | RAG pattern, pgvector, SEC filings, semantic search | 161 | Polished |
| predictor.md | LightGBM model, veto gate, IC metric | 103 | Polished |
| executor.md | Morning planner, daemon, risk guardrails | 114 | Polished |
| backtester.md | Signal quality, param sweeps, auto-apply | 98 | Polished |
| dashboard.md | Streamlit pages, caching, Cloudflare Access | 95 | Polished |

These are reader-friendly adaptations of the README content — no quickstart/config/deploy, focused on architecture and "how it works." Each includes an "Alpha contribution" statement explaining the module's role in generating alpha.

**Domain:** nousergon.ai via Cloudflare

### 1D. Cross-Referencing

Current cross-referencing is repo-to-repo via markdown links in "Related Modules" sections. The website docs pages exist but don't link back to the specific GitHub repos. READMEs don't link to the website docs. Blog posts reference the system conceptually but don't link to specific repo documentation or website docs pages.

---

## 2. Optimized State

### 2A. Documentation Architecture

Three tiers of documentation, each serving a different audience:

```
Tier 1: Website (nousergon.ai)              Audience: Public / recruiters / investors
  Blog posts (narrative, bi-weekly)
  Public dashboard (live performance)
  System overview (architecture, philosophy)
  
Tier 2: Repo READMEs                        Audience: Engineers / contributors / interviewers
  Standardized template per module
  Quick start → architecture → config → deploy
  Links up to Tier 1 (website) and across to sibling repos
  
Tier 3: Deep Reference                      Audience: Active developers / maintainers
  docs/ folders (architecture, deployment, API reference)
  CLAUDE.md (dev instructions, gitignored)
  Private docs (ROADMAP.md, SYSTEM-OPTIMIZED.md)
```

**Cross-referencing strategy:**

```
nousergon.ai/blog   ←→  nousergon.ai/docs   ←→  GitHub repos
     ↑                        ↑                       ↑
  Narrative              System docs              Code + README
  (why, story)         (how, reference)        (what, quickstart)
```

Every piece of documentation should link to its adjacent tier:
- Blog posts link to the relevant repo README for technical depth
- Repo READMEs link to the website for the narrative context
- docs/ folders link to both README (overview) and CLAUDE.md (dev workflow)

### 2B. Standardized README Template

Every module README follows this template:

```markdown
# alpha-engine-{module}

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)]()

> One-sentence role statement: what this module does and how it contributes to alpha.

**Part of the [Nous Ergon](https://nousergon.ai) autonomous trading system.**
See the [system overview](https://github.com/cipher813/alpha-engine#readme) for how all modules connect.

## Table of Contents
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
- [Key Files](#key-files)
- [Deployment](#deployment)
- [Testing](#testing)
- [S3 Contract](#s3-contract)
- [Related Modules](#related-modules)

## Architecture
ASCII or Mermaid diagram showing this module's data flow.

## Quick Start
### Prerequisites
### Setup
### First Run

## How It Works
2-3 sections explaining the core logic. This is the "teach someone" section.

## Configuration
Table of config keys, defaults, and descriptions. Reference config.yaml.example.

## Key Files
Table mapping file paths to responsibilities.

## Deployment
### Lambda / EC2 / Spot Instance
### Rollback

## Testing
```bash
pytest tests/ -v
```

## S3 Contract
### Reads
### Writes
Table of S3 paths this module reads from and writes to, with JSON schema summaries.

## Related Modules
Links to all sibling repos with one-line descriptions.

## License
MIT — see [LICENSE](LICENSE)
```

**Key differences from current state:**
- Badges at the top (professional signal)
- Table of contents for navigation
- Explicit "Part of Nous Ergon" branding with link to website
- System overview always points to the executor repo README (canonical system doc)
- S3 Contract section makes inter-module dependencies explicit and visible
- No "Opportunities" section in README (move to GitHub Issues or private ROADMAP)

### 2C. Two-Tier System Documentation (Hybrid Approach)

The executor repo README currently serves double duty: system overview + executor-specific docs (~470 lines). The optimized state splits this across two repos:

**alpha-engine (executor) README — Concise system overview + executor docs:**

The executor README keeps a *trimmed* system overview (~100 lines) at the top — just enough to orient someone who lands on the repo — then transitions to executor-specific documentation. The system overview section includes:
- System architecture diagram (the main pipeline ASCII art)
- Module table with one-line descriptions and GitHub links
- S3 layout (the inter-module contract)
- Key metrics table
- Link to alpha-engine-docs for the full documentation index

The detailed module descriptions (currently ~200 lines describing all 5 other modules) are *removed* from the executor README. Each module's own README now owns its description.

```
# Alpha Engine

> Autonomous equity portfolio — LLM research + GBM predictions + quantitative execution.

**[Nous Ergon](https://nousergon.ai)** | [Full Documentation](https://github.com/cipher813/alpha-engine-docs#readme) | [Blog](https://nousergon.ai/blog)

## System Architecture
[Trimmed pipeline diagram]

## Modules
| Module | Repo | Role |
[6-row table with links]

## S3 Layout
[Existing S3 tree — this is the canonical source]

## Key Metrics
[Existing metrics table]

---

# Executor

> Reads signals and predictions, applies risk rules, sizes positions, executes orders.

[Standard module template from here down: TOC, Architecture, Quick Start, How It Works, ...]
```

**alpha-engine-docs README — Full documentation index:**

The docs repo README becomes the comprehensive navigation hub — the place that links *everything* together. It provides:
- System architecture summary with link to executor README for the canonical diagram
- Module table with links to each repo AND to website /docs pages
- Blog post index with links to nousergon.ai/blog
- Audit history index (links to audit docs in this repo)
- Link to nousergon.ai for the public-facing narrative

This is where someone goes to understand the *full system documentation landscape* — which repo to read for what, where the website fits in, where the blog posts are.

```
# Alpha Engine Documentation

> Central index for the [Nous Ergon](https://nousergon.ai) autonomous trading system.

## System Overview
Architecture diagram and description. For the canonical S3 layout and pipeline
details, see the [system README](https://github.com/cipher813/alpha-engine#readme).

## Modules
| Module | GitHub | Website Docs | Role |
|--------|--------|--------------|------|
| Research | [repo](link) | [docs](link) | Signal generation |
| Predictor | [repo](link) | [docs](link) | ML prediction + veto |
| Executor | [repo](link) | [docs](link) | Position management |
| Backtester | [repo](link) | [docs](link) | System learning |
| Dashboard | [repo](link) | [docs](link) | Monitoring |
| Data | [repo](link) | [docs](link) | Centralized data |

## Blog Posts
| # | Title | Date | Topic |
[Index of published + planned posts]

## System Audits
| Date | Audit | Focus |
[Index of audit docs in this repo]

## Operational Docs
- [Deployment Runbooks](RUNBOOKS.md)
- [Live Trading Checklist](LIVE_TRADING_CHECKLIST.md)
```

**Why this hybrid works:**
- GitHub visitors landing on the executor repo get immediate system context without leaving
- The docs repo serves as the "table of contents" for the entire project
- The website (nousergon.ai) is the presentation layer, not the source of truth
- No documentation lives in only one place — repos are authoritative, website adapts, docs repo indexes

### 2D. Website Content Architecture

The website docs section **already exists** with 11 polished pages (see 1C above). The optimized state retains all existing pages and extends them:

```
nousergon.ai/
├── /                    Landing page: tagline, NAV chart, latest blog post
├── /dashboard           Public Streamlit: NAV vs SPY, alpha, holdings
├── /blog                Hugo blog: narrative posts (bi-weekly)
├── /Docs                Streamlit docs viewer (EXISTING, 11 pages):
│   ├── Overview         System architecture, module pipeline
│   ├── Data Dictionary  All inter-module schemas (research.db, trades.db, S3)
│   ├── Research (5)     Main + Architecture + Agents + LangGraph + RAG
│   ├── Predictor        LightGBM, veto gate, features
│   ├── Executor         Morning planner, daemon, risk guardrails
│   ├── Backtester       Signal quality, param optimization, auto-apply
│   ├── Dashboard        Streamlit pages, caching, auth
│   ├── Data (NEW)       ArcticDB, fetchers, data pipeline
│   └── Evaluation (NEW) System report card methodology, grading approach
└── /About               About the project, author, philosophy
```

**What to add:**
- **Data module page** — ArcticDB migration, fetcher architecture, data pipeline role (missing since alpha-engine-data is newer)
- **Evaluation page** — system report card methodology, how each component is graded, what precision/recall/F1 mean in this context (from today's eval work)
- **Cross-links** — each doc page should link to its GitHub repo README for quickstart/config/deploy details
- **"Last updated" timestamps** — so readers know if docs are current

**What to keep as-is:**
- All 11 existing docs are polished and current — no rewrites needed
- Data dictionary is especially valuable as the cross-module schema reference
- Research deep-dives (architecture, agents, LangGraph, RAG) are unique to the website

The docs pages are the **Tier 1 presentation layer** — reader-friendly, narrative, no developer setup instructions. They link down to GitHub READMEs (Tier 2) for technical detail, and the READMEs link up to these pages for narrative context.

### 2E. alpha-engine-docs README

Defined in 2C above. The docs repo README is the **full documentation index** — the single page that maps out everything: repos, website, blog, audits, runbooks. It links to the executor README for the canonical system architecture and S3 layout, and to each module repo for technical detail.

### 2F. alpha-engine-data README

Currently missing. Should follow the standard template:

```markdown
# alpha-engine-data

> Centralized data collection, storage, and distribution for the Alpha Engine system.
> Owns price data (ArcticDB), macro indicators, and alternative data fetchers.
> Runs as the first step in both Saturday and daily Step Function pipelines.
```

---

## 3. Gap Analysis

### Gap 1: Missing READMEs (HIGH priority)

| Repo | Status | Effort |
|------|--------|--------|
| alpha-engine-data | No README | LOW — follow template, document fetchers + ArcticDB |
| alpha-engine-docs | No README | LOW — create navigation index |

### Gap 2: No Badges (MEDIUM priority)

None of the 7 repos have badges. Adding Python version, license, and test status badges to every README is a small change with high professional signal.

**Effort:** LOW (15 min per repo)

### Gap 3: No Table of Contents (MEDIUM priority)

READMEs over 300 lines (executor, research, predictor, backtester) need a TOC for navigation. GitHub renders markdown TOC links natively.

**Effort:** LOW (10 min per repo)

### Gap 4: No Explicit S3 Contract Section (MEDIUM priority)

The S3 layout is documented in the executor README and CLAUDE.md but not in each module's README. Each module should have a concise "S3 Contract" section listing what it reads and writes.

**Effort:** LOW (20 min per repo — data already in CLAUDE.md)

### Gap 5: Executor README Role Confusion (HIGH priority)

The executor README is ~470 lines and serves as both system overview and executor docs. Per the hybrid approach (Section 2C), the system overview stays in the executor README but is trimmed to ~100 lines (diagram + module table + S3 layout + metrics). The ~200 lines of detailed module descriptions are removed — each module's own README now owns its description. A clear `---` separator divides system overview from executor-specific docs.

**Effort:** MEDIUM (1 hour — trim system overview, move module descriptions, restructure with separator)

### Gap 6: Website Docs Missing Data + Evaluation Pages (LOW priority)

The /Docs section already exists with 11 polished pages. Two gaps: no page for the alpha-engine-data module (newer repo) and no page for the evaluation/grading system (built today). Existing pages also lack cross-links back to GitHub repos.

**Effort:** LOW (1 hour — write 2 new markdown files, add repo links to existing pages)

### Gap 7: No Repo-to-Website Cross-Linking (LOW priority)

READMEs don't link to nousergon.ai. Website doesn't deep-link to repos. Adding "Part of Nous Ergon" to each README and repo links to the website closes the loop.

**Effort:** LOW (5 min per repo)

### Gap 8: Stale Content in READMEs and Website Docs (HIGH priority)

All 5 existing READMEs were last updated 2026-04-04. Major system changes since then (ArcticDB, config repo, SSM secrets, VWAP trigger, EOD pipeline, evaluation framework) are not reflected. 6 of 11 website docs pages are partially or fully stale.

**Reference documents for content updates:**
- `alpha-engine-system-docs-260408.md` — **Canonical current-state reference** (1,508 lines). All content updates should be validated against this document for accuracy. It covers all 6 modules with architecture, schemas, S3 paths, config, and deployment — updated to reflect every change through 2026-04-08.
- `alpha-engine-system-audit-260408.md` Section 4 — **Stale docs inventory** itemizing exactly what's stale in each README and website doc, categorized as HIGH/MEDIUM/Missing.

**Process:** When restructuring any README or website doc, pull the updated content from `system-docs-260408.md` rather than writing from scratch. This ensures consistency across all documentation surfaces.

**Effort:** MEDIUM (must be done during Phase 1-3 — update content while restructuring format)

### Gap 9: "Opportunities" Sections Are Stale (LOW priority)

Several READMEs have "Opportunities for Improvement" or "Deferred Opportunities" sections that mix completed work with aspirational items. These should be pruned — completed items removed, active items moved to GitHub Issues, long-term items kept in private ROADMAP.md only.

**Effort:** LOW-MEDIUM (30 min per repo to audit and clean)

### Gap 10: No CONTRIBUTING.md (LOW priority)

No repo has a standalone contributing guide. For a public project seeking community engagement, this signals openness. Even a minimal one ("this is a personal project, PRs welcome for bugs, open an issue first for features") sets expectations.

**Effort:** LOW (create one template, copy to all repos)

### Gap 11: Blog Posts 3-10 Not Published (ONGOING)

2 of 10 planned posts are published. The remaining 8 cover scoring, ML prediction, backtesting, execution, RAG, reliability, MCP, and lessons learned. These are on a bi-weekly cadence through July 2026.

**Effort:** HIGH (each post is 2-3K words, requires research + writing)

---

## 4. Implementation Plan

### Phase 1: Structure + Content Update (1-2 sessions)

**Source of truth for all content updates:** `alpha-engine-system-docs-260408.md` (1,508-line current-state reference). Pull architecture diagrams, S3 paths, schemas, and config details from this doc — don't write from memory.

**Stale item inventory:** `alpha-engine-system-audit-260408.md` Section 4 lists every stale item per document.

**Repo structure:**
1. **Restructure executor README** — trim system overview to ~100 lines (diagram, module table, S3 layout, metrics), remove detailed module descriptions, add `---` separator, apply standard template to executor section below. Update for: ArcticDB, config repo, SSM secrets, VWAP fix, graduated expiry, EOD Step Function. Source: system-docs sections 2.8, 3.6, 3.10, Orchestration, Deployment.
2. **Create alpha-engine-docs README** — full documentation index (system overview link, module table with repo + website links, blog post index, audit history index, runbook links)
3. **Create alpha-engine-data README** — standard module template. Source: system-docs sections 6.1-6.7.

**Content updates (while restructuring — validate each against system-docs-260408):**
4. **Update backtester README** — add evaluation framework (grades, P/R/F1, confusion matrix, structured JSON output), update report description, update test count (189). Source: system-docs sections 4.4, 4.8, 4.9 (new), 4.11.
5. **Update predictor README** — add v3.0 meta-model, feedback loop, drift detection, health check Lambda. Source: system-docs sections 2.2, 2.8.
6. **Update dashboard README** — add report card, execution evaluation tab, system health enhancements. Source: system-docs section 5.4.
7. **Update research README** — config repo loading path. Source: system-docs Deployment section.
8. **Update executor README** (as part of restructure) — VWAP trigger, graduated expiry, EOD pipeline, SSM secrets. Source: system-docs sections 3.6, 3.10, Deployment.

### Phase 2: Polish (1 session)
9. Add badges to all 7 READMEs (Python version, License, Tests)
10. Add TOC to 4 long READMEs (executor, research, predictor, backtester)
11. Add "Part of Nous Ergon" branding + links to website and docs repo in all READMEs
12. Add S3 Contract section (Reads/Writes) to each module README
13. Prune stale "Opportunities" sections — remove completed items, move active to GitHub Issues
14. Create minimal CONTRIBUTING.md template, deploy to all repos

### Phase 3: Website Docs (1 session — most content already exists)

**Source of truth:** `alpha-engine-system-docs-260408.md`. Adapt content for a public audience (strip quickstart/config/deploy, keep architecture and "how it works").

**New pages:**
15. Write data module docs page (public/docs/data.md) — ArcticDB, fetchers, pipeline role. Source: system-docs sections 6.1-6.5.
16. Write evaluation docs page (public/docs/evaluation.md) — report card methodology, grading, P/R/F1. Source: system-docs section 4.9.
17. Register new pages in the Docs page section registry (public/pages/2_Docs.py)

**Stale page updates (validate against system-docs-260408):**
18. Update overview.md — add 6th module (data), ArcticDB, evaluation framework, EOD pipeline. Source: system-docs Orchestration + S3 Layout.
19. Update data_dictionary.md — ArcticDB tables, new evaluation tables, updated schema fields. Source: system-docs sections 2.8, 4.9, S3 Layout.
20. Update predictor.md — meta-model, drift detection, health check. Source: system-docs sections 2.2, 2.8.
21. Update executor.md — VWAP trigger, graduated expiry, EOD pipeline. Source: system-docs sections 3.6, 3.10.
22. Update backtester.md — evaluation framework, grades, structured JSON. Source: system-docs sections 4.4, 4.8, 4.9.
23. Update dashboard.md — report card, execution evaluation, system health. Source: system-docs section 5.4.

**Cross-linking:**
24. Add GitHub repo links to all 13 docs pages
25. Add "Last updated" timestamps to all docs pages

### Phase 4: Ongoing
26. Continue blog post series (Posts 3-10 on bi-weekly cadence)
27. Update website docs pages when major features ship
28. Keep READMEs current with each PR
29. Keep alpha-engine-docs README index current when repos or blog posts change
