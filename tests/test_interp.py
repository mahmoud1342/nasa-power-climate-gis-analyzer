import numpy as np
import pandas as pd
import pytest

from npcga.interp import (
    convex_hull,
    cv_metrics,
    idw_grid,
    idw_predict,
    inside_hull,
    loo_cv_idw,
    make_grid,
    utm_epsg,
    validate_points,
)

P2 = np.array([[0.0, 0.0], [10.0, 0.0], [5.0, 8.0]])


def test_idw_hand_computed_values():
    xy = np.array([[0.0, 0.0], [10.0, 0.0], [0.0, 10.0]])
    v = np.array([10.0, 20.0, 30.0])
    # midpoint of the first two, third far: weights 1/25,1/25,1/(5^2+... ) computed by hand below
    t = np.array([[2.5, 0.0]])
    d = np.array([2.5, 7.5, np.hypot(2.5, 10)])
    w = d ** -2.0
    expected = (w * v).sum() / w.sum()
    assert idw_predict(xy, v, t, power=2, n_neighbors=None)[0] == pytest.approx(expected)
    two = idw_predict(xy[:2].tolist() + [[100.0, 100.0]], [10.0, 20.0, 99.0], t, power=2, n_neighbors=2)
    assert two[0] == pytest.approx(11.0)       # (1.6 + 0.3556)/0.1778 with weights 1/6.25, 1/56.25


def test_idw_exact_nearest_radius_and_bounds():
    v = np.array([1.0, 5.0, 9.0])
    assert idw_predict(P2, v, [[10.0, 0.0]])[0] == 5.0                       # exact at a data point
    assert idw_predict(P2, v, [[1.0, 0.0]], n_neighbors=1)[0] == 1.0         # nearest only
    assert np.isnan(idw_predict(P2, v, [[500.0, 500.0]], radius=10)[0])      # nothing in range
    t = np.random.default_rng(0).uniform(-5, 15, size=(200, 2))
    z = idw_predict(P2, v, t, power=3, n_neighbors=None)
    assert z.min() >= 1.0 - 1e-9 and z.max() <= 9.0 + 1e-9                   # never leaves data range


def test_idw_input_validation():
    with pytest.raises(ValueError, match="at least 3"):
        validate_points([[0, 0], [1, 1]], [1, 2])
    with pytest.raises(ValueError, match="finite"):
        validate_points(P2, [1, np.nan, 3])
    with pytest.raises(ValueError, match="duplicate"):
        validate_points([[0, 0], [0, 0], [1, 1]], [1, 2, 3])
    for kw in ({"power": 0}, {"n_neighbors": 0}, {"radius": -1}):
        with pytest.raises(ValueError):
            idw_predict(P2, [1, 2, 3], [[1, 1]], **kw)


def test_loo_cv_hand_computed():
    xy = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
    table, m = loo_cv_idw(xy, [0.0, 1.0, 2.0], power=2, n_neighbors=None)
    assert table.error.tolist() == pytest.approx([1.2, 0.0, -1.2])
    assert m["ME"] == pytest.approx(0.0, abs=1e-12) and m["MAE"] == pytest.approx(0.8)
    assert m["RMSE"] == pytest.approx(np.sqrt(0.96)) and m["R2"] == pytest.approx(-0.44)
    assert m["n"] == 3 and m["n_points"] == 3


def test_cv_metrics_edge_cases():
    assert cv_metrics([1, 1, 1], [1, 1, 1])["R2"] != cv_metrics([1, 1, 1], [1, 1, 1])["R2"]  # NaN
    assert cv_metrics([np.nan], [1.0])["n"] == 0
    m = cv_metrics([1, 2, 3], [1, 2, np.nan])
    assert m["n"] == 2 and m["RMSE"] == 0.0


def test_loo_radius_leaves_isolated_point_out():
    xy = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [1000.0, 0.0]])
    _, m = loo_cv_idw(xy, [1, 2, 3, 4], power=2, n_neighbors=None, radius=5)
    assert m["n"] == 3 and m["n_points"] == 4


