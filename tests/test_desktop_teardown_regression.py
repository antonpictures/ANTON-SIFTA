"""
CURSOR_JOB_DESKTOP_TEARDOWN_REGRESSION_v1 (trace c6be7b74-2eca-4d6e-b2f0-0c78ec679b24)

Offscreen subprocess smoke: SiftaDesktop close must not emit the classic
``QThread: Destroyed while thread is still running`` / SIGABRT failure mode.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

_TEARDOWN_SCRIPT = f"""
import sys
from pathlib import Path

REPO = Path({str(REPO)!r})
sys.path.insert(0, str(REPO))

from PyQt6.QtWidgets import QApplication

from sifta_os_desktop import SiftaDesktop

app = QApplication.instance() or QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

w = SiftaDesktop()
w.hide()

for _ in range(120):
    app.processEvents()
    mesh = getattr(w, "_desktop_mesh", None)
    if mesh is None or not mesh.isRunning():
        break

w.close()

for _ in range(300):
    app.processEvents()
    mesh = getattr(w, "_desktop_mesh", None)
    if mesh is None:
        break
    if not mesh.isRunning():
        break

app.quit()
sys.stdout.write("desktop_teardown_ok\\n")
sys.exit(0)
"""


def test_sifta_env_mesh_guard_honors_disable(monkeypatch):
    """1 / true / yes with strip — aligned with GCI, not bare == \"1\" only."""
    from sifta_os_desktop import _sifta_env_mesh_disabled

    monkeypatch.delenv("SIFTA_DISABLE_MESH", raising=False)
    assert _sifta_env_mesh_disabled() is False
    for val in ("1", " 1 ", "true", "TRUE", "yes", " Yes "):
        monkeypatch.setenv("SIFTA_DISABLE_MESH", val)
        assert _sifta_env_mesh_disabled() is True, val
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "0")
    assert _sifta_env_mesh_disabled() is False
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "false")
    assert _sifta_env_mesh_disabled() is False


def test_sifta_desktop_teardown_subprocess_clean_exit():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    # Autostarted MDI apps (e.g. Alice) may own QThreads; this smoke test targets shell + mesh only.
    env["SIFTA_DESKTOP_SKIP_WM_AUTOSTART"] = "1"
    env["SIFTA_DISABLE_MESH"] = "1"
    if sys.platform.startswith("linux"):
        env.setdefault("QT_QPA_PLATFORM", "offscreen")

    proc = subprocess.run(
        [sys.executable, "-c", _TEARDOWN_SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(REPO),
    )
    blob = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, blob
    assert "desktop_teardown_ok" in proc.stdout
    assert "Destroyed while thread is still running" not in blob
    assert "SIGABRT" not in blob
