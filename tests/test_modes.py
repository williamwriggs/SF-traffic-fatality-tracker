import pytest

from src.datasf import normalize_mode


@pytest.mark.parametrize(
    ("native", "collision_type", "expected"),
    [
        ("Pedestrian", "Pedestrian vs Motor Vehicle", "While Walking"),
        ("Bicyclist", "Bicycle Collision", "While Cycling"),
        ("Standup Powered Device Rider", "Motor Vehicle", "Micromobility"),
        ("Motorcyclist", "Motorcycle Collision", "While Riding a Motorcycle"),
        ("Driver", "Motor Vehicle & Pedestrian", "While Driving / Riding"),
        ("Moped", "Moped vs Motor Vehicle", "Other / Unresolved"),
        ("Unknown", "Unknown", "Other / Unresolved"),
    ],
)
def test_normalize_mode_preserves_deceased_person_mode(native, collision_type, expected):
    assert normalize_mode(native, native, collision_type) == expected
