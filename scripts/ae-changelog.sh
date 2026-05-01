#!/usr/bin/env bash
# ae-changelog — download the latest aggregated CHANGELOG.md from S3 to
# `alpha-engine-docs/private/CHANGELOG_<version>.md`.
#
# The aggregator workflow (aggregate-changelog.yml) materializes the
# changelog daily at 06:00 UTC and writes it to
# s3://alpha-engine-research/changelog/CHANGELOG.md. This script pulls
# that file, naming the local copy with the S3 object's Last-Modified
# timestamp so each pull is a discrete snapshot rather than overwriting
# in place.
#
# Usage:
#   ae-changelog              # pull latest, save to private/CHANGELOG_<ver>.md
#   ae-changelog --force      # re-download even if a snapshot for this version exists
#   ae-changelog --latest     # also write/update private/CHANGELOG.md (always-latest pointer)
#
# Setup convenience: add to ~/.zshrc
#   alias ae-changelog="$HOME/Development/alpha-engine-docs/scripts/ae-changelog.sh"
#
# Auth: uses active AWS CLI creds. Needs s3:GetObject on
# arn:aws:s3:::alpha-engine-research/changelog/CHANGELOG.md.

set -euo pipefail

BUCKET="${CHANGELOG_BUCKET:-alpha-engine-research}"
KEY="${CHANGELOG_KEY:-changelog/CHANGELOG.md}"
TARGET_DIR="${CHANGELOG_TARGET_DIR:-$HOME/Development/alpha-engine-docs/private}"

FORCE=false
WRITE_LATEST=false
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=true ;;
    --latest) WRITE_LATEST=true ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "ERROR: unknown arg '$arg'" >&2; exit 1 ;;
  esac
done

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI not on PATH. Add /opt/homebrew/bin to PATH or activate your venv." >&2
  exit 1
fi

# Use the S3 object's Last-Modified timestamp as the snapshot version.
# That's the "when the aggregator last ran" time — repeated pulls of
# the same version yield idempotent filenames.
LAST_MODIFIED=$(aws s3api head-object \
  --bucket "$BUCKET" \
  --key "$KEY" \
  --query 'LastModified' \
  --output text 2>/dev/null || echo "")

if [[ -z "$LAST_MODIFIED" ]]; then
  echo "ERROR: could not stat s3://${BUCKET}/${KEY}. Check creds + that the aggregator has run at least once." >&2
  exit 1
fi

# Format: 2026-05-01T17-15-04Z (filesystem-safe).
VERSION=$(python3 -c "
import sys
from datetime import datetime, timezone
raw = sys.argv[1]
# AWS returns ISO 8601 like '2026-05-01T17:15:04+00:00' — normalize.
ts = datetime.fromisoformat(raw.replace('Z', '+00:00')).astimezone(timezone.utc)
print(ts.strftime('%Y-%m-%dT%H-%M-%SZ'))
" "$LAST_MODIFIED")

mkdir -p "$TARGET_DIR"
SNAPSHOT="${TARGET_DIR}/CHANGELOG_${VERSION}.md"

if [[ -f "$SNAPSHOT" && "$FORCE" != "true" ]]; then
  echo "✓ Already have snapshot for version ${VERSION}: ${SNAPSHOT}"
  if "$WRITE_LATEST"; then
    cp "$SNAPSHOT" "${TARGET_DIR}/CHANGELOG.md"
    echo "  Also updated always-latest pointer: ${TARGET_DIR}/CHANGELOG.md"
  fi
  echo "  (--force to re-download)"
  exit 0
fi

echo "Pulling s3://${BUCKET}/${KEY} (version ${VERSION})..."
aws s3 cp "s3://${BUCKET}/${KEY}" "$SNAPSHOT"
echo "✓ Saved snapshot: ${SNAPSHOT}"

if "$WRITE_LATEST"; then
  cp "$SNAPSHOT" "${TARGET_DIR}/CHANGELOG.md"
  echo "✓ Also updated always-latest pointer: ${TARGET_DIR}/CHANGELOG.md"
fi

# Show a small head excerpt so the user sees what landed.
head -6 "$SNAPSHOT"
