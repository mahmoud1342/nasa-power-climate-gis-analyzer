"""Human-readable (Arabic) tables for download, each one stating its time scale.

Every table has a first column "نوع التحليل" (يومي / شهري / سنوي / ملخص لكل موقع) and every
column header is an Arabic name with its unit; in the per-location summary each header also
carries a tag [سنوي] / [شهري] / [يومي] / [الموقع] / [جودة]. Values are never modified, only
labelled. GIS files keep short English field names (safer for ArcGIS); `fields_guide_ar` explains them.
"""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd

from .. import __version__, config
from ..analysis import annual_indices, annual_totals, monthly_totals
from ..io.folder import FolderResult
from .points import FIELDS, MONTHS

MONTH_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
            "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
KIND_COL = "نوع التحليل"

# column -> (Arabic name, scale tag, Arabic unit)
POINT_AR: dict[str, tuple[str, str, str]] = {
    "location_id": ("معرّف الموقع", "الموقع", ""),
    "file": ("اسم الملف المصدر", "الموقع", ""),
    "latitude": ("خط العرض", "الموقع", "درجة"),
    "longitude": ("خط الطول", "الموقع", "درجة"),
    "elevation_m": ("الارتفاع", "الموقع", "م"),
    "n_records": ("عدد السجلات اليومية", "يومي - جودة", "سجل"),
    "start": ("تاريخ أول سجل", "يومي - جودة", ""),
    "end": ("تاريخ آخر سجل", "يومي - جودة", ""),
    "missing_dates": ("الأيام الناقصة", "يومي - جودة", "يوم"),
    "nodata_values": ("قيم -999 المحوّلة إلى Missing", "يومي - جودة", "قيمة"),
    "qc_errors": ("عدد أخطاء الجودة", "جودة", ""),
    "qc_warnings": ("عدد تحذيرات الجودة", "جودة", ""),
    "notes": ("ملاحظات القراءة", "جودة", ""),
    "mean_annual_rain_mm": ("متوسط المطر السنوي", "سنوي", "مم/سنة"),
    "std_annual_rain_mm": ("الانحراف المعياري للمطر السنوي", "سنوي", "مم"),
    "n_complete_years": ("عدد السنوات الكاملة المستخدمة", "سنوي", "سنة"),
    "rx1day_max_mm": ("أقصى مطر في يوم واحد خلال السجل", "يومي", "مم"),
    "mean_cdd_days": ("متوسط أطول فترة جفاف في السنة", "سنوي", "يوم"),
    "mean_r95p_mm": ("متوسط مطر الأيام شديدة الغزارة (R95p)", "سنوي", "مم/سنة"),
    "sen_slope_mm_per_year": ("ميل اتجاه المطر السنوي (سن)", "اتجاه سنوي", "مم/سنة لكل سنة"),
    "mk_p_value": ("قيمة p لاختبار مان-كيندال", "اتجاه سنوي", ""),
    "mk_trend": ("اتجاه المطر السنوي", "اتجاه سنوي", ""),
    "mk_small_sample": ("عينة صغيرة (أقل من 10 سنوات)؟ 1 = نعم", "اتجاه سنوي", ""),
    **{m: (f"متوسط مطر شهر {MONTH_AR[i]}", "شهري", "مم/شهر") for i, m in enumerate(MONTHS)},
    "duplicate_location": ("موقع مكرر؟ 1 = نعم", "جودة", ""),
    "duplicate_group": ("رقم مجموعة التكرار", "جودة", ""),
    "data_status": ("حالة البيانات", "جودة", ""),
    "idw_valid": ("صالح للاستيفاء؟ 1 = نعم", "جودة", ""),
    "note": ("ملاحظات / سبب عدم الحساب", "جودة", ""),
}
STATUS_AR = {"ok": "سليم", "no_complete_years": "لا توجد سنة كاملة", "qc_error": "خطأ جودة",
             "duplicate_location": "موقع مكرر"}
TREND_AR = {"increasing": "تزايد", "decreasing": "تناقص", "no trend": "لا يوجد اتجاه"}

