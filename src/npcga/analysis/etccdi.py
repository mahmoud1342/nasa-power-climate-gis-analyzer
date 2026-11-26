"""Annual rainfall indices following ETCCDI definitions (simplified where noted).

Wet day: >= 1 mm.  Runs are broken by missing days.  All amounts in mm, counts in days.
"""
from __future__ import annotations

import calendar

import numpy as np
import pandas as pd

from .common import DEFAULT_MIN_VALID_FRACTION, daily_series
from .rainfall import WET_DAY_MM

INDEX_UNITS = {
    "PRCPTOT": "mm", "SDII": "mm/wet day", "R10mm": "days", "R20mm": "days",
    "Rx1day": "mm", "Rx5day": "mm", "altRx5day": "mm", "CDD": "days", "CWD": "days",
    "altCDD": "days", "altCWD": "days", "R95p": "mm", "R99p": "mm",
}


def _runs(mask: np.ndarray):
    """(start, end_inclusive) index arrays of every run of True values."""
    padded = np.concatenate(([False], mask, [False])).astype(np.int8)
    edges = np.flatnonzero(np.diff(padded))
    return edges[::2], edges[1::2] - 1


def _max_run(mask: np.ndarray) -> int:
    """Length of the longest run of True values."""
    starts, ends = _runs(mask)
    return int((ends - starts + 1).max()) if len(starts) else 0


def _spell_max_by_end_year(s: pd.Series, mask: np.ndarray) -> dict[int, int]:
    """Longest spell per year where a spell may span years; its FULL length is credited to
    the year in which it ends (climdex 'spells can span years'). Missing days break spells."""
    starts, ends = _runs(mask)
    out: dict[int, int] = {}
    for a, b in zip(starts, ends, strict=True):
        year = int(s.index[b].year)
        out[year] = max(out.get(year, 0), int(b - a + 1))
    return out


def annual_indices(daily: pd.DataFrame, col: str = "PRECTOTCORR",
                   base_period: tuple[int, int] | None = None,
                   min_valid_fraction: float = DEFAULT_MIN_VALID_FRACTION) -> pd.DataFrame:
    """One row per year. Years with too few valid days get NaN indices (n_valid still shown).

    Rx5day: windows may start in the previous year and are credited to the year they end in;
    altRx5day keeps windows inside the year.
    CDD / CWD: longest dry (< 1 mm) / wet (>= 1 mm) spell; spells may cross year boundaries and
    are credited to the year they end in. altCDD / altCWD: spells cut at year boundaries.
    R95p / R99p: annual total on days above the 95th / 99th percentile of wet-day rainfall in
    ``base_period`` (default: the whole record). Simplification: the percentile is taken
    directly with linear interpolation, without ETCCDI's bootstrap procedure, and a short base
    period gives unstable thresholds.
    """
    s = daily_series(daily, col)
    base = s if base_period is None else s[(s.index.year >= base_period[0]) & (s.index.year <= base_period[1])]
    base_wet = base[base >= WET_DAY_MM]
    p95 = float(np.percentile(base_wet, 95)) if len(base_wet) else float("nan")
    p99 = float(np.percentile(base_wet, 99)) if len(base_wet) else float("nan")
    roll5 = s.rolling(5, min_periods=5).sum()
    rx5_span = roll5.groupby(roll5.index.year).max()   # 5-day window credited to the year it ends in
    cdd_span = _spell_max_by_end_year(s, (s < WET_DAY_MM).to_numpy())
    cwd_span = _spell_max_by_end_year(s, (s >= WET_DAY_MM).to_numpy())

    rows = []
    for year, ys in s.groupby(s.index.year):
        n_exp = 366 if calendar.isleap(year) else 365
        n_valid = int(ys.count())
        row = {"year": year, "n_valid": n_valid, "n_expected": n_exp}
        if n_valid / n_exp < min_valid_fraction:
            row.update({k: np.nan for k in INDEX_UNITS})
        else:
            wet = (ys >= WET_DAY_MM).to_numpy()
            prcptot = float(ys[ys >= WET_DAY_MM].sum())
            n_wet = int(wet.sum())
            row.update({
                "PRCPTOT": prcptot,
                "SDII": prcptot / n_wet if n_wet else np.nan,
                "R10mm": int((ys >= 10).sum()),
                "R20mm": int((ys >= 20).sum()),
                "Rx1day": float(ys.max()),
                "Rx5day": float(rx5_span.get(int(year), np.nan)),
                "altRx5day": float(ys.rolling(5, min_periods=5).sum().max()),
                "CDD": cdd_span.get(int(year), 0),
                "CWD": cwd_span.get(int(year), 0),
                "altCDD": _max_run((ys < WET_DAY_MM).to_numpy()),
                "altCWD": _max_run(wet),
                "R95p": float(ys[ys > p95].sum()) if not np.isnan(p95) else np.nan,
                "R99p": float(ys[ys > p99].sum()) if not np.isnan(p99) else np.nan,
            })
        rows.append(row)
    return pd.DataFrame(rows)
