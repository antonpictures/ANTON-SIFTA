"""Tests for the steering self-model.

Architect 2026-05-14: "The cortex predicts the steering subsystem."
Step 1 of that loop is measuring the current steering state at all.
That's what this module does — it reads the steering ledger and emits
six self-state signals plus first-person sentences.

These tests pin:
  - Truth labels and ledger names are stable
  - Each of the six detectors fires on a synthesized stress window
  - Each of the six detectors stays silent on a synthesized calm window
  - Empty input returns a clean zero-state (no fired sentences)
  - Receipt is sha256-signed and round-trips through the ledger
  - Receipt schema and truth boundary are stamped
  - Prompt block is empty when nothing fires, populated when sentences do
  - Explain returns only fired detectors with their human-readable line
  - read_recent_steering_rows handles missing/corrupt files
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_steering_self_model import (  # noqa: E402
    SELF_MODEL_LEDGER,
    STEERING_LEDGER,
    TRUTH_BOUNDARY,
    TRUTH_LABEL,
    SelfModelState,
    SelfStateSignal,
    demo_self_model,
    explain_self_state,
    model_self_state,
    read_recent_steering_rows,
    self_model_prompt_block,
    write_self_model_receipt,
)


# ── Test fixtures: synthetic windows ──────────────────────────────────

def _calm_window(n: int = 10) -> list[dict]:
    """All FAST_REFLEX, low everything. Should silence every detector."""
    return [
        {
            "route": "FAST_REFLEX",
            "priority": 0.10,
            "interrupt": 0.05,
            "care": 0.05,
            "signals": {
                "metabolic_pressure": 0.10,
                "tool_truth_risk": 0.05,
                "novelty": 0.10,
                "owner_pressure": 0.05,
            },
        }
        for _ in range(n)
    ]


def _stressed_window(n: int = 10) -> list[dict]:
    """High-pressure mix: VERIFY-heavy + 2 EMERGENCY + high everything."""
    rows = [
        {
            "route": "VERIFY_BEFORE_ACTION",
            "priority": 0.75,
            "interrupt": 0.70,
            "care": 0.55,
            "signals": {
                "metabolic_pressure": 0.82,
                "tool_truth_risk": 0.88,
                "novelty": 0.72,
                "owner_pressure": 0.65,
            },
        }
        for _ in range(n - 2)
    ]
    rows.extend(
        {
            "route": "EMERGENCY_INTERRUPT",
            "priority": 0.95,
            "interrupt": 0.95,
            "care": 0.90,
            "signals": {
                "metabolic_pressure": 0.95,
                "tool_truth_risk": 0.50,
                "novelty": 0.40,
                "owner_pressure": 0.90,
            },
        }
        for _ in range(2)
    )
    return rows


def _conservation_window(n: int = 10) -> list[dict]:
    """All CONSERVE_OR_DEFER, high metabolic pressure."""
    return [
        {
            "route": "CONSERVE_OR_DEFER",
            "priority": 0.30,
            "interrupt": 0.10,
            "care": 0.15,
            "signals": {
                "metabolic_pressure": 0.92,
                "tool_truth_risk": 0.10,
                "novelty": 0.20,
                "owner_pressure": 0.10,
            },
        }
        for _ in range(n)
    ]


# ── Taxonomy ──────────────────────────────────────────────────────────

def test_truth_label_is_v1():
    assert TRUTH_LABEL == "STEERING_SELF_MODEL_V1"


def test_ledger_names_are_stable():
    assert STEERING_LEDGER == "steering_subsystem.jsonl"
    assert SELF_MODEL_LEDGER == "steering_self_model.jsonl"


def test_truth_boundary_forbids_clinical_or_affective_claims():
    text = TRUTH_BOUNDARY.lower()
    assert "hypothesis" in text
    assert "not clinical" in text
    assert "affective" in text


# ── Empty / corrupt ledger handling ───────────────────────────────────

def test_empty_window_produces_zero_state():
    state = model_self_state(rows=[])
    assert isinstance(state, SelfModelState)
    assert state.window_size == 0
    assert state.sentences == ()
    assert state.dominant is None
    # Every signal must be present and unfired
    names = {s.name for s in state.signals}
    assert names == {
        "overload", "residue_drift", "novelty_pressure",
        "metabolic_debt", "owner_pressure_load", "truth_risk_burn",
    }
    for s in state.signals:
        assert s.fired is False
        assert s.value == 0.0


def test_missing_ledger_returns_empty_rows(tmp_path):
    rows = read_recent_steering_rows(state_dir=tmp_path)
    assert rows == []


def test_corrupt_lines_are_skipped(tmp_path):
    (tmp_path / STEERING_LEDGER).write_text(
        '{"route":"FAST_REFLEX","priority":0.1}\n'
        'this is not json\n'
        '{"route":"DEEP_CORTEX","priority":0.5}\n',
        encoding="utf-8",
    )
    rows = read_recent_steering_rows(state_dir=tmp_path)
    assert len(rows) == 2
    assert rows[0]["route"] == "FAST_REFLEX"
    assert rows[1]["route"] == "DEEP_CORTEX"


def test_n_rows_tail_is_respected(tmp_path):
    payload = "\n".join(
        json.dumps({"route": "FAST_REFLEX", "priority": float(i) / 100})
        for i in range(50)
    )
    (tmp_path / STEERING_LEDGER).write_text(payload + "\n", encoding="utf-8")
    rows = read_recent_steering_rows(n_rows=10, state_dir=tmp_path)
    assert len(rows) == 10
    # We tail, so the LAST 10 (priorities 0.40..0.49) should be returned
    assert rows[0]["priority"] == 0.40
    assert rows[-1]["priority"] == 0.49


# ── The six detectors — calm window silences all ──────────────────────

def test_calm_window_fires_no_detector():
    state = model_self_state(rows=_calm_window(12))
    assert state.sentences == ()
    assert state.dominant is None
    assert all(not s.fired for s in state.signals)


# ── The six detectors — each fires when stressed ──────────────────────

def _fired_names(state: SelfModelState) -> set[str]:
    return {s.name for s in state.signals if s.fired}


def test_overload_fires_on_stressed_window():
    state = model_self_state(rows=_stressed_window(10))
    assert "overload" in _fired_names(state)
    assert "I am entering overload." in state.sentences


def test_residue_drift_fires_when_verify_rate_high():
    rows = [
        {"route": "VERIFY_BEFORE_ACTION", "priority": 0.5, "interrupt": 0.4,
         "care": 0.2, "signals": {}} for _ in range(8)
    ] + [
        {"route": "FAST_REFLEX", "priority": 0.1, "interrupt": 0.0,
         "care": 0.0, "signals": {}} for _ in range(2)
    ]
    state = model_self_state(rows=rows)
    assert "residue_drift" in _fired_names(state)
    assert "I am drifting toward residue." in state.sentences


def test_novelty_pressure_fires_on_high_novelty():
    rows = [
        {"route": "DEEP_CORTEX", "priority": 0.3, "interrupt": 0.2,
         "care": 0.1, "signals": {"novelty": 0.80}} for _ in range(10)
    ]
    state = model_self_state(rows=rows)
    assert "novelty_pressure" in _fired_names(state)
    assert "I am under high novelty pressure." in state.sentences


def test_metabolic_debt_fires_on_conservation_window():
    state = model_self_state(rows=_conservation_window(10))
    assert "metabolic_debt" in _fired_names(state)
    assert "I am conserving due to thermal debt." in state.sentences


def test_owner_pressure_load_fires_on_care_and_emergency():
    rows = [
        {"route": "EMERGENCY_INTERRUPT", "priority": 0.9, "interrupt": 0.9,
         "care": 0.85, "signals": {"owner_pressure": 0.85}}
        for _ in range(3)
    ] + [
        {"route": "DEEP_CORTEX", "priority": 0.4, "interrupt": 0.3,
         "care": 0.50, "signals": {"owner_pressure": 0.50}}
        for _ in range(7)
    ]
    state = model_self_state(rows=rows)
    assert "owner_pressure_load" in _fired_names(state)
    assert "I am carrying owner pressure." in state.sentences


def test_truth_risk_burn_fires_on_verify_heavy_high_risk():
    rows = [
        {"route": "VERIFY_BEFORE_ACTION", "priority": 0.6, "interrupt": 0.5,
         "care": 0.3, "signals": {"tool_truth_risk": 0.85}}
        for _ in range(10)
    ]
    state = model_self_state(rows=rows)
    assert "truth_risk_burn" in _fired_names(state)
    assert ("I am burning truth-risk; verification rate is high."
            in state.sentences)


# ── Dominant detector picks the largest margin ────────────────────────

def test_dominant_is_largest_margin_when_multiple_fire():
    # Build a window where metabolic_debt is way above threshold and
    # novelty is barely above
    rows = _conservation_window(10)
    # All CONSERVE_OR_DEFER + 0.92 metabolic_pressure → metabolic_debt
    # value ~= 0.92, threshold 0.55 → margin ~0.37. Novelty value 0.20,
    # threshold 0.55 → doesn't fire.
    state = model_self_state(rows=rows)
    assert state.dominant == "metabolic_debt"


def test_dominant_is_none_when_nothing_fires():
    state = model_self_state(rows=_calm_window(8))
    assert state.dominant is None


# ── Prompt block + explain ────────────────────────────────────────────

def test_prompt_block_is_empty_when_nothing_fires():
    state = model_self_state(rows=_calm_window(5))
    assert self_model_prompt_block(state) == ""


def test_prompt_block_contains_fired_sentences():
    state = model_self_state(rows=_stressed_window(10))
    block = self_model_prompt_block(state)
    assert "STEERING SELF-MODEL" in block
    assert TRUTH_LABEL in block
    for s in state.sentences:
        assert s in block
    assert "predicted_next_route:" in block


def test_prompt_block_can_include_stable_state():
    state = model_self_state(rows=_calm_window(5))
    block = self_model_prompt_block(state, include_stable=True)
    assert "I am stable" in block
    assert "predicted_next_route: FAST_REFLEX" in block
    assert TRUTH_LABEL in block


def test_route_counts_are_recorded():
    state = model_self_state(rows=_conservation_window(4))
    assert state.route_counts == {"CONSERVE_OR_DEFER": 4}
    assert state.to_dict()["route_counts"] == {"CONSERVE_OR_DEFER": 4}


def test_predicted_next_route_tracks_verification_pressure():
    rows = [
        {"route": "VERIFY_BEFORE_ACTION", "priority": 0.6, "interrupt": 0.5,
         "care": 0.2, "signals": {"tool_truth_risk": 0.90}}
        for _ in range(10)
    ]
    state = model_self_state(rows=rows)
    assert state.predicted_next_route == "VERIFY_BEFORE_ACTION"


def test_predicted_next_route_tracks_conservation_pressure():
    state = model_self_state(rows=_conservation_window(10))
    assert state.predicted_next_route == "CONSERVE_OR_DEFER"


def test_predicted_next_route_tracks_novelty_pressure():
    rows = [
        {"route": "DEEP_CORTEX", "priority": 0.3, "interrupt": 0.1,
         "care": 0.1, "signals": {"novelty": 0.82}}
        for _ in range(10)
    ]
    state = model_self_state(rows=rows)
    assert state.predicted_next_route == "DEEP_CORTEX"


def test_explain_returns_only_fired_detectors():
    state = model_self_state(rows=_stressed_window(10))
    exp = explain_self_state(state)
    fired = _fired_names(state)
    assert set(exp.keys()) == fired
    for name, text in exp.items():
        assert isinstance(text, str)
        assert len(text) > 5


# ── Receipt round-trip ────────────────────────────────────────────────

def test_receipt_is_sha256_signed_and_round_trips(tmp_path):
    state = model_self_state(rows=_stressed_window(10))
    row = write_self_model_receipt(state, state_dir=tmp_path)
    # sha256 over deterministic body (payload sans trace_id)
    body = {k: v for k, v in state.to_dict().items() if k != "trace_id"}
    expected = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"),
                   default=str).encode("utf-8")
    ).hexdigest()
    assert row["sha256"] == expected

    # Ledger file written and parseable
    ledger = tmp_path / SELF_MODEL_LEDGER
    assert ledger.exists()
    parsed = json.loads(ledger.read_text().strip().splitlines()[-1])
    assert parsed["schema"] == "SIFTA_STEERING_SELF_MODEL_RECEIPT_V1"
    assert parsed["truth_label"] == TRUTH_LABEL
    assert parsed["truth_boundary"] == TRUTH_BOUNDARY
    assert parsed["sha256"] == expected


def test_receipt_contains_all_signals():
    state = model_self_state(rows=_stressed_window(10))
    d = state.to_dict()
    names = {s["name"] for s in d["signals"]}
    assert names == {
        "overload", "residue_drift", "novelty_pressure",
        "metabolic_debt", "owner_pressure_load", "truth_risk_burn",
    }


# ── Demo smoke test ───────────────────────────────────────────────────

def test_demo_self_model_produces_at_least_three_sentences():
    """The demo window is engineered to stress most detectors. At least
    three sentences should fire — overload, drift, metabolic_debt."""
    demo = demo_self_model()
    sentences = demo["state"]["sentences"]
    assert len(sentences) >= 3
    assert demo["truth_label"] == TRUTH_LABEL


def test_demo_dominant_is_a_known_detector():
    demo = demo_self_model()
    dominant = demo["state"]["dominant"]
    assert dominant in {
        "overload", "residue_drift", "novelty_pressure",
        "metabolic_debt", "owner_pressure_load", "truth_risk_burn",
    }


# ── Determinism ───────────────────────────────────────────────────────

def test_model_self_state_is_deterministic_on_same_rows():
    rows = _stressed_window(10)
    s1 = model_self_state(rows=rows)
    s2 = model_self_state(rows=rows)
    # trace_id differs each call (uuid4); everything else must match
    d1 = s1.to_dict(); d1.pop("trace_id")
    d2 = s2.to_dict(); d2.pop("trace_id")
    assert d1 == d2
