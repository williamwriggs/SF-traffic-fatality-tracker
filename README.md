# SF Traffic Fatality Tracker

An open-source, revision-aware tracker for traffic fatalities in San Francisco. It fetches the City’s official Vision Zero fatality records from DataSF, preserves every source snapshot, keeps recent public reports separate until reconciliation, and serves a Streamlit dashboard for year-to-year comparison and downloads.

Research by **William W. Riggs**. Source code, methodology, and revision history are maintained in this repository.

The tracker is designed for journalists, researchers, students, and residents who need to answer not only “what is the current count?” but also “what did the City publish last time, and what changed?”

![Generated publication chart](assets/generated_2017_vs_2026.png)

The supplied visual is retained as `assets/reference_chart.png`; the image above is regenerated from the stored official and provisional records.

## What it does

- Queries DataSF’s dedicated **Traffic Crashes Resulting in Fatality** API view (`dau3-4s8f`).
- Writes timestamped raw JSON plus a source manifest under `data/raw/YYYY-MM-DD/`.
- Normalizes official records to Parquet without discarding the City’s native mode.
- Compares each official snapshot with the prior snapshot.
- Logs additions, removals, mode reclassifications, date corrections, and location corrections.
- Keeps manually auditable recent reports in `data/provisional/incidents.csv`.
- Requires an explicit official record ID before a provisional incident is reconciled and removed from the combined count.
- Calculates monthly, cumulative, YTD, same-date comparison, mode shares, rolling 12-month, seasonality, and days-since-last-event metrics.
- Provides interactive charts, a map, exact record downloads, and downloadable snapshot comparisons.
- Supports a two-year detail view with modal endpoint stacks and a multi-year trend view with up to six selected years.
- Switches the annual mode chart between fatality totals and a 100%-normalized proportional breakdown.

## Why the official source changed from the original handoff

The initial brief named the victim-level injury table (`nwes-mmgh`). During implementation, DataSF’s live catalog exposed a more authoritative dedicated view: `dau3-4s8f`. Its metadata explicitly states that year-to-date records originate with Office of the Chief Medical Examiner death records and include cases that meet the multi-agency **San Francisco Vision Zero Fatality Protocol**.

That dedicated view is now canonical. The victim-level table remains a useful cross-check but does not define the official KPI. This distinction already matters: the latest dedicated snapshot contains a May 2026 bicyclist fatality that was absent from the broader victim-table query used in the supplied chart. The tracker records future differences instead of silently overwriting them.

## Run locally

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m src.refresh
streamlit run app.py
```

Then open the local URL printed by Streamlit, normally `http://localhost:8501`.

A Socrata token is optional for low-volume use. For more generous API limits:

```bash
export SOCRATA_APP_TOKEN="your-token"
python -m src.refresh
```

Useful shortcuts:

```bash
make test
make refresh
make app
```

Regenerate the publication PNG without opening Streamlit:

```bash
python -m src.export --comparison-year 2017 --current-year 2026 \
  --as-of 2026-08-12 --output assets/generated_2017_vs_2026.png
```

## Data model and provenance

### Official records

