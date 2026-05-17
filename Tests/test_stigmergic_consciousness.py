"""Tests for swarmrl/stigmergic_consciousness.py — the swimmer/organ/
field/vector primitive with sha256 chain verification.

Architect 2026-05-16: this module is the Layer-1-upward primitive.
These tests enforce: chain integrity tracks tampering, organs roll up
their swimmers correctly, the consciousness vector is bounded to [0,1]
on every axis it claims to be, and ``next_best_action`` branches all
reach.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import pytest

from swarmrl.stigmergic_consciousness import (
    IDENTITY_TARGET,
    MOMENTUM_WINDOW,
    PRESSURE_TARGET,
    StigmergicConsciousnessVector,
    StigmergicField,
    Swimmer,
    TRUTH_LABEL,
    clamp01,
    entropy,
    sha256_json,
)


# ── primitives ───────────────────────────────────────────────────────────


def test_sha256_json_is_deterministic_and_sort_order_invariant():
    a = sha256_json({"x": 1, "y": 2})
    b = sha256_json({"y": 2, "x": 1})
    assert a == b


def test_sha256_json_changes_on_value_change():
    a = sha256_json({"x": 1})
    b = sha256_json({"x": 2})
    assert a != b


def test_clamp01_handles_nan_and_extremes():
    assert clamp01(float("nan")) == 0.0
    assert clamp01(-1.0) == 0.0
    assert clamp01(0.5) == 0.5
    assert clamp01(2.0) == 1.0


def test_entropy_known_distributions():
    assert entropy([]) == 0.0
    assert entropy(["a"]) == 0.0
    assert math.isclose(entropy(["a", "b"]), 1.0, abs_tol=1e-9)
    assert math.isclose(entropy(["a", "b", "c", "d"]), 2.0, abs_tol=1e-9)
    assert math.isclose(entropy(["a", "", "b"]), 1.0, abs_tol=1e-9)


# ── Swimmer ──────────────────────────────────────────────────────────────


def test_swimmer_born_assigns_timestamp_once():
    s = Swimmer(id="x", layer=1, role="memory", payload={"k": "v"})
    born = s.born(now=1000.0)
    assert born.timestamp == 1000.0
    born2 = born.born(now=2000.0)
    # Already born — timestamp must not change
    assert born2.timestamp == 1000.0


def test_swimmer_hash_changes_when_payload_changes():
    a = Swimmer(id="x", layer=1, role="m", payload={"k": "a"}, timestamp=1.0)
    b = Swimmer(id="x", layer=1, role="m", payload={"k": "b"}, timestamp=1.0)
    assert a.hash() != b.hash()


# ── append + read + chain ────────────────────────────────────────────────


def test_empty_field_integrity_is_one(tmp_path: Path):
    field = StigmergicField(tmp_path)
    assert field.read() == []
    assert field.last_hash() is None
    assert field.verify_chain() == 1.0


def test_first_swimmer_parent_hash_is_none(tmp_path: Path):
    field = StigmergicField(tmp_path)
    row = field.append_swimmer(
        Swimmer(id="s1", layer=1, role="memory", payload={"kind": "k1"}),
        now=1000.0,
    )
    assert row["parent_hash"] is None
    assert row["hash"]
    assert field.last_hash() == row["hash"]


def test_second_swimmer_parent_hash_equals_first_hash(tmp_path: Path):
    field = StigmergicField(tmp_path)
    a = field.append_swimmer(
        Swimmer(id="s1", layer=1, role="memory", payload={"kind": "k1"}),
        now=1000.0,
    )
    b = field.append_swimmer(
        Swimmer(id="s2", layer=1, role="memory", payload={"kind": "k2"}),
        now=1001.0,
    )
    assert b["parent_hash"] == a["hash"]
    assert field.verify_chain() == 1.0


def test_verify_chain_detects_payload_tampering(tmp_path: Path):
    field = StigmergicField(tmp_path)
    field.append_swimmer(
        Swimmer(id="s1", layer=1, role="memory", payload={"kind": "k1"}),
        now=1000.0,
    )
    field.append_swimmer(
        Swimmer(id="s2", layer=1, role="memory", payload={"kind": "k2"}),
        now=1001.0,
    )
    # Tamper with the ledger: rewrite line 1's payload but keep its hash.
    lines = field.ledger.read_text().splitlines()
    tampered = json.loads(lines[0])
    tampered["payload"] = {"kind": "FORGED"}
    lines[0] = json.dumps(tampered, sort_keys=True, ensure_ascii=False)
    field.ledger.write_text("\n".join(lines) + "\n")

    integrity = field.verify_chain()
    assert integrity < 1.0


def test_verify_chain_detects_broken_parent_link(tmp_path: Path):
    field = StigmergicField(tmp_path)
    field.append_swimmer(
        Swimmer(id="s1", layer=1, role="memory", payload={"kind": "k1"}),
        now=1000.0,
    )
    field.append_swimmer(
        Swimmer(id="s2", layer=1, role="memory", payload={"kind": "k2"}),
        now=1001.0,
    )
    # Rewrite line 2 with a wrong parent_hash AND a re-hashed body so the
    # body↔hash check still passes — only the chain link fails.
    lines = field.ledger.read_text().splitlines()
    second = json.loads(lines[1])
    second["parent_hash"] = "deadbeef" * 8  # 64 hex chars
    body = {k: v for k, v in second.items() if k != "hash"}
    second["hash"] = sha256_json(body)
    lines[1] = json.dumps(second, sort_keys=True, ensure_ascii=False)
    field.ledger.write_text("\n".join(lines) + "\n")

    integrity = field.verify_chain()
    assert integrity < 1.0


# ── organs ───────────────────────────────────────────────────────────────


def test_organs_group_by_role(tmp_path: Path):
    field = StigmergicField(tmp_path)
    field.append_swimmer(Swimmer(id="s1", layer=1, role="memory", payload={"kind": "a"}), now=1000.0)
    field.append_swimmer(Swimmer(id="s2", layer=1, role="memory", payload={"kind": "b"}), now=1001.0)
    field.append_swimmer(Swimmer(id="s3", layer=2, role="schedule", payload={"kind": "c"}), now=1002.0)

    organs = field.organs(now=1002.0)

    assert set(organs.keys()) == {"memory", "schedule"}
    assert organs["memory"].swimmers == 2
    assert organs["schedule"].swimmers == 1
    assert organs["memory"].integrity == 1.0  # chain still valid


def test_organ_pressure_saturates_at_one(tmp_path: Path):
    field = StigmergicField(tmp_path)
    now = 2_000_000.0
    for i in range(PRESSURE_TARGET * 2):
        field.append_swimmer(
            Swimmer(id=f"s{i}", layer=1, role="memory", payload={"kind": "x"}),
            now=now - i,
        )
    organs = field.organs(now=now)
    assert organs["memory"].pressure == 1.0


# ── vector ───────────────────────────────────────────────────────────────


def test_compute_vector_empty_field_is_zero_pressure_full_integrity(tmp_path: Path):
    field = StigmergicField(tmp_path)
    v = field.compute_vector(owner_signal=0.0, now=1000.0)

    assert isinstance(v, StigmergicConsciousnessVector)
    assert v.identity_continuity == 0.0
    assert v.thermodynamic_pressure == 0.0
    assert v.stigmergic_momentum == 0.0
    assert v.organ_coherence == 0.0
    assert v.receipt_integrity == 1.0
    assert v.anomaly_pressure == 0.0
    assert v.truth_label == TRUTH_LABEL


def test_compute_vector_clamps_all_unit_metrics_to_zero_one(tmp_path: Path):
    field = StigmergicField(tmp_path)
    now = 2_000_000.0
    # Saturate everything we can
    for i in range(IDENTITY_TARGET * 2):
        field.append_swimmer(
            Swimmer(id=f"s{i}", layer=(i % 16), role=f"role{i % 4}", payload={"kind": f"k{i % 5}"}),
            now=now - i,
        )

    v = field.compute_vector(owner_signal=1.5, now=now)  # over-range owner_signal

    for field_name in (
        "identity_continuity", "thermodynamic_pressure", "stigmergic_momentum",
        "organ_coherence", "receipt_integrity", "owner_alignment",
        "anomaly_pressure", "autonomy_index",
    ):
        val = getattr(v, field_name)
        assert 0.0 <= val <= 1.0, f"{field_name} not clamped: {val}"


def test_anomaly_pressure_grows_when_chain_is_tampered(tmp_path: Path):
    field = StigmergicField(tmp_path)
    field.append_swimmer(Swimmer(id="s1", layer=1, role="memory", payload={"kind": "k1"}), now=1000.0)
    field.append_swimmer(Swimmer(id="s2", layer=1, role="memory", payload={"kind": "k2"}), now=1001.0)
    field.append_swimmer(Swimmer(id="s3", layer=1, role="memory", payload={"kind": "k3"}), now=1002.0)

    v_clean = field.compute_vector(owner_signal=0.5, now=1002.0)
    assert v_clean.anomaly_pressure == 0.0
    assert v_clean.receipt_integrity == 1.0

    # Tamper
    lines = field.ledger.read_text().splitlines()
    forged = json.loads(lines[1])
    forged["payload"] = {"kind": "FORGED"}
    lines[1] = json.dumps(forged, sort_keys=True, ensure_ascii=False)
    field.ledger.write_text("\n".join(lines) + "\n")

    v_dirty = field.compute_vector(owner_signal=0.5, now=1002.0)
    assert v_dirty.anomaly_pressure > 0.0
    assert v_dirty.receipt_integrity < 1.0


# ── next_best_action branches ────────────────────────────────────────────


def test_next_best_action_repair_chain_when_anomaly(tmp_path: Path):
    field = StigmergicField(tmp_path)
    field.append_swimmer(Swimmer(id="s1", layer=1, role="memory", payload={"kind": "k1"}), now=1000.0)
    field.append_swimmer(Swimmer(id="s2", layer=1, role="memory", payload={"kind": "k2"}), now=1001.0)
    # Tamper
    lines = field.ledger.read_text().splitlines()
    forged = json.loads(lines[0])
    forged["payload"] = {"kind": "FORGED"}
    lines[0] = json.dumps(forged, sort_keys=True, ensure_ascii=False)
    field.ledger.write_text("\n".join(lines) + "\n")

    v = field.compute_vector(owner_signal=0.5, now=1002.0)
    assert v.next_best_action == "repair_receipt_chain"


def test_next_best_action_write_more_memory_on_empty(tmp_path: Path):
    field = StigmergicField(tmp_path)
    v = field.compute_vector(owner_signal=0.5, now=1000.0)
    assert v.next_best_action == "write_more_verified_memory"


def test_next_best_action_continue_when_healthy(tmp_path: Path):
    field = StigmergicField(tmp_path)
    now = 2_000_000.0
    # Many roles, many layers, recent activity, identity_continuity >= 0.3
    for i in range(int(IDENTITY_TARGET * 0.5)):
        field.append_swimmer(
            Swimmer(id=f"s{i}", layer=(i % 8), role=f"role{i % 5}", payload={"kind": f"k{i % 7}"}),
            now=now - i * 0.001,  # all fresh (no pressure saturation)
        )
    v = field.compute_vector(owner_signal=0.8, now=now)
    # We expect either continue or reduce_pressure depending on saturation
    assert v.next_best_action in (
        "continue_stigmergic_action_loop",
        "reduce_pressure_and_summarize",
        "connect_more_organs",
    )


# ── persistence ──────────────────────────────────────────────────────────


def test_write_vector_persists_and_carries_vector_hash(tmp_path: Path):
    field = StigmergicField(tmp_path)
    field.append_swimmer(Swimmer(id="s1", layer=1, role="memory", payload={"kind": "k1"}), now=1000.0)
    out = field.write_vector(owner_signal=0.5, now=1001.0)
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["truth_label"] == TRUTH_LABEL
    assert "vector_hash" in data
    # vector_hash is sha256 of the rest of the dict
    body = {k: v for k, v in data.items() if k != "vector_hash"}
    assert data["vector_hash"] == sha256_json(body)


def test_read_vector_returns_none_when_not_written(tmp_path: Path):
    field = StigmergicField(tmp_path)
    assert field.read_vector() is None


def test_read_vector_returns_persisted_data(tmp_path: Path):
    field = StigmergicField(tmp_path)
    field.write_vector(owner_signal=0.5, now=1000.0)
    data = field.read_vector()
    assert data is not None
    assert data["truth_label"] == TRUTH_LABEL


# ── invariant: no hardcoded owner name ───────────────────────────────────


def test_module_has_no_owner_name_string_literal():
    """The module must accept owner_signal as a numeric parameter and
    never carry the Architect's name as a literal."""
    source = Path(
        __file__
    ).resolve().parent.parent / "swarmrl" / "stigmergic_consciousness.py"
    text = source.read_text(encoding="utf-8").lower()
    for forbidden in ("ioan", "george anton", "architect's name"):
        assert forbidden not in text, (
            f"Layer-1 violation — primitive contains literal '{forbidden}'"
        )
