import { describe, expect, it } from "vitest";
import { compareSnapshots, monthlyCumulative, summaryMetrics } from "./tracker";
import type { FatalityRecord, SnapshotRecord } from "./types";

const row = (id: string, date: string, status: "official" | "provisional" = "official"): FatalityRecord => ({
  record_id: id,
  collision_date: date,
  death_date: date,
  year: Number(date.slice(0, 4)),
  month: Number(date.slice(5, 7)),
  normalized_mode: "While Walking",
  native_victim_role: "Pedestrian",
  native_vehicle_type: null,
  record_status: status,
  classification_status: null,
  latitude: null,
  longitude: null,
  location: null,
  neighborhood: null,
  supervisor_district: null,
  police_district: null,
  source_dataset: null,
  notes: null,
});

describe("tracker metrics", () => {
  it("separates official and provisional cumulative values", () => {
    const result = monthlyCumulative([
      row("a", "2026-01-04"),
      row("b", "2026-02-04", "provisional"),
    ], 2026);
    expect(result[1]).toEqual({ month: 2, official: 1, combined: 2 });
  });

  it("calculates same-date comparison metrics", () => {
    const metrics = summaryMetrics([
      row("a", "2025-01-04"),
      row("b", "2025-10-04"),
      row("c", "2026-01-04"),
      row("d", "2026-02-04", "provisional"),
    ], 2026, 2025, new Date("2026-02-10T12:00:00Z"));
    expect(metrics.comparison).toBe(1);
    expect(metrics.combined).toBe(2);
    expect(metrics.change).toBe(1);
  });

  it("detects additions and field changes between snapshots", () => {
    const before = [{ record_id: "a", collision_date: "2025-01-01", normalized_mode: "While Walking" }] as SnapshotRecord[];
    const after = [
      { record_id: "a", collision_date: "2025-01-02", normalized_mode: "While Walking" },
      { record_id: "b", collision_date: "2025-01-02", normalized_mode: "While Cycling" },
    ] as SnapshotRecord[];
    const changes = compareSnapshots(before, after);
    expect(changes.some((change) => change.change_type === "addition")).toBe(true);
    expect(changes.some((change) => change.change_type === "date_correction")).toBe(true);
  });
});
