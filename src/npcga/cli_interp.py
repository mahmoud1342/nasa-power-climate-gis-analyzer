"""IDW interpolation of a points table (latitude, longitude, value) to a GeoTIFF + cross-validation.

    python -m npcga.cli_interp --points outputs/nepal/points_mean_annual_rainfall.csv \\
        --value mean_annual_rain_mm --name nepal_idw
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import config
from .interp import (
    MIN_POINTS,
    idw_grid,
    loo_cv_idw,
    project_points,
    utm_epsg,
    write_geotiff,
)
from .interp.idw import EXPLORATORY_BELOW
from .qc import check_points

POWERS_TO_COMPARE = [1.0, 1.5, 2.0, 3.0, 4.0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=f"{config.APP_NAME} - IDW interpolation")
    ap.add_argument("--points", required=True, help="CSV with latitude, longitude and a value column")
    ap.add_argument("--value", required=True, help="name of the value column")
    ap.add_argument("--lat-col", default="latitude")
    ap.add_argument("--lon-col", default="longitude")
    ap.add_argument("--cell", type=float, default=5000.0, help="cell size in metres (default 5000)")
    ap.add_argument("--power", type=float, default=2.0)
    ap.add_argument("--neighbors", type=int, default=12)
    ap.add_argument("--radius", type=float, default=None, help="search radius in metres (default: none)")
    ap.add_argument("--buffer", type=float, default=0.0, help="extra extent around the points, metres")
    ap.add_argument("--no-mask", action="store_true", help="do NOT mask cells outside the convex hull")
    ap.add_argument("--epsg", type=int, default=None, help="projected CRS (default: UTM zone of the centroid)")
    ap.add_argument("--drop-missing", action="store_true", help="drop rows with a missing value (reported)")
    ap.add_argument("--name", default="idw")
    ap.add_argument("--out", default="outputs")
    args = ap.parse_args(argv)

    try:
        df = pd.read_csv(args.points, encoding="utf-8-sig")
        for c in (args.lat_col, args.lon_col, args.value):
            if c not in df.columns:
                raise ValueError(f"column '{c}' not found; columns: {list(df.columns)}")
        qc = check_points(df, args.lat_col, args.lon_col)
        if qc.has_errors:
            raise ValueError("invalid coordinates:\n" + qc.to_text())
        n_missing = int(df[args.value].isna().sum())
        if n_missing and not args.drop_missing:
            raise ValueError(f"{n_missing} row(s) have no '{args.value}' value; fix them or use --drop-missing")
        df = df.dropna(subset=[args.value]).reset_index(drop=True)

        lon, lat = df[args.lon_col].to_numpy(float), df[args.lat_col].to_numpy(float)
        epsg = args.epsg or utm_epsg(float(lon.mean()), float(lat.mean()))
        x, y = project_points(lon, lat, epsg)
        xy = pd.DataFrame({"x": x, "y": y}).to_numpy()
        values = df[args.value].to_numpy(float)

        print(f"{len(df)} points, CRS EPSG:{epsg}, cell {args.cell:g} m")
        rows = []
        for p in POWERS_TO_COMPARE:
            _, m = loo_cv_idw(xy, values, p, args.neighbors, args.radius)
            rows.append({"power": p, **{k: m[k] for k in ("n", "ME", "MAE", "RMSE", "R2")}})
        powers = pd.DataFrame(rows)
        cv_table, cv = loo_cv_idw(xy, values, args.power, args.neighbors, args.radius)

        z, _, _, origin = idw_grid(xy, values, args.cell, args.power, args.neighbors,
                                   args.radius, args.buffer, mask_outside_hull=not args.no_mask)
    except (ValueError, OSError, ImportError) as exc:
        print(f"ERROR: {exc}")
        return 2

    if len(df) < EXPLORATORY_BELOW:
        status = f"EXPLORATORY (fewer than {EXPLORATORY_BELOW} points)"
    else:
        status = "interpolated with leave-one-out cross-validation (see statistics)"
    tags = {"method": "IDW", "power": args.power, "n_neighbors": args.neighbors,
            "radius_m": args.radius, "n_points": len(df), "value_column": args.value,
            "source": "NASA POWER (gridded product)", "status": status, "software": config.APP_NAME}
    out = Path(args.out) / args.name
    out.mkdir(parents=True, exist_ok=True)
    tif = write_geotiff(out / f"{args.name}.tif", z, origin, args.cell, epsg, tags)
    cv_out = df[[args.lat_col, args.lon_col]].join(cv_table)
    cv_out.to_csv(out / "cv_points.csv", index=False, encoding="utf-8-sig")
    powers.to_csv(out / "cv_power_comparison.csv", index=False, encoding="utf-8-sig")

    lon_span = float(lon.max() - lon.min())
    lines = [
        f"{config.APP_NAME} - IDW", f"Input: {args.points}  (value column: {args.value})",
        f"Points used: {len(df)}" + (f" ({n_missing} dropped: missing value)" if n_missing else ""),
        f"CRS: EPSG:{epsg} (distances in metres); cell size {args.cell:g} m",
        f"Parameters: power {args.power}, neighbours {args.neighbors}, radius {args.radius}",
        f"Cells outside the convex hull of the points: {'kept (extrapolated)' if args.no_mask else 'masked as NoData'}",
        (f"Leave-one-out CV (error = predicted - observed): n={cv['n']}/{cv['n_points']}, "
         f"ME={cv['ME']:.3f}, MAE={cv['MAE']:.3f}, RMSE={cv['RMSE']:.3f}, R2={cv['R2']:.3f}"),
        f"Status: {status}",
        ("Limitations: the input points are NASA POWER grid cells (about 0.5 x 0.625 degrees); the "
         "surface cannot contain detail finer than that grid, and the raster cell size is only a "
         "display resolution. IDW stays within the range of the input values and does not model "
         "spatial structure or give uncertainty (use Kriging for that)."),
    ]
    if lon_span > 12:
        lines.append(f"WARNING: longitude span {lon_span:.1f} degrees is large for a single UTM zone.")
    (out / "report.txt").write_text("\n".join(lines), encoding="utf-8")

    print("\nCross-validation by power (lower RMSE is better):")
    print(powers.round(3).to_string(index=False))
    print(f"\nUsing power {args.power}: RMSE {cv['RMSE']:.2f}, MAE {cv['MAE']:.2f}, R2 {cv['R2']:.3f}")
    print(f"Status: {status}")
    print(f"GeoTIFF: {tif.resolve()}")
    print(f"Min points required: {MIN_POINTS}. Open the .tif in ArcGIS Pro (Add Data).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
