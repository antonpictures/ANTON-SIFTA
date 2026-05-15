#!/usr/bin/env python3
"""Pytest coverage for the four EPR sibling modules + integration smoke.

Modules under test
------------------
1. System.swarm_epr_attention_bridge
2. System.swarm_quantum_stigmergic_substrate
3. System.swarm_epr_chorum_bridge
4. System.swarm_epr_field_memory

Integration test runs all four against a synthetic EPR ledger so the
combined surface is proven before any IDE Doctor wires them into Cursor's
widget.

Sandbox-safe: pure stdlib + pytest. No Qt, no Ollama, no real
.sifta_state mutations — every test uses tmp_path.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pytest

# ── Module imports ──────────────────────────────────────────────────────────
from System.swarm_epr_attention_bridge import (
    EPRAttentionBridge,
    EPR_TOPIC_KEYWORDS,
    TRUTH_LABEL as ATTN_TRUTH_LABEL,
    attention_for_epr_topics,
    compute_bridge,
    deposit as deposit_attn,
)
from System.swarm_quantum_stigmergic_substrate import (
    SUBSTRATE_LAYERS,
    SUBSTRATE_TRUTH_GUARD,
    SubstrateLayer,
    TRUTH_LABEL as SUBSTRATE_TRUTH_LABEL,
    layer_count,
    substrate_layers,
    substrate_payload,
    substrate_summary,
    write_substrate_receipt,
)
from System.swarm_epr_chorum_bridge import (
    ENFORCEMENT_ADVISORY,
    ENFORCEMENT_PASSIVE,
    ENFORCEMENT_STRICT,
    EPRChorumAdvisory,
    HIGH_PRESSURE_THRESHOLD,
    LOW_PRESSURE_THRESHOLD,
    TRUTH_LABEL as CHORUM_TRUTH_LABEL,
    _classify_pressure,
    compute_advisory,
    deposit_advisory,
)
from System.swarm_epr_field_memory import (
    ASCII_RAMP,
    DEFAULT_FIELDS,
    FieldMemory,
    FieldSnapshot,
    TRUTH_LABEL as MEMORY_TRUTH_LABEL,
    compute_memory,
    render_ascii,
    to_csv,
    to_json,
)
from System.swarm_architect_attention_field import (
    compute_attention,
)


# ── Helpers ─────────────────────────────────────────────────────────────────
def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _synthetic_epr_batch(ts: float, *, field_energy: float = 250.0,
                         residual: float = 0.6, fidelity: float = 0.5,
                         stgm_cost: float = 1700.0,
                         total_pairs: int = 2000,
                         kappa: float = 1.2) -> dict:
    return {
        "ts": ts,
        "schema": "SIFTA_EPR_STIGMERGIC_DISSOLUTION_V1",
        "kind": "EPR_STIGMERGIC_BATCH",
        "field_energy": field_energy,
        "stig_qm_residual": residual,
        "qm_fidelity": fidelity,
        "stgm_cost": stgm_cost,
        "total_pairs": total_pairs,
        "kappa": kappa,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Module 1 — swarm_epr_attention_bridge
# ═══════════════════════════════════════════════════════════════════════════
class TestAttentionBridge:
    def test_truth_label_v1(self):
        assert ATTN_TRUTH_LABEL == "EPR_ATTENTION_BRIDGE_V1"

    def test_topic_keywords_include_core_epr_vocab(self):
        assert "epr" in EPR_TOPIC_KEYWORDS
        assert "bell" in EPR_TOPIC_KEYWORDS
        assert "field" in EPR_TOPIC_KEYWORDS

    def test_compute_bridge_with_no_epr_rows(self, tmp_path):
        """Empty EPR ledger ⇒ zero EPR absorption, but attention field still computed."""
        ledger = tmp_path / "epr.jsonl"
        _write_jsonl(ledger, [])
        # Need trace + talk paths too — use empty.
        bridge = compute_bridge(
            now=1_000_000.0,
            epr_receipts_path=ledger,
            attention_field=compute_attention(
                now=1_000_000.0,
                trace_path=tmp_path / "trace.jsonl",
                talk_path=tmp_path / "talk.jsonl",
            ),
        )
        assert bridge.n_epr_rows_absorbed == 0
        assert bridge.truth_label == ATTN_TRUTH_LABEL

    def test_compute_bridge_absorbs_real_epr_row(self, tmp_path):
        now = 1_000_000.0
        ledger = tmp_path / "epr.jsonl"
        _write_jsonl(ledger, [_synthetic_epr_batch(now - 10)])
        bridge = compute_bridge(
            now=now,
            epr_receipts_path=ledger,
            attention_field=compute_attention(
                now=now,
                trace_path=tmp_path / "trace.jsonl",
                talk_path=tmp_path / "talk.jsonl",
            ),
        )
        assert bridge.n_epr_rows_absorbed == 1
        # field_energy is positive ⇒ axis_contribution must reflect it
        assert bridge.axis_contribution["field_dynamics"] > 0
        # decay-weighted recent field_energy is close to the input
        assert bridge.field_energy_recent == pytest.approx(250.0, rel=0.05)

    def test_attention_for_epr_topics_zero_for_irrelevant(self, tmp_path):
        af = compute_attention(
            now=1_000_000.0,
            trace_path=tmp_path / "trace.jsonl",
            talk_path=tmp_path / "talk.jsonl",
        )
        assert attention_for_epr_topics(field_obj=af) == 0.0

    def test_attention_for_epr_topics_rises_when_attention_is_epr_shaped(self, tmp_path):
        now = 1_000_000.0
        trace = tmp_path / "trace.jsonl"
        talk = tmp_path / "talk.jsonl"
        _write_jsonl(trace, [
            {"ts": now - 5,
             "intent": "EPR bell entanglement field stigmergy quantum singlet"},
        ])
        _write_jsonl(talk, [])
        af = compute_attention(now=now, trace_path=trace, talk_path=talk)
        score = attention_for_epr_topics(field_obj=af)
        assert score > 0.5  # EPR-loaded trace ⇒ strong topic salience

    def test_bridge_ledger_deposit_roundtrip(self, tmp_path):
        now = 1_000_000.0
        ledger = tmp_path / "epr.jsonl"
        _write_jsonl(ledger, [_synthetic_epr_batch(now - 5)])
        bridge = compute_bridge(
            now=now,
            epr_receipts_path=ledger,
            attention_field=compute_attention(
                now=now,
                trace_path=tmp_path / "trace.jsonl",
                talk_path=tmp_path / "talk.jsonl",
            ),
        )
        out_path = tmp_path / "bridge.jsonl"
        deposit_attn(bridge, path=out_path)
        rows = out_path.read_text("utf-8").splitlines()
        assert len(rows) == 1
        parsed = json.loads(rows[0])
        assert parsed["schema"] == ATTN_TRUTH_LABEL
        assert parsed["n_epr_rows_absorbed"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# Module 2 — swarm_quantum_stigmergic_substrate
# ═══════════════════════════════════════════════════════════════════════════
class TestSubstrate:
    def test_truth_label_v1(self):
        assert SUBSTRATE_TRUTH_LABEL == "QUANTUM_STIGMERGIC_SUBSTRATE_V1"
        assert "DESCRIPTIVE_SUBSTRATE_ONLY" in SUBSTRATE_TRUTH_GUARD

    def test_exactly_seven_layers(self):
        assert layer_count() == 7
        assert len(SUBSTRATE_LAYERS) == 7

    def test_layer_order_bottom_to_top(self):
        expected = (
            "electricity", "silicon", "transistor", "register",
            "bit_state", "swimmer", "organ",
        )
        got = tuple(layer.name for layer in SUBSTRATE_LAYERS)
        assert got == expected

    def test_layer_indices_monotonic(self):
        for i, layer in enumerate(SUBSTRATE_LAYERS):
            assert layer.index == i

    @pytest.mark.parametrize("layer", SUBSTRATE_LAYERS)
    def test_layer_carries_truth_guard(self, layer):
        assert layer.physical_form.strip()
        assert layer.next_layer_constraint.strip()
        assert layer.does_not_support.strip(), (
            f"layer {layer.name}: does_not_support must NOT be empty"
        )
        authors, title, year, venue, doi = layer.peer_review_anchor
        assert authors and title and venue
        assert 1900 < year <= 2100
        if doi:
            assert doi.startswith("10."), f"layer {layer.name}: bad DOI"

    def test_substrate_summary_is_human_readable(self):
        s = substrate_summary()
        assert "seven-layer" in s
        assert "electricity" in s
        assert "organ" in s
        assert "classical room-temperature silicon" in s
        # never claim quantum coherence
        assert "quantum coherence claimed" not in s or \
               "no quantum coherence claimed" in s

    def test_substrate_payload_stable(self):
        p = substrate_payload()
        assert p["truth_label"] == SUBSTRATE_TRUTH_LABEL
        assert p["layer_count"] == 7
        assert len(p["layers"]) == 7
        # Round-trip JSON without loss.
        ser = json.dumps(p, sort_keys=True)
        again = substrate_payload()
        assert ser == json.dumps(again, sort_keys=True)

    def test_substrate_receipt_writer(self, tmp_path):
        out = tmp_path / "substrate.jsonl"
        row = write_substrate_receipt(state_root=tmp_path, receipt_path=out)
        assert row["truth_label"] == SUBSTRATE_TRUTH_LABEL
        assert "sha256" in row and len(row["sha256"]) == 64
        lines = out.read_text("utf-8").splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["layer_count"] == 7

    def test_layer_frozen(self):
        with pytest.raises(Exception):
            SUBSTRATE_LAYERS[0].index = 99  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════════
# Module 3 — swarm_epr_chorum_bridge
# ═══════════════════════════════════════════════════════════════════════════
class TestChorumBridge:
    def test_truth_label_and_thresholds(self):
        assert CHORUM_TRUTH_LABEL == "EPR_CHORUM_PRESSURE_BRIDGE_V1"
        assert 0 < LOW_PRESSURE_THRESHOLD < HIGH_PRESSURE_THRESHOLD

    def test_classify_pressure_bands(self):
        adv, _ = _classify_pressure(LOW_PRESSURE_THRESHOLD / 2)
        assert adv == ENFORCEMENT_PASSIVE
        adv, _ = _classify_pressure((LOW_PRESSURE_THRESHOLD + HIGH_PRESSURE_THRESHOLD) / 2)
        assert adv == ENFORCEMENT_ADVISORY
        adv, _ = _classify_pressure(HIGH_PRESSURE_THRESHOLD * 2)
        assert adv == ENFORCEMENT_STRICT

    def test_empty_ledger_is_passive(self, tmp_path):
        ledger = tmp_path / "epr.jsonl"
        _write_jsonl(ledger, [])
        adv = compute_advisory(
            now=1_000_000.0, window_s=60.0,
            epr_receipts_path=ledger,
        )
        assert adv.n_events_in_window == 0
        assert adv.enforcement_mode_advisory == ENFORCEMENT_PASSIVE

    def test_high_rate_low_residual_pushes_to_strict(self, tmp_path):
        now = 1_000_000.0
        ledger = tmp_path / "epr.jsonl"
        # Lots of events in window with tight (small) residual → very high
        # pressure → advisory == strict.
        rows = [
            _synthetic_epr_batch(now - i, residual=0.01)
            for i in range(1, 30)
        ]
        _write_jsonl(ledger, rows)
        adv = compute_advisory(
            now=now, window_s=60.0, epr_receipts_path=ledger,
        )
        assert adv.n_events_in_window == 29
        assert adv.rate_events_per_min > 0
        assert adv.enforcement_mode_advisory == ENFORCEMENT_STRICT

    def test_deposit_does_not_mutate_chorum_state(self, tmp_path):
        ledger = tmp_path / "epr.jsonl"
        _write_jsonl(ledger, [_synthetic_epr_batch(1_000_000.0 - 5)])
        adv = compute_advisory(
            now=1_000_000.0, window_s=60.0, epr_receipts_path=ledger,
        )
        log = tmp_path / "chorum_gate_log.jsonl"
        state = tmp_path / "chorum_gate_state.json"
        state.write_text("{\"enforcement_mode\":\"passive\"}", "utf-8")
        deposit_advisory(adv, chorum_log_path=log)
        # state file must be untouched
        assert json.loads(state.read_text("utf-8"))["enforcement_mode"] == "passive"
        # log file gained one row, tagged advisory_only
        line = log.read_text("utf-8").strip()
        parsed = json.loads(line)
        assert parsed["kind"] == "EPR_PRESSURE_ADVISORY"
        assert parsed["advisory_only"] is True
        assert parsed["mutates_chorum_state"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Module 4 — swarm_epr_field_memory
# ═══════════════════════════════════════════════════════════════════════════
class TestFieldMemory:
    def test_truth_label_and_default_fields(self):
        assert MEMORY_TRUTH_LABEL == "EPR_FIELD_MEMORY_V1"
        assert "field_energy" in DEFAULT_FIELDS
        assert "qm_fidelity" in DEFAULT_FIELDS

    def test_empty_ledger_renders_empty_message(self, tmp_path):
        ledger = tmp_path / "epr.jsonl"
        _write_jsonl(ledger, [])
        mem = compute_memory(
            now=1_000_000.0, epr_receipts_path=ledger,
        )
        assert mem.empty()
        out = render_ascii(mem)
        assert "empty" in out.lower()

    def test_snapshots_in_chronological_order(self, tmp_path):
        now = 1_000_000.0
        ledger = tmp_path / "epr.jsonl"
        # Write rows out of order — memory must sort them.
        _write_jsonl(ledger, [
            _synthetic_epr_batch(now - 100),
            _synthetic_epr_batch(now - 1),
            _synthetic_epr_batch(now - 50),
        ])
        mem = compute_memory(now=now, epr_receipts_path=ledger)
        ts_list = [s.ts for s in mem.snapshots]
        assert ts_list == sorted(ts_list)
        assert mem.n_snapshots == 3

    def test_decayed_mean_skews_toward_recent(self, tmp_path):
        now = 1_000_000.0
        ledger = tmp_path / "epr.jsonl"
        _write_jsonl(ledger, [
            _synthetic_epr_batch(now - 1000, field_energy=10.0),
            _synthetic_epr_batch(now - 1,    field_energy=1000.0),
        ])
        mem = compute_memory(
            now=now, half_life_s=60.0, epr_receipts_path=ledger,
        )
        # Recent high value dominates because old one decayed away.
        assert mem.decayed_means["field_energy"] > 500.0

    def test_ascii_rendering_has_one_row_per_field(self, tmp_path):
        now = 1_000_000.0
        ledger = tmp_path / "epr.jsonl"
        _write_jsonl(ledger, [
            _synthetic_epr_batch(now - i) for i in range(1, 10)
        ])
        mem = compute_memory(
            now=now, epr_receipts_path=ledger,
            fields_of_interest=("field_energy", "qm_fidelity"),
        )
        out = render_ascii(mem, width=20)
        assert "field_energy" in out
        assert "qm_fidelity" in out
        # ramp characters used somewhere in the rendering
        assert any(ch in out for ch in ASCII_RAMP[1:])

    def test_csv_and_json_export(self, tmp_path):
        now = 1_000_000.0
        ledger = tmp_path / "epr.jsonl"
        _write_jsonl(ledger, [_synthetic_epr_batch(now - 5)])
        mem = compute_memory(now=now, epr_receipts_path=ledger)
        csv = to_csv(mem)
        assert csv.startswith("ts,")
        assert "field_energy" in csv.splitlines()[0]
        # JSON round-trips.
        parsed = json.loads(to_json(mem))
        assert parsed["truth_label"] == MEMORY_TRUTH_LABEL
        assert parsed["n_snapshots"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# Integration — all four modules together
# ═══════════════════════════════════════════════════════════════════════════
class TestEPRLaneIntegration:
    """Run all four modules against one synthetic EPR ledger."""

    def test_four_modules_consume_same_synthetic_ledger(self, tmp_path):
        now = 1_000_000.0
        ledger = tmp_path / "epr.jsonl"
        # 15 batches over a 5-minute window, residual narrows toward QM
        rows = []
        for i in range(15):
            rows.append(_synthetic_epr_batch(
                now - (60 + i * 20),
                field_energy=200.0 + i * 5.0,
                residual=max(0.05, 0.7 - i * 0.04),
                fidelity=min(0.95, 0.5 + i * 0.03),
            ))
        _write_jsonl(ledger, rows)

        # Module 1 — attention bridge
        bridge = compute_bridge(
            now=now, epr_receipts_path=ledger,
            attention_field=compute_attention(
                now=now,
                trace_path=tmp_path / "trace.jsonl",
                talk_path=tmp_path / "talk.jsonl",
            ),
        )
        assert bridge.n_epr_rows_absorbed > 0
        assert bridge.field_energy_recent > 0

        # Module 2 — substrate doctrine is independent of ledger,
        # but the integration assertion is that calling it does NOT
        # corrupt or read EPR data.
        payload = substrate_payload()
        assert payload["layer_count"] == 7

        # Module 3 — chorum advisory
        adv = compute_advisory(
            now=now, window_s=600.0, epr_receipts_path=ledger,
        )
        assert adv.n_events_in_window > 0
        assert adv.enforcement_mode_advisory in (
            ENFORCEMENT_PASSIVE, ENFORCEMENT_ADVISORY, ENFORCEMENT_STRICT
        )

        # Module 4 — field memory
        mem = compute_memory(now=now, epr_receipts_path=ledger)
        assert mem.n_snapshots > 0
        out = render_ascii(mem, width=30)
        # All four modules produced their own truth-labeled output
        # without any one of them mutating the input ledger.
        assert ledger.read_text("utf-8").count("\n") == 15
        # ASCII render visibly shows a tail.
        assert "EPR field memory" in out
