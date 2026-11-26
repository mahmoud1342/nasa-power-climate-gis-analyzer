"""Tests added after the external review (ChatGPT) - each one pins a verified fix."""
import numpy as np
import pandas as pd
import pytest

from npcga.analysis import annual_indices, mann_kendall
from npcga.io import PowerFileError, read_power_csv
from npcga.power.client import (
    PowerAPIError,
    PowerValidationError,
    fetch_point,
    parse_response,
    validate_request,
)
from npcga.qc import check_timeseries

HDR = """-BEGIN HEADER-
Location: latitude {lat}  longitude {lon}
parameter(s):
PRECTOTCORR    MERRA-2 Precipitation Corrected (mm/day)
-END HEADER-
YEAR,DOY,PRECTOTCORR
2020,1,1.0
2020,2,2.0
"""


def test_monthly_years_must_be_whole_and_sane():
    for bad in (2020.9, 0, -5, 1800, True, "abc", "2020.9"):
        with pytest.raises(PowerValidationError):
            validate_request(0, 0, ["T2M"], bad, 2022, temporal="monthly")
    assert validate_request(0, 0, ["T2M"], 2020.0, "2022", temporal="monthly")[3:5] == ("2020", "2022")


def test_nonfinite_coordinates_and_bad_parameter_names_rejected():
    for lat in (float("nan"), float("inf")):
        with pytest.raises(PowerValidationError):
            validate_request(lat, 0, ["T2M"], "20240101", "20240102")
    with pytest.raises(PowerValidationError, match="invalid parameter"):
        validate_request(0, 0, ["T2M;DROP"], "20240101", "20240102")
    # unknown-but-well-formed names are NOT blocked: POWER has hundreds of parameters
    assert validate_request(0, 0, ["SOME_NEW_PARAM"], "20240101", "20240102")[2] == ["SOME_NEW_PARAM"]


def test_fetch_argument_validation():
    for kw in ({"retries": 0}, {"timeout": 0}, {"backoff": 0.5}):
        with pytest.raises(PowerValidationError):
            fetch_point(0, 0, ["T2M"], "20240101", "20240102", **kw)


def test_parse_rejects_bad_structure():
    mp = {"properties": {"parameter": {"P": {"202414": 1.0}}}}
    with pytest.raises(PowerAPIError, match="month"):
        parse_response(mp, "monthly")
    mixed = {"properties": {"parameter": {"A": {"20240101": 1}, "B": {"20240102": 1}}}}
    with pytest.raises(PowerAPIError, match="different date keys"):
        parse_response(mixed, "daily")
    with pytest.raises(PowerValidationError):
        parse_response({"properties": {"parameter": {"A": {"20240101": 1}}}}, "hourly")


def test_parse_reports_non_numeric_values():
    payload = {"properties": {"parameter": {"A": {"20240101": 1.0, "20240102": "oops"}}}}
    r = parse_response(payload, "daily")
    assert np.isnan(r.data.A.iloc[1]) and "non-numeric" in r.extra["warnings"][0]


def test_qc_freq_infinite_and_near_sentinel():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=3), "PRECTOTCORR": [np.inf, -998.5, 1.0]})
    with pytest.raises(ValueError, match="freq"):
        check_timeseries(df, freq="W")
    rep = check_timeseries(df)
    assert "INFINITE_VALUES" in rep.codes()
    assert "NODATA_SENTINEL" not in rep.codes()          # -998.5 is not the sentinel
    assert "OUT_OF_RANGE" in rep.codes()


def test_power_csv_bad_coordinates_and_encoding(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text(HDR.format(lat=95.0, lon=10.0), encoding="utf-8")
    with pytest.raises(PowerFileError, match="out of range"):
        read_power_csv(f)
    g = tmp_path / "y.csv"
    g.write_bytes(HDR.format(lat=1.0, lon=2.0).replace("MERRA-2", "MERRA-\x00").encode("utf-8")
                  .replace(b"\x00", b"\xff"))
    assert any("undecodable" in w for w in read_power_csv(g).extra["warnings"])
    h = tmp_path / "z.csv"
    h.write_text(HDR.format(lat=1.0, lon=2.0).replace("2020,2,2.0", "2020,2,-999"), encoding="utf-8")
    assert read_power_csv(h).nodata_counts == {"PRECTOTCORR": 1}


def test_mann_kendall_input_validation_and_constant_series():
    with pytest.raises(ValueError, match="duplicate"):
        mann_kendall([1, 2, 3, 4], t=[2000, 2001, 2001, 2002])
    with pytest.raises(ValueError, match="NaN or infinite"):
        mann_kendall([1, 2, 3], t=[1, np.nan, 3])
    with pytest.raises(ValueError, match="alpha"):
        mann_kendall([1, 2, 3], alpha=1.5)
    with pytest.raises(ValueError, match="infinite"):
        mann_kendall([1, np.inf, 3])
    r = mann_kendall([5.0] * 12)                          # all equal -> var_s == 0, must not divide by 0
    assert r.var_s == 0 and r.z == 0 and r.p_value == 1 and r.trend == "no trend"


def test_cdd_spans_years_and_alt_does_not():
    dates = pd.date_range("2022-01-01", "2023-12-31", freq="D")
    rain = pd.Series(5.0, index=dates)
    rain["2022-12-21":"2023-01-10"] = 0.0                  # 11 dry days in 2022 + 10 in 2023 = 21
    df = pd.DataFrame({"date": dates, "PRECTOTCORR": rain.to_numpy()})
    idx = annual_indices(df).set_index("year")
    assert idx.loc[2023, "CDD"] == 21 and idx.loc[2022, "CDD"] == 0   # full spell credited to end year
    assert idx.loc[2022, "altCDD"] == 11 and idx.loc[2023, "altCDD"] == 10
    assert idx.loc[2023, "CWD"] == 355 and idx.loc[2023, "altCWD"] == 355
