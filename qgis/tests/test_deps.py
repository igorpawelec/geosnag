"""The dependency bootstrap, without a QGIS and without pip.

What is checked: scikit-learn is asked for at the version the models were
made with, a copy in libs/ in another version is found without importing it,
and the copies of interpreter-provided packages in libs/ are removed while
everything else in libs/ stays.
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

from geosnag_plugin import deps  # noqa: E402


def _package(folder, name, version=None):
    """A package on disk: ``folder/name/__init__.py``, optionally naming a version."""
    d = folder / name
    d.mkdir(parents=True)
    (d / "__init__.py").write_text(f'__version__ = "{version}"\n' if version else "", encoding="utf-8")
    return d


@pytest.fixture
def libs(tmp_path, monkeypatch):
    """An empty libs/ folder at the end of sys.path, as vendor_loader puts it."""
    folder = tmp_path / "libs"
    folder.mkdir()
    monkeypatch.setattr(deps, "LIBS_DIR", str(folder))
    monkeypatch.syspath_prepend(str(tmp_path / "unused"))        # keeps monkeypatch restoring sys.path
    sys.path.append(str(folder))
    yield folder
    for name in ("fakepinned", "fakeshadow", "fakeown"):
        sys.modules.pop(name, None)


def test_scikit_learn_is_asked_for_at_the_models_version():
    pin = deps.PINNED["sklearn"]
    assert f"scikit-learn=={pin}" in deps._install_specs()
    assert f"scikit-learn=={pin}" in deps._install_specs(["sklearn"])
    assert deps._install_specs(["sklearn"], pinned=False)[0] == "scikit-learn"
    assert f"scikit-learn=={pin}" in deps.manual_hint()


def test_the_pin_is_a_full_version():
    # "1.8" would let pip pick 1.8.1, and scikit-learn warns on any version but the pickle's own
    assert deps.PINNED["sklearn"].count(".") == 2


def test_installed_version_reads_the_file_and_does_not_import(libs):
    _package(libs, "fakepinned", "1.9.0")
    assert deps.installed_version("fakepinned") == ("1.9.0", str(libs / "fakepinned"))
    assert "fakepinned" not in sys.modules
    assert deps.installed_version("no_such_module_xyz") == (None, None)
    _package(libs, "fakeown")
    assert deps.installed_version("fakeown") == (None, str(libs / "fakeown"))


def test_another_version_in_libs_is_replaceable(libs, monkeypatch):
    monkeypatch.setattr(deps, "PINNED", {"fakepinned": "1.8.0"})
    _package(libs, "fakepinned", "1.9.0")
    found, wanted, folder, replaceable = deps.wrong_pins()["fakepinned"]
    assert (found, wanted, replaceable) == ("1.9.0", "1.8.0", True)
    assert folder == str(libs / "fakepinned")


def test_the_pinned_version_in_libs_is_left_alone(libs, monkeypatch):
    monkeypatch.setattr(deps, "PINNED", {"fakepinned": "1.8.0"})
    _package(libs, "fakepinned", "1.8.0")
    assert deps.wrong_pins() == {}


def test_another_version_outside_libs_is_not_replaceable(libs, tmp_path, monkeypatch):
    monkeypatch.setattr(deps, "PINNED", {"fakepinned": "1.8.0"})
    elsewhere = tmp_path / "site"
    _package(elsewhere, "fakepinned", "1.9.0")
    monkeypatch.syspath_prepend(str(elsewhere))
    assert deps.wrong_pins()["fakepinned"][3] is False


def test_a_loaded_copy_is_not_replaceable(libs, monkeypatch):
    monkeypatch.setattr(deps, "PINNED", {"fakepinned": "1.8.0"})
    folder = _package(libs, "fakepinned", "1.9.0")
    loaded = types.ModuleType("fakepinned")
    loaded.__file__ = str(folder / "__init__.py")
    monkeypatch.setitem(sys.modules, "fakepinned", loaded)
    found, wanted, _, replaceable = deps.wrong_pins()["fakepinned"]
    assert (found, wanted, replaceable) == ("1.9.0", "1.8.0", False)


def test_copies_of_what_the_interpreter_provides_are_removed(libs, tmp_path, monkeypatch):
    interpreter = tmp_path / "interpreter"
    _package(interpreter / "site-packages", "fakeshadow", "2.4.6")
    monkeypatch.setattr(deps, "_interpreter_roots", lambda: [str(interpreter)])
    monkeypatch.syspath_prepend(str(interpreter / "site-packages"))
    _package(libs, "fakeshadow", "2.5.5")
    (libs / "fakeshadow.libs").mkdir()
    (libs / "fakeshadow-2.5.5.dist-info").mkdir()
    _package(libs, "fakeown", "1.0")                             # only libs/ has this one
    (libs / "fakeown-1.0.dist-info").mkdir()

    assert deps.prune_shadowed(names=("fakeshadow", "fakeown")) == ["fakeshadow"]
    assert sorted(p.name for p in libs.iterdir()) == ["fakeown", "fakeown-1.0.dist-info"]
    assert deps.installed_version("fakeshadow")[0] == "2.4.6"
    assert deps.prune_shadowed(names=("fakeshadow", "fakeown")) == []      # nothing left to do


def test_a_copy_shadowed_by_another_plugin_stays(libs, tmp_path, monkeypatch):
    # what another plugin provides can go away with that plugin; only the interpreter's own counts
    other = tmp_path / "other_plugin" / "libs"
    _package(other, "fakeshadow", "2.4.6")
    monkeypatch.setattr(deps, "_interpreter_roots", lambda: [str(tmp_path / "interpreter")])
    monkeypatch.syspath_prepend(str(other))
    _package(libs, "fakeshadow", "2.5.5")
    assert deps.prune_shadowed(names=("fakeshadow",)) == []
    assert (libs / "fakeshadow").is_dir()


def test_the_metadata_of_the_replaced_version_goes(libs):
    # written in this order: 1.9.0 was there, pip then put 1.8.0 in its place
    for age, name in enumerate(("scikit_learn-1.9.0.dist-info", "scikit_learn-1.8.0.dist-info",
                                "threadpoolctl-3.6.0.dist-info", "threadpoolctl-3.8.0.dist-info",
                                "joblib-1.6.0.dist-info")):
        (libs / name).mkdir()
        os.utime(libs / name, (1_700_000_000 + age, 1_700_000_000 + age))
    deps._drop_stale_dist_info()
    assert sorted(p.name for p in libs.iterdir()) == [
        "joblib-1.6.0.dist-info", "scikit_learn-1.8.0.dist-info", "threadpoolctl-3.8.0.dist-info"]
