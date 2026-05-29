#!/usr/bin/env python3
"""Round 56 — pure view-model tests.

Swarm consensus from §ROUND 55 / 55.1 / 55.GROK / 58:
  - dedupe_key + message_id + collapse_default + receipts-as-metadata
  - receipt-driven duplicate suppression (adjacent same-key rows collapse)
  - speaker normalization (owner/alice/system/arm:*)
  - silence rows and FIELD_FAILURE rows classified distinctly
  - real ledger isolation (delta=0 across .sifta_state/*)

No Qt imports. Pure stdlib + pytest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import swarm_global_chat_view_model as vm


def _write_conversation(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _wrapped(event_id: str, payload: dict) -> dict:
    """Build a production-shape wrapped row."""
    return {
        "event_id": event_id,
        "ts": {"physical_pt": float(payload.get("ts", 0.0)), "logical": 0,
               "agent_id": "ALICE_M5"},
        "payload": payload,
        "prev_hash": "x",
        "this_hash": "y",
    }


# ─── Empty / malformed ─────────────────────────────────────────────────────


def test_returns_empty_list_when_state_dir_missing(tmp_path):
    assert vm.load_recent_view(tmp_path / "nowhere") == []


def test_returns_empty_when_file_empty(tmp_path):
    (tmp_path / "alice_conversation.jsonl").write_text("", encoding="utf-8")
    assert vm.load_recent_view(tmp_path) == []


def test_skips_malformed_rows(tmp_path):
    p = tmp_path / "alice_conversation.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as fh:
        fh.write("not json\n")
        fh.write(json.dumps(_wrapped("a1", {"ts": 1.0, "role": "user", "text": "hi"})) + "\n")
        fh.write("{still not json\n")
        fh.write(json.dumps(_wrapped("a2", {"ts": 2.0, "role": "alice", "text": "hello"})) + "\n")
    rows = vm.load_recent_view(tmp_path)
    assert len(rows) == 2
    assert rows[0].full_text == "hi"
    assert rows[1].full_text == "hello"


# ─── Wrapped + legacy shapes ───────────────────────────────────────────────


def test_unwraps_production_wrapped_rows(tmp_path):
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 100.0, "role": "user", "text": "hello alice"}),
        _wrapped("e2", {"ts": 101.0, "role": "alice", "text": "hello George"}),
    ])
    rows = vm.load_recent_view(tmp_path)
    assert len(rows) == 2
    assert rows[0].message_id == "msg_e1"
    assert rows[0].speaker == "owner"
    assert rows[0].kind == "owner_turn"
    assert rows[1].speaker == "alice"
    assert rows[1].kind == "alice_turn"


def test_accepts_flat_legacy_rows(tmp_path):
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        {"ts": 1.0, "role": "user", "text": "legacy ping"},
        {"ts": 2.0, "role": "alice", "text": "legacy pong"},
    ])
    rows = vm.load_recent_view(tmp_path)
    assert len(rows) == 2
    assert rows[0].full_text == "legacy ping"
    # message_id falls back to a hash-based form when no event_id present
    assert rows[0].message_id.startswith("msg_")
    assert len(rows[0].message_id) == len("msg_") + 12


# ─── Speaker normalization ─────────────────────────────────────────────────


@pytest.mark.parametrize("role,expected", [
    ("user", "owner"),
    ("owner", "owner"),
    ("George", "owner"),
    ("ioan", "owner"),
    ("architect", "owner"),
    ("alice", "alice"),
    ("assistant", "alice"),
    ("system", "system"),
])
def test_speaker_normalization(tmp_path, role, expected):
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 1.0, "role": role, "text": "x"}),
    ])
    rows = vm.load_recent_view(tmp_path)
    assert len(rows) == 1
    assert rows[0].speaker == expected


def test_arm_speaker_when_arm_id_present(tmp_path):
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 1.0, "role": "arm", "arm_id": "codex_agent",
                        "text": "codex output"}),
    ])
    rows = vm.load_recent_view(tmp_path)
    assert rows[0].speaker == "arm:codex_agent"
    assert rows[0].kind == "arm_output"


# ─── Silence + FIELD_FAILURE classification ────────────────────────────────


def test_silence_row_kind_and_severity(tmp_path):
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 1.0, "role": "user", "text": "hi"}),
        _wrapped("e2", {"ts": 2.0, "role": "alice",
                        "text": "(silent: repetition collapse)"}),
    ])
    rows = vm.load_recent_view(tmp_path)
    assert rows[1].kind == "silence"
    assert rows[1].severity == "warn"


def test_field_failure_row_kind_and_severity(tmp_path):
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 1.0, "role": "alice",
                        "text": "FIELD_FAILURE: missing plan anchor X"}),
    ])
    rows = vm.load_recent_view(tmp_path)
    assert rows[0].kind == "field_failure"
    assert rows[0].severity == "error"


# ─── Modality classification ───────────────────────────────────────────────


def test_modality_explicit_typed(tmp_path):
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 1.0, "role": "user", "text": "x",
                        "modality": "TYPED"}),
    ])
    assert vm.load_recent_view(tmp_path)[0].modality == "typed"


def test_modality_source_voice(tmp_path):
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 1.0, "role": "user", "text": "x",
                        "source": "voice", "stt_conf": 0.95}),
    ])
    assert vm.load_recent_view(tmp_path)[0].modality == "spoken"


def test_modality_unknown_default(tmp_path):
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 1.0, "role": "alice", "text": "hi"}),
    ])
    # Alice replies have no modality marker — that's expected; renderer
    # treats alice messages without modality as "spoken-or-typed neutral".
    assert vm.load_recent_view(tmp_path)[0].modality == "unknown"


# ─── Collapse default ──────────────────────────────────────────────────────


def test_collapse_default_false_for_short_text(tmp_path):
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 1.0, "role": "user", "text": "short hi"}),
    ])
    assert vm.load_recent_view(tmp_path)[0].collapse_default is False


def test_collapse_default_true_for_many_lines(tmp_path):
    body = "\n".join(f"line {i}" for i in range(20))
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 1.0, "role": "user", "text": body}),
    ])
    row = vm.load_recent_view(tmp_path)[0]
    assert row.collapse_default is True
    assert row.text_lines == 20


def test_collapse_default_true_for_long_single_line(tmp_path):
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 1.0, "role": "user", "text": "x" * 1000}),
    ])
    assert vm.load_recent_view(tmp_path)[0].collapse_default is True


def test_collapse_text_after_four_paragraphs_keeps_first_four_visible():
    body = "\n\n".join(f"paragraph {i}" for i in range(1, 7))
    preview = vm.collapse_text_after_paragraphs(body)

    assert preview.is_collapsed is True
    assert preview.visible_text == "\n\n".join(f"paragraph {i}" for i in range(1, 5))
    assert preview.hidden_text == "paragraph 5\n\nparagraph 6"
    assert preview.hidden_paragraph_count == 2


def test_collapse_text_after_paragraphs_leaves_short_answer_full():
    body = "one\n\ntwo\n\nthree\n\nfour"
    preview = vm.collapse_text_after_paragraphs(body)

    assert preview.is_collapsed is False
    assert preview.visible_text == body
    assert preview.hidden_text == ""
    assert preview.hidden_paragraph_count == 0


# ─── Dedupe ────────────────────────────────────────────────────────────────


def test_consecutive_duplicate_rows_collapse(tmp_path):
    """Streaming partial then final: same text, same speaker, same ts bucket
    → collapse to one (the LATER row wins)."""
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 1.0, "role": "alice", "text": "Online."}),
        _wrapped("e2", {"ts": 1.0, "role": "alice", "text": "Online."}),
    ])
    rows = vm.load_recent_view(tmp_path)
    assert len(rows) == 1
    assert rows[0].message_id == "msg_e2"   # later row wins


def test_non_adjacent_same_text_NOT_deduped(tmp_path):
    """Same text from a later turn is honest re-occurrence, not a dupe."""
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 1.0, "role": "alice", "text": "Online."}),
        _wrapped("e2", {"ts": 2.0, "role": "user", "text": "are you there?"}),
        _wrapped("e3", {"ts": 3.0, "role": "alice", "text": "Online."}),
    ])
    rows = vm.load_recent_view(tmp_path)
    assert len(rows) == 3


def test_dedupe_window_buckets(tmp_path):
    """Two identical rows within the window collapse; outside the window do not."""
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 1.0, "role": "alice", "text": "tick"}),
        _wrapped("e2", {"ts": 1.5, "role": "alice", "text": "tick"}),
        _wrapped("e3", {"ts": 10.0, "role": "alice", "text": "tick"}),
    ])
    rows = vm.load_recent_view(tmp_path, dedupe_window_s=2.0)
    # First two are in the same 2.0s bucket → collapse to one
    # Third is far away → separate row
    assert len(rows) == 2
    assert rows[0].full_text == "tick"
    assert rows[1].full_text == "tick"
    assert rows[1].ts == 10.0


# ─── Receipt refs ──────────────────────────────────────────────────────────


def test_extract_receipt_refs_round_style():
    text = "Receipt r58-src-e04da72a3c written. Also r57-bac2d20e29b0."
    refs = vm.extract_receipt_refs(text)
    assert "r58-src-e04da72a3c" in refs
    assert "r57-bac2d20e29b0" in refs


def test_extract_receipt_refs_uuid():
    text = "trace_id=feec7d58-8abb-4a78-ad2e-02255bb28746"
    refs = vm.extract_receipt_refs(text)
    assert "feec7d58-8abb-4a78-ad2e-02255bb28746" in refs


def test_extract_receipt_refs_cortex_pre_exec():
    text = "cortex_pre_exec_89e9b428f7ef4001"
    refs = vm.extract_receipt_refs(text)
    assert "cortex_pre_exec_89e9b428f7ef4001" in refs


def test_extract_receipt_refs_empty_on_normal_text():
    assert vm.extract_receipt_refs("hello there") == ()
    assert vm.extract_receipt_refs("") == ()


def test_receipt_refs_surface_on_chat_row(tmp_path):
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 1.0, "role": "alice",
                        "text": "Round 47 closed. Receipt r47-aabbcc112233 landed."}),
    ])
    row = vm.load_recent_view(tmp_path)[0]
    assert "r47-aabbcc112233" in row.receipt_refs


# ─── Preview ──────────────────────────────────────────────────────────────


def test_preview_truncates_long_text(tmp_path):
    body = "A " * 300  # ~600 chars
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 1.0, "role": "user", "text": body}),
    ])
    row = vm.load_recent_view(tmp_path)[0]
    assert len(row.text_preview) <= vm.PREVIEW_CHAR_LIMIT
    assert row.text_preview.endswith("…")
    # full body preserved (no truncation of full_text); .strip() is applied at ingest
    assert row.full_text == body.strip()
    assert len(row.full_text) > vm.PREVIEW_CHAR_LIMIT


def test_preview_flattens_newlines(tmp_path):
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped("e1", {"ts": 1.0, "role": "user",
                        "text": "first line\nsecond line\nthird line"}),
    ])
    row = vm.load_recent_view(tmp_path)[0]
    assert "\n" not in row.text_preview


# ─── max_n cap ─────────────────────────────────────────────────────────────


def test_max_n_caps_to_newest(tmp_path):
    _write_conversation(tmp_path / "alice_conversation.jsonl", [
        _wrapped(f"e{i}", {"ts": float(i), "role": "user", "text": f"msg {i}"})
        for i in range(20)
    ])
    rows = vm.load_recent_view(tmp_path, max_n=5)
    assert len(rows) == 5
    # newest at the bottom
    assert rows[-1].full_text == "msg 19"
    assert rows[0].full_text == "msg 15"


# ─── Real ledger isolation ─────────────────────────────────────────────────


def test_real_ledgers_untouched(tmp_path):
    """Hard invariant: view-model is READ-ONLY against every ledger it reads."""
    state = Path(".sifta_state")
    watch = [
        state / "alice_conversation.jsonl",
        state / "work_receipts.jsonl",
        state / "agent_arm_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
    ]
    before = {str(p): (p.stat().st_size if p.exists() else 0) for p in watch}

    _ = vm.load_recent_view(state)
    _ = vm.load_recent_view(state, max_n=10)
    _ = vm.classify_modality({"modality": "TYPED"})
    _ = vm.extract_receipt_refs("test r1-aabbcc test")
    _ = vm.dedupe_key_for("owner", 1.0, "hi")
    _ = vm.message_id_for("ev", 1.0, "hi")

    after = {str(p): (p.stat().st_size if p.exists() else 0) for p in watch}
    for k in before:
        assert before[k] == after[k], (
            f"view-model mutated {k}: {before[k]} -> {after[k]}"
        )
