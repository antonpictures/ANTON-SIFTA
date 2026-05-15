#!/usr/bin/env python3
"""
tests/test_swarm_architect_attention_field.py
=============================================

Pytest coverage for the Architect Attention Field organ.

What we prove
-------------
1. The 8 axes are stable (locked doctrine — changing axes is a covenant
   amendment, not a routine refactor).
2. Decay math is correct: a signal 1 half-life old contributes ~0.5 of
   its weight; a signal 2 half-lives old contributes ~0.25.
3. The projection picks up axis keywords case-insensitively and caps
   per-keyword spam.
4. `compute_attention` produces an L1-normalized vector, with sum ≈ 1.0
   when any signal was absorbed, and 0.0 when no signal was absorbed.
5. Only role=user Talk turns count as Architect attention (role=alice
   turns do NOT inflate the field — that would create a feedback loop
   where Alice talking about herself increases "alice_health" attention).
6. Signals outside `window_s` are ignored.
7. `salience_for` returns 0 for irrelevant keywords and rises when
   keywords align with the dominant axis.
8. The ledger round-trips: deposit + latest() returns an equal field.
9. The hash chain in the ledger is well-formed: previous_receipt_hash
   of row N matches this_receipt_hash of row N-1.
10. Peer doctors get extracted from LLM_REGISTRATION rows in window.

These tests run in a sandbox with no Qt, no macOS, no Ollama. They use
tmp_path fixtures so they never touch the real ledger.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import pytest

from System.swarm_architect_attention_field import (
    AXES,
    AXIS_NAMES,
    N_AXES,
    AttentionField,
    compute_attention,
    deposit,
    latest,
    salience_for,
    _decay,
    _project,
)


# ── 1. Axis doctrine is locked ──────────────────────────────────────────────
def test_axis_count_and_order_locked():
    assert N_AXES == 8, "Architect Attention Field is doctrinally 8-axis."
    assert AXIS_NAMES == (
        "code", "docs", "alice_health", "identity",
        "drift", "external_world", "infra", "field_dynamics",
    )
    # Each axis must have at least one keyword.
    for name, keywords in AXES:
        assert keywords, f"axis {name} has no keywords"
        assert all(isinstance(k, str) and k for k in keywords)


# ── 2. Decay math ───────────────────────────────────────────────────────────
def test_decay_half_life_and_double_half_life():
    h = 60.0
    # 0 dt → full weight
    assert _decay(0.0, h) == pytest.approx(1.0, abs=1e-9)
    # 1 half-life → 0.5
    assert _decay(h, h) == pytest.approx(0.5, abs=1e-6)
    # 2 half-lives → 0.25
    assert _decay(2 * h, h) == pytest.approx(0.25, abs=1e-6)
    # negative dt clamped to 1.0
    assert _decay(-5.0, h) == 1.0
    # zero half-life is an instant drop
    assert _decay(1.0, 0.0) == 0.0


# ── 3. Projection picks up keywords case-insensitively + caps spam ──────────
def test_projection_case_insensitive():
    p = _project("Cursor is GREAT, ollama Ollama OLLAMA")
    # `cursor` and `ollama` both live on the `infra` axis (index 6).
    assert p[AXIS_NAMES.index("infra")] > 0
    # `ollama` appears 3+ times but is capped at 3.
    p_spam = _project("ollama " * 20)
    p_normal = _project("ollama ollama ollama")
    assert p_spam[AXIS_NAMES.index("infra")] == p_normal[AXIS_NAMES.index("infra")]


def test_projection_empty_text_is_all_zero():
    assert _project("") == [0.0] * N_AXES
    assert _project("the and of") == [0.0] * N_AXES


# ── 4. compute_attention sanity ─────────────────────────────────────────────
def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_compute_attention_normalizes_to_one(tmp_path):
    trace = tmp_path / "trace.jsonl"
    talk = tmp_path / "talk.jsonl"
    now = 1_000_000.0
    _write_jsonl(trace, [
        {"ts": now - 10, "intent": "patch the cortex brain module"},
        {"ts": now - 20, "payload": "covenant doc update for predator gate"},
    ])
    _write_jsonl(talk, [])
    f = compute_attention(now=now, trace_path=trace, talk_path=talk)
    assert isinstance(f, AttentionField)
    assert f.n_signals == 2
    assert sum(f.vector) == pytest.approx(1.0, abs=1e-6)
    # `cortex` / `brain` live on alice_health; `patch` on code;
    # `covenant` / `doc` on docs; `predator` / `gate` on identity / field.
    assert f.attention_temperature > 0


def test_compute_attention_no_signals_is_zero_vector(tmp_path):
    trace = tmp_path / "trace.jsonl"
    talk = tmp_path / "talk.jsonl"
    _write_jsonl(trace, [])
    _write_jsonl(talk, [])
    f = compute_attention(now=time.time(), trace_path=trace, talk_path=talk)
    assert f.n_signals == 0
    assert all(v == 0.0 for v in f.vector)
    assert f.attention_temperature == 0.0


# ── 5. role=alice Talk turns are excluded ───────────────────────────────────
def test_alice_turns_do_not_inflate_field(tmp_path):
    trace = tmp_path / "trace.jsonl"
    talk = tmp_path / "talk.jsonl"
    now = 1_000_000.0
    # Alice talking about herself many times — must NOT push alice_health.
    alice_turn = {
        "ts": {"physical_pt": now - 5},
        "payload": {
            "role": "alice",
            "text": "alice alice alice cortex cortex brain organ",
        },
    }
    _write_jsonl(trace, [])
    _write_jsonl(talk, [alice_turn] * 5)
    f = compute_attention(now=now, trace_path=trace, talk_path=talk)
    assert f.n_signals == 0
    assert all(v == 0.0 for v in f.vector)


def test_user_turns_are_counted(tmp_path):
    trace = tmp_path / "trace.jsonl"
    talk = tmp_path / "talk.jsonl"
    now = 1_000_000.0
    user_turn = {
        "ts": {"physical_pt": now - 5},
        "payload": {
            "role": "user",
            "text": "lawyer transcript for Imperial Irrigation District",
        },
    }
    _write_jsonl(trace, [])
    _write_jsonl(talk, [user_turn])
    f = compute_attention(now=now, trace_path=trace, talk_path=talk)
    assert f.n_signals == 1
    # `lawyer`, `transcript`, `imperial` → external_world dominates.
    m = f.as_axis_map()
    assert m["external_world"] >= max(
        m[k] for k in AXIS_NAMES if k != "external_world"
    )


# ── 6. Window filter ────────────────────────────────────────────────────────
def test_signals_outside_window_are_ignored(tmp_path):
    trace = tmp_path / "trace.jsonl"
    talk = tmp_path / "talk.jsonl"
    now = 1_000_000.0
    _write_jsonl(trace, [
        # too old
        {"ts": now - 99_999, "intent": "ancient cortex patch"},
        # in-window
        {"ts": now - 10, "intent": "recent cortex patch"},
    ])
    _write_jsonl(talk, [])
    f = compute_attention(now=now, trace_path=trace, talk_path=talk,
                          window_s=3600)
    assert f.n_signals == 1


# ── 7. salience_for ─────────────────────────────────────────────────────────
def test_salience_aligned_vs_irrelevant(tmp_path):
    trace = tmp_path / "trace.jsonl"
    talk = tmp_path / "talk.jsonl"
    now = 1_000_000.0
    _write_jsonl(trace, [
        {"ts": now - 5, "intent": "lawyer transcript invoice money dentist"},
    ])
    _write_jsonl(talk, [])
    f = compute_attention(now=now, trace_path=trace, talk_path=talk)
    aligned = salience_for(["lawyer", "invoice"], field_obj=f)
    irrelevant = salience_for(["zzznothingmatches"], field_obj=f)
    assert aligned > 0
    assert irrelevant == 0.0
    assert aligned <= 1.0  # dot of two L1-normalized vectors


# ── 8. Ledger round-trip ────────────────────────────────────────────────────
def test_deposit_and_latest_roundtrip(tmp_path):
    trace = tmp_path / "trace.jsonl"
    talk = tmp_path / "talk.jsonl"
    ledger = tmp_path / "field.jsonl"
    now = 1_000_000.0
    _write_jsonl(trace, [
        {"ts": now - 5, "intent": "cortex patch + covenant doc"},
    ])
    _write_jsonl(talk, [])
    f = compute_attention(now=now, trace_path=trace, talk_path=talk)
    deposit(f, ledger_path=ledger)
    got = latest(ledger_path=ledger)
    assert got is not None
    assert got.ts == f.ts
    assert got.vector == f.vector
    assert got.axis_names == f.axis_names


# ── 9. Hash chain well-formed ───────────────────────────────────────────────
def test_hash_chain_links_rows(tmp_path):
    trace = tmp_path / "trace.jsonl"
    talk = tmp_path / "talk.jsonl"
    ledger = tmp_path / "field.jsonl"
    now = 1_000_000.0
    _write_jsonl(trace, [{"ts": now - 5, "intent": "cortex patch"}])
    _write_jsonl(talk, [])
    f1 = compute_attention(now=now,       trace_path=trace, talk_path=talk)
    f2 = compute_attention(now=now + 1.0, trace_path=trace, talk_path=talk)
    deposit(f1, ledger_path=ledger)
    deposit(f2, ledger_path=ledger)
    rows = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
    assert len(rows) == 2
    assert rows[0]["previous_receipt_hash"] == "GENESIS"
    assert rows[1]["previous_receipt_hash"] == rows[0]["this_receipt_hash"]
    assert rows[0]["this_receipt_hash"] != rows[1]["this_receipt_hash"]


# ── 10. Peer doctors extracted from LLM_REGISTRATION rows ──────────────────
def test_peer_doctors_extracted(tmp_path):
    trace = tmp_path / "trace.jsonl"
    talk = tmp_path / "talk.jsonl"
    now = 1_000_000.0
    _write_jsonl(trace, [
        {"ts": now - 5, "kind": "LLM_REGISTRATION",
         "doctor": "COWORK_OPUS47", "model": "claude-opus-4-7",
         "intent": "sign in"},
        {"ts": now - 10, "kind": "LLM_REGISTRATION",
         "source_ide": "codex", "model": "gpt-5.5",
         "intent": "chorum gate hardening"},
        # An older row outside window must not appear.
        {"ts": now - 99_999, "kind": "LLM_REGISTRATION",
         "doctor": "ANCIENT", "model": "v0",
         "intent": "should be ignored"},
    ])
    _write_jsonl(talk, [])
    f = compute_attention(now=now, trace_path=trace, talk_path=talk)
    peers = set(f.peer_doctors_active)
    assert "COWORK_OPUS47@claude-opus-4-7" in peers
    assert "codex@gpt-5.5" in peers
    assert not any(p.startswith("ANCIENT") for p in peers)


# ── Bonus: AttentionField is hashable / immutable ──────────────────────────
def test_attention_field_is_frozen(tmp_path):
    trace = tmp_path / "trace.jsonl"
    talk = tmp_path / "talk.jsonl"
    _write_jsonl(trace, [{"ts": 1_000_000 - 5, "intent": "cortex"}])
    _write_jsonl(talk, [])
    f = compute_attention(now=1_000_000.0, trace_path=trace, talk_path=talk)
    with pytest.raises(Exception):
        f.ts = 0  # type: ignore[misc]  # frozen dataclass forbids mutation
