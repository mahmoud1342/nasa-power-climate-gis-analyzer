"""NASA POWER point client: request validation, retries, response parsing.

Nothing is silently dropped or altered: the NoData sentinel (-999) becomes NaN and
the number of converted values is reported in ``PowerResult.nodata_counts``.
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import numpy as np
import pandas as pd
import requests

from .. import config
from .params import PARAMETERS

MAX_PARAMS_PER_REQUEST = 20  # verify against current POWER documentation
COMMUNITIES = ("AG", "RE", "SB")
TEMPORALS = ("daily", "monthly")


class PowerAPIError(Exception):
    """The API failed, or returned something we cannot interpret."""


class PowerValidationError(ValueError):
    """The request itself is invalid (caught before any network call)."""


@dataclass
class PowerResult:
    data: pd.DataFrame  # column "date" + one column per parameter (monthly: months 1-12 only)
    annual: pd.DataFrame  # monthly only: columns "year" + parameters (POWER month "13")
    units: dict[str, str]
    nodata_counts: dict[str, int]
    latitude: float
    longitude: float
    elevation: float | None
    temporal: str
    community: str
    fetched_at: str = ""
    from_cache: bool = False
    extra: dict = field(default_factory=dict)


def _to_date(value, name: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y%m%d", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                pass
    raise PowerValidationError(f"{name}: expected a date or 'YYYYMMDD'/'YYYY-MM-DD', got {value!r}")


_PARAM_RE = re.compile(r"^[A-Z0-9_]+$")


def _to_year(value, name: str) -> int:
    """Strict year: integers (or digit strings) only, so 2020.9 is rejected, not truncated."""
    if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
        raise PowerValidationError(f"{name}: expected a whole year, got {value!r}")
    try:
        year = int(str(value).strip()) if isinstance(value, str) else int(value)
    except (TypeError, ValueError):
        raise PowerValidationError(f"{name}: expected a year such as 2020, got {value!r}") from None
    if year < 1900:
        raise PowerValidationError(f"{name}: year {year} is not valid")
    return year


def validate_request(latitude, longitude, parameters, start, end, temporal="daily", community="AG"):
    """Validate and normalise a request. Returns (lat, lon, params, start, end, temporal, community)
    with start/end as 'YYYYMMDD' (daily) or 'YYYY' (monthly) strings."""
    if temporal not in TEMPORALS:
        raise PowerValidationError(f"temporal must be one of {TEMPORALS}, got {temporal!r}")
    if community not in COMMUNITIES:
        raise PowerValidationError(f"community must be one of {COMMUNITIES}, got {community!r}")
    try:
        lat, lon = float(latitude), float(longitude)
    except (TypeError, ValueError):
        raise PowerValidationError("latitude and longitude must be numbers") from None
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise PowerValidationError("latitude and longitude must be finite numbers")
    if not (-90 <= lat <= 90):
        raise PowerValidationError(f"latitude {lat} is outside -90..90")
    if not (-180 <= lon <= 180):
        raise PowerValidationError(f"longitude {lon} is outside -180..180")

    if isinstance(parameters, str):
        parameters = [p for p in parameters.split(",")]
    params = [str(p).strip().upper() for p in parameters if str(p).strip()]
    if not params:
        raise PowerValidationError("at least one parameter is required")
    if len(set(params)) != len(params):
        raise PowerValidationError("duplicate parameters in request")
    bad_names = [p for p in params if not _PARAM_RE.match(p)]
    if bad_names:
        raise PowerValidationError(f"invalid parameter name(s): {bad_names}")
    if len(params) > MAX_PARAMS_PER_REQUEST:
        raise PowerValidationError(f"at most {MAX_PARAMS_PER_REQUEST} parameters per request")

    if temporal == "daily":
        s, e = _to_date(start, "start"), _to_date(end, "end")
        if s > e:
            raise PowerValidationError("start date is after end date")
        if e > datetime.now(UTC).date():
            raise PowerValidationError("end date is in the future")
        return lat, lon, params, s.strftime("%Y%m%d"), e.strftime("%Y%m%d"), temporal, community

    sy, ey = _to_year(start, "start"), _to_year(end, "end")
    if sy > ey:
        raise PowerValidationError("start year is after end year")
    if ey > datetime.now(UTC).year:
        raise PowerValidationError("end year is in the future")
    return lat, lon, params, str(sy), str(ey), temporal, community


def build_request(latitude, longitude, parameters, start, end, temporal="daily", community="AG"):
    lat, lon, params, s, e, temporal, community = validate_request(
        latitude, longitude, parameters, start, end, temporal, community
    )
    url = f"{config.POWER_BASE_URL}/{temporal}/point"
    query = {
        "parameters": ",".join(params),
        "community": community,
        "longitude": lon,
        "latitude": lat,
        "start": s,
        "end": e,
        "format": "JSON",
    }
    return url, query


def parse_response(payload: dict, temporal: str, community: str = "AG") -> PowerResult:
    if temporal not in TEMPORALS:
        raise PowerValidationError(f"temporal must be one of {TEMPORALS}, got {temporal!r}")
    props = payload.get("properties") if isinstance(payload, dict) else None
    if not props or "parameter" not in props or not props["parameter"]:
        raise PowerAPIError("unexpected response: no 'properties.parameter' block")

    block = props["parameter"]
    if len({frozenset(v) for v in block.values()}) != 1:
        raise PowerAPIError("unexpected response: parameters have different date keys")

    warnings: list[str] = []
    columns = {}
    for code, values in block.items():
        raw = pd.Series(values)
        num = pd.to_numeric(raw, errors="coerce")
        bad = int((num.isna() & raw.notna()).sum())
        if bad:
            warnings.append(f"{code}: {bad} non-numeric value(s) in the response treated as missing")
        columns[code] = num
    frame = pd.DataFrame(columns)
    frame.index = frame.index.astype(str)

    nodata_counts: dict[str, int] = {}
    for col in frame.columns:
        mask = frame[col].to_numpy(dtype=float) == config.POWER_NODATA
        nodata_counts[col] = int(mask.sum())
        frame.loc[mask, col] = np.nan

    coords = (payload.get("geometry") or {}).get("coordinates") or []
    lon = float(coords[0]) if len(coords) > 0 else float("nan")
    lat = float(coords[1]) if len(coords) > 1 else float("nan")
    elev = float(coords[2]) if len(coords) > 2 else None

    api_units = {k: v.get("units", "") for k, v in (payload.get("parameters") or {}).items()
                 if isinstance(v, dict)}
    units = {c: api_units.get(c) or (PARAMETERS[c].default_units if c in PARAMETERS else "")
             for c in frame.columns}

    if temporal == "daily":
        try:
            frame.index = pd.to_datetime(frame.index, format="%Y%m%d")
        except ValueError as exc:
            raise PowerAPIError(f"unparseable daily date keys: {exc}") from None
        frame.index.name = "date"
        data = frame.sort_index().reset_index()
        annual = pd.DataFrame(columns=["year", *frame.columns])
    else:
        if (frame.index.str.len() != 6).any():
            raise PowerAPIError("unexpected monthly date keys (expected YYYYMM)")
        try:
            years = frame.index.str[:4].astype(int)
            months = frame.index.str[4:].astype(int)
        except ValueError:
            raise PowerAPIError("unexpected monthly date keys (expected YYYYMM)") from None
        if ((months < 1) | (months > 13)).any():
            raise PowerAPIError("unexpected monthly date keys (month must be 01-13)")
        is_annual = months == 13
        monthly = frame[~is_annual].copy()
        monthly.index = pd.to_datetime(
            [f"{y:04d}-{m:02d}-01" for y, m in zip(years[~is_annual], months[~is_annual], strict=True)]
        )
        monthly.index.name = "date"
        data = monthly.sort_index().reset_index()
        annual = frame[is_annual].copy()
        annual.insert(0, "year", years[is_annual])
        annual = annual.sort_values("year").reset_index(drop=True)

    return PowerResult(
        data=data, annual=annual, units=units, nodata_counts=nodata_counts,
        latitude=lat, longitude=lon, elevation=elev, temporal=temporal, community=community,
        fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
        extra={"warnings": warnings},
    )


def _api_message(resp) -> str:
    try:
        body = resp.json()
        msgs = body.get("messages") if isinstance(body, dict) else None
        if msgs:
            return "; ".join(str(m) for m in msgs)
    except (ValueError, AttributeError):
        return (getattr(resp, "text", "") or "")[:300]
    return (getattr(resp, "text", "") or "")[:300]


def fetch_point(latitude, longitude, parameters, start, end, temporal="daily", community="AG",
                *, session=None, retries=3, timeout=60, backoff=2.0, sleep=time.sleep) -> PowerResult:
    """Download one point from NASA POWER. Retries on network errors, HTTP 429 and 5xx."""
    if not isinstance(retries, int) or retries < 1:
        raise PowerValidationError("retries must be an integer >= 1")
    if not timeout or timeout <= 0:
        raise PowerValidationError("timeout must be > 0")
    if backoff < 1:
        raise PowerValidationError("backoff must be >= 1")
    url, query = build_request(latitude, longitude, parameters, start, end, temporal, community)
    session = session or requests.Session()
    headers = {"User-Agent": config.USER_AGENT}
    last_error = "unknown error"

    for attempt in range(1, retries + 1):
        wait = backoff ** attempt
        try:
            resp = session.get(url, params=query, timeout=timeout, headers=headers)
        except requests.RequestException as exc:
            last_error = f"network error: {exc}"
        else:
            if resp.status_code == 200:
                try:
                    payload = resp.json()
                except ValueError:
                    raise PowerAPIError("response is not valid JSON") from None
                return parse_response(payload, temporal, community)
            if resp.status_code == 429 or resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}: {_api_message(resp)}"
                retry_after = (getattr(resp, "headers", None) or {}).get("Retry-After")
                if retry_after and str(retry_after).isdigit():
                    wait = max(wait, float(retry_after))
            else:
                raise PowerAPIError(f"HTTP {resp.status_code}: {_api_message(resp)}")
        if attempt < retries:
            sleep(wait)

    raise PowerAPIError(f"failed after {retries} attempts ({last_error})")
