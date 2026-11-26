"""Reader for CSV files downloaded from the NASA POWER website / Data Access Viewer.

Format: a text header between '-BEGIN HEADER-' and '-END HEADER-', then a CSV table
(YEAR,DOY,PARAM... or YEAR,MO,DY,PARAM...). -999 is converted to NaN and counted.
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import pandas as pd

from .. import config
from ..power.client import PowerResult
from ..power.params import PARAMETERS
from .dates import dates_from_columns

_END = "-END HEADER-"
_COORD_RE = re.compile(r"latitude\s+(-?\d+(?:\.\d+)?)\s+longitude\s+(-?\d+(?:\.\d+)?)", re.IGNORECASE)
_ELEV_RE = re.compile(r"=\s*(-?\d+(?:\.\d+)?)\s*meters", re.IGNORECASE)
_UNITS_RE = re.compile(r"^(\w+)\s+.*\(([^()]*)\)\s*$")
_FILE_RE = re.compile(r"lat(-?\d+(?:\.\d+)?)_lon(-?\d+(?:\.\d+)?)", re.IGNORECASE)
_TIME_COLS = {"YEAR", "DOY", "MO", "DY", "DATE"}
_MONTH_COLS = {"JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC", "ANN"}


class PowerFileError(ValueError):
    """The file is not a readable NASA POWER daily CSV."""


def _parse_header(header: list[str]) -> dict:
    info: dict = {"lat": None, "lon": None, "elevation": None, "units": {}}
    in_params = False
    for line in header:
        if (m := _COORD_RE.search(line)):
            info["lat"], info["lon"] = float(m.group(1)), float(m.group(2))
        if (m := _ELEV_RE.search(line)):
            info["elevation"] = float(m.group(1))
        if line.strip().lower().startswith("parameter(s)"):
            in_params = True
            continue
        if in_params and (m := _UNITS_RE.match(line.strip())):
            info["units"][m.group(1)] = m.group(2).strip()
    return info


def read_power_csv(path) -> PowerResult:
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    had_bad_chars = "\ufffd" in text
    lines = text.splitlines()
    end = next((i for i, ln in enumerate(lines) if ln.strip() == _END), None)
    if end is None:
        raise PowerFileError("not a NASA POWER CSV ('-END HEADER-' line not found)")
    info = _parse_header(lines[:end])

    body = "\n".join(lines[end + 1:])
    if not body.strip():
        raise PowerFileError("no data rows after the header")
    table = pd.read_csv(io.StringIO(body))
    cols_upper = {c.upper() for c in table.columns}
    if cols_upper & _MONTH_COLS:
        raise PowerFileError("monthly/annual POWER CSV is not supported yet (daily files only)")

    try:
        dates, used = dates_from_columns(table)
    except (ValueError, KeyError) as exc:
        raise PowerFileError(f"cannot build dates: {exc}") from exc
    warnings: list[str] = []
    if had_bad_chars:
        warnings.append("file contains undecodable characters (replaced); check the file encoding")
    param_cols = [c for c in table.columns if c not in used and c.upper() not in _TIME_COLS]
    if not param_cols:
        raise PowerFileError("no parameter columns found")

    data = pd.DataFrame({"date": dates})
    nodata: dict[str, int] = {}
    for c in param_cols:
        num = pd.to_numeric(table[c], errors="coerce")
        bad = int((num.isna() & table[c].notna()).sum())
        if bad:
            warnings.append(f"{c}: {bad} non-numeric value(s) treated as missing")
        mask = num.to_numpy(dtype=float) == config.POWER_NODATA
        nodata[c] = int(mask.sum())
        data[c] = num.mask(mask).to_numpy()

    lat, lon = info["lat"], info["lon"]
    fm = _FILE_RE.search(path.name)
    if lat is None and fm:
        lat, lon = float(fm.group(1)), float(fm.group(2))
        warnings.append("coordinates taken from the file name (not found in the header)")
    elif lat is not None and fm and (abs(float(fm.group(1)) - lat) > 1e-6 or abs(float(fm.group(2)) - lon) > 1e-6):
        warnings.append(f"file name coordinates ({fm.group(1)}, {fm.group(2)}) differ from header ({lat}, {lon})")
    if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise PowerFileError(f"coordinates out of range: latitude {lat}, longitude {lon}")
    if lat is None:
        raise PowerFileError("cannot determine coordinates (no header location and no lat/lon in file name)")

    units = {c: info["units"].get(c) or (PARAMETERS[c].default_units if c in PARAMETERS else "")
             for c in param_cols}
    return PowerResult(
        data=data, annual=pd.DataFrame(), units=units, nodata_counts=nodata, latitude=lat,
        longitude=lon, elevation=info["elevation"], temporal="daily", community="",
        extra={"source_file": path.name, "warnings": warnings},
    )
