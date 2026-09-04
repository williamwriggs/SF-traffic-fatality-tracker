import { describe, expect, it } from "vitest";
import { compareSnapshots, coverageDate, monthlyCumulative, summaryMetrics } from "./tracker";
import type { FatalityRecord, SnapshotRecord, TrackerStatus } from "./types";

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
  const status = {
    fetched_at: "2026-09-04T18:28:04Z",
    source_data_as_of: "2026-07-08T00:00:00",
    provisional_checked_through: "2026-08-12T00:00:00",
  } as TrackerStatus;

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

  it("uses explicit review coverage rather than row-level data_as_of", () => {
    const records = [
      row("official", "2026-06-12"),
      row("provisional", "2026-08-07", "provisional"),
    ];

    expect(coverageDate(records, status, 2026, false).toISOString().slice(0, 10)).toBe("2026-06-12");
    expect(coverageDate(records, status, 2026, true).toISOString().slice(0, 10)).toBe("2026-08-12");
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

  it("ignores coordinate serialization noise but keeps material moves", () => {
    const before = [{ record_id: "a", latitude: 37.710409216678755 }] as SnapshotRecord[];
    const noise = [{ record_id: "a", latitude: 37.71040921667876 }] as SnapshotRecord[];
    const moved = [{ record_id: "a", latitude: 37.710509 }] as SnapshotRecord[];

    expect(compareSnapshots(before, noise)).toEqual([]);
    expect(compareSnapshots(before, moved)).toHaveLength(1);
    expect(compareSnapshots(before, moved)[0].change_type).toBe("location_correction");
    expect(compareSnapshots([{ record_id: "a", latitude: null }] as SnapshotRecord[], moved)).toHaveLength(1);
  });
});
