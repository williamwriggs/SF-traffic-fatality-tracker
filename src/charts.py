"""Publication-style Plotly figures for the tracker."""

from __future__ import annotations

import calendar

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.metrics import (
    MODE_ORDER,
    annual_mode_counts,
    mode_counts,
    monthly_cumulative,
    seasonality_matrix,
)

COLORS = {
    "comparison": "#E76600",
    "current": "#132A70",
    "While Walking": "#176F82",
    "While Driving / Riding": "#7D728F",
    "While Riding a Motorcycle": "#A06C4F",
    "While Cycling": "#719A9C",
    "Micromobility": "#9CBABD",
    "Other / Unresolved": "#9A9A95",
    "ink": "#1F2429",
    "muted": "#62676C",
    "grid": "#CDD0D2",
    "paper": "#FBFAF7",
}

YEAR_PALETTE = ["#E76600", "#176F82", "#7D728F", "#A06C4F", "#719A9C", "#8A7D25"]


def is_complete_year(records: pd.DataFrame, year: int) -> bool:
    """A year is complete when the dataset contains at least one later year."""
    years = pd.to_numeric(records.get("year", pd.Series(dtype="Int64")), errors="coerce")
    return bool(not years.dropna().empty and int(year) < int(years.max()))


def coverage_date(records: pd.DataFrame, year: int, as_of: pd.Timestamp) -> pd.Timestamp:
    """Return Dec. 31 for historical years and the checked-through date for the latest year."""
    if is_complete_year(records, year):
        return pd.Timestamp(year=int(year), month=12, day=31)
    date = pd.Timestamp(as_of)
    return date.tz_localize(None) if date.tzinfo else date


def coverage_label(records: pd.DataFrame, year: int, as_of: pd.Timestamp) -> str:
    date = coverage_date(records, year, as_of)
    return f"Dec. {year}" if is_complete_year(records, year) else date.strftime("%b. %-d, %Y")


def _series_label(records: pd.DataFrame, year: int, total: int, provisional: int = 0) -> str:
    if provisional:
        return f"{year} · {total} ({provisional} provisional)"
    if is_complete_year(records, year):
        return f"{year} · full year = {total}"
    return f"{year} · official = {total}"