def test_grid_layout_and_hull_mask():
    tri = np.array([[0.0, 0.0], [10.0, 0.0], [0.0, 10.0]])
    xs, ys, origin = make_grid(tri, 5.0)
    assert xs.tolist() == [2.5, 7.5] and ys.tolist() == [7.5, 2.5] and origin == (0.0, 10.0)
    z, *_ = idw_grid(tri, [1.0, 2.0, 3.0], 5.0, n_neighbors=None)
    assert np.isnan(z[0, 1]) and np.isfinite(z[0, 0]) and np.isfinite(z[1, 0]) and np.isfinite(z[1, 1])
    z2, *_ = idw_grid(tri, [1.0, 2.0, 3.0], 5.0, n_neighbors=None, mask_outside_hull=False)
    assert np.isfinite(z2).all()
    with pytest.raises(ValueError, match="max"):
        make_grid(tri, 0.001)
    with pytest.raises(ValueError):
        convex_hull(np.array([[0.0, 0], [1, 1], [2, 2]]))
    assert inside_hull(convex_hull(tri), np.array([[1.0, 1.0], [9.0, 9.0]])).tolist() == [True, False]


def test_utm_epsg():
    assert utm_epsg(29.92, 31.2) == 32635        # Alexandria
    assert utm_epsg(84.0, 28.0) == 32645         # Nepal centre
    assert utm_epsg(-70.0, -33.0) == 32719       # southern hemisphere
    assert utm_epsg(180, 0) == 32660
    with pytest.raises(ValueError):
        utm_epsg(200, 0)


def test_project_points_known_value():
    pytest.importorskip("pyproj")
    from npcga.interp import project_points
    x, y = project_points([33.0], [0.0], 32636)  # zone 36 central meridian is 33 E
    assert x[0] == pytest.approx(500000.0, abs=1e-3) and y[0] == pytest.approx(0.0, abs=1e-3)


def test_geotiff_roundtrip(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    from npcga.interp import write_geotiff
    arr = np.array([[1.0, np.nan], [3.0, 4.0]])
    f = write_geotiff(tmp_path / "t.tif", arr, (1000.0, 2000.0), 500.0, 32645, {"method": "IDW"})
    with rasterio.open(f) as r:
        assert r.crs.to_epsg() == 32645 and r.nodata == -9999.0 and r.res == (500.0, 500.0)
        assert r.transform.c == 1000.0 and r.transform.f == 2000.0
        data = r.read(1)
        assert data[0, 0] == 1.0 and data[0, 1] == -9999.0 and r.tags()["method"] == "IDW"


def test_cli_interp_end_to_end(tmp_path):
    pytest.importorskip("rasterio"); pytest.importorskip("pyproj")
    import rasterio

    from npcga.cli_interp import main
    rng = np.random.default_rng(3)
    lat, lon = rng.uniform(26, 30, 15), rng.uniform(80, 88, 15)
    csv = tmp_path / "p.csv"
    pd.DataFrame({"latitude": lat, "longitude": lon, "val": 100 + 10 * (lon - 80)}).to_csv(csv, index=False)
    code = main(["--points", str(csv), "--value", "val", "--cell", "40000", "--out", str(tmp_path), "--name", "t"])
    assert code == 0
    with rasterio.open(tmp_path / "t" / "t.tif") as r:
        assert r.crs.to_epsg() == 32645 and (r.read(1) != -9999).any()
        assert "cross-validation" in r.tags()["status"]
    assert {"cv_points.csv", "cv_power_comparison.csv", "report.txt"} <= {p.name for p in (tmp_path / "t").iterdir()}


def test_cli_interp_refuses_missing_values_and_few_points(tmp_path, capsys):
    from npcga.cli_interp import main
    csv = tmp_path / "p.csv"
    pd.DataFrame({"latitude": [1, 2, 3], "longitude": [1, 2, 3], "v": [1, np.nan, 3]}).to_csv(csv, index=False)
    assert main(["--points", str(csv), "--value", "v", "--out", str(tmp_path)]) == 2
    assert "no 'v' value" in capsys.readouterr().out
    two = tmp_path / "two.csv"
    pd.DataFrame({"latitude": [1, 2], "longitude": [1, 2], "v": [1, 2]}).to_csv(two, index=False)
    assert main(["--points", str(two), "--value", "v", "--out", str(tmp_path)]) == 2
    assert "at least 3" in capsys.readouterr().out
