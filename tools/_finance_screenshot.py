#!/usr/bin/env python3
"""Render Finance dashboard PNGs for visual verification."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "Applications"))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSize

from sifta_finance import FinanceDashboard

app = QApplication.instance() or QApplication(sys.argv)

dash = FinanceDashboard()
dash.resize(1100, 820)
dash.show()
app.processEvents()
app.processEvents()

# Each tab.
for idx, tag in [(0, "portfolio"), (1, "market"), (2, "warren")]:
    dash.tabs.setCurrentIndex(idx)
    app.processEvents()
    pm = dash.grab()
    out = os.path.join("/tmp", f"finance_{tag}.png")
    pm.save(out, "PNG")
    print(f"saved {out} {pm.size().width()}x{pm.size().height()}")
