"""High-level entry point: validate -> cache lookup -> download -> cache store."""
from __future__ import annotations

from .cache import PowerCache, make_key
from .client import fetch_point, validate_request


def get_point_data(latitude, longitude, parameters, start, end, temporal="daily", community="AG",
                   *, cache: PowerCache | None = None, use_cache: bool = True,
                   fetch=fetch_point, **fetch_kwargs):
    lat, lon, params, s, e, temporal, community = validate_request(
        latitude, longitude, parameters, start, end, temporal, community
    )
    cache = cache if cache is not None else (PowerCache() if use_cache else None)
    key = make_key(lat, lon, params, s, e, temporal, community)
    if use_cache and cache is not None:
        hit = cache.get(key)
        if hit is not None:
            return hit
    result = fetch(lat, lon, params, s, e, temporal, community, **fetch_kwargs)
    if use_cache and cache is not None:
        cache.put(key, result)
    return result
