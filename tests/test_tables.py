import io

import numpy as np
import pandas as pd
import pytest
from test_points import make_folder

from npcga.export import (
    COLUMNS,
    annual_table,
    arabic_points,
    build_points_table,
    daily_table,
    excel_workbook,
    fields_guide_ar,
    monthly_table,
    point_label,
    to_arabic,
    to_csv_bytes,
)
from npcga.export.tables import KIND_COL, POINT_AR
from npcga.io import load_power_folder


@pytest.fixture
def fr_pts(tmp_path):
    fr = load_power_folder(make_folder(tmp_path / "raw"))
    return fr, build_points_table(fr)


def test_every_point_column_has_a_unique_arabic_label():
    assert set(COLUMNS) <= set(POINT_AR)
    labels = [point_label(c) for c in COLUMNS]
    assert len(set(labels)) == len(labels) and all("[" in lab for lab in labels)
    assert point_label("mean_annual_rain_mm") == "[سنوي] متوسط المطر السنوي (مم/سنة)"
    assert point_label("M02").startswith("[شهري] متوسط مطر شهر فبراير")


def test_arabic_points_labels_values_and_keeps_original(fr_pts):
    _, pts = fr_pts
    before = pts.copy()
    ar = arabic_points(pts)
    assert list(ar.columns) == [point_label(c) for c in COLUMNS]
    assert set(ar["[جودة] حالة البيانات"]) <= {"سليم", "لا توجد سنة كاملة", "خطأ جودة", "موقع مكرر"}
    pd.testing.assert_frame_equal(pts, before)                       # input untouched
    assert np.allclose(ar["[سنوي] متوسط المطر السنوي (مم/سنة)"].dropna(), pts.mean_annual_rain_mm.dropna())


def test_annual_table_values_and_arabic_headers(fr_pts):
    fr, pts = fr_pts
    t = annual_table(fr, pts)
    rising = t[t.location_id == "N026.000_E0080.000"]
    assert rising.sort_values("year").total_mm.tolist() == [366.0, 730.0, 1095.0, 1460.0]
    ar = to_arabic(t, "annual")
    assert ar.columns[0] == KIND_COL and (ar[KIND_COL] == "سنوي").all()
    assert "إجمالي المطر السنوي (مم)" in ar.columns and "أطول فترة جفاف CDD (يوم)" in ar.columns
    assert not [c for c in ar.columns if c.isascii() and c not in ()]   # no English-only headers left


def test_monthly_table_values_and_arabic_headers(fr_pts):
    fr, pts = fr_pts
    t = monthly_table(fr, pts)
    one = t[(t.location_id == "N026.000_E0080.625") & (t.year == 2020) & (t.month == 1)].iloc[0]
    assert one.total_mm == 31.0 and one.month_name == "يناير"
    ar = to_arabic(t, "monthly")
    assert (ar[KIND_COL] == "شهري").all() and "إجمالي المطر الشهري (مم)" in ar.columns
    assert not [c for c in ar.columns if c.isascii()]


def test_daily_table_and_units(fr_pts):
    fr, pts = fr_pts
    d = daily_table(fr, pts)
    assert len(d) == sum(len(r.data) for r in fr.results)
    ar = to_arabic(d, "daily", fr.results[0].units)
    assert ar.columns[0] == KIND_COL and (ar[KIND_COL] == "يومي").all()
    assert "المطر المصحح (مم/يوم)" in ar.columns and "التاريخ" in ar.columns


def test_fields_guide_covers_all_fields():
    g = fields_guide_ar()
    assert len(g) == len(COLUMNS) and g["الاسم بالعربي"].str.len().min() > 2
    assert set(g["اسم الحقل في ملفات GIS"]) == set(COLUMNS)


def test_csv_bytes_open_in_excel_with_arabic():
    raw = to_csv_bytes(pd.DataFrame({"السنة": [2020], "قيمة": [1.5]}))
    assert raw.startswith(b"\xef\xbb\xbf") and "السنة".encode() in raw


def test_excel_workbook_sheets_rtl_and_headers(fr_pts):
    openpyxl = pytest.importorskip("openpyxl")
    fr, pts = fr_pts
    wb = openpyxl.load_workbook(io.BytesIO(excel_workbook(fr, pts)))
    assert wb.sheetnames == ["اقرأ أولاً", "ملخص المواقع", "تحليل سنوي", "تحليل شهري", "شرح الأعمدة"]
    ws = wb["تحليل سنوي"]
    assert ws.sheet_view.rightToLeft and ws["A1"].value == KIND_COL and ws["A2"].value == "سنوي"
    assert wb["ملخص المواقع"].max_row == 1 + len(pts)
    assert any("EPSG:4326" in str(c.value) for row in wb["اقرأ أولاً"].iter_rows() for c in row)
