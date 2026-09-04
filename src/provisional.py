"""Load the manually auditable provisional incident layer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.datasf import normalize_mode

PROVISIONAL_COLUMNS = [
    "provisional_id",
    "incident_date",
    "death_date",
    "person_name",
    "mode_reported",
    "normalized_mode",
    "latitude",
    "longitude",
    "location",
    "source_url",
    "source_name",
    "status",
    "last_checked",
    "matched_official_record_id",
    "reconciled_date",
    "notes",
]

OPEN_STATUSES = {"unreconciled", "provisional", "under-review"}
TERMINAL_STATUSES = {"reconciled", "excluded", "duplicate", "withdrawn"}
ALLOWED_STATUSES = OPEN_STATUSES | TERMINAL_STATUSES


def load_provisional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=PROVISIONAL_COLUMNS)
    frame = pd.read_csv(path, dtype="string", keep_default_na=True)
    for col in PROVISIONAL_COLUMNS:
        if col not in frame.columns:
            frame[col] = pd.NA
    frame = frame[PROVISIONAL_COLUMNS].copy()
    if frame["provisional_id"].isna().any() or frame["provisional_id"].duplicated().any():
        raise ValueError("Every provisional incident needs a unique provisional_id")
    for col in ("incident_date", "death_date", "last_checked", "reconciled_date"):
        frame[col] = pd.to_datetime(frame[col], errors="coerce")
    for col in ("latitude", "longitude"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    status = frame["status"].fillna("").str.strip().str.lower()
    unknown_status = ~status.isin(ALLOWED_STATUSES)
    if unknown_status.any():
        values = sorted(status[unknown_status].unique())
        raise ValueError(f"Unknown provisional status values: {values}")
    frame["status"] = status
    matched = frame["matched_official_record_id"].fillna("").str.strip().ne("")
    reconciled = status.eq("reconciled")
    invalid_reconciliation = matched.ne(reconciled)
    if invalid_reconciliation.any():
        ids = frame.loc[invalid_reconciliation, "provisional_id"].astype(str).tolist()
        raise ValueError(
            "Reconciled provisional rows require both status='reconciled' and "
            f"matched_official_record_id; invalid rows: {ids}"
        )
    missing_mode = frame["normalized_mode"].isna() | frame["normalized_mode"].eq("")
    frame.loc[missing_mode, "normalized_mode"] = [
        normalize_mode(value, value) for value in frame.loc[missing_mode, "mode_reported"]
    ]
    return frame


def as_tracker_records(provisional: pd.DataFrame, ingested_at: pd.Timestamp) -> pd.DataFrame:
    """Shape open provisional incidents like official records for analysis."""
    if provisional.empty:
        return pd.DataFrame()
    current = provisional[
        provisional["status"].fillna("").str.lower().isin(OPEN_STATUSES)
    ].copy()
    if current.empty:
        return pd.DataFrame()
    effective_date = current["incident_date"].fillna(current["death_date"])
    return pd.DataFrame(
        {
            "record_id": "provisional:" + current["provisional_id"].astype(str),
            "crash_id": pd.NA,
            "person_id": pd.NA,
            "collision_datetime": effective_date,
            "collision_date": effective_date,
            "death_date": current["death_date"],
            "year": effective_date.dt.year.astype("Int64"),
            "month": effective_date.dt.month.astype("Int64"),
            "native_party_type": current["mode_reported"],
            "native_victim_role": current["mode_reported"],
            "native_vehicle_type": pd.NA,
            "normalized_mode": current["normalized_mode"],
            "severity": "Reported fatality; Vision Zero eligibility not yet reconciled",
            "latitude": current["latitude"],
            "longitude": current["longitude"],
            "location": current["location"],
            "neighborhood": pd.NA,
            "supervisor_district": pd.NA,
            "police_district": pd.NA,
            "source_dataset": current["source_url"],
            "source_updated_at": current["last_checked"],
            "source_loaded_at": pd.NaT,
            "tracker_ingested_at": ingested_at,
            "record_status": "provisional",
            "classification_status": current["status"],
            "notes": current["notes"],
        }
    ).reset_index(drop=True)


def flag_possible_matches(provisional: pd.DataFrame, official: pd.DataFrame) -> pd.DataFrame:
    """Flag plausible official matches for review; never auto-reconcile them."""
    if provisional.empty:
        return provisional.assign(possible_official_match=pd.Series(dtype="string"))
    result = provisional.copy()
    result["possible_official_match"] = pd.NA
    for idx, row in result.iterrows():
        if pd.notna(row["matched_official_record_id"]) or pd.isna(row["incident_date"]):
            continue
        date_delta = (official["collision_date"] - row["incident_date"]).abs().dt.days
        candidates = official[
            date_delta.le(14) & official["normalized_mode"].eq(row["normalized_mode"])
        ]
        if len(candidates) == 1:
            result.at[idx, "possible_official_match"] = candidates.iloc[0]["record_id"]
    return result
