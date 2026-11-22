"""Shared helpers for the algorithm classes: the dependency gate, the JIT
warm-up, the progress adapter, the vector-input and library-log helpers and
the advanced-parameter flag."""
import contextlib
import logging
import threading
import os

from qgis.core import QgsProcessingException

from ..deps import ensure_dependencies, manual_hint

_WARMED = False
MODES = ["auto: read the band order from the pixels (4 bands = RGB+NIR, 3 bands = CIR or RGB; the log says which)",
         "rgbn: the bands are R, G, B, NIR",
         "cir: the bands are NIR, R, G (colour infrared)",
         "rgb: the bands are R, G, B, no infrared"]
MODE_KEYS = [None, "rgbn", "cir", "rgb"]
SCENE_NORM_OPTIONS = ["auto: normalise as the model was trained (recommended)",
                      "off: raw spectral values (only for a model trained without normalisation)"]
SCENE_NORM_KEYS = ["auto", "off"]
RADIOMETRY_OPTIONS = ["off: the orthophoto as it is (run this first)",
                      "auto: stretch a hazy or flat scene onto the range the model knows, only when it is one",
                      "match: always stretch every band onto that range"]
RADIOMETRY_KEYS = ["off", "auto", "match"]


def hp(param, text):
    """Attach a per-parameter help text (the tooltip / help panel of the dialog, QGIS >= 3.16)."""
    if hasattr(param, "setHelp"):
        param.setHelp(text)
    return param


def warm_jit(feedback=None):
    """Compile the adaptel kernels here, on the main thread.

    **Call this from prepareAlgorithm, never from processAlgorithm.**
    pygeoadaptels computes inside ``@njit(cache=True)`` functions; compiling
    them on the worker thread Processing runs on takes QGIS down with an
    access violation, and installing the plugin from a zip wipes the compiled
    cache, so every update arms that crash. ``prepareAlgorithm`` runs on the
    main thread before the task starts. Runs once per session, never fatal.
    """
    global _WARMED
    if _WARMED:
        return
    try:
        import contextlib
        import io

        import numpy as np

        from pygeoadaptels import adaptels_from_array
    except Exception:
        return
    if feedback is not None:
        feedback.pushInfo("Preparing the compute kernels (first run after an update only)...")
    data = np.zeros((3, 8, 8), dtype=np.float64)
    data[:, 2:5, 2:5] = 100.0
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            adaptels_from_array(data, threshold=10.0)
    except Exception as exc:
        if feedback is not None:
            feedback.pushInfo(f"Kernel warm-up skipped: {exc}")
    _WARMED = True


def require_packages(feedback):
    ok, missing = ensure_dependencies(feedback)
    if not ok:
        raise QgsProcessingException(
            "This algorithm needs the Python packages: " + ", ".join(missing)
            + ".\nInstall them into QGIS's own Python and restart QGIS:\n  " + manual_hint())
    check_session_packages(feedback)


def check_session_packages(feedback):
    """Log which copy of each bundled package this session actually runs,
    and refuse to run stale code.

    When the plugin's files are replaced under a running QGIS (a zip
    installed, or the folder copied over, without a restart), sys.modules
    keeps the previous version and a run silently uses it: the log then
    claims the new plugin while the old package computes. Seen with 0.4.1:
    the session kept pygeosnag 0.3.0, whose auto band mode read a CIR
    orthophoto as RGB. The version in memory is compared with
    vendor/VERSIONS.txt; a mismatch is an error naming the fix.
    """
    import importlib

    from .. import vendor_loader
    bundled = vendor_loader.vendored_versions()
    root = os.path.abspath(vendor_loader.VENDOR_DIR)
    lines, stale = [], []
    for name in vendor_loader.VENDORED:
        try:
            mod = importlib.import_module(name)
        except Exception as exc:                  # noqa: BLE001 -- reported, not fatal here
            lines.append(f"{name}: not importable ({exc})")
            continue
        origin = os.path.abspath(getattr(mod, "__file__", "") or "")
        ver = str(getattr(mod, "__version__", "?"))
        where = "bundled" if origin.startswith(root) else f"installed, {os.path.dirname(origin)}"
        lines.append(f"{name} {ver} ({where})")
        if where == "bundled" and bundled.get(name) and bundled[name] != ver:
            stale.append(f"{name} {ver} in memory, {bundled[name]} in the plugin folder")
    if feedback is not None:
        feedback.pushInfo("Running: " + ", ".join(lines))
    if stale:
        raise QgsProcessingException(
            "This QGIS session still runs the previous plugin code (" + "; ".join(stale)
            + "). The plugin was updated while QGIS was open; restart QGIS and run again.")


SETTINGS_KEY = "geosnag/assets_dir"


