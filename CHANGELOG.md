# Changelog

All notable changes to this project are documented in this file.

The project is currently in early development. Until the first stable release, versioned entries
may be incomplete and interfaces can change.

## [Unreleased]

## [0.1.0] - 2026-11-26
First public version (beta). Highlights: NASA POWER download with cache, daily-CSV folder reader,
quality checks, rainfall/climate analysis (ETCCDI, Mann-Kendall + Sen), location comparison,
labelled point tables for ArcGIS Pro (Shapefile, GeoPackage, GeoJSON, CSV, ArcPy script),
Arabic Excel/CSV downloads, one-page web interface, optional IDW.
Developer credit and LinkedIn link added to the app (About section), Excel and reports.
Known limitations: no NetCDF, no monthly POWER CSV, no Kriging, no standalone installer,
ArcPy script tested only by the author inside ArcGIS Pro.

### Added
- Location comparison in the time-analysis tab: overlaid yearly and monthly curves, ranking table,
  correlation matrix of monthly anomalies, Arabic CSV downloads (`npcga.analysis.compare_locations`).

### Added
- Arabic download tables (Excel workbook + CSV): per-location summary, annual and monthly
  analysis, optional daily data, each stating its time scale and with Arabic headers and units;
  Arabic field guide for the GIS files.
- Redesigned one-page interface: tabs (summary, time analysis, points, downloads), new theme.

### Added
- One-page Streamlit interface (`app.py`, `Start_NPCGA.bat`) and an Arabic user guide
  (first draft by ChatGPT, reviewed and corrected). Streamlit replaced the originally planned
  FastAPI + HTMX stack for this local page.
- `npcga.io.extract_uploads`: safe CSV/ZIP extraction (no path traversal, size limits).
- `npcga.analysis.variable_profile`: yearly series and monthly climatology with the correct
  aggregation (precipitation summed, other variables averaged).

### Fixed
- The first draft of the page summed temperature (and every non-rain variable) as if it were
  rainfall; it now averages them. The page also no longer renames `idw_valid`, so its CSV matches
  the command-line output and the generated ArcPy script.

### Added
- Point-table export for GIS (CSV, GeoJSON, GeoPackage, Shapefile) with stable IDs, QC summary,
  duplicate / validity flags, trend and monthly means per location, field documentation,
  `points_issues.csv` and a generated ArcPy import script (untested outside ArcGIS Pro).

### Changed
- Rx5day windows may cross year boundaries (`altRx5day` keeps the within-year version).
- `failed_files.csv` from an earlier run is removed when the new run has no failures.
- Optional `gis` dependencies reduced to geopandas, pyogrio, pyproj, rasterio (Kriging/scipy dropped).

### Added
- IDW interpolation (`npcga.interp`, `python -m npcga.cli_interp`): UTM projection, convex-hull
  masking, leave-one-out cross-validation (ME, MAE, RMSE, R2) and GeoTIFF export.

### Changed
- **CDD / CWD now follow the climdex default**: spells may cross year boundaries and are credited
  to the year they end in. The previous within-year behaviour is kept as `altCDD` / `altCWD`.
  Results produced with earlier development versions will differ for CDD / CWD.
- NoData detection uses exact equality with `-999` (no tolerance) in readers and QC.

### Fixed
- Monthly request years such as `2020.9`, `0` or negative values are rejected instead of truncated.
- NaN / infinite coordinates, malformed parameter names, invalid `retries` / `timeout` / `backoff`
  are rejected before any request.
- API responses with mismatched date keys or invalid month keys raise a clear error; non-numeric
  values in a response are counted as warnings.
- QC reports infinite values and rejects unsupported `freq` values.
- POWER CSV reader rejects out-of-range coordinates and warns about undecodable characters.
- Mann-Kendall rejects duplicate or non-finite times, infinite values and invalid `alpha`.

### Documentation
- Reworked the README to describe the repository's current capabilities, installation,
  command-line workflows, outputs, data-integrity rules, and known limitations.
- Added contribution guidance covering scientific reproducibility, tests, lazy imports, and
  source-data integrity.
- Added GitHub issue templates for bug reports and feature requests.

## [0.1.0.dev0]

### Added
- NASA POWER point-data client for daily and monthly requests.
- Retry handling for selected transient network and HTTP failures.
- Exact-request local cache backed by Parquet and SQLite.
- Time-series and point-coordinate quality-control reports.
- Daily NASA POWER CSV, generic CSV, and folder readers.
- Rainfall summaries, anomalies, extreme-day summaries, annual ETCCDI-style indices,
  Mann–Kendall trend testing, and Sen's slope.
- Command-line workflows for one point and folders of POWER CSV files.
- Automated tests and GitHub Actions test workflow.

### Notes
- This is a development version, not a stable release.
- Scientific definitions, simplifications, and limitations are described in `docs/METHODS.md`.
- Web interface, NetCDF ingestion, monthly POWER CSV ingestion, SPI, spatial interpolation,
  GeoTIFF / ArcGIS export, and PDF reporting are not implemented in this version.
