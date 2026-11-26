# Methods, units and limitations (rainfall & climate analysis)

## Data
NASA POWER daily point data. Precipitation (`PRECTOTCORR`) is in **mm/day**; units for every
parameter are read from the API response. POWER values are **gridded satellite/reanalysis
products**, not gauge observations. The NoData value **-999** is converted to NaN and counted.
Nothing is dropped, filled or interpolated.

## Completeness rule
A month or year gets a value only if at least **90 %** of its calendar days are valid
(`min_valid_fraction`, adjustable). Otherwise the value is NaN. `n_valid` and `n_expected`
are always reported. Partial first/last periods are therefore NaN, never under-counted.

## Rainfall
| Output | Definition | Unit |
|---|---|---|
| Monthly / annual total | sum of daily rainfall | mm |
| Monthly climatology | mean, std (n-1), min, max of the monthly totals per calendar month | mm |
| Anomaly | total - reference mean (same calendar month for monthly) | mm |
| Percent of normal | total / reference mean x 100 | % |
| z-score | anomaly / reference std (n-1) | - |
| Extreme days | days above the 95th percentile of wet days (>= 1 mm) of the whole record | mm |

## ETCCDI annual indices (wet day = rainfall >= 1 mm)
| Index | Definition | Unit |
|---|---|---|
| PRCPTOT | total rainfall on wet days | mm |
| SDII | PRCPTOT / number of wet days | mm per wet day |
| R10mm, R20mm | days with rainfall >= 10 mm, >= 20 mm | days |
| Rx1day, Rx5day | maximum 1-day, maximum 5-consecutive-day rainfall (window inside the year) | mm |
| CDD, CWD | longest dry (< 1 mm) / wet (>= 1 mm) spell; spells **may cross year boundaries** and the full spell is credited to the year it ends in (climdex.pcic default; not yet cross-checked numerically against R output) | days |
| altCDD, altCWD | same, but spells are cut at year boundaries | days |
| R95p, R99p | total rainfall on days above the 95th / 99th percentile of wet days in the base period | mm |

Simplifications: percentiles use linear interpolation over the whole record (or a chosen base
period) without the ETCCDI bootstrap; a short record gives unstable R95p/R99p thresholds.
A missing day breaks a dry/wet run. Rx1day and Rx5day are annual only (no monthly version yet).

## Trends
Mann-Kendall test (two-sided, normal approximation, tie-corrected variance) and Sen's slope
(median of pairwise slopes, per year when a year axis is given). Assumes independent
observations: **no autocorrelation correction**. With fewer than 10 values the result is flagged
`small_sample` and the p-value (normal approximation, no exact test) should be read as approximate.
Duplicate times, non-finite times and invalid `alpha` are rejected. Mann-Kendall results were verified against the `pymannkendall` package.

## Reading files
- **NASA POWER CSV (daily)**: header between `-BEGIN HEADER-` and `-END HEADER-` is parsed for
  coordinates, elevation and units; the table (`YEAR,DOY,...` or `YEAR,MO,DY,...`) gives the dates.
  Invalid day-of-year (e.g. 366 in a non-leap year) is an error, not a guess. `-999` becomes NaN
  and is counted. Coordinates fall back to the file name (`lat26.0_lon85.625`) with a warning.
- **Generic CSV**: separator auto-detected; date column auto-detected. A date format is accepted
  only if every value matches it. If day/month order is ambiguous the reader stops and asks.
- **Folder of files**: each file is read independently; files that fail are listed with the reason
  in `failed_files.csv`. Nothing is silently skipped. Duplicate coordinates are flagged.
- `points_mean_annual_rainfall.csv`: mean annual rainfall per location over complete years
  (>= 90 % valid days). It is the table to bring into ArcGIS Pro (XY Table To Point) or to use
  later for IDW / Kriging.

