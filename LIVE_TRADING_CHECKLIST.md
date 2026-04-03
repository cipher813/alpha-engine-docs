# Live Trading Readiness Checklist

Go/no-go criteria for graduating from paper to live trading.

## Performance Gates

- [ ] 90+ consecutive days of paper trading completed
- [ ] Cumulative alpha > 0% (portfolio beating SPY)
- [ ] Signal accuracy (10d) >= 55% with >= 100 samples
- [ ] Max drawdown never exceeded -8% circuit breaker during paper period
- [ ] Backtester Sharpe > 1.0 on synthetic 10y backtest
- [ ] GBM IC consistently positive (>0.02 median across walk-forward folds)

## System Reliability

- [ ] No unplanned pipeline failures for 30 consecutive trading days
- [ ] All Phase 1-3 optimization items completed
- [ ] Emergency shutdown tested successfully on paper account
- [ ] Drift detection running for 4+ weeks with no unresolved alerts
- [ ] Health checker running daily with no persistent stale-data alerts
- [ ] Feature store serving GBM inference with 0 inline fallback for 2+ weeks

## Testing

- [ ] Unit tests passing in all 6 repos (CI green)
- [ ] Integration test suite passing
- [ ] Executor dry-run passes with current signals and predictions
- [ ] pip-audit clean (no critical/high CVEs in dependencies)

## Operations

- [ ] Runbooks reviewed for all 10 failure modes
- [ ] EOD reconciliation email verified accurate for 30+ consecutive days
- [ ] Execution quality monitoring showing acceptable slippage (<20 bps avg)
- [ ] Dashboard accessible and showing current data

## Security (Live-Specific)

- [ ] IB live account credentials stored in AWS Secrets Manager (NOT on EC2)
- [ ] Paper safety check verified: account ID "D" prefix guard in daemon.py
- [ ] TOTP 2FA configured for live IB account
- [ ] Live account port (4001) not used anywhere in codebase — only 4002 (paper)
- [ ] EC2 security groups reviewed and tightened

## Capital & Risk

- [ ] Initial capital allocation decided and documented
- [ ] Position sizing parameters validated against live account size
- [ ] Max loss per day / per week tolerance documented
- [ ] Circuit breaker threshold (-8%) appropriate for account size

## Go/No-Go Decision

- [ ] All above boxes checked
- [ ] Manual review of last 30 days of paper trading decisions
- [ ] Written decision memo with rationale and risk acknowledgment
- [ ] Gradual rollout plan: start with reduced position sizes for first 2 weeks
