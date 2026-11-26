"""Coordinate handling. Distances for interpolation are ALWAYS computed in a projected CRS
(metres), never on raw latitude/longitude degrees."""
from __future__ import annotations

import numpy as np


def utm_epsg(lon: float, lat: float) -> int:
    """EPSG code of the WGS84 UTM zone containing (lon, lat)."""
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError("lon/lat out of range")
    zone = min(60, int((lon + 180) // 6) + 1)
    return (32600 if lat >= 0 else 32700) + zone


def project_points(lon, lat, epsg: int):
    """WGS84 lon/lat (degrees) -> projected x, y (metres) in ``epsg``. Needs pyproj (lazy import)."""
    from pyproj import Transformer  # heavy import kept out of module load

    tr = Transformer.from_crs(4326, epsg, always_xy=True)
    x, y = tr.transform(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))
    return np.asarray(x), np.asarray(y)
