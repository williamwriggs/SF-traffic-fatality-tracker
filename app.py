"""Streamlit application for the SF Traffic Fatality Tracker."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.charts import (
    COLORS,
    annual_mode_chart,
    coverage_date,
    hero_chart,
    is_complete_year,
    map_chart,
    multi_year_chart,
    seasonality_chart,
)
from src.export import write_matplotlib_fallback
from src.metrics import MODE_ORDER, mode_counts, summary_metrics
from src.reconcile import compare_snapshot_files, snapshot_files

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
PROCESSED = DATA_DIR / "processed"

st.set_page_config(
    page_title="SF Traffic Fatality Tracker",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown(
    """
    <style>
    .stApp { background: #FBFAF7; }
    .block-container { max-width: 1320px; padding-top: 2rem; padding-bottom: 4rem; }
    h1, h2, h3 { letter-spacing: -0.025em; color: #1F2429; }
    h1 { font-size: clamp(2.2rem, 5vw, 4.4rem) !important; line-height: .98 !important; }
    [data-testid="stMetric"] { border-top: 2px solid #1F2429; padding-top: .8rem; }
    [data-testid="stMetricValue"] { font-weight: 750; letter-spacing: -.04em; }
    .status-strip { background: #ECEAE4; border-left: 4px solid #132A70; padding: .85rem 1rem;
                    margin: .5rem 0 1.4rem 0; color: #34393D; }
    .status-strip.warn { border-left-color: #E76600; background: #F6EADF; }
    .eyebrow { text-transform: uppercase; letter-spacing: .13em; font-size: .72rem;
               font-weight: 700; color: #62676C; }
    .lede { max-width: 850px; font-size: 1.15rem; color: #565B60; margin-bottom: 1.2rem; }
    .provisional-pill { display:inline-block; border:1px dashed #132A70; color:#132A70;
                        padding:.15rem .45rem; border-radius:999px; font-size:.75rem; }
    .source-note { font-size: .82rem; color: #62676C; line-height: 1.45; }
    .research-credit { color: #62676C; font-size: .88rem; margin: -.55rem 0 1.15rem 0; }
    .research-credit a { color: #132A70; font-weight: 650; text-decoration: none; }
    .research-credit a:hover { text-decoration: underline; }
    div[data-testid="stDataFrame"] { border: 1px solid #D8D7D2; }
    @media (max-width: 700px) {
      .block-container { padding-left: 1rem; padding-right: 1rem; }
      [data-testid="column"] { min-width: 48% !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=900)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    official = pd.read_parquet(PROCESSED / "fatalities.parquet")
    combined = pd.read_parquet(PROCESSED / "combined.parquet")
    revisions_path = PROCESSED / "revisions.parquet"
    audit_path = PROCESSED / "provisional_audit.parquet"
    revisions = pd.read_parquet(revisions_path) if revisions_path.exists() else pd.DataFrame()
    provisional_audit = pd.read_parquet(audit_path) if audit_path.exists() else pd.DataFrame()
    status = json.loads((PROCESSED / "status.json").read_text(encoding="utf-8"))
    for frame in (official, combined):
        frame["collision_date"] = pd.to_datetime(frame["collision_date"])
        frame["death_date"] = pd.to_datetime(frame["death_date"])
    return official, combined, revisions, provisional_audit, status


def csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8")


def mode_bar(frame: pd.DataFrame, year: int) -> go.Figure:
    counts = mode_counts(frame, year)
    counts = counts.set_index("normalized_mode").reindex(MODE_ORDER).fillna(0).reset_index()
    fig = go.Figure(
        go.Bar(
            x=counts["fatalities"],
            y=counts["normalized_mode"],
            orientation="h",
            marker={"color": [COLORS.get(v, "#999999") for v in counts["normalized_mode"]]},
            text=counts["fatalities"].astype(int),
            textposition="outside",
            hovertemplate="%{y}: %{x}<extra></extra>",
        )
    )
    fig.update_layout(
        title={"text": f"{year} fatalities by mode<br><sup>Official and open provisional records</sup>", "x": 0},
        height=390,
        margin={"l": 15, "r": 30, "t": 80, "b": 30},
        paper_bgcolor=COLORS["paper"],
        plot_bgcolor=COLORS["paper"],
        font={"family": "Arial, sans-serif", "color": COLORS["ink"]},
        showlegend=False,
        xaxis={"showgrid": True, "gridcolor": COLORS["grid"], "zeroline": False},
        yaxis={"autorange": "reversed", "showgrid": False},
    )
    return fig


if not (PROCESSED / "fatalities.parquet").exists():
    st.error("No processed snapshot is available yet. Run `python -m src.refresh`, then reload.")
    st.stop()

official, combined, revisions, provisional_audit, status = load_data()
available_years = sorted(combined["year"].dropna().astype(int).unique(), reverse=True)
official_years = sorted(official["year"].dropna().astype(int).unique())

with st.sidebar:
    st.markdown("### Compare")
    view_mode = st.radio(
        "Visualization",
        ["Two-year detail", "Multi-year trend"],
        horizontal=True,
    )
    current_year = st.selectbox("Focus year", available_years, index=0)
    comparison_candidates = [y for y in official_years if y != current_year]
    default_comparison = comparison_candidates.index(2017) if 2017 in comparison_candidates else 0
    if view_mode == "Two-year detail":
        comparison_year = st.selectbox(
            "Comparison year", comparison_candidates, index=default_comparison
        )
        chart_years = [comparison_year, current_year]
    else:
        default_additional = [
            year
            for year in (current_year - 1, 2017)
            if year in comparison_candidates
        ]
        if not default_additional:
            default_additional = comparison_candidates[:2]
        additional_years = st.multiselect(
            "Additional years",
            comparison_candidates,
            default=default_additional,
            max_selections=5,
            help="The focus year is always included; add up to five more years.",
        )
        chart_years = sorted({current_year, *additional_years})
        earlier_years = [year for year in additional_years if year < current_year]
        comparison_year = (
            max(earlier_years)
            if earlier_years
            else additional_years[0]
            if additional_years
            else comparison_candidates[default_comparison]
        )
    st.divider()
    st.markdown("### Definitions")
    include_provisional = st.toggle("Include unreconciled reports", value=True)
    st.caption(
        "Official means published in DataSF's Vision Zero fatality table. "
        "Provisional means a public report not yet matched to that table."
    )
    st.divider()
    st.link_button(
        "Open official DataSF view",
        "https://data.sfgov.org/Public-Safety/Traffic-Crashes-Resulting-in-Fatality/dau3-4s8f",
        width="stretch",
    )

analysis_records = combined if include_provisional else official
source_loaded = pd.to_datetime(status.get("source_loaded_at"), errors="coerce")
source_reviewed = pd.to_datetime(status.get("source_data_as_of"), errors="coerce")
provisional_checked = pd.to_datetime(status.get("provisional_checked_through"), errors="coerce")
today = pd.Timestamp.today().normalize()
latest_checked = provisional_checked if include_provisional else source_reviewed
if pd.isna(latest_checked):
    latest_checked = today
focus_as_of = coverage_date(analysis_records, current_year, latest_checked)
summary = summary_metrics(
    official, analysis_records, current_year, comparison_year, focus_as_of
)
official_current = official[official["year"].eq(current_year)]
combined_current = analysis_records[analysis_records["year"].eq(current_year)]
latest_dataset_year = max(available_years)
latest_official_collision = official.loc[
    official["year"].eq(latest_dataset_year), "collision_date"
].max()
open_provisional_total = int(combined["record_status"].eq("provisional").sum())

st.markdown('<div class="eyebrow">Public data · revision aware · open source</div>', unsafe_allow_html=True)
st.title("SF Traffic Fatality Tracker")
st.markdown(
    '<div class="lede">Compare years, inspect mode and location, and download exactly what changed '
    "between DataSF snapshots. Unreconciled recent deaths stay visible without being silently counted "
    "as official.</div>",
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="research-credit">Research by <strong>William W. Riggs</strong> · '
    '<a href="https://github.com/williamwriggs/SF-traffic-fatality-tracker" '
    'target="_blank" rel="noopener noreferrer">View source and methodology on GitHub ↗</a></div>',
    unsafe_allow_html=True,
)

status_class = "warn" if open_provisional_total else ""
status_text = (
    f"Official records currently include collisions through "
    f"<strong>{latest_official_collision:%B %-d, %Y}</strong> and were loaded to DataSF "
    f"<strong>{source_loaded:%B %-d}</strong>. "
    f"<span class='provisional-pill'>{open_provisional_total} unreconciled public reports</span> "
    f"were checked through {provisional_checked:%B %-d, %Y}."
)
st.markdown(
    f'<div class="status-strip {status_class}">{status_text}</div>', unsafe_allow_html=True
)

metric_cols = st.columns(5)
focus_period = "full year" if is_complete_year(analysis_records, current_year) else "tracked YTD"
metric_cols[0].metric(
    f"{current_year} {focus_period}",
    summary.combined_ytd,
    help="Official plus open provisional records when the sidebar toggle is on.",
)
metric_cols[1].metric("Official", summary.official_ytd)
metric_cols[2].metric("Unreconciled", summary.provisional_open)
metric_cols[3].metric(
    (
        f"vs. {comparison_year} full year"
        if is_complete_year(analysis_records, current_year)
        else f"vs. {comparison_year} same date"
    ),
    f"{summary.year_over_year_change:+d}",
    delta=f"{summary.prior_year_same_date} in {comparison_year}",
    delta_color="off",
)
metric_cols[4].metric(
    (
        "Days from last death to year-end"
        if is_complete_year(analysis_records, current_year)
        else "Days since last tracked death"
    ),
    "—" if summary.days_since_last_fatality is None else summary.days_since_last_fatality,
)

overview, explore, audit, methodology = st.tabs(
    ["Overview", "Explore records", "Snapshots & revisions", "Methodology"]
)

with overview:
    if view_mode == "Two-year detail":
        hero = hero_chart(
            official,
            analysis_records,
            current_year,
            comparison_year,
            focus_as_of,
        )
    else:
        hero = multi_year_chart(
            official,
            analysis_records,
            chart_years,
            current_year,
        )
    st.plotly_chart(hero, width="stretch", config={"displaylogo": False})
    chart_note = (
        "Solid lines are official; dashed segments are unreconciled. Endpoint stacks use the "
        "tracker's normalized display taxonomy while retaining each source-native mode."
        if view_mode == "Two-year detail"
        else "The focus year is emphasized with a heavier navy line. Other selected years are "
        "context lines; any dashed extension remains unreconciled."
    )
    st.markdown(
        f'<div class="source-note">Source: SFDPH/SFPD/SFMTA via DataSF. {chart_note}</div>',
        unsafe_allow_html=True,
    )
    chart_download = analysis_records[analysis_records["year"].isin(chart_years)]
    year_slug = "-".join(str(year) for year in sorted(chart_years))
    download_cols = st.columns([1, 1, 1, 3])
    download_cols[0].download_button(
        "Download chart data",
        csv_bytes(chart_download),
        file_name=f"sf_traffic_fatalities_{year_slug}.csv",
        mime="text/csv",
        width="stretch",
    )
    download_cols[1].download_button(
        "Download interactive chart",
        hero.to_html(full_html=True, include_plotlyjs=True).encode("utf-8"),
        file_name=f"sf_traffic_fatalities_{year_slug}.html",
        mime="text/html",
        width="stretch",
    )
    if view_mode == "Two-year detail":
        with tempfile.TemporaryDirectory() as temporary_dir:
            temporary_png = Path(temporary_dir) / "hero.png"
            write_matplotlib_fallback(
                official,
                analysis_records,
                current_year,
                comparison_year,
                focus_as_of,
                temporary_png,
                1800,
                1080,
            )
            png = temporary_png.read_bytes()
        download_cols[2].download_button(
            "Download publication PNG",
            png,
            file_name=f"sf_traffic_fatalities_{comparison_year}_vs_{current_year}.png",
            mime="image/png",
            width="stretch",
        )

    left, right = st.columns([1.08, 0.92])
    with left:
        st.plotly_chart(mode_bar(analysis_records, current_year), width="stretch")
    with right:
        st.markdown("#### Read the current mix")
        st.metric("Walking share", f"{summary.pedestrian_share:.0%}")
        st.metric(
            "Cycling + micromobility share", f"{summary.cycling_micromobility_share:.0%}"
        )
        st.metric("Vehicle occupant share", f"{summary.vehicle_occupant_share:.0%}")
        st.metric("Rolling 12 months", summary.rolling_12_months)
        st.caption(
            f"Vision Zero target gap: {summary.combined_ytd} fatalities above the zero-death goal "
            f"in {current_year} to date."
        )

    normalize_annual_modes = st.toggle(
        "Show annual mode share (normalize each year to 100%)",
        value=False,
        help=(
            "Switch from fatality counts to the proportional mode mix within each year. "
            "The latest year may represent only a partial year."
        ),
    )
    st.plotly_chart(
        annual_mode_chart(official, normalized=normalize_annual_modes),
        width="stretch",
    )
    st.plotly_chart(seasonality_chart(official), width="stretch")

with explore:
    st.subheader("Filter and inspect records")
    f1, f2, f3 = st.columns(3)
    selected_years = f1.multiselect("Years", available_years, default=[current_year])
    selected_modes = f2.multiselect("Modes", MODE_ORDER, default=MODE_ORDER)
    statuses = sorted(analysis_records["record_status"].dropna().unique())
    selected_statuses = f3.multiselect("Status", statuses, default=statuses)
    filtered = analysis_records[
        analysis_records["year"].isin(selected_years)
        & analysis_records["normalized_mode"].isin(selected_modes)
        & analysis_records["record_status"].isin(selected_statuses)
    ].copy()
    st.plotly_chart(map_chart(filtered), width="stretch", config={"displaylogo": False})
    display_cols = [
        "collision_date",
        "death_date",
        "normalized_mode",
        "native_victim_role",
        "record_status",
        "location",
        "neighborhood",
        "supervisor_district",
        "record_id",
    ]
    st.dataframe(filtered[display_cols], hide_index=True, width="stretch")
    st.download_button(
        "Download filtered records",
        csv_bytes(filtered),
        file_name="sf_traffic_fatalities_filtered.csv",
        mime="text/csv",
    )

with audit:
    st.subheader("Snapshot comparison")
    files = snapshot_files(DATA_DIR)
    if len(files) < 2:
        st.info(
            "One baseline snapshot exists. Run `python -m src.refresh` after the next DataSF update "
            "to unlock a two-snapshot comparison."
        )
    else:
        labels = [path.name for path in files]
        a, b = st.columns(2)
        first_name = a.selectbox("Earlier snapshot", labels, index=max(0, len(labels) - 2))
        second_name = b.selectbox("Later snapshot", labels, index=len(labels) - 1)
        first_path = files[labels.index(first_name)]
        second_path = files[labels.index(second_name)]
        comparison = compare_snapshot_files(first_path, second_path)
        st.metric("Detected changes", len(comparison))
        st.dataframe(comparison, hide_index=True, width="stretch")
        st.download_button(
            "Download snapshot comparison",
            csv_bytes(comparison),
            file_name=f"comparison_{first_path.stem}_to_{second_path.stem}.csv",
            mime="text/csv",
        )

    st.subheader("Persistent revision log")
    if revisions.empty:
        st.caption("No post-baseline official revisions have been observed yet.")
    else:
        st.dataframe(revisions.sort_values("observed_at", ascending=False), hide_index=True)
        st.download_button(
            "Download revision log", csv_bytes(revisions), "sf_fatality_revisions.csv", "text/csv"
        )

    st.subheader("Provisional reconciliation queue")
    if provisional_audit.empty:
        st.caption("No provisional incidents are in the queue.")
    else:
        st.dataframe(
            provisional_audit[
                [
                    "provisional_id",
                    "incident_date",
                    "mode_reported",
                    "normalized_mode",
                    "location",
                    "status",
                    "last_checked",
                    "possible_official_match",
                    "matched_official_record_id",
                    "source_url",
                    "notes",
                ]
            ],
            hide_index=True,
            width="stretch",
            column_config={"source_url": st.column_config.LinkColumn("Source")},
        )

with methodology:
    st.subheader("What counts as official")
    st.markdown(
        "The canonical source is DataSF’s **Traffic Crashes Resulting in Fatality** dataset "
        "(`dau3-4s8f`). Its year-to-date records originate with the Office of the Chief Medical "
        "Examiner and include cases that City agencies determine meet the San Francisco Vision Zero "
        "Fatality Protocol. The broader victim-level injury table (`nwes-mmgh`) is useful as a "
        "cross-check, but it is not used to define the official count."
    )
    st.subheader("Collision date versus death date")
    st.markdown(
        "Charts group deaths by **collision date** for year-to-year comparability. Death date remains "
        "in every record and download. A person may die days after a collision; that is not treated "
        "as a date correction."
    )
    st.subheader("Official versus provisional")
    st.markdown(
        "A provisional record is a credible public report that has not yet been matched to an official "
        "DataSF row. It is drawn with a dashed line and excluded from the official KPI. Candidate "
        "matches are flagged for review but are never auto-reconciled. Once `matched_official_record_id` "
        "is filled in, that provisional row no longer contributes to the combined total."
    )
    st.subheader("Modes and revisions")
    st.markdown(
        "The app preserves DataSF’s `deceased` value and adds a transparent display taxonomy. "
        "Standup powered devices remain micromobility; they are not silently relabeled as bicycles. "
        "Every refresh stores a timestamped raw response and normalized Parquet snapshot. Additions, "
        "removals, date changes, location changes, and mode reclassifications are appended to the "
        "revision log. The first snapshot is a baseline, not hundreds of fake additions."
    )
    st.warning(
        "Provisional public reports may later be excluded under the City protocol or reclassified. "
        "This tracker is a research and transparency tool, not an official City publication."
    )
    st.markdown(
        "Sources: [official DataSF fatality dataset](https://data.sfgov.org/d/dau3-4s8f), "
        "[SF.gov traffic fatalities page](https://www.sf.gov/data--traffic-fatalities), and "
        "[DataSF victim-level cross-check](https://data.sfgov.org/d/nwes-mmgh)."
    )

st.divider()
st.markdown(
    f'<div class="source-note">Snapshot fetched {pd.to_datetime(status["fetched_at"]):%B %-d, %Y at %H:%M UTC}. '
    'Research by William W. Riggs. '
    '<a href="https://github.com/williamwriggs/SF-traffic-fatality-tracker" '
    'target="_blank" rel="noopener noreferrer">Source code and methodology on GitHub</a> are '
    "released under the MIT License. Values can change when City agencies reconcile records.</div>",
    unsafe_allow_html=True,
)
