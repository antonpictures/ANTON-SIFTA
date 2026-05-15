"""Tests for swarm_organ_tokenizer.

Architect 2026-05-13 said: 'we are the borg you will be assimilated'
after dropping a figure of the biomed.omics multi-align paper. This
module is the SIFTA-side assimilation: organ receipts → typed-token
stream. Tests guard:

  - Each token-type constant exists and is in TOKEN_TYPES
  - Known ledger filenames map to canonical organ names
  - Unknown ledgers get a sensible fallback (filename stem, upper)
  - time_bucket is stable, monotone older→bigger
  - row_to_tokens produces ORGAN_TYPE + TIME_TAG first
  - SCALAR_ATTR for numbers, TOKEN_ATTR for categorical keys,
    GENERAL_TOKEN for long strings
  - Nested dicts are flattened one level
  - Receipt is sha256-signed; payload round-trips
"""
import hashlib
import json
from pathlib import Path

import pytest

from System.swarm_organ_tokenizer import (
    ATTACHMENT_VISUAL_TOKEN_LEDGER_NAME,
    ATTACHMENT_VISUAL_TRUTH_LABEL,
    DEFAULT_LEDGERS,
    LEDGER_TO_ORGAN,
    OrganToken,
    TT_GENERAL,
    TT_ORGAN,
    TT_SCALAR,
    TT_TIME,
    TT_TOKEN,
    TOKEN_TYPES,
    TRUTH_LABEL,
    VISUAL_ATTACH_ORGAN,
    attachment_visual_mass,
    attachment_visual_surprise,
    organ_for_ledger,
    row_to_tokens,
    run_organ_tokenizer,
    summarize_tokens,
    time_bucket,
    tokenize_ledger,
    tokenize_recent,
    write_attachment_visual_token_receipt,
    write_tokenizer_receipt,
)


# ── Token-type taxonomy ─────────────────────────────────────────────

def test_token_type_constants_in_taxonomy():
    for tt in (TT_ORGAN, TT_SCALAR, TT_TOKEN, TT_GENERAL, TT_TIME):
        assert tt in TOKEN_TYPES
    assert len(TOKEN_TYPES) == 5


def test_known_ledger_maps_to_canonical_organ():
    assert organ_for_ledger("attachment_dynamics_receipts.jsonl") == "ATTACHMENT"
    assert organ_for_ledger("alice_first_person_journal.jsonl") == "JOURNAL"
    assert organ_for_ledger("ide_stigmergic_trace.jsonl") == "IDE_TRACE"
    assert organ_for_ledger("higgs_stigmergic_demo_path_receipts.jsonl") == "DEMO_PATH"
    # With full path
    assert organ_for_ledger("/foo/bar/work_receipts.jsonl") == "WORK"


def test_unknown_ledger_falls_back_to_uppercase_stem():
    assert organ_for_ledger("custom_organ.jsonl") == "CUSTOM_ORGAN"
    assert organ_for_ledger("some.weird-name.jsonl") == "SOME_WEIRD_NAME"


# ── Time bucket ────────────────────────────────────────────────────

def test_time_bucket_returns_expected_strings():
    now = 1_000_000_000.0
    assert time_bucket(now - 10, now=now) == "T-1m"
    assert time_bucket(now - 120, now=now) == "T-5m"
    assert time_bucket(now - 1000, now=now) == "T-1h"
    assert time_bucket(now - 10000, now=now) == "T-6h"
    assert time_bucket(now - 70000, now=now) == "T-1d"
    assert time_bucket(now - 200000, now=now) == "T-1w"
    assert time_bucket(now - 10_000_000, now=now) == "T-OLD"


def test_time_bucket_monotone_older_means_bigger_bucket():
    """The bucket label position in this list IS the age order."""
    order = ["T-1m", "T-5m", "T-1h", "T-6h", "T-1d", "T-1w", "T-OLD"]
    now = 1_000_000_000.0
    # Sample ages each definitely inside their bucket
    ages = [10, 120, 1000, 10000, 70000, 200000, 10_000_000]
    buckets = [time_bucket(now - a, now=now) for a in ages]
    assert buckets == order


