"""Command line: download one NASA POWER point and write a full rainfall/climate analysis.

    python -m npcga.cli --lat 31.20 --lon 29.92 --start 2015-01-01 --end 2024-12-31 --name alexandria
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import __version__, config
from .analysis import (
    annual_indices,
    annual_totals,
    anomalies,
    climate_summary,
    describe,
    extreme_days,
    monthly_climatology,
    monthly_totals,
    trend_table,
)
from .analysis.etccdi import INDEX_UNITS
from .power import get_point_data
from .qc import check_timeseries

PARAMETERS = ["PRECTOTCORR", "T2M"]


def _save(df: pd.DataFrame, folder: Path, name: str) -> None:
    df.to_csv(folder / name, index=False, encoding="utf-8-sig")  # utf-8-sig: opens cleanly in Excel
    print(f"  wrote {name}")


def main(argv=None, *, data_provider=get_point_data) -> int:
    ap = argparse.ArgumentParser(description=config.APP_NAME)
    ap.add_argument("--lat", type=float, default=31.20, help="latitude (default: Alexandria)")
    ap.add_argument("--lon", type=float, default=29.92, help="longitude (default: Alexandria)")
    ap.add_argument("--start", default="2015-01-01", help="YYYY-MM-DD")
    ap.add_argument("--end", default="2024-12-31", help="YYYY-MM-DD")
    ap.add_argument("--name", default="alexandria", help="output folder name")
    ap.add_argument("--out", default="outputs", help="parent output folder")
    ap.add_argument("--community", default="AG", choices=["AG", "RE", "SB"])
    args = ap.parse_args(argv)

    folder = Path(args.out) / args.name
    folder.mkdir(parents=True, exist_ok=True)

    print("1/4 Getting data (downloaded once, then cached)...")
    res = data_provider(args.lat, args.lon, PARAMETERS, args.start, args.end,
                        "daily", args.community)
    print(f"  {len(res.data)} daily records, {'from cache' if res.from_cache else 'downloaded'}")

    print("2/4 Quality check...")
    qc = check_timeseries(res.data, parameters=PARAMETERS)
    print("  " + qc.to_text().replace("\n", "\n  "))

    print("3/4 Analysis...")
    daily = res.data
    monthly = monthly_totals(daily)
    annual = annual_totals(daily)
    idx = annual_indices(daily)
    ex, thr = extreme_days(daily, q=95, top_n=20)
    trends_in = annual.merge(idx.drop(columns=["n_valid", "n_expected"]), on="year")
    trends_in = trends_in.rename(columns={"total_mm": "annual_total_mm"})
    trend_cols = ["annual_total_mm", *INDEX_UNITS]

    print("4/4 Writing results to:", folder.resolve())
    _save(daily, folder, "daily_data.csv")
    _save(describe(daily, PARAMETERS), folder, "descriptive_statistics.csv")
    _save(monthly, folder, "rain_monthly_totals.csv")
    _save(annual, folder, "rain_annual_totals.csv")
    _save(monthly_climatology(monthly), folder, "rain_monthly_climatology.csv")
    _save(anomalies(monthly, "monthly"), folder, "rain_monthly_anomalies.csv")
    _save(anomalies(annual, "annual"), folder, "rain_annual_anomalies.csv")
    _save(idx, folder, "rain_annual_indices_ETCCDI.csv")
    _save(ex, folder, "rain_extreme_days.csv")
    _save(trend_table(trends_in, trend_cols), folder, "rain_trends_MannKendall_Sen.csv")
    _save(climate_summary(daily, "M", PARAMETERS), folder, "climate_monthly_summary.csv")
    _save(climate_summary(daily, "Y", PARAMETERS), folder, "climate_annual_summary.csv")

    notes = [
        f"{config.APP_NAME} v{__version__}",
        f"Location requested: lat {args.lat}, lon {args.lon}",
        f"Location returned by POWER: lat {res.latitude}, lon {res.longitude}, elevation {res.elevation} m",
        f"Period: {args.start} to {args.end} (daily), community {args.community}",
        f"Parameters and units: {res.units}",
        f"NoData (-999) values converted to NaN: {res.nodata_counts}",
        f"Downloaded at (UTC): {res.fetched_at}; served from cache: {res.from_cache}",
        f"Extreme-day threshold (95th percentile of wet days >= 1 mm): {thr:.2f} mm",
        "",
        ("Source: data obtained from the NASA Langley Research Center (LaRC) POWER Project, "
         "https://power.larc.nasa.gov/"),
        ("Limitations: NASA POWER values are gridded satellite/reanalysis products, not station "
         "observations. Rainfall at a single grid cell can differ from local gauge records."),
        "Methods and definitions: see docs/METHODS.md",
        f"Developed by {config.DEVELOPER}  |  LinkedIn: {config.LINKEDIN_URL}",
    ]
    (folder / "metadata.txt").write_text("\n".join(notes), encoding="utf-8")
    (folder / "qc_report.txt").write_text(qc.to_text(), encoding="utf-8")
    print("  wrote metadata.txt, qc_report.txt")

    print("\nAnnual rainfall totals (mm):")
    print(annual[["year", "total_mm", "n_valid"]].round(1).to_string(index=False))
    print(f"\nDone. Open the CSV files in: {folder.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
