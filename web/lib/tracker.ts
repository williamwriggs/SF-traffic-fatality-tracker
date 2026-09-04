import type { FatalityRecord, SnapshotChange, SnapshotRecord, TrackerStatus } from "./types";

export const MODE_ORDER = [
  "While Walking",
  "While Driving / Riding",
  "While Riding a Motorcycle",
  "While Cycling",
  "Micromobility",
  "Other / Unresolved",
] as const;

export const COLORS: Record<string, string> = {
  comparison: "#e76600",
  current: "#132a70",
  "While Walking": "#176f82",
  "While Driving / Riding": "#7d728f",
  "While Riding a Motorcycle": "#a06c4f",
  "While Cycling": "#719a9c",
  Micromobility: "#9cbabd",
  "Other / Unresolved": "#9a9a95",
  ink: "#1f2429",
  muted: "#62676c",
  grid: "#cdd0d2",
  paper: "#fbfaf7",
};

export const YEAR_PALETTE = ["#e76600", "#176f82", "#7d728f", "#a06c4f", "#719a9c"];
export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function dateOnly(value: string): Date {
  return new Date(`${value.slice(0, 10)}T12:00:00Z`);
}

export function shortDate(value: string | null | undefined): string {
  if (!value) return "Unknown";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(dateOnly(value));
}

export function longDate(value: string | null | undefined): string {
  if (!value) return "Unknown";
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(dateOnly(value));
}

export function availableYears(records: FatalityRecord[]): number[] {
  return [...new Set(records.map((record) => record.year))].sort((a, b) => b - a);
}

export function isCompleteYear(records: FatalityRecord[], year: number): boolean {
  return year < Math.max(...records.map((record) => record.year));
}

export function coverageDate(
  records: FatalityRecord[],
  status: TrackerStatus,
  year: number,
  includeProvisional: boolean,
): Date {
  if (isCompleteYear(records, year)) return new Date(Date.UTC(year, 11, 31, 12));
  if (includeProvisional && status.provisional_checked_through) {
    return dateOnly(status.provisional_checked_through);
  }
  const latestOfficialCollision = records
    .filter((record) => record.year === year && record.record_status === "official")
    .map((record) => record.collision_date)
    .sort()
    .at(-1);
  return dateOnly(latestOfficialCollision || status.fetched_at);
}

export function filterThrough(records: FatalityRecord[], end: Date): FatalityRecord[] {
  return records.filter((record) => dateOnly(record.collision_date) <= end);
}

export interface MonthlyPoint {
  month: number;
  official: number;
  combined: number;
}

export function monthlyCumulative(records: FatalityRecord[], year: number): MonthlyPoint[] {
  const selected = records.filter((record) => record.year === year);
  let official = 0;
  let combined = 0;
  return MONTHS.map((_, index) => {
    const month = index + 1;
    const rows = selected.filter((record) => record.month === month);
    official += rows.filter((record) => record.record_status === "official").length;
    combined += rows.length;
    return { month, official, combined };
  });
}

export function countModes(records: FatalityRecord[]): Record<string, number> {
  const counts = Object.fromEntries(MODE_ORDER.map((mode) => [mode, 0]));
  records.forEach((record) => {
    const mode = MODE_ORDER.includes(record.normalized_mode as (typeof MODE_ORDER)[number])
      ? record.normalized_mode
      : "Other / Unresolved";
    counts[mode] += 1;
  });
  return counts;
}

function countSameDate(records: FatalityRecord[], year: number, end: Date): number {
  const month = end.getUTCMonth() + 1;
  const day = end.getUTCDate();
  return records.filter((record) => {
    const collision = dateOnly(record.collision_date);
    return (
      record.year === year &&
      (collision.getUTCMonth() + 1 < month ||
        (collision.getUTCMonth() + 1 === month && collision.getUTCDate() <= day))
    );
  }).length;
}

export interface SummaryMetrics {
  official: number;
  provisional: number;
  combined: number;
  comparison: number;
  change: number;
  daysSince: number | null;
  rolling12: number;
  walkingShare: number;
  activeShare: number;
  occupantShare: number;
}

