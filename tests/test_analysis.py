import numpy as np
import pandas as pd
import pytest

from npcga.analysis import (
    aggregate_series,
    annual_indices,
    annual_totals,
    anomalies,
    climate_summary,
    daily_series,
    describe,
    extreme_days,
    mann_kendall,
    monthly_climatology,
    monthly_totals,
    trend_table,
)


def daily_df(start, end, value=0.0, **overrides):
    dates = pd.date_range(start, end, freq="D")
    s = pd.Series(value, index=dates, dtype=float)
    for d, v in overrides.items():
        s[pd.Timestamp(d.replace("_", "-"))] = v
    return pd.DataFrame({"date": dates, "PRECTOTCORR": s.to_numpy()})


def test_daily_series_rejects_sentinel_and_duplicates():
    df = daily_df("2024-01-01", "2024-01-03")
    bad = df.copy(); bad.loc[1, "PRECTOTCORR"] = -999
    with pytest.raises(ValueError, match="NoData"):
        daily_series(bad, "PRECTOTCORR")
    dup = pd.concat([df, df.iloc[[0]]])
    with pytest.raises(ValueError, match="duplicate"):
        daily_series(dup, "PRECTOTCORR")


def test_daily_series_fills_gaps_with_nan():
    df = daily_df("2024-01-01", "2024-01-05").drop(index=[2])
    s = daily_series(df, "PRECTOTCORR")
    assert len(s) == 5 and np.isnan(s.iloc[2])


def test_monthly_total_and_completeness_rule():
    df = daily_df("2024-01-01", "2024-02-29", value=1.0)   # Jan 31 d, Feb 29 d (leap)
    df.loc[df["date"].between("2024-01-01", "2024-01-02"), "PRECTOTCORR"] = np.nan   # 2 missing
    df.loc[df["date"].between("2024-02-01", "2024-02-05"), "PRECTOTCORR"] = np.nan   # 5 missing
    m = monthly_totals(df)
    jan, feb = m.iloc[0], m.iloc[1]
    assert jan.total_mm == 29 and jan.n_valid == 29 and jan.n_expected == 31   # 93.5% >= 90%
    assert np.isnan(feb.total_mm) and feb.n_valid == 24 and feb.n_expected == 29  # 82.8% < 90%


def test_partial_year_is_nan_not_undercounted():
    df = daily_df("2023-07-01", "2024-12-31", value=1.0)
    a = annual_totals(df)
    assert np.isnan(a.loc[a.year == 2023, "total_mm"]).all()
    assert a.loc[a.year == 2024, "total_mm"].iloc[0] == 366


def test_etccdi_hand_computed_year():
    # 2023 (365 days) all dry except: Jan10=12, Jan11=3, Jan12=25, Jul1=0.9 (dry), Jul2=1.0 (wet)
    df = daily_df("2023-01-01", "2023-12-31", **{"2023_01_10": 12.0, "2023_01_11": 3.0,
                  "2023_01_12": 25.0, "2023_07_01": 0.9, "2023_07_02": 1.0})
    r = annual_indices(df).iloc[0]
    assert r.PRCPTOT == 41.0                 # 12+3+25+1 (0.9 mm day is not a wet day)
    assert r.SDII == pytest.approx(41 / 4)
    assert (r.R10mm, r.R20mm) == (2, 1)
    assert r.Rx1day == 25.0 and r.Rx5day == 40.0
    assert r.CWD == 3
    assert r.CDD == 182                      # Jul 3 .. Dec 31 is the longest dry spell
    # wet-day percentiles of [1,3,12,25]: p95 = 23.05, p99 = 24.61 -> only 25 mm exceeds both
    assert r.R95p == 25.0 and r.R99p == 25.0


def test_missing_day_breaks_dry_run():
    df = daily_df("2023-01-01", "2023-12-31")
    df.loc[df["date"] == "2023-06-01", "PRECTOTCORR"] = np.nan
    r = annual_indices(df).iloc[0]
    assert r.CDD == 213                      # Jun 2 .. Dec 31 (NaN day splits the 365-day dry year)


def test_climatology_and_anomalies():
    parts = [daily_df(f"{y}-01-01", f"{y}-12-31", value=v) for y, v in [(2020, 1.0), (2021, 2.0), (2022, 3.0)]]
    df = pd.concat(parts, ignore_index=True)
    ann = annual_totals(df)
    assert list(ann.total_mm) == [366.0, 730.0, 1095.0]
    an = anomalies(ann, "annual")
    mean = np.mean([366.0, 730.0, 1095.0])
    assert an.reference_mean_mm.iloc[0] == pytest.approx(mean)
    assert an.anomaly_mm.iloc[0] == pytest.approx(366 - mean)
    assert an.anomaly_pct.iloc[1] == pytest.approx(730 / mean * 100)
    clim = monthly_climatology(monthly_totals(df))
    assert len(clim) == 12 and clim.loc[0, "n_years"] == 3
    assert clim.loc[0, "mean_mm"] == pytest.approx((31 + 62 + 93) / 3)
    ref = anomalies(monthly_totals(df), "monthly", reference=(2020, 2020))
    assert ref.loc[ref.year == 2020, "anomaly_mm"].abs().max() == pytest.approx(0.0)


