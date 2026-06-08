from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    QApplication = None


def test_buzdugan_lcr_engine_retrieves_exact_receipts(tmp_path: Path) -> None:
    from System import swarm_buzdugan_lcr as lcr

    receipt = lcr.run_lcr_benchmark(
        token_target=20_000,
        needle_count=4,
        state_dir=tmp_path,
        force=True,
    )

    assert receipt["truth_label"] == lcr.TRUTH_LABEL
    assert receipt["mode"] == "sifta_body_retrieval_first"
    assert receipt["all_verified"] is True
    assert receipt["pass_count"] == 4
    assert receipt["fact_count"] == 4
    assert receipt["target_retrieval"]["verified_hash"] is True
    assert receipt["target_retrieval"]["line_no"] > 0
    assert receipt["target_retrieval"]["byte_offset"] >= 0
    assert Path(receipt["target_retrieval"]["source_path"]).exists()


def test_buzdugan_lcr_retrieval_fails_honestly_for_missing_key(tmp_path: Path) -> None:
    from System import swarm_buzdugan_lcr as lcr

    lcr.run_lcr_benchmark(token_target=8_000, needle_count=2, state_dir=tmp_path, force=True)
    missing = lcr.retrieve_fact("not_a_real_key", state_dir=tmp_path)

    assert missing["ok"] is False
    assert missing["error"] == "key_not_found"


def test_buzdugan_lcr_manifest_and_help_registered() -> None:
    manifest = json.loads(Path("Applications/apps_manifest.json").read_text(encoding="utf-8"))
    entry = manifest["Buzdugan LCR"]

    assert entry["entry_point"] == "Applications/sifta_buzdugan_lcr.py"
    assert entry["widget_class"] == "BuzduganLCRWidget"
    assert entry["category"] == "Research"

    app_help = Path("Documents/APP_HELP.md").read_text(encoding="utf-8")
    assert "### Buzdugan LCR" in app_help


@pytest.mark.skipif(QApplication is None, reason="PyQt6 unavailable")
def test_buzdugan_lcr_widget_loads_without_fake_receipt(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    from Applications import sifta_buzdugan_lcr as appmod

    monkeypatch.setattr(appmod.lcr, "latest_receipt", lambda: None)
    widget = appmod.BuzduganLCRWidget()

    assert "No Buzdugan LCR receipt yet" in widget.receipt_text.toPlainText()
    assert "Benchmark receipt pending" in widget.claim_text.toPlainText()
    widget.close()
    app.processEvents()
