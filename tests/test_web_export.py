import json
from pathlib import Path

import pandas as pd

from scripts.export_web_data import export_web_data


def test_export_web_data_writes_current_records_and_individual_snapshots(tmp_path: Path):
    data_dir = tmp_path / "data"
    processed = data_dir / "processed"
    snapshots = processed / "snapshots"
    snapshots.mkdir(parents=True)

    records = pd.DataFrame(
        [
            {
                "record_id": "official-1",
                "collision_date": pd.Timestamp("2025-02-03"),
                "death_date": pd.Timestamp("2025-02-03"),
                "year": 2025,
                "month": 2,
                "normalized_mode": "While Walking",
                "native_victim_role": "Pedestrian",
                "record_status": "official",
                "latitude": 37.77,
                "longitude": -122.42,
            }
        ]
    )
    records.to_parquet(processed / "combined.parquet", index=False)
    records.to_parquet(snapshots / "fatalities_20250101T000000Z.parquet", index=False)
    (processed / "status.json").write_text(
        json.dumps({"fetched_at": "2025-01-01T00:00:00+00:00"}), encoding="utf-8"
    )

    output = tmp_path / "web-data"
    destination = export_web_data(data_dir, output)
    payload = json.loads(destination.read_text(encoding="utf-8"))

    assert payload["schemaVersion"] == 1
    assert payload["records"][0]["collision_date"] == "2025-02-03T00:00:00"
    assert payload["snapshots"][0]["name"] == "fatalities_20250101T000000Z.parquet"
    assert (output / "snapshots" / "fatalities_20250101T000000Z.json").exists()
