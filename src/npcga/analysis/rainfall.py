"""Rainfall analysis. Units: millimetres (mm) of precipitation; input is daily mm/day."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .common import DEFAULT_MIN_VALID_FRACTION, aggregate_series, daily_series

WET_DAY_MM = 1.0  # ETCCDI wet-day threshold


def monthly_totals(daily: pd.DataFrame, col: str = "PRECTOTCORR",
                   min_valid_fraction: float = DEFAULT_MIN_VALID_FRACTION) -> pd.DataFrame:
    a = aggregate_series(daily_series(daily, col), "M", "sum", min_valid_fraction)
    return a.rename(columns={"value": "total_mm", "period_start": "date"})


def annual_totals(daily: pd.DataFrame, col: str = "PRECTOTCORR",
                  min_valid_fraction: float = DEFAULT_MIN_VALID_FRACTION) -> pd.DataFrame:
    a = aggregate_series(daily_series(daily, col), "Y", "sum", min_valid_fraction)
    return a.rename(columns={"value": "total_mm"}).drop(columns="period_start")


def monthly_climatology(monthly: pd.DataFrame) -> pd.DataFrame:
    """Mean/std/min/max of the monthly totals for each calendar month (NaN months excluded)."""
    g = monthly.dropna(subset=["total_mm"]).groupby("month")["total_mm"]
    out = pd.DataFrame({"mean_mm": g.mean(), "std_mm": g.std(ddof=1), "min_mm": g.min(),
                        "max_mm": g.max(), "n_years": g.count()})
    return out.reindex(range(1, 13)).rename_axis("month").reset_index()


def anomalies(totals: pd.DataFrame, kind: str, reference: tuple[int, int] | None = None) -> pd.DataFrame:
    """Anomalies of monthly ('monthly') or annual ('annual') totals against a reference period.

    anomaly_mm   = total - reference mean (same calendar month for monthly data)
    anomaly_pct  = total / reference mean * 100   (percent of normal; NaN if the mean is 0)
    z            = anomaly / reference std (ddof=1; NaN if std is 0 or undefined)
    ``reference`` = (first_year, last_year) inclusive; default is the whole record.
    """
    if kind not in ("monthly", "annual"):
        raise ValueError("kind must be 'monthly' or 'annual'")
    out = totals.copy()
    ref = out if reference is None else out[(out["year"] >= reference[0]) & (out["year"] <= reference[1])]
    keys = ["month"] if kind == "monthly" else []
    if keys:
        stats = ref.dropna(subset=["total_mm"]).groupby(keys)["total_mm"].agg(["mean", "std"])
        out = out.merge(stats, left_on=keys, right_index=True, how="left")
        mean, std = out["mean"], out["std"]
    else:
        valid = ref["total_mm"].dropna()
        mean, std = valid.mean(), valid.std(ddof=1)
    out["reference_mean_mm"] = mean
    out["anomaly_mm"] = out["total_mm"] - mean
    out["anomaly_pct"] = np.where(np.asarray(mean) > 0, out["total_mm"] / mean * 100, np.nan)
    out["z"] = np.where(np.asarray(std) > 0, out["anomaly_mm"] / std, np.nan)
    return out.drop(columns=[c for c in ("mean", "std") if c in out.columns])


def extreme_days(daily: pd.DataFrame, col: str = "PRECTOTCORR", q: float = 95.0,
                 top_n: int | None = None) -> tuple[pd.DataFrame, float]:
    """Days with rainfall above the q-th percentile of wet days (>= 1 mm) of the whole record.

    Returns (table sorted by rainfall, threshold_mm). Threshold is NaN if there are no wet days.
    """
    s = daily_series(daily, col)
    wet = s[s >= WET_DAY_MM]
    if wet.empty:
        return pd.DataFrame(columns=["date", "precip_mm"]), float("nan")
    thr = float(np.percentile(wet, q))
    ex = s[s > thr].sort_values(ascending=False)
    table = pd.DataFrame({"date": ex.index, "precip_mm": ex.to_numpy()})
    return (table.head(top_n) if top_n else table), thr
