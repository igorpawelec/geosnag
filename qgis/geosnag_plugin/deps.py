"""Dependency bootstrap -- the single highest-risk piece of this plugin.

QGIS ships its own Python, and things have to be importable *from that
interpreter*. The three pure-Python packages (pygeosnag, pygeoadaptels,
pygeopalette) ride along inside the plugin (see ``vendor_loader``), so this
module only ever has to fetch the ones that carry compiled binaries.

**Where they go: a plugin-private folder, never the user site.** The first
version used ``pip install --user``, as the GeoAdaptels + GeoPalette plugin
does. That writes into ``%APPDATA%/Python/Python312/site-packages``, which
*every* Python 3.12 on the machine reads before its own site-packages --
conda environments included. The plugin's scikit-learn 1.9 then shadowed a
conda environment's 1.8 and broke it (a missing dependency), and the older
plugin's numba and rasterio had been shadowing that environment's for
months without anyone noticing. So the binary dependencies are installed
with ``pip --target`` into ``<plugin>/libs``, which only this plugin puts on
``sys.path``. Reinstalling the plugin zip keeps the folder (QGIS replaces
the files it ships, not the folder), and deleting it just triggers a fresh
install.

Other lessons kept from the older plugin, learned against QGIS 3.40/3.44
(Python 3.12) on Windows: ``sys.executable`` is a launcher, not the
interpreter (the real one sits at ``sys.prefix``); recent rasterio/fiona
drag in numpy 2.x, which breaks numba and scipy on the numpy 1.26 that QGIS
ships, so the installs are pinned to keep the interpreter's numpy; pip's
real error is captured and reported; PEP 668 externally-managed
interpreters are retried with ``--break-system-packages``.

**scikit-learn is pinned to the version the models were made with.** The
forests are pickles, and scikit-learn promises a pickle only to the version
that wrote it. Unpinned, pip installed the newest release (1.9.0 against
models pickled with 1.8.0), which loaded them with a warning and no
guarantee for the next release. A copy in libs/ in another version is
replaced on the next run; where the pinned version does not exist for the
interpreter (an older QGIS), pip's own choice is taken and the log says so.

**libs/ holds only what nothing else provides.** ``pip --target`` ignores
what the interpreter has and puts its own copy of every dependency into
libs/: numpy and scipy came along with scikit-learn and numba, 150 MB that
Python never imports, because libs/ is appended to ``sys.path`` behind the
interpreter's own site-packages. Those copies are removed after an install
and at the start of a run.

Copyright (C) 2026 Igor Pawelec. Licence: GPLv3.
"""
import importlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys

from .vendor_loader import LIBS_DIR

# module name -> pip name. The vendored pure-Python packages are checked but
# never handed to pip.
REQUIRED = {
    "pygeosnag": None, "pygeoadaptels": None, "pygeopalette": None,
    "numba": "numba", "scipy": "scipy", "sklearn": "scikit-learn", "joblib": "joblib",
    "rasterio": "rasterio", "fiona": "fiona", "shapely": "shapely",
}

# module name -> the exact version pip is asked for. scikit-learn: the value
# of "sklearn" in manifest.json of the model release pygeosnag points at
# (pygeosnag.assets.RELEASE, assets-v3). New models, new pin: change them
# together; a run says so in the log when the two disagree.
PINNED = {"sklearn": "1.8.0"}

# Packages the interpreter of QGIS provides itself. Their copies in libs/ are
# never imported and are removed (see the module docstring).
SHADOWED = ("numpy", "scipy")


def _numpy_major():
    try:
        import numpy
        return int(numpy.__version__.split(".")[0])
    except Exception:
        return 1


def _install_specs(modules=None, pinned=True):
    """pip specs for the binary dependencies: scikit-learn at the models' version,
    the rest pinned to the interpreter's numpy line."""
    pins = {"rasterio": "rasterio<1.4", "fiona": "fiona<1.10"} if _numpy_major() < 2 else {}
    wanted = [m for m in (modules or REQUIRED) if REQUIRED.get(m)]
    specs = []
    for m in wanted:
        name = REQUIRED[m]
        specs.append(f"{name}=={PINNED[m]}" if pinned and m in PINNED else pins.get(name, name))
    if _numpy_major() < 2 and specs:
        specs.append("numpy<2")           # keep pip from putting a numpy 2 into libs/ underneath numba
    return specs


def _same_or_under(path, root):
    """True when ``path`` is ``root`` or lies inside it. Real paths are compared:
    QGIS on Windows reports its prefix in the 8.3 short form (C:\\PROGRA~1\\...)."""
    try:
        p = os.path.normcase(os.path.realpath(path))
        r = os.path.normcase(os.path.realpath(root))
    except OSError:
        return False
    return p == r or p.startswith(r.rstrip("\\/") + os.sep)


def _interpreter_roots():
    return [r for r in {sys.prefix, sys.base_prefix, sys.exec_prefix} if r]


