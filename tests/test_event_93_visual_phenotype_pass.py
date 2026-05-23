#!/usr/bin/env python3
"""
tests/test_event_93_visual_phenotype_pass.py
══════════════════════════════════════════════════════════════════════════════
Event 93 — Live QOpenGLWidget Composite / Stigmergic OpenGL Driver

Pytest proof that:
  1. visual_phenotype_uniforms.jsonl has receipt_backed=True rows (real data)
  2. VisualPhenotypeModernGLPass can ingest a ledger row and produce uniforms
  3. Uniforms are non-trivial (at least one value > 0) — not a dead renderer
  4. clamp_uniforms() keeps all values in [0, 1] — shader contract respected
  5. ModernGL offscreen context can be created (GPU driver real)
  6. Phase detector is wired: evaluate_regime() returns a valid macro-state

This file turning green == §F row for Event 93 can be marked SHIPPED.

Truth label: OBSERVED_ENGINEERING_SUBSTRATE
Research: Friston (2010) free energy / honeybee waggle-dance algorithm
"""
from __future__ import annotations

import json
import sys
import time
import math
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "visual_phenotype_uniforms.jsonl"

# ── helpers ──────────────────────────────────────────────────────────────────

def _load_ledger() -> list[dict]:
    if not _LEDGER.exists():
        return []
    rows = []
    for line in _LEDGER.read_text("utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


# ═════════════════════════════════════════════════════════════════════════════
# 1. Ledger presence — gate 0
# ═════════════════════════════════════════════════════════════════════════════

def test_event93_ledger_exists():
    """Ledger must exist with at least one row."""
    rows = _load_ledger()
    assert rows, (
        "visual_phenotype_uniforms.jsonl is missing or empty. "
        "Run at least one body-brain tick to generate real uniform data."
    )


def test_event93_receipt_backed_rows():
    """At least one row must carry receipt_backed=True (real stigmergic data)."""
    rows = _load_ledger()
    backed = [r for r in rows if r.get("receipt_backed")]
    assert backed, (
        "No receipt_backed=True rows in visual_phenotype_uniforms.jsonl. "
        "The chromatophore pass is not wired to real body-brain receipts."
    )


# ═════════════════════════════════════════════════════════════════════════════
# 2. clamp_uniforms — shader contract
# ═════════════════════════════════════════════════════════════════════════════

def test_event93_clamp_uniforms_contract():
    """clamp_uniforms() must keep [0,1] uniforms in [0,1]; u_heading is radians [-tau,tau]."""
    import math
    from System.swarm_visual_phenotype_gl import clamp_uniforms, CLAMP_01_KEYS

    rows = _load_ledger()
    backed = [r for r in rows if r.get("receipt_backed")]
    assert backed

    for row in backed[-3:]:  # check last 3 backed rows
        clamped = clamp_uniforms(row)
        for key, val in clamped.items():
            if key in CLAMP_01_KEYS:
                assert 0.0 <= val <= 1.0, (
                    f"Uniform {key}={val} out of [0,1] shader contract "
                    f"(row ts={row.get('ts','?')})"
                )
            elif key == "u_heading":
                # heading is a radian angle, clamp range is [-tau, tau]
                assert -math.tau <= val <= math.tau, (
                    f"u_heading={val} out of [-tau,tau] radian range"
                )


def test_event93_uniforms_nontrivial():
    """At least one uniform value > 0.001 — renderer is not dead/zeroed."""
    from System.swarm_visual_phenotype_gl import clamp_uniforms

    rows = _load_ledger()
    backed = [r for r in rows if r.get("receipt_backed")]
    clamped = clamp_uniforms(backed[-1])
    max_val = max(clamped.values(), default=0.0)
    assert max_val > 0.001, (
        f"All uniforms are near-zero (max={max_val:.6f}). "
        "Stigmergic drive is not flowing into the GL pass."
    )


# ═════════════════════════════════════════════════════════════════════════════
# 3. VisualPhenotypeModernGLPass — ledger ingestion
# ═════════════════════════════════════════════════════════════════════════════

def test_event93_pass_ingests_ledger(tmp_path):
    """VisualPhenotypeUniformTail reads ledger and produces non-zero stigmergic drive."""
    from System.swarm_visual_phenotype_gl import VisualPhenotypeUniformTail

    # Write a synthetic backed row to tmp ledger
    synthetic_row = {
        "receipt_backed": True,
        "action": "forage",
        "drive_state": "ACTIVE",
        "metabolic_mode": "GREEN_GROW",
        "plasticity_danger": "NONE",
        "u_stigmergic_drive": 0.75,
        "u_confidence": 0.60,
        "u_quorum_signal": 0.50,
        "u_chemotaxis_gradient": 0.35,
        "u_cost": 0.20,
        "u_reward": 0.80,
        "u_metabolic_scope": 0.70,
        "u_distance": 0.40,
        "u_heading": 0.55,
        "u_cot_factor": 0.65,
        "source": "test_event93",
        "ts": time.time(),
        "tick_id": 1,
    }
    ledger_path = tmp_path / "visual_phenotype_uniforms.jsonl"
    ledger_path.write_text(json.dumps(synthetic_row) + "\n", encoding="utf-8")

    tail = VisualPhenotypeUniformTail(str(ledger_path))
    frame = tail.read_frame(force=True)

    assert frame is not None, "VisualPhenotypeUniformTail.read_frame() returned None"
    assert frame.receipt_backed is True
    drive = frame.uniforms.get("u_stigmergic_drive", 0.0)
    assert drive > 0.5, (
        f"Expected u_stigmergic_drive > 0.5, got {drive}"
    )
    confidence = frame.uniforms.get("u_confidence", 0.0)
    assert 0.0 <= confidence <= 1.0


# ═════════════════════════════════════════════════════════════════════════════
# 4. ModernGL context (offscreen GPU driver)
# ═════════════════════════════════════════════════════════════════════════════

def test_event93_moderngl_available():
    """ModernGL must be importable — GPU driver is installed."""
    try:
        import moderngl
        assert moderngl.__version__, "moderngl has no version"
    except ImportError:
        pytest.fail(
            "moderngl not installed. Run: pip install moderngl\n"
            "This is required for the Event 93 chromatophore pass."
        )


def test_event93_gl_context_probe():
    """Offscreen GL context must be creatable (hardware driver real)."""
    from System.swarm_visual_phenotype_gl import modern_gl_available, try_create_standalone_context

    if not modern_gl_available():
        pytest.skip("ModernGL context not available in this environment")

    probe = try_create_standalone_context()
    assert getattr(probe, "ok", False), (
        f"Offscreen GL context creation failed: renderer={getattr(probe, 'renderer', '?')}"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 5. Uniform delta test — pixels shift when ledger changes
# ═════════════════════════════════════════════════════════════════════════════

def test_event93_uniform_delta_on_ledger_change(tmp_path):
    """
    Falsifiable: writing two different rows to ledger must produce
    two different UniformFrames. Proves the tail is reading live data.
    """
    from System.swarm_visual_phenotype_gl import VisualPhenotypeUniformTail

    ledger = tmp_path / "visual_phenotype_uniforms.jsonl"

    def _write(drive: float) -> object:
        row = {
            "receipt_backed": True,
            "u_stigmergic_drive": drive,
            "u_confidence": 0.5,
            "u_quorum_signal": 0.5,
            "u_chemotaxis_gradient": 0.3,
            "u_cost": 0.2,
            "u_reward": 0.6,
            "u_metabolic_scope": 0.7,
            "u_distance": 0.4,
            "u_heading": 0.5,
            "u_cot_factor": 0.6,
            "action": "forage",
            "drive_state": "ACTIVE",
            "metabolic_mode": "GREEN_GROW",
            "plasticity_danger": "NONE",
            "source": "test_delta",
            "ts": time.time(),
            "tick_id": 1,
        }
        ledger.write_text(json.dumps(row) + "\n")
        tail = VisualPhenotypeUniformTail(str(ledger))
        return tail.read_frame(force=True)

    frame_a = _write(0.10)
    frame_b = _write(0.90)

    assert frame_a is not None
    assert frame_b is not None

    drive_a = frame_a.uniforms.get("u_stigmergic_drive", 0.0)
    drive_b = frame_b.uniforms.get("u_stigmergic_drive", 0.0)
    delta = abs(drive_b - drive_a)
    assert delta > 0.3, (
        f"Ledger change produced no meaningful uniform delta "
        f"(Δu_stigmergic_drive={delta:.4f}). "
        "The tail is not reading live data."
    )


# ═════════════════════════════════════════════════════════════════════════════
# 6. Phase Detector — wired and returning valid macro-state
# ═════════════════════════════════════════════════════════════════════════════

def test_phase_detector_returns_valid_regime(tmp_path, monkeypatch):
    """Phase detector must return one of the three canonical regimes."""
    import System.phase_transition_control as ptc_mod

    # Isolate state files
    monkeypatch.setattr(ptc_mod, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(ptc_mod, "_REGIME_STATE_FILE", tmp_path / "regime_state.json")
    monkeypatch.setattr(ptc_mod, "_TRACE_LOG", tmp_path / "execution_traces.jsonl")
    monkeypatch.setattr(ptc_mod, "_PTC", None)

    ptc = ptc_mod.PhaseTransitionController()
    regime = ptc.evaluate_regime()

    assert regime in {"EXPLORATION", "CONSOLIDATION", "CRITICAL_COLLAPSE"}, (
        f"Unexpected regime: {regime}"
    )
    assert 0.0 <= ptc.state.stigmergic_density <= 1.0
    assert 0.0 <= ptc.state.EWS_score <= 1.0


def test_phase_detector_cusum_stats(tmp_path, monkeypatch):
    """
    Phase detector must detect a regime shift when body_brain TD values
    suddenly drop (simulated drive saturation / anti-correlation).
    This proves the CUSUM path is wired.
    """
    import System.phase_transition_control as ptc_mod
    from System.phase_transition_control import PhaseDetectorStats

    # Write a sequence of high-TD rows followed by low-TD rows
    mem_log = tmp_path / "body_brain_memory.jsonl"
    rows = []
    for i in range(20):
        td = 0.8 if i < 10 else 0.05  # regime shift at index 10
        rows.append(json.dumps({
            "event": "body_brain_tick",
            "td_value": td,
            "ts": time.time() - (20 - i) * 10,
        }))
    mem_log.write_text("\n".join(rows) + "\n")

    stats = PhaseDetectorStats(mem_log)
    result = stats.compute()

    assert result is not None
    assert "td_mean" in result
    assert "td_variance" in result
    assert "cusum_alarm" in result
    # With the simulated drop, CUSUM should alarm
    assert result["cusum_alarm"] is True, (
        f"CUSUM did not detect the simulated regime shift. "
        f"td_variance={result.get('td_variance','?')}, "
        f"cusum_score={result.get('cusum_score','?')}"
    )


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pytest as _pt
    _pt.main([__file__, "-v"])
