# `append-changelog` composite action

Writes a JSON deploy-event to the system-wide changelog S3 prefix
(`s3://alpha-engine-research/changelog/`). Every alpha-engine* repo's
deploy workflow calls this on success so cross-repo deploy provenance
lives in one place. The companion `aggregate-changelog.yml` cron in
this repo materializes the entries into a Markdown view daily.

## Caller pattern

Add a final step to your existing deploy job:

```yaml
- name: Append to system changelog
  if: always()  # capture failures too — set deploy_status accordingly
  uses: cipher813/alpha-engine-docs/.github/actions/append-changelog@main
  with:
    deploy_status: ${{ job.status == 'success' && 'success' || 'failure' }}
    deploy_workflow: ${{ github.workflow }}
```

For repos without a CI deploy step (config / docs — where push-to-main
is the deploy itself), use a dedicated minimal workflow:

```yaml
on:
  push:
    branches: [main]

jobs:
  changelog:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - name: Configure AWS credentials via OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::711398986525:role/github-actions-lambda-deploy
          aws-region: us-east-1
      - uses: actions/checkout@v4
      - uses: cipher813/alpha-engine-docs/.github/actions/append-changelog@main
        with:
          deploy_status: merged
```

## What gets written

S3 key: `s3://alpha-engine-research/changelog/{YYYY}/{MM}/{DD}T{HH-MM-SS}_{repo}_{sha7}.json`

```json
{
  "ts_utc": "2026-05-01T15:23:44Z",
  "repo": "cipher813/alpha-engine-data",
  "branch": "main",
  "sha": "febaccb...",
  "sha7": "febaccb",
  "pr_number": 119,
  "pr_title": "feat(daily_append): producer-side universe-freshness scan + S3 receipt",
  "pr_url": "https://github.com/cipher813/alpha-engine-data/pull/119",
  "author": "cipher813",
  "files_changed": 8,
  "deploy_workflow": "deploy.yml",
  "deploy_status": "success",
  "event_name": "push",
  "workflow_name": "Deploy",
  "workflow_run_id": "1234567890"
}
```

PR number + title are auto-derived from the merge-commit message
(`<title> (#<number>)` shape from squash/merge-commit/rebase strategies).
You can override either via inputs.

## Reading the materialized changelog

Local pull:

```bash
aws s3 cp s3://alpha-engine-research/changelog/CHANGELOG.md \
  ~/Development/alpha-engine-docs/private/CHANGELOG.md
```

Or query S3 directly:

```bash
aws s3 ls s3://alpha-engine-research/changelog/2026/05/ --recursive
aws s3 cp s3://alpha-engine-research/changelog/2026/05/01T15-23-44_alpha-engine-data_febaccb.json -
```

## IAM grant

The OIDC role `github-actions-lambda-deploy` needs:

```json
{
  "Effect": "Allow",
  "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
  "Resource": [
    "arn:aws:s3:::alpha-engine-research",
    "arn:aws:s3:::alpha-engine-research/changelog/*"
  ]
}
```

(`ListBucket` is on the bucket itself, `PutObject` + `GetObject` on the
prefix. The aggregator needs ListBucket to enumerate; appenders only need
PutObject.)
