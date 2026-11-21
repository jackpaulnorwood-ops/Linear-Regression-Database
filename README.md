# Stock trading experiments

The existing linear-regression script remains available as `train_model.py`.
For a tabular Q-learning experiment, train and evaluate using the local,
read-only five-minute SQLite bars:

```bash
python q_learning.py --symbol AAPL --episodes 200
```

The trainer uses regular-session bars, a chronological date split, and a
training-only feature discretization. Its actions are flat or long (no short
selling); simulated returns deduct a configurable transaction cost of 5 basis
points per position change. By default, it runs five independent trials with
distinct seeds. It creates a UTC-timestamped run directory under
`runs/run_YYYYMMDD_HHMMSS/`, with `run.log`, `analyses.md`, `trials.csv`,
`tuning_advice.md`, `trial_comparison.png`, and one `trial_####/` folder per
trial. Use `--trials` to set the number of runs or `--run-root` to change the
run directory. A single trial saves to `q_learning_model.json` by default and
archives the previous active model in that trial's `model_archive/` folder.
With multiple trials, each model remains in its trial folder and the active
project-level model is not replaced. It reports
held-out net return versus buy-and-hold, completed round-trip trades and
entries/exits, trades per session, exposure, wins/losses, win rate, average
trade outcome, profit factor, and positive/negative sessions. A backtest is
not a guarantee of future performance, and trade frequency alone does not
establish over- or under-trading. Each completed trial appends its parameters
and held-out metrics to the run's CSV (customize with `--trial-log`). The
Sharpe ratio is annualized from daily held-out returns
using a zero risk-free rate; it is a historical risk-adjusted metric, not a
forecast or an accuracy score. The log also compares the learned strategy to a
seeded random flat/long policy and buy-and-hold; the random policy is a simple
reference, not proof of skill. Each row includes notes on interpreting epsilon,
Sharpe, and that trial's baseline results. Epsilon is the training-time
probability of choosing a random action rather than the current best-known
action. There is no universal best value; the default schedule decays from 1.0
to 0.05, configurable with `--epsilon-start` and `--epsilon-end`. Compare
schedules over multiple seeds and validation periods. Backtest decisions are
greedy (no random exploration). During training, the terminal prints progress
approximately every 5% of episodes, including the current episode, exploration
rate, elapsed time, and estimated time remaining.

To test a small training-only entry incentive across the default five seeds,
run `python q_learning.py --entry-bonus-bps 1`. This adds 1 basis point
(0.01%) to training reward only when opening a long position. The held-out
backtest still measures actual market returns after simulated costs, without
the bonus. Compare that run with a zero-bonus run; the bonus may encourage
churn and is not profit. The log records the configured bonus for each trial.

The trainer uses CPU-based tabular Q-learning. Its sequential lookup-table
updates do not benefit from GPU acceleration, so the GPU is not used.

To run one decision against Alpaca:

1. Install the dependencies in `requirements.txt`.
2. Set `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` in your local environment.
3. Run `python paper_trade.py --model q_learning_model.json` to inspect a
   dry-run decision.
4. Add `--submit-paper-order` only when you want to submit an order.

For VS Code debugging, create a workspace-root `.env` file containing
`APCA_API_KEY_ID=your_paper_key` and
`APCA_API_SECRET_KEY=your_paper_secret`, then select the **Debug paper trader**
configuration. The `.env` file is Git-ignored; never commit or share it.

`paper_trade.py` constructs its trading client with Alpaca's paper mode and
requests historical bars from Alpaca's IEX feed, avoiding the SIP data
subscription required by the default feed. IEX market coverage can differ from
SIP. The script has no live-trading option. It defaults to the symbol stored
in the model and a $100 notional limit for a new long position. To close an existing position,
also pass `--manage-existing-position` after confirming that the bot should
manage that symbol's position. Review the model, account, and order details
before submitting; the script evaluates a single decision per run and does
not run continuously.

## Quick start

From the project directory, install dependencies and run a small test:

```powershell
python -m pip install -r requirements.txt
python .\q_learning.py --symbol AAPL --trials 1 --episodes 20
```

This is a smoke test, not enough evidence for future profitability. For a meaningful local comparison, begin with 5–10 trials and at least 200 episodes:

```powershell
python .\q_learning.py --symbol AAPL --trials 5 --episodes 200 --seed 0
```

## Database setup

The trainer is read-only and loads five-minute stock bars from `bars_5m` in an SQLite database. Set `STOCK_DB_PATH` once to the database location:

```powershell
[Environment]::SetEnvironmentVariable("STOCK_DB_PATH", "C:\Users\Jack Attack\Documents\intraday_5m.sqlite", "User")
```

Close and reopen VS Code or the terminal so the persistent value is loaded. The database finder first checks `STOCK_DB_PATH`, then a project-local `intraday_5m.sqlite`, several common local locations, and finally the classroom NAS. Verify access with:

```powershell
python -c "import explore_stocks; print(explore_stocks.DB_PATH)"
```

Do not modify the source database. The scripts open it read-only.

## How episodes, trials, and seeds work

- **Episode:** one complete pass through the training sessions for that trial.
- **Trial:** an independent seeded training run followed by a held-out backtest.
- **Seed:** initializes random epsilon exploration and random-policy baselines.

Trial 1 uses `--seed` unchanged; trial 2 uses seed + 1, and each later trial increments it. For example, `--trials 5 --seed 100` uses seeds 100–104.

Start seed comparisons with 5–10 trials and keep all other settings the same. Compare average and median net return, Sharpe, drawdown, and trade counts rather than selecting only the best seed. Reuse the same seed range when comparing parameter settings. Do not repeatedly tune until one seed looks profitable.

