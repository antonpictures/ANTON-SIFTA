"""r683: Alice's own / palette — list, switch, diary awareness. Qt-free."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System import swarm_alice_slash_commands as slash


TAGS = ["alice-m5-cortex-8b", "heretic", "gemini-2.5-pro", "cline"]


def _run(text: str, tmp_path: Path, *, current: str = "alice-m5-cortex-8b", hand=None):
    calls: list[str] = []

    def _default_hand(tag: str) -> None:
        calls.append(tag)

    res = slash.handle_slash_command(
        text,
        state_dir=tmp_path,
        current_cortex=current,
        available=list(TAGS),
        set_cortex_fn=hand if hand is not None else _default_hand,
    )
    return res, calls


def _diary_rows(tmp_path: Path) -> list[dict]:
    p = tmp_path / "episodic_diary.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def test_slash_detection_and_escape():
    assert slash.is_slash_command("/cortex")
    assert slash.is_slash_command("  /help")
    assert not slash.is_slash_command("//literal slash text")
    assert not slash.is_slash_command("https://youtube.com")
    assert not slash.is_slash_command("plain prose with / inside")
    assert not slash.is_slash_command("")


def test_help_lists_her_own_commands(tmp_path):
    res, calls = _run("/help", tmp_path)
    assert res["handled"] and not res["error"]
    assert "/cortex" in res["reply"] and "diary" in res["reply"]
    assert calls == [] and _diary_rows(tmp_path) == []


def test_cortex_list_marks_current_and_numbers(tmp_path):
    res, calls = _run("/cortex", tmp_path)
    assert res["handled"] and not res["error"]
    assert "● " in res["reply"] and " 1." in res["reply"] and "heretic" in res["reply"]
    assert "live registry" in res["reply"]
    assert calls == [] and _diary_rows(tmp_path) == []


def test_cortex_switch_by_number_writes_diary_first_person(tmp_path):
    res, calls = _run("/cortex 2", tmp_path)
    assert res["switched"] and res["to_tag"] == "heretic" and calls == ["heretic"]
    rows = _diary_rows(tmp_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "CORTEX_SWITCH_CONTINUITY"
    assert row["phase"] == "slash_command_switch"
    assert row["from_cortex"] == "alice-m5-cortex-8b" and row["to_cortex"] == "heretic"
    assert "next thinking turn" in row["note"] and "I am on heretic" in row["note"]


def test_cortex_switch_by_name_resolves(tmp_path):
    res, calls = _run("/cortex heretic", tmp_path)
    assert res["switched"] and calls == ["heretic"]


def test_same_cortex_is_a_noop_with_no_diary_row(tmp_path):
    res, calls = _run("/cortex 1", tmp_path)
    assert not res["switched"] and calls == []
    assert "already on" in res["reply"]
    assert _diary_rows(tmp_path) == []


def test_bad_number_and_garbage_fail_honestly(tmp_path):
    res, _ = _run("/cortex 99", tmp_path)
    assert res["error"] == "index_out_of_range" and not res["switched"]
    res, _ = _run("/cortex zzqxv", tmp_path)
    assert res["error"] == "unresolved_target" and not res["switched"]
    assert _diary_rows(tmp_path) == []


def test_switch_hand_failure_is_reported_not_hidden(tmp_path):
    def _broken(tag: str) -> None:
        raise RuntimeError("stores locked")

    res, _ = _run("/cortex 3", tmp_path, hand=_broken)
    assert not res["switched"]
    assert "switch_failed" in res["error"] and "stores locked" in res["reply"]
    # diary row was written before the hand failed — the trace tells the truth
    assert len(_diary_rows(tmp_path)) == 1


def test_unknown_command_returns_her_list(tmp_path):
    res, _ = _run("/teleport mars", tmp_path)
    assert res["error"] == "unknown_command" and "/cortex" in res["reply"]
