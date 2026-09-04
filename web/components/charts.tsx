"use client";

import type { Data, Layout } from "plotly.js";
import PlotFigure from "./PlotFigure";
import type { FatalityRecord } from "@/lib/types";
import {
  COLORS,
  MODE_ORDER,
  MONTHS,
  YEAR_PALETTE,
  countModes,
  isCompleteYear,
  monthlyCumulative,
} from "@/lib/tracker";

const baseLayout: Partial<Layout> = {
  paper_bgcolor: COLORS.paper,
  plot_bgcolor: COLORS.paper,
  font: { family: "Arial, Helvetica, sans-serif", color: COLORS.ink, size: 13 },
  hoverlabel: { font: { family: "Arial, Helvetica, sans-serif" } },
  margin: { l: 58, r: 24, t: 26, b: 54 },
  legend: { orientation: "h", x: 0, y: 1.12, xanchor: "left", yanchor: "bottom" },
  xaxis: { showgrid: false, linecolor: COLORS.ink, linewidth: 1, fixedrange: false },
  yaxis: {
    gridcolor: COLORS.grid,
    griddash: "dash",
    zeroline: false,
    linecolor: COLORS.ink,
    linewidth: 1,
    fixedrange: false,
  },
};

function yearSeries(
  records: FatalityRecord[],
  year: number,
  color: string,
  width: number,
): Data[] {
  const selected = records.filter((record) => record.year === year);
  const officialRows = selected.filter((record) => record.record_status === "official");
  if (!selected.length) return [];
  const monthly = monthlyCumulative(records, year);
  const complete = isCompleteYear(records, year);
  const latestOfficialMonth = complete
    ? 12
    : Math.max(1, ...officialRows.map((record) => record.month));
  const latestCombinedMonth = complete ? 12 : Math.max(1, ...selected.map((record) => record.month));
  const provisional = selected.filter((record) => record.record_status === "provisional").length;
  const total = selected.length;
  const name = provisional
    ? `${year} · ${total} (${provisional} provisional)`
    : complete
      ? `${year} · full year = ${total}`
      : `${year} · official = ${officialRows.length}`;
  const officialPoints = monthly.slice(0, latestOfficialMonth);
  const traces: Data[] = [
    {
      type: "scatter",
      mode: "lines+markers",
      x: officialPoints.map((point) => point.month),
      y: officialPoints.map((point) => point.official),
      name,
      legendgroup: String(year),
      line: { color, width },
      marker: { size: width >= 4 ? 8 : 6 },
      hovertemplate: `${year} %{x}: %{y} official fatalities<extra></extra>`,
    },
  ];
  if (provisional && latestCombinedMonth > latestOfficialMonth) {
    const provisionalPoints = monthly.slice(latestOfficialMonth - 1, latestCombinedMonth);
    traces.push({
      type: "scatter",
      mode: "lines+markers",
      x: provisionalPoints.map((point) => point.month),
      y: provisionalPoints.map((point, index) =>
        index === 0 ? officialPoints.at(-1)?.official ?? 0 : point.combined,
      ),
      name: `${year} provisional extension`,
      legendgroup: String(year),
      showlegend: false,
      line: { color, width, dash: "dash" },
      marker: { size: 7, symbol: "circle-open" },
      hovertemplate: `${year} %{x}: %{y} official + provisional<extra></extra>`,
    });
  }
  return traces;
}

interface HeroChartProps {
  records: FatalityRecord[];
  focusYear: number;
  comparisonYear: number;
  multiYears: number[];
  view: "detail" | "multi";
}

export function HeroChart({ records, focusYear, comparisonYear, multiYears, view }: HeroChartProps) {
  const years = view === "detail" ? [comparisonYear, focusYear] : [...new Set(multiYears)].sort();
  const data = years.flatMap((year, index) =>
    yearSeries(
      records,
      year,
      year === focusYear
        ? COLORS.current
        : view === "detail"
          ? COLORS.comparison
          : YEAR_PALETTE[index % YEAR_PALETTE.length],
      year === focusYear ? 4 : 2.7,
    ),
  );
  const maxTotal = Math.max(
    10,
    ...years.map((year) => records.filter((record) => record.year === year).length + 4),
  );
  const layout: Partial<Layout> = {
    ...baseLayout,
    height: view === "detail" ? 570 : 520,
    margin: { l: 58, r: 24, t: 72, b: 52 },
    xaxis: {
      ...baseLayout.xaxis,
      tickmode: "array",
      tickvals: MONTHS.map((_, index) => index + 1),
      ticktext: MONTHS,
      range: [0.75, 12.25],
    },
    yaxis: {
      ...baseLayout.yaxis,
      title: { text: "Cumulative traffic fatalities", standoff: 12 },
      range: [0, maxTotal],
      dtick: 5,
    },
  };
  return <PlotFigure data={data} layout={layout} />;
}

