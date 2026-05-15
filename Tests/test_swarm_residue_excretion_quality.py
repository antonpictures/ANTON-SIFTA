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