# ── row_to_tokens ──────────────────────────────────────────────────

def test_row_to_tokens_starts_with_organ_then_time():
    row = {"ts": 1_000_000_000.0, "kind": "X", "value": 0.5}
    tokens = row_to_tokens(row, "TEST_ORGAN", now=1_000_000_010.0)
    assert tokens[0].type == TT_ORGAN
    assert tokens[0].value == "TEST_ORGAN"
    assert tokens[1].type == TT_TIME
    assert tokens[1].value == "T-1m"


def test_row_to_tokens_classifies_numbers_as_scalar():
    row = {"ts": 1.0, "work_value": 0.42, "count": 7}
    tokens = row_to_tokens(row, "WORK")
    scalar_fields = {t.field for t in tokens if t.type == TT_SCALAR}
    assert "work_value" in scalar_fields
    assert "count" in scalar_fields
    # ts also gets a SCALAR_ATTR copy
    assert "ts" in scalar_fields


def test_row_to_tokens_classifies_known_categorical_keys_as_token_attr():
    row = {
        "ts": 1.0,
        "kind": "DECISION",
        "truth_label": "ATTACHMENT_DYNAMICS_V2",
        "decision": "FIRE",
    }
    tokens = row_to_tokens(row, "TEST")
    token_attr_fields = {t.field for t in tokens if t.type == TT_TOKEN}
    assert "kind" in token_attr_fields
    assert "truth_label" in token_attr_fields
    assert "decision" in token_attr_fields


def test_row_to_tokens_classifies_long_strings_as_general_token():
    long_text = "Here is a much longer line of text that should chunk."
    row = {"ts": 1.0, "line": long_text}
    tokens = row_to_tokens(row, "JOURNAL")
    general = [t for t in tokens if t.type == TT_GENERAL]
    assert len(general) >= 1
    assert all(t.field == "line" for t in general)


def test_row_to_tokens_flattens_nested_dicts_one_level():
    row = {
        "ts": 1.0,
        "payload": {"mechanism": "momentum_share", "ratio": 0.473},
    }
    tokens = row_to_tokens(row, "ATTACHMENT")
    fields = {t.field for t in tokens}
    # Nested keys are flattened with dot notation
    assert "payload.mechanism" in fields
    assert "payload.ratio" in fields


def test_row_to_tokens_skips_pure_bookkeeping_keys():
    row = {
        "ts": 1.0, "sha256": "deadbeef" * 8, "trace_id": "uuid-here",
        "homeworld_serial": "GTH4921YP3", "kind": "X",
    }
    tokens = row_to_tokens(row, "TEST")
    fields = {t.field for t in tokens}
    # These bookkeeping keys must not produce tokens
    assert "sha256" not in fields
    assert "trace_id" not in fields
    assert "homeworld_serial" not in fields
    # But kind (a normal categorical) survives
    assert "kind" in fields


def test_row_to_tokens_handles_non_dict_input():
    # Defensive: tokenizer must not crash on malformed rows
    assert row_to_tokens("not a dict", "TEST") == []
    assert row_to_tokens(None, "TEST") == []
    assert row_to_tokens(42, "TEST") == []


def test_row_to_tokens_handles_non_numeric_ts():
    """Some ledgers have non-numeric ts fields — must not crash."""
    row = {"ts": {"nested": "value"}, "kind": "X"}
    tokens = row_to_tokens(row, "TEST")
    # Just doesn't crash; ts falls back to 0.
    assert tokens[0].ts == 0.0


def _visual_attachment_row() -> dict:
    return {
        "schema": "SIFTA_ATTACHMENT_VISION_LANE_RECEIPT_V1",
        "ts": 123.0,
        "trace_id": "source-trace",
        "truth_label": "ATTACHMENT_VISION_LANE_V1",
        "ok": True,
        "image_path": "/tmp/screen.png",
        "image_format": "png",
        "width": 1200,
        "height": 800,
        "byte_count": 650_000,
        "sha256": "abcdef1234567890",
        "zone_labels": {
            "left": ["Codex"],
            "middle": ["Alice/SIFTA"],
            "right": ["Claude/Cowork"],
        },
        "ocr_rows": [
            {"text": "Dr. Codex IDE", "x": 0.05, "w": 0.10, "confidence": 0.92},
            {"text": "SIFTA Alice chat", "x": 0.45, "w": 0.10, "confidence": 0.91},
            {"text": "Dr. Claude IDE", "x": 0.78, "w": 0.10, "confidence": 0.90},
        ],
    }


