"""Train and backtest a tabular Q-learning policy on local five-minute bars."""

import argparse
import csv
from contextlib import redirect_stdout
import importlib.metadata
import json
import math
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


def ensure_requirements(requirements_path: Path) -> None:
    """Install requirement entries that are not already present."""
    if not requirements_path.is_file():
        print(f"Dependency file not found: {requirements_path}", flush=True)
        return

    missing: list[str] = []
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        requirement = raw_line.strip()
        if not requirement or requirement.startswith("#"):
            continue

        distribution_name = re.split(r"[<>=!~;\s\[]", requirement, maxsplit=1)[0]
        if not distribution_name:
            continue
        try:
            importlib.metadata.version(distribution_name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(requirement)

    if not missing:
        print("All packages in requirements.txt are already installed.", flush=True)
        return

    print("Installing missing packages: " + ", ".join(missing), flush=True)
    subprocess.run([sys.executable, "-m", "pip", "install", *missing], check=True)


ensure_requirements(Path(__file__).resolve().parent / "requirements.txt")

import numpy as np
import pandas as pd

from explore_stocks import DB_PATH, DB_URI

FEATURES = [
    "return_1_pct",
    "return_3_pct",
    "return_12_pct",
    "volatility_12_pct",
]
BIN_QUANTILES = (0.2, 0.4, 0.6, 0.8)
FIVE_MINUTES = pd.Timedelta(minutes=5)
MODEL_VERSION = 1
TRIAL_LOG_FIELDS = [
    "trial_number",
    "run_directory",
    "compute_device",
    "run_started_at_utc",
    "training_duration_seconds",
    "symbol",
    "episodes",
    "epsilon_start",
    "epsilon_end",
    "entry_bonus_bps",
    "epsilon_guidance",
    "sharpe_definition",
    "trial_analysis",
    "learning_rate",
    "discount",
    "transaction_cost_bps",
    "seed",
    "training_sessions",
    "training_bars",
    "training_start",
    "training_end",
    "test_sessions",
    "test_bars",
    "test_start",
    "test_end",
    "agent_return_pct",
    "buy_hold_return_pct",
    "random_return_pct",
    "sharpe_ratio",
    "random_sharpe_ratio",
    "max_drawdown_pct",
    "trades",
    "entries",
    "exits",
    "winning_trades",
    "losing_trades",
    "breakeven_trades",
    "win_rate_pct",
    "average_trade_return_pct",
    "profit_factor",
    "average_trades_per_session",
    "sessions_without_trades",
    "exposure_pct",
    "positive_sessions",
    "negative_sessions",
    "model_path",
]


def load_bars(symbol: str, db_path: Path = DB_PATH, db_uri: str = DB_URI) -> pd.DataFrame:
    if not db_path.is_file():
        raise FileNotFoundError(f"Cannot see database: {db_path}")

    with sqlite3.connect(db_uri, uri=True) as conn:
        conn.execute("PRAGMA query_only = ON")
        return pd.read_sql_query(
            """
            SELECT symbol, ts_utc, high, low, close, volume
            FROM bars_5m
            WHERE symbol = ?
            ORDER BY ts_utc ASC
            """,
            conn,
            params=(symbol,),
        )


def prepare_bars(bars: pd.DataFrame, require_next: bool = True) -> pd.DataFrame:
    required = {"ts_utc", "high", "low", "close", "volume"}
    missing = required.difference(bars.columns)
    if missing:
        raise ValueError(f"Bar data is missing columns: {', '.join(sorted(missing))}")

    data = bars.copy()
    data["timestamp"] = pd.to_datetime(data["ts_utc"], utc=True, errors="coerce")
    for column in ("high", "low", "close", "volume"):
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data = (
        data.dropna(subset=["timestamp", "high", "low", "close", "volume"])
        .sort_values("timestamp")
        .drop_duplicates("timestamp", keep="last")
    )
    local_time = data["timestamp"].dt.tz_convert("America/New_York")
    market_minutes = local_time.dt.hour * 60 + local_time.dt.minute
    data = data.loc[
        (market_minutes >= 9 * 60 + 30) & (market_minutes < 16 * 60)
    ].copy()
    data["session_date"] = local_time.loc[data.index].dt.date

    sessions = []
    for _, day in data.groupby("session_date", sort=True):
        day = day.sort_values("timestamp").copy()
        close = day["close"]
        gaps = day["timestamp"].diff().eq(FIVE_MINUTES)

        day["return_1_pct"] = close.pct_change() * 100
        day["return_3_pct"] = (close / close.shift(3) - 1) * 100
        day["return_12_pct"] = (close / close.shift(12) - 1) * 100
        day["volatility_12_pct"] = (
            day["return_1_pct"].rolling(12, min_periods=12).std()
        )
        day["consecutive_history"] = (
            gaps.rolling(12, min_periods=12).sum().eq(12)
        )
        day["next_return_pct"] = (close.shift(-1) / close - 1) * 100
        day["next_bar_valid"] = day["timestamp"].shift(-1).sub(
            day["timestamp"]
        ).eq(FIVE_MINUTES)
        sessions.append(day)

    if not sessions:
        raise ValueError("No regular-hours stock bars were found.")

    prepared = pd.concat(sessions, ignore_index=True)
    valid_rows = (
        prepared["consecutive_history"]
        & prepared[FEATURES].notna().all(axis=1)
    )
    if require_next:
        valid_rows &= prepared["next_bar_valid"] & prepared["next_return_pct"].notna()
    prepared = prepared.loc[valid_rows].copy()
    if prepared.empty:
        raise ValueError("No valid consecutive five-minute feature windows were found.")
    return prepared.reset_index(drop=True)


def fit_feature_bins(training_data: pd.DataFrame) -> dict[str, list[float]]:
    return {
        feature: [
            float(value)
            for value in np.quantile(training_data[feature], BIN_QUANTILES)
        ]
        for feature in FEATURES
    }


def state_key(row: pd.Series, position: int, bins: dict[str, list[float]]) -> str:
    feature_bins = [
        int(np.searchsorted(bins[feature], row[feature], side="right"))
        for feature in FEATURES
    ]
    return ",".join(str(value) for value in (*feature_bins, position))


class QLearningAgent:
    """Tabular Q-learning with actions representing target flat/long exposure."""

    def __init__(
        self,
        bins: dict[str, list[float]],
        learning_rate: float = 0.1,
        discount: float = 0.95,
        seed: int = 0,
    ) -> None:
        self.bins = bins
        self.learning_rate = learning_rate
        self.discount = discount
        self.q_values: dict[str, list[float]] = {}
        self.rng = np.random.default_rng(seed)

    def values(self, key: str) -> list[float]:
        return self.q_values.setdefault(key, [0.0, 0.0])

    def choose_action(self, key: str, epsilon: float = 0.0) -> int:
        if self.rng.random() < epsilon:
            return int(self.rng.integers(0, 2))
        return int(np.argmax(self.values(key)))

    def update(
        self, key: str, action: int, reward: float, next_key: str, terminal: bool
    ) -> None:
        next_value = 0.0 if terminal else max(self.values(next_key))
        current = self.values(key)[action]
        self.q_values[key][action] = current + self.learning_rate * (
            reward + self.discount * next_value - current
        )

    def predict(self, row: pd.Series, position: int) -> int:
        return int(np.argmax(self.values(state_key(row, position, self.bins))))

    def save(self, path: Path, symbol: str, transaction_cost_bps: float) -> None:
        if path.exists():
            archive_directory = path.resolve().parent / "q_learning_model_archive"
            archive_directory.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            archive_path = archive_directory / f"{path.stem}_{timestamp}.json"
            suffix = 1
            while archive_path.exists():
                archive_path = archive_directory / f"{path.stem}_{timestamp}_{suffix:02d}.json"
                suffix += 1
            shutil.copy2(path, archive_path)

        document = {
            "version": MODEL_VERSION,
            "symbol": symbol,
            "features": FEATURES,
            "bins": self.bins,
            "q_values": self.q_values,
            "transaction_cost_bps": transaction_cost_bps,
            "learning_rate": self.learning_rate,
            "discount": self.discount,
        }
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> tuple["QLearningAgent", dict]:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("version") != MODEL_VERSION:
            raise ValueError(f"Unsupported model version in {path}")
        if document.get("features") != FEATURES:
            raise ValueError(f"Model features do not match this implementation: {path}")
        agent = cls(document["bins"], document["learning_rate"], document["discount"])
        agent.q_values = document["q_values"]
        return agent, document


class RandomPolicy:
    """Uniform random flat/long target baseline for held-out comparisons."""

    def __init__(self, seed: int) -> None:
        self.rng = np.random.default_rng(seed)

    def predict(self, row: pd.Series, position: int) -> int:
        del row, position
        return int(self.rng.integers(0, 2))


def _session_rows(data: pd.DataFrame):
    if "symbol" in data.columns:
        for _, session in data.groupby(["symbol", "session_date"], sort=True):
            yield session.reset_index(drop=True)
    else:
        for _, session in data.groupby("session_date", sort=True):
            yield session.reset_index(drop=True)


def training_reward(
    position: int,
    next_position: int,
    next_return_pct: float,
    transaction_cost_bps: float,
    entry_bonus_bps: float,
    terminal: bool,
) -> float:
    costs_pct = transaction_cost_bps / 100
    reward = next_position * next_return_pct
    reward -= abs(next_position - position) * costs_pct
    if position == 0 and next_position == 1:
        reward += entry_bonus_bps / 100
    if terminal and next_position:
        reward -= costs_pct
    return float(reward)


def append_trial_log(path: Path, trial: dict[str, object]) -> None:
    missing = set(TRIAL_LOG_FIELDS).difference(trial)
    if missing:
        raise ValueError(f"Trial log row is missing fields: {', '.join(sorted(missing))}")

    path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not path.exists() or path.stat().st_size == 0

    if not needs_header:
        with path.open("r", newline="", encoding="utf-8") as log_file:
            reader = csv.DictReader(log_file)
            existing_header = reader.fieldnames or []
            existing_rows = list(reader)

        if existing_header != TRIAL_LOG_FIELDS:
            # Upgrade an older q_learning_trials.csv rather than silently losing
            # existing rows or raising an avoidable header error.
            old_fields = set(existing_header)
            new_fields = set(TRIAL_LOG_FIELDS)
            unknown_fields = old_fields.difference(new_fields)
            if unknown_fields:
                raise ValueError(
                    f"Trial log columns in {path} contain unknown fields: "
                    f"{', '.join(sorted(unknown_fields))}."
                )

            with path.open("w", newline="", encoding="utf-8") as log_file:
                writer = csv.DictWriter(log_file, fieldnames=TRIAL_LOG_FIELDS)
                writer.writeheader()
                for existing_row in existing_rows:
                    writer.writerow(
                        {
                            field: existing_row.get(field, "")
                            for field in TRIAL_LOG_FIELDS
                        }
                    )

    with path.open("a", newline="", encoding="utf-8") as log_file:
        writer = csv.DictWriter(log_file, fieldnames=TRIAL_LOG_FIELDS)
        if needs_header:
            writer.writeheader()
        writer.writerow({field: trial[field] for field in TRIAL_LOG_FIELDS})


class Tee:
    def __init__(self, *streams) -> None:
        self.streams = streams

    def write(self, text: str) -> int:
        for stream in self.streams:
            stream.write(text)
            if "\n" in text:
                stream.flush()
        return len(text)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()


def create_run_directory(run_root: Path) -> Path:
    run_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    candidate = run_root / f"run_{timestamp}"
    suffix = 1
    while candidate.exists():
        candidate = run_root / f"run_{timestamp}_{suffix:02d}"
        suffix += 1
    candidate.mkdir()
    return candidate


def run_trial(
    *,
    trial_number: int,
    total_trials: int,
    run_directory: Path,
    training_data: pd.DataFrame,
    test_data: pd.DataFrame,
    bins: dict[str, list[float]],
    args: argparse.Namespace,
    trial_log_path: Path,
) -> dict[str, object]:
    trial_directory = run_directory / f"trial_{trial_number:04d}"
    trial_directory.mkdir()
    log_path = trial_directory / "train.log"
    model_path = trial_directory / "q_learning_model.json"
    seed = args.seed + trial_number - 1
    started_at = datetime.now(timezone.utc)
    test_dates = sorted(test_data["session_date"].unique())
    train_dates = sorted(training_data["session_date"].unique())
    training_sessions = len(train_dates)
    training_started = time.perf_counter()

    with log_path.open("w", encoding="utf-8", buffering=1) as log_file:
        with redirect_stdout(Tee(sys.stdout, log_file)):
            try:
                print(f"Trial {trial_number}/{total_trials} started: {started_at.isoformat()}")
                print(f"Symbol: {args.symbol}; compute device: CPU")
                print(
                    "Tabular Q-learning uses sequential table updates; GPU execution "
                    "is not used."
                )
                print(
                    f"Episodes: {args.episodes}; seed: {seed}; "
                    f"epsilon: {args.epsilon_start} -> {args.epsilon_end}; "
                    f"transaction cost: {args.cost_bps} bps; "
                    f"entry bonus: {args.entry_bonus_bps} bps"
                )
                print(
                    f"Training: {training_sessions} sessions, {len(training_data)} bars "
                    f"({min(train_dates)} to {max(train_dates)})"
                )
                print(
                    f"Test: {len(test_dates)} sessions, {len(test_data)} bars "
                    f"({min(test_dates)} to {max(test_dates)})"
                )

                def report_progress(completed: int, total: int, epsilon: float) -> None:
                    elapsed = time.perf_counter() - training_started
                    estimated_total = elapsed / completed * total
                    remaining = max(0.0, estimated_total - elapsed)
                    print(
                        f"Training progress: episode {completed}/{total} "
                        f"({completed / total:.0%}), epsilon={epsilon:.3f}, "
                        f"elapsed={elapsed / 60:.1f} min, ETA={remaining / 60:.1f} min",
                        flush=True,
                    )

                agent = train_agent(
                    training_data,
                    bins,
                    episodes=args.episodes,
                    epsilon_start=args.epsilon_start,
                    epsilon_end=args.epsilon_end,
                    entry_bonus_bps=args.entry_bonus_bps,
                    transaction_cost_bps=args.cost_bps,
                    seed=seed,
                    progress_callback=report_progress,
                )
                training_duration = time.perf_counter() - training_started
                report = backtest(agent, test_data, args.cost_bps)
                random_report = backtest(
                    RandomPolicy(seed + 1_000_000), test_data, args.cost_bps
                )
                agent.save(model_path, args.symbol, args.cost_bps)

                if total_trials == 1:
                    active_path = args.model if args.model.is_absolute() else Path(__file__).resolve().parent / args.model
                    active_path.parent.mkdir(parents=True, exist_ok=True)
                    if active_path.exists():
                        archive_directory = trial_directory / "model_archive"
                        archive_directory.mkdir(parents=True, exist_ok=True)
                        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                        archive_path = archive_directory / f"{active_path.stem}_{timestamp}.json"
                        suffix = 1
                        while archive_path.exists():
                            archive_path = archive_directory / f"{active_path.stem}_{timestamp}_{suffix:02d}.json"
                            suffix += 1
                        shutil.copy2(active_path, archive_path)
                    shutil.copy2(model_path, active_path)
               

                epsilon_guidance = (
                    "No universal optimum: epsilon is the training-time random-action "
                    "chance, not decision quality. This run linearly decays the "
                    "configured start to end; compare schedules across multiple seeds "
                    "using validation data. Backtest prediction is greedy (epsilon=0)."
                )
                sharpe_definition = (
                    "Annualized mean daily net return divided by daily return standard "
                    "deviation (252 sessions/year, 0% risk-free rate); not prediction "
                    "accuracy and not itself a comparison against random."
                )
                if report["agent_return_pct"] > random_report["agent_return_pct"]:
                    baseline_analysis = (
                        "The learned policy beat the seeded random flat/long baseline."
                    )
                elif report["agent_return_pct"] < random_report["agent_return_pct"]:
                    baseline_analysis = (
                        "The learned policy lagged the seeded random flat/long baseline."
                    )
                else:
                    baseline_analysis = (
                        "The learned policy matched the seeded random flat/long baseline."
                    )
                if report["trades"] == 0:
                    activity_analysis = (
                        "The learned policy made no trades and stayed flat; its return "
                        "and Sharpe should not be interpreted as evidence of skill."
                    )
                else:
                    activity_analysis = (
                        f"The policy completed {report['trades']} round-trip trades "
                        f"with {report['exposure_pct']:.1f}% market exposure."
                    )
                trial_analysis = (
                    f"{baseline_analysis} {activity_analysis} Learned net return "
                    f"{report['agent_return_pct']:.3f}% versus random "
                    f"{random_report['agent_return_pct']:.3f}% and buy-and-hold "
                    f"{report['buy_hold_return_pct']:.3f}%. This is one seed on one "
                    "held-out period, not conclusive evidence of future performance."
                )
                trial = {
                    "trial_number": trial_number,
                    "run_directory": str(run_directory),
                    "compute_device": "cpu",
                    "run_started_at_utc": started_at.isoformat(),
                    "training_duration_seconds": round(training_duration, 3),
                    "symbol": args.symbol,
                    "episodes": args.episodes,
                    "epsilon_start": args.epsilon_start,
                    "epsilon_end": args.epsilon_end,
                    "entry_bonus_bps": args.entry_bonus_bps,
                    "epsilon_guidance": epsilon_guidance,
                    "sharpe_definition": sharpe_definition,
                    "trial_analysis": trial_analysis,
                    "learning_rate": 0.1,
                    "discount": 0.95,
                    "transaction_cost_bps": args.cost_bps,
                    "seed": seed,
                    "training_sessions": training_sessions,
                    "training_bars": len(training_data),
                    "training_start": min(train_dates),
                    "training_end": max(train_dates),
                    "test_sessions": len(test_dates),
                    "test_bars": len(test_data),
                    "test_start": min(test_dates),
                    "test_end": max(test_dates),
                    "random_return_pct": random_report["agent_return_pct"],
                    "random_sharpe_ratio": random_report["sharpe_ratio"],
                    "model_path": str(model_path),
                    **report,
                }

                result_label = (
                    "PROFIT"
                    if report["agent_return_pct"] > 1e-12
                    else "LOSS"
                    if report["agent_return_pct"] < -1e-12
                    else "BREAK-EVEN"
                )
                print("\n=== Held-out backtest ===")
                print(f"Net result: {result_label} ({report['agent_return_pct']:.2f}%)")
                print(f"Buy-and-hold return: {report['buy_hold_return_pct']:.2f}%")
                print(f"Random flat/long return: {random_report['agent_return_pct']:.2f}%")
                print(f"Annualized Sharpe: {report['sharpe_ratio']:.3f}")
                print(f"Random baseline Sharpe: {random_report['sharpe_ratio']:.3f}")
                print(f"Maximum drawdown: {report['max_drawdown_pct']:.2f}%")
                print(f"Completed trades: {report['trades']}")
                print(f"Entries: {report['entries']}; exits: {report['exits']}")
                print(f"Win rate: {report['win_rate_pct']:.1f}%")
                print(f"Average trades/session: {report['average_trades_per_session']:.2f}")
                print(f"Time in market: {report['exposure_pct']:.1f}%")
                print(f"Analysis: {trial_analysis}")
                print(f"Epsilon: {epsilon_guidance}")
                print(f"Sharpe: {sharpe_definition}")
                print(f"Saved model: {model_path}")
                print("Past simulated performance does not establish future profitability.")

                append_trial_log(trial_log_path, trial)
                print(f"Trial summary appended to {trial_log_path}")
                write_trial_analysis(run_directory, trial_directory, trial)
                print(f"Trial analysis written to {trial_directory / 'analysis.md'}")
                return trial
            except Exception as exc:
                print(f"TRIAL FAILED: {type(exc).__name__}: {exc}", flush=True)
                raise


def write_trial_analysis(run_directory: Path, trial_directory: Path, trial: dict[str, object]) -> None:
    """Write searchable human-readable analysis files for one completed trial."""
    trial_number = int(trial["trial_number"])
    analysis = str(trial["trial_analysis"])
    analysis_path = trial_directory / "analysis.md"

    analysis_path.write_text(
        "# Trial analysis\n\n"
        f"- **Trial:** {trial_number}\n"
        f"- **Run:** {run_directory}\n"
        f"- **Started:** {trial['run_started_at_utc']}\n"
        f"- **Symbol:** {trial['symbol']}\n"
        f"- **Seed:** {trial['seed']}\n"
        f"- **Episodes:** {trial['episodes']}\n"
        f"- **Test period:** {trial['test_start']} to {trial['test_end']}\n"
        f"- **Net return:** {float(trial['agent_return_pct']):.3f}%\n"
        f"- **Buy-and-hold:** {float(trial['buy_hold_return_pct']):.3f}%\n"
        f"- **Random baseline:** {float(trial['random_return_pct']):.3f}%\n"
        f"- **Sharpe:** {float(trial['sharpe_ratio']):.3f}\n"
        f"- **Trades:** {trial['trades']}\n\n"
        "## Analysis\n\n"
        f"{analysis}\n\n"
        "## Interpretation notes\n\n"
        f"- **Epsilon:** {trial['epsilon_guidance']}\n"
        f"- **Sharpe:** {trial['sharpe_definition']}\n",
        encoding="utf-8",
    )

    run_index = run_directory / "analyses.md"
    with run_index.open("a", encoding="utf-8") as index_file:
        index_file.write(
            f"## Trial {trial_number}: {trial['symbol']} (seed {trial['seed']})\n\n"
            f"- **Net return:** {float(trial['agent_return_pct']):.3f}%\n"
            f"- **Sharpe:** {float(trial['sharpe_ratio']):.3f}\n"
            f"- **Trades:** {trial['trades']}\n"
            f"- **Details:** [`{analysis_path.name}`](trial_{trial_number:04d}/analysis.md)\n\n"
            f"{analysis}\n\n"
        )


def train_agent(
    training_data: pd.DataFrame,
    bins: dict[str, list[float]],
    episodes: int = 200,
    learning_rate: float = 0.1,
    discount: float = 0.95,
    epsilon_start: float = 1.0,
    epsilon_end: float = 0.05,
    entry_bonus_bps: float = 0.0,
    transaction_cost_bps: float = 5.0,
    seed: int = 0,
    progress_callback: Callable[[int, int, float], None] | None = None,
) -> QLearningAgent:
    if episodes < 1:
        raise ValueError("episodes must be at least 1")
    if entry_bonus_bps < 0:
        raise ValueError("entry_bonus_bps cannot be negative")
    sessions = list(_session_rows(training_data))
    agent = QLearningAgent(bins, learning_rate, discount, seed)
    progress_interval = max(1, math.ceil(episodes / 20))

    for episode in range(episodes):
        fraction = episode / max(episodes - 1, 1)
        epsilon = epsilon_start + fraction * (epsilon_end - epsilon_start)
        for session in sessions:
            position = 0
            for index in range(len(session)):
                row = session.iloc[index]
                key = state_key(row, position, bins)
                action = agent.choose_action(key, epsilon)
                next_position = action
                terminal = index == len(session) - 1
                reward = training_reward(
                    position,
                    next_position,
                    float(row["next_return_pct"]),
                    transaction_cost_bps,
                    entry_bonus_bps,
                    terminal,
                )
                if terminal:
                    next_key = ""
                else:
                    next_row = session.iloc[index + 1]
                    next_key = state_key(next_row, next_position, bins)
                agent.update(key, action, reward, next_key, terminal)
                position = next_position

        completed = episode + 1
        if progress_callback and (
            completed % progress_interval == 0 or completed == episodes
        ):
            progress_callback(completed, episodes, epsilon)

    return agent


def backtest(
    agent: QLearningAgent | RandomPolicy,
    test_data: pd.DataFrame,
    transaction_cost_bps: float = 5.0,
) -> dict[str, float | int | list[int]]:
    costs_pct = transaction_cost_bps / 100
    equity = 1.0
    buy_hold = 1.0
    entries = 0
    exits = 0
    returns = []
    trade_returns = []
    daily_trade_counts = []
    daily_returns = []
    invested_bars = 0

    for session in _session_rows(test_data):
        position = 0
        trade_equity = None
        session_entries = 0
        session_equity_before = equity
        for index, row in session.iterrows():
            action = agent.predict(row, position)
            reward = action * row["next_return_pct"]
            if action != position:
                reward -= costs_pct
                if action:
                    entries += 1
                    session_entries += 1
                    trade_equity = 1.0
                else:
                    exits += 1
            if index == len(session) - 1 and action:
                reward -= costs_pct
                exits += 1
            reward = float(reward)
            multiplier = max(0.0, 1 + reward / 100)
            equity *= multiplier
            returns.append(reward)
            if action:
                invested_bars += 1
                if trade_equity is None:
                    raise RuntimeError("Backtest position is long without an open trade.")
                trade_equity *= multiplier
            if (action == 0 and position == 1) or (
                index == len(session) - 1 and action == 1
            ):
                if trade_equity is None:
                    raise RuntimeError("Backtest closed a position without an open trade.")
                trade_returns.append((trade_equity - 1) * 100)
                trade_equity = None
            position = action

        daily_trade_counts.append(session_entries)
        daily_returns.append((equity / session_equity_before - 1) * 100)
        daily_gross = np.prod(1 + session["next_return_pct"].to_numpy() / 100)
        entry_and_exit = max(0.0, 1 - costs_pct / 100) ** 2
        buy_hold *= max(0.0, float(daily_gross) * entry_and_exit)

    peak = 1.0
    max_drawdown = 0.0
    running_equity = 1.0
    for value in returns:
        running_equity *= max(0.0, 1 + value / 100)
        peak = max(peak, running_equity)
        if peak:
            max_drawdown = max(max_drawdown, (peak - running_equity) / peak)

    winning_trades = [value for value in trade_returns if value > 1e-12]
    losing_trades = [value for value in trade_returns if value < -1e-12]
    breakeven_trades = len(trade_returns) - len(winning_trades) - len(losing_trades)
    gross_wins = sum(winning_trades)
    gross_losses = abs(sum(losing_trades))
    daily_volatility = float(np.std(daily_returns, ddof=1)) if len(daily_returns) > 1 else 0.0
    sharpe_ratio = (
        float(np.mean(daily_returns)) / daily_volatility * np.sqrt(252)
        if daily_volatility > 0
        else 0.0
    )

    return {
        "agent_return_pct": (equity - 1) * 100,
        "buy_hold_return_pct": (buy_hold - 1) * 100,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown_pct": max_drawdown * 100,
        "trades": len(trade_returns),
        "entries": entries,
        "exits": exits,
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "breakeven_trades": breakeven_trades,
        "win_rate_pct": (
            len(winning_trades) / len(trade_returns) * 100 if trade_returns else 0.0
        ),
        "average_trade_return_pct": (
            float(np.mean(trade_returns)) if trade_returns else 0.0
        ),
        "average_winning_trade_pct": (
            float(np.mean(winning_trades)) if winning_trades else 0.0
        ),
        "average_losing_trade_pct": (
            float(np.mean(losing_trades)) if losing_trades else 0.0
        ),
        "profit_factor": (
            gross_wins / gross_losses if gross_losses else (
                float("inf") if gross_wins else 0.0
            )
        ),
        "sessions": len(daily_trade_counts),
        "sessions_without_trades": sum(count == 0 for count in daily_trade_counts),
        "average_trades_per_session": (
            float(np.mean(daily_trade_counts)) if daily_trade_counts else 0.0
        ),
        "min_trades_per_session": min(daily_trade_counts, default=0),
        "max_trades_per_session": max(daily_trade_counts, default=0),
        "positive_sessions": sum(value > 1e-12 for value in daily_returns),
        "negative_sessions": sum(value < -1e-12 for value in daily_returns),
        "exposure_pct": (
            invested_bars / len(test_data) * 100 if len(test_data) else 0.0
        ),
        "daily_trade_counts": daily_trade_counts,
        "bars": len(test_data),
    }


def generate_tuning_recommendations(
    run_directory: Path,
    trials: list[dict[str, object]],
    args: argparse.Namespace,
) -> None:
    recommendations: list[dict[str, object]] = []
    if not trials:
        return

    best = max(trials, key=lambda trial: float(trial["agent_return_pct"]))
    worst = min(trials, key=lambda trial: float(trial["agent_return_pct"]))

    def add(parameter: str, current: float, suggested: float, reason: str) -> None:
        recommendations.append({
            "parameter": parameter,
            "current_value": current,
            "suggested_value": suggested,
            "direction": "increase" if suggested > current else "decrease" if suggested < current else "keep",
            "reason": reason,
            "confidence": "low",
        })

    average_return = sum(float(trial["agent_return_pct"]) for trial in trials) / len(trials)
    average_trades = sum(int(trial["trades"]) for trial in trials) / len(trials)

    if average_trades == 0:
        add("entry_bonus_bps", float(args.entry_bonus_bps), max(1.0, float(args.entry_bonus_bps) + 1.0),
            "No completed trades occurred; a small training-only entry bonus may encourage exploration of long positions.")
    elif average_trades > 250:
        add("cost_bps", float(args.cost_bps), float(args.cost_bps) + 5.0,
            "Average trial trade count was high; a larger cost can discourage churn, but it should be compared on validation data.")

    if float(best["agent_return_pct"]) <= 0:
        add("epsilon_end", float(args.epsilon_end), max(0.01, float(args.epsilon_end) - 0.02),
            "The best trial was not profitable; reducing final exploration can stabilize greedy behavior, but this remains an empirical result.")

    if not recommendations:
        add("episodes", float(args.episodes), float(args.episodes) * 2,
            "There was no strong rule violation; a larger episode count is a cautious next experiment rather than a proven improvement.")

    csv_path = run_directory / "tuning_recommendations.csv"
    fields = ["parameter", "current_value", "suggested_value", "direction", "reason", "confidence"]
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(recommendations)

    advice_path = run_directory / "tuning_advice.md"
    advice_path.write_text(
        "# Tuning recommendations\n\n"
        "These are rule-based hypotheses from this run, not guaranteed improvements.\n"
        "Compare them on held-out validation periods and never tune repeatedly against a final test set.\n\n"
        f"- **Trials compared:** {len(trials)}\n"
        f"- **Average net return:** {average_return:.3f}%\n"
        f"- **Best net return:** {float(best['agent_return_pct']):.3f}%\n"
        f"- **Worst net return:** {float(worst['agent_return_pct']):.3f}%\n"
        f"- **Average trades:** {average_trades:.1f}\n\n"
        + "\n".join(
            f"## {item['parameter']} — {item['direction']}\n"
            f"- Current: {item['current_value']}\n"
            f"- Suggested: {item['suggested_value']}\n"
            f"- Reason: {item['reason']}\n"
            f"- Confidence: {item['confidence']}\n"
            for item in recommendations
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="AAPL", help="Stock ticker (default: AAPL)")
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Train one pooled model on multiple tickers, for example --symbols AAPL MSFT RBLX",
    )
    parser.add_argument("--db", type=Path, default=DB_PATH, help="SQLite database path")
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("q_learning_model.json"),
        help="Model output path when running exactly one trial",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=5,
        help="Number of independent seeded runs (default: 5)",
    )
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path(__file__).resolve().parent / "runs",
        help="Parent directory for timestamped run and per-trial logs",
    )
    parser.add_argument(
        "--trial-log",
        type=Path,
        help="Optional CSV path for completed trial summaries (default: run folder/trials.csv)",
    )
    parser.add_argument("--episodes", type=int, default=200)
    parser.add_argument("--epsilon-start", type=float, default=1.0)
    parser.add_argument("--epsilon-end", type=float, default=0.05)
    parser.add_argument(
        "--entry-bonus-bps",
        type=float,
        default=0.0,
        help=(
            "Training-only reward bonus, in basis points, for flat-to-long entries "
            "(default: 0; backtest returns never include this bonus)"
        ),
    )
    parser.add_argument("--cost-bps", type=float, default=5.0)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be at least 1")
    if args.episodes < 1:
        parser.error("--episodes must be at least 1")
    if args.cost_bps < 0:
        parser.error("--cost-bps cannot be negative")
    if args.entry_bonus_bps < 0:
        parser.error("--entry-bonus-bps cannot be negative")
    if not 0 <= args.epsilon_start <= 1 or not 0 <= args.epsilon_end <= 1:
        parser.error("--epsilon-start and --epsilon-end must be between 0 and 1")

    run_directory = create_run_directory(args.run_root)
    (run_directory / "analyses.md").write_text(
        f"# Training analyses\n\n"
        f"- **Symbol:** {args.symbol}\n"
        f"- **Trials:** {args.trials}\n"
        f"- **Episodes per trial:** {args.episodes}\n"
        f"- **Seed:** {args.seed}\n\n",
        encoding="utf-8",
    )
    trial_log_path = args.trial_log or Path(__file__).resolve().parent / "q_learning_trials.csv"
    with (run_directory / "run.log").open("w", encoding="utf-8", buffering=1) as run_log:
        with redirect_stdout(Tee(sys.stdout, run_log)):
            print(f"Run directory: {run_directory}")
            print(f"Trials: {args.trials}; episodes per trial: {args.episodes}")
            print("Compute device: CPU (tabular Q-learning; GPU is not used)")
            print(f"Symbol: {args.symbol}; base seed: {args.seed}")
            print(f"Trial CSV: {trial_log_path}")

            db_uri = f"{args.db.resolve().as_uri()}?mode=ro&immutable=1"
            print(f"Loading bars from {args.db} ...", flush=True)
            symbols = args.symbols if args.symbols else [args.symbol]
            symbols = [symbol.upper() for symbol in symbols]
            args.symbol = "+".join(symbols)

            prepared_frames = []
            for symbol in symbols:
                symbol_samples = prepare_bars(load_bars(symbol, args.db, db_uri))
                symbol_samples = symbol_samples.copy()
                symbol_samples["symbol"] = symbol
                prepared_frames.append(symbol_samples)

            samples = pd.concat(prepared_frames, ignore_index=True)
            dates = sorted(samples["session_date"].unique())
            if len(dates) < 2:
                raise ValueError(
                    "At least two trading dates are required for a chronological split."
                )

            split_index = max(1, int(len(dates) * 0.8))
            if split_index == len(dates):
                split_index -= 1
            train_dates = set(dates[:split_index])
            training_data = samples.loc[samples["session_date"].isin(train_dates)]
            test_data = samples.loc[~samples["session_date"].isin(train_dates)]
            bins = fit_feature_bins(training_data)
            print(
                f"Data ready: {len(samples)} bars across {len(dates)} sessions; "
                f"train={len(training_data)} bars, test={len(test_data)} bars."
            )

            trial_summaries: list[dict[str, object]] = []
            for trial_number in range(1, args.trials + 1):
                trial_result = run_trial(
                    trial_number=trial_number,
                    total_trials=args.trials,
                    run_directory=run_directory,
                    training_data=training_data,
                    test_data=test_data,
                    bins=bins,
                    args=args,
                    trial_log_path=trial_log_path,
                )
                trial_summaries.append(trial_result)
            generate_tuning_recommendations(run_directory, trial_summaries, args)
            print(f"All {args.trials} trials completed.")
