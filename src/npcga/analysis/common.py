"""Shared helpers: clean daily series and completeness-aware aggregation."""
from __future__ import annotations

import pandas as pd

from .. import config

DEFAULT_MIN_VALID_FRACTION = 0.9


def daily_series(df: pd.DataFrame, col: str, date_col: str = "date") -> pd.Series:
    """Return ``col`` as a float Series on a complete daily index (missing days = NaN).

    Raises ValueError on duplicate dates, unparseable dates or an unconverted -999 NoData
    sentinel, because silently analysing those would give wrong numbers.
    """
    if date_col not in df.columns or col not in df.columns:
        raise KeyError(f"columns '{date_col}' and '{col}' are required")
    idx = pd.DatetimeIndex(pd.to_datetime(df[date_col], errors="coerce")).normalize()
    if idx.hasnans:
        raise ValueError("unparseable dates found; run npcga.qc.check_timeseries first")
    values = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
    if (values == config.POWER_NODATA).any():
        raise ValueError(f"{col}: NoData sentinel {config.POWER_NODATA:g} found; convert to NaN first")
    s = pd.Series(values, index=idx).sort_index()
    if s.index.has_duplicates:
        raise ValueError("duplicate dates found; run npcga.qc.check_timeseries first")
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"))


def aggregate_series(s: pd.Series, freq: str, how: str = "sum",
                     min_valid_fraction: float = DEFAULT_MIN_VALID_FRACTION) -> pd.DataFrame:
    """Aggregate a daily series to calendar months ('M') or years ('Y').

    A period gets a value only if at least ``min_valid_fraction`` of its calendar days are
    valid; otherwise the value is NaN. ``n_valid`` / ``n_expected`` are always returned so
    nothing is hidden. Partial first/last periods therefore become NaN, not under-counts.
    """
    if freq not in ("M", "Y"):
        raise ValueError("freq must be 'M' or 'Y'")
    if how not in ("sum", "mean"):
        raise ValueError("how must be 'sum' or 'mean'")
    grp = s.groupby(s.index.to_period(freq))
    n_valid = grp.count()
    n_expected = pd.Series(
        [(p.end_time.normalize() - p.start_time).days + 1 for p in n_valid.index], index=n_valid.index
    )
    value = grp.sum(min_count=1) if how == "sum" else grp.mean()
    value = value.where(n_valid / n_expected >= min_valid_fraction)
    out = pd.DataFrame({"value": value, "n_valid": n_valid, "n_expected": n_expected})
    out.insert(0, "year", out.index.year)
    if freq == "M":
        out.insert(1, "month", out.index.month)
    out.index = out.index.to_timestamp()
    out.index.name = "period_start"
    return out.reset_index()
