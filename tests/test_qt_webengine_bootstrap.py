import os
import subprocess
import sys


def test_merge_chromium_gpu_flags_sets_env_and_argv():
    from System import qt_webengine_bootstrap as boot

    boot._BOOTSTRAP_RESULT = None
    os.environ.pop("QTWEBENGINE_CHROMIUM_FLAGS", None)
    try:
        sys.argv.remove("--use-gl=desktop")
    except ValueError:
        pass
    merged = boot._merge_chromium_gpu_flags()
    assert "--enable-gpu" in merged
    if sys.platform == "darwin":
        assert "--use-gl=desktop" not in merged
        assert "--use-gl=desktop" not in sys.argv
    else:
        assert "--use-gl=desktop" in merged
        assert "--use-gl=desktop" in sys.argv
    assert os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS") == merged
    assert "--enable-gpu" in sys.argv


def test_qt_webengine_bootstrap_runs_before_qapplication():
    code = """
from System.qt_webengine_bootstrap import bootstrap_qt_webengine
r = bootstrap_qt_webengine()
print(r.available)
print(r.error)
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        text=True,
        capture_output=True,
    )
    assert proc.stdout.splitlines()[0] in {"True", "False"}
    assert "AA_ShareOpenGLContexts must be set before" not in proc.stdout


def test_alice_browser_imports_after_desktop_bootstrap():
    code = """
from System.qt_webengine_bootstrap import bootstrap_qt_webengine
bootstrap_qt_webengine()
from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from Applications import sifta_alice_browser_widget as browser
print(browser._HAS_WEBENGINE)
print(browser._WEBENGINE_IMPORT_ERROR)
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "AA_ShareOpenGLContexts must be set before" not in proc.stdout
