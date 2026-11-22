"""The stand mask in another coordinate system than the raster.

``load_stands`` used the polygons as they came. A stand layer in geographic
coordinates over an orthophoto in a projected system then contained no point
at all, and ``detect`` dropped every tree without saying why.
"""
import numpy as np
import pytest

fiona = pytest.importorskip("fiona")
pytest.importorskip("rasterio")
from rasterio.warp import transform_geom  # noqa: E402
from shapely.geometry import box, mapping  # noqa: E402

from pygeosnag.mask import inside, load_stands  # noqa: E402

SQUARE = box(540000.0, 810000.0, 540100.0, 810100.0)          # 100 m x 100 m in EPSG:2180
POINTS = np.array([[540050.0, 810050.0], [540001.0, 810001.0], [540200.0, 810050.0]])


def _write(path, geom, crs):
    schema = {"geometry": "Polygon", "properties": {"species_age": "int"}}
    with fiona.open(str(path), "w", driver="GPKG", crs=crs, schema=schema) as dst:
        dst.write({"geometry": geom, "properties": {"species_age": 50}})
    return str(path)


def test_a_layer_in_the_rasters_system_is_used_as_it_is(tmp_path):
    path = _write(tmp_path / "stands_2180.gpkg", mapping(SQUARE), "EPSG:2180")
    mask = load_stands(path, buffer_m=-2.0, quiet=True, crs="EPSG:2180")
    assert inside(mask, POINTS).tolist() == [True, False, False]   # the second is within the 2 m shrunk away
    assert mask.area == pytest.approx(96.0 * 96.0, rel=1e-9)


def test_a_layer_in_geographic_coordinates_is_brought_into_the_rasters_system(tmp_path):
    lonlat = transform_geom("EPSG:2180", "EPSG:4326", mapping(SQUARE))
    path = _write(tmp_path / "stands_4326.gpkg", lonlat, "EPSG:4326")
    mask = load_stands(path, buffer_m=-2.0, quiet=True, crs="EPSG:2180")
    assert inside(mask, POINTS).tolist() == [True, False, False]
    assert mask.area == pytest.approx(96.0 * 96.0, rel=1e-3)       # the buffer is in metres of the raster's system

    # as before 0.5.3, without the raster's system: degrees held against metres
    untouched = load_stands(path, buffer_m=0.0, quiet=True)
    assert not inside(untouched, POINTS).any()