def test_visual_attachment_row_emits_clean_visual_tokens():
    row = _visual_attachment_row()
    tokens = row_to_tokens(row, VISUAL_ATTACH_ORGAN, now=130.0)
    fields = {t.field for t in tokens}
    zone_values = {(t.field, t.value) for t in tokens if t.type == TT_TOKEN}
    scalar_by_field = {t.field: t.value for t in tokens if t.type == TT_SCALAR}

    assert tokens[0].type == TT_ORGAN
    assert tokens[0].value == VISUAL_ATTACH_ORGAN
    assert "ocr_rows_count" in fields
    assert "ocr_chars" in fields
    assert "zone_count" in fields
    assert "visual_mass" in fields
    assert "visual_surprise" in fields
    assert ("zone_labels.left", "Codex") in zone_values
    assert ("zone_labels.middle", "Alice/SIFTA") in zone_values
    assert ("zone_labels.right", "Claude/Cowork") in zone_values
    assert ("ocr_rows[0].zone", "left") in zone_values
    assert ("ocr_rows[2].zone", "right") in zone_values
    assert any(t.type == TT_GENERAL and t.field == "ocr_rows[1].text" for t in tokens)
    assert scalar_by_field["visual_mass"] > 0.0
    assert scalar_by_field["visual_surprise"] >= scalar_by_field["visual_mass"] * 0.5


def test_attachment_visual_mass_and_surprise_are_bounded():
    row = _visual_attachment_row()
    mass = attachment_visual_mass(row)
    surprise = attachment_visual_surprise(row)
    assert 0.0 < mass <= 1.0
    assert 0.0 < surprise <= 1.0
    assert attachment_visual_mass({"ok": False}) == 0.0


def test_write_attachment_visual_token_receipt_round_trips(tmp_path):
    state = tmp_path / "state"
    row = _visual_attachment_row()
    receipt = write_attachment_visual_token_receipt(row, state_root=state, now=200.0)

    ledger = state / ATTACHMENT_VISUAL_TOKEN_LEDGER_NAME
    parsed = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert parsed["trace_id"] == receipt["trace_id"]
    assert parsed["truth_label"] == ATTACHMENT_VISUAL_TRUTH_LABEL
    assert parsed["payload"]["source_trace_id"] == "source-trace"
    assert parsed["payload"]["token_count"] > 0
    assert parsed["payload"]["visual_mass"] > 0.0


# ── Ledger-level tokenization ──────────────────────────────────────

def test_tokenize_ledger_reads_last_n_only(tmp_path):
    ledger = tmp_path / "work_receipts.jsonl"
    lines = [
        json.dumps({"ts": float(i), "work_type": f"T{i}"})
        for i in range(20)
    ]
    ledger.write_text("\n".join(lines) + "\n")
    tokens = tokenize_ledger(ledger, last_n=5)
    # 5 receipts × (ORGAN + TIME + ts + work_type) = 20 tokens
    assert any(t.type == TT_ORGAN and t.organ == "WORK" for t in tokens)
    # Get the ts values that came through
    ts_seen = sorted({t.ts for t in tokens if t.ts > 0})
    # Only the last 5 receipts (ts=15..19) should appear
    assert ts_seen == [15.0, 16.0, 17.0, 18.0, 19.0]


def test_tokenize_ledger_handles_missing_file(tmp_path):
    assert tokenize_ledger(tmp_path / "nope.jsonl") == []


def test_tokenize_ledger_handles_empty_file(tmp_path):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    assert tokenize_ledger(empty) == []


