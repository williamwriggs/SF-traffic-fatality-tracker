import pandas as pd

from src.provisional import as_tracker_records


def test_explicitly_reconciled_provisional_record_does_not_count():
    provisional = pd.DataFrame(
        [
            {
                "provisional_id": "open",
                "incident_date": pd.Timestamp("2026-08-01"),
                "death_date": pd.Timestamp("2026-08-01"),
                "mode_reported": "Bicyclist",
                "normalized_mode": "While Cycling",
                "latitude": 37.7,
                "longitude": -122.4,
                "location": "A & B",
                "source_url": "https://example.com/open",
                "status": "unreconciled",
                "last_checked": pd.Timestamp("2026-08-12"),
                "matched_official_record_id": pd.NA,
                "notes": "",
            },
            {
                "provisional_id": "matched",
                "incident_date": pd.Timestamp("2026-07-01"),
                "death_date": pd.Timestamp("2026-07-01"),
                "mode_reported": "Pedestrian",
                "normalized_mode": "While Walking",
                "latitude": 37.7,
                "longitude": -122.4,
                "location": "C & D",
                "source_url": "https://example.com/matched",
                "status": "reconciled",
                "last_checked": pd.Timestamp("2026-08-12"),
                "matched_official_record_id": "official-1",
                "notes": "",
            },
        ]
    )
    result = as_tracker_records(provisional, pd.Timestamp("2026-08-12"))
    assert list(result["record_id"]) == ["provisional:open"]
