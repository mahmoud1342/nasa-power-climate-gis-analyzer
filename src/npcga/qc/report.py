"""Data-quality checks. These functions only REPORT; they never modify the input."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .. import config
from ..power.params import PHYSICAL_RANGES

_NON_PARAM_COLUMNS = {"date", "year", "lat", "lon", "latitude", "longitude"}


@dataclass
class QCIssue:
    severity: str  # "error" | "warning" | "info"
    code: str
    message: str
    count: int = 0
    details: dict = field(default_factory=dict)


@dataclass
class QCReport:
    n_rows: int
    issues: list[QCIssue] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    def codes(self) -> set[str]:
        return {i.code for i in self.issues}

    def to_dict(self) -> dict:
        return {"n_rows": self.n_rows, "summary": self.summary,
                "issues": [vars(i) for i in self.issues]}

    def to_text(self) -> str:
        lines = [f"Rows checked: {self.n_rows}"]
        if not self.issues:
            lines.append("No issues found.")
        for i in self.issues:
            lines.append(f"[{i.severity.upper()}] {i.code}: {i.message}")
        return "\n".join(lines)


def check_timeseries(df: pd.DataFrame, date_col: str = "date", freq: str = "D",
                     parameters: list[str] | None = None,
                     ranges: dict[str, tuple[float, float]] | None = None) -> QCReport:
    """freq: 'D' (daily) or 'MS' (monthly). Returns a QCReport; ``df`` is left untouched."""
    if freq not in ("D", "MS"):
        raise ValueError("freq must be 'D' (daily) or 'MS' (monthly)")
    report = QCReport(n_rows=len(df))
    ranges = {**PHYSICAL_RANGES, **(ranges or {})}

    if date_col not in df.columns:
        report.issues.append(QCIssue("error", "NO_DATE_COLUMN", f"column '{date_col}' not found"))
        return report

    dates = pd.to_datetime(df[date_col], errors="coerce")
    bad = int(dates.isna().sum())
    if bad:
        report.issues.append(QCIssue("error", "BAD_DATES", f"{bad} unparseable date value(s)", bad))
    valid = dates.dropna()

    if len(valid):
        report.summary.update(start=str(valid.min().date()), end=str(valid.max().date()))
        norm = valid.dt.to_period("M").dt.to_timestamp() if freq == "MS" else valid.dt.normalize()

        dup = int(norm.duplicated().sum())
        if dup:
            report.issues.append(QCIssue("error", "DUPLICATE_DATES", f"{dup} duplicate date(s)", dup))
        if not valid.is_monotonic_increasing:
            report.issues.append(QCIssue("warning", "UNSORTED", "dates are not in ascending order"))

        expected = pd.date_range(norm.min(), norm.max(), freq=freq)
        missing = expected.difference(pd.DatetimeIndex(norm.unique()))
        report.summary["expected_steps"] = len(expected)
        if len(missing):
            sample = [str(d.date()) for d in missing[:5]]
            report.issues.append(QCIssue(
                "warning", "MISSING_DATES", f"{len(missing)} missing time step(s), e.g. {sample}",
                len(missing), {"first": sample}))

    cols = parameters or [c for c in df.columns
                          if c.lower() not in _NON_PARAM_COLUMNS and c != date_col]
    per_param: dict[str, dict] = {}
    for col in cols:
        if col not in df.columns:
            report.issues.append(QCIssue("error", "MISSING_COLUMN", f"parameter column '{col}' not found"))
            continue
        raw = df[col]
        values = pd.to_numeric(raw, errors="coerce")
        non_numeric = int((values.isna() & raw.notna()).sum())
        if non_numeric:
            report.issues.append(QCIssue("error", "NON_NUMERIC", f"{col}: {non_numeric} non-numeric value(s)", non_numeric))

        arr = values.to_numpy(dtype=float)
        n_inf = int(np.isinf(arr).sum())
        if n_inf:
            report.issues.append(QCIssue("error", "INFINITE_VALUES", f"{col}: {n_inf} infinite value(s)", n_inf))
        sentinel = int((arr == config.POWER_NODATA).sum())
        if sentinel:
            report.issues.append(QCIssue(
                "warning", "NODATA_SENTINEL",
                f"{col}: {sentinel} value(s) equal to {config.POWER_NODATA:g} (NASA POWER NoData). "
                "Left unchanged; convert to NaN explicitly before analysis.", sentinel))

        n_nan = int(values.isna().sum())
        pct = round(100 * n_nan / len(df), 2) if len(df) else 0.0
        per_param[col] = {"missing": n_nan, "missing_pct": pct}
        if len(df) and n_nan == len(df):
            report.issues.append(QCIssue("error", "ALL_MISSING", f"{col}: every value is missing", n_nan))
        elif n_nan:
            report.issues.append(QCIssue("info", "MISSING_VALUES", f"{col}: {n_nan} missing ({pct}%)", n_nan))

        if col in ranges:
            lo, hi = ranges[col]
            usable = values[np.isfinite(arr) & (arr != config.POWER_NODATA)]
            out = usable[(usable < lo) | (usable > hi)]
            if len(out):
                report.issues.append(QCIssue(
                    "warning", "OUT_OF_RANGE",
                    f"{col}: {len(out)} value(s) outside [{lo:g}, {hi:g}] "
                    f"(observed min {out.min():g}, max {out.max():g})", len(out)))

    report.summary["parameters"] = per_param
    return report


def check_points(df: pd.DataFrame, lat_col: str = "lat", lon_col: str = "lon") -> QCReport:
    """Validate a table of locations (e.g. an uploaded CSV). Does not modify ``df``."""
    report = QCReport(n_rows=len(df))
    for col in (lat_col, lon_col):
        if col not in df.columns:
            report.issues.append(QCIssue("error", "NO_COORD_COLUMN", f"column '{col}' not found"))
    if report.issues:
        return report

    lat = pd.to_numeric(df[lat_col], errors="coerce")
    lon = pd.to_numeric(df[lon_col], errors="coerce")
    unreadable = int((lat.isna() | lon.isna()).sum())
    if unreadable:
        report.issues.append(QCIssue("error", "BAD_COORDS", f"{unreadable} row(s) with missing/non-numeric coordinates", unreadable))
    out = int((((lat < -90) | (lat > 90)) | ((lon < -180) | (lon > 180))).sum())
    if out:
        report.issues.append(QCIssue("error", "COORDS_OUT_OF_RANGE", f"{out} row(s) outside lat -90..90 / lon -180..180", out))
    dup = int(pd.DataFrame({"a": lat, "b": lon}).dropna().duplicated().sum())
    if dup:
        report.issues.append(QCIssue("warning", "DUPLICATE_POINTS", f"{dup} duplicate coordinate pair(s)", dup))
    return report