## Current run locations

Every run uses a UTC timestamped folder:

```text
runs/
  run_YYYYMMDD_HHMMSS/
    run.log
    analyses.md
    trial_comparison.png
    tuning_advice.md
    tuning_recommendations.csv
    trials.csv
    trial_0001/
      train.log
      analysis.md
      q_learning_model.json
      model_archive/
      visualizations/
        performance_dashboard.png
        position_and_exposure.png
        README.md
```

A project-level `q_learning_trials.csv` accumulates trial summaries. Use `--trial-log` to send them elsewhere.

## Single-stock and pooled-training commands

Single-stock training:

```powershell
python .\q_learning.py --symbol AAPL --trials 5 --episodes 200 --seed 0
```

Pooled multi-stock training is an experiment, not the default recommendation:

```powershell
python .\q_learning.py --symbols AAPL MSFT RBLX --trials 5 --episodes 200 --seed 0
```

Pooled training uses the same feature bins and Q-table for separate symbol/date sessions. It does not merge bars from different symbols into a fake single timeline. High-volume or high-availability symbols can dominate pooled training, so compare pooled results against separately trained stock models before choosing it.

## Tuning and reward settings

- `--episodes`: number of complete training passes per trial.
- `--trials`: number of independent seeded training runs.
- `--seed`: first seed; later trials increment it.
- `--epsilon-start`: exploration probability for the first episode.
- `--epsilon-end`: exploration probability for the final episode.
- `--cost-bps`: transaction cost per position change, in basis points.
- `--entry-bonus-bps`: training-only flat-to-long entry reward; never added to held-out returns.
- `--model`: project-relative or absolute active-model output for a one-trial run.
- `--run-root`: parent directory for run folders.
- `--trial-log`: optional CSV override.

For a simple tuning workflow:

1. Choose a fixed seed range and run baseline trials.
2. Change one setting at a time.
3. Repeat across the same seed range and held-out period.
4. Compare median/average result, not only the best trial.
5. Re-test in a new held-out period before considering deployment.

The generated `tuning_advice.md` contains rule-based hypotheses, not guaranteed improvements.

## Model archiving

With exactly one trial, the completed model is copied to `q_learning_model.json` as the active model. If that file already existed, the previous file is copied into `trial_0001/model_archive/` before replacement.

With multiple trials, each trial keeps its model inside `trial_####/q_learning_model.json`; the active project-level model is not replaced.

Check the active model status before a one-trial run:

```powershell
Test-Path .\q_learning_model.json
```

`True` means a previous active model will be archived; `False` means no previous model exists.

## Visualizations and trial access

View the latest trial or search the accumulated project CSV:

```powershell
python .\view_trials.py --latest
python .\view_trials.py --trial 1
python .\view_trials.py --search "random flat/long"
python .\view_trials.py --symbol AAPL
python .\view_trials.py --advice
```

Trial visualizations include:

- Cumulative model, buy-and-hold, and random equity curves
- Drawdown
- Daily strategy-return distribution
- Completed trade-return distribution
- Flat/long position history
- Entries by session
- Pooled per-symbol comparison, when applicable

The run-level `trial_comparison.png` compares net return, Sharpe, trades, and drawdown between trials.

## Paper trading

The Alpaca integration is paper-trading only. Install dependencies and set paper credentials:

```powershell
$env:APCA_API_KEY_ID = "your_paper_key"
$env:APCA_API_SECRET_KEY = "your_paper_secret"
python .\paper_trade.py --model q_learning_model.json
```

For VS Code, create a workspace-root `.env` file containing:

```text
APCA_API_KEY_ID=your_paper_key
APCA_API_SECRET_KEY=your_paper_secret
```

The `.env` file is Git-ignored. Use `--submit-paper-order` only after reviewing the model, account, market data, and proposed order. Every newly trained model has `paper_ready: false` until it is explicitly validated and approved. Paper submission also requires `PAPER_TRADING_ENABLED=true`; the value must be set outside the model file. Pooled models are rejected for paper submission because their output cannot be mapped safely to one account position.

The `.github/workflows/paper-trader.yml` workflow runs a dry-run by schedule and can submit paper orders only through manual dispatch after repository secrets and `PAPER_TRADING_ENABLED=true` are configured. Paper-trading success is not live-trading proof.

## Tests and migration

Run the automated tests:

```powershell
python -m unittest tests.test_q_learning
```

Move and update older Desktop `tuner_runs` results:

```powershell
python .\migrate_runs.py
```

## Common troubleshooting

- **Cannot find `intraday_5m.sqlite`:** verify `STOCK_DB_PATH`, then reopen the terminal or VS Code.
- **Only one dependency line appears:** rerun from the project directory and ensure `q_learning.py` contains `if __name__ == "__main__": main()` at the end.
- **Old CSV header error:** the implementation can migrate supported old headers, or choose a new `--trial-log` path.
- **No run folder appears:** check that the command included valid arguments and that training did not fail before `create_run_directory()`.
- **No model archive appears:** archives are created only by a one-trial run that replaces an existing active model.

## Interpretation and safety

This program is a historical simulation. Net return, Sharpe, drawdown, and trade counts describe one chronological held-out period and do not establish future profitability. The random baseline and buy-and-hold comparisons are references, not guarantees of skill. Transaction costs, market gaps, position timing, and data quality can materially change results.

## Improvement log

All controlled experiments, code improvements, validation outcomes, and deployment decisions are recorded in `IMPROVEMENT_LOG.md`. Historical backtests remain non-deployment evidence until repeated out-of-sample performance is demonstrated.
