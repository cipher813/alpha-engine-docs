# OVERVIEW.md Template — Per-Module Code Tour

Canonical structure for each public alpha-engine repo's `OVERVIEW.md` — the comprehensive annotated code tour an interviewer reads before asking deep questions.

> Per the presentation-revamp plan §1.2. **Goal: comprehensive coverage of the repo's substantive code, not a top-5 list.** Readers navigate by tier; comprehensive is fine.

**Length:** 5–15 pages is appropriate. Use `<details>` blocks for Tier 3 / Tier 4 to keep the page scannable.

---

## Section order (locked across all 6 module repos)

1. Module purpose (2 sentences)
2. Phase context — what this module measures and why that matters for Phase 3
3. Architecture diagram (more detailed than README's)
4. **Tier 1 — Critical path files** (3–7 files, deep annotation)
5. **Tier 2 — Substantive supporting code** (grouped by purpose)
6. **Tier 3 — Infrastructure and glue** (collapsed by category)
7. **Tier 4 — Tests and fixtures** (layout + conventions)
8. Data contracts (S3 paths, JSON schemas, ArcticDB libraries, SQLite tables)
9. Configuration (local vs `alpha-engine-config`)
10. Deployment
11. Failure modes + retros
12. Measurement surfaces (Phase 2 framing — what telemetry this module emits, where to find it on the dashboard, what each surface proves)
13. Next-question pointers — anticipates the interviewer's next 5–10 questions

---

## Tier definitions

- **Tier 1 — Critical path (must-read).** The 3–7 files that define the module's core behavior. If an interviewer reads only these, they understand what the module does and how. Annotated heavily: file path · key function names with line ranges · what to notice · trade-offs taken · why this design.
- **Tier 2 — Substantive supporting code.** Files that implement secondary but important behavior — risk gates, feature engineering, data adapters, scoring helpers, retry logic, etc. Annotated lightly: file path · one-paragraph purpose · 2–3 key functions called out by name.
- **Tier 3 — Infrastructure and glue.** Config loaders, S3 helpers, logging, utility modules, prompt loaders, deployment scripts, IAM helpers. Annotated minimally: file path · one-line purpose. Grouped by category. **Collapsed by default.**
- **Tier 4 — Tests and fixtures.** Test layout (e.g., `tests/unit/`, `tests/integration/`, fixture conventions, replay-based LLM testing pattern). Surface this as evidence of testing discipline; don't enumerate every test file. **Collapsed by default.**

---

## Boilerplate (copy-paste, fill in `<>` placeholders)

```markdown
# alpha-engine-<module> — Code Tour

> Comprehensive annotated tour of this repo's substantive code. Companion to [README.md](README.md). Readers navigate by tier — Tier 1 is must-read, Tiers 3–4 are collapsed by default.
>
> Last reviewed: <YYYY-MM-DD>

## Module purpose

<Two sentences: what this module does, why it exists in the larger system.>

## Phase context

This module's Phase 2 contribution: <what it measures · what telemetry it emits · why that's load-bearing for Phase 3 alpha tuning>.

## Architecture

```mermaid
<MORE-DETAILED MODULE-INTERNAL DIAGRAM than the one in README.md — full state machine / data flow / component graph>
```

<1–2 paragraphs of design rationale. What trade-offs were taken. What was considered and rejected.>

---

## Tier 1 — Critical path files

If you only read these, you understand the module.

### [`<file1.py>`](<path>) — <one-line purpose>

**Key functions:**
- [`<function_name>`](<path#L<start>-L<end>>) — <what it does, what to notice>
- [`<function_name>`](<path#L<start>-L<end>>) — <what it does, what to notice>

**Trade-offs taken:**
- <Decision and rationale — interviewer-grade explanation>

**What to notice:**
- <Subtle invariant, edge case, or non-obvious design>

### [`<file2.py>`](<path>) — <one-line purpose>

<Same structure.>

<!-- Repeat for 3–7 files total -->

---

## Tier 2 — Substantive supporting code

Grouped by purpose.

### Risk and sizing
- [`<file>`](<path>) — <paragraph on what this implements; key functions: `<fn1>`, `<fn2>`, `<fn3>`>
- [`<file>`](<path>) — <paragraph; key functions>

### Data ingestion
- [`<file>`](<path>) — <paragraph; key functions>

### Scoring + composition
- [`<file>`](<path>) — <paragraph; key functions>

### Persistence
- [`<file>`](<path>) — <paragraph; key functions>

<!-- Adjust group headings per repo. Each group: 1-5 files. -->

---

## Tier 3 — Infrastructure and glue

<details>
<summary>Configuration + secrets</summary>

- [`<file>`](<path>) — <one-line purpose>
- [`<file>`](<path>) — <one-line purpose>

</details>

<details>
<summary>S3 + storage helpers</summary>

- [`<file>`](<path>) — <one-line purpose>
- [`<file>`](<path>) — <one-line purpose>

</details>

<details>
<summary>Logging + observability</summary>

- [`<file>`](<path>) — <one-line purpose>

</details>

<details>
<summary>Deployment + IAM</summary>

- [`<file>`](<path>) — <one-line purpose>

</details>

<details>
<summary>Utilities</summary>

- [`<file>`](<path>) — <one-line purpose>

</details>

---

## Tier 4 — Tests and fixtures

<details>
<summary>Test layout</summary>

- `tests/unit/` — <count> tests, scope: <pure-function unit tests>
- `tests/integration/` — <count> tests, scope: <S3-roundtrip, DB writes, etc.>
- `tests/replay/` — <count> tests, scope: <LLM fixture replay if applicable>
- Total test surface: <count>

**Conventions:**
- <Fixture pattern, e.g., "all LLM responses replayed from `tests/fixtures/llm/`">
- <Coverage targets, marker conventions>

</details>

---

## Data contracts

### Reads
| Source | Path / location | Format | Used for |
|---|---|---|---|
| <Source> | <path> | <format> | <use> |

### Writes
| Destination | Path / location | Format | Schema |
|---|---|---|---|
| <Dest> | <path> | <format> | <schema link> |

### Schemas
- [`<schema_name>`](<path or link>) — <one-line description>

## Configuration

### Local (`config.yaml` — gitignored)
<What's here, why it's local.>

### Private repo (`alpha-engine-config`)
<What's there: prompts, weights, scoring params, etc.>

### Environment variables
<List of env vars + what they're for. Never include actual values.>

## Deployment

- **Target:** <Lambda / EC2 / spot>
- **Trigger:** <SF step name / EventBridge / systemd>
- **Schedule:** <cron / on-event>
- **Deploy mechanism:** <`deploy.sh` / `git pull` on boot / etc.>
- **Local run:** <command>
- **Dry run:** <command>

## Failure modes + retros

This module has been through <N> production incidents. Each retro: symptoms → root cause → fix → systemic improvement.

| Date | Incident | Public retro |
|---|---|---|
| <YYYY-MM-DD> | <One-line summary> | <link to /retros> |

## Measurement surfaces

What telemetry this module emits — Phase 2 receipts.

| Surface | What it proves | Where to find it |
|---|---|---|
| <Log line / S3 artifact / SQLite table> | <What this proves about the system> | <Dashboard page or path> |

## Next-question pointers

Anticipated interviewer questions and where to look:

- *"How does <X> work?"* → start with [`<file>`](<path>); then read [`<file>`](<path>).
- *"What happens when <edge case>?"* → see [`<file:line>`](<path#L>) — handled by `<function>`.
- *"Why <design choice X> instead of <Y>?"* → see [Architecture](#architecture) trade-off paragraph; deeper retro at <link>.
- *"How is <Y> tested?"* → [Tier 4 — Tests](#tier-4--tests-and-fixtures).
- *"What's the failure mode if <Z>?"* → [Failure modes + retros](#failure-modes--retros).
```

---

## Notes on applying this template

- **Comprehensive, not exhaustive.** Tier 3 and Tier 4 are collapsed; readers can pick depth. Don't enumerate every test file by name; describe layout and conventions.
- **Tier assignment is editorial.** A file isn't Tier 1 because it's long; it's Tier 1 because reading it teaches the module's core behavior. Be opinionated.
- **Cite specific line ranges** in Tier 1 where helpful — `path#L42-L78`. Costs nothing to write, lets the reader jump straight to the substance.
- **Trade-offs sections are interviewer catnip.** Even one well-written trade-off note per Tier 1 file is more valuable than a paragraph of generic description.
- **Phase 2 framing in the Phase context section is mandatory** — same as README. Ties the document back to the central narrative.
- **Keep it current.** When code shifts substantially, update OVERVIEW.md in the same PR.
