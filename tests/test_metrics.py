import pandas as pd

from src.metrics import monthly_cumulative, same_date_prior_year, summary_metrics


def records():
    return pd.DataFrame(
        [
            {"record_id": "a", "collision_date": pd.Timestamp("2025-01-10"), "year": 2025, "month": 1, "normalized_mode": "While Walking", "record_status": "official"},
            {"record_id": "b", "collision_date": pd.Timestamp("2025-02-15"), "year": 2025, "month": 2, "normalized_mode": "While Cycling", "record_status": "official"},
            {"record_id": "c", "collision_date": pd.Timestamp("2026-01-11"), "year": 2026, "month": 1, "normalized_mode": "While Walking", "record_status": "official"},
            {"record_id": "p", "collision_date": pd.Timestamp("2026-03-01"), "year": 2026, "month": 3, "normalized_mode": "Micromobility", "record_status": "provisional"},
        ]
    )


def test_monthly_cumulative_separates_official_and_provisional():
    result = monthly_cumulative(records(), 2026).set_index("month")
    assert result.loc[1, "official_cumulative"] == 1
    assert result.loc[2, "combined_cumulative"] == 1
    assert result.loc[3, "combined_cumulative"] == 2
    assert result.loc[3, "provisional"] == 1


def test_same_date_prior_year_uses_month_and_day_cutoff():
    assert same_date_prior_year(records(), 2025, pd.Timestamp("2026-02-01")) == 1


def test_summary_keeps_official_kpi_distinct():
    all_records = records()
    official = all_records[all_records["record_status"].eq("official")]
    summary = summary_metrics(official, all_records, 2026, 2025, pd.Timestamp("2026-03-10"))
    assert summary.official_ytd == 1
    assert summary.provisional_open == 1
    assert summary.combined_ytd == 2
    assert summary.cycling_micromobility_share == 0.5
