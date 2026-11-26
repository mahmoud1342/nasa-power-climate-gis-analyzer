"""Load a folder of NASA POWER CSV files (one file per location) and summarise it."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from ..analysis import annual_indices, annual_totals
from ..power.client import PowerResult
from ..qc import QCReport, check_points, check_timeseries
from .power_csv import PowerFileError, read_power_csv


@dataclass
class FolderResult:
    results: list[PowerResult]
    failures: list[dict]          # files that could not be read, with the reason (never silent)
    locations: pd.DataFrame       # one row per successfully read file
    points_qc: QCReport = field(default_factory=lambda: QCReport(0))


def load_power_folder(folder, pattern: str = "*.csv", progress=None) -> FolderResult:
    files = sorted(Path(folder).glob(pattern))
    if not files:
        raise FileNotFoundError(f"no files matching '{pattern}' in {folder}")
    results, failures, rows = [], [], []
    for i, f in enumerate(files, 1):
        try:
            res = read_power_csv(f)
        except (PowerFileError, ValueError, KeyError, pd.errors.ParserError, OSError) as exc:
            failures.append({"file": f.name, "reason": str(exc)})
        else:
            qc = check_timeseries(res.data, parameters=list(res.units))
            missing = sum(x.count for x in qc.issues if x.code == "MISSING_DATES")
            results.append(res)
            rows.append({
                "file": f.name, "latitude": res.latitude, "longitude": res.longitude,
                "elevation_m": res.elevation, "n_records": len(res.data),
                "start": qc.summary.get("start"), "end": qc.summary.get("end"),
                "missing_dates": missing, "nodata_values": sum(res.nodata_counts.values()),
                "qc_errors": sum(x.severity == "error" for x in qc.issues),
                "qc_warnings": sum(x.severity == "warning" for x in qc.issues),
                "notes": "; ".join(res.extra.get("warnings", [])),
            })
        if progress:
            progress(i, len(files))
    locations = pd.DataFrame(rows)
    points_qc = check_points(locations, "latitude", "longitude") if len(locations) else QCReport(0)
    return FolderResult(results, failures, locations, points_qc)


def rainfall_by_location(fr: FolderResult, col: str = "PRECTOTCORR") -> pd.DataFrame:
    """One row per location: mean annual rainfall (complete years only) and a few indices.

    This table (latitude, longitude, value) is the input for spatial interpolation / GIS.
    """
    rows = []
    for res in fr.results:
        row = {"file": res.extra.get("source_file"), "latitude": res.latitude,
               "longitude": res.longitude, "elevation_m": res.elevation, "note": ""}
        try:
            if col not in res.data.columns:
                raise ValueError(f"column {col} not in file")
            ann = annual_totals(res.data, col)
            idx = annual_indices(res.data, col)
            ok = ann["total_mm"].dropna()
            if not len(ok):
                row["note"] = "no complete year (>= 90% valid days): annual rainfall not computed"
            row.update({
                "mean_annual_rain_mm": ok.mean() if len(ok) else np.nan,
                "std_annual_rain_mm": ok.std(ddof=1) if len(ok) > 1 else np.nan,
                "n_complete_years": len(ok), "n_years_in_file": len(ann),
                "rx1day_max_mm": idx["Rx1day"].max(), "mean_cdd_days": idx["CDD"].mean(),
                "mean_r95p_mm": idx["R95p"].mean(),
            })
        except (ValueError, KeyError) as exc:
            row["note"] = f"not computed: {exc}"
        rows.append(row)
    return pd.DataFrame(rows)
