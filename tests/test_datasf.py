from datetime import UTC, datetime

import pytest

from src.datasf import DataSFError, normalize_fatal_victims


def normalize(rows):
    return normalize_fatal_victims(rows, datetime(2026, 9, 4, tzinfo=UTC))


def test_empty_official_payload_is_rejected():
    with pytest.raises(DataSFError, match="empty"):
        normalize([])


def test_duplicate_official_ids_are_rejected():
    rows = [
        {"unique_id": "same", "collision_date": "2026-01-01", "deceased": "Pedestrian"},
        {"unique_id": "same", "collision_date": "2026-01-02", "deceased": "Bicyclist"},
    ]
    with pytest.raises(DataSFError, match="duplicate"):
        normalize(rows)


@pytest.mark.parametrize(
    "row",
    [
        {"unique_id": "a", "collision_date": "not-a-date", "deceased": "Pedestrian"},
        {"unique_id": "a", "collision_date": "2026-01-01", "deceased": None},
    ],
)
def test_invalid_required_values_are_rejected(row):
    with pytest.raises(DataSFError):
        normalize([row])
