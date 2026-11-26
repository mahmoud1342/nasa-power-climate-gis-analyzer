"""Raster grid construction and convex-hull masking (to avoid presenting extrapolation)."""
from __future__ import annotations

import numpy as np

MAX_CELLS = 4_000_000


def make_grid(xy: np.ndarray, cell: float, buffer: float = 0.0, max_cells: int = MAX_CELLS):
    """Cell-centre coordinates covering the points' bounding box (+ buffer, same units).

    Returns (xs ascending, ys descending (north first), (west, north) of the upper-left corner).
    """
    if cell <= 0 or buffer < 0:
        raise ValueError("cell must be > 0 and buffer >= 0")
    xmin, ymin = xy.min(axis=0) - buffer
    xmax, ymax = xy.max(axis=0) + buffer
    ncols = max(1, int(np.ceil((xmax - xmin) / cell)))
    nrows = max(1, int(np.ceil((ymax - ymin) / cell)))
    if ncols * nrows > max_cells:
        raise ValueError(f"grid would have {ncols * nrows:,} cells (max {max_cells:,}); use a larger cell size")
    xs = xmin + (np.arange(ncols) + 0.5) * cell
    ys = ymax - (np.arange(nrows) + 0.5) * cell
    return xs, ys, (float(xmin), float(ymax))


def convex_hull(xy: np.ndarray) -> np.ndarray:
    """Counter-clockwise convex hull (Andrew's monotone chain). Raises if points are collinear."""
    pts = np.unique(np.asarray(xy, dtype=float), axis=0)
    if len(pts) < 3:
        raise ValueError("need at least 3 distinct points for a hull")
    pts = pts[np.lexsort((pts[:, 1], pts[:, 0]))]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in pts[::-1]:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = np.array(lower[:-1] + upper[:-1])
    if len(hull) < 3:
        raise ValueError("points are collinear; cannot interpolate over an area")
    return hull


def inside_hull(hull: np.ndarray, targets: np.ndarray) -> np.ndarray:
    """Boolean mask: target points inside or on the boundary of the convex hull."""
    span = float(np.ptp(hull, axis=0).max())
    tol = -1e-9 * span * span
    inside = np.ones(len(targets), dtype=bool)
    for i in range(len(hull)):
        a, b = hull[i], hull[(i + 1) % len(hull)]
        c = (b[0] - a[0]) * (targets[:, 1] - a[1]) - (b[1] - a[1]) * (targets[:, 0] - a[0])
        inside &= c >= tol
    return inside
