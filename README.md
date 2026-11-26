# NASA POWER Climate & GIS Analyzer (NPCGA)

**Open-source Python toolkit for NASA POWER climate data, rainfall analysis, quality
control, and GIS-ready exports.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue.svg)](#requirements)

> **Development status:** early development (`0.1.0.dev0`). The command-line workflows and
> Python modules described below are present in this repository. The web interface, spatial
> interpolation, NetCDF ingestion, SPI, and GIS raster export are not implemented yet.
> Do not interpret the project roadmap as a list of available features.

## What it does

- Downloads daily or monthly point data from the NASA POWER API.
- Retries selected transient HTTP/network failures.
- Caches exact requests locally using Parquet files and a SQLite index.
- Checks time series and point-coordinate data without silently correcting the input.
- Reads daily NASA POWER CSV files and generic date-based CSV time series.
- Reads folders of NASA POWER CSV files and reports files that could not be read.
- Calculates rainfall summaries, anomalies, extreme-day summaries, ETCCDI-style annual
  indices, and Mann–Kendall / Sen trend statistics.
- Exports tabular results as CSV for inspection or use in GIS software such as ArcGIS Pro.

## Current status and scope

| Area | Repository status |
|---|---|
| NASA POWER point client | Implemented |
| Exact-request local cache | Implemented |
| Quality-control reports | Implemented |
| Daily POWER CSV reader | Implemented |
| Generic CSV time-series reader | Implemented |
| Folder ingestion and location summary | Implemented |
| Rainfall statistics and annual indices | Implemented |
| Mann–Kendall and Sen's slope | Implemented |
| CLI workflows | Implemented |
| FastAPI / HTMX web interface | Not implemented |
| NetCDF and monthly POWER CSV ingestion | Not implemented |
| SPI | Not implemented |
| IDW interpolation + GeoTIFF export | Implemented (needs the `gis` extra) |
| Kriging | Not implemented |
| GIS point table (CSV / GeoJSON / GPKG / SHP) | Implemented (shapefile/GPKG need the `gis` extra) |
| ArcPy import-script generator | Implemented, untested outside ArcGIS Pro |
| PDF reports | Not implemented |

“Implemented” means code exists in this repository; it does not imply every possible input,
environment, or scientific use case has been validated. See [Methods and limitations](docs/METHODS.md).

## Requirements

- Python **3.11 or 3.12** according to the current package metadata and CI matrix.
- Internet access for live NASA POWER downloads.
- The core package dependencies are installed by the standard project installation.
- Optional GIS dependencies are separate and are not needed for the current CLI workflows.

Python 3.12 is a suitable development environment. The current CI also tests Python 3.11;
the declared minimum should only be changed when that compatibility is intentionally dropped.

## Installation

### Windows (PowerShell)

```powershell
git clone <repository-url>
cd <repository-directory>

py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

If PowerShell blocks activation, run the environment's Python directly:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest
```

### Linux / macOS

```bash
git clone <repository-url>
cd <repository-directory>

python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Optional dependency groups

```bash
# Web dependencies reserved for the planned web application
python -m pip install -e ".[web]"

# Optional geospatial / spatial-analysis dependencies
python -m pip install -e ".[gis]"
```

Installing an optional group does not mean the corresponding end-user workflow is complete.
The `web` extra currently declares FastAPI and Uvicorn; it does not provide a finished web UI.

## Quick start

### 1. Download and analyse one location

The following example uses the CLI defaults for Alexandria, Egypt:

```bash
python -m npcga.cli \
  --lat 31.20 \
  --lon 29.92 \
  --start 2015-01-01 \
  --end 2024-12-31 \
  --name alexandria
```

On Windows PowerShell, the command can be entered on one line:

```powershell
python -m npcga.cli --lat 31.20 --lon 29.92 --start 2015-01-01 --end 2024-12-31 --name alexandria
```

The workflow requests `PRECTOTCORR` and `T2M`, runs QC and analysis, and writes CSV outputs,
`metadata.txt`, and `qc_report.txt` under:

```text
outputs/alexandria/
```

The first run may need internet access. An identical request can be served from the local cache.

### 2. Analyse a folder of NASA POWER CSV files

Place one daily POWER CSV per location in a folder, then run:

```powershell
python -m npcga.cli_folder --folder "D:\data\nasa_power_csv" --name study_area
```

The output is written under `outputs/study_area/`. It includes location summaries,
mean annual rainfall by location, and `failed_files.csv` when one or more files cannot be read.
Failures are reported rather than silently skipped.

## Output files

The single-location CLI currently writes:

- `daily_data.csv`
- `descriptive_statistics.csv`
- `rain_monthly_totals.csv`
- `rain_annual_totals.csv`
- `rain_monthly_climatology.csv`
- `rain_monthly_anomalies.csv`
- `rain_annual_anomalies.csv`
- `rain_annual_indices_ETCCDI.csv`
- `rain_extreme_days.csv`
- `rain_trends_MannKendall_Sen.csv`
- `climate_monthly_summary.csv`
- `climate_annual_summary.csv`
- `metadata.txt`
- `qc_report.txt`

The folder workflow writes `locations.csv`, `points_mean_annual_rainfall.csv`,
`folder_report.txt`, and (if needed) `failed_files.csv`.

## Data integrity and scientific-use notes

- NASA POWER is a gridded satellite / model-based data product, not a substitute for local
  rain-gauge observations.
- The POWER NoData sentinel `-999` is converted to `NaN` and counted by the relevant readers.
- Missing values are not filled or interpolated by the readers.
- QC reports problems; it is not intended to silently modify or “repair” source data.
- Aggregated monthly and annual rainfall totals use the documented completeness threshold
  (90% by default); counts of valid and expected days are retained.
- The current annual ETCCDI-style implementation has documented simplifications, including
  percentile calculation without the ETCCDI bootstrap. See `docs/METHODS.md` before interpreting
  percentile-based indices or publishing results.
- The current Mann–Kendall implementation uses a two-sided normal approximation with
  tie-corrected variance and does not correct for autocorrelation. See `docs/METHODS.md`.

This software is an analytical aid, not a certified climate-data product. Validate methods,
periods, units, completeness rules, and results for the intended study.

## Project layout

```text
src/npcga/
├── analysis/   # rainfall statistics, ETCCDI-style indices, trend analysis
├── io/         # POWER CSV, generic CSV, date parsing, folder ingestion
├── power/      # NASA POWER client, parameters, cache, service
├── qc/         # quality-control reports
├── cli.py      # single-point workflow
└── cli_folder.py
tests/          # automated tests
docs/           # method definitions and limitations
.github/        # GitHub Actions workflow and issue templates
```

## Tests and code quality

Run the standard offline test suite:

```bash
python -m pytest
```

Run Ruff:

```bash
ruff check src tests
```

The repository's pytest configuration excludes tests marked `network` by default. To explicitly
run the live NASA POWER tests:

```bash
python -m pytest -m network
```

Live tests require network access and depend on the external NASA POWER service. They are not a
replacement for deterministic unit tests.

## Configuration

- Cache location defaults to `~/.npcga/cache`.
- Set `NPCGA_CACHE_DIR` to use a different cache directory.

Example (PowerShell):

```powershell
$env:NPCGA_CACHE_DIR = "D:\npcga-cache"
```

## Data source and attribution

Data are retrieved from the **NASA Langley Research Center (LaRC) POWER Project**:

- https://power.larc.nasa.gov/

Please retain appropriate NASA POWER attribution when redistributing outputs and consult the
NASA POWER documentation for data access, parameter definitions, temporal coverage, and use
conditions.

## Contributing

Bug reports, reproducible examples, scientific-method feedback, and focused pull requests are
welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Use the GitHub
issue templates for bug reports and feature proposals.

## License

This project is licensed under the [MIT License](LICENSE).


## One-page web interface (Windows)

A local Streamlit page (`app.py`) covers the whole workflow:
**upload a folder / ZIP / several daily NASA POWER CSV files -> analyse -> download the point table.**

Double-click `Start_NPCGA.bat` (Python 3.12 required). The first launch creates the environment,
installs the `web` and `gis` extras and opens `http://localhost:8501`. Keep the terminal window
open while using the app. Arabic guide: `دليل_الاستخدام_بالعربي.md`.

Downloads: the point table as CSV, or a ZIP with Shapefile, GeoPackage, GeoJSON, CSV, the field
guide, `points_issues.csv` and the generated ArcPy script. The page does not interpolate; it
prepares points for ArcGIS Pro. Monthly POWER CSV and NetCDF are not supported yet.
Files are processed on your computer only.


## Developer
Developed by **Mahmoud Mohamed Atia** (محمود محمد عطية), surveying engineer (geomatics and GIS).
LinkedIn: https://www.linkedin.com/in/𝐌𝐚𝐡𝐦𝐨𝐮𝐝-𝐌𝐨𝐡𝐚𝐦𝐞𝐝-𝐀𝐭𝐢𝐚-57a9ba235

## How to cite
See `CITATION.cff`. Please also acknowledge the data source: NASA Langley Research Center (LaRC)
POWER Project, https://power.larc.nasa.gov/.

## More documentation
`docs/METHODS.md` (definitions, units, limitations) - `docs/WINDOWS.md` - `docs/GITHUB_PUBLISHING.md`
- `examples/README.md` - `CHANGELOG.md` - `CONTRIBUTING.md` - `SECURITY.md`.
