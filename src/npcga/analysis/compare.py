"""Compare several locations (layers) with each other for one variable.

Aggregation follows the variable: precipitation is summed, everything else averaged.
Correlation is computed on monthly ANOMALIES (each month minus that location's own mean for the
same calendar month), so the shared seasonal cycle does not inflate the result. Gridded
neighbouring cells are often strongly correlated by construction (shared source cells).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .stats import DEFAULT_HOW, climate_summary

MIN_PAIRS = 12  # fewer overlapping months than this -> correlation left as NaN


@dataclass
class CompareResult:
    yearly: pd.DataFrame        # long: label, year, value
    climatology: pd.DataFrame   # long: label, month, value
    summary: pd.DataFrame       # one row per location
    correlation: pd.DataFrame   # square matrix of monthly-anomaly Pearson correlations
    how: str                    # 'sum' or 'mean'


def compare_locations(items: dict[str, pd.DataFrame], var: str, min_pairs: int = MIN_PAIRS) -> CompareResult:
    """items = {label: daily DataFrame with 'date' and ``var``}. At least two locations."""
    if len(items) < 2:
        raise ValueError("select at least two locations to compare")
    how = DEFAULT_HOW.get(var, "mean")
    yearly_rows, clim_rows, summ_rows, anomalies = [], [], [], {}

    for label, df in items.items():
        y = climate_summary(df, "Y", [var])[["year", var]].rename(columns={var: "value"})
        m = climate_summary(df, "M", [var])
        ok = m.dropna(subset=[var])
        clim = ok.groupby("month")[var].mean().reindex(range(1, 13))
        yearly_rows.append(y.assign(label=label))
        clim_rows.append(clim.rename("value").rename_axis("month").reset_index().assign(label=label))

        vals = y["value"].dropna()
        years = y.dropna(subset=["value"])
        mean = float(vals.mean()) if len(vals) else np.nan
        std = float(vals.std(ddof=1)) if len(vals) > 1 else np.nan
        # CV only makes sense for ratio-scale totals such as rainfall (not for degrees C)
        cv = std / mean * 100 if how == "sum" and np.isfinite(mean) and mean != 0 and np.isfinite(std) else np.nan
        summ_rows.append({
            "label": label, "n_years": len(vals), "mean": mean, "std": std,
            # CV only makes sense for ratio-scale totals such as rainfall (not for degrees C)
            "cv_pct": cv,
            "min": float(vals.min()) if len(vals) else np.nan,
            "min_year": int(years.loc[years["value"].idxmin(), "year"]) if len(vals) else np.nan,
            "max": float(vals.max()) if len(vals) else np.nan,
            "max_year": int(years.loc[years["value"].idxmax(), "year"]) if len(vals) else np.nan,
            "peak_month": int(clim.idxmax()) if clim.notna().any() else np.nan,
            "low_month": int(clim.idxmin()) if clim.notna().any() else np.nan,
        })
        s = pd.Series(m[var].to_numpy(dtype=float), index=m["period_start"])
        anomalies[label] = s - s.groupby(s.index.month).transform("mean")

    wide = pd.DataFrame(anomalies)
    corr = wide.corr(min_periods=min_pairs)
    return CompareResult(
        yearly=pd.concat(yearly_rows, ignore_index=True)[["label", "year", "value"]],
        climatology=pd.concat(clim_rows, ignore_index=True)[["label", "month", "value"]],
        summary=pd.DataFrame(summ_rows), correlation=corr, how=how,
    )
