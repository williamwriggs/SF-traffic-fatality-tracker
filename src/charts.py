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
    comparator = monthly_cumulative(official, comparison_year)
    current = monthly_cumulative(combined, current_year)
    current_official = monthly_cumulative(official, current_year)
    current_rows = combined[combined["year"].eq(current_year)]
    official_rows = official[official["year"].eq(current_year)]
    latest_official_month = int(official_rows["month"].max()) if not official_rows.empty else 1
    latest_current_month = int(current_rows["month"].max()) if not current_rows.empty else latest_official_month

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=comparator["month"],
            y=comparator["official_cumulative"],
            mode="lines+markers",
            name=f"{comparison_year} (full year = {int(comparator['official'].sum())})",
            line={"color": COLORS["comparison"], "width": 3},
            marker={"size": 7},
            hovertemplate="%{x}: %{y} fatalities<extra></extra>",
        )
    )
    official_part = current_official[current_official["month"].le(latest_official_month)]
    fig.add_trace(
        go.Scatter(
            x=official_part["month"],
            y=official_part["official_cumulative"],
            mode="lines+markers",
            name=f"{current_year} official ({len(official_rows)})",
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
                name="Provisional extension",
                line={"color": COLORS["current"], "width": 3, "dash": "dash"},
                marker={"size": 7, "symbol": "circle-open"},
                hovertemplate="%{x}: %{y} official + provisional<extra></extra>",
            )
        )

    current_mix = mode_counts(current_rows, current_year)
    comparison_mix = mode_counts(official, comparison_year)
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
    fig.add_annotation(
        x=bar_positions["current"],
        y=combined_total + 0.6,
        text=f"<b>{as_of:%b. %-d, %Y}</b><br>official + provisional = {combined_total}",
        showarrow=False,
        font={"color": COLORS["current"], "size": 13},
    )
    comparison_total = len(official[official["year"].eq(comparison_year)])
    fig.add_annotation(
        x=bar_positions["comparison"],
        y=comparison_total + 0.6,
        text=f"<b>Dec. {comparison_year}</b><br>total = {comparison_total}",
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


def annual_mode_chart(records: pd.DataFrame, start_year: int = 2014) -> go.Figure:
    annual = annual_mode_counts(records, start_year)
    fig = px.bar(
        annual,
        x="year",
        y="fatalities",
        color="normalized_mode",
        category_orders={"normalized_mode": MODE_ORDER},
        color_discrete_map=COLORS,
        labels={"year": "Collision year", "fatalities": "Fatalities", "normalized_mode": "Mode"},
    )
    fig.update_layout(
        title={
            "text": "Annual traffic fatalities by mode<br><sup>Official victim-level DataSF records</sup>",
            "x": 0,
        },
        bargap=0.22,
    )
    return _base_layout(fig, 480)


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
