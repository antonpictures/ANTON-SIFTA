"""
CURSOR_JOB_BIOLOGICAL_DASHBOARD_QT_CONTRACT_v1 (trace edc8a603-4e08-46f4-bb2e-3db30a8099c7)

Biological Dashboard must load on the Qt path without importing Tk / _tkinter.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _fresh_subprocess_code() -> str:
    return f"""
import importlib.util
import sys
from pathlib import Path

REPO = Path({str(REPO)!r})
sys.path.insert(0, str(REPO))

from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

spec = importlib.util.spec_from_file_location(
    "sifta_biological_dashboard_qt",
    REPO / "Applications" / "sifta_biological_dashboard_qt.py",
)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)

assert "tkinter" not in sys.modules, "tkinter must not load for Qt dashboard module"
assert "_tkinter" not in sys.modules, "_tkinter must not load for Qt dashboard module"

w = mod.BiologicalDashboardWidget()
assert w.minimumWidth() >= 400
print("biological_qt_contract_ok")
"""


def test_biological_dashboard_qt_module_never_imports_tkinter():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    proc = subprocess.run(
        [sys.executable, "-c", _fresh_subprocess_code()],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
        cwd=str(REPO),
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    assert "biological_qt_contract_ok" in out
    assert "_tkinter" not in out.lower()
