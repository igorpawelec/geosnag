"""The plugin's own logic that needs neither a QGIS nor the models: how a vector
parameter becomes a file the package can open, what the log says about the
operating point, and the markup of the help texts. Runs against tests/qgis_stub.
"""
import os
import sys
import types

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (os.path.join(HERE, "qgis_stub"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from qgis.core import QgsProcessingException  # noqa: E402

from geosnag_plugin.algorithms import _base  # noqa: E402


# -- a vector parameter reaches the package as a file ---------------------------

class _Algorithm:
    """The one call vector_source makes on a QgsProcessingAlgorithm."""

    def __init__(self, answer):
        self.answer = answer
        self.asked = None

    def parameterAsCompatibleSourceLayerPathAndLayerName(self, parameters, name, context, formats, preferred, feedback):
        self.asked = (name, list(formats), preferred)
        return self.answer


def test_a_layer_in_a_geopackage_keeps_its_file_and_layer_name():
    alg = _Algorithm(("D:/data/trees.gpkg", "dead_trees"))
    assert _base.vector_source(alg, {}, "POINTS", None, None) == ("D:/data/trees.gpkg", "dead_trees")
    # GeoPackage and shapefile are what pygeosnag opens; anything else QGIS converts
    assert alg.asked == ("POINTS", ["gpkg", "shp"], "gpkg")


def test_a_scratch_layer_arrives_as_the_file_qgis_wrote_for_it():
    """A temporary scratch layer has no file: its source reads
    ``Point?crs=EPSG:2180&field=id:integer&uid={...}``, which went to the
    package as a path until 0.5.5 and failed with "Failed to open dataset".
    QGIS exports such a layer and answers with the export."""
    alg = _Algorithm(("C:/Temp/processing_x/POINTS.gpkg", ""))
    assert _base.vector_source(alg, {}, "POINTS", None, None) == ("C:/Temp/processing_x/POINTS.gpkg", None)


def test_a_layer_that_cannot_be_read_is_a_message():
    with pytest.raises(QgsProcessingException) as caught:
        _base.vector_source(_Algorithm(("", "")), {}, "STANDS", None, None)
    assert "STANDS" in str(caught.value)


# -- what the log says about the operating point --------------------------------

class _Feedback:
    def __init__(self):
        self.lines = []

    def pushInfo(self, text):
        self.lines.append(text)

    def pushWarning(self, text):
        self.lines.append("WARNING " + text)


@pytest.fixture
def assets_v3(monkeypatch):
    """A pygeosnag.assets that answers like assets-v3: 0.7, and 0.6 for rgb."""
    assets = types.ModuleType("pygeosnag.assets")
    assets.RELEASE = "assets-v3"
    assets.assets_dir = lambda: "C:/cache/assets-v3"
    assets.manifest = lambda quiet=True: {"release": "assets-v3", "sklearn": "",
                                          "operating_point": {"threshold": 0.7, "per_mode": {"rgb": 0.6}}}
    package = types.ModuleType("pygeosnag")
    package.assets = assets
    monkeypatch.setitem(sys.modules, "pygeosnag", package)
    monkeypatch.setitem(sys.modules, "pygeosnag.assets", assets)


def _report(threshold, mode):
    fb = _Feedback()
    _base.report_models(fb, threshold, mode)
    return fb.lines


def test_auto_mode_names_every_operating_point(assets_v3):
    lines = _report(None, None)
    assert "p >= 0.7, rgb p >= 0.6" in lines[0] and "band mode auto" in lines[0]
    assert lines[1] == "Threshold 0: the operating point of the band mode is used"


@pytest.mark.parametrize("threshold", [0.6, 0.7])
def test_auto_mode_does_not_call_an_operating_point_different(assets_v3, threshold):
    """0.6 is the operating point of an RGB image. In auto mode the log named
    0.7 alone and said that 0.6 "differs from the models' operating point"."""
    assert not [line for line in _report(threshold, None) if "differs" in line]


def test_auto_mode_names_them_all_when_the_threshold_is_none_of_them(assets_v3):
    differs = [line for line in _report(0.65, None) if "differs" in line]
    assert differs == ["Threshold 0.65 differs from the models' operating points 0.7, rgb 0.6"]


def test_a_given_mode_is_held_against_its_own_operating_point(assets_v3):
    assert "p >= 0.6 for mode rgb" in _report(0.6, "rgb")[0]
    assert not [line for line in _report(0.6, "rgb") if "differs" in line]
    assert [line for line in _report(0.7, "rgb") if "differs" in line] == [
        "Threshold 0.7 differs from the models' operating point rgb 0.6"]
    assert "p >= 0.7" in _report(0.7, "rgbn")[0]
    assert not [line for line in _report(0.7, "rgbn") if "differs" in line]


# -- help texts -------------------------------------------------------------------

def test_help_does_not_use_the_b_tag():
    """QGIS gives the help panel of a Processing dialog its own style sheet with
    ``b { color: #333333; }``: dark grey on the dark background of a dark
    theme. ``<strong>`` is as bold and keeps the paragraph's colour."""
    from geosnag_plugin.algorithms.detect import DetectDeadTreesAlgorithm
    from geosnag_plugin.algorithms.grow import GrowCrownsAlgorithm
    for cls in (DetectDeadTreesAlgorithm, GrowCrownsAlgorithm):
        text = cls().shortHelpString()
        assert "<b>" not in text and "</b>" not in text, cls.__name__
        assert text.count("<strong>") == text.count("</strong>") > 0, cls.__name__


# -- a library's log record does not reach a root logger that cannot write ---------

def test_library_records_stay_away_from_the_root_logger_during_a_run(capsys):
    """What happens in a QGIS on Windows with a plugin that called
    ``logging.basicConfig()`` at start-up: the root logger holds a stream
    handler whose stream is None, and every record that reaches it makes
    ``logging`` print "--- Logging error ---" with a traceback through the
    code that was running. Grow crowns was that code: its first
    polygonisation of a session makes GDAL warn through rasterio."""
    import logging

    root = logging.getLogger()
    broken = logging.StreamHandler()
    broken.stream = None                              # sys.stderr was None when the handler was made
    root.addHandler(broken)
    rasterio_env = logging.getLogger("rasterio._env")
    state = [(logging.getLogger(n).propagate, list(logging.getLogger(n).handlers)) for n in ("rasterio", "fiona")]
    try:
        with _base.library_logs():
            rasterio_env.warning("%s in %s", "CPLE_AppDefined", "'Memory' driver is deprecated")
            assert logging.getLogger("rasterio").propagate is False
        inside = capsys.readouterr().err
        assert [(logging.getLogger(n).propagate, list(logging.getLogger(n).handlers)) for n in ("rasterio", "fiona")] == state
        rasterio_env.warning("%s in %s", "CPLE_AppDefined", "the same record, outside a run")
        outside = capsys.readouterr().err
    finally:
        root.removeHandler(broken)
    assert "Logging error" not in inside
    assert "Logging error" in outside                 # the test set-up does reproduce the fault


def test_library_logging_is_put_back_when_the_run_fails():
    import logging
    state = [(logging.getLogger(n).propagate, list(logging.getLogger(n).handlers)) for n in ("rasterio", "fiona")]
    with pytest.raises(RuntimeError):
        with _base.library_logs():
            raise RuntimeError("pygeosnag: cancelled")
    assert [(logging.getLogger(n).propagate, list(logging.getLogger(n).handlers)) for n in ("rasterio", "fiona")] == state


def test_overlapping_runs_leave_the_loggers_as_they_found_them():
    """Two runs at once, the first to start being the first to finish. Each used
    to save and restore the propagation on its own: the first switched it back
    on under the second, and the second then left it off for good."""
    import logging
    names = ("rasterio", "fiona")
    state = [(logging.getLogger(n).propagate, list(logging.getLogger(n).handlers)) for n in names]
    first, second = _base.library_logs(), _base.library_logs()
    first.__enter__()
    second.__enter__()
    assert all(logging.getLogger(n).propagate is False for n in names)
    first.__exit__(None, None, None)
    assert all(logging.getLogger(n).propagate is False for n in names)      # the second is still running
    second.__exit__(None, None, None)
    assert [(logging.getLogger(n).propagate, list(logging.getLogger(n).handlers)) for n in names] == state
    # and once more, to see that nothing is left counted
    with _base.library_logs():
        assert all(logging.getLogger(n).propagate is False for n in names)
    assert [(logging.getLogger(n).propagate, list(logging.getLogger(n).handlers)) for n in names] == state