export function ModeChart({ records, year }: { records: FatalityRecord[]; year: number }) {
  const counts = countModes(records.filter((record) => record.year === year));
  const data: Data[] = [
    {
      type: "bar",
      orientation: "h",
      x: MODE_ORDER.map((mode) => counts[mode]),
      y: [...MODE_ORDER],
      marker: { color: MODE_ORDER.map((mode) => COLORS[mode]) },
      text: MODE_ORDER.map((mode) => String(counts[mode])),
      textposition: "outside",
      cliponaxis: false,
      hovertemplate: "%{y}: %{x}<extra></extra>",
    },
  ];
  return (
    <PlotFigure
      data={data}
      layout={{
        ...baseLayout,
        height: 340,
        margin: { l: 174, r: 36, t: 12, b: 44 },
        showlegend: false,
        xaxis: { ...baseLayout.xaxis, gridcolor: COLORS.grid, showgrid: true },
        yaxis: { autorange: "reversed", showgrid: false, linecolor: COLORS.ink },
      }}
    />
  );
}

export function AnnualModeChart({ records, normalized }: { records: FatalityRecord[]; normalized: boolean }) {
  const official = records.filter((record) => record.record_status === "official" && record.year >= 2014);
  const years = [...new Set(official.map((record) => record.year))].sort();
  const totals = new Map(years.map((year) => [year, official.filter((record) => record.year === year).length]));
  const data: Data[] = MODE_ORDER.map((mode) => ({
    type: "bar",
    name: mode,
    x: years,
    y: years.map((year) => {
      const value = official.filter((record) => record.year === year && record.normalized_mode === mode).length;
      return normalized ? (value / (totals.get(year) || 1)) * 100 : value;
    }),
    customdata: years.map((year) => {
      const count = official.filter((record) => record.year === year && record.normalized_mode === mode).length;
      return [count, totals.get(year) ?? 0];
    }),
    marker: { color: COLORS[mode] },
    hovertemplate: normalized
      ? `<b>${mode}</b><br>Collision year=%{x}<br>Share=%{y:.1f}%<br>Fatalities=%{customdata[0]} of %{customdata[1]}<extra></extra>`
      : `<b>${mode}</b><br>Collision year=%{x}<br>Fatalities=%{y}<br>Annual total=%{customdata[1]}<extra></extra>`,
  }));
  return (
    <PlotFigure
      data={data}
      layout={{
        ...baseLayout,
        barmode: "stack",
        bargap: 0.2,
        height: 500,
        margin: { l: 58, r: 24, t: 70, b: 54 },
        xaxis: { ...baseLayout.xaxis, title: { text: "Collision year" }, dtick: 2 },
        yaxis: {
          ...baseLayout.yaxis,
          title: { text: normalized ? "Share of annual fatalities" : "Fatalities", standoff: 10 },
          range: normalized ? [0, 100] : undefined,
          ticksuffix: normalized ? "%" : undefined,
        },
      }}
    />
  );
}

export function SeasonalityChart({ records }: { records: FatalityRecord[] }) {
  const official = records.filter((record) => record.record_status === "official" && record.year >= 2014);
  const years = [...new Set(official.map((record) => record.year))].sort((a, b) => b - a);
  const z = years.map((year) =>
    MONTHS.map((_, index) => official.filter((record) => record.year === year && record.month === index + 1).length),
  );
  const data: Data[] = [
    {
      type: "heatmap",
      x: MONTHS,
      y: years.map(String),
      z,
      texttemplate: "%{z}",
      colorscale: [[0, "#f1f0eb"], [0.5, "#719a9c"], [1, "#176f82"]],
      colorbar: { title: { text: "Fatalities" }, thickness: 14 },
      hovertemplate: "%{y} %{x}: %{z}<extra></extra>",
    },
  ];
  return <PlotFigure data={data} layout={{ ...baseLayout, height: 430, margin: { l: 48, r: 70, t: 16, b: 52 } }} />;
}

export function MapChart({ records }: { records: FatalityRecord[] }) {
  const plotted = records.filter((record) => record.latitude !== null && record.longitude !== null);
  const data: Data[] = MODE_ORDER.map((mode) => {
    const selected = plotted.filter((record) => record.normalized_mode === mode);
    return {
      type: "scattermapbox",
      mode: "markers",
      name: mode,
      lat: selected.map((record) => record.latitude),
      lon: selected.map((record) => record.longitude),
      text: selected.map((record) => record.location ?? "Location unavailable"),
      customdata: selected.map((record) => [record.collision_date.slice(0, 10), record.record_status, record.neighborhood ?? ""]),
      marker: { size: 10, opacity: 0.82, color: COLORS[mode] },
      hovertemplate: "<b>%{text}</b><br>%{customdata[0]}<br>%{customdata[1]}<br>%{customdata[2]}<extra></extra>",
    } as Data;
  });
  return (
    <PlotFigure
      data={data}
      layout={{
        ...baseLayout,
        height: 520,
        margin: { l: 0, r: 0, t: 72, b: 0 },
        mapbox: { style: "carto-positron", center: { lat: 37.76, lon: -122.44 }, zoom: 10.4 },
      }}
    />
  );
}
