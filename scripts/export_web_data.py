"""Export compact, browser-friendly data for the Vercel dashboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DEFAULT_OUTPUT = ROOT / "web" / "public" / "data"

RECORD_FIELDS = [
    "record_id",
    "collision_date",
    "death_date",
    "year",
    "month",
    "normalized_mode",
    "native_victim_role",
    "native_vehicle_type",
    "record_status",
    "classification_status",
    "latitude",
    "longitude",
    "location",
    "neighborhood",
    "supervisor_district",
    "police_district",
    "source_dataset",
    "notes",
]

SNAPSHOT_FIELDS = [
    "record_id",
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


def _json_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def records_for_json(frame: pd.DataFrame, fields: list[str]) -> list[dict[str, Any]]:
    selected = frame[[field for field in fields if field in frame.columns]].copy()
    return [
        {key: _json_value(value) for key, value in row.items()}
        for row in selected.to_dict(orient="records")
    ]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def export_web_data(data_dir: Path = DATA_DIR, output_dir: Path = DEFAULT_OUTPUT) -> Path:
    processed = data_dir / "processed"
    combined = pd.read_parquet(processed / "combined.parquet")
    status = json.loads((processed / "status.json").read_text(encoding="utf-8"))

    revision_path = processed / "revisions.parquet"
    revisions = pd.read_parquet(revision_path) if revision_path.exists() else pd.DataFrame()
    audit_path = processed / "provisional_audit.parquet"
    provisional_audit = pd.read_parquet(audit_path) if audit_path.exists() else pd.DataFrame()

    snapshot_manifest: list[dict[str, Any]] = []
    snapshot_dir = output_dir / "snapshots"
    for path in sorted((processed / "snapshots").glob("fatalities_*.parquet")):
        snapshot = pd.read_parquet(path)
        json_name = f"{path.stem}.json"
        write_json(snapshot_dir / json_name, records_for_json(snapshot, SNAPSHOT_FIELDS))
        snapshot_manifest.append(
            {
                "name": path.name,
                "file": f"/data/snapshots/{json_name}",
                "records": int(len(snapshot)),
                "collisionDateMax": (
                    _json_value(pd.to_datetime(snapshot["collision_date"]).max())
                    if not snapshot.empty
                    else None
                ),
            }
        )

    payload = {
        "schemaVersion": 1,
        "status": status,
        "records": records_for_json(combined, RECORD_FIELDS),
        "revisions": records_for_json(revisions, list(revisions.columns)),
        "provisionalAudit": records_for_json(
            provisional_audit, list(provisional_audit.columns)
        ),
        "snapshots": snapshot_manifest,
    }
    destination = output_dir / "tracker.json"
    write_json(destination, payload)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    destination = export_web_data(args.data_dir, args.output_dir)
    print(destination)


if __name__ == "__main__":
    main()
