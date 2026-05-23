#!/usr/bin/env python3
"""
tests/test_event_103_regime_policy_mass.py
══════════════════════════════════════════════════════════════════════════════
Event 103 extension — regime-aware policy mass tests.

Proves the stabilizer → phase controller → policy mass feedback loop:
  1. EXPLORATION regime amplifies explore skill mass
  2. CRITICAL_COLLAPSE regime suppresses explore, amplifies repair mass
  3. crystallizer_gate=0.0 collapses all skill mass to zero (epsilon floor wins)
  4. crystallizer_gate=1.0 leaves mass unchanged
  5. Regime auto-read from regime_state.json when regime=None
  6. write_motor_policy_row stamps regime + crystallizer_gate in ledger
  7. CONSOLIDATION boosts learn/optimize over explore
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _dummy_skill(action: str, reward: float = 0.8, stability: float = 0.9,
                 usage: int = 10) -> dict:
    return {
        "action": action,
        "success_rate": reward,
        "stability": stability,
        "usage_count": usage,
        "pattern_signature": f"body_brain:{action}:target|SIFTA",
        "payload": {"drive_state": "explore"},
    }


def _write_skills(state_dir: Path, skills: list[dict]) -> None:
    """Write crystallized_skills.json with the given skill list."""
    data = {f"skill_{i}": s for i, s in enumerate(skills)}
    (state_dir / "crystallized_skills.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 1. EXPLORATION amplifies explore mass
# ═════════════════════════════════════════════════════════════════════════════

def test_regime_exploration_amplifies_explore(tmp_path):
    from System.swarm_motor_policy import compute_policy_bias
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    _write_skills(state_dir, [
        _dummy_skill("explore", reward=0.7, stability=0.8),
        _dummy_skill("repair", reward=0.7, stability=0.8),
    ])
    bias_explore = compute_policy_bias("explore", state_dir=state_dir, regime="EXPLORATION")
    bias_collapse = compute_policy_bias("explore", state_dir=state_dir, regime="CRITICAL_COLLAPSE")
    assert bias_explore.get("explore", 0) > bias_collapse.get("explore", 0), (
        f"EXPLORATION explore mass={bias_explore.get('explore')} should be > "
        f"CRITICAL_COLLAPSE explore mass={bias_collapse.get('explore')}"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 2. CRITICAL_COLLAPSE suppresses explore, amplifies repair
# ═════════════════════════════════════════════════════════════════════════════

def test_regime_critical_collapse_amplifies_repair(tmp_path):
    from System.swarm_motor_policy import compute_policy_bias
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    _write_skills(state_dir, [
        _dummy_skill("explore", reward=0.8, stability=0.9),
        _dummy_skill("repair", reward=0.8, stability=0.9),
    ])
    bias = compute_policy_bias("explore", state_dir=state_dir, regime="CRITICAL_COLLAPSE")
    repair_mass = bias.get("repair", 0.0)
    explore_mass = bias.get("explore", 0.0)
    assert repair_mass > explore_mass, (
        f"CRITICAL_COLLAPSE: repair={repair_mass:.4f} should be >> explore={explore_mass:.4f}"
    )
    # Ratio should be large (repair scale=2.0 vs explore scale=0.15 → ~13x)
    assert repair_mass / (explore_mass + 1e-9) > 5.0, (
        f"ratio={repair_mass / (explore_mass + 1e-9):.1f} — expected > 5"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 3. crystallizer_gate=0.0 collapses all mass to zero
# ═════════════════════════════════════════════════════════════════════════════

def test_crystallizer_gate_zero_collapses_mass(tmp_path):
    from System.swarm_motor_policy import compute_policy_bias
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    _write_skills(state_dir, [_dummy_skill("explore"), _dummy_skill("repair")])
    bias = compute_policy_bias("explore", state_dir=state_dir,
                               regime="EXPLORATION", crystallizer_gate=0.0)
    total = sum(bias.values())
    assert total == pytest.approx(0.0, abs=1e-6), (
        f"crystallizer_gate=0.0 should zero all mass, got total={total}"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 4. crystallizer_gate=1.0 does not degrade mass
# ═════════════════════════════════════════════════════════════════════════════

def test_crystallizer_gate_one_preserves_mass(tmp_path):
    from System.swarm_motor_policy import compute_policy_bias
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    _write_skills(state_dir, [_dummy_skill("explore")])
    b1 = compute_policy_bias("explore", state_dir=state_dir,
                              regime="EXPLORATION", crystallizer_gate=1.0)
    b_base = compute_policy_bias("explore", state_dir=state_dir,
                                  regime="EXPLORATION")
    assert b1.get("explore", 0) == pytest.approx(b_base.get("explore", 0), rel=1e-4)


# ═════════════════════════════════════════════════════════════════════════════
# 5. Regime auto-reads from regime_state.json when regime=None
# ═════════════════════════════════════════════════════════════════════════════

def test_regime_auto_read_from_cache(tmp_path, monkeypatch):
    from System import swarm_motor_policy as mod
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    rf = state_dir / "regime_state.json"
    rf.write_text(json.dumps({"state": "CRITICAL_COLLAPSE"}), encoding="utf-8")
    monkeypatch.setattr(mod, "_REPO", tmp_path)

    _write_skills(state_dir, [
        _dummy_skill("explore", reward=0.9, stability=0.9),
        _dummy_skill("repair", reward=0.9, stability=0.9),
    ])
    # regime=None → auto-reads CRITICAL_COLLAPSE → repair > explore
    bias = mod.compute_policy_bias("explore", state_dir=state_dir, regime=None)
    assert bias.get("repair", 0) > bias.get("explore", 0), (
        "Auto-read CRITICAL_COLLAPSE should give repair > explore"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 6. write_motor_policy_row stamps regime + crystallizer_gate
# ═════════════════════════════════════════════════════════════════════════════

def test_write_motor_policy_row_stamps_regime(tmp_path):
    from System.swarm_motor_policy import write_motor_policy_row
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    row = write_motor_policy_row(
        selected_action="repair",
        bias={"repair": 0.8, "explore": 0.2},
        current_drive="repair",
        state_dir=state_dir,
        regime="CRITICAL_COLLAPSE",
        crystallizer_gate=0.10,
    )
    assert row["regime"] == "CRITICAL_COLLAPSE"
    assert row["crystallizer_gate"] == pytest.approx(0.10, abs=1e-4)
    assert row["truth_label"] == "SKILL_WEIGHTED_POLICY"

    ledger = state_dir / "motor_policy.jsonl"
    assert ledger.exists()
    written = json.loads(ledger.read_text().strip().splitlines()[-1])
    assert written["regime"] == "CRITICAL_COLLAPSE"
    assert written["crystallizer_gate"] == pytest.approx(0.10, abs=1e-4)


# ═════════════════════════════════════════════════════════════════════════════
# 7. CONSOLIDATION boosts learn/optimize
# ═════════════════════════════════════════════════════════════════════════════

def test_regime_consolidation_boosts_learn(tmp_path):
    from System.swarm_motor_policy import compute_policy_bias
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    _write_skills(state_dir, [
        _dummy_skill("learn",   reward=0.7, stability=0.8),
        _dummy_skill("explore", reward=0.7, stability=0.8),
    ])
    bias_consol = compute_policy_bias("learn", state_dir=state_dir, regime="CONSOLIDATION")
    bias_explo  = compute_policy_bias("learn", state_dir=state_dir, regime="EXPLORATION")
    assert bias_consol.get("learn", 0) > bias_explo.get("learn", 0), (
        f"CONSOLIDATION learn={bias_consol.get('learn'):.4f} should be > "
        f"EXPLORATION learn={bias_explo.get('learn'):.4f}"
    )
    assert bias_consol.get("explore", 0) < bias_explo.get("explore", 0), (
        "CONSOLIDATION should suppress explore mass vs EXPLORATION"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 8. select_action_type_from_skills passes regime through
# ═════════════════════════════════════════════════════════════════════════════

def test_select_uses_regime(tmp_path):
    """In CRITICAL_COLLAPSE, repair should win over explore when both are candidates."""
    from System.swarm_motor_policy import select_action_type_from_skills
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    # Give both explore and repair equal raw skill quality
    _write_skills(state_dir, [
        _dummy_skill("explore", reward=0.8, stability=0.9, usage=20),
        _dummy_skill("repair",  reward=0.8, stability=0.9, usage=20),
    ])
    selected, norm = select_action_type_from_skills(
        ("explore", "repair"),
        "explore",
        state_dir=state_dir,
        regime="CRITICAL_COLLAPSE",
    )
    assert selected == "repair", (
        f"CRITICAL_COLLAPSE with equal skills should select repair, got {selected!r}"
    )
    assert norm["repair"] > norm["explore"], (
        f"repair norm={norm['repair']:.4f} should be > explore norm={norm['explore']:.4f}"
    )


if __name__ == "__main__":
    import pytest as _pt
    _pt.main([__file__, "-v"])
