"""Generic CSV time-series reader (any CSV with a date column or YEAR+DOY / YEAR+MONTH+DAY)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .dates import dates_from_columns


def read_timeseries_csv(path, date_col: str | None = None, dayfirst: bool | None = None) -> pd.DataFrame:
    """Return a DataFrame whose first column is ``date``; other columns are kept untouched.

    Separator is auto-detected. Rows are never dropped or modified; run npcga.qc afterwards.
    """
    df = pd.read_csv(Path(path), sep=None, engine="python", encoding="utf-8-sig")
    dates, used = dates_from_columns(df, date_col, dayfirst)
    rest = df.drop(columns=used)
    out = pd.concat([pd.Series(dates, name="date"), rest.reset_index(drop=True)], axis=1)
    return out
