"""Mann-Kendall trend test and Sen's slope (no extra dependencies).

Assumes independent observations: no correction for autocorrelation. Intended for annual
or monthly series (up to a few thousand values), not for raw daily records.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

MAX_N = 5000


@dataclass
class MKResult:
    n: int
    s: float
    var_s: float
    z: float
    p_value: float
    trend: str  # "increasing" | "decreasing" | "no trend"
    sen_slope: float  # units of the data per unit of t (e.g. mm per year)
    alpha: float
    small_sample: bool  # True when n < 10: the normal approximation is unreliable


def mann_kendall(values, t=None, alpha: float = 0.05) -> MKResult:
    if not (0 < alpha < 1):
        raise ValueError("alpha must be between 0 and 1 (exclusive)")
    x = np.asarray(values, dtype=float)
    t_arr = np.arange(len(x), dtype=float) if t is None else np.asarray(t, dtype=float)
    if len(t_arr) != len(x):
        raise ValueError("values and t must have the same length")
    if not np.isfinite(t_arr).all():
        raise ValueError("t contains NaN or infinite values")
    if np.isinf(x).any():
        raise ValueError("values contain infinite numbers")
    keep = ~np.isnan(x)
    x, t_arr = x[keep], t_arr[keep]
    if len(np.unique(t_arr)) != len(t_arr):
        raise ValueError("duplicate time values in t; each observation needs a unique time")
    n = len(x)
    if n < 3:
        raise ValueError("at least 3 valid values are required")
    if n > MAX_N:
        raise ValueError(f"series too long ({n}); aggregate to monthly/annual first")

    order = np.argsort(t_arr, kind="stable")
    x, t_arr = x[order], t_arr[order]

    s = 0.0
    slopes = []
    for i in range(n - 1):
        dx = x[i + 1:] - x[i]
        s += np.sign(dx).sum()
        dt = t_arr[i + 1:] - t_arr[i]
        ok = dt != 0
        slopes.append(dx[ok] / dt[ok])
    sen = float(np.median(np.concatenate(slopes))) if slopes else float("nan")

    _, counts = np.unique(x, return_counts=True)
    ties = counts[counts > 1]
    var_s = (n * (n - 1) * (2 * n + 5) - float((ties * (ties - 1) * (2 * ties + 5)).sum())) / 18.0

    if s > 0:
        z = (s - 1) / math.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / math.sqrt(var_s)
    else:
        z = 0.0
    p = math.erfc(abs(z) / math.sqrt(2))
    trend = "no trend" if p >= alpha else ("increasing" if z > 0 else "decreasing")
    return MKResult(n, float(s), var_s, z, p, trend, sen, alpha, n < 10)


def trend_table(df: pd.DataFrame, columns: list[str], t_col: str = "year",
                alpha: float = 0.05) -> pd.DataFrame:
    """Mann-Kendall + Sen's slope for several columns of an annual table."""
    rows = []
    for c in columns:
        try:
            r = mann_kendall(df[c].to_numpy(dtype=float), df[t_col].to_numpy(dtype=float), alpha)
            rows.append({"variable": c, **vars(r)})
        except ValueError as exc:
            rows.append({"variable": c, "trend": f"not computed ({exc})"})
    return pd.DataFrame(rows)
