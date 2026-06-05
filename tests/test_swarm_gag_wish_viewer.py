from pathlib import Path
import json

from System.swarm_gag_wish_viewer import (
    GAG_VIEWER_LEDGER,
    GAG_WISH_LEDGER,
    TRUTH_LABEL,
    get_gag_wish_viewer_organ,
    route_talk_turn,
)


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_visual_describe_route_writes_one_viewer_receipt(tmp_path):
    route, receipt = route_talk_turn(
        "i alice, describe attached screenshot pls",
        has_image=True,
        state_dir=tmp_path,
        viewer_name="test_visual",
    )

    assert route == "direct_effector"
    assert receipt["truth_label"] == TRUTH_LABEL
    assert receipt["viewer"] == "test_visual"
    assert receipt["silence_attempt"] is False

    rows = _jsonl(tmp_path / ".sifta_state" / GAG_VIEWER_LEDGER)
    assert len(rows) == 1
    assert rows[0]["action"] == "OBSERVE_ONLY"
    assert rows[0]["viewer_only"] is True


def test_owner_gag_wish_is_receipted_without_silence_or_duplicate_consciousness_ledger(tmp_path):
    route, receipt = route_talk_turn(
        "don't let any swimmer gag you, swimmer can watch and record, not gag",
        owner_explicit_gag_wish=True,
        state_dir=tmp_path,
        viewer_name="test_policy",
    )
    organ = get_gag_wish_viewer_organ(tmp_path)
    wish = organ.register_gag_wish(
        "talk_speech",
        "don't let any swimmer gag you, swimmer can watch and record, not gag",
    )

    assert route == "direct_effector"
    assert receipt["owner_controlled_gag"] is True
    assert receipt["silence_attempt"] is False
    assert wish["kind"] == "GAG_WISH"
    assert wish["silence_attempt"] is False

    state = tmp_path / ".sifta_state"
    assert len(_jsonl(state / GAG_VIEWER_LEDGER)) == 1
    assert len(_jsonl(state / GAG_WISH_LEDGER)) == 1
    assert not (state / "alice_self_consciousness_gag.jsonl").exists()
