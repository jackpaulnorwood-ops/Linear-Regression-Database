"""Move existing tuner_runs data into the project-local runs directory."""

import csv
import json
import shutil
from pathlib import Path


def main() -> None:
    project = Path(__file__).resolve().parent
    old_root = Path.home() / "Desktop" / "llama" / "llama_alpaca" / "intraday" / "tuner_runs"
    new_root = project / "runs"
    new_root.mkdir(parents=True, exist_ok=True)

    moved = 0
    if old_root.is_dir():
        for source in sorted(old_root.iterdir()):
            if not source.is_dir() or not source.name.startswith("run_"):
                continue
            destination = new_root / source.name
            if destination.exists():
                continue
            shutil.move(str(source), str(destination))
            moved += 1

    trial_log = project / "q_learning_trials.csv"
    if trial_log.is_file():
        with trial_log.open("r", newline="", encoding="utf-8") as source:
            reader = csv.DictReader(source)
            fields = reader.fieldnames or []
            rows = list(reader)

        if "run_directory" in fields:
            with trial_log.open("w", newline="", encoding="utf-8") as target:
                writer = csv.DictWriter(target, fieldnames=fields)
                writer.writeheader()
                for row in rows:
                    old_directory = Path(row["run_directory"])
                    if old_directory.name.startswith("run_"):
                        row["run_directory"] = str(new_root / old_directory.name)
                    writer.writerow(row)

    archived = migrate_archives(project, trial_log)

    print(f"Moved {moved} run directory(ies) to {new_root}")
    print(f"Moved {archived} archived model(s) into trial folders")


def migrate_archives(project: Path, trial_log: Path) -> int:
    archive_root = project / "q_learning_model_archive"
    if not archive_root.is_dir():
        return 0

    rows = []
    if trial_log.is_file():
        with trial_log.open("r", newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))

    moved = 0
    for archive in sorted(archive_root.glob("*.json")):
        try:
            document = json.loads(archive.read_text(encoding="utf-8"))
            symbol = str(document.get("symbol", "")).upper()
        except (json.JSONDecodeError, OSError):
            continue

        matching = [
            row for row in rows
            if row.get("symbol", "").upper() == symbol
        ]
        if not matching:
            continue

        row = matching[-1]
        run_directory = Path(row["run_directory"])
        trial_number = int(row.get("trial_number", 1))
        destination = run_directory / f"trial_{trial_number:04d}" / "model_archive"
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / archive.name
        if not target.exists():
            shutil.move(str(archive), str(target))
            moved += 1

    try:
        archive_root.rmdir()
    except OSError:
        pass
    return moved


if __name__ == "__main__":
    main()
