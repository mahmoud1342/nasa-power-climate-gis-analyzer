"""Date-format detection. Never guesses silently: ambiguous day/month order raises an error."""
from __future__ import annotations

import pandas as pd

_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
            "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%d.%m.%Y"]
_DAY_FIRST = {"%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"}
_MONTH_FIRST = {"%m/%d/%Y", "%m-%d-%Y"}


def parse_dates_auto(values, dayfirst: bool | None = None):
    """Detect the date format of ``values`` and return (DatetimeIndex at midnight, format).

    A format is accepted only if EVERY non-empty value matches it. If day/month order cannot
    be determined (all days <= 12) a ValueError asks for ``dayfirst=True/False``.
    Empty values become NaT (reported later by the QC step, not dropped).
    """
    s = pd.Series(values).reset_index(drop=True)
    if pd.api.types.is_datetime64_any_dtype(s):
        return pd.DatetimeIndex(s).normalize(), "datetime"
    text = s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    present = s.notna() & (text != "") & (text.str.lower() != "nan")
    if not present.any():
        raise ValueError("no dates found in the date column")
    masked = text.where(present)

    fits = []
    for fmt in _FORMATS:
        parsed = pd.to_datetime(masked, format=fmt, errors="coerce")
        if parsed[present].notna().all():
            fits.append((fmt, parsed))
    if not fits:
        raise ValueError(f"unrecognised date format; examples: {list(text[present].head(3))}")
    if len(fits) > 1:
        if dayfirst is None:
            raise ValueError("ambiguous date order (day/month vs month/day); "
                             "pass dayfirst=True or dayfirst=False")
        wanted = _DAY_FIRST if dayfirst else _MONTH_FIRST
        fits = [f for f in fits if f[0] in wanted] or fits
    fmt, parsed = fits[0]
    return pd.DatetimeIndex(parsed).normalize(), fmt


def dates_from_columns(df: pd.DataFrame, date_col: str | None = None, dayfirst: bool | None = None):
    """Build dates from a single date column, or YEAR+DOY, or YEAR+MONTH+DAY columns.

    Returns (DatetimeIndex, list_of_columns_used).
    """
    lower = {c.lower(): c for c in df.columns}
    if date_col:
        if date_col not in df.columns:
            raise KeyError(f"date column '{date_col}' not found; columns: {list(df.columns)}")
        return parse_dates_auto(df[date_col], dayfirst)[0], [date_col]
    for name in ("date", "datetime", "time", "timestamp"):
        if name in lower:
            return parse_dates_auto(df[lower[name]], dayfirst)[0], [lower[name]]

    if "year" in lower and "doy" in lower:
        y = pd.to_numeric(df[lower["year"]], errors="coerce")
        doy = pd.to_numeric(df[lower["doy"]], errors="coerce")
        if y.isna().any() or doy.isna().any():
            raise ValueError("YEAR/DOY columns contain non-numeric values")
        y, doy = y.astype(int), doy.astype(int)
        d = pd.to_datetime(y.astype(str) + "-01-01") + pd.to_timedelta(doy - 1, unit="D")
        bad = int(((d.dt.year != y) | (doy < 1)).sum())
        if bad:
            raise ValueError(f"{bad} invalid YEAR/DOY combination(s) (e.g. day 366 in a non-leap year)")
        return pd.DatetimeIndex(d), [lower["year"], lower["doy"]]

    month = next((lower[n] for n in ("mo", "month", "m") if n in lower), None)
    day = next((lower[n] for n in ("dy", "day", "d") if n in lower), None)
    if "year" in lower and month and day:
        parts = pd.DataFrame({"year": pd.to_numeric(df[lower["year"]], errors="coerce"),
                              "month": pd.to_numeric(df[month], errors="coerce"),
                              "day": pd.to_numeric(df[day], errors="coerce")})
        d = pd.to_datetime(parts, errors="coerce")
        if d.isna().any():
            raise ValueError(f"{int(d.isna().sum())} invalid YEAR/MONTH/DAY combination(s)")
        return pd.DatetimeIndex(d), [lower["year"], month, day]

    raise ValueError(f"could not find date information; columns found: {list(df.columns)}")