def set_assets_dir(path, feedback=None):
    """Point pygeosnag at a local model directory instead of the download cache.

    A folder given once is remembered in the QGIS settings, so the parameter
    can stay empty on later runs. Order: the parameter, then the remembered
    folder, then whatever PYGEOSNAG_ASSETS already says, then the download
    cache (which needs the GitHub release to exist).
    """
    try:
        from qgis.core import QgsSettings
        settings = QgsSettings()
    except Exception:
        settings = None
    if path:
        if settings is not None:
            settings.setValue(SETTINGS_KEY, path)
    elif settings is not None:
        saved = settings.value(SETTINGS_KEY, "", type=str)
        if saved and os.path.isdir(saved):
            path = saved
    if path:
        os.environ["PYGEOSNAG_ASSETS"] = path
        if feedback is not None:
            feedback.pushInfo(f"Models from {path}")
    elif feedback is not None:
        feedback.pushInfo("Models from the download cache (the geosnag GitHub release); "
                          "give a local models folder under Advanced if that fails.")
    return path


def report_models(feedback, threshold, mode=None):
    """Which models a run will use and their operating point (the band mode's own when
    the manifest has one), with a note when the chosen threshold differs from it."""
    try:
        from pygeosnag import assets
        man = assets.manifest(quiet=True)
        opd = man.get("operating_point", {})
        common = float(opd.get("threshold", 0.5))
        per = {k: float(v) for k, v in (opd.get("per_mode") or {}).items()}
        # With band mode auto the mode is only known once the raster is read,
        # so every operating point the run may end up on is named: assets-v3
        # has 0.7 and, for rgb, 0.6. Naming 0.7 alone made a threshold of 0.6
        # on an RGB image "differ from the operating point" it was equal to.
        if mode:
            ops = {mode: per.get(mode, common)}
            text = f"p >= {ops[mode]:g}" + (f" for mode {mode}" if mode in per else "")
        else:
            ops = dict({"": common}, **per)
            text = f"p >= {common:g}" + "".join(f", {k} p >= {v:g}" for k, v in sorted(per.items()))
            text += " (band mode auto: the mode decides, see the first pygeosnag line)"
        feedback.pushInfo(f"Models: {man.get('release', assets.RELEASE)} from {assets.assets_dir()}, operating point {text}")
        if threshold is None:
            feedback.pushInfo("Threshold 0: the operating point of the band mode is used")
        elif all(abs(float(threshold) - v) > 1e-9 for v in ops.values()):
            feedback.pushInfo(f"Threshold {float(threshold):g} differs from the models' operating point"
                              f"{'s' if len(ops) > 1 else ''} "
                              + ", ".join(f"{(k + ' ') if k else ''}{v:g}" for k, v in sorted(ops.items())))
        _report_sklearn(feedback, str(man.get("sklearn") or ""))
    except Exception as exc:                      # detect fetches the manifest again and reports properly
        feedback.pushInfo(f"Models: manifest not readable yet ({exc})")


def _report_sklearn(feedback, made_with):
    """Say so when the scikit-learn of this run is not the one the models name.

    The forests are pickles; scikit-learn loads them across close versions
    with a warning of its own and promises nothing. The plugin installs the
    version in ``deps.PINNED``; a manifest that names another one means the
    models changed and the pin did not.
    """
    if not made_with:
        return
    from ..deps import PINNED, installed_version
    have, _ = installed_version("sklearn")
    if have and have != made_with:
        feedback.pushWarning(f"The models were made with scikit-learn {made_with}; this run uses {have}.")
    if PINNED.get("sklearn") and PINNED["sklearn"] != made_with:
        feedback.pushInfo(f"The plugin installs scikit-learn {PINNED['sklearn']} but these models name "
                          f"{made_with}: the plugin is older or newer than the models.")


def _release():
    try:
        from pygeosnag import assets
        return assets.RELEASE
    except Exception:
        return "assets-v3"


def package_error(e):
    """A pygeosnag RuntimeError as a readable Processing error."""
    msg = str(e)
    if any(k in msg for k in ("could not download", "HTTP Error", "URLError", "urlopen", "Not Found")):
        msg += ("\n\nThe models could not be downloaded (the geosnag GitHub release is not published "
                "yet, or the machine is offline). Copy manifest.json and the model files into "
                f"{os.path.join(os.path.expanduser('~'), '.cache', 'pygeosnag', _release())} -- that is "
                "where pygeosnag looks without any setting -- or open Advanced and set 'Local models "
                "folder' to the folder that holds them; it is remembered for later runs.")
    return QgsProcessingException(msg)


