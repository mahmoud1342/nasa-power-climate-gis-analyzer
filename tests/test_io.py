import numpy as np
import pandas as pd
import pytest

from npcga.cli_folder import main as folder_main
from npcga.io import (
    PowerFileError,
    dates_from_columns,
    load_power_folder,
    parse_dates_auto,
    rainfall_by_location,
    read_power_csv,
    read_timeseries_csv,
)

HEADER = """-BEGIN HEADER-
NASA/POWER Source Native Resolution Daily Data
Dates (month/day/year): 01/01/2020 through 12/31/2021 in LST
Location: latitude {lat}  longitude {lon}
elevation from MERRA-2: Average for 0.5 x 0.625 degree lat/lon region = 52.99 meters
The value for missing source data that cannot be computed or is outside of the sources availability range: -999
parameter(s):
PRECTOTCORR    MERRA-2 Precipitation Corrected (mm/day)
-END HEADER-
YEAR,DOY,PRECTOTCORR
"""


def power_text(lat=26.0, lon=85.625, value=1.0, years=(2020, 2021), nodata_rows=()):
    rows = []
    for y in years:
        n = 366 if y % 4 == 0 else 365
        for d in range(1, n + 1):
            v = -999 if (y, d) in nodata_rows else value
            rows.append(f"{y},{d},{v}")
    return HEADER.format(lat=lat, lon=lon) + "\n".join(rows) + "\n"


def test_parse_dates_iso_and_compact():
    d, fmt = parse_dates_auto(["2024-01-31", "2024-02-01"])
    assert fmt == "%Y-%m-%d" and d[1] == pd.Timestamp("2024-02-01")
    d, fmt = parse_dates_auto([20240131, 20240201])
    assert fmt == "%Y%m%d" and d[0] == pd.Timestamp("2024-01-31")


def test_parse_dates_ambiguity_is_never_guessed():
    with pytest.raises(ValueError, match="ambiguous"):
        parse_dates_auto(["01/02/2024", "03/04/2024"])
    d, _ = parse_dates_auto(["01/02/2024", "03/04/2024"], dayfirst=True)
    assert d[0] == pd.Timestamp("2024-02-01")
    d, _ = parse_dates_auto(["01/02/2024", "03/04/2024"], dayfirst=False)
    assert d[0] == pd.Timestamp("2024-01-02")
    d, fmt = parse_dates_auto(["25/02/2024", "03/04/2024"])   # 25 can only be a day
    assert fmt == "%d/%m/%Y" and d[0] == pd.Timestamp("2024-02-25")


def test_parse_dates_errors_and_blanks():
    with pytest.raises(ValueError, match="unrecognised"):
        parse_dates_auto(["not a date"])
    d, _ = parse_dates_auto(["2024-01-01", "", None])
    assert d[0] == pd.Timestamp("2024-01-01") and d.isna().sum() == 2


def test_dates_from_year_doy_validates_leap_day():
    ok = pd.DataFrame({"YEAR": [2020, 2020], "DOY": [1, 366]})
    d, used = dates_from_columns(ok)
    assert d[1] == pd.Timestamp("2020-12-31") and used == ["YEAR", "DOY"]
    bad = pd.DataFrame({"YEAR": [2021], "DOY": [366]})
    with pytest.raises(ValueError, match="invalid YEAR/DOY"):
        dates_from_columns(bad)


def test_dates_from_year_month_day():
    df = pd.DataFrame({"YEAR": [2024, 2024], "MO": [2, 3], "DY": [29, 1]})
    d, used = dates_from_columns(df)
    assert d[0] == pd.Timestamp("2024-02-29") and len(used) == 3


def test_read_power_csv_matches_real_file_layout(tmp_path):
    f = tmp_path / "POWER_daily_lat26.0_lon85.625.csv"
    f.write_text(power_text(nodata_rows={(2020, 3)}), encoding="utf-8")
    r = read_power_csv(f)
    assert (r.latitude, r.longitude, r.elevation) == (26.0, 85.625, 52.99)
    assert r.units == {"PRECTOTCORR": "mm/day"}
    assert len(r.data) == 731 and r.data.date.iloc[0] == pd.Timestamp("2020-01-01")
    assert r.data.date.iloc[-1] == pd.Timestamp("2021-12-31")
    assert np.isnan(r.data.PRECTOTCORR.iloc[2]) and r.nodata_counts == {"PRECTOTCORR": 1}
    assert r.extra["warnings"] == []


