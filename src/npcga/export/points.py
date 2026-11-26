"""Per-location point table for GIS (ArcGIS Pro): one row per NASA POWER grid cell.

Nothing is removed: duplicates, QC problems and missing results are FLAGGED with explicit
columns so the user decides what to use. CRS of all outputs: WGS 84 (EPSG:4326).
Flags are written as 1/0 (not True/False) for reliable import into ArcGIS.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..analysis import annual_totals, mann_kendall, monthly_climatology, monthly_totals
from ..io.folder import FolderResult, rainfall_by_location

MONTHS = [f"M{m:02d}" for m in range(1, 13)]

# (column, shapefile name <= 10 chars, unit, description)
FIELDS: list[tuple[str, str, str, str]] = [
    ("location_id", "loc_id", "", "Stable unique ID built from the coordinates (N/S lat, E/W lon); repeats get -2, -3..."),
    ("file", "src_file", "", "Source CSV file name"),
    ("latitude", "lat", "degrees", "Latitude, WGS 84 (EPSG:4326)"),
    ("longitude", "lon", "degrees", "Longitude, WGS 84 (EPSG:4326)"),
    ("elevation_m", "elev_m", "m", "Elevation of the POWER cell from the file header"),
    ("n_records", "n_rec", "days", "Number of daily records in the file"),
    ("start", "start", "", "First date in the file"),
    ("end", "end", "", "Last date in the file"),
    ("missing_dates", "miss_dts", "days", "Calendar days absent from the file between first and last date"),
    ("nodata_values", "nodata", "count", "Values equal to -999 converted to NaN"),
    ("qc_errors", "qc_err", "count", "Number of QC errors for this file (see points_issues.csv)"),
    ("qc_warnings", "qc_warn", "count", "Number of QC warnings for this file"),
    ("mean_annual_rain_mm", "rain_mean", "mm/year", "Mean of annual totals over COMPLETE years (>= 90% valid days)"),
    ("std_annual_rain_mm", "rain_std", "mm/year", "Standard deviation (n-1) of annual totals"),
    ("n_complete_years", "n_years", "years", "Years used for the annual statistics"),
    ("rx1day_max_mm", "rx1d_max", "mm", "Largest 1-day rainfall in the record"),
    ("mean_cdd_days", "cdd_mean", "days", "Mean annual maximum dry spell (CDD)"),
    ("mean_r95p_mm", "r95p_mean", "mm", "Mean annual rainfall on very wet days (R95p, simplified)"),
    ("sen_slope_mm_per_year", "sen_slope", "mm/year per year", "Sen's slope of annual totals (needs >= 3 complete years)"),
    ("mk_p_value", "mk_p", "", "Mann-Kendall p-value (normal approximation; approximate if few years)"),
    ("mk_trend", "mk_trend", "", "increasing / decreasing / no trend at alpha = 0.05"),
    ("mk_small_sample", "mk_small", "0/1", "1 if fewer than 10 years: trend test is only indicative"),
    *[(m, m.lower(), "mm/month", f"Mean monthly rainfall for month {int(m[1:])} (complete months only)") for m in MONTHS],
    ("duplicate_location", "dup_flag", "0/1", "1 if another file has the same coordinates (nothing is removed)"),
    ("duplicate_group", "dup_group", "", "Group number shared by duplicate locations (blank if none)"),
    ("data_status", "status", "", "ok / no_complete_years / qc_error / duplicate_location"),
    ("idw_valid", "idw_valid", "0/1", "1 only if status is ok: finite rainfall, no QC error, not duplicated"),
    ("note", "note", "", "Reason when a value could not be computed"),
]
COLUMNS = [f[0] for f in FIELDS]
SHP_NAMES = {f[0]: f[1] for f in FIELDS}


def _location_ids(lat: pd.Series, lon: pd.Series) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for la, lo in zip(lat, lon, strict=True):
        base = f"{'N' if la >= 0 else 'S'}{abs(la):07.3f}_{'E' if lo >= 0 else 'W'}{abs(lo):08.3f}"
        seen[base] = seen.get(base, 0) + 1
        out.append(base if seen[base] == 1 else f"{base}-{seen[base]}")
    return out


def build_points_table(fr: FolderResult) -> pd.DataFrame:
    """Build the point table from a loaded folder (see npcga.io.load_power_folder)."""
    base = rainfall_by_location(fr).drop(columns=["latitude", "longitude", "elevation_m"], errors="ignore")
    t = fr.locations.merge(base, on="file", how="left", suffixes=("", "_r"))

    extra = []
    for res in fr.results:
        e = {"file": res.extra.get("source_file"), "sen_slope_mm_per_year": np.nan, "mk_p_value": np.nan,
             "mk_trend": "", "mk_small_sample": np.nan, **{m: np.nan for m in MONTHS}, "_note": ""}
        try:
            ann = annual_totals(res.data)
            ok = ann.dropna(subset=["total_mm"])
            if len(ok) >= 3:
                r = mann_kendall(ok["total_mm"].to_numpy(), ok["year"].to_numpy(float))
                e.update(sen_slope_mm_per_year=r.sen_slope, mk_p_value=r.p_value, mk_trend=r.trend,
                         mk_small_sample=int(r.small_sample))
            else:
                e["_note"] = "fewer than 3 complete years: no trend computed"
            clim = monthly_climatology(monthly_totals(res.data)).set_index("month")["mean_mm"]
            for i, m in enumerate(MONTHS, 1):
                e[m] = clim.get(i, np.nan)
        except ValueError as exc:
            e["_note"] = f"not computed: {exc}"
        extra.append(e)
    t = t.merge(pd.DataFrame(extra), on="file", how="left")

    key = list(zip(t.latitude.round(6), t.longitude.round(6), strict=True))
    counts = pd.Series(key).map(pd.Series(key).value_counts())
    t["duplicate_location"] = (counts > 1).astype(int).to_numpy()
    groups = {k: i + 1 for i, k in enumerate(dict.fromkeys(k for k, c in zip(key, counts, strict=True) if c > 1))}
    t["duplicate_group"] = [groups.get(k, np.nan) for k in key]
    t["location_id"] = _location_ids(t.latitude, t.longitude)

    def status(r):
        if r["duplicate_location"]:
            return "duplicate_location"
        if r["qc_errors"] > 0:
            return "qc_error"
        if not np.isfinite(r.get("mean_annual_rain_mm", np.nan)):
            return "no_complete_years"
        return "ok"

    t["data_status"] = t.apply(status, axis=1)
    t["idw_valid"] = (t["data_status"] == "ok").astype(int)
    notes = (t["note"].fillna("").astype(str) + "; " + t["_note"].fillna("") + "; " + t["notes"].fillna(""))
    t["note"] = notes.str.replace(r"(^[; ]+|[; ]+$)", "", regex=True).str.replace(r"(; ){2,}", "; ", regex=True)
    return t[COLUMNS].sort_values(["latitude", "longitude", "file"]).reset_index(drop=True)


def write_points(table: pd.DataFrame, folder, formats=("csv", "geojson", "gpkg", "shp")) -> dict:
    """Write the point table. Returns {'written': [...], 'skipped': [...]}.

    csv needs only pandas; the others need geopandas + pyogrio (the 'gis' extra).
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    written, skipped = [], []
    if "csv" in formats:
        table.to_csv(folder / "points.csv", index=False, encoding="utf-8-sig")
        written.append("points.csv")
    doc = pd.DataFrame(FIELDS, columns=["field", "shapefile_name", "unit", "description"])
    doc.to_csv(folder / "points_fields.csv", index=False, encoding="utf-8-sig")
    written.append("points_fields.csv")
    from .tables import fields_guide_ar

    fields_guide_ar().to_csv(folder / "points_fields_ar.csv", index=False, encoding="utf-8-sig")
    written.append("points_fields_ar.csv")

    gis = [f for f in formats if f != "csv"]
    if gis:
        try:
            import geopandas as gpd
        except ImportError:
            skipped.append("geojson/gpkg/shp skipped: install the GIS extra (pip install -e \".[gis]\")")
            return {"written": written, "skipped": skipped}
        gdf = gpd.GeoDataFrame(table.copy(), geometry=gpd.points_from_xy(table.longitude, table.latitude),
                               crs="EPSG:4326")
        if "geojson" in gis:
            gdf.to_file(folder / "points.geojson", driver="GeoJSON")
            written.append("points.geojson")
        if "gpkg" in gis:
            gdf.to_file(folder / "points.gpkg", driver="GPKG", layer="points")
            written.append("points.gpkg")
        if "shp" in gis:
            shp = gdf.rename(columns=SHP_NAMES)
            shp.to_file(folder / "points.shp", driver="ESRI Shapefile", encoding="utf-8")
            written.append("points.shp (+ .dbf .shx .prj .cpg)")
    return {"written": written, "skipped": skipped}
