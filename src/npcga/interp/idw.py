"""Inverse Distance Weighting.

    z(x) = sum(w_i * z_i) / sum(w_i),   w_i = 1 / d_i**power

d_i are Euclidean distances in a PROJECTED CRS (metres). At most ``n_neighbors`` nearest points
within ``radius`` are used; a target with no point in range is NaN (NoData). A target that
coincides with a data point returns that point's value (exact interpolator). IDW never produces
values outside the range of the input values.
"""
from __future__ import annotations

import numpy as np

from .grid import convex_hull, inside_hull, make_grid

MIN_POINTS = 3
EXPLORATORY_BELOW = 10   # fewer points than this: surface is exploratory only
_EXACT = 1e-9


def validate_points(xy, values) -> tuple[np.ndarray, np.ndarray]:
    xy = np.asarray(xy, dtype=float)
    values = np.asarray(values, dtype=float)
    if xy.ndim != 2 or xy.shape[1] != 2 or len(xy) != len(values):
        raise ValueError("xy must be (n, 2) and values must have length n")
    if not (np.isfinite(xy).all() and np.isfinite(values).all()):
        raise ValueError("coordinates and values must be finite (no NaN/Inf); remove or fix them first")
    if len(xy) < MIN_POINTS:
        raise ValueError(f"IDW needs at least {MIN_POINTS} points; got {len(xy)}. "
                         "A single NASA POWER point cannot be interpolated.")
    if len(np.unique(xy, axis=0)) != len(xy):
        raise ValueError("duplicate point coordinates found; remove duplicates first")
    return xy, values


def _check_params(power, n_neighbors, radius):
    if not power > 0:
        raise ValueError("power must be > 0")
    if n_neighbors is not None and (not isinstance(n_neighbors, int | np.integer) or n_neighbors < 1):
        raise ValueError("n_neighbors must be a positive integer or None")
    if radius is not None and not radius > 0:
        raise ValueError("radius must be > 0 or None")


def _idw_core(D: np.ndarray, values: np.ndarray, power: float, k: int | None, radius: float | None):
    """D: (targets, points) distances; inf marks 'not usable'."""
    n = D.shape[1]
    D = np.where(np.isfinite(D), D, np.inf)
    if radius is not None:
        D = np.where(D <= radius, D, np.inf)
    k = n if k is None else min(k, n)
    idx = np.argpartition(D, k - 1, axis=1)[:, :k] if k < n else np.broadcast_to(np.arange(n), D.shape)
    dk = np.take_along_axis(D, idx, axis=1)
    vk = values[idx]
    valid = np.isfinite(dk)
    exact = valid & (dk < _EXACT)
    with np.errstate(divide="ignore", over="ignore"):
        w = np.where(valid & ~exact, dk ** -power, 0.0)
    wsum = w.sum(axis=1)
    out = np.full(D.shape[0], np.nan)
    ok = wsum > 0
    out[ok] = (w[ok] * vk[ok]).sum(axis=1) / wsum[ok]
    has_exact = exact.any(axis=1)
    if has_exact.any():
        first = exact.argmax(axis=1)
        out[has_exact] = vk[has_exact, first[has_exact]]
    return out


def idw_predict(xy, values, targets, power: float = 2.0, n_neighbors: int | None = 12,
                radius: float | None = None) -> np.ndarray:
    xy, values = validate_points(xy, values)
    _check_params(power, n_neighbors, radius)
    targets = np.asarray(targets, dtype=float)
    out = np.empty(len(targets))
    chunk = max(1, 4_000_000 // len(xy))
    for s in range(0, len(targets), chunk):
        t = targets[s:s + chunk]
        D = np.hypot(t[:, None, 0] - xy[None, :, 0], t[:, None, 1] - xy[None, :, 1])
        out[s:s + chunk] = _idw_core(D, values, power, n_neighbors, radius)
    return out


def idw_grid(xy, values, cell: float, power: float = 2.0, n_neighbors: int | None = 12,
             radius: float | None = None, buffer: float = 0.0, mask_outside_hull: bool = True):
    """Interpolate onto a regular grid. Returns (array[rows, cols] with NaN as NoData, xs, ys, origin).

    Cells outside the convex hull of the data points are set to NaN by default, so the
    raster does not present extrapolation as if it were interpolation.
    """
    xy, values = validate_points(xy, values)
    xs, ys, origin = make_grid(xy, cell, buffer)
    gx, gy = np.meshgrid(xs, ys)
    targets = np.column_stack([gx.ravel(), gy.ravel()])
    z = idw_predict(xy, values, targets, power, n_neighbors, radius)
    if mask_outside_hull:
        z[~inside_hull(convex_hull(xy), targets)] = np.nan
    return z.reshape(gx.shape), xs, ys, origin
