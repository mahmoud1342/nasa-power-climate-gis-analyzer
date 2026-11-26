from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from npcga.analysis import variable_profile

APP = Path(__file__).resolve().parents[1] / "app.py"


def daily(temp=20.0, rain=1.0):
    d = pd.date_range("2020-01-01", "2021-12-31")
    return pd.DataFrame({"date": d, "T2M": temp, "PRECTOTCORR": rain})


def test_temperature_is_averaged_not_summed():
    yearly, clim, how = variable_profile(daily(), "T2M")
    assert how == "mean" and yearly.value.tolist() == [20.0, 20.0] and clim.value.eq(20.0).all()


def test_rain_is_summed():
    yearly, clim, how = variable_profile(daily(), "PRECTOTCORR")
    assert how == "sum" and yearly.value.tolist() == [366.0, 365.0]
    assert clim.loc[clim.month == 2, "value"].iloc[0] == pytest.approx((29 + 28) / 2)
    assert len(clim) == 12 and np.isfinite(clim.value).all()


def test_streamlit_page_renders_results(tmp_path):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    from npcga.export import build_points_table
    from npcga.io import load_power_folder

    hdr = ("-BEGIN HEADER-\nLocation: latitude {lat}  longitude {lon}\nparameter(s):\n"
           "PRECTOTCORR    MERRA-2 Precipitation Corrected (mm/day)\n"
           "T2M            MERRA-2 Temperature at 2 Meters (C)\n-END HEADER-\nYEAR,DOY,PRECTOTCORR,T2M\n")
    for lat, lon in [(26.0, 80.0), (26.0, 80.625), (26.5, 80.0)]:
        rows = [f"{y},{d},1.0,20.0" for y in (2020, 2021) for d in range(1, (366 if y == 2020 else 365) + 1)]
        (tmp_path / f"POWER_daily_lat{lat}_lon{lon}.csv").write_text(hdr.format(lat=lat, lon=lon) + "\n".join(rows))
    fr = load_power_folder(tmp_path)
    pts = build_points_table(fr)

    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    assert not at.exception and [b.label for b in at.button] == ["🔎 حلّل الملفات"]
    at.session_state["analysis_done"] = True
    at.session_state["fr"], at.session_state["points"] = fr, pts
    from npcga.export import (
        annual_table,
        arabic_points,
        excel_workbook,
        monthly_table,
        to_arabic,
        to_csv_bytes,
    )
    at.session_state["zip_bytes"], at.session_state["zip_msgs"] = b"zip", []
    at.session_state["excel"] = excel_workbook(fr, pts)
    at.session_state["points_ar"] = to_csv_bytes(arabic_points(pts))
    at.session_state["annual_ar"] = to_csv_bytes(to_arabic(annual_table(fr, pts), "annual"))
    at.session_state["monthly_ar"] = to_csv_bytes(to_arabic(monthly_table(fr, pts), "monthly"))
    at.run()
    assert not at.exception
    assert len(at.tabs) == 4
    next(s for s in at.selectbox if "متغيرًا" in s.label).select("T2M")
    at.run()
    assert not at.exception
    ms = next(m for m in at.multiselect if "المراد مقارنتها" in m.label)
    assert len(ms.value) == 3                                   # default: first three locations
    ms.set_value(ms.value[:2])
    at.run()
    assert not at.exception and any("ارتباط" in str(m.value) for m in at.markdown)
    ms = next(m for m in at.multiselect if "المراد مقارنتها" in m.label)
    ms.set_value(ms.value[:1])
    at.run()
    assert not at.exception and any("موقعين على الأقل" in str(i.value) for i in at.info)
    next(t for t in at.toggle if "بالإنجليزية" in t.label).set_value(True)
    at.run()
    assert not at.exception
    next(b for b in at.button if b.label == "جهّز الملف اليومي").click()
    at.run()
    assert not at.exception and at.session_state["daily_csv"].startswith(b"\xef\xbb\xbf")


def test_developer_credit_and_linkedin_everywhere(tmp_path):
    from urllib.parse import unquote

    from npcga import config

    href = config.linkedin_href()
    assert href.startswith("https://www.linkedin.com/in/") and href.isascii() and "%" in href
    assert unquote(href) == config.LINKEDIN_URL                     # encoding is lossless
    assert config.DEVELOPER == "Mahmoud Mohamed Atia" and config.DEVELOPER_AR == "محمود محمد عطية"

    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=60).run()      # no analysis yet: About must still show
    assert not at.exception
    page = " ".join(str(m.value) for m in at.markdown) + " ".join(str(c.value) for c in at.caption)
    assert "محمود محمد عطية" in page and "Mahmoud Mohamed Atia" in page and "LinkedIn" in page
    links = [str(getattr(b, "proto", b)) for b in at.get("link_button")]
    assert links and "linkedin.com/in/" in links[0]


def test_excel_info_sheet_credits_developer(tmp_path):
    from test_points import make_folder

    from npcga.export import build_points_table, info_table
    from npcga.io import load_power_folder

    fr = load_power_folder(make_folder(tmp_path / "raw"))
    info = info_table(fr, build_points_table(fr))
    text = " ".join(info["التفاصيل"].astype(str))
    assert "Mahmoud Mohamed Atia" in text and "linkedin.com/in/" in text and "0.1.0" in " ".join(info["التفاصيل"].astype(str))
