"""The README figure, generated from test_data so it can be remade.

    python www/figures.py            # from the package folder, python/

The package is read from the checkout and need not be installed; the script
itself needs matplotlib, rasterio and fiona. The models are downloaded by the
package on first use into its cache, as for any user.

Writes www/detect_grow.png and prints the numbers the README captions quote.
One scene, test_data/SNP_21_2020_1.tif: a 100 x 100 m RGB orthophoto at
0.25 m of a circular sample plot in a spruce stand, with 36 standing dead
trees digitised by hand as points (test_data/dead_trees_test.shp). The
package runs on it as a user would run it: detect() with its defaults, then
grow_crowns() from the detected points, into a temporary folder that is
removed afterwards. Left: the orthophoto. Middle: the detected points coloured
by their confidence, with the reference trees as hollow rings. Right: the
crowns grown from the points. The orthophoto is stretched for display only.
"""
import contextlib
import io
import os
import re
import sys
import tempfile

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import rasterio  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import pygeosnag  # noqa: E402

RGB = os.path.join(ROOT, "test_data", "SNP_21_2020_1.tif")
REF = os.path.join(ROOT, "test_data", "dead_trees_test.shp")
# The family's orange for the crowns, a light-to-orange ramp for the confidence
# (it has to read on a dark canopy), white rings for the reference trees.
CONF = LinearSegmentedColormap.from_list("conf", ["#fff3b0", "#f9c74f", "#eb6834", "#b5301b"])
ORANGE, INK, MUTED = "#eb6834", "#1f1f1f", "#6b6b6b"
NEAR, FAR = 1.5, 3.0                                      # m: match radii
STRICT = 0.7                                              # a stricter cut, applied to the written p afterwards


def read_points(path):
    import fiona
    with fiona.open(path) as src:
        feats = list(src)
    xy = np.array([f["geometry"]["coordinates"][:2] for f in feats], float).reshape(-1, 2)
    return xy, [dict(f["properties"]) for f in feats]


def read_rings(path):
    import fiona
    with fiona.open(path) as src:
        feats = list(src)
    rings = []
    for f in feats:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            rings.extend(np.asarray(r, float)[:, :2] for r in poly)
    return rings, [dict(f["properties"]) for f in feats]


def nearest(a, b):
    """Distance from every point of a to the nearest point of b."""
    if len(a) == 0 or len(b) == 0:
        return np.full(len(a), np.inf)
    return np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(axis=2)).min(axis=1)


def to_px(xy, inv):
    cols, rows = inv * (xy[:, 0], xy[:, 1])
    return np.column_stack([np.asarray(cols) - 0.5, np.asarray(rows) - 0.5])   # imshow centres pixels on integers


def panel(ax, img, label):
    ax.imshow(img, interpolation="nearest")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_edgecolor("#d9d9d9")
    ax.set_xlabel(label, fontsize=9.5, color=INK, labelpad=7)


# ---- the package, as a user runs it ----------------------------------------------
log = io.StringIO()
with tempfile.TemporaryDirectory(prefix="geosnag_figures_") as tmp:
    pts_path = os.path.join(tmp, "trees.gpkg")
    crowns_path = os.path.join(tmp, "crowns.gpkg")
    with contextlib.redirect_stdout(log):
        n_det = pygeosnag.detect(RGB, pts_path)
        n_grown = pygeosnag.grow_crowns(RGB, pts_path, crowns_path)
    det_xy, det_props = read_points(pts_path)
    rings, crown_props = read_rings(crowns_path)
for line in log.getvalue().splitlines():
    print("   | " + line)
first = next(line for line in log.getvalue().splitlines() if "threshold" in line)
threshold = float(re.search(r"threshold ([0-9.]+)", first).group(1))
mode = re.search(r"mode (\w+)", first).group(1)
models = sorted({p["model"] for p in det_props})
p = np.array([q["p"] for q in det_props], float)
areas = np.array([q["area_m2"] for q in crown_props], float)

