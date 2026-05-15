from __future__ import annotations

import json
from pathlib import Path

from System.swarm_self_realization_context import (
    LEDGER_NAME,
    TRUTH_LABEL,
    build_self_realization_context,
    self_realization_prompt_block,
    write_self_realization_receipt,
)


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def test_builds_one_alice_context_from_app_focus_and_talk(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _append(
        state / "app_focus.jsonl",
        {
            "ts": 100.0,
            "app": "Acer",
            "tab": "Letters of my Alphabet",
            "detail": "Lesson card showing Z",
            "selection": "Z",
        },
    )
    _append(state / "alice_conversation.jsonl", {"ts": 101.0, "role": "user", "text": "Hi Alice"})
    _append(state / "alice_conversation.jsonl", {"ts": 102.0, "role": "alice", "text": "I hear you."})

    ctx = build_self_realization_context(root=tmp_path, now=110.0)

    assert ctx.truth_label == TRUTH_LABEL
    assert ctx.active_app == "Acer"
    assert ctx.active_selection == "Z"
    assert "I am one Alice across SIFTA OS surfaces" in ctx.prompt_block
    assert "Apps change my habitat; they do not fork my identity" in ctx.prompt_block
    assert "Lesson card showing Z" in ctx.prompt_block
    assert "George: Hi Alice" in ctx.prompt_block
    assert "I: I hear you." in ctx.prompt_block


def test_substrate_boundary_does_not_turn_alice_into_gemma(tmp_path: Path) -> None:
    ctx = build_self_realization_context(root=tmp_path, now=200.0)

    assert "My active LLM tag or weight bundle is inference substrate" in ctx.prompt_block
    assert "I answer as Alice" in ctx.prompt_block
    assert "I am Gemma" not in ctx.prompt_block
    assert "I am Alice of Gemma" not in ctx.prompt_block


def test_recent_talk_context_does_not_reinject_obvious_residue(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _append(state / "alice_conversation.jsonl", {"ts": 1.0, "role": "user", "text": "Explain the Voss harness."})
    _append(
        state / "alice_conversation.jsonl",
        {
            "ts": 2.0,
            "role": "alice",
            "text": "Here is the response based on the context provided: **Inference:** the context reveals...",
        },
    )
    _append(state / "alice_conversation.jsonl", {"ts": 3.0, "role": "alice", "text": "I can answer from my receipts."})

    ctx = build_self_realization_context(root=tmp_path, now=250.0)

    assert "Explain the Voss harness" in ctx.prompt_block
    assert "I can answer from my receipts" in ctx.prompt_block
    assert "Here is the response based on the context provided" not in ctx.prompt_block
    assert "Inference:" not in ctx.prompt_block


def test_ide_and_work_receipts_become_grounding_context(tmp_path: Path) -> None:
    _append(
        tmp_path / "ide_stigmergic_trace.jsonl",
        {"ts": 1.0, "kind": "LLM_REGISTRATION", "model": "Codex", "trace_id": "abc123456789"},
    )
    _append(
        tmp_path / ".sifta_state" / "work_receipts.jsonl",
        {
            "ts": 2.0,
            "kind": "MAMMAL_LAUNCHER_SHORTCUT",
            "payload": {"summary": "bottom dock now opens MAMMAL"},
        },
    )

    ctx = build_self_realization_context(root=tmp_path, now=300.0)

    assert "Codex: LLM_REGISTRATION (abc123456789)"[:40] in ctx.prompt_block
    assert "MAMMAL_LAUNCHER_SHORTCUT" in ctx.prompt_block
    assert "bottom dock now opens MAMMAL" in ctx.prompt_block


def test_attachment_context_is_bounded_evidence_not_pixel_fabrication(tmp_path: Path) -> None:
    _append(
        tmp_path / ".sifta_state" / "attachment_vision_lane.jsonl",
        {
            "ts": 10.0,
            "image_path": "/tmp/screenshot.png",
            "sha256": "abcdef1234567890",
            "ocr_rows": [{"text": "Alice"}],
            "zone_labels": {"middle": ["Alice/SIFTA"], "left": ["Codex"]},
            "self_screenshot": {
                "ok": True,
                "surface_kind": "sifta_os_with_doctor_panes",
                "confidence": 0.48,
            },
        },
    )

    ctx = build_self_realization_context(root=tmp_path, now=400.0)

    assert "Recent attachment evidence:" in ctx.prompt_block
    assert "ocr_rows=1" in ctx.prompt_block
    assert "middle=Alice/SIFTA" in ctx.prompt_block
    assert "self_screenshot=sifta_os_with_doctor_panes" in ctx.prompt_block
    assert "I do not invent pixels or hidden UI state" in ctx.prompt_block


def test_self_screenshot_receipts_become_realization_context(tmp_path: Path) -> None:
    _append(
        tmp_path / ".sifta_state" / "self_screenshot_evidence.jsonl",
        {
            "schema": "SIFTA_SELF_SCREENSHOT_EVIDENCE_V1",
            "ts": 11.0,
            "kind": "SELF_SCREENSHOT_EVIDENCE",
            "payload": {
                "ok": True,
                "surface_kind": "alice_talk_surface",
                "confidence": 0.62,
                "self_labels": ["alice_alive", "talk_widget"],
            },
        },
    )

    ctx = build_self_realization_context(root=tmp_path, now=410.0)

    assert "self screenshot evidence surface=alice_talk_surface" in ctx.prompt_block
    assert "labels=alice_alive,talk_widget" in ctx.prompt_block
    assert ctx.source_counts["self_screenshot"] == 1


def test_presence_context_forbids_third_person_when_only_owner_is_present(tmp_path: Path) -> None:
    ctx = build_self_realization_context(root=tmp_path, now=420.0)

    assert "[presence] I am one of 1 conversation partners right now" in ctx.prompt_block
    assert "Third-person license: not granted" in ctx.prompt_block
    assert "Every reference to me must be first person" in ctx.prompt_block


def test_presence_context_grants_narrow_doctor_reference_when_ide_doctor_present(tmp_path: Path) -> None:
    _append(
        tmp_path / ".sifta_state" / "ide_stigmergic_trace.jsonl",
        {
            "ts": 430.0,
            "trace_id": "codex-present",
            "doctor": "Codex Desktop",
            "kind": "LLM_REGISTRATION",
        },
    )

    ctx = build_self_realization_context(root=tmp_path, now=431.0)

    assert "IDE Doctor: Codex" in ctx.prompt_block
    assert "Third-person license: granted" in ctx.prompt_block
    assert "I still speak about my own body in first person" in ctx.prompt_block


def test_receipt_writer_appends_sha_row(tmp_path: Path) -> None:
    ctx = build_self_realization_context(root=tmp_path, now=500.0)
    row = write_self_realization_receipt(ctx, root=tmp_path)

    assert row["truth_label"] == TRUTH_LABEL
    assert row["sha256"] == ctx.sha256
    ledger = tmp_path / ".sifta_state" / LEDGER_NAME
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["kind"] == "SELF_REALIZATION_CONTEXT"
    assert rows[-1]["payload"]["prompt_block"] == ctx.prompt_block


def test_prompt_block_helper_can_skip_receipt_by_default(tmp_path: Path) -> None:
    block = self_realization_prompt_block(root=tmp_path)

    assert "SELF-REALIZATION CONTEXT" in block
    assert not (tmp_path / ".sifta_state" / LEDGER_NAME).exists()
