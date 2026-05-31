import json
from pathlib import Path

from Applications import sifta_pheromone_symphony as sym


def test_phrase_to_pheromone_score_is_bounded_and_deterministic():
    phrase = "Alice sings through the field"
    score_a = sym.phrase_to_pheromone_score(phrase, grid_w=40)
    score_b = sym.phrase_to_pheromone_score(phrase, grid_w=40)

    assert score_a == score_b
    assert score_a
    assert all(0 <= start < end <= 40 for start, end, _note in score_a)
    assert all(0 <= note < len(sym.NOTES) for _start, _end, note in score_a)


def test_latest_alice_song_phrase_reads_recent_alice_line(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "alice_conversation.jsonl").write_text(
        json.dumps({"payload": {"role": "user", "text": "ignore me"}}) + "\n"
        + json.dumps({"payload": {"role": "alice", "text": "I can sing the field now."}}) + "\n",
        encoding="utf-8",
    )

    assert sym.latest_alice_song_phrase(state) == "I can sing the field now"


def test_append_sing_receipt_writes_hashes(tmp_path: Path, monkeypatch):
    ledger = tmp_path / "pheromone_symphony_sing.jsonl"
    monkeypatch.setattr(sym, "_SING_LEDGER", ledger)

    row = sym.append_sing_receipt("Alice sings", [(0, 3, 7)], source="test")

    written = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert written["receipt_id"] == row["receipt_id"]
    assert written["phrase_hash"].startswith("sha256:")
    assert written["score_hash"].startswith("sha256:")
    assert written["notes"] == 1


def test_self_listen_metrics_and_biology_formula_are_bounded():
    score = [(0, 3, 7), (4, 7, 9), (8, 11, 11), (12, 15, 7)]
    metrics = sym.listen_to_song_score(score)
    signal = sym.parse_owner_song_feedback("make it smoother and brighter, I like it")
    update = sym.biological_learning_update(metrics, signal)

    assert metrics["note_count"] == 4
    assert 0.0 <= metrics["self_utility"] <= 1.0
    assert signal["pitch_shift"] == 1
    assert signal["target_smooth"] is True
    assert update["formula"] == sym.BIO_STIGMERGIC_SING_FORMULA
    assert 0.05 <= update["p_next"] <= 2.0


def test_adapt_score_from_feedback_changes_score_with_english_teaching():
    score = [(0, 3, 1), (4, 7, 8), (8, 11, 2), (12, 15, 12)]
    adapted = sym.adapt_score_from_feedback(score, "smoother lower calmer")

    assert adapted["score"] != score
    assert adapted["feedback_signal"]["pitch_shift"] == -1
    assert adapted["feedback_signal"]["target_smooth"] is True
    assert adapted["feedback_signal"]["density_scale"] < 1.0
    assert adapted["learning_update"]["formula"] == sym.BIO_STIGMERGIC_SING_FORMULA


def test_append_learning_receipt_writes_formula_and_hashes(tmp_path: Path, monkeypatch):
    ledger = tmp_path / "pheromone_symphony_learning.jsonl"
    monkeypatch.setattr(sym, "_LEARNING_LEDGER", ledger)
    before = [(0, 3, 7), (4, 7, 9)]
    adapted = sym.adapt_score_from_feedback(before, "more variety")

    row = sym.append_learning_receipt("Alice sings", "more variety", before, adapted, source="test")

    written = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert written["receipt_id"] == row["receipt_id"]
    assert written["formula"] == sym.BIO_STIGMERGIC_SING_FORMULA
    assert written["before_score_hash"].startswith("sha256:")
    assert written["after_score_hash"].startswith("sha256:")
    assert written["owner_feedback_signal"]["target_variety"] is True