def test_tokenize_ledger_skips_malformed_lines(tmp_path):
    ledger = tmp_path / "x.jsonl"
    ledger.write_text(
        '{"ts": 1.0, "kind": "A"}\n'
        'not valid json\n'
        '{"ts": 2.0, "kind": "B"}\n'
    )
    tokens = tokenize_ledger(ledger, last_n=10)
    # 2 valid receipts × 2+ tokens, no crash on the bad middle line
    organs = [t for t in tokens if t.type == TT_ORGAN]
    assert len(organs) == 2


# ── tokenize_recent — the full unified stream ─────────────────────

def test_tokenize_recent_stitches_multiple_organs(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "attachment_dynamics_receipts.jsonl").write_text(
        json.dumps({"ts": 100.0, "kind": "ATTACHMENT_DYNAMICS_EXPERIMENT"}) + "\n"
    )
    (state / "ide_stigmergic_trace.jsonl").write_text(
        json.dumps({"ts": 200.0, "kind": "LLM_REGISTRATION"}) + "\n"
    )
    tokens = tokenize_recent(
        state_root=state,
        ledgers=["attachment_dynamics_receipts.jsonl", "ide_stigmergic_trace.jsonl"],
        last_n_per_ledger=5,
    )
    organs_seen = {t.organ for t in tokens}
    assert "ATTACHMENT" in organs_seen
    assert "IDE_TRACE" in organs_seen
    # Stream is sorted chronologically — ATTACHMENT (ts=100) before IDE_TRACE (ts=200)
    ts_seq = [t.ts for t in tokens if t.ts > 0]
    assert ts_seq == sorted(ts_seq)


# ── summarize + receipt ────────────────────────────────────────────

def test_summarize_tokens_counts_by_type_and_organ():
    toks = [
        OrganToken(type=TT_ORGAN, organ="A", value="A", ts=1.0, field="_organ"),
        OrganToken(type=TT_TIME, organ="A", value="T-1m", ts=1.0, field="_time"),
        OrganToken(type=TT_SCALAR, organ="B", value=2.5, ts=1.0, field="x"),
    ]
    s = summarize_tokens(toks)
    assert s["n_tokens"] == 3
    assert s["tokens_by_type"][TT_ORGAN] == 1
    assert s["tokens_by_type"][TT_SCALAR] == 1
    assert s["n_organs_seen"] == 2


def test_run_organ_tokenizer_returns_truth_label_and_summary(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "work_receipts.jsonl").write_text(
        json.dumps({"ts": 1.0, "work_type": "T", "work_value": 0.5}) + "\n"
    )
    r = run_organ_tokenizer(
        state_root=state, ledgers=["work_receipts.jsonl"], write=False,
    )
    assert r["truth_label"] == TRUTH_LABEL
    assert r["n_tokens"] > 0
    assert "tokens_by_type" in r
    assert "tokens_by_organ" in r
    assert "preview_first_24_tokens" in r


def test_write_tokenizer_receipt_is_sha256_signed(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "work_receipts.jsonl").write_text(
        json.dumps({"ts": 1.0, "work_type": "T"}) + "\n"
    )
    r = run_organ_tokenizer(
        state_root=state, ledgers=["work_receipts.jsonl"], write=False,
    )
    row = write_tokenizer_receipt(r, state_root=state)
    expected = hashlib.sha256(
        json.dumps(r, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert row["sha256"] == expected
    # Roundtrip from disk
    ledger = state / "organ_tokenizer_receipts.jsonl"
    line = ledger.read_text().strip().splitlines()[-1]
    parsed = json.loads(line)
    assert parsed["truth_label"] == TRUTH_LABEL
    assert parsed["kind"] == "MULTI_ALIGN_ORGAN_TOKENIZER"


def test_default_ledger_list_is_nonempty():
    """Guard against accidental empty default ledger list."""
    assert len(DEFAULT_LEDGERS) >= 8
    # All default ledgers must have a canonical organ mapping
    for name in DEFAULT_LEDGERS:
        assert name in LEDGER_TO_ORGAN, (
            f"default ledger {name} missing from LEDGER_TO_ORGAN — "
            f"would tokenize as filename stem instead of canonical organ"
        )
