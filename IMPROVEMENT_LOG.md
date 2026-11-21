# Q-learning improvement log

## Scope and safety

- Goal: improve historical held-out performance while maintaining repeatable, chronological validation.
- The baseline currently produces no trades across five AAPL trials, so deployment is not supported yet.
- This log records code changes, experiments, outcomes, and deployment recommendations.
- Historical results do not establish future profitability.

## Experiment 1 — entry reward

- Status: Complete
- Hypothesis: a training-only entry bonus may overcome conservative Q-values and create exploratory long positions.
- Configuration: AAPL, 5 trials, 200 episodes, seeds 0–4, epsilon 1.0 to 0.05, transaction cost 5 bps.
- Change: `--entry-bonus-bps 5` versus the baseline `0` bps.
- Backtest: held-out period 2025-07-03 to 2026-11-19.
- Expected outcome: additional entries or an increase in net return. A small trade increase with lower risk-adjusted performance will not count as improvement.
- Outcome: The entry bonus successfully stopped four of five? Actually the models traded, but every trial had a negative held-out net return. Trial net returns were -4.776%, -0.372%, -7.133%, -1.523%, and -2.240%: mean -3.209%, median -2.240%. Sharpe values were -5.242, -1.608, -5.372, -2.296, and -2.950: mean -3.494, median -2.950. Maximum drawdowns were 4.776%, 0.372%, 7.136%, 1.523%, and 2.247%: mean 3.211%, median 2.247%. Completed trades were 56, 3, 58, 16, and 19: mean 30.4, median 19.
- Decision: Not an improvement. The entry bonus increased activity but degraded net return and Sharpe consistently enough to reject 5-bps entry reward as a standalone improvement.
- Next experiment: retain the 5-bps entry bonus, but increase transaction cost from 5 to 10 bps. This is intended to reduce excessive entry/exit activity while testing whether fewer trades improve return and drawdown.

## Experiment 2 — entry reward plus higher transaction cost

- Status: Complete
- Hypothesis: retaining the 5-bps entry bonus may still generate tradable states, while a 10-bps position-change cost will penalize churn and potentially improve net return and drawdown.
- Configuration: AAPL, 5 trials, 200 episodes, seeds 0–4, epsilon 1.0 to 0.05, transaction cost 10 bps, entry bonus 5 bps.
- Change: `--cost-bps 10` versus Experiment 1's 5-bps cost, while holding the entry bonus and all other baseline settings constant.
- Backtest: held-out period 2025-07-03 to 2026-11-19.
- Expected outcome: fewer completed trades and lower turnover. Improvement requires positive relative net return, higher or less-negative Sharpe, lower drawdown, and repeatability across seeds.
- Outcome: All five trials remained flat. Completed trades were 0, 0, 0, 0, and 0. Net returns were 0.00%, 0.00%, 0.00%, 0.00%, and 0.00%; mean and median were 0.00%. Sharpe values were 0.000 across all five trials. Maximum drawdowns were 0.00% across all five trials.
- Decision: Not an improvement. The 10-bps transaction cost suppressed every entry, yielding the same no-trade baseline without evidence of better feature-policy learning. The combination of 5-bps entry reward and 10-bps transaction cost is rejected.

## Experiment 3 — lower entry reward

- Status: Running
- Hypothesis: a 1-bps training-only entry bonus may create enough exploration to find opportunities without generating the heavy negative-mean activity seen at 5 bps.
- Configuration: AAPL, 5 trials, 200 episodes, seeds 0–4, epsilon 1.0 to 0.05, transaction cost 5 bps, entry bonus 1 bps.
- Change: `--entry-bonus-bps 1` versus both baseline 0 bps and Experiment 1 5 bps.
- Backtest: held-out period 2025-07-03 to 2026-11-19.
- Expected outcome: selective entries with lower turnover than 5 bps and a less-negative or positive net result.
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
