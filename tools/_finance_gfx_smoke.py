#!/usr/bin/env python3
"""Offscreen smoke test for the Finance graphics polish.

Instantiates FinanceDashboard, marketplace, and the install dialog under
QT_QPA_PLATFORM=offscreen, drives one paint cycle on each new visual
widget, and confirms the canonical wallet sum still reaches the hero
balance unchanged.
"""

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "Applications"))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSize

from sifta_finance import (
    FinanceDashboard,
    InstallAgentDialog,
    AgentCard,
    _HeroBalance,
    _StatTile,
    _MetabolicPill,
    finance_truth_snapshot,
    _FIN_ACCENT,
)

app = QApplication.instance() or QApplication(sys.argv)

# 1. Live truth snapshot — make sure Codex's math is still reachable.
truth = finance_truth_snapshot()
print(f"canonical_wallet_sum={truth['canonical_wallet_sum']:.4f}")
print(f"metabolic_mode={truth['metabolic'].get('mode')}")
print(f"warnings={truth.get('warnings')}")

# 2. Build the dashboard widget tree.
dash = FinanceDashboard()
dash.resize(900, 720)
dash.show()
app.processEvents()
print(f"dash size = {dash.size().width()}x{dash.size().height()}")
print(f"hero_balance value = {dash.hero_balance._value:.4f}")
assert abs(dash.hero_balance._value - truth["canonical_wallet_sum"]) < 1e-6, \
    "Hero balance must mirror canonical wallet sum exactly"

# 3. Confirm the metabolic pill mode reflects truth.
pill_mode = dash.metabolic_pill._mode
print(f"metabolic_pill.mode = {pill_mode}")
assert pill_mode == truth["metabolic"].get("mode")

# 4. Drive a paint cycle on each new visual widget.
hero = _HeroBalance()
hero.resize(QSize(420, 96))
hero.set_value(1234567.8901)
hero.show()
hero.repaint()
print("hero paint OK")

tile = _StatTile("Minted")
tile.resize(QSize(160, 72))
tile.set_value(99.5, accent=_FIN_ACCENT)
tile.show()
tile.repaint()
print("tile paint OK")

pill = _MetabolicPill()
pill.resize(QSize(420, 58))
pill.set_state(
    mode="GREEN_GROW", pressure=0.42,
    budget_mult=1.0, recommendation="proceed; stigmergic load nominal",
)
pill.show()
pill.repaint()
print("pill paint OK")

# 5. Drive an AgentCard with a synthetic local-node row.
synth_local = {
    "id": "ALICE_M5",
    "stgm_balance": 12.3456,
    "stgm_balance_file": 12.3456,
    "stgm_cache_drift": 0.0,
    "energy": 87,
    "style": "PRIMARY",
    "homeworld_serial": "GTH4921YP3",
    "sybil_quarantined": False,
    "asset_class": "STGM",
}
card_local = AgentCard(synth_local, local_node=True)
card_local.resize(QSize(420, 84))
card_local.show()
card_local.repaint()
print("local AgentCard paint OK; localNode prop =",
      card_local.property("localNode"))

# 6. Sybil-flagged card.
synth_sybil = dict(synth_local)
synth_sybil["id"] = "ROGUE_AGENT"
synth_sybil["sybil_quarantined"] = True
card_sybil = AgentCard(synth_sybil, local_node=False)
card_sybil.repaint()
print("sybil AgentCard paint OK; sybil prop =",
      card_sybil.property("sybil"))

# 7. Marketplace table draws without exception.
mt = dash.market_tab
mt.resize(QSize(900, 600))
mt.show()
mt.repaint()
print(f"market table rows = {mt.table.rowCount()}")

# 8. Warren tab renders.
dash.tabs.setCurrentIndex(2)
app.processEvents()
warren_text = dash.warren_view.toPlainText()[:80]
print(f"warren first 80 chars = {warren_text!r}")

# 9. Install dialog can be constructed (do not exec — offscreen).
dlg = InstallAgentDialog(dash)
dlg.repaint()
print("install dialog OK")

# 10. Refresh path runs without exception.
dash._refresh_all()
print("refresh path OK")

print("FINANCE GFX SMOKE: PASS")
