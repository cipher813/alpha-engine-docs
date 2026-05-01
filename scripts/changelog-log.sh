#!/usr/bin/env bash
# changelog-log — emit a manual / recovery / incident entry to the system-wide changelog.
#
# Usage:
#   changelog-log manual    "Patched live SF DeployDriftCheck timeout 60→300"
#   changelog-log manual    "Pulled alpha-engine on ae-trading + restarted morning service"
#   changelog-log recovery  "Morning planner ran clean — order book written to S3"
#   changelog-log incident  "Daemon hung on ae-trading; killed pid 12345 manually"
#   changelog-log manual    "Ran daily_append manually" --details "Specific notes…"
#
# Lands the entry at:
#   s3://alpha-engine-research/changelog/{event_type}s/{YYYY}/{MM}/{DD}T{HH-MM-SS}_{actor}_{hash}.json
#
# Schema matches the aggregator (alpha-engine-docs/.github/workflows/
# aggregate-changelog.yml) so manual entries interleave with deploy +
# incident entries in the daily-materialized CHANGELOG.md.
#
# Auth: uses the active AWS CLI creds (e.g. ~/.aws/credentials). The IAM
# user / role needs s3:PutObject on
# arn:aws:s3:::alpha-engine-research/changelog/*. The cipher813 personal
# IAM user already has this; for other operators, grant separately.
#
# Setup convenience: add to ~/.zshrc (or wherever):
#   alias changelog-log="$HOME/Development/alpha-engine-docs/scripts/changelog-log.sh"

set -euo pipefail

usage() {
  cat <<EOF
Usage: changelog-log <event_type> <summary> [--details "<longer text>"] [--actor <name>]

  event_type   manual | recovery | incident
  summary      one-line description (~< 240 chars recommended)
  --details    optional longer body (multi-line OK; quote it)
  --actor      override actor (default: \$USER)

Examples:
  changelog-log manual "Patched live SF timeout 60→300"
  changelog-log recovery "Morning planner ran clean"
  changelog-log incident "Daemon hung; killed pid 12345"
EOF
  exit 1
}

[[ $# -lt 2 ]] && usage

EVENT_TYPE="$1"; shift
SUMMARY="$1"; shift
DETAILS=""
ACTOR="${USER:-unknown}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --details)
      [[ $# -lt 2 ]] && { echo "ERROR: --details requires a value" >&2; exit 1; }
      DETAILS="$2"; shift 2 ;;
    --actor)
      [[ $# -lt 2 ]] && { echo "ERROR: --actor requires a value" >&2; exit 1; }
      ACTOR="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "ERROR: unknown arg '$1'" >&2; usage ;;
  esac
done

case "$EVENT_TYPE" in
  manual|recovery|incident) ;;
  *) echo "ERROR: event_type must be one of: manual, recovery, incident (got '$EVENT_TYPE')" >&2; exit 1 ;;
esac

# Sub-prefix mirrors the aggregator's expectations:
# manual    -> changelog/manual/...
# recovery  -> changelog/recoveries/...
# incident  -> changelog/incidents/...
case "$EVENT_TYPE" in
  manual)   SUB_PREFIX="manual" ;;
  recovery) SUB_PREFIX="recoveries" ;;
  incident) SUB_PREFIX="incidents" ;;
esac

BUCKET="${CHANGELOG_BUCKET:-alpha-engine-research}"
TS_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
TS_KEY=$(date -u +%Y/%m/%dT%H-%M-%S)

# Hash the summary + ts so re-running with the same args within the same
# second gets a unique-ish key. Avoids accidental overwrite if a script
# loops faster than the second resolution.
HASH=$(printf '%s|%s|%s' "$TS_UTC" "$ACTOR" "$SUMMARY" | shasum -a 1 | cut -c1-7)

# Build the entry via python3 so newlines + quotes in summary / details
# round-trip cleanly. Vars are exported below the heredoc so os.environ
# sees them.
export TS_UTC EVENT_TYPE ACTOR SUMMARY DETAILS
ENTRY=$(python3 - <<'PY'
import json, os
print(json.dumps({
    "ts_utc": os.environ["TS_UTC"],
    "event_type": os.environ["EVENT_TYPE"],
    "source": "changelog-log",
    "actor": os.environ["ACTOR"],
    "summary": os.environ["SUMMARY"],
    "details": os.environ.get("DETAILS", ""),
    "machine": os.uname().nodename,
}))
PY
)

S3_KEY="changelog/${SUB_PREFIX}/${TS_KEY}_${ACTOR}_${HASH}.json"

echo "→ Posting ${EVENT_TYPE} entry to s3://${BUCKET}/${S3_KEY}"
echo "  summary: ${SUMMARY}"
[[ -n "$DETAILS" ]] && echo "  details: $(echo "$DETAILS" | head -c 100)$([[ ${#DETAILS} -gt 100 ]] && echo "…" || true)"

echo "${ENTRY}" | aws s3 cp - "s3://${BUCKET}/${S3_KEY}" --content-type application/json

echo "✓ Posted."
