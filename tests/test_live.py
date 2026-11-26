"""Live API test. Run explicitly with:  pytest -m network"""
import pytest

from npcga.power import fetch_point


@pytest.mark.network
def test_live_daily_alexandria():
    r = fetch_point(31.20, 29.92, ["PRECTOTCORR", "T2M"], "20240101", "20240110")
    assert len(r.data) == 10
    assert set(r.units) == {"PRECTOTCORR", "T2M"}
    print(r.units, r.nodata_counts)
