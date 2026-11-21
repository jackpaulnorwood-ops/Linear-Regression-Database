# Q-learning improvement log

## Scope and safety

- Goal: improve historical held-out performance while maintaining repeatable, chronological validation.
- The baseline currently produces no trades across five AAPL trials, so deployment is not supported yet.
- This log records code changes, experiments, outcomes, and deployment recommendations.
- Historical results do not establish future profitability.

## Experiment 1 — entry reward

- Status: Running (trial 1 started)
- Hypothesis: a training-only entry bonus may overcome conservative Q-values and create exploratory long positions.
- Configuration: AAPL, 5 trials, 200 episodes, seeds 0–4, epsilon 1.0 to 0.05, transaction cost 5 bps.
- Change: `--entry-bonus-bps 5` versus the baseline `0` bps.
- Backtest: held-out period 2025-07-03 to 2026-11-19.
- Expected outcome: additional entries or an increase in net return. A small trade increase with lower risk-adjusted performance will not count as improvement.
- Outcome: pending.

## Baseline reference

Source: `runs/run_20261121_062003/`

- Five trials.
- Mean net return: 0.00%
- Mean Sharpe: 0.000
- Mean completed trades: 0
- Mean maximum drawdown: 0.00%
- Entry bonus: 0 bps

## Decision rules

- A run is improved only if it exceeds baseline median net return and does not materially worsen Sharpe, maximum drawdown, or repeatability.
- One profitable seed will not count as evidence.
- No active model or live/paper-deployment change will be made without repeated positive validation.

## Code-change 1 — default paper-readiness guard

- Added `paper_ready: false` and a review reason to every newly saved model.
- Paper submissions now require `PAPER_TRADING_ENABLED=true`.
- Pooled multi-symbol models are rejected for paper submission because they cannot be mapped safely to one Alpaca symbol.
- Added a GitHub Actions workflow that defaults to dry-run decisions and requires manual dispatch plus repository configuration for submissions.
- No model is currently paper-ready.

## Validation 1 — unit tests

- Ran `python -m unittest tests.test_q_learning`.
- Result: 15 tests passed.
- Covered: data windows, training, backtests, logs, model round-trip, archiving, and visualizations.
- Added: newly saved models default to `paper_ready: false`.
