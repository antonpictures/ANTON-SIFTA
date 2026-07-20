"""Double Apex Predator — united surfaces + dual doctor launcher."""
from __future__ import annotations

from System.swarm_double_apex import (
    DEFAULT_LOCAL_MODEL,
    TRUTH_LABEL,
    doctor_status,
    launch_doctor,
    list_local_models,
    pick_default_model,
)


def test_truth_label_and_default_model() -> None:
    assert TRUTH_LABEL.startswith("DOUBLE_APEX")
    assert "qwen" in DEFAULT_LOCAL_MODEL.lower() or "nightshift" in DEFAULT_LOCAL_MODEL.lower()


def test_pick_default_prefers_nightshift() -> None:
    models = [
        "ornith:latest",
        "jikepjikep_16HEX/qwen3.6-27b-nightshift-heretic-uncensored-q4:latest",
        "other:latest",
    ]
    assert "nightshift" in pick_default_model(models).lower()


def test_unknown_arm_fails_clean() -> None:
    r = launch_doctor("not_an_arm", model="x")
    assert r["ok"] is False
    assert "unknown_arm" in str(r.get("reason"))


def test_doctor_status_shape() -> None:
    st = doctor_status()
    assert "ollama" in st and "codex" in st and "claude" in st
    assert st["truth_label"] == TRUTH_LABEL


def test_list_models_shape() -> None:
    info = list_local_models()
    assert "models" in info
    assert isinstance(info["models"], list)


def test_widget_builds_three_tabs(monkeypatch) -> None:
    import os
    import sys

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    from Applications.sifta_double_apex_predator import DoubleApexPredatorWidget

    app = QApplication.instance() or QApplication(sys.argv)
    w = DoubleApexPredatorWidget()
    assert hasattr(w, "tabs")
    assert w.tabs.count() == 3
    titles = [w.tabs.tabText(i) for i in range(w.tabs.count())]
    assert any("Perceiver" in t for t in titles)
    assert any("Field" in t for t in titles)
    assert any("Doctors" in t for t in titles)
    w.close()
