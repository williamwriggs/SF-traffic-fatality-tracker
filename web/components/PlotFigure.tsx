"use client";

import dynamic from "next/dynamic";
import type { Config, Data, Layout } from "plotly.js";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface PlotFigureProps {
  data: Data[];
  layout: Partial<Layout>;
  config?: Partial<Config>;
  className?: string;
}

export default function PlotFigure({ data, layout, config, className }: PlotFigureProps) {
  return (
    <div className={className ?? "plot-wrap"}>
      <Plot
        data={data}
        layout={{ ...layout, autosize: true }}
        config={{
          displaylogo: false,
          responsive: true,
          scrollZoom: false,
          modeBarButtonsToRemove: ["lasso2d", "select2d"],
          toImageButtonOptions: { format: "png", scale: 2 },
          ...config,
        }}
        useResizeHandler
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  );
}
