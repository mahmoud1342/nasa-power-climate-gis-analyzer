"""Descriptive statistics and monthly/annual summaries for any climate parameter."""
from __future__ import annotations

import pandas as pd

from .common import DEFAULT_MIN_VALID_FRACTION, aggregate_series, daily_series

# Precipitation is accumulated (sum); everything else is averaged.
DEFAULT_HOW = {"PRECTOTCORR": "sum"}


def describe(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """count, missing, mean, median, std (ddof=1), min, p25, p75, max per column."""
    cols = columns or [c for c in df.select_dtypes("number").columns if c.lower() != "year"]
    rows = {}
    for c in cols:
        v = pd.to_numeric(df[c], errors="coerce")
        rows[c] = {
            "count": int(v.count()), "missing": int(v.isna().sum()), "mean": v.mean(),
            "median": v.median(), "std": v.std(ddof=1), "min": v.min(),
            "p25": v.quantile(0.25), "p75": v.quantile(0.75), "max": v.max(),
        }
    return pd.DataFrame(rows).T.rename_axis("parameter").reset_index()


def climate_summary(df: pd.DataFrame, freq: str, columns: list[str],
                    how: dict[str, str] | None = None,
                    min_valid_fraction: float = DEFAULT_MIN_VALID_FRACTION) -> pd.DataFrame:
    """Wide monthly ('M') or annual ('Y') table: one value column + one n_valid column per parameter."""
    how = {**DEFAULT_HOW, **(how or {})}
    out = None
    for c in columns:
        agg = aggregate_series(daily_series(df, c), freq, how.get(c, "mean"), min_valid_fraction)
        keys = [k for k in ("period_start", "year", "month") if k in agg.columns]
        part = agg.rename(columns={"value": c, "n_valid": f"{c}_n_valid"}).drop(columns="n_expected")
        out = part if out is None else out.merge(part, on=keys, how="outer")
    return out.sort_values("period_start").reset_index(drop=True)
