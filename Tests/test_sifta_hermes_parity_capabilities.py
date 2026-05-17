"""Hermes Parity renders the unified Capability Field."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

_QT_APP = None


def _app():
    global _QT_APP
    _QT_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _QT_APP


class FakeCapability:
    def __init__(
        self,
        name: str,
        *,
        can_execute: bool,
        can_teach_compose: bool,
        learned_from_trace: bool = False,
        description: str = "",
    ) -> None:
        self.name = name
        self.description = description or f"{name} description"
        self.when_to_use = self.description
        self.confidence = 0.8
        self.cost_stgm = 0.02
        self.can_execute = can_execute
        self.can_teach_compose = can_teach_compose
        self.learned_from_trace = learned_from_trace

    def is_hybrid(self) -> bool:
        return self.can_execute and self.can_teach_compose

    def to_alice_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "when_to_use": self.when_to_use,
            "confidence": self.confidence,
            "cost_stgm": self.cost_stgm,
            "can_execute": self.can_execute,
            "can_teach_compose": self.can_teach_compose,
            "learned_from_trace": self.learned_from_trace,
            "backing": {
                "tool": self.name if self.can_execute else None,
                "skill": self.name if self.can_teach_compose else None,
            },
        }


def test_hermes_parity_tools_row_uses_unified_capabilities(monkeypatch):
    import Applications.sifta_hermes_parity_widget as hermes

    _app()
    hermes.SiftaHermesParityWidget._live_instance = None
    hermes.SiftaHermesParityWidget._initialized_instance_ids.clear()

    fake_caps = [
        FakeCapability("hybrid_reader", can_execute=True, can_teach_compose=True),
        FakeCapability("read_file", can_execute=True, can_teach_compose=False),
        FakeCapability(
            "learned_trace_reader",
            can_execute=False,
            can_teach_compose=True,
            learned_from_trace=True,
        ),
        FakeCapability("morning_briefing", can_execute=False, can_teach_compose=True),
    ]
    monkeypatch.setattr(hermes, "_capabilities", SimpleNamespace(build_capability_index=lambda: fake_caps))
    monkeypatch.setattr(
        hermes,
        "_skill_lib",
        SimpleNamespace(
            build_skill_index=lambda: [],
            load_procedure=lambda name: f"# {name}\n\nProcedure body for {name}.",
        ),
    )
    monkeypatch.setattr(hermes, "_publish_focus", None)
    monkeypatch.setattr(hermes, "_recent_receipts", lambda *args, **kwargs: [])

    w = hermes.SiftaHermesParityWidget()
    buttons = [b for b in w.findChildren(QtWidgets.QPushButton) if b.text().startswith("[")]
    labels = [b.text() for b in buttons]

    assert labels[:4] == [
        "[hybrid] hybrid_reader",
        "[tool] read_file",
        "[skill·learned] learned_trace_reader",
        "[skill] morning_briefing",
    ]
    assert buttons[0].objectName() == "HermesCapPillHybrid"
    assert buttons[1].objectName() == "HermesCapPillTool"
    assert buttons[2].objectName() == "HermesCapPillSkillLearned"
    assert buttons[3].objectName() == "HermesCapPillSkill"

    w._on_capability_pill(fake_caps[3].to_alice_dict())
    assert "Procedure body for morning_briefing" in w._chat_log.toPlainText()

    w.close()
