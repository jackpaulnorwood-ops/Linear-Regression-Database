"""Display and search completed Q-learning trial analyses."""

import argparse
import csv
from pathlib import Path


def load_rows(log_path: Path) -> list[dict[str, str]]:
    if not log_path.is_file():
        raise FileNotFoundError(f"Trial log not found: {log_path}")
    with log_path.open("r", newline="", encoding="utf-8") as log_file:
        return list(csv.DictReader(log_file))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--log",
        type=Path,
        default=Path(__file__).resolve().parent / "q_learning_trials.csv",
        help="Trial CSV to read",
    )
    parser.add_argument("--trial", type=int, help="Show one trial by trial number")
    parser.add_argument("--latest", action="store_true", help="Show the latest trial")
    parser.add_argument("--search", help="Search trial analysis text")
    parser.add_argument("--top", type=int, default=10, help="Number of rows in rankings")
    parser.add_argument("--symbol", help="Filter by symbol or symbol-containing pooled model")
    parser.add_argument("--advice", action="store_true", help="Print tuning advice from the latest run")
    args = parser.parse_args()

    rows = load_rows(args.log)
    if not rows:
        print("No completed trials found.")
        return

    if args.trial is not None:
        matching = [row for row in rows if row.get("trial_number") == str(args.trial)]
        if not matching:
            raise SystemExit(f"Trial {args.trial} was not found.")
        selected = matching
    elif args.latest:
        selected = [rows[-1]]
    elif args.search:
        needle = args.search.lower()
        selected = [
            row
            for row in rows
            if needle in " ".join(row.values()).lower()
        ]
    else:
        selected = rows

    if args.symbol:
        symbol = args.symbol.upper()
        rows = [row for row in rows if symbol in row.get("symbol", "").upper().split("+")]
        if not rows:
            print(f"No trials found for {symbol}.")
            return

    for row in selected:
        print(f"\n=== Trial {row.get('trial_number', '?')} ===")
        print(f"Symbol: {row.get('symbol', '')}")
        print(f"Started: {row.get('run_started_at_utc', '')}")
        print(f"Seed: {row.get('seed', '')}")
        print(f"Test period: {row.get('test_start', '')} to {row.get('test_end', '')}")
        print(f"Net return: {row.get('agent_return_pct', '')}%")
        print(f"Buy-and-hold: {row.get('buy_hold_return_pct', '')}%")
        print(f"Random baseline: {row.get('random_return_pct', '')}%")
        print(f"Sharpe: {row.get('sharpe_ratio', '')}")
        print(f"Trades: {row.get('trades', '')}")
        print(f"Model: {row.get('model_path', '')}")
        print(f"Analysis: {row.get('trial_analysis', '')}")

    if args.advice:
        latest = rows[-1]
        advice = Path(latest["run_directory"]) / "tuning_advice.md"
        if not advice.is_file():
            raise SystemExit(f"Tuning advice not found: {advice}")
        print(advice.read_text(encoding="utf-8"))
        return

    if not args.trial and not args.latest and not args.search:
        ranked = sorted(
            rows,
            key=lambda row: float(row.get("agent_return_pct") or 0.0),
            reverse=True,
        )[: args.top]
        print("\n=== Top trials by net return ===")
        for position, row in enumerate(ranked, start=1):
            print(
                f"{position}. Trial {row.get('trial_number', '?')}: "
                f"{row.get('agent_return_pct', '')}% "
                f"(Sharpe {row.get('sharpe_ratio', '')}, "
                f"seed {row.get('seed', '')})"
            )


if __name__ == "__main__":
    main()