ref_xy, _ = read_points(REF)
d_ref = nearest(ref_xy, det_xy)                           # reference tree -> nearest detected point
d_det = nearest(det_xy, ref_xy)                           # detected point -> nearest reference tree
strict = p >= STRICT
d_ref_strict = nearest(ref_xy, det_xy[strict])

with rasterio.open(RGB) as src:
    rgb = src.read()
    tf, res = src.transform, src.res[0]
valid = ~(rgb == 0).all(axis=0)
img = np.ones(rgb.shape[1:] + (3,))
for k in range(3):                                        # 1-99 percentile stretch, for display only
    lo, hi = np.percentile(rgb[k][valid], [1, 99])
    img[..., k] = np.clip((rgb[k] - lo) / max(hi - lo, 1e-9), 0, 1)
img[~valid] = 1.0                                         # outside the plot: white

n_ref = len(ref_xy)
print(f"scene {os.path.basename(RGB)}: {rgb.shape[2]} x {rgb.shape[1]} px at {res:g} m, "
      f"{rgb.shape[0]} bands; {n_ref} reference dead trees")
print(f"detect: {n_det} points, mode {mode}, threshold {threshold:g}, model {', '.join(models)}; "
      f"p from {p.min():.2f} to {p.max():.2f}")
print(f"reference trees with a detected point within {NEAR:g} m: {int((d_ref <= NEAR).sum())} of {n_ref}; "
      f"within {FAR:g} m: {int((d_ref <= FAR).sum())} of {n_ref}")
print(f"detected points with a reference tree within {NEAR:g} m: {int((d_det <= NEAR).sum())} of {n_det}; "
      f"within {FAR:g} m: {int((d_det <= FAR).sum())} of {n_det}")
hit = d_det <= NEAR
print(f"keeping only p >= {STRICT:g}: {int(strict.sum())} points, {int((hit & strict).sum())} with a "
      f"reference tree within {NEAR:g} m; {int((d_ref_strict <= NEAR).sum())} of {n_ref} reference trees "
      f"with a point within {NEAR:g} m; the cut drops {int((~strict).sum())} points, "
      f"{int((~strict & ~hit).sum())} without and {int((~strict & hit).sum())} with a reference tree within {NEAR:g} m")
print(f"grow_crowns: {n_grown} crowns from {n_det} points, median area {np.median(areas):.1f} m2 "
      f"(from {areas.min():.1f} to {areas.max():.1f} m2)")

# ---- the figure ----------------------------------------------------------------------
inv = ~tf
det_px, ref_px = to_px(det_xy, inv), to_px(ref_xy, inv)
fig, axes = plt.subplots(1, 3, figsize=(11.4, 4.1))
panel(axes[0], img, f"RGB orthophoto, {res:g} m")
panel(axes[1], img, f"{n_det} points by confidence, {n_ref} reference trees")
axes[1].scatter(ref_px[:, 0], ref_px[:, 1], s=90, facecolors="none", edgecolors="white", linewidths=1.3, zorder=3)
sc = axes[1].scatter(det_px[:, 0], det_px[:, 1], s=26, c=p, cmap=CONF, vmin=threshold, vmax=1.0,
                     edgecolors=INK, linewidths=0.6, zorder=4)
panel(axes[2], img, f"{n_grown} crowns grown from the points")
for ring in rings:
    axes[2].add_patch(Polygon(to_px(ring, inv), closed=True, fill=False, ec=ORANGE, lw=1.1))
fig.subplots_adjust(wspace=0.05)
cb = fig.colorbar(sc, ax=axes, fraction=0.018, pad=0.012, shrink=0.82)
cb.set_label("confidence p", fontsize=9, color=MUTED)
cb.ax.tick_params(labelsize=8, colors=MUTED)
cb.outline.set_edgecolor("#d9d9d9")
fig.savefig(os.path.join(HERE, "detect_grow.png"), dpi=160, bbox_inches="tight", facecolor="white",
            metadata={"Author": "Igor Pawelec", "Software": None})
print("written: www/detect_grow.png")
