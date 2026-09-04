"""Rebuild the derived revision log from immutable official snapshots."""

from __future__ import annotations

import argparse
import json
from itertools import pairwise
from pathlib import Path

import pandas as pd

from src.reconcile import REVISION_COLUMNS, compare_snapshots, snapshot_files

ROOT = Path(__file__).resolve().parents[1]


def snapshot_timestamp(path: Path) -> pd.Timestamp:
    stamp = path.stem.removeprefix("fatalities_")
    return pd.to_datetime(stamp, format="%Y%m%dT%H%M%SZ", utc=True).tz_localize(None)


def rebuild(data_dir: Path) -> pd.DataFrame:
    files = snapshot_files(data_dir)
    batches: list[pd.DataFrame] = []
    for previous_path, current_path in pairwise(files):
        previous = pd.read_parquet(previous_path)
        current = pd.read_parquet(current_path)
        changes = compare_snapshots(
            previous,
            current,
            previous_path.name,
            current_path.name,
            snapshot_timestamp(current_path),
        )
        if not changes.empty:
            batches.append(changes)

    revisions = (
        pd.concat(batches, ignore_index=True)
        if batches
        else pd.DataFrame(columns=REVISION_COLUMNS)
    )
    revisions = revisions.drop_duplicates("revision_id", keep="first").sort_values("observed_at")

    processed = data_dir / "processed"
    destination = processed / "revisions.parquet"
    temporary = destination.with_suffix(".parquet.tmp")
    revisions.to_parquet(temporary, index=False)
    temporary.replace(destination)

    status_path = processed / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["revision_log_rows"] = len(revisions)
    status["revisions_detected"] = (
        0
        if len(files) < 2
        else len(
            compare_snapshots(
                pd.read_parquet(files[-2]),
                pd.read_parquet(files[-1]),
                files[-2].name,
                files[-1].name,
                snapshot_timestamp(files[-1]),
            )
        )
    )
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return revisions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    revisions = rebuild(args.data_dir)
    print(f"Rebuilt {len(revisions)} revision rows from {len(snapshot_files(args.data_dir))} snapshots")


if __name__ == "__main__":
    main()
