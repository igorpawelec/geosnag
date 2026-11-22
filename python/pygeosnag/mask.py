"""Optional filters on the objects: a stand mask from forest-management
polygons, and the distance of an object to the nodata edge.

On seven Polish sites half of the detector's background objects were
roads and fields -- land no stand map contains. Keeping only objects
whose centroid lies inside stands of at least 10 years, shrunk by 2 m,
removed a quarter of all objects and, on 60 reviewed chips, only roads
and fields; younger stands are clear-cuts and plantations whose bare
soil rows the detector likes. Age thresholds above 10 start removing
real dead trees.
"""
import numpy as np


def load_stands(path, layer=None, age_field="species_age", min_age=10, buffer_m=-2.0, quiet=False, crs=None):
    """Union of stand polygons as a shapely geometry.

    Polygons with `age_field` below `min_age` are dropped; if the field is
    missing every polygon counts (a warning says so). A negative buffer
    shrinks the mask inward, a positive one grows it.

    `crs` is the coordinate system of the raster the mask is for. A layer in
    another one is brought into it before the buffer, which is in metres of
    the raster's system. Until 0.5.3 the polygons were used as they came, so
    a stand layer in geographic coordinates over an orthophoto in a projected
    system contained no point at all and every tree was dropped without a
    word.
    """
    import fiona
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union
    geoms, missing = [], 0
    with fiona.open(path, layer=layer) as src:
        reproject = None
        if crs is not None and src.crs:
            from rasterio.crs import CRS
            layer_crs, target = CRS.from_user_input(src.crs_wkt or src.crs), CRS.from_user_input(crs)
            if layer_crs != target:
                from rasterio.warp import transform_geom
                reproject = lambda g: transform_geom(layer_crs, target, g)      # noqa: E731
                if not quiet:
                    print(f"pygeosnag: stand polygons brought from {layer_crs.to_string()} to {target.to_string()}",
                          flush=True)
        has_age = age_field in src.schema["properties"]
        for f in src:
            if has_age and min_age is not None:
                age = f["properties"].get(age_field)
                if age is None or age < min_age:
                    missing += 1
                    continue
            geom = shape(f["geometry"])
            geoms.append(shape(reproject(mapping(geom))) if reproject else geom)
    if not has_age and min_age is not None and not quiet:
        import warnings
        warnings.warn(f"stand layer has no {age_field!r} field; using every polygon")
    if not geoms:
        raise ValueError("no stand polygons left after the age filter")
    g = unary_union(geoms)
    if buffer_m:
        g = g.buffer(buffer_m)
    if not quiet:
        print(f"pygeosnag: stand mask from {len(geoms)} polygons"
              + (f", {missing} below age {min_age}" if missing else "")
              + (f", buffer {buffer_m:g} m" if buffer_m else ""), flush=True)
    return g


def inside(geom, xy):
    """Boolean per point (n, 2): centroid inside the mask geometry."""
    import shapely
    if len(xy) == 0:
        return np.zeros(0, bool)
    return shapely.contains_xy(geom, xy[:, 0], xy[:, 1])


def nodata_distance(valid):
    """Distance (px) of every pixel to the nearest nodata pixel or window edge."""
    from scipy.ndimage import distance_transform_edt
    padded = np.pad(valid, 1, constant_values=False)
    return distance_transform_edt(padded)[1:-1, 1:-1]
