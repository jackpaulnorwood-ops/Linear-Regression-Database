import csv
import unittest
from tempfile import TemporaryDirectory
from argparse import Namespace
from pathlib import Path

import pandas as pd

from q_learning import (
    FEATURES,
    QLearningAgent,
    RandomPolicy,
    TRIAL_LOG_FIELDS,
    append_trial_log,
    backtest,
    create_run_directory,
    fit_feature_bins,
    prepare_bars,
    run_trial,
    state_key,
    train_agent,
    training_reward,
)


def make_bars(count: int = 40) -> pd.DataFrame:
    timestamps = pd.date_range(
        "2025-01-02 14:30:00+00:00", periods=count, freq="5min"
    )
    close = [100 + index * 0.1 for index in range(count)]
    return pd.DataFrame(
        {
            "ts_utc": timestamps,
            "high": [value + 0.1 for value in close],
            "low": [value - 0.1 for value in close],
            "close": close,
            "volume": [1000] * count,
        }
    )


class QLearningTests(unittest.TestCase):
    def test_prepare_bars_creates_consecutive_feature_windows(self):
        prepared = prepare_bars(make_bars())

        self.assertFalse(prepared.empty)
        self.assertTrue(prepared[FEATURES].notna().all().all())
        self.assertTrue(prepared["next_return_pct"].notna().all())
        self.assertTrue(prepared["next_bar_valid"].all())

    def test_live_features_keep_latest_bar_without_a_future_return(self):
        bars = make_bars()

        prepared = prepare_bars(bars, require_next=False)

        self.assertEqual(prepared.iloc[-1]["timestamp"], bars.iloc[-1]["ts_utc"])
        self.assertTrue(pd.isna(prepared.iloc[-1]["next_return_pct"]))

    def test_prepare_bars_excludes_gaps(self):
        bars = make_bars()
        missing_timestamp = bars.iloc[20]["ts_utc"]
        bars = bars.drop(index=20).reset_index(drop=True)

        prepared = prepare_bars(bars)
        after_gap = prepared.loc[prepared["timestamp"] > missing_timestamp]

        self.assertEqual(after_gap["timestamp"].min(), bars.iloc[32]["ts_utc"])

    def test_training_and_backtest_produce_finite_metrics(self):
        prepared = prepare_bars(make_bars())
        bins = fit_feature_bins(prepared)
        agent = train_agent(prepared, bins, episodes=4, seed=7)
        report = backtest(agent, prepared)

        self.assertTrue(agent.q_values)
        self.assertTrue(pd.notna(report["agent_return_pct"]))
        self.assertGreaterEqual(report["trades"], 0)

    def test_entry_bonus_only_changes_training_entry_reward(self):
        entry_without_bonus = training_reward(0, 1, 0.0, 5.0, 0.0, False)
        entry_with_bonus = training_reward(0, 1, 0.0, 5.0, 2.0, False)
        hold_with_bonus = training_reward(1, 1, 0.0, 5.0, 2.0, False)
        exit_with_bonus = training_reward(1, 0, 0.0, 5.0, 2.0, False)

        self.assertAlmostEqual(entry_without_bonus, -0.05)
        self.assertAlmostEqual(entry_with_bonus, -0.03)
        self.assertEqual(hold_with_bonus, 0.0)
        self.assertAlmostEqual(exit_with_bonus, -0.05)

    def test_training_reports_progress_at_intervals_and_completion(self):
        prepared = prepare_bars(make_bars())
        bins = fit_feature_bins(prepared)
        progress = []

        train_agent(
            prepared,
            bins,
            episodes=21,
            seed=7,
            progress_callback=lambda completed, total, epsilon: progress.append(
                (completed, total, epsilon)
            ),
        )

        self.assertEqual([item[0] for item in progress], [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 21])
        self.assertTrue(all(item[1] == 21 for item in progress))
        self.assertAlmostEqual(progress[-1][2], 0.05)

    def test_backtest_reports_round_trips_and_net_trade_outcomes(self):
        bins = {
            feature: [value + 0.5 for value in range(7)]
            for feature in FEATURES
        }
        agent = QLearningAgent(bins)
        actions = [1, 1, 0, 0, 0, 1, 1, 0]
        returns = [3.0, 2.0, 0.0, 0.0, 0.0, -1.0, -1.0, 0.0]
        dates = [pd.Timestamp("2025-01-02").date()] * 4
        dates += [pd.Timestamp("2025-01-03").date()] * 4
        rows = []
        for index, (action, next_return) in enumerate(zip(actions, returns)):
            row = {feature: index + 0.1 for feature in FEATURES}
            row.update(session_date=dates[index], next_return_pct=next_return)
            rows.append(row)
            for position in (0, 1):
                key = state_key(pd.Series(row), position, bins)
                agent.q_values[key] = [1.0, 0.0] if action == 0 else [0.0, 1.0]

        report = backtest(agent, pd.DataFrame(rows), transaction_cost_bps=5.0)

        self.assertEqual(report["trades"], 2)
        self.assertEqual(report["entries"], 2)
        self.assertEqual(report["exits"], 2)
        self.assertEqual(report["winning_trades"], 1)
        self.assertEqual(report["losing_trades"], 1)
        self.assertEqual(report["breakeven_trades"], 0)
        self.assertEqual(report["daily_trade_counts"], [1, 1])
        self.assertGreater(report["agent_return_pct"], 0)
        self.assertEqual(report["exposure_pct"], 50.0)
        self.assertNotEqual(report["sharpe_ratio"], 0.0)

    def test_random_policy_baseline_is_seeded_and_has_backtest_metrics(self):
        prepared = prepare_bars(make_bars())
        first = backtest(RandomPolicy(11), prepared)
        second = backtest(RandomPolicy(11), prepared)

        self.assertEqual(first["agent_return_pct"], second["agent_return_pct"])
        self.assertIn("sharpe_ratio", first)
        self.assertIn("trades", first)

    def test_trial_log_appends_rows_with_one_header(self):
        trial = {field: "" for field in TRIAL_LOG_FIELDS}
        trial.update(symbol="AAPL", episodes=200, agent_return_pct=1.25)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "logs" / "trials.csv"

            append_trial_log(path, trial)
            append_trial_log(path, trial)

            with path.open(newline="", encoding="utf-8") as log_file:
                rows = list(csv.DictReader(log_file))

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["symbol"], "AAPL")
        self.assertEqual(rows[1]["agent_return_pct"], "1.25")

    def test_run_trial_writes_incremental_log_and_model(self):
        samples = prepare_bars(make_bars())
        bins = fit_feature_bins(samples)
        args = Namespace(
            model=Path("unused-default-model.json"),
            symbol="AAPL",
            episodes=2,
            epsilon_start=1.0,
            epsilon_end=0.05,
            entry_bonus_bps=1.0,
            cost_bps=5.0,
            seed=10,
        )

        with TemporaryDirectory() as directory:
            run_directory = create_run_directory(Path(directory))
            trial_csv = run_directory / "trials.csv"
            run_trial(
                trial_number=1,
                total_trials=2,
                run_directory=run_directory,
                training_data=samples,
                test_data=samples,
                bins=bins,
                args=args,
                trial_log_path=trial_csv,
            )

            log_path = run_directory / "trial_0001" / "train.log"
            model_path = run_directory / "trial_0001" / "q_learning_model.json"
            with trial_csv.open(newline="", encoding="utf-8") as log_file:
                rows = list(csv.DictReader(log_file))

            self.assertTrue(log_path.is_file())
            self.assertIn("Training progress: episode 2/2", log_path.read_text())
            self.assertTrue(model_path.is_file())
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["compute_device"], "cpu")
            self.assertEqual(rows[0]["entry_bonus_bps"], "1.0")

    def test_model_round_trip_preserves_q_values(self):
        bins = {feature: [0.0, 1.0, 2.0, 3.0] for feature in FEATURES}
        agent = QLearningAgent(bins)
        key = state_key(pd.Series({feature: 1.5 for feature in FEATURES}), 0, bins)
        agent.q_values[key] = [0.25, 0.75]

        with TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            agent.save(path, "AAPL", 5.0)
            restored, metadata = QLearningAgent.load(path)

        self.assertEqual(restored.q_values[key], [0.25, 0.75])
        self.assertEqual(metadata["symbol"], "AAPL")

    def test_saving_model_archives_previous_model(self):
        bins = {feature: [0.0, 1.0, 2.0, 3.0] for feature in FEATURES}
        agent = QLearningAgent(bins)

        with TemporaryDirectory() as directory:
            path = Path(directory) / "q_learning_model.json"
            agent.save(path, "AAPL", 5.0)
            agent.q_values["new-state"] = [0.25, 0.75]
            agent.save(path, "AAPL", 5.0)

            archive_directory = Path(directory) / "q_learning_model_archive"
            archives = list(archive_directory.glob("q_learning_model_*.json"))

        self.assertEqual(len(archives), 1)


if __name__ == "__main__":
    unittest.main()
