#!/usr/bin/env bash
# changelog-log — emit a structured entry to the system-wide changelog.
#
# This shim execs the Python implementation in changelog_log.py.
# The legacy positional interface (`changelog-log manual "summary"`) was
# removed in PR 1 of the schema-discipline arc — see ROADMAP > Observability >
# "System-wide changelog: schema discipline + artifact linking + aggregation
# layer". Use --event-type / --summary flags now (see `changelog-log --help`).
#
# Setup convenience: alias in ~/.zshrc:
#   alias changelog-log="$HOME/Development/alpha-engine-docs/scripts/changelog-log.sh"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect legacy positional invocation: first arg is one of the old event-type
# keywords without a leading dash. Print migration help + exit non-zero —
# callers see a clear error rather than a confusing argparse complaint.
if [[ $# -ge 1 && "$1" =~ ^(manual|recovery|incident)$ ]]; then
  cat >&2 <<EOF
ERROR: the legacy positional interface was removed in the schema-discipline
arc. Use flag-based invocation:

  Old:  changelog-log manual "Patched live SF timeout 60→300"
  New:  changelog-log --event-type change --subsystem infrastructure \\
          --resolution-type manual_intervention \\
          --detected-at $(date -u +%Y-%m-%dT%H:%M:%SZ) \\
          --resolved-at $(date -u +%Y-%m-%dT%H:%M:%SZ) \\
          --verified-at $(date -u +%Y-%m-%dT%H:%M:%SZ) \\
          --summary "Patched live SF timeout 60→300"

  Old:  changelog-log incident "Daemon hung on ae-trading"
  New:  changelog-log --event-type incident --severity high \\
          --subsystem executor --root-cause infrastructure_failure \\
          --started-at <when_it_started> --detected-at <when_we_noticed> \\
          --resolved-at <when_fixed>     --verified-at <when_confirmed> \\
          --summary "Daemon hung on ae-trading" \\
          --resolution-notes "Root cause: ... Resolution: ... (≥ 200 chars)"

See \`changelog-log --help\` for the full surface and vocab values.
EOF
  exit 2
fi

exec python3 "${SCRIPT_DIR}/changelog_log.py" "$@"
