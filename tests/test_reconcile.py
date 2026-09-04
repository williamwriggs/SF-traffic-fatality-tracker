import pandas as pd

from src.reconcile import compare_snapshots


def frame(rows):
    defaults = {
        "collision_date": pd.Timestamp("2026-01-01"),
        "death_date": pd.NaT,
        "normalized_mode": "While Walking",
        "native_party_type": "Pedestrian",
        "native_victim_role": "Pedestrian",
        "native_vehicle_type": "Pedestrian vs Motor Vehicle",
        "latitude": 37.7,
        "longitude": -122.4,
        "location": "A & B",
        "neighborhood": "Mission",
        "supervisor_district": "9",
        "classification_status": "source-classified",
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


def test_compare_snapshots_detects_add_remove_and_field_changes():
    old = frame([{"record_id": "keep"}, {"record_id": "remove"}])
    new = frame(
        [
            {"record_id": "keep", "normalized_mode": "While Cycling", "location": "C & D"},
            {"record_id": "add"},
        ]
    )
    changes = compare_snapshots(old, new, "old", "new", pd.Timestamp("2026-08-12"))
    kinds = set(changes["change_type"])
    assert {"addition", "removal", "mode_reclassification", "location_correction"} <= kinds
    assert changes["revision_id"].is_unique


def test_identical_snapshots_have_no_revisions():
    old = frame([{"record_id": "same"}])
    assert compare_snapshots(old, old.copy(), "old", "new", pd.Timestamp("2026-08-12")).empty


def test_coordinate_serialization_noise_is_not_a_revision():
    old = frame([{"record_id": "same", "latitude": 37.710409216678755}])
    new = frame([{"record_id": "same", "latitude": 37.71040921667876}])

    assert compare_snapshots(old, new, "old", "new", pd.Timestamp("2026-08-13")).empty


def test_material_coordinate_change_is_a_revision():
    old = frame([{"record_id": "moved", "latitude": 37.710409}])
    new = frame([{"record_id": "moved", "latitude": 37.710509}])

    changes = compare_snapshots(old, new, "old", "new", pd.Timestamp("2026-08-13"))
    assert list(changes["change_type"]) == ["location_correction"]
