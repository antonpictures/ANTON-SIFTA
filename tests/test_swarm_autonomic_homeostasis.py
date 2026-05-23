from __future__ import annotations

import json

import System.swarm_autonomic_homeostasis as homeostasis


def _redirect_state(monkeypatch, tmp_path):
    monkeypatch.setattr(homeostasis, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(homeostasis, "_DOPAMINE_LOG", tmp_path / "dopaminergic_state.json")
    monkeypatch.setattr(homeostasis, "_HOMEOSTASIS_REPORT", tmp_path / "autonomic_homeostasis.json")


def test_no_dopamine_state_returns_diagnostic_and_receipt(monkeypatch, tmp_path):
    _redirect_state(monkeypatch, tmp_path)

    out = homeostasis.trigger_parasympathetic_healing()

    assert out["status"] == "NO_STATE_FOUND"
    assert out["action_taken"] == "NONE"
    assert "diagnostic" in out
    report = json.loads((tmp_path / "autonomic_homeostasis.json").read_text(encoding="utf-8"))
    assert report["status"] == "NO_STATE_FOUND"
    assert "inflammatory lock" in report["diagnostic"]


def test_inflammatory_state_resets_to_idle_and_writes_report(monkeypatch, tmp_path):
    _redirect_state(monkeypatch, tmp_path)
    (tmp_path / "dopaminergic_state.json").write_text(
        json.dumps({
            "dopamine_level": 0.1,
            "behavioral_state": "INFLAMMATORY_DEFENSE",
            "action_directive": "LOCKED",
        }),
        encoding="utf-8",
    )

    out = homeostasis.trigger_parasympathetic_healing()

    assert out["action_taken"] == "PARASYMPATHETIC_RESET"
    assert out["previous_state"] == "INFLAMMATORY_DEFENSE"
    updated = json.loads((tmp_path / "dopaminergic_state.json").read_text(encoding="utf-8"))
    assert updated["dopamine_level"] == 0.5
    assert updated["behavioral_state"] == "IDLE"
    report = json.loads((tmp_path / "autonomic_homeostasis.json").read_text(encoding="utf-8"))
    assert report["swimmer_health_status"] == "HEALED_STABLE"
