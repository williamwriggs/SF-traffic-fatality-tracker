"""Export the publication hero chart without running Streamlit."""

from __future__ import annotations

import argparse
import calendar
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from src.charts import COLORS, hero_chart
from src.metrics import MODE_ORDER, mode_counts, monthly_cumulative

ROOT = Path(__file__).resolve().parents[1]


def write_matplotlib_fallback(
    official: pd.DataFrame,
    combined: pd.DataFrame,
    current_year: int,
    comparison_year: int,
    as_of: pd.Timestamp,
    output: Path,
    width: int,
    height: int,
) -> None:
    """Render a publication PNG when Chrome/Kaleido is unavailable."""
    comparator = monthly_cumulative(official, comparison_year)
    current = monthly_cumulative(combined, current_year)
    current_official = monthly_cumulative(official, current_year)
    official_rows = official[official["year"].eq(current_year)]
    current_rows = combined[combined["year"].eq(current_year)]
    latest_official_month = int(official_rows["month"].max())
    latest_month = int(current_rows["month"].max())

    dpi = 100
    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi, facecolor=COLORS["paper"])
    ax = fig.add_axes([0.07, 0.17, 0.90, 0.56], facecolor=COLORS["paper"])
    ax.plot(
        comparator["month"],
        comparator["official_cumulative"],
        color=COLORS["comparison"],
        marker="o",
        linewidth=3,
        markersize=7,
    )
    official_part = current_official[current_official["month"].le(latest_official_month)]
    ax.plot(
        official_part["month"],
        official_part["official_cumulative"],
        color=COLORS["current"],
        marker="o",
        linewidth=3,
        markersize=7,
    )
    if latest_month > latest_official_month:
        provisional_part = current[
            current["month"].between(latest_official_month, latest_month)
        ].copy()
        provisional_part.loc[
            provisional_part["month"].eq(latest_official_month), "combined_cumulative"
        ] = int(official_part.iloc[-1]["official_cumulative"])
        ax.plot(
            provisional_part["month"],
            provisional_part["combined_cumulative"],
            color=COLORS["current"],
            marker="o",
            markerfacecolor=COLORS["paper"],
            linestyle="--",
            linewidth=3,
            markersize=7,
        )

    current_mix = mode_counts(current_rows)
    comparison_mix = mode_counts(official, comparison_year)
    positions = [latest_month + 0.25, 13.15]
    bottoms = [0, 0]
    for mode in MODE_ORDER:
        values = [
            int(current_mix.loc[current_mix["normalized_mode"].eq(mode), "fatalities"].sum()),
            int(
                comparison_mix.loc[
                    comparison_mix["normalized_mode"].eq(mode), "fatalities"
                ].sum()
            ),
        ]
        bars = ax.bar(
            positions,
            values,
            bottom=bottoms,
            width=0.58,
            color=COLORS.get(mode, COLORS["Other / Unresolved"]),
            edgecolor=COLORS["paper"],
            linewidth=1,
        )
        for bar, value, bottom in zip(bars, values, bottoms, strict=True):
            if value:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bottom + value / 2,
                    str(value),
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=11,
                    fontweight="bold",
                )
        bottoms = [bottoms[i] + values[i] for i in range(2)]

    current_total = len(current_rows)
    comparison_total = len(official[official["year"].eq(comparison_year)])
    ax.text(
        positions[0],
        current_total + 0.7,
        f"{as_of:%b. %-d, %Y}\nofficial + provisional = {current_total}",
        ha="center",
        va="bottom",
        color=COLORS["current"],
        fontsize=11,
        fontweight="bold",
    )
    ax.text(
        positions[1],
        comparison_total + 0.7,
        f"Dec. {comparison_year}\ntotal = {comparison_total}",
        ha="center",
        va="bottom",
        color=COLORS["comparison"],
        fontsize=11,
        fontweight="bold",
    )

    y_max = max(current_total, comparison_total) + 5
    ax.set_xlim(0.45, 13.65)
    ax.set_ylim(0, y_max)
    ax.set_xticks(
        range(1, 13),
        [calendar.month_abbr[i] for i in range(1, 13)],
        rotation=45,
        ha="right",
    )
    ax.set_yticks(range(0, y_max + 1, 5))
    ax.set_ylabel("Cumulative traffic fatalities", fontsize=13, fontweight="bold")
    ax.grid(axis="y", color=COLORS["grid"], linestyle=(0, (4, 4)), linewidth=1)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(COLORS["ink"])
    ax.tick_params(labelsize=11, colors=COLORS["ink"])

    fig.text(
        0.02,
        0.955,
        f"Traffic Fatalities in San Francisco: {comparison_year} vs. {current_year}",
        fontsize=28,
        fontweight="bold",
        color=COLORS["ink"],
        va="top",
    )
    fig.text(
        0.02,
        0.902,
        "Cumulative fatalities by collision month, with fatalities by travel mode",
        fontsize=16,
        color=COLORS["muted"],
        va="top",
    )
    fig.text(
        0.02,
        0.862,
        f"Source: SFDPH/SFPD/SFMTA via DataSF; provisional reports checked {as_of:%B %-d, %Y}.",
        fontsize=12,
        color=COLORS["muted"],
        style="italic",
        va="top",
    )
    legend_handles = [
        Line2D(
            [0], [0], color=COLORS["comparison"], marker="o", lw=3,
            label=f"{comparison_year} (full year = {comparison_total})",
        ),
        Line2D(
            [0], [0], color=COLORS["current"], marker="o", lw=3,
            label=f"{current_year} official ({len(official_rows)})",
        ),
        Line2D(
            [0], [0], color=COLORS["current"], marker="o",
            markerfacecolor=COLORS["paper"], linestyle="--", lw=3,
            label="Provisional extension",
        ),
        *[Patch(facecolor=COLORS[mode], label=mode) for mode in MODE_ORDER],
    ]
    fig.legend(
        handles=legend_handles,
        loc="upper left",
        bbox_to_anchor=(0.065, 0.82),
        ncol=4,
        frameon=False,
        fontsize=10.5,
        handlelength=2.2,
        columnspacing=1.5,
    )
    fig.text(
        0.02,
        0.045,
        "Note: City records can lag and be revised. Dashed values are public reports not yet matched "
        "to the Vision Zero fatality table. Native City mode is retained alongside the display taxonomy.",
        fontsize=10.5,
        color=COLORS["muted"],
        va="bottom",
        wrap=True,
    )
    fig.savefig(output, dpi=dpi, facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--current-year", type=int)
    parser.add_argument("--comparison-year", type=int, default=2017)
    parser.add_argument("--as-of", type=pd.Timestamp)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "assets" / "generated_hero.png"
    )
    parser.add_argument("--width", type=int, default=1800)
    parser.add_argument("--height", type=int, default=1080)
    args = parser.parse_args()

    official = pd.read_parquet(args.data_dir / "processed" / "fatalities.parquet")
    combined = pd.read_parquet(args.data_dir / "processed" / "combined.parquet")
    current_year = args.current_year or int(combined["year"].max())
    as_of = args.as_of or pd.Timestamp.today().normalize()
    figure = hero_chart(official, combined, current_year, args.comparison_year, as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        figure.write_image(args.output, width=args.width, height=args.height, scale=1)
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"Kaleido export unavailable ({type(exc).__name__}); using Matplotlib fallback")
        write_matplotlib_fallback(
            official,
            combined,
            current_year,
            args.comparison_year,
            as_of,
            args.output,
            args.width,
            args.height,
        )
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
