# Alpha Engine Runbooks

Procedures for the 10 most common failure modes.

---

## 1. IB Gateway Disconnects Mid-Day

**Symptoms:** Daemon log shows `IB Gateway connection lost during poll` repeatedly. No trades executing. Telegram heartbeat stops.

**Diagnosis:**
```bash
ae "tail -20 /var/log/daemon.log"
ae "sudo systemctl status ibgateway"
ae "docker ps | grep ib-gateway"
```

**Resolution:**
1. Restart IB Gateway: `ae "sudo systemctl restart ibgateway"`
2. Wait 30 seconds for connection
3. Restart daemon: `ae "sudo systemctl restart alpha-engine-daemon"`
4. Verify: `ae "tail -5 /var/log/daemon.log"` should show `Connected to IB Gateway`

**Prevention:** IBC `ExistingSessionDetectedAction=primary` prevents session conflicts. Docker restart policy handles transient failures.

---

## 2. Lambda Times Out During Research

**Symptoms:** Saturday pipeline fails at Research step. SNS failure email received. No signals.json for this week.

**Diagnosis:**
```bash
# Check Step Function execution in AWS Console
# Check CloudWatch logs for alpha-engine-research-runner
aws logs tail /aws/lambda/alpha-engine-research-runner --since 2h
```

**Resolution:**
1. Check if partial signals were written: `aws s3 ls s3://alpha-engine-research/signals/$(date +%Y-%m-%d)/`
2. If no signals, manually trigger: open Lambda console > alpha-engine-research-runner > Test with `{"weekly_run": true, "force": true}`
3. If persistent timeout, check if universe grew too large or Anthropic API is throttling

**Prevention:** Research Lambda has 15-min timeout. If universe exceeds ~50 tickers in deep analysis, timeout risk increases. Scanner quant filter should keep it under 50.

---

## 3. Signals Stale (>8 Days)

**Symptoms:** Health checker alert: `signals: stale`. Executor uses fallback signals from previous week.

**Diagnosis:**
```bash
# Check latest signals
aws s3 ls s3://alpha-engine-research/signals/ --recursive | tail -5
# Check Saturday pipeline execution
# AWS Step Functions console > alpha-engine-saturday-pipeline > recent executions
```

**Resolution:**
1. If Saturday pipeline didn't run: check EventBridge rule, manually start execution
2. If pipeline ran but Research failed: see Runbook #2
3. If signals written but latest.json not updated: manually copy the dated file

**Prevention:** Health checker runs after each pipeline. `signals/latest.json` pointer reduces date-scanning fragility.

---

## 4. Predictions Stale (>2 Days)

**Symptoms:** Health checker alert: `predictions: stale`. Morning briefing email not received. Executor runs without GBM input.

**Diagnosis:**
```bash
aws s3 ls s3://alpha-engine-research/predictor/predictions/ | tail -5
# Check daily Step Function
# AWS Step Functions console > alpha-engine-weekday-pipeline
```

**Resolution:**
1. Check if daily pipeline ran (Step Function console)
2. If PredictorInference step failed: check Lambda CloudWatch logs
3. Manual rerun: Lambda console > alpha-engine-predictor-inference > Test with `{"action": "predict"}`
4. If feature store missing: check DailyData step completed first

**Prevention:** Daily pipeline runs Mon-Fri 6:05 AM PT. Holiday skip (trading_calendar.py) is normal.

---

## 5. EC2 Trading Instance Fails to Start

**Symptoms:** No executor or daemon logs for the day. No trades. No EOD email.

**Diagnosis:**
```bash
export PATH="/opt/homebrew/bin:$PATH"
aws ec2 describe-instance-status --instance-ids <trading-instance-id> --query "InstanceStatuses[0].InstanceState.Name" --output text
```

**Resolution:**
1. Check instance state: if `stopped`, start manually: `aws ec2 start-instances --instance-ids <id>`
2. If `terminated`: instance was terminated (not stopped). Restore from latest AMI or rebuild.
3. If `running` but no services: SSH in and check systemd: `ae "sudo systemctl status alpha-engine-morning"`
4. If boot-pull failed: `ae "cd ~/alpha-engine && git pull && sudo systemctl restart alpha-engine-morning"`

**Prevention:** Step Function starts instance automatically. EventBridge Scheduler stops it at 1:30 PM PT.

---

## 6. S3 Access Denied

