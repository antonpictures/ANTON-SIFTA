#!/usr/bin/env python3
"""
Compatibility shim for the biological visualizer.

- **Qt / manifest:** import ``BiologicalDashboardWidget`` from
  ``Applications.sifta_biological_dashboard_qt`` (no Tk / ``_tkinter``).
- **Tk standalone:** ``python3 Applications/sifta_biological_gui.py`` delegates to
  ``sifta_biological_gui_tk.run_standalone``.
"""

from __future__ import annotations

if __name__ == "__main__":
    from Applications.sifta_biological_gui_tk import run_standalone

    run_standalone()
else:
    from Applications.sifta_biological_dashboard_qt import BiologicalDashboardWidget
