"""Known NASA POWER parameters and physical sanity ranges used by QC."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParamInfo:
    code: str
    name: str
    default_units: str  # fallback only; real units are read from the API response when present


PARAMETERS: dict[str, ParamInfo] = {
    p.code: p
    for p in [
        ParamInfo("PRECTOTCORR", "Corrected precipitation", "mm/day"),
        ParamInfo("T2M", "Temperature at 2 m", "C"),
        ParamInfo("T2M_MAX", "Maximum temperature at 2 m", "C"),
        ParamInfo("T2M_MIN", "Minimum temperature at 2 m", "C"),
        ParamInfo("RH2M", "Relative humidity at 2 m", "%"),
        ParamInfo("WS2M", "Wind speed at 2 m", "m/s"),
        ParamInfo("PS", "Surface pressure", "kPa"),
        ParamInfo("ALLSKY_SFC_SW_DWN", "All-sky surface shortwave downward irradiance", "MJ/m^2/day"),
    ]
}

# Generous physical bounds, (min, max). Violations are reported as warnings, never "fixed".
PHYSICAL_RANGES: dict[str, tuple[float, float]] = {
    "PRECTOTCORR": (0.0, 2000.0),
    "T2M": (-90.0, 60.0),
    "T2M_MAX": (-90.0, 65.0),
    "T2M_MIN": (-90.0, 60.0),
    "RH2M": (0.0, 100.0),
    "WS2M": (0.0, 120.0),
    "PS": (0.0, 110.0),
    "ALLSKY_SFC_SW_DWN": (0.0, 50.0),
}
