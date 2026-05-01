# `scripts/` — operational helpers

Local + on-machine helpers for the system-wide changelog mining surface.
None of these are auto-invoked; they exist for the operator to drop
manual annotations into the changelog or pull aggregated views locally.

## `changelog-log` — manual annotations

Drops a JSON entry into `s3://alpha-engine-research/changelog/{event_type}s/`
so manual operator actions interleave with auto-emitted deploys + incidents
in the daily-aggregated `CHANGELOG.md`.

```bash
changelog-log manual    "Patched live SF DeployDriftCheck timeout 60→300"
changelog-log recovery  "Morning planner ran clean — order book written"
changelog-log incident  "Daemon hung on ae-trading; killed pid 12345"
changelog-log manual    "Ran daily_append manually" --details "Specific notes…"
```

**Setup** — add to `~/.zshrc`:

```bash
alias changelog-log="$HOME/Development/alpha-engine-docs/scripts/changelog-log.sh"
```

**Auth** — uses active AWS CLI creds. Needs `s3:PutObject` on
`arn:aws:s3:::alpha-engine-research/changelog/*`. The `cipher813` IAM user
already has it; for other operators, grant separately.

**Why this exists** — the auto-emitted deploy + incident streams capture
CI events. They don't capture operator interventions like "I patched the
live SF" or "I ssh'd in and restarted the daemon." Without manual
annotations, retro queries months later can't reconstruct what happened —
the deploy log shows the fix PRs, but not the operator actions that
unblocked the day. This script closes that gap.

## `pull-changelog` — local CHANGELOG.md refresh

(Future helper; for now use:)

```bash
aws s3 cp s3://alpha-engine-research/changelog/CHANGELOG.md \
  $HOME/Development/alpha-engine-docs/private/CHANGELOG.md
```

The aggregator cron runs at 06:00 UTC daily. To force a refresh sooner:

```bash
gh workflow run aggregate-changelog.yml -R cipher813/alpha-engine-docs
```
