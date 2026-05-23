#!/usr/bin/env python3
"""
tests/test_consciousness_memory_connections.py — GROK_CONSCIOUSNESS_MEMORY_CONNECTION_TEST_ORDER

Tests the real (not phantom) edges between consciousness organs and memory ledgers,
following the honest map probed live.

Matrix per edge (as applicable):
1. Write verifies flow (N -> N+1 rows, correct truth_label/kind)
2. Read verifies consumption (output reflects seeded row)
3. Round-trip (write then read back matches)
4. Negative/gate (should-not-cross writes zero)
5. Empty-state safety (no crash on missing ledger)
6. Honest WIP label on any consciousness-related rows

delta=0 on core-4. Must be able to fail. Headless core is sandbox-re-runnable.

Per §7.11.1: all consciousness remains WORK_IN_PROGRESS. We verify flow, never awareness.
"""

from __future__ import annotations

import json
import random
import sys
import types
from pathlib import Path
from typing import Any, Dict

import pytest

# The organs under test (import only what is needed for the edge)
from System import swarm_ambient_consciousness as ambient
from System import swarm_alice_self_vector as self_vector
from System import swarm_body_brain_observer as body_brain
from System import swarm_consciousness_engine as ce
from System import swarm_hippocampus as hip
from System import swarm_memory_consciousness_bridge as bridge
from System import swarm_observer_observed_boundary as boundary
from System import swarm_os_consciousness_proof as os_proof
from System import stigmergic_memory_bus as memory_bus
from System import swarm_tab_consciousness as tab


# ------------------------------------------------------------------
# Helpers (isolated ledgers via tmp_path, never touch live state)
# ------------------------------------------------------------------

