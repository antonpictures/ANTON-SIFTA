import json
from pathlib import Path

from System.swarm_self_citation_organ import (
    BRIEFING_LEDGER,
    TRUTH_LABEL,
    UTTERANCE_LEDGER,
    build_between_turns_briefing,
    compute_body_n,
    format_turn_start_self_citation_block,
    trace_utterance,
)


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_compute_body_n_tracks_alice_and_owner_intervals(tmp_path):
    now = 1_000.0
    _append(
        tmp_path / "alice_conversation.jsonl",
        {"payload": {"ts": now - 120, "role": "alice", "text": "I spoke about residue.", "model": "m"}},
    )
    _append(
        tmp_path / "alice_conversation.jsonl",
        {"payload": {"ts": now - 30, "role": "user", "text": "Alice, this is owner input."}},
    )

    n = compute_body_n(state_dir=tmp_path, now=now)

    assert n["truth_label"] == TRUTH_LABEL
    assert n["n_minutes_since_alice_speech"] == 2.0
    assert n["n_minutes_since_owner_body_or_input"] == 0.5


def test_turn_start_briefing_writes_gradient_and_n(tmp_path):
    now = 2_000.0
    _append(
        tmp_path / "ambient_room_transcripts.jsonl",
        {"ts": now - 10, "text": "George is teaching Alice about residue, STGM, and self citation."},
    )
    _append(
        tmp_path / "owner_teaching_moments.jsonl",
        {"ts": now - 20, "owner_text": "Residue should remove words, not whole paragraphs."},
    )

    block = format_turn_start_self_citation_block(
        "build all self citation",
        state_dir=tmp_path,
        now=now,
    )

    assert "SELF-CITATION ORGAN" in block
    assert "N_owner=" in block
    assert "residue_voice" in block
    rows = [
        json.loads(line)
        for line in (tmp_path / BRIEFING_LEDGER).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[-1]["kind"] == "SELF_CITATION_TURN_START_BRIEFING"
    assert rows[-1]["gradient"]["lanes"]


def test_trace_utterance_cites_prior_owner_turn_and_flags_uncited_sentence(tmp_path):
    now = 3_000.0
    briefing = build_between_turns_briefing(
        user_text="residue self citation",
        state_dir=tmp_path,
        now=now,
        write=False,
    )
    assert briefing["truth_label"] == TRUTH_LABEL

    summary = trace_utterance(
        "I kept the residue sentence alive. Zqxv orbital blue.",
        prior_user_text="Please keep residue words but do not swallow the sentence.",
        model="test-model",
        state_dir=tmp_path,
        now=now,
    )

    assert summary["truth_label"] == TRUTH_LABEL
    assert summary["sentence_count"] == 2
    assert summary["zero_citation_count"] == 1
    rows = [
        json.loads(line)
        for line in (tmp_path / UTTERANCE_LEDGER).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[-1]["sentences"][0]["citations"][0]["source"] == "current_owner_turn"
    assert rows[-1]["sentences"][1]["uncertain_no_citation"] is True