def test_extreme_days():
    df = daily_df("2023-01-01", "2023-12-31", **{"2023_03_01": 30.0, "2023_03_02": 2.0,
                  "2023_03_03": 5.0, "2023_03_04": 50.0})
    ex, thr = extreme_days(df, q=50)
    assert thr == pytest.approx(np.percentile([30, 2, 5, 50], 50))   # 17.5
    assert list(ex.precip_mm) == [50.0, 30.0]
    none, thr = extreme_days(daily_df("2023-01-01", "2023-01-10"))
    assert none.empty and np.isnan(thr)


def test_describe_and_climate_summary():
    df = daily_df("2024-01-01", "2024-12-31", value=2.0)
    df["T2M"] = 20.0
    d = describe(df, ["PRECTOTCORR"]).iloc[0]
    assert d["mean"] == 2.0 and d["std"] == 0.0 and d["missing"] == 0
    s = climate_summary(df, "Y", ["PRECTOTCORR", "T2M"])
    assert s.loc[0, "PRECTOTCORR"] == 732.0 and s.loc[0, "T2M"] == 20.0


def test_aggregate_validation():
    s = daily_series(daily_df("2024-01-01", "2024-01-31"), "PRECTOTCORR")
    with pytest.raises(ValueError):
        aggregate_series(s, "W")
    with pytest.raises(ValueError):
        aggregate_series(s, "M", how="max")


def test_mann_kendall_hand_check():
    r = mann_kendall([3, 1, 2])           # pairs: -1, -1, +1  -> S = -1
    assert r.s == -1 and r.z == 0 and r.p_value == 1 and r.trend == "no trend" and r.small_sample


def test_mann_kendall_clear_trend_and_slope():
    t = np.arange(2000, 2020)
    r = mann_kendall(0.5 * t + 100, t)
    assert r.s == 190 and r.trend == "increasing" and r.sen_slope == pytest.approx(0.5)
    d = mann_kendall(-2 * t, t)
    assert d.trend == "decreasing" and d.sen_slope == pytest.approx(-2)


def test_mann_kendall_ignores_nan_and_uses_t_spacing():
    t = np.array([2000, 2001, 2005, 2006, 2010])
    x = np.array([1.0, np.nan, 3.0, 4.0, 5.0])
    r = mann_kendall(x, t)
    assert r.n == 4 and r.sen_slope > 0


def test_mann_kendall_matches_pymannkendall():
    mk = pytest.importorskip("pymannkendall")
    rng = np.random.default_rng(42)
    for x in (rng.normal(size=30).cumsum(), np.round(rng.normal(size=40), 1), rng.integers(0, 5, 25)):
        ref = mk.original_test(x)
        mine = mann_kendall(x)
        assert mine.s == ref.s and mine.z == pytest.approx(ref.z) and mine.p_value == pytest.approx(ref.p)
        assert mine.sen_slope == pytest.approx(ref.slope) and mine.trend == ref.trend


def test_trend_table():
    df = pd.DataFrame({"year": np.arange(2000, 2015), "a": np.arange(15) * 1.0, "b": np.zeros(15)})
    t = trend_table(df, ["a", "b"])
    assert t.loc[t.variable == "a", "trend"].iloc[0] == "increasing"
    assert t.loc[t.variable == "b", "trend"].iloc[0] == "no trend"


def test_cli_writes_all_outputs(tmp_path):
    from npcga.cli import main
    from npcga.power.client import PowerResult

    rng = np.random.default_rng(1)
    dates = pd.date_range("2020-01-01", "2022-12-31", freq="D")
    rain = np.where(rng.random(len(dates)) < 0.2, rng.exponential(5, len(dates)), 0.0)
    data = pd.DataFrame({"date": dates, "PRECTOTCORR": rain,
                         "T2M": 20 + 8 * np.sin(np.arange(len(dates)) / 58.0)})

    def fake_provider(*args, **kwargs):
        return PowerResult(data=data, annual=pd.DataFrame(), units={"PRECTOTCORR": "mm/day", "T2M": "C"},
                           nodata_counts={"PRECTOTCORR": 0, "T2M": 0}, latitude=31.2, longitude=29.92,
                           elevation=10.0, temporal="daily", community="AG", fetched_at="t")

    out = tmp_path / "o"
    assert main(["--out", str(out), "--name", "x", "--start", "2020-01-01", "--end", "2022-12-31"],
                data_provider=fake_provider) == 0
    files = {p.name for p in (out / "x").iterdir()}
    assert {"rain_annual_totals.csv", "rain_annual_indices_ETCCDI.csv", "metadata.txt",
            "rain_trends_MannKendall_Sen.csv", "climate_monthly_summary.csv"} <= files
    tot = pd.read_csv(out / "x" / "rain_annual_totals.csv")
    assert tot.total_mm.iloc[0] == pytest.approx(data[data.date.dt.year == 2020].PRECTOTCORR.sum())
