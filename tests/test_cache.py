from npcga.power.cache import PowerCache, make_key
from npcga.power.client import parse_response
from npcga.power.service import get_point_data


def test_key_ignores_parameter_order_but_not_values():
    a = make_key(31.2, 29.92, ["T2M", "PS"], "20240101", "20240103", "daily", "AG")
    assert a == make_key(31.2, 29.92, ["PS", "T2M"], "20240101", "20240103", "daily", "AG")
    assert a != make_key(31.2, 29.92, ["PS", "T2M"], "20240101", "20240104", "daily", "AG")


def test_roundtrip_preserves_data(tmp_path, daily_payload):
    cache = PowerCache(tmp_path)
    res = parse_response(daily_payload, "daily")
    cache.put("k1", res)
    back = cache.get("k1")
    assert back.from_cache and back.units == res.units and back.nodata_counts == res.nodata_counts
    assert back.data.equals(res.data)
    assert cache.get("missing") is None


def test_service_downloads_once(tmp_path, daily_payload):
    calls = []

    def fake_fetch(*args, **kwargs):
        calls.append(args)
        return parse_response(daily_payload, "daily")

    cache = PowerCache(tmp_path)
    args = (31.2, 29.92, ["PRECTOTCORR", "T2M"], "20240101", "20240103")
    first = get_point_data(*args, cache=cache, fetch=fake_fetch)
    second = get_point_data(*args, cache=cache, fetch=fake_fetch)
    assert len(calls) == 1 and not first.from_cache and second.from_cache


def test_corrupt_cache_entry_is_dropped(tmp_path, daily_payload):
    cache = PowerCache(tmp_path)
    cache.put("k", parse_response(daily_payload, "daily"))
    (tmp_path / "k.parquet").unlink()
    assert cache.get("k") is None