def progress_adapter(feedback):
    """pygeosnag's progress callback wired to the Processing feedback.

    Returning False cancels the run inside the package, which raises; the
    algorithm turns that into a clean Processing cancel.
    """
    def cb(fraction, message):
        try:
            feedback.setProgress(int(round(100 * float(fraction))))
            if message:
                feedback.pushInfo(message)
        except Exception:
            pass
        return not feedback.isCanceled()
    return cb


def source_path(layer):
    """File path of a layer's source, without the ``|layername=`` suffix
    pygeosnag cannot open (rasters) -- vector sources keep it, pygeosnag's
    point reader understands it."""
    src = layer.source()
    if "|" in src:
        src = src.split("|", 1)[0]
    return src


# Runs overlap: two dialogs working in the background, or this plugin and its
# sibling (GeoSnag, GeoAdaptels + GeoPalette), which does the same to the same
# two loggers from its own copy of this routine. So what a run changes is
# counted on the logger itself, under names both plugins use: the first run to
# arrive stops the propagation and notes how it was, the last one to leave puts
# it back. Saved and restored per run, the run that left first switched the
# propagation back on under the one still working, and that one then left it
# off for the rest of the session.
_RUN_LOCK = "_geo_plugins_run_lock"
_RUN_DEPTH = "_geo_plugins_run_depth"
_RUN_PROPAGATE = "_geo_plugins_run_propagate"


def _run_lock(logger):
    return logger.__dict__.setdefault(_RUN_LOCK, threading.Lock())


class _ToMessageLog(logging.Handler):
    """What a library logs, into the Log Messages panel under the plugin's name."""

    def emit(self, record):
        try:
            from qgis.core import QgsMessageLog
            QgsMessageLog.logMessage(f"{record.name}: {record.getMessage()}", "GeoSnag")
        except Exception:
            pass


@contextlib.contextmanager
def library_logs(names=("rasterio", "fiona")):
    """Keep what rasterio and fiona log during a run away from the root logger.

    GDAL's warnings reach Python as log records of rasterio; one arrives with
    the first polygonisation of every session ("'Memory' driver is deprecated
    since GDAL 3.11"), which here is the first Grow crowns. The two libraries
    have no handler of their own, so the record travels up to the root logger,
    and in a QGIS on Windows the root logger may hold a handler that cannot
    write: a plugin that calls ``logging.basicConfig()`` while QGIS starts gets
    a stream handler on ``sys.stderr``, which is None at that moment and stays
    None in the handler. Every record that reaches it raises inside
    ``logging``, which prints "--- Logging error ---" and a traceback through
    this plugin's source into the Python console. The crowns are fine; it
    reads as a crash.

    For the length of a run the two loggers get a handler that writes to the
    Log Messages panel and stop propagating. Both are put back when the last
    run that asked for this has finished, so nothing changes for anything
    else that uses them. The same routine as in
    the GeoAdaptels + GeoPalette plugin.
    """
    handler = _ToMessageLog()
    loggers = [logging.getLogger(name) for name in names]
    for logger in loggers:
        with _run_lock(logger):
            depth = getattr(logger, _RUN_DEPTH, 0)
            if depth == 0:
                setattr(logger, _RUN_PROPAGATE, logger.propagate)
                logger.propagate = False
            setattr(logger, _RUN_DEPTH, depth + 1)
            logger.addHandler(handler)
    try:
        yield
    finally:
        for logger in loggers:
            with _run_lock(logger):
                logger.removeHandler(handler)
                depth = getattr(logger, _RUN_DEPTH, 1) - 1
                setattr(logger, _RUN_DEPTH, max(depth, 0))
                if depth <= 0:
                    logger.propagate = getattr(logger, _RUN_PROPAGATE, True)


def vector_source(algorithm, parameters, name, context, feedback):
    """``(path, layer name)`` of a vector parameter, as a file pygeosnag can open.

    pygeosnag reads its points and its stand polygons from a path. A layer
    that lives in a GeoPackage or a shapefile comes back as that file and is
    not copied. A temporary scratch layer has no file at all -- its source
    reads ``Point?crs=EPSG:2180&field=...`` -- and a layer with a filter or
    with "selected features only" has a file that holds more than the
    operator sees. For those QGIS writes what is asked for into a temporary
    GeoPackage and that is what the package gets. Until 0.5.5 the layer's
    source string went to the package as it was, and a layer clicked in QGIS,
    which the help recommends, failed with "Failed to open dataset".

    The layer name is None for a file with a single layer.
    """
    path, layer_name = algorithm.parameterAsCompatibleSourceLayerPathAndLayerName(
        parameters, name, context, ["gpkg", "shp"], "gpkg", feedback)
    if not path:
        raise QgsProcessingException(f"The layer given as {name} could not be read.")
    return path, (layer_name or None)


def advanced(param):
    try:
        from qgis.core import QgsProcessingParameterDefinition
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
    except Exception:
        pass
    return param
