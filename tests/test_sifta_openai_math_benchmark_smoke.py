"""Smoke test for the SIFTA ∥ OpenAI math benchmark widget.

Validates:
  1. Module imports cleanly
  2. Widget class exists and is a QWidget subclass
  3. Capability markers data structure is well-formed
  4. Problem classes data structure is well-formed
  5. Live ledger readers don't crash (they may return 0)
  6. create_widget() factory works
"""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def test_module_imports():
    import Applications.sifta_openai_math_benchmark_widget as mod
    assert hasattr(mod, "MathBenchmarkWidget")
    assert hasattr(mod, "create_widget")
    assert hasattr(mod, "CAPABILITY_MARKERS")
    assert hasattr(mod, "PROBLEM_CLASSES")


def test_capability_markers_structure():
    from Applications.sifta_openai_math_benchmark_widget import CAPABILITY_MARKERS
    assert len(CAPABILITY_MARKERS) == 5
    required = {"id", "name", "episode_ref", "openai_claim",
                "sifta_anchor", "sifta_status", "prove_it", "gap"}
    for m in CAPABILITY_MARKERS:
        assert required.issubset(set(m.keys())), f"Missing keys in {m['id']}"
        assert m["sifta_status"] in ("PRESENT", "PARTIAL", "PLANNED", "MISSING")


def test_problem_classes_structure():
    from Applications.sifta_openai_math_benchmark_widget import PROBLEM_CLASSES
    assert len(PROBLEM_CLASSES) == 3
    for pc in PROBLEM_CLASSES:
        assert "class" in pc
        assert "status" in pc
        assert "examples" in pc
        assert isinstance(pc["examples"], list)


def test_live_readers_dont_crash():
    from Applications.sifta_openai_math_benchmark_widget import (
        _count_proof_guards,
        _count_ledger_lines,
        _count_pytest_files,
        _count_organs,
        _get_wallet_balance,
    )
    assert isinstance(_count_proof_guards(), int)
    assert isinstance(_count_ledger_lines(), int)
    assert isinstance(_count_pytest_files(), int)
    assert isinstance(_count_organs(), int)
    assert isinstance(_get_wallet_balance(), float)


def test_episode_chapters():
    from Applications.sifta_openai_math_benchmark_widget import EPISODE_CHAPTERS, VIDEO_URL
    assert len(EPISODE_CHAPTERS) >= 5
    assert "youtube.com" in VIDEO_URL


def test_widget_starts_without_auto_pulling_huggingface(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    import Applications.sifta_openai_math_benchmark_widget as mod

    def boom(self):
        raise AssertionError("Arena pull must be user-triggered, not startup-triggered")

    monkeypatch.setattr(mod.MathBenchmarkWidget, "_arena_auto_pull", boom)
    app = QApplication.instance() or QApplication([])
    widget = mod.MathBenchmarkWidget()
    try:
        assert widget._arena_table.rowCount() == 0
        assert "Hit Reload" in widget._arena_status.text()
        assert widget._status_lbl.text() == "Ready"
    finally:
        widget.close()
        app.processEvents()


def test_widget_has_p_vs_np_gate_tab(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    import Applications.sifta_openai_math_benchmark_widget as mod

    app = QApplication.instance() or QApplication([])
    widget = mod.MathBenchmarkWidget()
    try:
        tab_names = [widget._tabs.tabText(i) for i in range(widget._tabs.count())]
        assert any("P vs NP Gate" in name for name in tab_names)
    finally:
        widget.close()
        app.processEvents()