ANNUAL_AR = {
    "location_id": "معرّف الموقع", "latitude": "خط العرض (درجة)", "longitude": "خط الطول (درجة)",
    "year": "السنة", "total_mm": "إجمالي المطر السنوي (مم)", "n_valid": "الأيام الصالحة في السنة",
    "n_expected": "عدد أيام السنة", "PRCPTOT": "مجموع مطر الأيام الرطبة PRCPTOT (مم)",
    "SDII": "متوسط شدة المطر في اليوم الرطب SDII (مم/يوم رطب)", "R10mm": "عدد أيام مطر 10 مم فأكثر (يوم)",
    "R20mm": "عدد أيام مطر 20 مم فأكثر (يوم)", "Rx1day": "أقصى مطر في يوم Rx1day (مم)",
    "Rx5day": "أقصى مطر في 5 أيام متتالية Rx5day (مم)",
    "altRx5day": "أقصى مطر في 5 أيام داخل السنة فقط (مم)",
    "CDD": "أطول فترة جفاف CDD (يوم)", "CWD": "أطول فترة مطر متواصل CWD (يوم)",
    "altCDD": "أطول فترة جفاف داخل السنة فقط (يوم)", "altCWD": "أطول فترة مطر داخل السنة فقط (يوم)",
    "R95p": "مطر الأيام شديدة الغزارة R95p (مم)", "R99p": "مطر الأيام الاستثنائية R99p (مم)",
}
MONTHLY_AR = {
    "location_id": "معرّف الموقع", "latitude": "خط العرض (درجة)", "longitude": "خط الطول (درجة)",
    "year": "السنة", "month": "رقم الشهر", "month_name": "اسم الشهر",
    "total_mm": "إجمالي المطر الشهري (مم)", "n_valid": "الأيام الصالحة في الشهر",
    "n_expected": "عدد أيام الشهر",
}
PARAM_AR = {
    "PRECTOTCORR": "المطر المصحح", "T2M": "درجة الحرارة على ارتفاع 2م", "T2M_MAX": "أعلى درجة حرارة على 2م",
    "T2M_MIN": "أدنى درجة حرارة على 2م", "RH2M": "الرطوبة النسبية على 2م", "WS2M": "سرعة الرياح على 2م",
    "PS": "الضغط السطحي", "ALLSKY_SFC_SW_DWN": "الإشعاع الشمسي السطحي",
}
_UNIT_AR = {"mm/day": "مم/يوم", "C": "°م", "m/s": "م/ث", "%": "%", "kPa": "kPa"}


def point_label(col: str) -> str:
    """Header for the per-location summary: '[تحليل] الاسم (الوحدة)'."""
    if col not in POINT_AR:
        return col
    name, tag, unit = POINT_AR[col]
    return f"[{tag}] {name}" + (f" ({unit})" if unit else "")


def arabic_points(points: pd.DataFrame) -> pd.DataFrame:
    """Per-location summary with Arabic headers and Arabic status/trend words (values unchanged)."""
    t = points.copy()
    t["data_status"] = t["data_status"].map(STATUS_AR).fillna(t["data_status"])
    t["mk_trend"] = t["mk_trend"].map(TREND_AR).fillna(t["mk_trend"])
    return t.rename(columns={c: point_label(c) for c in t.columns})