Canonical dataset: [DataSF Traffic Crashes Resulting in Fatality](https://data.sfgov.org/d/dau3-4s8f)

The processed file keeps:

- tracker record ID, crash ID, and person ID;
- collision date/time and death date;
- collision year and month;
- City-native deceased mode and collision type;
- normalized display mode;
- severity/protocol status;
- latitude, longitude, location, neighborhood, police district, and supervisor district;
- DataSF dataset ID, row `data_as_of`, portal load time, and tracker ingest time;
- official/provisional and classification status fields.

Charts group fatalities by **collision date**. Death date remains in every record and download because a death can occur after the collision.

### Provisional records

`data/provisional/incidents.csv` is deliberately small and reviewable. Each row needs a stable provisional ID, incident and death dates when known, source-native and normalized mode, location, source link, status, last-checked date, and notes.

Open provisional statuses are `unreconciled`, `provisional`, and `under-review`. A row stops contributing to the combined total only when `matched_official_record_id` is filled and its status is changed to `reconciled`. The fuzzy matcher can flag a candidate within 14 days and the same normalized mode, but it never auto-reconciles.

Public reporting can describe a death that City agencies later exclude under the Vision Zero Fatality Protocol. That is why the dashboard draws provisional values with a dashed line, labels the official count separately, and avoids calling the combined count “official.”

### Mode normalization

The City-native `deceased` value is preserved. The display taxonomy is:

| Native examples | Display mode |
|---|---|
| Pedestrian | While Walking |
| Bicyclist | While Cycling |
| Standup Powered Device Rider, scooter | Micromobility |
| Motorcyclist | While Riding a Motorcycle |
| Driver, Passenger | While Driving / Riding |
| Unrecognized or missing | Other / Unresolved |

A scooter is never silently counted as a bicycle.

## Snapshot and revision behavior

Every successful refresh creates:

```text
data/
├── raw/YYYY-MM-DD/
│   ├── dau3-4s8f_<UTC timestamp>.json
│   └── manifest_<UTC timestamp>.json
├── processed/
│   ├── snapshots/fatalities_<UTC timestamp>.parquet
│   ├── fatalities.parquet
│   ├── combined.parquet
│   ├── provisional_audit.parquet
│   ├── revisions.parquet
│   └── status.json
└── provisional/incidents.csv
```

The first snapshot is a baseline. It does not create hundreds of fake “addition” revisions. Later snapshots are compared by stable official record ID. Revision rows contain the two snapshot names, observation time, record ID, change type, changed field, and old/new value.

If DataSF is unavailable, the refresh command returns a nonzero exit status and writes the error to `status.json`; it does not replace a good processed snapshot. The Streamlit app continues to serve the last successful data and shows its dates.

## Dashboard guide

- **Overview**: scan-first KPIs, a two-year detail or multi-year trend view, mode composition, annual history, and seasonality. Historical selections use full-year/December labels; the latest year uses its actual checked-through date.
- **Explore records**: filter by year, normalized mode, and status; inspect a location map; download exact rows.
- **Snapshots & revisions**: compare any two stored snapshots, download the diff, inspect the persistent revision log, and review provisional matches.
- **Methodology**: definitions, caveats, source links, and the reconciliation policy.

Plotly’s camera control exports any visible chart from the browser. Every chart view can also be downloaded as a self-contained interactive HTML file, and the two-year detail view has a dedicated publication PNG export using a headless-safe Matplotlib renderer. The command-line exporter will use Kaleido when the optional `plotly-png` extra and a working Chrome runtime are available, then fall back to Matplotlib automatically.

## Automated refresh

`.github/workflows/refresh.yml` runs tests, refreshes DataSF daily, and commits changed data. Add a repository secret named `SOCRATA_APP_TOKEN` if desired. GitHub Actions needs `contents: write`, already declared in the workflow.

For Streamlit Community Cloud, deploy `app.py` and keep processed snapshots in the repository. The scheduled GitHub refresh becomes the durable source of updates; Streamlit’s data cache expires every 15 minutes.

## Testing

```bash
python -m pytest -q
```

Tests cover source-mode normalization, official/provisional metric separation, same-date comparison, explicit provisional reconciliation, and the full revision taxonomy.

## Limitations

- Official publication lags collisions and can be revised later.
- The Vision Zero Fatality Protocol can exclude deaths that appear traffic-related in initial reporting.
- Public reports can be incomplete, wrong, duplicated, or later reclassified.
- Coordinates are DataSF’s geocoded collision locations and can be generalized to a street segment or intersection.
- Monthly charts use collision month, not death month.
- The dashboard is an independent analysis and must not be attributed to the City and County of San Francisco.

Review the City dataset metadata before republishing analysis. Acknowledge Vision Zero and TransBASE, include the pull date, and retain the caveats.

## Contributing

Issues and pull requests are welcome. For a provisional incident correction, include a durable source URL, explain the requested status or mode change, and never add personally identifying information unless it is necessary and already clearly public.

## License

Code is MIT licensed. DataSF’s source data is public data; its metadata and use caveats remain applicable. News links are provenance references, not redistributed article content.
