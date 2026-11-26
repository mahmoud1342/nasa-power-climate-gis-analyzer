from __future__ import annotations

import io
import tempfile
import time
import zipfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from npcga import __version__, config
from npcga.analysis import compare_locations, describe, variable_profile
from npcga.export import (
    annual_table,
    arabic_points,
    build_points_table,
    compare_to_arabic,
    daily_table,
    excel_workbook,
    fields_guide_ar,
    label_columns,
    monthly_table,
    to_arabic,
    to_csv_bytes,
    write_arcpy_script,
    write_points,
)
from npcga.io import extract_uploads, load_power_folder

_LINK = config.linkedin_href()
_DEV_CHIP = (f'<a class="chip" href="{_LINK}" target="_blank" style="color:#fff;text-decoration:none">'
             f'👤 تطوير: {config.DEVELOPER_AR}</a>')

st.set_page_config(page_title="NASA POWER | محلل المناخ وGIS", page_icon="🌦️", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
html, body, [class*="css"], .stMarkdown, button, input, label, textarea {
  font-family: 'Cairo','Segoe UI',Tahoma,sans-serif !important; }
.block-container {padding-top: 1.2rem; max-width: 1380px;}
.stMarkdown, .stCaption, [data-testid="stWidgetLabel"], [data-testid="stAlert"] {direction: rtl; text-align: right;}
.hero {background: linear-gradient(120deg,#0b3954 0%,#0e7490 60%,#14b8a6 120%); color:#fff; border-radius:22px;
  padding:30px 36px; margin-bottom:18px; box-shadow:0 10px 30px rgba(11,57,84,.25);}
.hero h1 {font-size:32px; font-weight:800; margin:0 0 6px 0; letter-spacing:.2px;}
.hero p {margin:0; font-size:16px; color:#e0f4f7;}
.chips {margin-top:14px;} .chip {display:inline-block; background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.25);
  border-radius:999px; padding:4px 14px; font-size:13px; margin-left:8px;}
.steps {display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:6px 0 18px 0;}
.step {background:#fff; border:1px solid #d9e6ee; border-radius:16px; padding:14px 18px; display:flex; gap:14px;
  align-items:center; box-shadow:0 2px 10px rgba(11,57,84,.06);}
.step .n {background:linear-gradient(135deg,#0e7490,#14b8a6); color:#fff; min-width:44px; height:44px; border-radius:12px;
  display:flex; align-items:center; justify-content:center; font-weight:800; font-size:18px;}
.step b {color:#0f2a3d; font-size:16px; display:block;} .step span {color:#5b7083; font-size:13px;}
.sec {font-size:20px; font-weight:800; color:#0b3954; margin:6px 0 8px 0; border-right:5px solid #14b8a6; padding-right:10px;}
.card {background:#fff; border:1px solid #d9e6ee; border-radius:16px; padding:16px 18px; margin-bottom:12px;
  box-shadow:0 2px 10px rgba(11,57,84,.05);}
.card h4 {margin:0 0 4px 0; color:#0b3954; font-size:17px;} .card p {margin:0 0 10px 0; color:#5b7083; font-size:13.5px;}
.tag {display:inline-block; border-radius:8px; padding:2px 10px; font-size:12px; font-weight:700; margin-left:6px;}
.t-y {background:#dff5f1; color:#0b6b5c;} .t-m {background:#e3eefc; color:#1d4f9c;}
.t-d {background:#fdeccf; color:#8a5a0b;} .t-s {background:#ece8fb; color:#4b3d9c;}
div[data-testid="stMetric"] {background:#fff; border:1px solid #d9e6ee; border-radius:14px; padding:14px 16px;
  box-shadow:0 2px 10px rgba(11,57,84,.05);}
button[data-baseweb="tab"] {font-weight:700; font-size:16px;}
.stButton>button, .stDownloadButton>button {border-radius:12px; font-weight:700; padding:.55rem 1rem;}
</style>
<div class="hero" dir="rtl">
  <h1>NASA POWER Climate & GIS Analyzer</h1>
  <p>ارفع ملفات NASA POWER ← حلّل المطر والمناخ ← نزّل جداول عربية واضحة ونقاط جاهزة لـ ArcGIS Pro</p>
  <div class="chips"><span class="chip">🌧️ تحليل يومي وشهري وسنوي</span><span class="chip">📍 WGS 84</span>
  <span class="chip">🔒 الملفات تُعالج على جهازك</span> __DEV__</div>
</div>
<div class="steps" dir="rtl">
  <div class="step"><div class="n">1</div><div><b>ارفع الملفات</b><span>مجلد أو ZIP أو عدة ملفات CSV</span></div></div>
  <div class="step"><div class="n">2</div><div><b>حلّل</b><span>فحص الجودة والمطر والاتجاهات</span></div></div>
  <div class="step"><div class="n">3</div><div><b>نزّل</b><span>Excel عربي أو ملفات ArcGIS</span></div></div>
</div>
""".replace("__DEV__", _DEV_CHIP), unsafe_allow_html=True)

st.markdown('<div class="sec">١ · إدخال البيانات</div>', unsafe_allow_html=True)
upload = st.file_uploader(
    "اختر مجلد ملفات NASA POWER أو ملف ZIP أو عدة ملفات CSV", type=["csv", "zip"],
    accept_multiple_files="directory",
    help="ملفات NASA POWER اليومية التي تحتوي على ترويسة -BEGIN HEADER- و-END HEADER-.")
st.caption("الملفات غير المقروءة تظهر في تقرير أخطاء ولا تُحذف بصمت. القيم -999 تتحول إلى Missing ويُحسب عددها. "
           "جدول النقاط يعتمد على المطر المصحح PRECTOTCORR (مم/يوم).")


def build_zip(points: pd.DataFrame) -> tuple[bytes, list[str]]:
    """GIS formats + English and Arabic field guides + ArcPy script, in one ZIP."""
    with tempfile.TemporaryDirectory(prefix="npcga_pts_") as d:
        out = Path(d) / "points"
        res = write_points(points, out)
        write_arcpy_script(out / "arcpy_import_points.py", "points.csv")
        issues = points[(points.data_status != "ok") | (points.note != "") | (points.qc_warnings > 0)]
        issues[["location_id", "file", "data_status", "qc_errors", "qc_warnings", "duplicate_group", "note"]].to_csv(
            out / "points_issues.csv", index=False, encoding="utf-8-sig")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(out.iterdir()):
                z.write(f, f.name)
    return buf.getvalue(), res["skipped"]



@st.cache_data(show_spinner=False, max_entries=8)
def _compare_cached(token, labels, var, _fr, _items):
    """Heavy comparison, cached per analysis run + selection (underscore args are not hashed)."""
    return compare_locations(_items, var)


if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False
if st.button("🔎 حلّل الملفات", type="primary", disabled=not upload, width="stretch"):
    st.session_state.analysis_done = False
    st.session_state.pop("daily_csv", None)
    with st.spinner("جارٍ قراءة الملفات وفحصها وحساب المؤشرات..."):
        try:
            with tempfile.TemporaryDirectory(prefix="npcga_") as tmp:
                root = Path(tmp)
                n = extract_uploads([(up.name, up.getvalue()) for up in upload], root)
                if n == 0:
                    raise ValueError("لم يتم العثور على ملفات CSV صالحة داخل المدخلات.")
                fr = load_power_folder(root)
            if not fr.results:
                raise ValueError("لم ينجح النظام في قراءة أي ملف. راجع تنسيق ملفات NASA POWER.")
            pts = build_points_table(fr)
            zip_bytes, zip_msgs = build_zip(pts)
            annual, monthly = annual_table(fr, pts), monthly_table(fr, pts)
            try:
                excel = excel_workbook(fr, pts)
            except ImportError:
                excel = None
            st.session_state.update(
                fr=fr, points=pts, zip_bytes=zip_bytes, zip_msgs=zip_msgs, excel=excel,
                points_ar=to_csv_bytes(arabic_points(pts)),
                annual_ar=to_csv_bytes(to_arabic(annual, "annual")),
                monthly_ar=to_csv_bytes(to_arabic(monthly, "monthly")),
                analysis_done=True, token=time.time())
            st.success(f"اكتمل التحليل: تمت قراءة {len(fr.results)} ملفًا بنجاح من أصل {n} ملف.")
        except Exception as e:  # noqa: BLE001 - show any problem to the user instead of a stack trace
            st.error(f"تعذر إكمال التحليل: {e}")

if st.session_state.analysis_done:
    fr = st.session_state.fr
    points = st.session_state.points
    st.markdown('<div class="sec">٢ · النتائج</div>', unsafe_allow_html=True)
    tab_sum, tab_ts, tab_pts, tab_dl = st.tabs(["📊 الملخص وجودة البيانات", "📈 التحليل الزمني", "📍 جدول النقاط", "⬇️ التنزيلات"])

    with tab_sum:
        x, y, z, w = st.columns(4)
        x.metric("المواقع المقروءة", len(fr.results))
        y.metric("السجلات اليومية", f"{int(fr.locations.n_records.sum()):,}")
        z.metric("ملفات بها مشاكل", len(fr.failures))
        w.metric("قيم NoData (-999)", int(fr.locations.nodata_values.sum()))
        st.markdown("**فحص كل موقع**")
        st.dataframe(label_columns(fr.locations), width="stretch", hide_index=True)
        if fr.failures:
            st.warning("بعض الملفات لم تُقرأ؛ لم يتم تجاهلها دون توضيح.")
            st.dataframe(pd.DataFrame(fr.failures).rename(columns={"file": "الملف", "reason": "السبب"}),
                         width="stretch", hide_index=True)

    with tab_ts:
        common = sorted(set.intersection(*(set(r.data.columns) for r in fr.results)) - {"date"})
        if common:
            default = common.index("PRECTOTCORR") if "PRECTOTCORR" in common else 0
            c1, c2 = st.columns(2)
            chosen = c1.selectbox("اختر متغيرًا لعرض التحليل الزمني", common, index=default)
            names = [f"{r.extra.get('source_file', 'site')} | {r.latitude:.3f}, {r.longitude:.3f}" for r in fr.results]
            selected = c2.selectbox("الموقع", range(len(names)), format_func=lambda i: names[i])
            res = fr.results[selected]
            yearly, clim, how = variable_profile(res.data, chosen)
            unit = res.units.get(chosen, "")
            kind = "الإجمالي" if how == "sum" else "المتوسط"
            p1, p2 = st.columns(2)
            with p1:
                st.markdown(f'<span class="tag t-y">سنوي</span> **{kind} السنوي ({unit})**', unsafe_allow_html=True)
                st.caption("السنوات الناقصة (أقل من 90% من الأيام) لا تُحسب ولا تظهر.")
                fig = px.line(yearly, x="year", y="value", markers=True, template="plotly_white",
                              labels={"year": "السنة", "value": f"{kind} ({unit})"}, color_discrete_sequence=["#0e7490"])
                fig.update_layout(font_family="Cairo", margin={"l": 10, "r": 10, "t": 10, "b": 10}, height=360)
                st.plotly_chart(fig, width="stretch")
            with p2:
                st.markdown(f'<span class="tag t-m">شهري</span> **المتوسط المناخي الشهري ({unit})**', unsafe_allow_html=True)
                st.caption("متوسط قيمة كل شهر عبر السنوات الكاملة.")
                fig = px.bar(clim, x="month", y="value", template="plotly_white",
                             labels={"month": "الشهر", "value": f"{kind} الشهري ({unit})"}, color_discrete_sequence=["#14b8a6"])
                fig.update_layout(font_family="Cairo", margin={"l": 10, "r": 10, "t": 10, "b": 10}, height=360,
                                  xaxis={"dtick": 1})
                st.plotly_chart(fig, width="stretch")
            st.markdown('<span class="tag t-d">يومي</span> **الإحصاءات الوصفية للقيم اليومية**', unsafe_allow_html=True)
            stats = describe(res.data, [chosen]).rename(columns={
                "parameter": "المتغير", "count": "العدد", "missing": "الناقص", "mean": "المتوسط", "median": "الوسيط",
                "std": "الانحراف المعياري", "min": "الأدنى", "p25": "الربيع الأول", "p75": "الربيع الثالث", "max": "الأعلى"})
            st.dataframe(stats, width="stretch", hide_index=True)

            st.divider()
            st.markdown('<div class="sec">مقارنة المواقع ببعضها</div>', unsafe_allow_html=True)
            st.caption(f"قارن عدة مواقع (طبقات) معًا لنفس المتغير المختار أعلاه: **{chosen}**. "
                       "الرسوم فوق بعضها، وجدول يرتّب المواقع، ومصفوفة ارتباط بين المواقع.")
            ids = dict(zip(points["file"], points["location_id"], strict=True))
            label_of = [ids.get(r.extra.get("source_file"), f"موقع {i + 1}") for i, r in enumerate(fr.results)]
            q1, q2 = st.columns([4, 1])
            pick_all = q2.checkbox("كل المواقع", help="مقارنة كل المواقع المقروءة")
            if pick_all:
                chosen_labels = label_of
            else:
                chosen_labels = q1.multiselect("اختر المواقع المراد مقارنتها (موقعان على الأقل)", label_of,
                                               default=label_of[:3])
            if len(chosen_labels) < 2:
                st.info("اختر موقعين على الأقل لبدء المقارنة.")
            else:
                items = {lab: fr.results[label_of.index(lab)].data for lab in chosen_labels}
                with st.spinner("جارٍ حساب المقارنة..."):
                    cmp = _compare_cached(st.session_state.get("token", 0), tuple(chosen_labels), chosen,
                                          fr, items)
                many = len(chosen_labels) > 15
                if many:
                    st.warning("عدد المواقع كبير؛ الخطوط الفردية باهتة وخط المتوسط العام بارز. الجدول والارتباط يشملان الكل.")
                u = res.units.get(chosen, "")
                k1, k2 = st.columns(2)
                with k1:
                    st.markdown(f'<span class="tag t-y">سنوي</span> **مقارنة {kind} السنوي ({u})**', unsafe_allow_html=True)
                    fig = px.line(cmp.yearly, x="year", y="value", color="label", markers=not many, template="plotly_white",
                                  labels={"year": "السنة", "value": f"{kind} ({u})", "label": "الموقع"})
                    if many:
                        fig.update_traces(opacity=0.25, line={"width": 1}, showlegend=False)
                        avg = cmp.yearly.groupby("year", as_index=False)["value"].mean()
                        fig.add_scatter(x=avg["year"], y=avg["value"], mode="lines+markers", name="المتوسط العام",
                                        line={"width": 4, "color": "#0b3954"})
                    fig.update_layout(font_family="Cairo", margin={"l": 10, "r": 10, "t": 10, "b": 10}, height=380)
                    st.plotly_chart(fig, width="stretch")
                with k2:
                    st.markdown(f'<span class="tag t-m">شهري</span> **مقارنة المتوسط المناخي الشهري ({u})**', unsafe_allow_html=True)
                    fig = px.line(cmp.climatology, x="month", y="value", color="label", markers=not many, template="plotly_white",
                                  labels={"month": "الشهر", "value": f"{kind} الشهري ({u})", "label": "الموقع"})
                    if many:
                        fig.update_traces(opacity=0.25, line={"width": 1}, showlegend=False)
                        avg = cmp.climatology.groupby("month", as_index=False)["value"].mean()
                        fig.add_scatter(x=avg["month"], y=avg["value"], mode="lines+markers", name="المتوسط العام",
                                        line={"width": 4, "color": "#0b3954"})
                    fig.update_layout(font_family="Cairo", margin={"l": 10, "r": 10, "t": 10, "b": 10}, height=380,
                                      xaxis={"dtick": 1})
                    st.plotly_chart(fig, width="stretch")

                st.markdown("**جدول المقارنة (مرتّب من الأعلى إلى الأدنى)**")
                table_ar = compare_to_arabic(cmp.summary.sort_values("mean", ascending=False), cmp.how, u)
                st.dataframe(table_ar, width="stretch", hide_index=True)
                st.markdown('<span class="tag t-m">شهري</span> **ارتباط المواقع ببعضها**', unsafe_allow_html=True)
                st.caption("الارتباط محسوب على الشذوذ الشهري (كل شهر ناقص متوسط نفس الشهر لنفس الموقع) حتى لا تضخّمه الدورة الموسمية المشتركة. "
                           "القيمة من -1 إلى 1. المواقع المتجاورة في NASA POWER غالبًا شديدة الارتباط لأنها من نفس الشبكة. "
                           "تظهر الخلية فارغة إذا كان التداخل أقل من 12 شهرًا.")
                heat = px.imshow(cmp.correlation, zmin=-1, zmax=1, color_continuous_scale="RdBu", aspect="auto",
                                 labels={"color": "الارتباط"})
                heat.update_layout(font_family="Cairo", margin={"l": 10, "r": 10, "t": 10, "b": 10}, height=480)
                st.plotly_chart(heat, width="stretch")
                d1, d2 = st.columns(2)
                d1.download_button("⬇ جدول المقارنة CSV", to_csv_bytes(table_ar), "NPCGA_locations_comparison_AR.csv",
                                   mime="text/csv", width="stretch")
                d2.download_button("⬇ مصفوفة الارتباط CSV", cmp.correlation.to_csv().encode("utf-8-sig"),
                                   "NPCGA_locations_correlation.csv", mime="text/csv", width="stretch")

    with tab_pts:
        st.caption("صف واحد لكل موقع. الإحداثيات WGS 84 — EPSG:4326. لا يتم حذف أي موقع تلقائيًا؛ "
                   "المكرر والناقص يظهران في حقول الجودة. الوسم بين [ ] يوضح نوع التحليل: سنوي / شهري / يومي.")
        english = st.toggle("عرض أسماء الحقول بالإنجليزية (كما ستدخل ArcGIS Pro)", value=False)
        st.dataframe(points if english else arabic_points(points), width="stretch", hide_index=True)

    with tab_dl:
        def card(title: str, scale: str, cls: str, text: str) -> None:
            st.markdown(f'<div class="card" dir="rtl"><h4>{title} <span class="tag {cls}">{scale}</span></h4><p>{text}</p></div>',
                        unsafe_allow_html=True)

        card("ملف Excel عربي شامل (الأسهل)", "كل المقاييس", "t-s",
             "أوراق: اقرأ أولاً · ملخص المواقع · تحليل سنوي · تحليل شهري · شرح الأعمدة. كل عمود اسمه بالعربي مع وحدته.")
        if st.session_state.excel:
            st.download_button("⬇ تنزيل Excel العربي الشامل", st.session_state.excel, "NPCGA_Analysis_AR.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               type="primary", width="stretch")
        else:
            st.info("لتفعيل ملف Excel شغّل Start_NPCGA.bat مرة أخرى (يثبّت مكتبة openpyxl).")

        a, b, c = st.columns(3)
        with a:
            card("ملخص المواقع", "عدة مقاييس", "t-s", "صف لكل موقع. الوسم [سنوي]/[شهري]/[يومي] في اسم كل عمود.")
            st.download_button("⬇ ملخص المواقع CSV", st.session_state.points_ar, "NPCGA_locations_summary_AR.csv",
                               mime="text/csv", width="stretch")
        with b:
            card("التحليل السنوي", "سنوي", "t-y", "صف لكل موقع وسنة: إجمالي المطر السنوي + مؤشرات ETCCDI.")
            st.download_button("⬇ التحليل السنوي CSV", st.session_state.annual_ar, "NPCGA_annual_analysis_AR.csv",
                               mime="text/csv", width="stretch")
        with c:
            card("التحليل الشهري", "شهري", "t-m", "صف لكل موقع وسنة وشهر: إجمالي المطر الشهري.")
            st.download_button("⬇ التحليل الشهري CSV", st.session_state.monthly_ar, "NPCGA_monthly_analysis_AR.csv",
                               mime="text/csv", width="stretch")

        card("ملفات ArcGIS Pro", "نقاط", "t-s",
             "Shapefile وGeoPackage وGeoJSON وCSV + سكريبت ArcPy + قاموس الحقول بالعربي. أسماء الحقول داخلها إنجليزية مختصرة "
             "لأن Shapefile لا يدعم الأسماء العربية جيدًا، وشرح كل حقل بالعربي في ملف points_fields_ar.csv.")
        st.download_button("⬇ تنزيل ملفات ArcGIS (ZIP)", st.session_state.zip_bytes, "NPCGA_points_ArcGIS.zip",
                           mime="application/zip", width="stretch")
        for m in st.session_state.zip_msgs:
            st.info(m)
        st.download_button("⬇ قاموس الحقول بالعربي CSV", to_csv_bytes(fields_guide_ar()), "NPCGA_fields_guide_AR.csv",
                           mime="text/csv")

        card("البيانات اليومية لكل المواقع", "يومي", "t-d", "ملف كبير (كل يوم لكل موقع). يُجهَّز عند الطلب فقط.")
        if st.button("جهّز الملف اليومي"):
            with st.spinner("جارٍ تجهيز الملف اليومي..."):
                units = fr.results[0].units
                st.session_state.daily_csv = to_csv_bytes(to_arabic(daily_table(fr, points), "daily", units))
        if st.session_state.get("daily_csv"):
            st.download_button("⬇ تنزيل البيانات اليومية CSV", st.session_state.daily_csv,
                               "NPCGA_daily_data_AR.csv", mime="text/csv", type="primary")

st.divider()
st.markdown('<div class="sec">ℹ️ عن التطبيق والمطوّر</div>', unsafe_allow_html=True)
ab1, ab2 = st.columns([1, 1])
with ab1:
    st.markdown(f"""<div class="card" dir="rtl"><h4>المطوّر</h4>
<p style="font-size:17px;color:#0f2a3d;margin-bottom:4px"><b>{config.DEVELOPER_AR}</b></p>
<p>{config.DEVELOPER}<br>مهندس مساحة · جيوماتكس ونظم المعلومات الجغرافية</p></div>""", unsafe_allow_html=True)
    st.link_button("🔗 صفحة المطوّر على LinkedIn", _LINK, width="stretch")
    st.caption("إذا لم يفتح الرابط، ابحث عن الاسم على LinkedIn: Mahmoud Mohamed Atia.")
with ab2:
    st.markdown(f"""<div class="card" dir="rtl"><h4>{config.APP_NAME}</h4>
<p>الإصدار {__version__} · ترخيص MIT (مفتوح المصدر)<br>
تحليل المطر والمناخ من بيانات NASA POWER وتجهيز نقاط GIS لـ ArcGIS Pro.<br>
<b>مصدر البيانات:</b> NASA Langley Research Center (LaRC) POWER Project — https://power.larc.nasa.gov/<br>
<b>تنبيه علمي:</b> بيانات POWER منتج شبكي من الأقمار الصناعية وإعادة التحليل، وليست قياسات محطات أرضية.
اتجاهات Mann-Kendall تقريبية خاصة إذا قلّ عدد السنوات عن 10.</p></div>""", unsafe_allow_html=True)
st.caption(f"تطوير: {config.DEVELOPER_AR} ({config.DEVELOPER}) · [LinkedIn]({_LINK}) · {config.APP_NAME} v{__version__}")

with st.expander("📘 دليل الاستخدام بالعربي — اضغط للفتح",expanded=not st.session_state.analysis_done):
    st.markdown("""
    **الخطوة 1 — تجهيز المجلد**
    - ضع ملفات NASA POWER اليومية CSV الخاصة بالمواقع داخل مجلد واحد.
    - يجب أن يحتوي كل ملف على ترويسة NASA POWER القياسية، بما فيها `-END HEADER-`، وحقول التاريخ `YEAR,MO,DY` أو `YEAR,DOY`.
    - يجب أن تكون الإحداثيات موجودة في الترويسة أو في اسم الملف بصيغة `lat26.5_lon30.2.csv`.

    **الخطوة 2 — رفع المجلد**
    - اضغط منطقة الرفع واختر المجلد كاملًا من نافذة الملفات، أو ارفع ZIP للمجلد، أو حدد عدة ملفات CSV.
    - لا تخلط ملفات شهرية/سنوية مع الملفات اليومية؛ دعم الملفات الشهرية غير متاح في هذه النسخة.

    **الخطوة 3 — التحليل**
    - اضغط «حلّل الملفات». سيقرأ النظام كل ملف، ويتحقق من الإحداثيات والتواريخ والقيم المفقودة والتكرار.
    - الملفات التي تفشل في القراءة تظهر في جدول أخطاء مع السبب.
    - يعرض النظام ملخصًا، ورسومًا زمنية حقيقية للمتغيرات المشتركة بين الملفات.

    **الخطوة 4 — تنزيل النقاط**
    - افتح تبويب «التنزيلات». الأسهل: ملف **Excel عربي شامل** (ملخص المواقع + تحليل سنوي + تحليل شهري + شرح الأعمدة). لـ ArcGIS Pro حمّل ZIP الصيغ (Shapefile وGeoPackage وGeoJSON وسكريبت ArcPy).\n    - كل ملف يبدأ بعمود «نوع التحليل» (يومي / شهري / سنوي)، وكل عمود اسمه بالعربي مع وحدته.\n    - ملفات ArcGIS أسماء حقولها إنجليزية مختصرة (لأن Shapefile لا يدعم الأسماء العربية جيدًا)، وشرحها بالعربي في ملف قاموس الحقول.
    - في ArcGIS Pro استخدم **XY Table To Point**، واجعل X Field = `longitude` وY Field = `latitude`، وحدد نظام الإحداثيات **GCS WGS 1984 (EPSG:4326)**.
    - راجع `data_status` و`idw_valid` وحقول QC قبل اختيار المواقع للتحليل.

    **ملاحظات علمية مهمة**
    - قيم NASA POWER التي تساوي `-999` تُعامل كقيم مفقودة ويُسجل عددها.
    - السنوات غير المكتملة لا تدخل في متوسط المطر السنوي إلا إذا حققت شرط اكتمال 90% من الأيام وفق المحرك.
    - R95p وR99p في المحرك الحالي مؤشرات مبسطة وليست تنفيذًا كاملًا لإجراءات ETCCDI القياسية.
    - اختبار Mann–Kendall الحالي لا يصحح الارتباط الذاتي؛ تعامل مع دلالته بحذر.
    - التطبيق يجهز نقاطًا وجدول سمات لـ ArcGIS Pro فقط؛ لا ينفذ IDW أو Kriging أو أي Interpolation.
    """)

st.caption("NPCGA · نسخة محلية تجريبية · Python 3.12+ · لا يتم إرسال ملفاتك إلى أي خادم خارجي عبر واجهة التطبيق.")
