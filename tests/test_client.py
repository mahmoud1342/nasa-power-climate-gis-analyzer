import math

import pytest
import requests
from conftest import FakeResp, FakeSession

from npcga.power.client import (
    PowerAPIError,
    PowerValidationError,
    build_request,
    fetch_point,
    parse_response,
    validate_request,
)


def test_validate_rejects_bad_input():
    with pytest.raises(PowerValidationError):
        validate_request(91, 0, ["T2M"], "20240101", "20240102")
    with pytest.raises(PowerValidationError):
        validate_request(0, 181, ["T2M"], "20240101", "20240102")
    with pytest.raises(PowerValidationError):
        validate_request(0, 0, [], "20240101", "20240102")
    with pytest.raises(PowerValidationError):
        validate_request(0, 0, ["T2M", "t2m"], "20240101", "20240102")
    with pytest.raises(PowerValidationError):
        validate_request(0, 0, ["T2M"], "20240103", "20240101")
    with pytest.raises(PowerValidationError):
        validate_request(0, 0, ["T2M"], "20240101", "20240102", temporal="hourly")
    with pytest.raises(PowerValidationError):
        validate_request(0, 0, ["T2M"], "20240101", "29990101")


def test_validate_normalises_dates_and_params():
    _, _, params, s, e, _, _ = validate_request(31.2, 29.92, "prectotcorr, t2m", "2024-01-01", "20240103")
    assert params == ["PRECTOTCORR", "T2M"] and s == "20240101" and e == "20240103"
    _, _, _, s, e, *_ = validate_request(31.2, 29.92, ["T2M"], 2020, "2022", temporal="monthly")
    assert (s, e) == ("2020", "2022")


def test_build_request_url_and_query():
    url, q = build_request(31.2, 29.92, ["T2M"], "20240101", "20240103")
    assert url.endswith("/daily/point")
    assert q["format"] == "JSON" and q["start"] == "20240101" and q["latitude"] == 31.2


def test_parse_daily_converts_nodata_and_counts(daily_payload):
    r = parse_response(daily_payload, "daily")
    assert list(r.data.columns) == ["date", "PRECTOTCORR", "T2M"]
    assert len(r.data) == 3
    assert math.isnan(r.data.loc[1, "PRECTOTCORR"]) and math.isnan(r.data.loc[2, "T2M"])
    assert r.data.loc[0, "PRECTOTCORR"] == 0.02
    assert r.nodata_counts == {"PRECTOTCORR": 1, "T2M": 1}
    assert r.units["PRECTOTCORR"] == "mm/day"
    assert (r.latitude, r.longitude, r.elevation) == (31.2, 29.92, 12.5)
    assert str(r.data["date"].iloc[0].date()) == "2024-01-01"


def test_parse_monthly_separates_annual(monthly_payload):
    r = parse_response(monthly_payload, "monthly")
    assert len(r.data) == 2 and list(r.annual["year"]) == [2024]
    assert r.annual.loc[0, "PRECTOTCORR"] == 0.6
    assert str(r.data["date"].iloc[1].date()) == "2024-02-01"


def test_parse_rejects_unexpected_payload():
    with pytest.raises(PowerAPIError):
        parse_response({"oops": 1}, "daily")


def test_fetch_retries_then_succeeds(daily_payload):
    sess = FakeSession([FakeResp(503, {"messages": ["busy"]}), requests.ConnectionError("x"),
                        FakeResp(200, daily_payload)])
    waits = []
    r = fetch_point(31.2, 29.92, ["PRECTOTCORR", "T2M"], "20240101", "20240103",
                    session=sess, sleep=waits.append)
    assert len(sess.calls) == 3 and len(waits) == 2 and len(r.data) == 3


def test_fetch_fails_after_retries():
    sess = FakeSession([FakeResp(500, {}) for _ in range(3)])
    with pytest.raises(PowerAPIError, match="failed after 3 attempts"):
        fetch_point(0, 0, ["T2M"], "20240101", "20240102", session=sess, sleep=lambda s: None)


def test_fetch_client_error_not_retried():
    sess = FakeSession([FakeResp(422, {"messages": ["bad parameter"]})])
    with pytest.raises(PowerAPIError, match="bad parameter"):
        fetch_point(0, 0, ["T2M"], "20240101", "20240102", session=sess, sleep=lambda s: None)
    assert len(sess.calls) == 1
