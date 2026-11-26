import ast

import numpy as np
import pandas as pd
import pytest
from test_io import HEADER

from npcga.analysis import annual_indices
from npcga.cli_folder import main as folder_main
from npcga.export import (
    COLUMNS,
    FIELDS,
    SHP_NAMES,
    build_points_table,
    write_arcpy_script,
    write_points,
)
from npcga.io import load_power_folder


def text(lat, lon, per_year, max_rows=None):
    rows = []
    for y, v in per_year.items():
        for d in range(1, (366 if y % 4 == 0 else 365) + 1):
            rows.append(f"{y},{d},{v}")
    if max_rows:
        rows = rows[:max_rows]
    return HEADER.format(lat=lat, lon=lon) + "\n".join(rows) + "\n"


def make_folder(d):
    d.mkdir(exist_ok=True)
    rising = {2020: 1.0, 2021: 2.0, 2022: 3.0, 2023: 4.0}
    (d / "POWER_daily_lat26.0_lon80.0.csv").write_text(text(26.0, 80.0, rising), encoding="utf-8")
    (d / "POWER_daily_lat26.0_lon80.625.csv").write_text(text(26.0, 80.625, {2020: 1.0, 2021: 1.0}), encoding="utf-8")
    (d / "copy_of_lat26.0_lon80.0.csv").write_text(text(26.0, 80.0, rising), encoding="utf-8")
    (d / "POWER_daily_lat26.5_lon80.0.csv").write_text(text(26.5, 80.0, {2020: 1.0}, max_rows=100), encoding="utf-8")
    return d


def test_points_table_flags_and_values(tmp_path):
    t = build_points_table(load_power_folder(make_folder(tmp_path / "raw"))).set_index("file")
    assert list(t.columns) == [c for c in COLUMNS if c != "file"] and t.index.is_unique and len(t) == 4
    assert t.location_id.is_unique and t.location_id.str.startswith(("N026", "N026")).all()
    a, c = t.loc["POWER_daily_lat26.0_lon80.0.csv"], t.loc["copy_of_lat26.0_lon80.0.csv"]
    assert a.duplicate_location == c.duplicate_location == 1 and a.duplicate_group == c.duplicate_group == 1
    assert a.idw_valid == 0 and a.data_status == "duplicate_location"           # flagged, not removed
    assert a.mean_annual_rain_mm == pytest.approx((366 + 730 + 1095 + 1460) / 4)
    totals = np.array([366.0, 730.0, 1095.0, 1460.0])
    slopes = [(totals[j] - totals[i]) / (j - i) for i in range(4) for j in range(i + 1, 4)]
    assert a.sen_slope_mm_per_year == pytest.approx(np.median(slopes)) and a.mk_trend == "no trend"   # perfectly rising, but n=4 gives p~0.09 (not significant)
    assert a.mk_small_sample == 1 and a.M01 == pytest.approx((31 + 62 + 93 + 124) / 4)
    ok = t.loc["POWER_daily_lat26.0_lon80.625.csv"]
    assert ok.data_status == "ok" and ok.idw_valid == 1 and np.isnan(ok.sen_slope_mm_per_year)
    assert "fewer than 3" in ok.note
    short = t.loc["POWER_daily_lat26.5_lon80.0.csv"]
    assert short.data_status == "no_complete_years" and np.isnan(short.mean_annual_rain_mm)
    assert "no complete year" in short.note and short.idw_valid == 0 and short.missing_dates == 0


def test_shapefile_names_valid_and_documented():
    assert set(SHP_NAMES) == set(COLUMNS) and len(FIELDS) == len(COLUMNS)
    assert all(len(v) <= 10 for v in SHP_NAMES.values()) and len(set(SHP_NAMES.values())) == len(SHP_NAMES)


def test_write_points_all_formats(tmp_path):
    gpd = pytest.importorskip("geopandas")
    t = build_points_table(load_power_folder(make_folder(tmp_path / "raw")))
    res = write_points(t, tmp_path / "pts")
    assert not res["skipped"] and (tmp_path / "pts" / "points_fields.csv").exists()
    g = gpd.read_file(tmp_path / "pts" / "points.gpkg")
    assert len(g) == 4 and g.crs.to_epsg() == 4326 and g.geometry.iloc[0].x == t.longitude.iloc[0]
    s = gpd.read_file(tmp_path / "pts" / "points.shp")
    assert len(s) == 4 and s.crs.to_epsg() == 4326 and "rain_mean" in s.columns and "idw_valid" in s.columns
    assert len(gpd.read_file(tmp_path / "pts" / "points.geojson")) == 4
    csv = pd.read_csv(tmp_path / "pts" / "points.csv")
    assert list(csv.columns) == COLUMNS


def test_csv_only_when_gis_missing_is_not_an_error(tmp_path):
    t = build_points_table(load_power_folder(make_folder(tmp_path / "raw")))
    assert write_points(t, tmp_path / "o", formats=("csv",))["written"][0] == "points.csv"


def test_arcpy_script_is_valid_python(tmp_path):
    f = write_arcpy_script(tmp_path / "s.py", r"C:\data\points.csv")
    src = f.read_text(encoding="utf-8")
    ast.parse(src)
    assert "XYTableToPoint" in src and "idw_valid = 1" in src and "RUN_IDW = False" in src
    assert "NOT tested" in src and r"C:\\data\\points.csv" in src


def test_cli_folder_writes_points_and_removes_stale_failures(tmp_path):
    raw = make_folder(tmp_path / "raw")
    out = tmp_path / "out"
    (out / "x").mkdir(parents=True)
    (out / "x" / "failed_files.csv").write_text("stale", encoding="utf-8")
    assert folder_main(["--folder", str(raw), "--out", str(out), "--name", "x", "--formats", "csv"]) == 0
    assert not (out / "x" / "failed_files.csv").exists()
    names = {p.name for p in (out / "x" / "points").iterdir()}
    assert {"points.csv", "points_fields.csv", "points_issues.csv", "arcpy_import_points.py"} <= names
    issues = pd.read_csv(out / "x" / "points" / "points_issues.csv")
    assert len(issues) == 4   # 2 duplicates + 1 no_complete_years + 1 short note about trend
    assert "WGS 84" in (out / "x" / "folder_report.txt").read_text(encoding="utf-8")
    arabic = {p.name for p in (out / "x" / "arabic").iterdir()}
    assert {"ملخص_المواقع.csv", "تحليل_سنوي.csv", "تحليل_شهري.csv"} <= arabic
    ann = pd.read_csv(out / "x" / "arabic" / "تحليل_سنوي.csv")
    assert ann.columns[0] == "نوع التحليل" and (ann["نوع التحليل"] == "سنوي").all()


def test_rx5day_crosses_year_boundary_and_alt_does_not():
    dates = pd.date_range("2022-01-01", "2023-12-31", freq="D")
    rain = pd.Series(0.0, index=dates)
    rain["2022-12-30":"2023-01-03"] = 10.0                     # five wet days spanning the new year
    df = pd.DataFrame({"date": dates, "PRECTOTCORR": rain.to_numpy()})
    idx = annual_indices(df).set_index("year")
    assert idx.loc[2023, "Rx5day"] == 50.0 and idx.loc[2022, "Rx5day"] == 20.0
    assert idx.loc[2023, "altRx5day"] == 30.0 and idx.loc[2022, "altRx5day"] == 20.0