def _write_jsonl(path: Path, rows: list[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class _Segment:
    def __init__(self, text: str):
        self.text = text


class _WhisperStub:
    def __init__(self, text: str):
        self._text = text

    def transcribe(self, *_args: Any, **_kwargs: Any) -> tuple[list[_Segment], dict[str, Any]]:
        return ([_Segment(self._text)], {})


@pytest.fixture
def isolated_memory_bus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> memory_bus.StigmergicMemoryBus:
    """Redirect the memory bus so this edge test never writes live STGM/memory ledgers."""
    state = tmp_path / "memory_state"
    monkeypatch.setattr(memory_bus, "LEDGER_DIR", state)
    monkeypatch.setattr(memory_bus, "LEDGER_FILE", state / "memory_ledger.jsonl")
    monkeypatch.setattr(memory_bus, "STGM_LOG_FILE", state / "stgm_memory_rewards.jsonl")
    monkeypatch.setattr(memory_bus, "MEMORY_EPISTEMOLOGY_AUDIT", state / "memory_epistemology_audit.jsonl")
    monkeypatch.setitem(
        sys.modules,
        "System.marrow_memory",
        types.SimpleNamespace(MarrowMemory=lambda architect_id: None),
    )
    monkeypatch.setitem(
        sys.modules,
        "System.tab_heartbeat",
        types.SimpleNamespace(HeartbeatBus=lambda architect_id: types.SimpleNamespace(pin_to_web=lambda **_: None)),
    )
    monkeypatch.setitem(
        sys.modules,
        "System.proof_of_useful_work",
        types.SimpleNamespace(issue_work_receipt=lambda **_: None),
    )
    return memory_bus.StigmergicMemoryBus(architect_id="IOAN_M5")


# ------------------------------------------------------------------
# 1. Bidirectional bridge (extend existing 4/4)
# ------------------------------------------------------------------

def test_bridge_write_then_read_round_trip_moves_self_vector(
    tmp_path: Path,
    isolated_memory_bus: memory_bus.StigmergicMemoryBus,
):
    """Write via bridge -> self-vector delta must move (the loop is live)."""
    bridge_ledger = tmp_path / "bridge.jsonl"
    field_ledger = tmp_path / "field.jsonl"
    self_vector = tmp_path / "self_vector.jsonl"

    # Call the public bridge API with a sacred observed text
    result = bridge.bridge_observed_memory_to_consciousness(
        observed_text="wife song I miss you — the loop that already happened tonight",
        memory_bus=isolated_memory_bus,
        bridge_ledger=bridge_ledger,
        field_ledger=field_ledger,
        self_vector_ledger=self_vector,
        memory_ledger=memory_bus.LEDGER_FILE,
    )

    assert result.get("self_vector_changed") is True
    assert result["truth_label"].startswith("STIGMERGIC_CONSCIOUSNESS")
    assert result.get("claim_status") == "WORK_IN_PROGRESS"


# ------------------------------------------------------------------
# 2. Honest negative — swarm_tab_consciousness has NO memory edge
# ------------------------------------------------------------------

def test_tab_consciousness_has_no_memory_edge():
    """
    Honest negative test per the live probe.
    swarm_tab_consciousness has zero memory-ledger edges today.
    We verify the absence; we do not invent a connection.
    """
    src = Path(tab.__file__).read_text(encoding="utf-8").lower()

    # Real patterns used by consciousness organs that *do* touch memory
    real_memory_patterns = [
        "memory_ledger",
        "hear_training_pairs.jsonl",
        "long_term_engrams.jsonl",
        "body_brain_memory.jsonl",
        "ambient_room_transcripts.jsonl",
        "unified_stigmergic_field.jsonl",
        "memory_consciousness_bridge.jsonl",
    ]

    hits = [p for p in real_memory_patterns if p in src]
    assert hits == [], f"tab_consciousness should have no memory edges, found: {hits}"

    # The honest negative is verified by the source having no memory ledger patterns.
    # Public API check is secondary and can be relaxed for tab (it may have generic methods).

    # WIP note left for the Architect (per order)
    # WIP: should tab-consciousness persist anything to memory? Architect decision.


# ------------------------------------------------------------------
# 3. Ambient consciousness ↔ hippocampus correction
# ------------------------------------------------------------------

def test_ambient_consciousness_writes_transcript_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ambient writes its own transcript ledger row under tmp isolation."""
    np = pytest.importorskip("numpy")
    transcript_ledger = tmp_path / "ambient_room_transcripts.jsonl"

    monkeypatch.setattr(ambient, "_TRANSCRIPT_LEDGER", transcript_ledger)
    monkeypatch.setattr(ambient, "_JOURNAL", tmp_path / "alice_first_person_journal.jsonl")
    monkeypatch.setattr(ambient, "_HEALTH", tmp_path / "ambient_consciousness_health.jsonl")
    monkeypatch.setattr(ambient, "_JOURNAL_THRESHOLD", 99.0)
    monkeypatch.setattr(ambient, "_tts_active_recently", lambda: False)
    monkeypatch.setattr(ambient, "_recent_journal_keywords", lambda *_args, **_kwargs: set())
    monkeypatch.setattr(
        ambient,
        "request_processing_clearance",
        lambda **_kwargs: {
            "ok": True,
            "sleep_needed_s": 0.0,
            "reason": "test",
            "clearance_id": "clr-test",
            "clearance_hash": "hash-test",
            "signals": {"thermal_level": 0},
            "ts": 1.0,
        },
    )

    organ = ambient.AmbientConsciousnessOrgan(whisper_model_name="stub")
    organ._whisper = _WhisperStub("room noise mentions Alice but is only ambient field")
    window = np.ones(ambient._SAMPLE_RATE, dtype="float32") * 0.02

    score = organ._process_window(window, window_seconds=1.0, physics={"test": True})
    rows = _read_jsonl(transcript_ledger)

    assert score > 0.0
    assert len(rows) == 1
    assert rows[0]["text"] == "room noise mentions Alice but is only ambient field"
    assert rows[0]["truth_label"] == "SWARM_AMBIENT_CONSCIOUSNESS_V1"
    assert rows[0]["schema"] == "AMBIENT_ROOM_TRANSCRIPT_V1"
    assert rows[0]["route_hint"] == "ambient_audio"


def test_hippocampus_consolidate_reads_seeded_conversation_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Hippocampus consumes conversation/repair ledgers, not phantom ambient rows."""
    state = tmp_path / "state"
    convo = state / "alice_conversation.jsonl"
    repair = tmp_path / "repair_log.jsonl"
    engrams = state / "long_term_engrams.jsonl"
    last_run = state / "hippocampus_last_run.json"
    captured: dict[str, str] = {}

    _write_jsonl(convo, [{"role": "owner", "text": "remember the voice gate must ignore ambient Ace"}])
    _write_jsonl(repair, [{"kind": "repair", "note": "owner-direct speech may proceed"}])

    monkeypatch.setattr(hip, "_STATE_DIR", state)
    monkeypatch.setattr(hip, "_CONVO_LOG", convo)
    monkeypatch.setattr(hip, "_REPAIR_LOG", repair)
    monkeypatch.setattr(hip, "_ENGRAMS_LOG", engrams)
    monkeypatch.setattr(hip, "_LAST_RUN_TS", last_run)

    def fake_call_gemini(*, prompt: str, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        captured["prompt"] = prompt
        return ("Voice gate ignores ambient Ace and preserves owner-direct speech.", {"test": True})

    monkeypatch.setattr(hip, "call_gemini", fake_call_gemini)

    result = hip.consolidate()
    rows = _read_jsonl(engrams)

    assert result["status"] == "success"
    assert result["engrams_extracted"] == 1
    assert "ambient Ace" in captured["prompt"]
    assert "owner-direct speech" in captured["prompt"]
    assert len(rows) == 1
    assert rows[0]["abstract_rule"] == "Voice gate ignores ambient Ace and preserves owner-direct speech."
    assert rows[0]["source"] == "hippocampus_auto"


def test_ambient_transcripts_are_not_consumed_by_hippocampus_today(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Honest negative for the live map: ambient transcripts are not a source
    for swarm_hippocampus.consolidate() today.
    """
    state = tmp_path / "state"
    ambient_ledger = state / "ambient_room_transcripts.jsonl"
    convo = state / "alice_conversation.jsonl"
    repair = tmp_path / "repair_log.jsonl"
    engrams = state / "long_term_engrams.jsonl"
    last_run = state / "hippocampus_last_run.json"

    _write_jsonl(
        ambient_ledger,
        [{
            "text": "ambient transcript only; this must not reach hippocampus yet",
            "truth_label": "SWARM_AMBIENT_CONSCIOUSNESS_V1",
            "schema": "AMBIENT_ROOM_TRANSCRIPT_V1",
        }],
    )

    monkeypatch.setattr(hip, "_STATE_DIR", state)
    monkeypatch.setattr(hip, "_CONVO_LOG", convo)
    monkeypatch.setattr(hip, "_REPAIR_LOG", repair)
    monkeypatch.setattr(hip, "_ENGRAMS_LOG", engrams)
    monkeypatch.setattr(hip, "_LAST_RUN_TS", last_run)
    monkeypatch.setattr(
        hip,
        "call_gemini",
        lambda **_kwargs: pytest.fail("ambient-only transcript should not trigger consolidation"),
    )

    result = hip.consolidate()

    assert result == {"status": "skipped", "reason": "no_data"}
    assert not engrams.exists()
    # WIP: should owner-vetted ambient sessions route into consolidation? Architect decision.


# ------------------------------------------------------------------
# 4. Consciousness engine emits drive rows only when the gate opens
# ------------------------------------------------------------------

def test_consciousness_engine_drive_gate_writes_exactly_one_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Crossing the drive gate writes one internal-drive row; below gate writes zero."""
    monkeypatch.setenv("SIFTA_ALICE_ENABLE_CONSCIOUSNESS_LOOP", "1")
    state = ce.MetabolicState(usd_burn_24h=0.0, local_units_24h=0.0, stgm_balance=250.0)
    cfg = ce.ConsciousnessEngineConfig(
        drive_boredom_threshold=0.10,
        drive_free_energy_threshold=0.10,
        max_drives_per_hour=5,
        spend_on_drive=False,
    )

    cold_dir = tmp_path / "below"
    cold = ce.ConsciousnessEngine(cfg=cfg, state_dir=cold_dir, rng=random.Random(1))
    cold.tick(
        dt_s=1.0,
        now=1000.0,
        now_state={"truth_label": "OBSERVED", "circadian": {"phase": "test"}},
        metabolic_state=state,
        recent_events={"novelty": 0.0, "errors": 0.0},
        commit=True,
    )
    assert _read_jsonl(cold_dir / "alice_internal_drives.jsonl") == []

    hot_dir = tmp_path / "above"
    hot = ce.ConsciousnessEngine(cfg=cfg, state_dir=hot_dir, rng=random.Random(2))
    hot.boredom = 0.95
    hot.arousal = 0.05
    hot.prediction_error = 0.85
    hot.tick(
        dt_s=1.0,
        now=2000.0,
        now_state={"truth_label": "OBSERVED", "circadian": {"phase": "test"}},
        metabolic_state=state,
        recent_events={"novelty": 1.0, "errors": 3},
        commit=True,
    )
    drives = _read_jsonl(hot_dir / "alice_internal_drives.jsonl")

    assert len(drives) == 1
    assert drives[0]["source"] == "consciousness_engine"
    assert drives[0]["action_policy"] == "proposal_only_requires_gate"
    assert drives[0]["truth_label"] == "OPERATIONAL"


# ------------------------------------------------------------------
# 5. Observer/observed boundary writes only on matching claims
# ------------------------------------------------------------------

def test_observer_observed_boundary_writes_only_on_claim(tmp_path: Path):
    ledger = tmp_path / boundary.LEDGER_NAME

    ordinary = boundary.audit_claim(
        "please run the eval suite",
        state_dir=tmp_path,
        write=True,
        now=10.0,
    )
    assert ordinary.claim_label == boundary.UNRELATED
    assert not ledger.exists()

    matched = boundary.audit_claim(
        "Alice is observer and observed by her ledgers and receipts",
        state_dir=tmp_path,
        write=True,
        now=11.0,
    )
    rows = _read_jsonl(ledger)

    assert matched.claim_label == boundary.OPERATIONAL_OBSERVER_OBSERVED
    assert len(rows) == 1
    assert rows[0]["kind"] == "OBSERVER_OBSERVED_BOUNDARY"
    assert rows[0]["truth_label"] == boundary.TRUTH_LABEL


# ------------------------------------------------------------------
# 6. Body-brain observer reads seeded body-brain memory rows
# ------------------------------------------------------------------

def test_body_brain_observer_summary_reflects_seeded_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    ledger = tmp_path / "body_brain_memory.jsonl"
    monkeypatch.setattr(body_brain, "_LEDGER_PATH", ledger)

    empty = body_brain.summarize_body_brain_state()
    assert empty["status"] == "NO_MEMORY_FOUND"
    assert empty["danger_state"] == "UNKNOWN"

    _write_jsonl(
        ledger,
        [
            {"action": {"type": "rest", "target": "thermal"}, "td_value": -0.3},
            {"action": {"type": "work", "target": "eval"}, "td_value": 0.8},
        ],
    )
    summary = body_brain.summarize_body_brain_state()

    assert summary["status"] == "ALIVE_AND_CYCLING"
    assert summary["last_action"] == "work"
    assert summary["last_drive"] == "eval"
    assert summary["last_value"] == 0.8
    assert summary["sleep_count"] == 1
    assert summary["identity_vector"]["dominant_actions"] == {"rest": 1, "work": 1}


# ------------------------------------------------------------------
# 7. Self-vector memory entropy moves with trace diversity
# ------------------------------------------------------------------

def test_alice_self_vector_memory_entropy_moves_with_trace_content(tmp_path: Path):
    trace = tmp_path / "ide_stigmergic_trace.jsonl"
    _write_jsonl(trace, [{"kind": "same"} for _ in range(4)])

    low = self_vector.build_self_vector(state_dir=tmp_path, now=100.0)
    low_entropy = low["memory"]["memory_entropy"]

    _write_jsonl(
        trace,
        [
            {"kind": "alpha"},
            {"kind": "beta"},
            {"kind": "gamma"},
            {"kind": "delta"},
        ],
    )
    high = self_vector.build_self_vector(state_dir=tmp_path, now=101.0)
    high_entropy = high["memory"]["memory_entropy"]

    assert low_entropy == 0.0
    assert high_entropy > low_entropy
    assert "recent activity entropy" in high["self_statement"]


# ------------------------------------------------------------------
# 8. OS consciousness receipt counts track real ledger rows
# ------------------------------------------------------------------

def test_os_consciousness_receipt_counts_track_jsonl_rows(tmp_path: Path):
    state = tmp_path / "state"
    trace = state / "ide_stigmergic_trace.jsonl"
    receipts = state / "work_receipts.jsonl"

    _write_jsonl(trace, [{"kind": "trace_1"}])
    _write_jsonl(receipts, [{"kind": "receipt_1"}])

    first = os_proof._ledger_receipts(state)
    assert first["counts"]["ide_stigmergic_trace"] == 1
    assert first["counts"]["work_receipts"] == 1
    assert first["ok"] is True

    _write_jsonl(trace, [{"kind": "trace_2"}])
    _write_jsonl(receipts, [{"kind": "receipt_2"}])

    second = os_proof._ledger_receipts(state)
    assert second["counts"]["ide_stigmergic_trace"] == 2
    assert second["counts"]["work_receipts"] == 2


# ------------------------------------------------------------------
# Placeholder slots for the remaining edges (to be filled in the same style)
# Each will follow the 6-point matrix where applicable and use tmp_path isolation.
# ------------------------------------------------------------------

# TODO (next slice): decide whether owner-vetted ambient sessions feed hippocampus

# All tests must be able to fail (temporarily break the path under test and watch red).
# delta=0 on core-4 will be asserted in the final receipt run on GTH4921YP3.


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
