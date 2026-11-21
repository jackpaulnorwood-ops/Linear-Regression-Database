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
distinct seeds. It creates a new run directory under
`~/Desktop/llama/llama_alpaca/intraday/tuner_runs`, with a `run.log`,
`trials.csv`, and one `trial_####/train.log` plus model per trial. Use
`--trials` to set the number of runs or `--run-root` to change the log
directory. A single trial saves to `q_learning_model.json` by default; with
multiple trials, each model is saved in its trial directory and none is
automatically selected using held-out test performance. It reports
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

## Reviewing training analyses

Every completed trial now saves an organized Markdown analysis in
`trial_####/analysis.md`, while the run directory also contains `analyses.md`
with a linked summary of every trial. The project-level `q_learning_trials.csv`
stores the same analysis plus sortable metrics for spreadsheet and terminal use.

View the latest result:

```bash
python view_trials.py --latest
```

View or search one specific result:

```bash
python view_trials.py --trial 1
python view_trials.py --search "random flat/long"
```

Running `python view_trials.py` prints all analyses followed by a ranking of the
highest-net-return trials.

## Multi-symbol pooled training

Train one shared tabular model on several symbols:

```bash
python q_learning.py --symbols AAPL MSFT RBLX --trials 5 --episodes 200
```

Each symbol contributes separate daily trading sessions, while the same Q-table and feature bins are shared. Use `--symbol AAPL` for a one-symbol experiment.

## Run organization

New runs are stored in `runs/run_YYYYMMDD_HHMMSS/` using UTC timestamps. Every run contains `run.log`, `analyses.md`, `trials.csv`, and `tuning_advice.md`. Each trial contains its model, analysis, log, and `model_archive/` for previous versions.

To migrate older Desktop `tuner_runs` folders, run:

```bash
python migrate_runs.py
```

## Tuning recommendations

After a run, review:

```bash
python view_trials.py --latest
python view_trials.py --advice
python view_trials.py --symbol AAPL
```

`tuning_advice.md` and `tuning_recommendations.csv` contain rule-based hypotheses. They are suggestions for further validation, not guaranteed parameter improvements.

## Trial visualizations

Each completed trial saves PNG charts inside:

```text
runs/run_YYYYMMDD_HHMMSS/trial_####/visualizations/
```

The visualizations include cumulative equity versus buy-and-hold and random baselines,
model drawdown, daily return distributions, completed trade outcomes, position/exposure
over time, and per-symbol comparisons for pooled models. The run folder also contains
`trial_comparison.png`, comparing net return, Sharpe, trades, and drawdown across trials.
