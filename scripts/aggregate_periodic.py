#!/usr/bin/env python3
"""Weekly + monthly rollup aggregator for the system-wide changelog.

PR 5 of the schema-discipline arc (ROADMAP > Observability >
"System-wide changelog: schema discipline + artifact linking +
aggregation layer", sub-item 4). Reads the structured corpus at
s3://alpha-engine-research/changelog/entries/ + writes period-scoped
rollups (JSON + Markdown) to s3://.../changelog/aggregates/{period_type}/.

Daily Markdown summary already exists (alpha-engine-docs#5 —
aggregate-changelog.yml). This script adds the next two granularities:
weekly (Monday cron) + monthly (1st-of-month cron). The daily renderer
is the operator's "what shipped yesterday"; weekly + monthly answer
"what trends are forming" + power the future Streamlit dashboard +
external portfolio narrative.

JSON shape (schema 1.0.0):
    period_type:    "weekly" | "monthly"
    period_id:      "2026-W18" | "2026-05"
    period_start:   "2026-04-27"          (inclusive, UTC)
    period_end:     "2026-05-03"          (inclusive, UTC)
    generated_at:   "2026-05-04T07:00:00Z"
    entry_count:    87
    by_event_type:  {"change": 65, "incident": 18, ...}
    by_subsystem:   {"infrastructure": 32, ...}
    by_severity:    {"high": 8, ...}                    (incidents only)
    by_root_cause_category: {"infrastructure_failure": 12, ...}
    by_resolution_type:     {"code_fix": 50, ...}
    incidents: {
        count, with_root_cause_pct,
        mttd_seconds_mean, mttd_seconds_p50, mttd_seconds_p95,
        mttr_seconds_mean, mttr_seconds_p50, mttr_seconds_p95
    }
    open_issues:    [{event_id, summary, age_days}, ...]   (started_at populated, resolved_at null)
    deltas_vs_prior: {entry_count, incident_count, mttr_mean_seconds}

Self-contained on stdlib + the `aws` CLI subprocess (no boto3 dep).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
DEFAULT_BUCKET = "alpha-engine-research"
ENTRIES_PREFIX = "changelog/entries"
AGGREGATES_PREFIX = "changelog/aggregates"


# -------------------- period helpers --------------------------------

def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def weekly_period(reference: date) -> tuple[date, date, str]:
    """Return (start, end, period_id) for the ISO week containing `reference`.

    Rollup runs on Mondays — the period is the prior 7 days (Mon→Sun
    of last week). period_id is ISO week format `YYYY-Www`.
    """
    # Find last Monday strictly before the reference.
    days_since_mon = (reference.weekday() - 0) % 7
    if days_since_mon == 0:
        # If reference is Monday, treat as "last week" → Mon a week ago.
        last_mon = reference - timedelta(days=7)
    else:
        last_mon = reference - timedelta(days=days_since_mon)
    start = last_mon
    end = start + timedelta(days=6)
    iso_year, iso_week, _ = start.isocalendar()
    period_id = f"{iso_year}-W{iso_week:02d}"
    return start, end, period_id


def monthly_period(reference: date) -> tuple[date, date, str]:
    """Return (start, end, period_id) for the calendar month BEFORE `reference`.

    Rollup runs on the 1st — period is the entire prior month. period_id
    is `YYYY-MM`.
    """
    if reference.day == 1:
        anchor = reference
    else:
        # Generated mid-month — still report on prior month.
        anchor = reference.replace(day=1)
    # Move one day back to land in the prior month.
    last_of_prior = anchor - timedelta(days=1)
    start = last_of_prior.replace(day=1)
    end = last_of_prior
    period_id = f"{start.year}-{start.month:02d}"
    return start, end, period_id


def prior_period(period_type: str, start: date) -> tuple[date, date, str]:
    """Period preceding `start` (same length, immediately before)."""
    if period_type == "weekly":
        prior_end = start - timedelta(days=1)
        prior_start = prior_end - timedelta(days=6)
        iso_year, iso_week, _ = prior_start.isocalendar()
        return prior_start, prior_end, f"{iso_year}-W{iso_week:02d}"
    elif period_type == "monthly":
        prior_anchor = (start - timedelta(days=1)).replace(day=1)
        # Find last day of that prior month
        if prior_anchor.month == 12:
            after = prior_anchor.replace(year=prior_anchor.year + 1, month=1)
        else:
            after = prior_anchor.replace(month=prior_anchor.month + 1)
        prior_end = after - timedelta(days=1)
        return prior_anchor, prior_end, f"{prior_anchor.year}-{prior_anchor.month:02d}"
    else:
        raise ValueError(f"unknown period_type: {period_type}")


# -------------------- S3 helpers (subprocess, no boto3) --------------

def _aws_s3_sync(bucket: str, prefix: str, dest: Path) -> None:
    """Sync entries under `bucket/prefix` to local `dest`."""
    proc = subprocess.run(
        ["aws", "s3", "sync", f"s3://{bucket}/{prefix}", str(dest), "--quiet"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"ERROR: aws s3 sync failed (exit {proc.returncode})")


def _aws_s3_put(bucket: str, key: str, body: bytes, content_type: str) -> None:
    proc = subprocess.run(
        ["aws", "s3", "cp", "-", f"s3://{bucket}/{key}", "--content-type", content_type],
        input=body,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr.decode("utf-8", errors="replace"))
        raise SystemExit(f"ERROR: aws s3 cp (write) failed for {key}")


# -------------------- corpus loading ---------------------------------

def load_entries_in_range(
    corpus_dir: Path,
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    """Load all structured entries with ts_utc dates in [start, end]."""
    out: list[dict[str, Any]] = []
    for path in sorted(corpus_dir.glob("**/*.json")):
        try:
            with path.open() as f:
                e = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        ts = e.get("ts_utc", "")
        if not ts:
            continue
        try:
            d = date.fromisoformat(ts[:10])
        except ValueError:
            continue
        if start <= d <= end:
            out.append(e)
    return out


# -------------------- rollup math ------------------------------------

def _parse_iso_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _percentile(values: list[float], pct: float) -> float | None:
    """Return the percentile (0..100). None if values empty."""
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    sorted_v = sorted(values)
    rank = pct / 100.0 * (len(sorted_v) - 1)
    lo, hi = int(math.floor(rank)), int(math.ceil(rank))
    if lo == hi:
        return sorted_v[lo]
    frac = rank - lo
    return sorted_v[lo] * (1 - frac) + sorted_v[hi] * frac


def compute_rollup(
    entries: list[dict[str, Any]],
    *,
    period_type: str,
    period_id: str,
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    counts: dict[str, dict[str, int]] = {
        "by_event_type": {},
        "by_subsystem": {},
        "by_severity": {},
        "by_root_cause_category": {},
        "by_resolution_type": {},
    }

    incidents = [e for e in entries if e.get("event_type") == "incident"]
    mttd_secs: list[float] = []
    mttr_secs: list[float] = []
    with_root_cause = 0

    for e in entries:
        for field, bucket in [
            ("event_type", "by_event_type"),
            ("subsystem", "by_subsystem"),
            ("severity", "by_severity"),
            ("root_cause_category", "by_root_cause_category"),
            ("resolution_type", "by_resolution_type"),
        ]:
            v = e.get(field)
            if v:
                counts[bucket][v] = counts[bucket].get(v, 0) + 1

    for inc in incidents:
        if inc.get("root_cause_category"):
            with_root_cause += 1
        started = _parse_iso_utc(inc.get("started_at"))
        detected = _parse_iso_utc(inc.get("detected_at"))
        resolved = _parse_iso_utc(inc.get("resolved_at"))
        if started and detected and detected >= started:
            mttd_secs.append((detected - started).total_seconds())
        if detected and resolved and resolved >= detected:
            mttr_secs.append((resolved - detected).total_seconds())

    open_issues: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for e in entries:
        started = _parse_iso_utc(e.get("started_at"))
        resolved = _parse_iso_utc(e.get("resolved_at"))
        if started and not resolved:
            age = (now - started).total_seconds() / 86400.0
            open_issues.append(
                {
                    "event_id": e.get("event_id", ""),
                    "summary": (e.get("summary") or "")[:160],
                    "age_days": round(age, 2),
                }
            )
    open_issues.sort(key=lambda x: x["age_days"], reverse=True)
    open_issues = open_issues[:10]

    return {
        "schema_version": SCHEMA_VERSION,
        "period_type": period_type,
        "period_id": period_id,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entry_count": len(entries),
        **counts,
        "incidents": {
            "count": len(incidents),
            "with_root_cause_pct": (
                round(with_root_cause / len(incidents) * 100.0, 1)
                if incidents
                else None
            ),
            "mttd_seconds_mean": round(statistics.fmean(mttd_secs), 1) if mttd_secs else None,
            "mttd_seconds_p50": _percentile(mttd_secs, 50),
            "mttd_seconds_p95": _percentile(mttd_secs, 95),
            "mttr_seconds_mean": round(statistics.fmean(mttr_secs), 1) if mttr_secs else None,
            "mttr_seconds_p50": _percentile(mttr_secs, 50),
            "mttr_seconds_p95": _percentile(mttr_secs, 95),
        },
        "open_issues": open_issues,
    }


def add_deltas(rollup: dict[str, Any], prior: dict[str, Any] | None) -> dict[str, Any]:
    if prior is None:
        rollup["deltas_vs_prior"] = None
        return rollup
    rollup["deltas_vs_prior"] = {
        "prior_period_id": prior.get("period_id"),
        "entry_count_delta": rollup["entry_count"] - prior.get("entry_count", 0),
        "incident_count_delta": rollup["incidents"]["count"]
        - prior.get("incidents", {}).get("count", 0),
        "mttr_seconds_mean_delta": _safe_delta(
            rollup["incidents"].get("mttr_seconds_mean"),
            prior.get("incidents", {}).get("mttr_seconds_mean"),
        ),
    }
    return rollup


def _safe_delta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return round(a - b, 1)


# -------------------- markdown render --------------------------------

def render_markdown(rollup: dict[str, Any]) -> str:
    p = rollup
    lines: list[str] = []
    lines.append(
        f"# Changelog rollup — {p['period_type']} {p['period_id']}"
    )
    lines.append("")
    lines.append(
        f"_Range: {p['period_start']} → {p['period_end']} (UTC, inclusive)._  "
    )
    lines.append(f"_Generated: {p['generated_at']}._  ")
    lines.append(
        f"_Entries: {p['entry_count']} · Incidents: {p['incidents']['count']}._"
    )
    lines.append("")

    if p.get("deltas_vs_prior"):
        d = p["deltas_vs_prior"]
        delta_line = (
            f"vs `{d['prior_period_id']}`: entries {_signed(d['entry_count_delta'])}"
            f", incidents {_signed(d['incident_count_delta'])}"
        )
        if d.get("mttr_seconds_mean_delta") is not None:
            delta_line += f", MTTR {_signed(d['mttr_seconds_mean_delta'])}s"
        lines.append(f"**Trend:** {delta_line}")
        lines.append("")

    def render_counter(title: str, key: str) -> None:
        c = p[key]
        if not c:
            return
        lines.append(f"## {title}")
        lines.append("")
        for k, n in sorted(c.items(), key=lambda x: -x[1]):
            lines.append(f"- `{k}`: **{n}**")
        lines.append("")

    render_counter("By event type", "by_event_type")
    render_counter("By subsystem", "by_subsystem")
    render_counter("By severity (incidents)", "by_severity")
    render_counter("By root cause category", "by_root_cause_category")
    render_counter("By resolution type", "by_resolution_type")

    inc = p["incidents"]
    if inc["count"]:
        lines.append("## Incident metrics")
        lines.append("")
        lines.append(
            f"- count: **{inc['count']}**, with `root_cause_category`: **{inc['with_root_cause_pct']}%**"
        )
        if inc["mttd_seconds_mean"] is not None:
            lines.append(
                f"- MTTD (start → detect): mean **{_fmt_secs(inc['mttd_seconds_mean'])}** "
                f"(p50 {_fmt_secs(inc['mttd_seconds_p50'])}, p95 {_fmt_secs(inc['mttd_seconds_p95'])})"
            )
        if inc["mttr_seconds_mean"] is not None:
            lines.append(
                f"- MTTR (detect → resolve): mean **{_fmt_secs(inc['mttr_seconds_mean'])}** "
                f"(p50 {_fmt_secs(inc['mttr_seconds_p50'])}, p95 {_fmt_secs(inc['mttr_seconds_p95'])})"
            )
        lines.append("")

    if p["open_issues"]:
        lines.append("## Longest-lived open issues")
        lines.append("")
        for oi in p["open_issues"]:
            lines.append(
                f"- `{oi['age_days']}d` — {oi['summary']}  "
                f"<sub>`event_id={oi['event_id']}`</sub>"
            )
        lines.append("")

    return "\n".join(lines)


def _signed(n: float | int | None) -> str:
    if n is None:
        return "n/a"
    if n > 0:
        return f"+{n}"
    return str(n)


def _fmt_secs(s: float | None) -> str:
    if s is None:
        return "n/a"
    if s < 60:
        return f"{int(s)}s"
    if s < 3600:
        return f"{s/60:.1f}m"
    if s < 86400:
        return f"{s/3600:.1f}h"
    return f"{s/86400:.1f}d"


# -------------------- main entry -------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aggregate_periodic.py",
        description="Generate a weekly or monthly changelog rollup.",
    )
    parser.add_argument("--period", choices=["weekly", "monthly"], required=True)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument(
        "--reference-date",
        help="ISO date (YYYY-MM-DD) override — default is today UTC.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute + print to stdout but do not write to S3.",
    )
    parser.add_argument(
        "--corpus-dir",
        help=(
            "Local dir of structured entries (one .json per file). "
            "If omitted, syncs s3://{bucket}/changelog/entries/ to a temp dir."
        ),
    )
    args = parser.parse_args(argv)

    reference = (
        date.fromisoformat(args.reference_date) if args.reference_date else _utc_today()
    )
    if args.period == "weekly":
        start, end, period_id = weekly_period(reference)
    else:
        start, end, period_id = monthly_period(reference)
    prior_start, prior_end, prior_id = prior_period(args.period, start)

    corpus_dir: Path
    cleanup_temp = False
    if args.corpus_dir:
        corpus_dir = Path(args.corpus_dir)
    else:
        corpus_dir = Path(tempfile.mkdtemp(prefix="changelog-corpus-"))
        cleanup_temp = True
        _aws_s3_sync(args.bucket, ENTRIES_PREFIX + "/", corpus_dir)

    try:
        period_entries = load_entries_in_range(corpus_dir, start, end)
        prior_entries = load_entries_in_range(corpus_dir, prior_start, prior_end)
        prior_rollup = compute_rollup(
            prior_entries,
            period_type=args.period,
            period_id=prior_id,
            period_start=prior_start,
            period_end=prior_end,
        )
        rollup = compute_rollup(
            period_entries,
            period_type=args.period,
            period_id=period_id,
            period_start=start,
            period_end=end,
        )
        rollup = add_deltas(rollup, prior_rollup if prior_entries else None)
        markdown = render_markdown(rollup)
    finally:
        if cleanup_temp:
            import shutil
            shutil.rmtree(corpus_dir, ignore_errors=True)

    json_payload = json.dumps(rollup, ensure_ascii=False, indent=2, sort_keys=True)
    json_key = f"{AGGREGATES_PREFIX}/{args.period}/{period_id}.json"
    md_key = f"{AGGREGATES_PREFIX}/{args.period}/{period_id}.md"

    print(f"Period:    {args.period} {period_id} ({start} → {end})")
    print(f"Entries:   {rollup['entry_count']}")
    print(f"Incidents: {rollup['incidents']['count']}")
    print(f"JSON key:  s3://{args.bucket}/{json_key}")
    print(f"MD key:    s3://{args.bucket}/{md_key}")

    if args.dry_run:
        print("\n=== JSON ===")
        print(json_payload)
        print("\n=== Markdown ===")
        print(markdown)
        print("\n(--dry-run; no S3 writes performed)")
        return 0

    _aws_s3_put(args.bucket, json_key, json_payload.encode("utf-8"), "application/json")
    _aws_s3_put(
        args.bucket,
        md_key,
        markdown.encode("utf-8"),
        "text/markdown; charset=utf-8",
    )
    print("\nWrote rollup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
