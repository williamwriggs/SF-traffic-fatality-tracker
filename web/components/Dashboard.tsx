"use client";

import { useEffect, useMemo, useState } from "react";
import { AnnualModeChart, HeroChart, MapChart, ModeChart, SeasonalityChart } from "./charts";
import type {
  SnapshotChange,
  SnapshotRecord,
  TrackerData,
} from "@/lib/types";
import {
  MODE_ORDER,
  availableYears,
  compareSnapshots,
  coverageDate,
  downloadText,
  isCompleteYear,
  longDate,
  shortDate,
  summaryMetrics,
  toCsv,
} from "@/lib/tracker";

const REPOSITORY = "https://github.com/williamwriggs/SF-traffic-fatality-tracker";
const DATASF = "https://data.sfgov.org/Public-Safety/Traffic-Crashes-Resulting-in-Fatality/dau3-4s8f";
const LIVE_DATA = "https://raw.githubusercontent.com/williamwriggs/SF-traffic-fatality-tracker/main/web/public/data";

type Tab = "overview" | "explore" | "revisions" | "methodology";

function ChartCard({
  title,
  subtitle,
  children,
  action,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="chart-card">
      <header className="chart-heading">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
}) {
  return (
    <label className="toggle-row">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span className="toggle" aria-hidden="true"><span /></span>
      <span>{label}</span>
    </label>
  );
}

function Metric({ label, value, detail }: { label: string; value: string | number; detail?: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </div>
  );
}

function formatTableValue(key: string, value: unknown): string {
  const text = String(value);
  if (!/(date|observed_at|last_checked)/.test(key) || !/^\d{4}-\d{2}-\d{2}T/.test(text)) return text;
  if (text.slice(11, 19) === "00:00:00") return text.slice(0, 10);
  return `${text.slice(0, 10)} ${text.slice(11, 16)} UTC`;
}

