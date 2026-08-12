"""Metric calculations used by both the app and tests."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

MODE_ORDER = [
    "While Walking",
    "While Driving / Riding",
    "While Riding a Motorcycle",
    "While Cycling",
    "Micromobility",
    "Other / Unresolved",
]


def combine_records(official: pd.DataFrame, provisional: pd.DataFrame) -> pd.DataFrame:
    if provisional.empty:
        return official.copy()
    if official.empty:
        return provisional.copy()
    return pd.concat([official, provisional], ignore_index=True, sort=False).sort_values(
        ["collision_date", "record_id"]
    )


def filter_as_of(records: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    if records.empty:
        return records.copy()
    date = pd.Timestamp(as_of).tz_localize(None) if pd.Timestamp(as_of).tzinfo else pd.Timestamp(as_of)
    return records[pd.to_datetime(records["collision_date"]).le(date)].copy()


def monthly_cumulative(records: pd.DataFrame, year: int) -> pd.DataFrame:
    selected = records[records["year"].eq(year)].copy()
    grouped = selected.groupby(["month", "record_status"], dropna=False).size().unstack(fill_value=0)
    result = pd.DataFrame(index=pd.Index(range(1, 13), name="month")).join(grouped).fillna(0)
    for status in ("official", "provisional"):
        if status not in result:
            result[status] = 0
        result[status] = result[status].astype(int)
    result["monthly_total"] = result["official"] + result["provisional"]
    result["official_cumulative"] = result["official"].cumsum()
    result["combined_cumulative"] = result["monthly_total"].cumsum()
    return result.reset_index()


def mode_counts(records: pd.DataFrame, year: int | None = None) -> pd.DataFrame:
    selected = records if year is None else records[records["year"].eq(year)]
    counts = selected.groupby("normalized_mode", dropna=False).size().rename("fatalities").reset_index()
    counts["normalized_mode"] = counts["normalized_mode"].fillna("Other / Unresolved")
    counts["sort"] = counts["normalized_mode"].map({v: i for i, v in enumerate(MODE_ORDER)}).fillna(99)
    return counts.sort_values(["sort", "normalized_mode"]).drop(columns="sort").reset_index(drop=True)


def annual_mode_counts(records: pd.DataFrame, start_year: int = 2014) -> pd.DataFrame:
    selected = records[records["year"].ge(start_year)].copy()
    return (
        selected.groupby(["year", "normalized_mode"], dropna=False)
        .size()
        .rename("fatalities")
        .reset_index()
    )


def same_date_prior_year(records: pd.DataFrame, year: int, as_of: pd.Timestamp) -> int:
    cutoff = pd.Timestamp(as_of)
    month, day = cutoff.month, cutoff.day
    selected = records[
        records["year"].eq(year)
        & (
            records["collision_date"].dt.month.lt(month)
            | (
                records["collision_date"].dt.month.eq(month)
                & records["collision_date"].dt.day.le(day)
            )
        )
    ]
    return len(selected)


def rolling_12_month_count(records: pd.DataFrame, as_of: pd.Timestamp) -> int:
    end = pd.Timestamp(as_of).tz_localize(None) if pd.Timestamp(as_of).tzinfo else pd.Timestamp(as_of)
    start = end - pd.DateOffset(months=12)
    dates = pd.to_datetime(records["collision_date"])
    return int(dates.gt(start).sum() - dates.gt(end).sum())


def share(records: pd.DataFrame, modes: set[str]) -> float:
    if records.empty:
        return 0.0
    return float(records["normalized_mode"].isin(modes).mean())


@dataclass(frozen=True)
class Summary:
    official_ytd: int
    provisional_open: int
    combined_ytd: int
    prior_year_same_date: int
    year_over_year_change: int
    rolling_12_months: int
    pedestrian_share: float
    cycling_micromobility_share: float
    vehicle_occupant_share: float
    days_since_last_fatality: int | None


def summary_metrics(
    official: pd.DataFrame,
    combined: pd.DataFrame,
    year: int,
    comparison_year: int,
    as_of: pd.Timestamp,
) -> Summary:
    official_ytd_rows = filter_as_of(official[official["year"].eq(year)], as_of)
    combined_ytd_rows = filter_as_of(combined[combined["year"].eq(year)], as_of)
    provisional = combined_ytd_rows[combined_ytd_rows["record_status"].eq("provisional")]
    prior = same_date_prior_year(official, comparison_year, as_of)
    last_date = combined_ytd_rows["collision_date"].max() if not combined_ytd_rows.empty else pd.NaT
    days_since = None if pd.isna(last_date) else int((pd.Timestamp(as_of) - last_date).days)
    return Summary(
        official_ytd=len(official_ytd_rows),
        provisional_open=len(provisional),
        combined_ytd=len(combined_ytd_rows),
        prior_year_same_date=prior,
        year_over_year_change=len(combined_ytd_rows) - prior,
        rolling_12_months=rolling_12_month_count(combined, as_of),
        pedestrian_share=share(combined_ytd_rows, {"While Walking"}),
        cycling_micromobility_share=share(
            combined_ytd_rows, {"While Cycling", "Micromobility"}
        ),
        vehicle_occupant_share=share(
            combined_ytd_rows,
            {"While Driving / Riding", "While Riding a Motorcycle"},
        ),
        days_since_last_fatality=days_since,
    )


def seasonality_matrix(records: pd.DataFrame, start_year: int = 2014) -> pd.DataFrame:
    selected = records[records["year"].ge(start_year)]
    counts = selected.groupby(["year", "month"]).size().unstack(fill_value=0)
    return counts.reindex(columns=range(1, 13), fill_value=0).sort_index()
