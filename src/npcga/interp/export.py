"""GeoTIFF export (needs rasterio; imported lazily)."""
from __future__ import annotations

from pathlib import Path

import numpy as np

NODATA = -9999.0


def write_geotiff(path, array: np.ndarray, origin: tuple[float, float], cell: float, epsg: int,
                  tags: dict | None = None) -> Path:
    """Write a single-band float32 GeoTIFF. NaN -> NoData (-9999). ``origin`` = (west, north)
    of the upper-left corner; the CRS is the projected ``epsg`` the grid was computed in."""
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import from_origin

    path = Path(path)
    data = np.where(np.isfinite(array), array, NODATA).astype("float32")
    with rasterio.open(
        path, "w", driver="GTiff", height=data.shape[0], width=data.shape[1], count=1,
        dtype="float32", crs=CRS.from_epsg(epsg),
        transform=from_origin(origin[0], origin[1], cell, cell), nodata=NODATA,
    ) as dst:
        dst.write(data, 1)
        if tags:
            dst.update_tags(**{k: str(v) for k, v in tags.items()})
    return path
