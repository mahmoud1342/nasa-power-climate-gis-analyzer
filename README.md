# NASA POWER Climate & GIS Analyzer (NPCGA)

**Open-source tool to read, check and analyse NASA POWER climate data (rainfall focus) and to
prepare labelled point tables for ArcGIS Pro. Includes a one-page web interface with Arabic
tables.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](#requirements)

> **Status: v0.1.0 (beta).** Tested by the author on Windows with Python 3.12 (ArcGIS Pro was used
> to check the point files and the ArcPy script). The GitHub Actions workflow is defined but not
> confirmed yet, so Python 3.11 and Ubuntu are **not verified**. See [Known limitations](#known-limitations).

Developed by **Mahmoud Mohamed Atia** (محمود محمد عطية) -
[LinkedIn](https://www.linkedin.com/in/𝐌𝐚𝐡𝐦𝐨𝐮𝐝-𝐌𝐨𝐡𝐚𝐦𝐞𝐝-𝐀𝐭𝐢𝐚-57a9ba235)

## Quick start (Windows, no programming needed)

1. Install **Python 3.12** from python.org (tick "Add python.exe to PATH").
2. Download this repository (green **Code** button -> **Download ZIP**) and unzip it.
3. Double-click **`Start_NPCGA.bat`**. The first launch installs the packages and opens
   `http://localhost:8501`. Keep the black window open while you work.
4. Upload your NASA POWER daily CSV files (a folder, a ZIP, or several files), press **Analyse**,
   then use the **Downloads** tab.

Arabic user guide: [`دليل_الاستخدام_بالعربي.md`](دليل_الاستخدام_بالعربي.md). More: [`docs/WINDOWS.md`](docs/WINDOWS.md).

## What it does

- **Reads** daily NASA POWER CSV files (single file or a folder of one-file-per-location) and
  generic CSV time series; downloads a point directly from the NASA POWER API with a local cache.
- **Checks quality** without silently changing data: duplicates, gaps, `-999` NoData (converted to
  NaN and counted), out-of-range and infinite values, bad coordinates. Files that cannot be read are
  listed with the reason, never skipped silently.
- **Analyses rainfall and climate**: daily / monthly / annual totals and means, monthly climatology,
  anomalies, extreme days, ETCCDI-style annual indices, Mann-Kendall + Sen's slope trends.
- **Compares locations** with each other: overlaid yearly and monthly curves, ranking table,
  correlation matrix of monthly anomalies.
- **Prepares GIS point tables** (one row per location) with a stable ID, QC summary and flags
  (`duplicate_location`, `data_status`, `idw_valid`): Shapefile, GeoPackage, GeoJSON, CSV, a field
  guide, and a generated ArcPy import script. Nothing is deleted; problems are flagged.
- **Arabic downloads**: Excel workbook and CSV files with Arabic column names, units, and a
  "نوع التحليل" column (daily / monthly / annual).
- **Optional** IDW interpolation to GeoTIFF with leave-one-out cross-validation
  (interpolation is normally done in ArcGIS Pro).

## Feature status

| Area | Status |
|---|---|
| NASA POWER point client + exact-request cache | Implemented |
| Daily POWER CSV reader, generic CSV reader, folder loader | Implemented |
| Quality-control reports | Implemented |
| Rainfall statistics, anomalies, ETCCDI-style indices | Implemented (documented simplifications) |
| Mann-Kendall / Sen's slope | Implemented (no autocorrelation correction) |
| Location comparison | Implemented |
| GIS point tables (SHP / GPKG / GeoJSON / CSV) | Implemented |
| ArcPy import-script generator | Implemented; checked by the author in ArcGIS Pro only |
| Arabic Excel / CSV downloads | Implemented |
| One-page web interface (Streamlit, Arabic) | Implemented |
| IDW + GeoTIFF export | Implemented (optional) |
| Kriging, SPI, PDF reports | Not implemented |
| NetCDF input, monthly POWER CSV input | Not implemented |
| Standalone Windows installer | Not implemented (`Start_NPCGA.bat` is the supported way) |

"Implemented" means code and automated tests exist; it does not mean every input or scientific
use has been validated. See [`docs/METHODS.md`](docs/METHODS.md).

## Requirements

- Python **3.12** (tested). The package declares 3.11+, but 3.11 has not been verified yet.
- Internet access only for live NASA POWER downloads and the page's web font.

## Installation (command line / developers)

```powershell
git clone https://github.com/mahmoud1342/nasa-power-climate-gis-analyzer.git
cd nasa-power-climate-gis-analyzer
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev,gis,web]"
.venv\Scripts\python.exe -m pytest
```

Linux / macOS: `python3.12 -m venv .venv && source .venv/bin/activate && python -m pip install -e ".[dev,gis,web]"`.

Extras: `web` = Streamlit, Plotly, openpyxl (web page + Excel); `gis` = geopandas, pyogrio, pyproj,
rasterio (Shapefile / GeoPackage / GeoTIFF); `dev` = pytest, ruff, pymannkendall.

## Command line

```powershell
# one location downloaded from NASA POWER
python -m npcga.cli --lat 31.20 --lon 29.92 --start 2015-01-01 --end 2024-12-31 --name alexandria

# a folder of NASA POWER CSV files (one per location)
python -m npcga.cli_folder --folder "path\to\csv_folder" --name study_area

# optional IDW on a points table
python -m npcga.cli_interp --points outputs\study_area\points_mean_annual_rainfall.csv --value mean_annual_rain_mm --name idw
```

Results go to `outputs/<name>/`. `cli_folder` writes `locations.csv`, `folder_report.txt`,
`failed_files.csv` (only if needed), a `points/` folder (SHP, GPKG, GeoJSON, CSV, `points_fields.csv`,
`points_fields_ar.csv`, `points_issues.csv`, `arcpy_import_points.py`) and an `arabic/` folder
(Excel + CSV). All point files use WGS 84 (EPSG:4326).

## Data integrity and scientific notes

- NASA POWER is a **gridded satellite / reanalysis product**, not rain-gauge data. Compare with
  local observations before drawing local conclusions.
- `-999` becomes NaN and is counted; nothing is filled or interpolated by the readers.
- A month or year gets a value only if at least 90 % of its days are valid (`n_valid` and
  `n_expected` are kept).
- Percentile indices (R95p, R99p) use a simplified percentile without the ETCCDI bootstrap.
- CDD / CWD may cross year boundaries (climdex default; not yet cross-checked numerically against
  R). Mann-Kendall p-values are approximate, especially with fewer than 10 years.
- This is an analytical aid, not a certified climate product. Validate results for your study.

## Known limitations

No NetCDF or monthly-CSV input, no Kriging, no installer; ArcPy script verified only by the
author; Python 3.11 and Linux not verified by automated CI yet (GitHub Actions is currently
disabled for the maintainer's account); the web page was designed without being checked on
screens other than the author's browser.

## Project layout

```text
app.py                  # Streamlit page
Start_NPCGA.bat         # Windows launcher
src/npcga/
  analysis/             # statistics, ETCCDI indices, trends, comparison
  io/                   # POWER CSV, generic CSV, dates, folders, safe uploads
  power/                # NASA POWER client, cache
  qc/                   # quality-control reports
  export/               # GIS point tables, Arabic tables, Excel, ArcPy script
  interp/               # optional IDW + GeoTIFF
docs/  tests/  examples/
```

## Tests and code quality

```bash
python -m pytest          # offline tests (101)
ruff check src tests app.py
python -m pytest -m network   # optional live NASA POWER test
```

## Configuration

Cache folder: `~/.npcga/cache`, or set `NPCGA_CACHE_DIR`.

## Data source and attribution

Data: **NASA Langley Research Center (LaRC) POWER Project**, https://power.larc.nasa.gov/ .
Please keep the attribution when you share outputs and read the POWER documentation for use
conditions.

## Contributing

Bug reports with a reproducible example, scientific-method feedback and focused pull requests are
welcome. See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License and citation

[MIT License](LICENSE). To cite, see [`CITATION.cff`](CITATION.cff).
Docs: [`docs/METHODS.md`](docs/METHODS.md), [`docs/GITHUB_PUBLISHING.md`](docs/GITHUB_PUBLISHING.md),
[`examples/README.md`](examples/README.md), [`CHANGELOG.md`](CHANGELOG.md).