def _origin(name):
    """The file ``name`` is imported from, or would be, without importing it; None when not found."""
    loaded = getattr(sys.modules.get(name), "__file__", None)
    if loaded and os.path.isfile(loaded):
        return loaded                             # find_spec trusts a loaded module's __spec__, which may be absent
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError):
        return None
    origin = getattr(spec, "origin", None)
    return origin if origin and os.path.isfile(origin) else None


def installed_version(name):
    """``(version, folder)`` of the copy of ``name`` Python would import, read from
    its ``__init__`` without importing it (an imported package cannot be replaced
    on Windows). ``(None, None)`` when it is not found, ``(None, folder)`` when
    the file names no version."""
    origin = _origin(name)
    if origin is None:
        return None, None
    folder = os.path.dirname(os.path.abspath(origin))
    try:
        with open(origin, encoding="utf-8", errors="replace") as fh:
            m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', fh.read(), re.M)
    except OSError:
        return None, folder
    return (m.group(1) if m else None), folder


def wrong_pins():
    """Pinned packages found in another version: ``{module: (found, wanted, folder, replaceable)}``.

    ``replaceable`` is True for a copy in libs/ that this session has not
    imported: only that one can be swapped by pip, here and now.
    """
    importlib.invalidate_caches()                 # a folder pip filled a moment ago is otherwise not seen
    out = {}
    for mod, wanted in PINNED.items():
        found, folder = installed_version(mod)
        if found and found != wanted:
            out[mod] = (found, wanted, folder, _same_or_under(folder, LIBS_DIR) and mod not in sys.modules)
    return out


def _drop_stale_dist_info():
    """pip --target leaves the metadata folder of every version it replaced; keep the newest.

    The package folder itself is replaced, so two ``<name>-<version>.dist-info``
    for one name mean the older one describes files that are gone.
    """
    try:
        entries = [e for e in os.listdir(LIBS_DIR) if e.lower().endswith(".dist-info") and "-" in e]
    except OSError:
        return
    by_name = {}
    for entry in entries:
        by_name.setdefault(entry.split("-", 1)[0].lower(), []).append(entry)
    for group in by_name.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda e: os.path.getmtime(os.path.join(LIBS_DIR, e)))
        for entry in group[:-1]:
            shutil.rmtree(os.path.join(LIBS_DIR, entry), ignore_errors=True)


def prune_shadowed(feedback=None, names=SHADOWED):
    """Remove from libs/ the copies of packages the interpreter provides itself.

    A copy goes only when Python would import the package from the
    interpreter's own folders, which come before libs/ on ``sys.path``: the
    copy is then never the one in use, and removing it changes nothing but
    the size of the folder. Returns the names removed.
    """
    removed = []
    if not os.path.isdir(LIBS_DIR):
        return removed
    for name in names:
        if not os.path.isdir(os.path.join(LIBS_DIR, name)):
            continue
        origin = _origin(name)
        if origin is None or _same_or_under(origin, LIBS_DIR):
            continue                              # the copy in libs/ is the one in use
        if not any(_same_or_under(origin, root) for root in _interpreter_roots()):
            continue                              # provided by something that can go away again
        loaded = getattr(sys.modules.get(name), "__file__", None)
        if loaded and _same_or_under(loaded, LIBS_DIR):
            continue
        for entry in os.listdir(LIBS_DIR):
            low = entry.lower()
            if low in (name, name + ".libs") or (low.startswith(name + "-") and low.endswith(".dist-info")):
                shutil.rmtree(os.path.join(LIBS_DIR, entry), ignore_errors=True)
        removed.append(name)
    if removed and feedback is not None:
        feedback.pushInfo("Removed from the plugin's libs folder the copies of " + ", ".join(removed)
                          + " that pip put there: QGIS has its own and those are the ones in use.")
    return removed


def _qgis_python():
    names = ("python.exe", "python3.exe", "python3", "python")
    for base in (sys.prefix, os.path.join(sys.prefix, "bin")):
        for name in names:
            p = os.path.join(base, name)
            if os.path.exists(p):
                return p
    return sys.executable


def _importable(name):
    """``(True, "")`` when the module can be imported, else ``(False, why)``.

    ``find_spec`` alone is not trusted: in a long QGIS session it answered
    None for scikit-learn and joblib that sat in libs/ and imported fine --
    a FileFinder for libs/ or another plugin's finder holding a stale
    answer until the import caches were cleared (which pip's post-install
    step did, so every session paid a pip run "for the first time"). An
    import that succeeds is the last word; one that fails gives the reason
    for the log.
    """
    try:
        if importlib.util.find_spec(name) is not None:
            return True, ""
        why = "find_spec found nothing on sys.path"
    except (ImportError, ValueError) as exc:
        why = f"find_spec: {exc}"
    try:
        importlib.import_module(name)
        return True, ""
    except Exception as exc:                      # noqa: BLE001 -- the reason is reported, not hidden
        return False, f"{why}; import: {type(exc).__name__}: {str(exc)[:160]}"


