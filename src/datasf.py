"""DataSF API access and source-faithful normalization."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

DATASET_ID = "dau3-4s8f"
DATASET_NAME = "Traffic Crashes Resulting in Fatality"
API_ROOT = "https://data.sfgov.org"

SELECT_FIELDS = [
    "unique_id",
    "case_id_fkey",
    "collision_datetime",
    "collision_date",
    "death_datetime",
    "death_date",
    "collision_year",
    "deceased",
    "collision_type",
    "latitude",
    "longitude",
    "location",
    "analysis_neighborhood",
    "supervisor_district",
    "police_district",
    "publish",
    "data_as_of",
    "data_loaded_at",
]


class DataSFError(RuntimeError):
    """Raised when DataSF cannot provide a valid response."""


@dataclass(frozen=True)
class FetchResult:
    rows: list[dict[str, Any]]
    metadata: dict[str, Any]
    fetched_at: datetime


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def normalize_mode(victim_role: object, party_type: object, vehicle_type: object = None) -> str:
    """Map native DataSF modes to a display taxonomy without losing raw values."""
    primary = " ".join(str(v) for v in (victim_role, party_type) if pd.notna(v)).lower()
    fallback = str(vehicle_type).lower() if pd.notna(vehicle_type) else ""
    if "pedestrian" in primary:
        return "While Walking"
    if "bicycl" in primary or "bike" in primary:
        return "While Cycling"
    if "scooter" in primary or "standup" in primary or "micro" in primary:
        return "Micromobility"
    if "motorcycle" in primary or "motorcyclist" in primary:
        return "While Riding a Motorcycle"
    if "driver" in primary or "passenger" in primary:
        return "While Driving / Riding"
    if "bicycl" in fallback or "bike" in fallback:
        return "While Cycling"
    if "scooter" in fallback or "standup" in fallback:
        return "Micromobility"
    if "motorcycle" in fallback:
        return "While Riding a Motorcycle"
    return "Other / Unresolved"


class DataSFClient:
    def __init__(self, app_token: str | None = None, timeout: int = 45) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        token = app_token or os.getenv("SOCRATA_APP_TOKEN")
        if token:
            self.session.headers["X-App-Token"] = token
        self.session.headers["User-Agent"] = "sf-traffic-fatality-tracker/0.1"

    def _get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise DataSFError(f"DataSF request failed: {exc}") from exc

    def fetch_fatal_victims(self, start_year: int = 2014) -> FetchResult:
        fetched_at = utc_now()
        metadata = self._get_json(f"{API_ROOT}/api/views/{DATASET_ID}")
        params = {
            "$select": ",".join(SELECT_FIELDS),
            "$where": (
                "publish=true "
                f"AND collision_date >= '{int(start_year)}-01-01T00:00:00'"
            ),
            "$order": "collision_date,unique_id",
            "$limit": 50000,
        }
        rows = self._get_json(f"{API_ROOT}/resource/{DATASET_ID}.json", params=params)
        if not isinstance(rows, list):
            raise DataSFError("DataSF returned an unexpected payload")
        return FetchResult(rows=rows, metadata=metadata, fetched_at=fetched_at)


def write_raw_snapshot(result: FetchResult, data_dir: Path) -> tuple[Path, Path]:
    stamp = result.fetched_at.strftime("%Y-%m-%dT%H%M%SZ")
    day_dir = data_dir / "raw" / result.fetched_at.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    rows_path = day_dir / f"{DATASET_ID}_{stamp}.json"
    manifest_path = day_dir / f"manifest_{stamp}.json"
    rows_path.write_text(json.dumps(result.rows, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "dataset_id": DATASET_ID,
        "dataset_name": DATASET_NAME,
        "dataset_url": f"{API_ROOT}/resource/{DATASET_ID}.json",
        "fetched_at": result.fetched_at.isoformat(),
        "row_count": len(result.rows),
        "metadata_rows_updated_at": result.metadata.get("rowsUpdatedAt"),
        "metadata_rows_updated_by": result.metadata.get("rowsUpdatedBy"),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return rows_path, manifest_path


def normalize_fatal_victims(rows: list[dict[str, Any]], fetched_at: datetime) -> pd.DataFrame:
    raw = pd.DataFrame(rows)
    if raw.empty:
        return pd.DataFrame()
    required = {"unique_id", "collision_date", "deceased"}
    missing = required.difference(raw.columns)
    if missing:
        raise DataSFError(f"Required DataSF columns missing: {sorted(missing)}")

    for col in SELECT_FIELDS:
        if col not in raw.columns:
            raw[col] = pd.NA

    dates = pd.to_datetime(raw["collision_date"], errors="coerce", utc=True)
    lat = pd.to_numeric(raw["latitude"], errors="coerce")
    lon = pd.to_numeric(raw["longitude"], errors="coerce")

    normalized = pd.DataFrame(
        {
            "record_id": raw["unique_id"].astype(str),
            "crash_id": raw["case_id_fkey"].astype("string"),
            "person_id": raw["unique_id"].astype("string"),
            "collision_datetime": pd.to_datetime(
                raw["collision_datetime"], errors="coerce", utc=True
            ),
            "collision_date": dates.dt.tz_localize(None),
            "death_date": pd.to_datetime(raw["death_date"], errors="coerce", utc=True).dt.tz_localize(None),
            "year": dates.dt.year.astype("Int64"),
            "month": dates.dt.month.astype("Int64"),
            "native_party_type": raw["deceased"].astype("string"),
            "native_victim_role": raw["deceased"].astype("string"),
            "native_vehicle_type": raw["collision_type"].astype("string"),
            "normalized_mode": [
                normalize_mode(role, party, vehicle)
                for role, party, vehicle in zip(
                    raw["deceased"], raw["deceased"], raw["collision_type"], strict=True
                )
            ],
            "severity": "Fatality meeting the San Francisco Vision Zero Fatality Protocol",
            "latitude": lat,
            "longitude": lon,
            "location": raw["location"].astype("string"),
            "neighborhood": raw["analysis_neighborhood"].astype("string"),
            "supervisor_district": raw["supervisor_district"].astype("string"),
            "police_district": raw["police_district"].astype("string"),
            "source_dataset": DATASET_ID,
            "source_updated_at": pd.to_datetime(
                raw["data_as_of"], errors="coerce", utc=True
            ).dt.tz_localize(None),
            "source_loaded_at": pd.to_datetime(
                raw["data_loaded_at"], errors="coerce", utc=True
            ).dt.tz_localize(None),
            "tracker_ingested_at": pd.Timestamp(fetched_at).tz_convert(None),
            "record_status": "official",
            "classification_status": "source-classified",
            "notes": pd.NA,
        }
    )
    return normalized.sort_values(["collision_date", "record_id"]).reset_index(drop=True)
