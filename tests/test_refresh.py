import pandas as pd
import pytest

from src.datasf import DataSFError
from src.refresh import _validate_snapshot_transition


def test_large_snapshot_drop_is_rejected():
    previous = pd.DataFrame({"record_id": range(100)})
    current = pd.DataFrame({"record_id": range(79)})

    with pytest.raises(DataSFError, match="volume fell"):
        _validate_snapshot_transition(previous, current)


def test_small_snapshot_drop_is_allowed_for_real_revisions():
    previous = pd.DataFrame({"record_id": range(100)})
    current = pd.DataFrame({"record_id": range(99)})

    _validate_snapshot_transition(previous, current)