function DataTable({
  rows,
  columns,
  limit = 100,
}: {
  rows: Record<string, unknown>[];
  columns: { key: string; label: string; link?: boolean }[];
  limit?: number;
}) {
  return (
    <div className="table-shell">
      <table>
        <thead>
          <tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.slice(0, limit).map((row, index) => (
            <tr key={String(row.record_id ?? row.revision_id ?? row.provisional_id ?? index)}>
              {columns.map((column) => {
                const value = row[column.key];
                return (
                  <td key={column.key}>
                    {column.link && value ? (
                      <a href={String(value)} target="_blank" rel="noreferrer">Source ↗</a>
                    ) : value === null || value === undefined || value === "" ? (
                      <span className="empty">—</span>
                    ) : (
                      formatTableValue(column.key, value)
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > limit && <p className="table-note">Showing {limit.toLocaleString()} of {rows.length.toLocaleString()} rows. Download includes all rows.</p>}
      {!rows.length && <p className="empty-state">No matching records.</p>}
    </div>
  );
}

function snapshotLabel(name: string): string {
  const match = name.match(/fatalities_(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z/);
  if (!match) return name;
  return `${match[1]}-${match[2]}-${match[3]} ${match[4]}:${match[5]} UTC`;
}

export default function Dashboard({ initialData }: { initialData: TrackerData }) {
  const [trackerData, setTrackerData] = useState(initialData);
  const years = useMemo(() => availableYears(trackerData.records), [trackerData.records]);
  const latestYear = years[0];
  const [view, setView] = useState<"detail" | "multi">("detail");
  const [focusYear, setFocusYear] = useState(latestYear);
  const [comparisonYear, setComparisonYear] = useState(years.includes(2017) ? 2017 : years[1]);
  const [multiYears, setMultiYears] = useState<number[]>(
    [latestYear, latestYear - 1, 2017].filter((year, index, values) => years.includes(year) && values.indexOf(year) === index),
  );
  const [includeProvisional, setIncludeProvisional] = useState(true);
  const [normalized, setNormalized] = useState(false);
  const [tab, setTab] = useState<Tab>("overview");
  const [exploreYears, setExploreYears] = useState<number[]>([latestYear]);
  const [exploreModes, setExploreModes] = useState<string[]>([...MODE_ORDER]);
  const [query, setQuery] = useState("");
  const [snapshotFrom, setSnapshotFrom] = useState(Math.max(0, initialData.snapshots.length - 2));
  const [snapshotTo, setSnapshotTo] = useState(Math.max(0, initialData.snapshots.length - 1));
  const [snapshotChanges, setSnapshotChanges] = useState<SnapshotChange[] | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetch(`${LIVE_DATA}/tracker.json`, { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`Latest tracker data returned ${response.status}`);
        return response.json() as Promise<TrackerData>;
      })
      .then((latest) => {
        if (!active) return;
        setTrackerData(latest);
        setSnapshotFrom(Math.max(0, latest.snapshots.length - 2));
        setSnapshotTo(Math.max(0, latest.snapshots.length - 1));
      })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);

  const records = useMemo(
    () => includeProvisional
      ? trackerData.records
      : trackerData.records.filter((record) => record.record_status === "official"),
    [includeProvisional, trackerData.records],
  );
  const asOf = coverageDate(records, trackerData.status, focusYear, includeProvisional);
  const complete = isCompleteYear(records, focusYear);
  const summary = summaryMetrics(records, focusYear, comparisonYear, asOf);
  const currentRows = records.filter((record) => record.year === focusYear && new Date(record.collision_date) <= asOf);
  const latestOfficial = trackerData.records
    .filter((record) => record.record_status === "official" && record.year === latestYear)
    .map((record) => record.collision_date)
    .sort()
    .at(-1);
  const openProvisional = trackerData.records.filter((record) => record.record_status === "provisional").length;
  const chartYears = view === "detail" ? [comparisonYear, focusYear] : multiYears;
  const chartRows = records.filter((record) => chartYears.includes(record.year));

  const filteredRows = records.filter((record) => {
    const haystack = `${record.location ?? ""} ${record.neighborhood ?? ""} ${record.record_id}`.toLowerCase();
    return exploreYears.includes(record.year) && exploreModes.includes(record.normalized_mode) && haystack.includes(query.toLowerCase());
  });

  const toggleMultiYear = (year: number) => {
    if (year === focusYear) return;
    setMultiYears((selected) =>
      selected.includes(year)
        ? selected.filter((value) => value !== year)
        : selected.length < 6
          ? [...selected, year].sort()
          : selected,
    );
  };

  const selectFocusYear = (year: number) => {
    setFocusYear(year);
    setMultiYears((selected) => [...new Set([year, ...selected])].slice(0, 6).sort());
    setExploreYears([year]);
    if (comparisonYear === year) setComparisonYear(years.find((candidate) => candidate !== year) ?? year);
  };

  const loadSnapshotComparison = async () => {
    setSnapshotLoading(true);
    setSnapshotError(null);
    try {
      const fetchSnapshot = async (index: number) => {
        const snapshot = trackerData.snapshots[index];
        const remoteFile = snapshot.file.replace(/^\/data\//, "");
        const remote = await fetch(`${LIVE_DATA}/${remoteFile}`, { cache: "no-store" });
        if (remote.ok) return remote;
        const local = await fetch(snapshot.file);
        if (!local.ok) throw new Error("Snapshot data could not be loaded");
        return local;
      };
      const [beforeResponse, afterResponse] = await Promise.all([fetchSnapshot(snapshotFrom), fetchSnapshot(snapshotTo)]);
      const [before, after] = await Promise.all([
        beforeResponse.json() as Promise<SnapshotRecord[]>,
        afterResponse.json() as Promise<SnapshotRecord[]>,
      ]);
      setSnapshotChanges(compareSnapshots(before, after));
    } catch {
      setSnapshotChanges(null);
      setSnapshotError("Those snapshots could not be loaded. Try again in a moment.");
    } finally {
      setSnapshotLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#top" aria-label="SF Traffic Fatality Tracker home">
          <span className="brand-mark" />
          <span>SF fatality<br />tracker</span>
        </a>
        <div className="sidebar-section">
          <p className="control-label">Visualization</p>
          <div className="segmented">
            <button className={view === "detail" ? "active" : ""} onClick={() => setView("detail")}>Two-year</button>
            <button className={view === "multi" ? "active" : ""} onClick={() => setView("multi")}>Multi-year</button>
          </div>
          <label>
            <span className="control-label">Focus year</span>
            <select value={focusYear} onChange={(event) => selectFocusYear(Number(event.target.value))}>
              {years.map((year) => <option key={year}>{year}</option>)}
            </select>
          </label>
          {view === "detail" ? (
            <label>
              <span className="control-label">Comparison year</span>
              <select value={comparisonYear} onChange={(event) => setComparisonYear(Number(event.target.value))}>
                {years.filter((year) => year !== focusYear).map((year) => <option key={year}>{year}</option>)}
              </select>
            </label>
          ) : (
            <fieldset className="year-picker">
              <legend>Additional years <small>{multiYears.length}/6</small></legend>
              <div>
                {years.map((year) => (
                  <label key={year} className={year === focusYear ? "focus" : ""}>
                    <input
                      type="checkbox"
                      checked={multiYears.includes(year)}
                      disabled={year === focusYear || (!multiYears.includes(year) && multiYears.length >= 6)}
                      onChange={() => toggleMultiYear(year)}
                    />
                    {year}
                  </label>
                ))}
              </div>
            </fieldset>
          )}
        </div>
        <div className="sidebar-section">
          <p className="control-label">Definitions</p>
          <Toggle checked={includeProvisional} onChange={setIncludeProvisional} label="Include unreconciled reports" />
          <p className="sidebar-copy">Official records are published by DataSF. Provisional reports remain separate until matched.</p>
        </div>
        <a className="button secondary sidebar-link" href={DATASF} target="_blank" rel="noreferrer">Open official DataSF ↗</a>
        <a className="repo-link" href={REPOSITORY} target="_blank" rel="noreferrer">GitHub repository ↗</a>
      </aside>

      <main id="top">
        <header className="hero-copy">
          <p className="eyebrow">Public data · revision aware · open source</p>
          <h1>SF Traffic Fatality Tracker</h1>
          <p className="lede">Compare years, inspect mode and location, and download exactly what changed between DataSF snapshots. Unreconciled recent deaths stay visible without being silently counted as official.</p>
          <p className="credit">Research by <strong>William W. Riggs</strong> · <a href={REPOSITORY} target="_blank" rel="noreferrer">Source and methodology on GitHub ↗</a></p>
        </header>

        <div className={`status-strip ${openProvisional ? "warning" : ""}`}>
          <span>Official records currently include collisions through <strong>{longDate(latestOfficial)}</strong> and were loaded to DataSF <strong>{shortDate(trackerData.status.source_loaded_at)}</strong>.</span>
          <span className="status-pill">{openProvisional} unreconciled public reports</span>
          <span>checked through {longDate(trackerData.status.provisional_checked_through)}.</span>
        </div>

        <section className="metrics-grid" aria-label="Summary metrics">
          <Metric label={`${focusYear} ${complete ? "full year" : "tracked YTD"}`} value={summary.combined} />
          <Metric label="Official" value={summary.official} />
          <Metric label="Unreconciled" value={summary.provisional} />
          <Metric
            label={`vs. ${comparisonYear} ${complete ? "full year" : "same date"}`}
            value={`${summary.change >= 0 ? "+" : ""}${summary.change}`}
            detail={`${summary.comparison} in ${comparisonYear}`}
          />
          <Metric label={complete ? "Days from last death to year-end" : "Days since last tracked death"} value={summary.daysSince ?? "—"} />
        </section>

        <nav className="tabs" role="tablist" aria-label="Dashboard sections">
          {([
            ["overview", "Overview"],
            ["explore", "Explore records"],
            ["revisions", "Snapshots & revisions"],
            ["methodology", "Methodology"],
          ] as [Tab, string][]).map(([value, label]) => (
            <button key={value} role="tab" aria-selected={tab === value} className={tab === value ? "active" : ""} onClick={() => setTab(value)}>{label}</button>
          ))}
        </nav>

        {tab === "overview" && (
          <div className="section-stack">
            <ChartCard
              title={view === "detail" ? `Traffic fatalities: ${comparisonYear} vs. ${focusYear}` : "Traffic fatalities: multi-year comparison"}
              subtitle={view === "detail" ? "Cumulative fatalities by collision month; dashed segments are unreconciled" : `${multiYears.join(", ")} · focus year is emphasized · dashed segments are unreconciled`}
              action={<button className="button secondary compact" onClick={() => downloadText(`sf-traffic-fatalities-${chartYears.join("-")}.csv`, toCsv(chartRows as unknown as Record<string, unknown>[]))}>Download CSV</button>}
            >
              <HeroChart records={records} focusYear={focusYear} comparisonYear={comparisonYear} multiYears={multiYears} view={view} />
              <p className="source-note">Source: SFDPH/SFPD/SFMTA via DataSF. Solid lines are official; dashed segments are unreconciled.</p>
            </ChartCard>

            <div className="two-column">
              <ChartCard title={`${focusYear} fatalities by mode`} subtitle="Official and open provisional records">
                <ModeChart records={currentRows} year={focusYear} />
              </ChartCard>
              <section className="mix-card">
                <p className="eyebrow">Read the current mix</p>
                <Metric label="Walking share" value={`${Math.round(summary.walkingShare * 100)}%`} />
                <Metric label="Cycling + micromobility share" value={`${Math.round(summary.activeShare * 100)}%`} />
                <Metric label="Vehicle occupant share" value={`${Math.round(summary.occupantShare * 100)}%`} />
                <Metric label="Rolling 12 months" value={summary.rolling12} />
                <p className="goal-gap">Vision Zero target gap: {summary.combined} fatalities above the zero-death goal in {focusYear} {complete ? "for the full year" : "to date"}.</p>
              </section>
            </div>

            <ChartCard
              title="Annual traffic fatalities by mode"
              subtitle={normalized ? "Mode share within each year · each bar = 100% · latest year may be partial" : "Official victim-level DataSF records · latest year may be partial"}
              action={<Toggle checked={normalized} onChange={setNormalized} label="Normalize to 100%" />}
            >
              <AnnualModeChart records={trackerData.records} normalized={normalized} />
            </ChartCard>

            <ChartCard title="Monthly seasonality" subtitle="Official fatalities by collision month">
              <SeasonalityChart records={trackerData.records} />
            </ChartCard>
          </div>
        )}

        {tab === "explore" && (
          <div className="section-stack">
            <section className="filter-card">
              <div>
                <span className="control-label">Years</span>
                <div className="chip-row">{years.map((year) => <button key={year} className={exploreYears.includes(year) ? "chip active" : "chip"} onClick={() => setExploreYears((selected) => selected.includes(year) ? selected.filter((value) => value !== year) : [...selected, year])}>{year}</button>)}</div>
              </div>
              <div>
                <span className="control-label">Modes</span>
                <div className="chip-row">{MODE_ORDER.map((mode) => <button key={mode} className={exploreModes.includes(mode) ? "chip active" : "chip"} onClick={() => setExploreModes((selected) => selected.includes(mode) ? selected.filter((value) => value !== mode) : [...selected, mode])}>{mode.replace("While ", "")}</button>)}</div>
              </div>
              <label>
                <span className="control-label">Search location or record ID</span>
                <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Market St, SoMa, record 18…" />
              </label>
            </section>
            <ChartCard title="Fatal crash locations" subtitle={`${filteredRows.length} records · points reflect collision locations`}>
              <MapChart records={filteredRows} />
            </ChartCard>
            <section className="content-card">
              <div className="section-heading">
                <div><h2>Records</h2><p>{filteredRows.length} matching victim-level records</p></div>
                <button className="button secondary compact" onClick={() => downloadText("sf-traffic-fatalities-filtered.csv", toCsv(filteredRows as unknown as Record<string, unknown>[]))}>Download filtered CSV</button>
              </div>
              <DataTable rows={filteredRows as unknown as Record<string, unknown>[]} columns={[
                { key: "collision_date", label: "Collision date" },
                { key: "normalized_mode", label: "Mode" },
                { key: "record_status", label: "Status" },
                { key: "location", label: "Location" },
                { key: "neighborhood", label: "Neighborhood" },
                { key: "supervisor_district", label: "District" },
                { key: "record_id", label: "Record ID" },
              ]} />
            </section>
          </div>
        )}

        {tab === "revisions" && (
          <div className="section-stack">
            <section className="content-card">
              <div className="section-heading"><div><h2>Snapshot comparison</h2><p>Compare any two immutable official snapshots.</p></div></div>
              <div className="comparison-controls">
                <label><span>Earlier snapshot</span><select value={snapshotFrom} onChange={(event) => setSnapshotFrom(Number(event.target.value))}>{trackerData.snapshots.map((snapshot, index) => <option key={snapshot.name} value={index}>{snapshotLabel(snapshot.name)}</option>)}</select></label>
                <label><span>Later snapshot</span><select value={snapshotTo} onChange={(event) => setSnapshotTo(Number(event.target.value))}>{trackerData.snapshots.map((snapshot, index) => <option key={snapshot.name} value={index}>{snapshotLabel(snapshot.name)}</option>)}</select></label>
                <button className="button primary" disabled={snapshotLoading} onClick={loadSnapshotComparison}>{snapshotLoading ? "Comparing…" : "Compare snapshots"}</button>
              </div>
              {snapshotError && <p className="warning-box" role="alert">{snapshotError}</p>}
              {snapshotChanges !== null && (
                <>
                  <div className="comparison-result"><strong>{snapshotChanges.length}</strong><span>detected changes</span><button className="button secondary compact" onClick={() => downloadText("snapshot-comparison.csv", toCsv(snapshotChanges as unknown as Record<string, unknown>[]))}>Download comparison</button></div>
                  <DataTable rows={snapshotChanges as unknown as Record<string, unknown>[]} columns={[
                    { key: "record_id", label: "Record ID" },
                    { key: "change_type", label: "Change type" },
                    { key: "field", label: "Field" },
                    { key: "old_value", label: "Old value" },
                    { key: "new_value", label: "New value" },
                  ]} />
                </>
              )}
            </section>

            <section className="content-card">
              <div className="section-heading"><div><h2>Persistent revision log</h2><p>{trackerData.revisions.length} observed changes since the baseline snapshot</p></div><button className="button secondary compact" onClick={() => downloadText("sf-fatality-revisions.csv", toCsv(trackerData.revisions as unknown as Record<string, unknown>[]))}>Download log</button></div>
              <DataTable rows={[...trackerData.revisions].reverse() as unknown as Record<string, unknown>[]} columns={[
                { key: "observed_at", label: "Observed" },
                { key: "record_id", label: "Record ID" },
                { key: "change_type", label: "Change type" },
                { key: "field", label: "Field" },
                { key: "old_value", label: "Old value" },
                { key: "new_value", label: "New value" },
              ]} />
            </section>

            <section className="content-card">
              <div className="section-heading"><div><h2>Provisional reconciliation queue</h2><p>Credible public reports not yet matched to DataSF</p></div></div>
              <DataTable rows={trackerData.provisionalAudit as unknown as Record<string, unknown>[]} columns={[
                { key: "incident_date", label: "Incident date" },
                { key: "normalized_mode", label: "Mode" },
                { key: "location", label: "Location" },
                { key: "status", label: "Status" },
                { key: "last_checked", label: "Last checked" },
                { key: "source_url", label: "Source", link: true },
                { key: "notes", label: "Notes" },
              ]} />
            </section>
          </div>
        )}

        {tab === "methodology" && (
          <article className="methodology content-card">
            <p className="eyebrow">Methods and definitions</p>
            <h2>How the tracker works</h2>
            <section><h3>What counts as official</h3><p>The canonical source is DataSF’s <a href={DATASF} target="_blank" rel="noreferrer">Traffic Crashes Resulting in Fatality dataset</a> (<code>dau3-4s8f</code>). Year-to-date records originate with the Office of the Chief Medical Examiner and include cases City agencies determine meet the San Francisco Vision Zero Fatality Protocol.</p></section>
            <section><h3>Collision date versus death date</h3><p>Charts group deaths by collision date for year-to-year comparability. Death date remains in every record and download. A person may die days after a collision; that is not treated as a date correction.</p></section>
            <section><h3>Official versus provisional</h3><p>A provisional record is a credible public report that has not yet been matched to an official DataSF row. It is drawn with a dashed line and excluded from the official KPI. Candidate matches are flagged for review but never auto-reconciled.</p></section>
            <section><h3>Modes and revisions</h3><p>The tracker preserves DataSF’s native role and vehicle values and adds a transparent display taxonomy. Every refresh stores timestamped raw data and a normalized Parquet snapshot. Additions, removals, date changes, location changes, and mode reclassifications are retained in the revision log.</p></section>
            <div className="warning-box">Provisional public reports may later be excluded under the City protocol or reclassified. This is an independent research and transparency tool, not an official City publication.</div>
            <p>Additional sources: <a href="https://www.sf.gov/data--traffic-fatalities" target="_blank" rel="noreferrer">SF.gov traffic fatalities</a> and the <a href="https://data.sfgov.org/d/nwes-mmgh" target="_blank" rel="noreferrer">DataSF victim-level cross-check</a>.</p>
          </article>
        )}

        <footer>
          <p>Snapshot fetched {longDate(trackerData.status.fetched_at)}. Research by William W. Riggs. <a href={REPOSITORY} target="_blank" rel="noreferrer">Source code and methodology</a> are released under the MIT License.</p>
          <p>Values can change when City agencies reconcile records.</p>
        </footer>
      </main>
    </div>
  );
}