**Symptoms:** Any module fails with `AccessDenied` or `403 Forbidden` when reading/writing S3.

**Diagnosis:**
```bash
# Test access from EC2
ae "aws s3 ls s3://alpha-engine-research/ --max-items 1"
# Check IAM role
ae "curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/"
```

**Resolution:**
1. Verify the EC2 instance profile has the correct IAM role attached
2. Check IAM role policy allows `s3:GetObject`, `s3:PutObject` on `alpha-engine-research/*`
3. Check if bucket policy was changed
4. If Lambda: check execution role in Lambda configuration

**Prevention:** IAM roles are attached to EC2 instances and Lambda functions. Never use hardcoded credentials.

---

## 7. Anthropic API Rate Limit or Outage

**Symptoms:** Research Lambda fails with `429 Too Many Requests` or `503 Service Unavailable`. Partial signals generated.

**Diagnosis:**
```bash
# Check Anthropic status
# https://status.anthropic.com
# Check CloudWatch logs for rate limit errors
aws logs filter-events --log-group /aws/lambda/alpha-engine-research-runner --filter-pattern "429"
```

**Resolution:**
1. If rate limit: wait 1 hour and retry. Research has built-in retry with backoff.
2. If outage: wait for Anthropic to resolve. Manual rerun after recovery.
3. If persistent: check monthly API usage, consider upgrading tier.

**Prevention:** Research uses Haiku for per-ticker analysis (cheap, fast) and Sonnet only for synthesis. This keeps costs and rate limits manageable.

---

## 8. yfinance / polygon.io Data Source Outage

**Symptoms:** DataPhase1 fails or completes with high error count. Stale price data.

**Diagnosis:**
```bash
aem "tail -30 /var/log/data-phase1.log"
# Check manifest for errors
aws s3 cp s3://alpha-engine-research/market_data/weekly/$(date +%Y-%m-%d)/manifest.json - | python -m json.tool
```

**Resolution:**
1. Check if source is down (yfinance GitHub issues, polygon.io status page)
2. If yfinance: price data is cached in S3. Stale by 1 day is acceptable for 5-day horizon.
3. If polygon.io: universe returns are weekly. 1-week stale is tolerable.
4. Manual collection: `aem "cd ~/alpha-engine-data && source .venv/bin/activate && python weekly_collector.py --phase 1 --only prices"`

**Prevention:** Polygon.io migration (future) provides a more reliable alternative to yfinance. Current thresholds (8 days for signals, 2 days for predictions) provide buffer.

---

## 9. Drawdown Circuit Breaker Triggered

**Symptoms:** EOD email shows drawdown exceeding tier thresholds. Position sizes reduced or halted.

**Diagnosis:**
```bash
# Check current drawdown
aws s3 cp s3://alpha-engine-research/trades/eod_pnl.csv - | tail -10
# Check risk.yaml thresholds
ae "cat ~/alpha-engine/config/risk.yaml | grep -A5 graduated_drawdown"
```

**Resolution:**
1. Drawdown tiers reduce position sizes automatically — this is working as designed
2. If circuit breaker halt (-8%): no new entries until NAV recovers above threshold
3. Review positions: are losses concentrated in one sector? Consider manual exits.
4. If drawdown is due to market-wide decline (SPY also down): alpha may still be positive

**Prevention:** Graduated drawdown tiers (0%/-2%/-4%/-6%/-8%) reduce exposure progressively. The backtester optimizes these thresholds weekly.

---

## 10. Emergency Shutdown Needed

**Symptoms:** Any situation requiring immediate cessation of all trading activity.

**Resolution:**
```bash
# From local machine (SSH to trading instance)
ae "cd ~/alpha-engine && source .venv/bin/activate && python executor/emergency_shutdown.py --execute"

# If also need to stop the instance
ae "cd ~/alpha-engine && source .venv/bin/activate && python executor/emergency_shutdown.py --execute --stop-instance"

# If SSH not available, stop instance directly
export PATH="/opt/homebrew/bin:$PATH"
aws ec2 stop-instances --instance-ids <trading-instance-id>
```

**What emergency_shutdown.py does:**
1. Cancels all open orders (reqGlobalCancel)
2. Closes all positions at market
3. Stops the daemon service
4. Backs up trades.db to S3
5. Sends SNS notification

**Prevention:** Test emergency shutdown on paper account monthly. Verify it works before going live.
