"""Snapshot comparison and immutable revision logging."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

TRACKED_FIELDS = [
    "collision_date",
    "death_date",
    "normalized_mode",
    "native_party_type",
    "native_victim_role",
    "native_vehicle_type",
    "latitude",
    "longitude",
    "location",
    "neighborhood",
    "supervisor_district",
    "classification_status",
]


def _display(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value)


def _revision_id(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]


def compare_snapshots(
    previous: pd.DataFrame,
    current: pd.DataFrame,
    previous_name: str,
    current_name: str,
    observed_at: pd.Timestamp,
) -> pd.DataFrame:
    columns = [
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
    if previous.empty and current.empty:
        return pd.DataFrame(columns=columns)
    old = previous.set_index("record_id", drop=False)
    new = current.set_index("record_id", drop=False)
    changes: list[dict[str, object]] = []

    def add_change(record_id: str, kind: str, field: str, old_value: str, new_value: str) -> None:
        parts = [previous_name, current_name, record_id, kind, field, old_value, new_value]
        changes.append(
            {
                "revision_id": _revision_id(parts),
                "observed_at": observed_at,
                "snapshot_from": previous_name,
                "snapshot_to": current_name,
                "record_id": record_id,
                "change_type": kind,
                "field": field,
                "old_value": old_value,
                "new_value": new_value,
            }
        )

    for record_id in sorted(set(new.index) - set(old.index)):
        add_change(str(record_id), "addition", "", "", "record added")
    for record_id in sorted(set(old.index) - set(new.index)):
        add_change(str(record_id), "removal", "", "record removed", "")
    for record_id in sorted(set(old.index) & set(new.index)):
        for field in TRACKED_FIELDS:
            if field not in old.columns or field not in new.columns:
                continue
            before = _display(old.at[record_id, field])
            after = _display(new.at[record_id, field])
            if before == after:
                continue
            kind = {
                "normalized_mode": "mode_reclassification",
                "native_party_type": "mode_reclassification",
                "native_victim_role": "mode_reclassification",
                "native_vehicle_type": "mode_reclassification",
                "collision_date": "date_correction",
                "death_date": "date_correction",
                "latitude": "location_correction",
                "longitude": "location_correction",
                "location": "location_correction",
                "neighborhood": "location_correction",
                "supervisor_district": "location_correction",
            }.get(field, "field_update")
            add_change(str(record_id), kind, field, before, after)
    return pd.DataFrame(changes, columns=columns)


def append_revision_log(path: Path, changes: pd.DataFrame) -> pd.DataFrame:
    if path.exists():
        existing = pd.read_parquet(path)
    else:
        existing = pd.DataFrame(columns=changes.columns)
    if changes.empty:
        return existing
    combined = pd.concat([existing, changes], ignore_index=True)
    combined = combined.drop_duplicates("revision_id", keep="first").sort_values("observed_at")
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(path, index=False)
    return combined


def snapshot_files(data_dir: Path) -> list[Path]:
    return sorted((data_dir / "processed" / "snapshots").glob("fatalities_*.parquet"))


def compare_snapshot_files(first: Path, second: Path) -> pd.DataFrame:
    first_df = pd.read_parquet(first)
    second_df = pd.read_parquet(second)
    return compare_snapshots(
        first_df,
        second_df,
        first.name,
        second.name,
        pd.Timestamp.now(tz="UTC").tz_localize(None),
    )
