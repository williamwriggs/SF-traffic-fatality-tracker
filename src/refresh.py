"""Refresh official data, preserve snapshots, and record revisions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from src.datasf import DataSFClient, DataSFError, normalize_fatal_victims, write_raw_snapshot
from src.metrics import combine_records
from src.provisional import as_tracker_records, flag_possible_matches, load_provisional
from src.reconcile import append_revision_log, compare_snapshots, snapshot_files

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIN_SNAPSHOT_RETENTION = 0.8


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def _validate_snapshot_transition(previous: pd.DataFrame, current: pd.DataFrame) -> None:
    """Stop a likely truncated response from replacing the last good snapshot."""
    if previous.empty:
        return
    retention = len(current) / len(previous)
    if retention < MIN_SNAPSHOT_RETENTION:
        raise DataSFError(
            "DataSF snapshot volume fell from "
            f"{len(previous)} to {len(current)} records ({retention:.1%} retained)"
        )


def refresh(data_dir: Path, start_year: int = 2014) -> dict[str, object]:
    data_dir = Path(data_dir)
    processed_dir = data_dir / "processed"
    snapshots_dir = processed_dir / "snapshots"
    processed_dir.mkdir(parents=True, exist_ok=True)
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    client = DataSFClient()
    prior_files = snapshot_files(data_dir)
    prior_path = prior_files[-1] if prior_files else None
    prior = pd.read_parquet(prior_path) if prior_path else pd.DataFrame()

    try:
        result = client.fetch_fatal_victims(start_year=start_year)
        official = normalize_fatal_victims(result.rows, result.fetched_at)
        _validate_snapshot_transition(prior, official)
    except DataSFError as exc:
        status_path = processed_dir / "status.json"
        old_status = json.loads(status_path.read_text()) if status_path.exists() else {}
        old_status.update(
            {
                "refresh_ok": False,
                "last_refresh_error": str(exc),
                "last_refresh_attempt": pd.Timestamp.now(tz="UTC").isoformat(),
            }
        )
        status_path.write_text(json.dumps(old_status, indent=2), encoding="utf-8")
        raise

    raw_path, manifest_path = write_raw_snapshot(result, data_dir)
    stamp = result.fetched_at.strftime("%Y%m%dT%H%M%SZ")
    snapshot_path = snapshots_dir / f"fatalities_{stamp}.parquet"
    _atomic_parquet(official, snapshot_path)
    _atomic_parquet(official, processed_dir / "fatalities.parquet")

    if prior_path:
        changes = compare_snapshots(
            prior,
            official,
            prior_path.name,
            snapshot_path.name,
            pd.Timestamp(result.fetched_at).tz_convert(None),
        )
    else:
        changes = pd.DataFrame(
            columns=[
                "revision_id",
                "observed_at",
                "snapshot_from",
                "snapshot_to",
                "record_id",
                "change_type",
                "field",
                "old_value",
                "new_value",
            ]
        )
    revisions = append_revision_log(processed_dir / "revisions.parquet", changes)

    provisional_path = data_dir / "provisional" / "incidents.csv"
    provisional = load_provisional(provisional_path)
    provisional_audit = flag_possible_matches(provisional, official)
    provisional_records = as_tracker_records(
        provisional_audit, pd.Timestamp(result.fetched_at).tz_convert(None)
    )
    combined = combine_records(official, provisional_records)
    _atomic_parquet(combined, processed_dir / "combined.parquet")
    _atomic_parquet(provisional_audit, processed_dir / "provisional_audit.parquet")

    source_as_of = official["source_updated_at"].max()
    source_loaded_at = official["source_loaded_at"].max()
    provisional_checked = provisional["last_checked"].max() if not provisional.empty else pd.NaT
    status = {
        "refresh_ok": True,
        "fetched_at": result.fetched_at.isoformat(),
        "source_data_as_of": None if pd.isna(source_as_of) else source_as_of.isoformat(),
        "source_loaded_at": None if pd.isna(source_loaded_at) else source_loaded_at.isoformat(),
        "provisional_checked_through": (
            None if pd.isna(provisional_checked) else provisional_checked.isoformat()
        ),
        "official_records": len(official),
        "open_provisional_records": len(provisional_records),
        "snapshot": snapshot_path.name,
        "raw_snapshot": str(raw_path.relative_to(data_dir)),
        "raw_manifest": str(manifest_path.relative_to(data_dir)),
        "revisions_detected": len(changes),
        "revision_log_rows": len(revisions),
    }
    (processed_dir / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--start-year", type=int, default=2014)
    args = parser.parse_args()
    try:
        status = refresh(args.data_dir, args.start_year)
    except DataSFError as exc:
        print(f"Refresh failed; existing processed data was preserved: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
