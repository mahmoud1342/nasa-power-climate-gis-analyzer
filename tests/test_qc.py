import numpy as np
import pandas as pd

from npcga.qc import check_points, check_timeseries


def make(dates, **cols):
    return pd.DataFrame({"date": pd.to_datetime(dates), **cols})


def test_clean_series_has_no_errors():
    df = make(pd.date_range("2024-01-01", periods=5), PRECTOTCORR=[0, 1, 2, 0, 0.5])
    rep = check_timeseries(df)
    assert not rep.has_errors and not (rep.codes() - {"MISSING_VALUES"})


def test_detects_gaps_duplicates_and_missing():
    df = make(["2024-01-01", "2024-01-02", "2024-01-02", "2024-01-05"],
              PRECTOTCORR=[1.0, np.nan, 2.0, 3.0])
    rep = check_timeseries(df)
    assert {"DUPLICATE_DATES", "MISSING_DATES", "MISSING_VALUES"} <= rep.codes()
    gap = next(i for i in rep.issues if i.code == "MISSING_DATES")
    assert gap.count == 2  # Jan 3 and Jan 4
    assert rep.has_errors


def test_sentinel_and_range_reported_not_fixed():
    df = make(pd.date_range("2024-01-01", periods=3), PRECTOTCORR=[-999.0, -5.0, 1.0])
    before = df.copy()
    rep = check_timeseries(df)
    assert "NODATA_SENTINEL" in rep.codes() and "OUT_OF_RANGE" in rep.codes()
    pd.testing.assert_frame_equal(df, before)  # input untouched


def test_non_numeric_and_bad_dates():
    df = pd.DataFrame({"date": ["2024-01-01", "not-a-date"], "T2M": ["10", "abc"]})
    rep = check_timeseries(df)
    assert {"BAD_DATES", "NON_NUMERIC"} <= rep.codes()


def test_monthly_gap_detection():
    df = make(["2024-01-01", "2024-02-01", "2024-04-01"], T2M=[1, 2, 3])
    rep = check_timeseries(df, freq="MS")
    assert next(i for i in rep.issues if i.code == "MISSING_DATES").count == 1


def test_missing_date_column():
    assert "NO_DATE_COLUMN" in check_timeseries(pd.DataFrame({"x": [1]})).codes()


def test_points_checks():
    df = pd.DataFrame({"lat": [31.2, 95, None, 31.2], "lon": [29.9, 10, 5, 29.9]})
    rep = check_points(df)
    assert {"BAD_COORDS", "COORDS_OUT_OF_RANGE", "DUPLICATE_POINTS"} <= rep.codes()
    assert "NO_COORD_COLUMN" in check_points(pd.DataFrame({"a": [1]})).codes()