def _base_layout(fig: go.Figure, height: int = 540) -> go.Figure:
    fig.update_layout(
        font={"family": "Arial, sans-serif", "color": COLORS["ink"], "size": 14},
        paper_bgcolor=COLORS["paper"],
        plot_bgcolor=COLORS["paper"],
        height=height,
        margin={"l": 55, "r": 35, "t": 125, "b": 65},
        hoverlabel={"font_family": "Arial, sans-serif"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
    )
    fig.update_xaxes(showgrid=False, linecolor=COLORS["ink"], linewidth=1)
    fig.update_yaxes(
        gridcolor=COLORS["grid"],
        griddash="dash",
        zeroline=False,
        linecolor=COLORS["ink"],
        linewidth=1,
    )
    return fig


def hero_chart(
    official: pd.DataFrame,
    combined: pd.DataFrame,
    current_year: int,
    comparison_year: int,
    as_of: pd.Timestamp,
) -> go.Figure:
    comparator = monthly_cumulative(combined, comparison_year)
    comparator_official = monthly_cumulative(official, comparison_year)
    current = monthly_cumulative(combined, current_year)
    current_official = monthly_cumulative(official, current_year)
    current_rows = combined[combined["year"].eq(current_year)]
    official_rows = official[official["year"].eq(current_year)]
    comparison_rows = combined[combined["year"].eq(comparison_year)]
    comparison_official_rows = official[official["year"].eq(comparison_year)]
    latest_official_month = (
        12
        if is_complete_year(combined, current_year)
        else int(official_rows["month"].max())
        if not official_rows.empty
        else 1
    )
    latest_current_month = (
        12
        if is_complete_year(combined, current_year)
        else int(current_rows["month"].max())
        if not current_rows.empty
        else latest_official_month
    )
    latest_comparison_official_month = (
        12
        if is_complete_year(combined, comparison_year)
        else int(comparison_official_rows["month"].max())
        if not comparison_official_rows.empty
        else 1
    )
    latest_comparison_month = (
        12
        if is_complete_year(combined, comparison_year)
        else int(comparison_rows["month"].max())
        if not comparison_rows.empty
        else latest_comparison_official_month
    )

    fig = go.Figure()
    comparison_provisional_total = int(
        comparison_rows["record_status"].eq("provisional").sum()
    )
    comparison_total = len(comparison_rows)
    comparison_official_part = comparator_official[
        comparator_official["month"].le(latest_comparison_official_month)
    ]
    fig.add_trace(
        go.Scatter(
            x=comparison_official_part["month"],
            y=comparison_official_part["official_cumulative"],
            mode="lines+markers",
            name=_series_label(
                combined,
                comparison_year,
                comparison_total,
                comparison_provisional_total,
            ),
            line={"color": COLORS["comparison"], "width": 3},
            marker={"size": 7},
            hovertemplate="%{x}: %{y} fatalities<extra></extra>",
        )
    )
    if (
        comparison_provisional_total
        and latest_comparison_month > latest_comparison_official_month
    ):
        comparison_provisional_part = comparator[
            comparator["month"].between(
                latest_comparison_official_month, latest_comparison_month
            )
        ].copy()
        comparison_provisional_part.loc[
            comparison_provisional_part["month"].eq(latest_comparison_official_month),
            "combined_cumulative",
        ] = int(comparison_official_part.iloc[-1]["official_cumulative"])
        fig.add_trace(
            go.Scatter(
                x=comparison_provisional_part["month"],
                y=comparison_provisional_part["combined_cumulative"],
                mode="lines+markers",
                name=f"{comparison_year} provisional extension",
                line={"color": COLORS["comparison"], "width": 3, "dash": "dash"},
                marker={"size": 7, "symbol": "circle-open"},
                hovertemplate="%{x}: %{y} official + provisional<extra></extra>",
            )
        )
    official_part = current_official[current_official["month"].le(latest_official_month)]
    fig.add_trace(
        go.Scatter(
            x=official_part["month"],
            y=official_part["official_cumulative"],
            mode="lines+markers",
            name=_series_label(combined, current_year, len(official_rows)),
            line={"color": COLORS["current"], "width": 3},
            marker={"size": 7},
            hovertemplate="%{x}: %{y} official fatalities<extra></extra>",
        )
    )
    if latest_current_month > latest_official_month:
        provisional_part = current[
            current["month"].between(latest_official_month, latest_current_month)
        ].copy()
        provisional_part.loc[
            provisional_part["month"].eq(latest_official_month), "combined_cumulative"
        ] = int(current_official.loc[
            current_official["month"].eq(latest_official_month), "official_cumulative"
        ].iloc[0])
        fig.add_trace(
            go.Scatter(
                x=provisional_part["month"],
                y=provisional_part["combined_cumulative"],
                mode="lines+markers",
                name=f"{current_year} provisional extension",
                line={"color": COLORS["current"], "width": 3, "dash": "dash"},
                marker={"size": 7, "symbol": "circle-open"},
                hovertemplate="%{x}: %{y} official + provisional<extra></extra>",
            )
        )

    current_mix = mode_counts(current_rows, current_year)
    comparison_mix = mode_counts(comparison_rows, comparison_year)
    bar_positions = {"current": latest_current_month + 0.22, "comparison": 13.1}
    for mode in MODE_ORDER:
        current_value = int(
            current_mix.loc[current_mix["normalized_mode"].eq(mode), "fatalities"].sum()
        )
        comparison_value = int(
            comparison_mix.loc[comparison_mix["normalized_mode"].eq(mode), "fatalities"].sum()
        )
        fig.add_trace(
            go.Bar(
                x=[bar_positions["current"], bar_positions["comparison"]],
                y=[current_value, comparison_value],
                name=mode,
                legendgroup=mode,
                marker={"color": COLORS.get(mode, COLORS["Other / Unresolved"]), "line_width": 0.7},
                width=0.58,
                text=[current_value or "", comparison_value or ""],
                textposition="inside",
                textfont={"color": "white", "size": 12},
                hovertemplate=f"{mode}: %{{y}}<extra></extra>",
            )
        )
    fig.update_layout(barmode="stack")
    combined_total = len(current_rows)
    provisional_total = int(current_rows["record_status"].eq("provisional").sum())
    if provisional_total:
        current_total_label = f"official + provisional = {combined_total}"
    elif is_complete_year(combined, current_year):
        current_total_label = f"total = {combined_total}"
    else:
        current_total_label = f"official = {combined_total}"
    fig.add_annotation(
        x=bar_positions["current"],
        y=combined_total + 0.6,
        text=(
            f"<b>{coverage_label(combined, current_year, as_of)}</b>"
            f"<br>{current_total_label}"
        ),
        showarrow=False,
        font={"color": COLORS["current"], "size": 13},
    )
    if comparison_provisional_total:
        comparison_total_label = f"official + provisional = {comparison_total}"
    elif is_complete_year(combined, comparison_year):
        comparison_total_label = f"total = {comparison_total}"
    else:
        comparison_total_label = f"official = {comparison_total}"
    fig.add_annotation(
        x=bar_positions["comparison"],
        y=comparison_total + 0.6,
        text=(
            f"<b>{coverage_label(combined, comparison_year, as_of)}</b>"
            f"<br>{comparison_total_label}"
        ),
        showarrow=False,
        font={"color": COLORS["comparison"], "size": 13},
    )
    fig.update_xaxes(
        tickmode="array",
        tickvals=list(range(1, 13)),
        ticktext=[calendar.month_abbr[i] for i in range(1, 13)],
        range=[0.45, 13.65],
        title=None,
    )
    max_y = max(combined_total, comparison_total, 5)
    fig.update_yaxes(range=[0, max_y + 4], title="Cumulative traffic fatalities", dtick=5)
    fig.update_layout(
        title={
            "text": (
                f"Traffic Fatalities in San Francisco: {comparison_year} vs. {current_year}"
                "<br><sup>Cumulative fatalities by collision month; dashed segment is unreconciled</sup>"
            ),
            "x": 0,
            "xanchor": "left",
        }
    )
    styled = _base_layout(fig, 720)
    styled.update_layout(margin={"l": 55, "r": 35, "t": 205, "b": 65})
    return styled


def multi_year_chart(
    official: pd.DataFrame,
    combined: pd.DataFrame,
    years: list[int],
    focus_year: int,
) -> go.Figure:
    """Compare cumulative monthly trajectories for up to six selected years."""
    selected_years = sorted({int(year) for year in years})
    if not selected_years:
        return go.Figure()

    other_years = [year for year in selected_years if year != focus_year]
    color_map = {focus_year: COLORS["current"]}
    for year, color in zip(other_years, YEAR_PALETTE, strict=False):
        color_map[year] = color

    fig = go.Figure()
    max_total = 0
    for year in selected_years:
        year_official = official[official["year"].eq(year)]
        year_combined = combined[combined["year"].eq(year)]
        if year_official.empty and year_combined.empty:
            continue
        official_months = monthly_cumulative(official, year)
        latest_official_month = (
            12 if is_complete_year(combined, year) else int(year_official["month"].max())
        )
        official_part = official_months[official_months["month"].le(latest_official_month)]
        color = color_map.get(year, YEAR_PALETTE[0])
        width = 4 if year == focus_year else 2.5
        provisional_total = int(year_combined["record_status"].eq("provisional").sum())
        combined_total = len(year_combined) if provisional_total else len(year_official)
        max_total = max(max_total, combined_total)
        fig.add_trace(
            go.Scatter(
                x=official_part["month"],
                y=official_part["official_cumulative"],
                mode="lines+markers",
                name=_series_label(combined, year, combined_total, provisional_total),
                legendgroup=str(year),
                line={"color": color, "width": width},
                marker={"size": 8 if year == focus_year else 6},
                hovertemplate=f"{year} %{{x}}: %{{y}} official fatalities<extra></extra>",
            )
        )

        latest_combined_month = (
            12
            if is_complete_year(combined, year)
            else int(year_combined["month"].max())
            if not year_combined.empty
            else latest_official_month
        )
        if provisional_total and latest_combined_month > latest_official_month:
            combined_months = monthly_cumulative(combined, year)
            provisional_part = combined_months[
                combined_months["month"].between(latest_official_month, latest_combined_month)
            ].copy()
            provisional_part.loc[
                provisional_part["month"].eq(latest_official_month), "combined_cumulative"
            ] = int(official_part.iloc[-1]["official_cumulative"])
            fig.add_trace(
                go.Scatter(
                    x=provisional_part["month"],
                    y=provisional_part["combined_cumulative"],
                    mode="lines+markers",
                    name=f"{year} provisional extension",
                    legendgroup=str(year),
                    showlegend=False,
                    line={"color": color, "width": width, "dash": "dash"},
                    marker={"size": 7, "symbol": "circle-open"},
                    hovertemplate=(
                        f"{year} %{{x}}: %{{y}} official + provisional<extra></extra>"
                    ),
                )
            )

    fig.update_xaxes(
        tickmode="array",
        tickvals=list(range(1, 13)),
        ticktext=[calendar.month_abbr[i] for i in range(1, 13)],
        range=[0.75, 12.25],
        title=None,
    )
    fig.update_yaxes(
        range=[0, max(max_total + 4, 10)],
        title="Cumulative traffic fatalities",
        dtick=5,
    )
    fig.update_layout(
        title={
            "text": (
                "Traffic Fatalities in San Francisco: Multi-year comparison"
                f"<br><sup>{', '.join(str(year) for year in selected_years)}; "
                "dashed segment is unreconciled</sup>"
            ),
            "x": 0,
            "xanchor": "left",
        }
    )
    styled = _base_layout(fig, 650)
    styled.update_layout(margin={"l": 55, "r": 35, "t": 165, "b": 65})
    return styled


def annual_mode_chart(
    records: pd.DataFrame,
    start_year: int = 2014,
    normalized: bool = False,
) -> go.Figure:
    annual = annual_mode_counts(records, start_year)
    annual["annual_total"] = annual.groupby("year")["fatalities"].transform("sum")
    annual["share"] = annual["fatalities"].div(annual["annual_total"]).mul(100)
    value_column = "share" if normalized else "fatalities"
    subtitle = (
        "Mode share within each year · each bar = 100% · latest year may be partial"
        if normalized
        else "Official victim-level DataSF records · latest year may be partial"
    )
    fig = px.bar(
        annual,
        x="year",
        y=value_column,
        color="normalized_mode",
        custom_data=["fatalities", "annual_total"],
        category_orders={"normalized_mode": MODE_ORDER},
        color_discrete_map=COLORS,
        labels={
            "year": "Collision year",
            "fatalities": "Fatalities",
            "share": "Share of annual fatalities",
            "normalized_mode": "Mode",
        },
    )
    if normalized:
        fig.update_traces(
            hovertemplate=(
                "<b>%{fullData.name}</b><br>Collision year=%{x}<br>"
                "Share=%{y:.1f}%<br>Fatalities=%{customdata[0]} of %{customdata[1]}"
                "<extra></extra>"
            )
        )
    else:
        fig.update_traces(
            hovertemplate=(
                "<b>%{fullData.name}</b><br>Collision year=%{x}<br>"
                "Fatalities=%{y}<br>Annual total=%{customdata[1]}<extra></extra>"
            )
        )
    _base_layout(fig, 560)
    fig.update_layout(
        title={
            "text": f"Annual traffic fatalities by mode<br><sup>{subtitle}</sup>",
            "x": 0,
            "xanchor": "left",
            "y": 0.98,
            "yanchor": "top",
        },
        bargap=0.22,
        margin={"l": 55, "r": 35, "t": 190, "b": 65},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.01,
            "x": 0,
            "xanchor": "left",
            "title": None,
        },
    )
    if normalized:
        fig.update_yaxes(range=[0, 100], ticksuffix="%", title="Share of annual fatalities")
    else:
        fig.update_yaxes(title="Fatalities")
    return fig


