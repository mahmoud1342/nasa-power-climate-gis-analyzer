from .common import aggregate_series, daily_series
from .compare import CompareResult, compare_locations
from .etccdi import annual_indices
from .profile import variable_profile
from .rainfall import (
    annual_totals,
    anomalies,
    extreme_days,
    monthly_climatology,
    monthly_totals,
)
from .stats import climate_summary, describe
from .trends import MKResult, mann_kendall, trend_table

__all__ = [
    "CompareResult",
    "MKResult",
    "aggregate_series",
    "annual_indices",
    "annual_totals",
    "anomalies",
    "climate_summary",
    "compare_locations",
    "daily_series",
    "describe",
    "extreme_days",
    "mann_kendall",
    "monthly_climatology",
    "monthly_totals",
    "trend_table",
    "variable_profile",
]
