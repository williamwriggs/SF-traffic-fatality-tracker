import pandas as pd

from src.charts import (
    annual_mode_chart,
    coverage_date,
    coverage_label,
    hero_chart,
    multi_year_chart,
)


def chart_records() -> pd.DataFrame:
    rows = [
        ("2016-a", "2016-01-10", "While Walking", "official"),
        ("2016-b", "2016-10-10", "While Driving / Riding", "official"),
        ("2022-a", "2022-02-10", "While Walking", "official"),
        ("2022-b", "2022-09-10", "While Cycling", "official"),
        ("2026-a", "2026-06-10", "While Walking", "official"),
        ("2026-p", "2026-08-07", "Micromobility", "provisional"),
    ]
    frame = pd.DataFrame(
        rows,
        columns=["record_id", "collision_date", "normalized_mode", "record_status"],
    )
    frame["collision_date"] = pd.to_datetime(frame["collision_date"])
    frame["year"] = frame["collision_date"].dt.year.astype("Int64")
    frame["month"] = frame["collision_date"].dt.month.astype("Int64")
    return frame


def test_historical_coverage_uses_year_end_instead_of_tracker_date():
    records = chart_records()
    tracker_date = pd.Timestamp("2026-08-12")
    assert coverage_label(records, 2022, tracker_date) == "Dec. 2022"
    assert coverage_date(records, 2022, tracker_date) == pd.Timestamp("2022-12-31")
    assert coverage_label(records, 2026, tracker_date) == "Aug. 12, 2026"


def test_two_year_chart_labels_historical_focus_year_correctly():
    records = chart_records()
    official = records[records["record_status"].eq("official")]
    figure = hero_chart(
        official,
        records,
        current_year=2022,
        comparison_year=2016,
        as_of=pd.Timestamp("2022-12-31"),
    )
    annotations = " ".join(annotation.text for annotation in figure.layout.annotations)
    assert "Dec. 2022" in annotations
    assert "Aug. 12, 2026" not in annotations
    assert "total = 2" in annotations


def test_multi_year_chart_includes_each_selected_year_and_provisional_extension():
    records = chart_records()
    official = records[records["record_status"].eq("official")]
    figure = multi_year_chart(official, records, [2016, 2022, 2026], focus_year=2026)
    trace_names = [trace.name for trace in figure.data]
    assert any(name.startswith("2016") for name in trace_names)
    assert any(name.startswith("2022") for name in trace_names)
    assert any(name.startswith("2026") for name in trace_names)
    assert "2026 provisional extension" in trace_names
    assert figure.layout.title.text.startswith(
        "Traffic Fatalities in San Francisco: Multi-year comparison"
    )


def test_annual_mode_chart_can_normalize_each_year_to_100_percent():
    records = chart_records()
    official = records[records["record_status"].eq("official")]
    figure = annual_mode_chart(official, start_year=2016, normalized=True)

    totals_by_year: dict[int, float] = {}
    for trace in figure.data:
        for year, share in zip(trace.x, trace.y, strict=True):
            totals_by_year[int(year)] = totals_by_year.get(int(year), 0) + float(share)

    assert all(round(total, 8) == 100 for total in totals_by_year.values())
    assert figure.layout.yaxis.range == (0, 100)
    assert figure.layout.yaxis.ticksuffix == "%"
    assert "each bar = 100%" in figure.layout.title.text


def test_annual_mode_chart_reserves_header_space_for_title_and_legend():
    records = chart_records()
    official = records[records["record_status"].eq("official")]
    figure = annual_mode_chart(official, start_year=2016)

    assert figure.layout.margin.t >= 180
    assert figure.layout.title.yanchor == "top"
    assert figure.layout.legend.yanchor == "bottom"
