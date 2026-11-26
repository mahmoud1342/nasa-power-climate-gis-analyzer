import numpy as np
import pandas as pd
import pytest

from npcga.analysis import compare_locations
from npcga.export import compare_to_arabic


def make(fn, start="2021-01-01", end="2022-12-31", var="PRECTOTCORR"):
    d = pd.date_range(start, end)
    return pd.DataFrame({"date": d, var: [fn(x) for x in d]})


def base(d):                       # 1 mm/day, +1 in March 2021
    return 1.0 + (1.0 if (d.year == 2021 and d.month == 3) else 0.0)


A = make(base)
B = make(lambda d: 2 * base(d))            # exactly 2 x A
C = make(lambda d: 3 - base(d))            # mirror image of A


def test_summary_values_by_hand():
    r = compare_locations({"A": A, "B": B}, "PRECTOTCORR")
    a, b = r.summary.set_index("label").loc["A"], r.summary.set_index("label").loc["B"]
    # A: 2021 = 365 + 31 (extra March mm) = 396, 2022 = 365
    assert a.n_years == 2 and a["mean"] == pytest.approx((396 + 365) / 2) and a["max"] == 396 and a.max_year == 2021
    assert a["min"] == 365 and a.min_year == 2022 and a.peak_month == 3
    assert a["std"] == pytest.approx(np.std([396, 365], ddof=1))
    assert a.cv_pct == pytest.approx(a["std"] / a["mean"] * 100)
    assert b["mean"] == pytest.approx(2 * a["mean"]) and r.how == "sum"


def test_correlation_of_anomalies_perfect_and_mirrored():
    r = compare_locations({"A": A, "B": B, "C": C}, "PRECTOTCORR")
    c = r.correlation
    assert c.loc["A", "B"] == pytest.approx(1.0) and c.loc["A", "C"] == pytest.approx(-1.0)
    assert (np.diag(c) == 1.0).all() and c.loc["A", "B"] == c.loc["B", "A"]


def test_long_tables_shape_and_climatology():
    r = compare_locations({"A": A, "B": B}, "PRECTOTCORR")
    assert set(r.yearly.label) == {"A", "B"} and len(r.yearly) == 4
    clim = r.climatology.set_index(["label", "month"]).value
    assert len(r.climatology) == 24 and clim["A", 3] == pytest.approx((62 + 31) / 2)
    assert clim["B", 1] == pytest.approx(62.0)


def test_temperature_uses_mean_and_no_cv():
    t1, t2 = make(lambda d: 20.0, var="T2M"), make(lambda d: 25.0, var="T2M")
    r = compare_locations({"x": t1, "y": t2}, "T2M")
    s = r.summary.set_index("label")
    assert r.how == "mean" and s.loc["x", "mean"] == 20.0 and s.loc["y", "mean"] == 25.0
    assert np.isnan(s.loc["x", "cv_pct"])          # CV is meaningless for degrees C


def test_needs_two_locations_and_short_series_gives_nan_correlation():
    with pytest.raises(ValueError, match="at least two"):
        compare_locations({"A": A}, "PRECTOTCORR")
    short_a, short_b = make(base, end="2021-05-31"), make(base, end="2021-05-31")
    r = compare_locations({"a": short_a, "b": short_b}, "PRECTOTCORR")
    assert np.isnan(r.correlation.loc["a", "b"])    # only 5 months: below the minimum


def test_missing_variable_is_an_error():
    with pytest.raises(KeyError):
        compare_locations({"A": A, "B": B}, "T2M")


def test_arabic_summary():
    r = compare_locations({"A": A, "B": B}, "PRECTOTCORR")
    ar = compare_to_arabic(r.summary, r.how, "mm/day")
    assert ar.columns[0] == "نوع التحليل" and "الموقع" in ar.columns
    assert ar.loc[ar["الموقع"] == "A", "الشهر الأعلى مناخيًا"].iloc[0] == "مارس"
    assert not [c for c in ar.columns if c.isascii()]