def label_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename any known column to its Arabic header (used for on-screen tables)."""
    return df.rename(columns={c: point_label(c) for c in df.columns})


def _ids(points: pd.DataFrame) -> dict:
    return dict(zip(points["file"], points["location_id"], strict=True))


def _head(res, ids) -> dict:
    f = res.extra.get("source_file")
    return {"location_id": ids.get(f), "latitude": res.latitude, "longitude": res.longitude}


def annual_table(fr: FolderResult, points: pd.DataFrame) -> pd.DataFrame:
    """One row per location and year: annual rainfall total + ETCCDI indices (raw English columns)."""
    ids, frames = _ids(points), []
    for res in fr.results:
        try:
            a = annual_totals(res.data)
            idx = annual_indices(res.data).drop(columns=["n_valid", "n_expected"])
        except (KeyError, ValueError):
            continue
        m = a.merge(idx, on="year", how="left")
        for i, (k, v) in enumerate(_head(res, ids).items()):
            m.insert(i, k, v)
        frames.append(m)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=list(ANNUAL_AR))


def monthly_table(fr: FolderResult, points: pd.DataFrame) -> pd.DataFrame:
    """One row per location, year and month: monthly rainfall total."""
    ids, frames = _ids(points), []
    for res in fr.results:
        try:
            m = monthly_totals(res.data).drop(columns=["date"])
        except (KeyError, ValueError):
            continue
        m.insert(2, "month_name", m["month"].map(lambda k: MONTH_AR[k - 1]))
        for i, (k, v) in enumerate(_head(res, ids).items()):
            m.insert(i, k, v)
        frames.append(m)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=list(MONTHLY_AR))


def daily_table(fr: FolderResult, points: pd.DataFrame) -> pd.DataFrame:
    """Every daily record of every location (large)."""
    ids, frames = _ids(points), []
    for res in fr.results:
        d = res.data.copy()
        for i, (k, v) in enumerate(_head(res, ids).items()):
            d.insert(i, k, v)
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


def to_arabic(df: pd.DataFrame, kind: str, units: dict[str, str] | None = None) -> pd.DataFrame:
    """Arabic headers + a first column "نوع التحليل". kind: annual | monthly | daily."""
    kinds = {"annual": ("سنوي", ANNUAL_AR), "monthly": ("شهري", MONTHLY_AR), "daily": ("يومي", None)}
    label, mapping = kinds[kind]
    if mapping is None:
        mapping = {"location_id": "معرّف الموقع", "latitude": "خط العرض (درجة)",
                   "longitude": "خط الطول (درجة)", "date": "التاريخ"}
        for code, unit in (units or {}).items():
            u = _UNIT_AR.get(unit, unit)
            mapping[code] = f"{PARAM_AR.get(code, code)}" + (f" ({u})" if u else "")
    out = df.rename(columns=mapping)
    out.insert(0, KIND_COL, label)
    return out


def compare_to_arabic(summary: pd.DataFrame, how: str, unit: str = "") -> pd.DataFrame:
    """Arabic version of the location-comparison summary (first column: نوع التحليل)."""
    kind = "إجمالي" if how == "sum" else "متوسط"
    u = f" ({_UNIT_AR.get(unit, unit)})" if unit else ""
    out = summary.copy()
    for col in ("peak_month", "low_month"):
        out[col] = out[col].map(lambda k: MONTH_AR[int(k) - 1] if pd.notna(k) else "")
    out = out.rename(columns={
        "label": "الموقع", "n_years": "عدد السنوات الكاملة", "mean": f"متوسط {kind} السنة{u}",
        "std": f"الانحراف المعياري{u}", "cv_pct": "معامل الاختلاف (%) - للمطر فقط",
        "min": f"أدنى قيمة سنوية{u}", "min_year": "سنة الأدنى", "max": f"أعلى قيمة سنوية{u}",
        "max_year": "سنة الأعلى", "peak_month": "الشهر الأعلى مناخيًا", "low_month": "الشهر الأدنى مناخيًا"})
    out.insert(0, KIND_COL, "مقارنة مواقع (سنوي + شهري)")
    return out


def fields_guide_ar() -> pd.DataFrame:
    """Explains every field of the GIS point files (English name, shapefile name, Arabic name, scale)."""
    rows = []
    for col, shp, unit, desc in FIELDS:
        name, tag, ar_unit = POINT_AR.get(col, (col, "", unit))
        rows.append((col, shp, name, tag, ar_unit, desc))
    return pd.DataFrame(rows, columns=["اسم الحقل في ملفات GIS", "اسم الحقل في Shapefile", "الاسم بالعربي",
                                       "نوع التحليل", "الوحدة", "الشرح (إنجليزي)"])


def info_table(fr: FolderResult, points: pd.DataFrame) -> pd.DataFrame:
    loc = fr.locations
    items = [
        ("التطبيق", f"{config.APP_NAME} - الإصدار {__version__}"),
        ("المطوّر", f"{config.DEVELOPER_AR} ({config.DEVELOPER})"),
        ("LinkedIn", config.LINKEDIN_URL),
        ("تاريخ إنشاء الملف", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("مصدر البيانات", "NASA POWER (https://power.larc.nasa.gov/) - منتج شبكي من الأقمار الصناعية وإعادة التحليل، وليس قياسات محطات"),
        ("عدد المواقع", len(points)),
        ("فترة البيانات اليومية", f"{loc.start.min()} إلى {loc.end.max()}" if len(loc) else ""),
        ("نظام الإحداثيات", "WGS 84 (EPSG:4326)"),
        ("القيم -999", "تُحوَّل إلى Missing ويُحسب عددها، ولا تُحذف أي بيانات"),
        ("السنة/الشهر الناقص", "لا يُحسب إلا إذا توفر 90% من أيامه على الأقل"),
        ("أوراق الملف", "ملخص المواقع (عدة مقاييس زمنية - الوسم بين [] في اسم العمود) / تحليل سنوي / تحليل شهري / شرح الأعمدة"),
        ("تنبيه", "اتجاهات Mann-Kendall تقريبية خاصة إذا كان عدد السنوات أقل من 10"),
    ]
    return pd.DataFrame(items, columns=["البند", "التفاصيل"])


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")  # utf-8-sig: Arabic opens correctly in Excel


def build_excel(sheets: dict[str, pd.DataFrame]) -> bytes:
    """One workbook, right-to-left sheets, bold frozen header row. Needs openpyxl."""
    try:
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise ImportError("openpyxl is required for Excel export (pip install openpyxl)") from exc
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in sheets.items():
            sheet = name[:31]
            df.to_excel(xw, sheet_name=sheet, index=False)
            ws = xw.sheets[sheet]
            ws.sheet_view.rightToLeft = True
            ws.freeze_panes = "A2"
            for i, col in enumerate(df.columns, 1):
                cell = ws.cell(row=1, column=i)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="0E7490")
                cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
                body = df[col].astype(str).str.len().max() if len(df) else 0
                ws.column_dimensions[get_column_letter(i)].width = min(48, max(14, body + 2, 18))
            ws.row_dimensions[1].height = 48
    return buf.getvalue()


def excel_workbook(fr: FolderResult, points: pd.DataFrame) -> bytes:
    return build_excel({
        "اقرأ أولاً": info_table(fr, points),
        "ملخص المواقع": arabic_points(points),
        "تحليل سنوي": to_arabic(annual_table(fr, points), "annual"),
        "تحليل شهري": to_arabic(monthly_table(fr, points), "monthly"),
        "شرح الأعمدة": fields_guide_ar(),
    })
