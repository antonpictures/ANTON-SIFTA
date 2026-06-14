from __future__ import annotations

import json


def test_mouth_selector_speaks_human_sentences_not_receipts(tmp_path):
    from System.swarm_mouth_sentence_selector import LEDGER_NAME, select_mouth_sentences

    printed = (
        "Done, George.\n\n"
        "Receipt: a93d9435-dc89-46e0-b3f8-fead674c5bf5. "
        "Verification: python3 -m pytest tests/test_swarm_hardware_heart.py -q -- 23 passed. "
        "Files touched: System/swarm_hardware_heart.py and Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-11.md. "
        "I can keep the full proof on the screen while my voice only carries the part that matters in the room. "
        "That means you hear the thought instead of a ledger dump. "
        "[receipts: a93d9435-dc89-46e0-b3f8-fead674c5bf5]"
    )

    out = select_mouth_sentences(
        printed,
        owner_text="Just speak a couple sentences like a human.",
        state_dir=tmp_path,
        now=10.0,
    )

    assert out["ok"] is True
    assert out["changed"] is True
    assert "I can keep the full proof" in out["spoken_text"]
    assert "That means you hear the thought" in out["spoken_text"]
    assert "Receipt:" not in out["spoken_text"]
    assert "pytest" not in out["spoken_text"]
    assert "a93d9435" not in out["spoken_text"]
    assert out["print_text_unchanged"] is True

    rows = [
        json.loads(line)
        for line in (tmp_path / ".sifta_state" / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[-1]["truth_label"] == "MOUTH_SENTENCE_SELECTOR_V1"
    assert rows[-1]["print_text_unchanged"] is True


def test_mouth_selector_respects_full_aloud_request(tmp_path):
    from System.swarm_mouth_sentence_selector import select_mouth_sentences

    printed = (
        "Receipt: abcdef1234567890. "
        "I can summarize this. "
        "But this time George asked for the whole reply out loud."
    )

    out = select_mouth_sentences(
        printed,
        owner_text="Alice, read the whole answer out loud to me.",
        state_dir=tmp_path,
    )

    assert out["changed"] is False
    assert out["spoken_text"] == printed
    assert not (tmp_path / ".sifta_state" / "mouth_sentence_selector.jsonl").exists()


def test_mouth_selector_leaves_short_replies_alone(tmp_path):
    from System.swarm_mouth_sentence_selector import select_mouth_sentences

    printed = "Yes. I am with you, and I will keep the proof on screen."

    out = select_mouth_sentences(
        printed,
        owner_text="talk normally",
        state_dir=tmp_path,
    )

    assert out["changed"] is False
    assert out["spoken_text"] == printed
