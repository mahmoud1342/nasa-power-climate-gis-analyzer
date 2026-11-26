"""Yearly series and monthly climatology for ANY variable, with the right aggregation:
precipitation is summed (mm), everything else is averaged. Used by the web page."""
from __future__ import annotations

import pandas as pd

from .stats import DEFAULT_HOW, climate_summary


def variable_profile(daily: pd.DataFrame, var: str) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Return (yearly[year, value], monthly_climatology[month, value], 'sum' | 'mean')."""
    how = DEFAULT_HOW.get(var, "mean")
    yearly = climate_summary(daily, "Y", [var])[["year", var]].rename(columns={var: "value"})
    monthly = climate_summary(daily, "M", [var])
    clim = (monthly.dropna(subset=[var]).groupby("month")[var].mean()
            .reindex(range(1, 13)).rename_axis("month").rename("value").reset_index())
    return yearly, clim, how
