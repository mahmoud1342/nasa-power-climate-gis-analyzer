"""Leave-one-out cross-validation and error metrics (error = predicted - observed)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .idw import _check_params, _idw_core, validate_points


def cv_metrics(observed, predicted) -> dict:
    """ME, MAE, RMSE and R2 (coefficient of determination, 1 - SSres/SStot; can be negative)."""
    obs, pred = np.asarray(observed, dtype=float), np.asarray(predicted, dtype=float)
    ok = np.isfinite(obs) & np.isfinite(pred)
    n = int(ok.sum())
    if n == 0:
        return {"n": 0, "ME": np.nan, "MAE": np.nan, "RMSE": np.nan, "R2": np.nan}
    err = pred[ok] - obs[ok]
    ss_tot = float(((obs[ok] - obs[ok].mean()) ** 2).sum())
    return {
        "n": n, "ME": float(err.mean()), "MAE": float(np.abs(err).mean()),
        "RMSE": float(np.sqrt((err ** 2).mean())),
        "R2": float(1 - (err ** 2).sum() / ss_tot) if ss_tot > 0 else np.nan,
    }


def loo_cv_idw(xy, values, power: float = 2.0, n_neighbors: int | None = 12,
               radius: float | None = None):
    """Predict every point from all the others. Returns (per-point DataFrame, metrics dict).

    Points left without any neighbour (radius too small) get NaN and are excluded from the
    metrics; their number is the difference between ``n_points`` and ``n``.
    """
    xy, values = validate_points(xy, values)
    _check_params(power, n_neighbors, radius)
    D = np.hypot(xy[:, None, 0] - xy[None, :, 0], xy[:, None, 1] - xy[None, :, 1])
    np.fill_diagonal(D, np.inf)
    pred = _idw_core(D, values, power, n_neighbors, radius)
    table = pd.DataFrame({"observed": values, "predicted": pred, "error": pred - values})
    metrics = cv_metrics(values, pred)
    metrics["n_points"] = len(values)
    return table, metrics
