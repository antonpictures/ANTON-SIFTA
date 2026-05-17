"""Focused checks for the playable Stigmergic Speech Game script."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import scripts.stigmergic_speech_game as game  # noqa: E402
from System.swarm_speech_game_sentence_corpus import RealSentence  # noqa: E402


def _sentence() -> RealSentence:
    return RealSentence(
        text="Alice keeps the field grounded with receipts.",
        source_kind="digest",
        source_path="Documents/architect_memory_digest/example.md",
        word_count=7,
    )


def test_consensus_uses_owner_supervised_ground_truth(monkeypatch):
    monkeypatch.setattr(game, "build_alice_self_vector", lambda **kwargs: {})

    target = _sentence()
    out = game.alice_consensus(
        "Alice keeps the field grounded with receipt.",
        target.text,
        target_sentence=target,
    )

    assert out["corrected"] == target.text
    assert out["intended"] == target.text
    assert out["corrected_by"] == "owner_supervised_ground_truth"
    assert out["target_sentence"]["source_path"] == target.source_path
    assert out["confidence"] == 1.0
    assert out["stgm_earned"] == 3.5


def test_consensus_without_ground_truth_stays_honest(monkeypatch):
    monkeypatch.setattr(game, "build_alice_self_vector", lambda **kwargs: {})

    out = game.alice_consensus("mammary digest oregon")

    assert out["corrected"] == "mammary digest oregon"
    assert out["intended"] == ""
    assert out["corrected_by"] == "raw_transcript_no_ground_truth"
    assert out["confidence"] == 0.45
    assert out["stgm_earned"] == 0.5


def test_record_round_persists_target_sentence(tmp_path, monkeypatch):
    rounds = tmp_path / "speech_game_rounds.jsonl"
    stgm = tmp_path / "stgm_ledger.jsonl"
    monkeypatch.setattr(game, "_SPEECH_ROUNDS", rounds)
    monkeypatch.setattr(game, "_STGM_LEDGER", stgm)
    monkeypatch.setattr(game, "label_knowledge", lambda payload: {"reality_boundary": "OBSERVED"})

    target = _sentence()
    consensus = game.alice_consensus("Alice keeps the field grounded.", target.text, target_sentence=target)
    round_id = game.record_round("Alice keeps the field grounded.", consensus, 1, 0, target_sentence=target)

    round_row = json.loads(rounds.read_text(encoding="utf-8").splitlines()[0])
    stgm_row = json.loads(stgm.read_text(encoding="utf-8").splitlines()[0])

    assert round_row["round_id"] == round_id
    assert round_row["intended"] == target.text
    assert round_row["target_sentence"]["text"] == target.text
    assert round_row["target_sentence"]["source_kind"] == "digest"
    assert round_row["reality_boundary"] == "OBSERVED"
    assert stgm_row["round_id"] == round_id
    assert stgm_row["amount"] == consensus["stgm_earned"]