def seasonality_chart(records: pd.DataFrame, start_year: int = 2014) -> go.Figure:
    matrix = seasonality_matrix(records, start_year)
    fig = go.Figure(
        go.Heatmap(
            z=matrix.values,
            x=[calendar.month_abbr[i] for i in range(1, 13)],
            y=[str(int(year)) for year in matrix.index],
            colorscale=[[0, "#F1F0EB"], [0.5, "#719A9C"], [1, "#176F82"]],
            text=matrix.values,
            texttemplate="%{text}",
            colorbar={"title": "Fatalities"},
            hovertemplate="%{y} %{x}: %{z}<extra></extra>",
        )
    )
    fig.update_layout(
        title={"text": "Monthly seasonality<br><sup>Official fatalities by collision month</sup>", "x": 0}
    )
    return _base_layout(fig, 480)


def map_chart(records: pd.DataFrame) -> go.Figure:
    plotted = records.dropna(subset=["latitude", "longitude"]).copy()
    if plotted.empty:
        return go.Figure()
    plotted["date_label"] = plotted["collision_date"].dt.strftime("%b %-d, %Y")
    fig = px.scatter_map(
        plotted,
        lat="latitude",
        lon="longitude",
        color="normalized_mode",
        color_discrete_map=COLORS,
        category_orders={"normalized_mode": MODE_ORDER},
        hover_name="location",
        hover_data={
            "date_label": True,
            "record_status": True,
            "neighborhood": True,
            "latitude": False,
            "longitude": False,
        },
        zoom=10.5,
        center={"lat": 37.76, "lon": -122.44},
        map_style="carto-positron",
    )
    fig.update_traces(marker={"size": 12, "opacity": 0.82})
    fig.update_layout(
        title={"text": "Fatal crash locations<br><sup>Points reflect collision locations</sup>", "x": 0},
        margin={"l": 0, "r": 0, "t": 90, "b": 0},
        height=560,
        paper_bgcolor=COLORS["paper"],
        font={"family": "Arial, sans-serif", "color": COLORS["ink"]},
        legend={"orientation": "h", "y": 1.01},
    )
    return fig