## Point table for GIS (main output for ArcGIS Pro)
`python -m npcga.cli_folder` writes `outputs/<name>/points/`: `points.csv`, `points.geojson`,
`points.gpkg`, `points.shp`, `points_fields.csv` (every field: unit + description + shapefile
name), `points_issues.csv` and `arcpy_import_points.py`. All files are **WGS 84 (EPSG:4326)**.
- One row per NASA POWER grid cell, with a stable `location_id` built from the coordinates.
- **Nothing is removed.** Duplicate coordinates, QC errors and missing results are flagged:
  `duplicate_location`, `duplicate_group`, `qc_errors`, `qc_warnings`, `data_status`
  (ok / no_complete_years / qc_error / duplicate_location), `idw_valid` (1 only if status is ok)
  and `note` (the reason when a value could not be computed). Flags are 1/0 for ArcGIS.
- Shapefile field names are limited to 10 characters; the mapping is in `points_fields.csv`.
- The ArcPy script is generated, **not tested by the generator** (ArcPy exists only in ArcGIS Pro).
- Rx5day windows may cross the year boundary and are credited to the year they end in;
  `altRx5day` keeps windows inside the year.

## Comparing locations (layers)
`npcga.analysis.compare_locations` compares two or more locations for one variable:
- yearly series and monthly climatology of every location, overlaid;
- per-location table: number of complete years, mean, standard deviation (n-1), minimum and
  maximum yearly value with their years, climatologically highest / lowest month, and the
  coefficient of variation (**rainfall only**, since it is meaningless for degrees C);
- correlation matrix (Pearson) of **monthly anomalies** (each month minus the location's own mean
  for that calendar month) so the shared seasonal cycle does not inflate the result; cells need at
  least 12 overlapping months, otherwise they stay empty.
Neighbouring NASA POWER cells share source data, so high correlations between them are expected.

## Arabic download tables
Every table states its time scale in a first column `نوع التحليل` (يومي / شهري / سنوي) and has
Arabic headers with units. The per-location summary tags each header: `[سنوي]`, `[شهري]`,
`[يومي]`, `[الموقع]`, `[جودة]`. Values are only labelled, never changed. GIS files keep short
English field names (Shapefile limit and ArcGIS compatibility); `points_fields_ar.csv` explains
each one in Arabic. The Excel workbook has right-to-left sheets: اقرأ أولاً, ملخص المواقع,
تحليل سنوي, تحليل شهري, شرح الأعمدة. Daily data (large) is generated on request.

## Spatial interpolation (IDW) - optional, not the focus
Interpolation is expected to be done in ArcGIS Pro. The command below is an optional extra.
`python -m npcga.cli_interp` interpolates a table of points (latitude, longitude, value).
- Points are projected to the **UTM zone of their centroid** (or `--epsg`); distances are in metres.
- z(x) = sum(w_i z_i) / sum(w_i), w_i = 1 / d_i^power. At most `--neighbors` nearest points inside
  `--radius` are used; no point in range gives NoData. A cell on a data point returns that value.
- IDW never produces values outside the range of the input values; it models no spatial
  structure and gives **no uncertainty**.
- Cells outside the convex hull of the points are NoData by default (`--no-mask` keeps them), so
  extrapolation is not presented as interpolation.
- At least 3 points are required (a single POWER point cannot be interpolated); fewer than 10
  points is labelled **EXPLORATORY**.
- **Leave-one-out cross-validation**: each point is predicted from the others. error = predicted -
  observed; ME = mean error, MAE, RMSE, and R2 = 1 - SSres/SStot (can be negative). A power
  comparison table (1, 1.5, 2, 3, 4) is written; the power actually used is the one you choose.
- Output: float32 GeoTIFF in the projected CRS, NoData -9999, method and parameters stored as
  GeoTIFF tags. The input points are NASA POWER grid cells (~0.5 x 0.625 degrees): the surface
  cannot hold finer detail, and the raster cell size is only a display resolution.
- Verified by hand-computed tests (weights, leave-one-out errors, hull masking, UTM/GeoTIFF
  round trip). Not yet compared against ArcGIS Pro's IDW output.

## Not yet implemented
NetCDF reading, monthly POWER CSV, SPI, Kriging, ArcPy script generation, PDF reports, web interface.
