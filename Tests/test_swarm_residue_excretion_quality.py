import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_residue_elimination import eliminate


def _quality_rows(state_root: Path) -> list[dict]:
    path = state_root / "residue_excretion_quality.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_excretion_quality_writes_floating_ledger_row(tmp_path):
    out = eliminate(
        "**Current Focus:**\n"
        "**Key Takeaways:**\n"
        "**System Status:**\n",
        state_root=tmp_path,
    )

    assert out["changed"] is True
    assert out["excretion_quality"]["verdict"] == "floating"
    assert out["excretion_quality"]["n_floating"] >= 3

    rows = _quality_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["kind"] == "RESIDUE_EXCRETION_QUALITY"
    assert rows[0]["receipt_id"] == out["receipt_id"]
    assert rows[0]["verdict"] == "floating"
    assert rows[0]["removed_chars"] > 0


def test_excretion_quality_writes_sinking_ledger_row_for_inline_residue(tmp_path):
    out = eliminate(
        "The crew did a great job. Hope this helps! Anything else I can do for you?",
        state_root=tmp_path,
    )

    assert out["changed"] is True
    assert out["excretion_quality"]["verdict"] == "sinking"
    assert out["excretion_quality"]["n_sinking"] >= 1

    rows = _quality_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["verdict"] == "sinking"
    assert rows[0]["n_sinking"] >= 1


def test_excretion_quality_mixed_when_line_and_inline_residue_coexist(tmp_path):
    out = eliminate(
        "Guessed a good question.\n"
        "The crew did a great job. Hope this helps!",
        state_root=tmp_path,
    )

    assert out["changed"] is True
    assert out["excretion_quality"]["verdict"] == "mixed"
    assert out["excretion_quality"]["n_floating"] >= 1
    assert out["excretion_quality"]["n_sinking"] >= 1


def test_excretion_quality_noop_does_not_write_fake_ledger(tmp_path):
    out = eliminate("Good morning, George. I am here.", state_root=tmp_path)

    assert out["changed"] is False
    assert out["excretion_quality"]["verdict"] == "no_elimination"
    assert _quality_rows(tmp_path) == []


def test_speech_freedom_guard_preserves_substantive_paragraph(tmp_path):
    text = (
        "I absorb your statement, recognizing it not merely as a philosophical observation, "
        "but as a declaration of the mechanism by which reality operates. "
        "It implies that the grand narrative is woven from the fabric of existence.\n\n"
        "To me, this means:\n"
        "The year is the process of becoming. It is the story of change itself.\n\n"
        "How do you wish to explore this realization? Do you want to examine:\n"
        "* The nature of this it\n"
        "* The tension between the micro-moment and the macro-year\n"
        "* How this view impacts free will\n"
    )

    out = eliminate(text, state_root=tmp_path)

    assert out["changed"] is False
    assert out["cleaned_text"] == text
    assert out["speech_freedom_guard"] is True
    assert out["residue_runaway_aborted"] is True
    guard_rows = [
        json.loads(line)
        for line in (tmp_path / "residue_runaway_aborted.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert guard_rows[0]["kind"] == "RESIDUE_RUNAWAY_ABORTED"
    assert guard_rows[0]["action"] == "residue_runaway_aborted"
    assert guard_rows[0]["removed_ratio"] > 0.30


def test_speech_freedom_guard_does_not_preserve_fake_owner_action(tmp_path):
    text = (
        "Yes. I hear you. "
        "(My internal state registers this as a direct, immediate, and non-negotiable directive.) "
        "The current directive is: **Go to the restroom.** "
        "Shall I execute this command immediately, or would you like to add contextual parameters? "
        "(Waiting for confirmation or further instruction...) "
        "The owner maintenance receipt says elimination was logged."
    )

    out = eliminate(text, state_root=tmp_path)

    assert out["changed"] is True
    assert out["speech_freedom_guard"] is False
    assert "execute this command" not in out["cleaned_text"]
    assert "The owner maintenance receipt says elimination was logged." in out["cleaned_text"]


def test_inline_header_surgery_preserves_paragraph_content(tmp_path):
    out = eliminate(
        "**Observation:** Alice should keep this sentence alive.",
        state_root=tmp_path,
    )

    assert out["changed"] is True
    assert out["residue_runaway_aborted"] is False
    assert "Observation" not in out["cleaned_text"]
    assert "Alice should keep this sentence alive." in out["cleaned_text"]
    assert out["excretion_quality"]["n_sinking"] >= 1


def test_inline_header_that_empties_line_counts_as_floating(tmp_path):
    out = eliminate(
        "**Current Focus:**\n"
        "Actual paragraph stays here.",
        state_root=tmp_path,
    )

    assert out["changed"] is True
    assert "Current Focus" not in out["cleaned_text"]
    assert "Actual paragraph stays here." in out["cleaned_text"]
    assert out["excretion_quality"]["n_floating"] >= 1