def missing_packages(reasons=None):
    """Names that cannot be imported; ``reasons`` (a dict) collects why."""
    importlib.invalidate_caches()
    out = []
    for m in REQUIRED:
        ok, why = _importable(m)
        if not ok:
            out.append(m)
            if reasons is not None:
                reasons[m] = why
    return out


def _pip(py, specs, extra=()):
    os.makedirs(LIBS_DIR, exist_ok=True)
    cmd = [py, "-m", "pip", "install", "--target", LIBS_DIR, "--upgrade", *extra, *specs]
    return subprocess.run(cmd, capture_output=True, text=True)


def ensure_dependencies(feedback=None, auto_install=True):
    """Return ``(ok, missing)``. Never raises; never hard-crashes the plugin."""
    from . import vendor_loader
    vendor_loader.activate(feedback)

    reasons = {}
    missing = missing_packages(reasons)
    stale = wrong_pins()
    repin = [m for m, v in stale.items() if v[3] and m not in missing]
    if feedback is not None:
        for m, (found, wanted, folder, replaceable) in stale.items():
            if not replaceable:
                feedback.pushWarning(
                    f"{REQUIRED.get(m) or m} {found} is in use ({folder}); the models were made with {wanted}. "
                    + ("It is already loaded in this session: restart QGIS and run again to have it replaced."
                       if _same_or_under(folder, LIBS_DIR) else
                       "That copy is outside the plugin's libs folder, so the plugin leaves it alone."))
    if not missing and not repin:
        _drop_stale_dist_info()
        prune_shadowed(feedback)
        return True, []
    if missing and feedback is not None:
        feedback.pushInfo("Not importable: " + "; ".join(f"{m} ({reasons.get(m, '?')})" for m in missing))
    if repin and feedback is not None:
        feedback.pushInfo("In the plugin's libs folder in another version than the models were made with: "
                          + ", ".join(f"{REQUIRED[m]} {stale[m][0]} ({stale[m][1]} wanted)" for m in repin))
    if not auto_install:
        return (not missing), missing

    to_install = [m for m in missing if REQUIRED.get(m)]
    vendored_missing = [m for m in missing if not REQUIRED.get(m)]
    if vendored_missing and feedback is not None:
        feedback.reportError(
            "These are bundled with the plugin but did not import: " + ", ".join(vendored_missing)
            + ". The plugin's vendor/ folder looks incomplete -- reinstall the plugin zip.")
    if not to_install and not repin:
        return False, missing

    py = _qgis_python()
    specs = _install_specs(to_install + repin)
    if feedback is not None:
        feedback.pushInfo(f"Installing {', '.join(specs)} into {LIBS_DIR} using {py} "
                          "(only when a package is not importable or not the version the models need; "
                          "the lines above say which)")

    def run_pip(wanted_specs):
        r = _pip(py, wanted_specs)
        if r.returncode != 0 and "externally-managed-environment" in ((r.stderr or "") + (r.stdout or "")):
            if feedback is not None:
                feedback.pushInfo("Interpreter is externally managed; retrying with --break-system-packages.")
            r = _pip(py, wanted_specs, extra=("--break-system-packages",))
        return r

    try:
        r = run_pip(specs)
        if r.returncode != 0 and any(m in PINNED for m in to_install):
            # The pinned version may not exist for this Python (an older QGIS). A
            # plugin that runs on pip's own choice beats one that does not run.
            specs = _install_specs(to_install, pinned=False)
            if feedback is not None:
                feedback.pushWarning("pip could not install the pinned versions for this Python; taking the "
                                     "versions pip offers instead: " + ", ".join(specs))
            r = run_pip(specs)
    except Exception as e:  # pragma: no cover - environment dependent
        if feedback is not None:
            feedback.reportError(f"Could not launch pip: {e}\n{manual_hint()}")
        return (not missing), missing

    if r.returncode != 0:
        if feedback is not None:
            tail = (r.stdout or "")[-2000:] + "\n" + (r.stderr or "")[-2000:]
            if missing:
                feedback.reportError("pip failed:\n" + tail.strip()
                                     + "\n\nInstall by hand and restart QGIS:\n  " + manual_hint())
            else:
                # Nothing is missing; only the swap to the models' version failed.
                feedback.pushWarning("pip could not replace " + ", ".join(REQUIRED[m] for m in repin)
                                     + "; the run goes on with the version that is there.\n" + tail.strip()[-600:])
        return (not missing), missing

    importlib.invalidate_caches()                 # before anything looks at what pip just wrote
    _drop_stale_dist_info()
    prune_shadowed(feedback)
    vendor_loader.activate()
    still = missing_packages()
    if still and feedback is not None:
        feedback.reportError("pip reported success but these are still not importable: "
                             + ", ".join(still) + ".\nRestart QGIS, then try again.")
    return (not still), still


def manual_hint():
    py = _qgis_python()
    return f'"{py}" -m pip install --target "{LIBS_DIR}" --upgrade ' + " ".join(_install_specs())
