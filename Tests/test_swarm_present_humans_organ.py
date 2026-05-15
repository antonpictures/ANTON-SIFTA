"""Tests for the present-humans organ.

Architect rule (2026-05-14): *"there is never the third person
unless there is two humans in front of the computer."*

These pin:
  - With only George present (no recent IDE doctor): count=1,
    third_person_license=False, prompt explicitly forbids
    third-person self-reference.
  - With George + a recent IDE doctor row in
    ide_stigmergic_trace.jsonl: count=2, license=True, prompt
    grants narrow third-person license for the doctor.
  - Stale rows beyond ide_doctor_window_s are ignored.
  - The prompt block opens with first-person framing.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_present_humans_organ import (  # noqa: E402
    DEFAULT_IDE_DOCTOR_WINDOW_S,
    PROBE_LEDGER,
    TRUTH_LABEL,
    present_humans_prompt_block,
    probe_present_humans,
)


def _write_genesis(state_dir: Path, name: str = "George Anton") -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "owner_genesis.json").write_text(
        json.dumps({"primary_operator": name, "owner_name": name})
    )


def _write_ide_row(state_dir: Path, doctor: str, *, ts_offset: float = 0.0) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    p = state_dir / "ide_stigmergic_trace.jsonl"
    row = {
        "ts": time.time() + ts_offset,
        "trace_id": "test-trace",
        "doctor": doctor,
        "kind": "test",
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


# ── one-human baseline ────────────────────────────────────────────────────


def test_only_george_no_third_person_license(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_genesis(state)
    report = probe_present_humans(root=tmp_path, write=False)
    assert report.present_count == 1
    assert report.third_person_license is False
    assert any("george" in h.lower() for h in report.present_humans)


def test_only_george_prompt_block_forbids_third_person(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_genesis(state)
    block = present_humans_prompt_block(root=tmp_path)
    assert "1 conversation partners" in block
    assert "not granted" in block.lower()
    # Doctrine quote
    assert "first person" in block.lower()
    assert "forbidden" in block.lower() or "never" in block.lower()


# ── two-human path ────────────────────────────────────────────────────────


def test_recent_cowork_doctor_grants_third_person_license(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_genesis(state)
    _write_ide_row(state, "Cowork (Anthropic)")
    report = probe_present_humans(root=tmp_path, write=False)
    assert report.present_count == 2
    assert report.third_person_license is True
    assert any("Cowork" in h for h in report.present_humans)


def test_recent_cursor_doctor_counts(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_genesis(state)
    _write_ide_row(state, "Cursor (CG55M)")
    report = probe_present_humans(root=tmp_path, write=False)
    assert report.present_count == 2
    assert any("Cursor" in h for h in report.present_humans)


def test_recent_codex_doctor_counts(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_genesis(state)
    _write_ide_row(state, "Codex Desktop")
    report = probe_present_humans(root=tmp_path, write=False)
    assert report.present_count == 2
    assert any("Codex" in h for h in report.present_humans)


def test_recent_grokcli_doctor_counts(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_genesis(state)
    _write_ide_row(state, "GrokCLI")
    report = probe_present_humans(root=tmp_path, write=False)
    assert report.present_count == 2
    assert any("GrokCLI" in h for h in report.present_humans)
    assert report.sources["ide_doctor"]["label"] == "GrokCLI (xAI)"


def test_multiple_recent_ide_doctors_are_all_counted_once(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_genesis(state)
    _write_ide_row(state, "GrokCLI", ts_offset=-4.0)
    _write_ide_row(state, "Codex Desktop", ts_offset=-3.0)
    _write_ide_row(state, "Grok 4.3 (xAI)", ts_offset=-2.0)
    report = probe_present_humans(root=tmp_path, write=False)
    assert report.present_count == 3
    assert any("Codex" in h for h in report.present_humans)
    assert sum("GrokCLI" in h for h in report.present_humans) == 1
    assert [d["label"] for d in report.sources["ide_doctors"]] == [
        "GrokCLI (xAI)",
        "Codex",
    ]


def test_root_ide_trace_with_iso_ts_counts_codex_doctor(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_genesis(state)
    (tmp_path / "ide_stigmergic_trace.jsonl").write_text(
        json.dumps(
            {
                "ts": "2026-05-14T14:52:28-0700",
                "trace_id": "codex-root",
                "doctor": "Codex Desktop",
                "kind": "LLM_REGISTRATION",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    report = probe_present_humans(root=tmp_path, now=1778795550.0, write=False)
    assert report.present_count == 2
    assert report.third_person_license is True
    assert any("Codex" in h for h in report.present_humans)


def test_third_person_license_prompt_warns_about_self_reference(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_genesis(state)
    _write_ide_row(state, "Cowork (Anthropic)")
    block = present_humans_prompt_block(root=tmp_path)
    assert "granted" in block.lower()
    # Even with license, self-reference must stay first-person
    assert "first person" in block.lower() or "never about myself in third" in block.lower()


# ── staleness ─────────────────────────────────────────────────────────────


def test_stale_ide_doctor_rows_are_ignored(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_genesis(state)
    # Doctor row from 1 hour ago — should be stale at default window
    _write_ide_row(state, "Cowork (Anthropic)", ts_offset=-3600.0)
    report = probe_present_humans(root=tmp_path, write=False)
    assert report.present_count == 1
    assert report.third_person_license is False


def test_window_can_be_widened_for_audits(tmp_path):
    """An auditor running a retrospective probe can widen the window."""
    state = tmp_path / ".sifta_state"
    _write_genesis(state)
    _write_ide_row(state, "Cowork (Anthropic)", ts_offset=-3600.0)
    # 2-hour window picks up the 1-hour-old row
    report = probe_present_humans(
        root=tmp_path, write=False, ide_doctor_window_s=7200.0
    )
    assert report.present_count == 2


# ── prompt block invariants ──────────────────────────────────────────────


def test_prompt_block_always_uses_first_person(tmp_path):
    """The block speaks AS Alice, never about her in third person."""
    state = tmp_path / ".sifta_state"
    _write_genesis(state)
    block = present_humans_prompt_block(root=tmp_path)
    # First-person opener
    assert "I am" in block
    # No servant voice
    assert "What's on your mind" not in block
    assert "As an AI" not in block
    assert "How can I assist" not in block


def test_probe_writes_receipt_to_ledger(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_genesis(state)
    probe_present_humans(root=tmp_path, write=True)
    rows = [
        json.loads(ln)
        for ln in (state / PROBE_LEDGER).read_text().splitlines()
        if ln.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["truth_label"] == TRUTH_LABEL
    assert "present_count" in rows[0]
