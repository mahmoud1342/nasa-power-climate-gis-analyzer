"""Analyse a folder of NASA POWER CSV files (one per location).

    python -m npcga.cli_folder --folder "D:\\path\\to\\nasa_power_raw" --name nepal
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import config
from .export import (
    annual_table,
    arabic_points,
    build_points_table,
    excel_workbook,
    monthly_table,
    to_arabic,
    to_csv_bytes,
    write_arcpy_script,
    write_points,
)
from .io import load_power_folder, rainfall_by_location


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=f"{config.APP_NAME} - folder of POWER CSV files")
    ap.add_argument("--folder", required=True, help="folder containing the POWER CSV files")
    ap.add_argument("--pattern", default="*.csv")
    ap.add_argument("--name", default="folder_analysis", help="output sub-folder name")
    ap.add_argument("--out", default="outputs", help="parent output folder")
    ap.add_argument("--formats", default="csv,geojson,gpkg,shp", help="point formats to write")
    args = ap.parse_args(argv)

    out = Path(args.out) / args.name
    out.mkdir(parents=True, exist_ok=True)

    def progress(i, n):
        if i == n or i % 20 == 0:
            print(f"  read {i}/{n} files")

    print("Reading files...")
    fr = load_power_folder(args.folder, args.pattern, progress)
    pts = rainfall_by_location(fr)

    fr.locations.to_csv(out / "locations.csv", index=False, encoding="utf-8-sig")
    pts.to_csv(out / "points_mean_annual_rainfall.csv", index=False, encoding="utf-8-sig")
    failed_path = out / "failed_files.csv"
    if fr.failures:
        import pandas as pd
        pd.DataFrame(fr.failures).to_csv(failed_path, index=False, encoding="utf-8-sig")
    else:
        failed_path.unlink(missing_ok=True)   # never leave a stale file from an earlier run

    table = build_points_table(fr)
    res = write_points(table, out / "points", tuple(args.formats.split(",")))
    write_arcpy_script(out / "points" / "arcpy_import_points.py", (out / "points" / "points.csv").resolve())
    ar = out / "arabic"
    ar.mkdir(exist_ok=True)
    (ar / "ملخص_المواقع.csv").write_bytes(to_csv_bytes(arabic_points(table)))
    (ar / "تحليل_سنوي.csv").write_bytes(to_csv_bytes(to_arabic(annual_table(fr, table), "annual")))
    (ar / "تحليل_شهري.csv").write_bytes(to_csv_bytes(to_arabic(monthly_table(fr, table), "monthly")))
    try:
        (ar / "تحليل_عربي_شامل.xlsx").write_bytes(excel_workbook(fr, table))
    except ImportError:
        res["skipped"].append("Excel skipped: pip install openpyxl")
    issues = table[(table.data_status != "ok") | (table.note != "") | (table.qc_warnings > 0)]
    issues[["location_id", "file", "data_status", "qc_errors", "qc_warnings", "duplicate_group", "note"]].to_csv(
        out / "points" / "points_issues.csv", index=False, encoding="utf-8-sig")

    loc = fr.locations
    lines = [f"Files found: {len(loc) + len(fr.failures)}",
             f"Read successfully: {len(loc)}", f"Failed: {len(fr.failures)}"]
    if len(loc):
        lines += [
            f"Latitude range: {loc.latitude.min()} to {loc.latitude.max()}",
            f"Longitude range: {loc.longitude.min()} to {loc.longitude.max()}",
            f"Period in files: {loc.start.min()} to {loc.end.max()}",
            f"Records per file: min {loc.n_records.min()}, max {loc.n_records.max()}",
            f"Files with QC errors: {int((loc.qc_errors > 0).sum())}; with warnings: {int((loc.qc_warnings > 0).sum())}",
            f"Total NoData (-999) values converted to NaN: {int(loc.nodata_values.sum())}",
            f"Duplicate/invalid location checks: {fr.points_qc.to_text()}",
        ]
        r = pts["mean_annual_rain_mm"]
        lines.append(f"Mean annual rainfall across locations: min {r.min():.0f}, max {r.max():.0f} mm")
        lines.append("Note: NASA POWER values are gridded products, not station observations.")
    lines += [
        "", f"Point table: {len(table)} locations; usable for interpolation (idw_valid = 1): {int(table.idw_valid.sum())}",
        (f"  flagged duplicates: {int(table.duplicate_location.sum())}; "
         f"no complete year: {int((table.data_status == 'no_complete_years').sum())}; "
         f"QC errors: {int((table.data_status == 'qc_error').sum())}"),
        "  CRS of all point files: WGS 84 (EPSG:4326). Nothing was removed; see points_issues.csv.",
        f"Developed by {config.DEVELOPER}  |  LinkedIn: {config.LINKEDIN_URL}",
        f"  written in {out / 'points'}: " + ", ".join(res["written"] + ["arcpy_import_points.py", "points_issues.csv"]),
        f"  Arabic tables (Excel + CSV: summary / annual / monthly) in {out / 'arabic'}",
        *res["skipped"],
    ]
    report = "\n".join(lines)
    (out / "folder_report.txt").write_text(report, encoding="utf-8")
    print("\n" + report)
    print(f"\nResults saved in: {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