export function summaryMetrics(
  records: FatalityRecord[],
  focusYear: number,
  comparisonYear: number,
  asOf: Date,
): SummaryMetrics {
  const focus = filterThrough(
    records.filter((record) => record.year === focusYear),
    asOf,
  );
  const official = focus.filter((record) => record.record_status === "official").length;
  const provisional = focus.length - official;
  const comparison = countSameDate(
    records.filter((record) => record.record_status === "official"),
    comparisonYear,
    asOf,
  );
  const last = focus
    .map((record) => dateOnly(record.collision_date).getTime())
    .sort((a, b) => b - a)[0];
  const twelveMonthsAgo = new Date(asOf);
  twelveMonthsAgo.setUTCFullYear(asOf.getUTCFullYear() - 1);
  const rolling12 = records.filter((record) => {
    const date = dateOnly(record.collision_date);
    return date > twelveMonthsAgo && date <= asOf;
  }).length;
  const share = (modes: string[]) =>
    focus.length ? focus.filter((record) => modes.includes(record.normalized_mode)).length / focus.length : 0;
  return {
    official,
    provisional,
    combined: focus.length,
    comparison,
    change: focus.length - comparison,
    daysSince: last === undefined ? null : Math.floor((asOf.getTime() - last) / 86_400_000),
    rolling12,
    walkingShare: share(["While Walking"]),
    activeShare: share(["While Cycling", "Micromobility"]),
    occupantShare: share(["While Driving / Riding", "While Riding a Motorcycle"]),
  };
}

export function toCsv(rows: Record<string, unknown>[]): string {
  if (!rows.length) return "";
  const headers = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  const quote = (value: unknown) => {
    if (value === null || value === undefined) return "";
    const text = String(value);
    return /[\n,\"]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  };
  return [headers.join(","), ...rows.map((row) => headers.map((key) => quote(row[key])).join(","))].join("\n");
}

export function downloadText(filename: string, body: string, mime = "text/csv"): void {
  const blob = new Blob([body], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

const TRACKED_FIELDS: (keyof SnapshotRecord)[] = [
  "collision_date",
  "death_date",
  "normalized_mode",
  "native_party_type",
  "native_victim_role",
  "native_vehicle_type",
  "latitude",
  "longitude",
  "location",
  "neighborhood",
  "supervisor_district",
  "classification_status",
];

const COORDINATE_TOLERANCE = 1e-6;

function snapshotValuesEqual(field: keyof SnapshotRecord, before: unknown, after: unknown): boolean {
  if ((before === null || before === undefined) && (after === null || after === undefined)) return true;
  if (before === null || before === undefined || after === null || after === undefined) return false;
  if (field === "latitude" || field === "longitude") {
    const beforeNumber = Number(before);
    const afterNumber = Number(after);
    if (Number.isFinite(beforeNumber) && Number.isFinite(afterNumber)) {
      return Math.abs(beforeNumber - afterNumber) <= COORDINATE_TOLERANCE;
    }
  }
  return String(before ?? "") === String(after ?? "");
}

export function compareSnapshots(previous: SnapshotRecord[], current: SnapshotRecord[]): SnapshotChange[] {
  const before = new Map(previous.map((record) => [record.record_id, record]));
  const after = new Map(current.map((record) => [record.record_id, record]));
  const changes: SnapshotChange[] = [];
  for (const [id] of after) {
    if (!before.has(id)) {
      changes.push({ record_id: id, change_type: "addition", field: "", old_value: "", new_value: "record added" });
    }
  }
  for (const [id] of before) {
    if (!after.has(id)) {
      changes.push({ record_id: id, change_type: "removal", field: "", old_value: "record removed", new_value: "" });
    }
  }
  for (const [id, oldRecord] of before) {
    const newRecord = after.get(id);
    if (!newRecord) continue;
    for (const field of TRACKED_FIELDS) {
      const oldValue = oldRecord[field];
      const newValue = newRecord[field];
      if (snapshotValuesEqual(field, oldValue, newValue)) continue;
      const changeType =
        field.includes("mode") || field.includes("victim") || field.includes("vehicle") || field === "native_party_type"
          ? "mode_reclassification"
          : field.includes("date")
            ? "date_correction"
            : ["latitude", "longitude", "location", "neighborhood", "supervisor_district"].includes(field)
              ? "location_correction"
              : "field_update";
      changes.push({
        record_id: id,
        change_type: changeType,
        field,
        old_value: String(oldValue ?? ""),
        new_value: String(newValue ?? ""),
      });
    }
  }
  return changes;
}