def test_read_power_csv_warns_on_filename_mismatch_and_uses_filename_fallback(tmp_path):
    f = tmp_path / "POWER_daily_lat10.0_lon20.0.csv"
    f.write_text(power_text(lat=26.0, lon=85.625), encoding="utf-8")
    assert "differ from header" in read_power_csv(f).extra["warnings"][0]
    g = tmp_path / "POWER_daily_lat10.0_lon20.0_b.csv"
    g.write_text(power_text().replace("Location: latitude 26.0  longitude 85.625", "no location here"),
                 encoding="utf-8")
    r = read_power_csv(g)
    assert (r.latitude, r.longitude) == (10.0, 20.0) and "file name" in r.extra["warnings"][0]


def test_read_power_csv_rejects_other_files(tmp_path):
    f = tmp_path / "plain.csv"
    f.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(PowerFileError, match="not a NASA POWER"):
        read_power_csv(f)
    m = tmp_path / "monthly.csv"
    m.write_text(HEADER.format(lat=1, lon=2).replace("YEAR,DOY,PRECTOTCORR\n", "") +
                 "PARAMETER,YEAR,JAN,FEB,ANN\nPRECTOTCORR,2020,1,2,3\n", encoding="utf-8")
    with pytest.raises(PowerFileError, match="monthly"):
        read_power_csv(m)


def test_read_timeseries_csv_generic(tmp_path):
    f = tmp_path / "g.csv"
    f.write_text("Date;rain\n2024-01-01;1.5\n2024-01-02;2.5\n", encoding="utf-8")
    df = read_timeseries_csv(f)
    assert list(df.columns) == ["date", "rain"] and df.rain.sum() == 4.0
    h = tmp_path / "h.csv"
    h.write_text("day,rain\n01/02/2024,1\n03/04/2024,2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_timeseries_csv(h, date_col="day")
    assert read_timeseries_csv(h, date_col="day", dayfirst=True).date[0] == pd.Timestamp("2024-02-01")


def make_folder(tmp_path):
    (tmp_path / "POWER_daily_lat26.0_lon80.0.csv").write_text(power_text(26.0, 80.0, 1.0), encoding="utf-8")
    (tmp_path / "POWER_daily_lat26.0_lon80.625.csv").write_text(
        power_text(26.0, 80.625, 2.0, nodata_rows={(2020, 5)}), encoding="utf-8")
    (tmp_path / "POWER_daily_lat26.5_lon80.0.csv").write_text("garbage\n", encoding="utf-8")
    return tmp_path


def test_folder_loader_reports_failures_and_locations(tmp_path):
    fr = load_power_folder(make_folder(tmp_path))
    assert len(fr.results) == 2 and len(fr.failures) == 1
    assert fr.failures[0]["file"].endswith("lat26.5_lon80.0.csv") and "not a NASA POWER" in fr.failures[0]["reason"]
    loc = fr.locations
    assert list(loc.n_records) == [731, 731] and loc.nodata_values.tolist() == [0, 1]
    assert loc.qc_errors.sum() == 0
    with pytest.raises(FileNotFoundError):
        load_power_folder(tmp_path, "*.nothing")


def test_rainfall_by_location_values(tmp_path):
    fr = load_power_folder(make_folder(tmp_path))
    pts = rainfall_by_location(fr)
    a, b = pts.iloc[0], pts.iloc[1]
    assert a.n_complete_years == 2 and a.mean_annual_rain_mm == pytest.approx((366 + 365) / 2)  # 1 mm/day
    assert b.n_complete_years == 2   # one missing day (99.7% valid) still passes the 90% rule
    assert b.mean_annual_rain_mm == pytest.approx((365 * 2 + 365 * 2) / 2)  # 2020: 365 valid days x2; 2021: 365 x2
    assert a.rx1day_max_mm == 1.0


def test_duplicate_locations_flagged(tmp_path):
    (tmp_path / "a_lat1.0_lon2.0.csv").write_text(power_text(1.0, 2.0), encoding="utf-8")
    (tmp_path / "b_lat1.0_lon2.0.csv").write_text(power_text(1.0, 2.0), encoding="utf-8")
    assert "DUPLICATE_POINTS" in load_power_folder(tmp_path).points_qc.codes()


def test_folder_cli_writes_outputs(tmp_path):
    src = make_folder(tmp_path / "raw") if (tmp_path / "raw").mkdir() is None else None
    out = tmp_path / "out"
    assert folder_main(["--folder", str(src), "--out", str(out), "--name", "t"]) == 0
    names = {p.name for p in (out / "t").iterdir()}
    assert {"locations.csv", "points_mean_annual_rainfall.csv", "failed_files.csv", "folder_report.txt"} <= names
    pts = pd.read_csv(out / "t" / "points_mean_annual_rainfall.csv")
    assert list(pts.columns[:3]) == ["file", "latitude", "longitude"] and len(pts) == 2
