from __future__ import annotations

import json
from pathlib import Path

from System import swarm_native_app_teaching as native


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_seed_chess_app_skill_writes_playbook_and_work_receipt(tmp_path: Path) -> None:
    row = native.seed_chess_app_skill(now=100.0, state_dir=tmp_path)

    assert row["app"] == "Chess.app"
    assert row["skill"] == "play_game"
    assert row["owner_confirmed"] is True
    assert "verify" in " ".join(row["how_to"]).lower()

    playbook = tmp_path / ".sifta_state" / native.PLAYBOOK_NAME
    data = json.loads(playbook.read_text(encoding="utf-8"))
    assert data["truth_label"] == native.TRUTH_LABEL
    assert "Chess.app" in data["apps"]
    assert "play_game" in data["apps"]["Chess.app"]["skills"]

    receipts = _rows(tmp_path / ".sifta_state" / native.RECEIPTS_LEDGER)
    work = _rows(tmp_path / ".sifta_state" / "work_receipts.jsonl")
    assert receipts[-1]["kind"] == "native_app_skill_recorded"
    assert work[-1]["receipt_id"] == receipts[-1]["receipt_id"]


def test_plan_native_app_action_infers_chess_from_owner_text(tmp_path: Path) -> None:
    native.seed_chess_app_skill(now=101.0, state_dir=tmp_path)

    plan = native.plan_native_app_action(
        "Alice play a game in Chess.app",
        state_dir=tmp_path,
    )

    assert plan["ok"] is True
    assert plan["app"] == "Chess.app"
    assert plan["skill"] == "play_game"
    assert plan["observe_first"] is True
    assert plan["verify_after_act"] is True
    assert native.EPISODES_LEDGER in plan["receipt_ledgers"]


def test_record_native_app_episode_is_latest_and_teaching_pair(tmp_path: Path) -> None:
    episode = native.record_native_app_episode(
        app="Chess",
        skill="play game",
        owner_text="Play Chess.app",
        observed_state={"window": "Game 1", "side_to_move": "white"},
        action_steps=[
            {"kind": "click_square", "square": "e2"},
            {"kind": "click_square", "square": "e4"},
        ],
        outcome_state={"white_pawn": "e4", "black_reply": "e6"},
        ok=True,
        note="e4 worked and black answered e6",
        now=200.0,
        state_dir=tmp_path,
    )

    latest = native.latest_native_app_episode(now=205.0, state_dir=tmp_path)
    assert latest["receipt_id"] == episode["receipt_id"]
    assert latest["age_s"] == 5.0

    pairs = native.native_app_teaching_pairs(state_dir=tmp_path)
    assert pairs
    assert "Chess.app/play_game" in pairs[0]["completion"]
    assert episode["receipt_id"] in pairs[0]["completion"]


def test_native_app_skill_block_surfaces_chess_lesson(tmp_path: Path) -> None:
    native.seed_chess_app_skill(now=300.0, state_dir=tmp_path)

    block = native.native_app_skill_block(
        owner_text="can Alice use Chess.app?",
        state_dir=tmp_path,
    )

    assert "NATIVE MAC APP BODY SKILL" in block
    assert "Chess.app / play_game" in block
    assert "observe" in block.lower()
    assert "verify" in block.lower()
    assert "System/swarm_hands.py" in block


def test_write_teaching_jsonl_outputs_successful_episode_pairs(tmp_path: Path) -> None:
    native.record_native_app_episode(
        app="Chess.app",
        skill="play_game",
        owner_text="Play chess",
        ok=True,
        now=400.0,
        state_dir=tmp_path,
    )

    out = native.write_teaching_jsonl(tmp_path / "native_pairs.jsonl", state_dir=tmp_path)

    assert out["ok"] is True
    assert out["pairs"] == 1
    assert "native macOS app body" in (tmp_path / "native_pairs.jsonl").read_text(encoding="utf-8")


def test_talk_prompt_wires_native_app_skill_block() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "Applications"
        / "sifta_talk_to_alice_widget.py"
    ).read_text(encoding="utf-8", errors="replace")

    assert "from System.swarm_native_app_teaching import native_app_skill_block" in source
    assert "_native_app_skill_block(" in source
