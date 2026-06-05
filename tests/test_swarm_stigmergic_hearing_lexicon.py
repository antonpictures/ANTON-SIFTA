from __future__ import annotations

import json

from System.swarm_stigmergic_hearing_lexicon import (
    apply_hearing_lexicon,
    normalize_stigmergic_terms,
)


def test_normalizes_stigmergic_homophones_without_touching_plain_stigma():
    text, corrections = normalize_stigmergic_terms("stick magic and stigma magical are the word")

    assert text == "STIGMERGIC and STIGMERGIC are the word"
    assert [c["reason"] for c in corrections] == [
        "stigmergic_term_stt_homophone",
        "stigmergic_term_stt_homophone",
    ]

    unchanged, no_corrections = normalize_stigmergic_terms("social stigma is not the same word")
    assert unchanged == "social stigma is not the same word"
    assert no_corrections == []


def test_apply_hearing_lexicon_writes_receipt(tmp_path):
    out = apply_hearing_lexicon(
        "stigma magic memory",
        state_dir=tmp_path,
        source="test",
        stt_conf=0.42,
        persist=True,
    )

    assert out["changed"] is True
    assert out["normalized_text"] == "STIGMERGIC memory"
    rows = (tmp_path / "hearing_lexicon_corrections.jsonl").read_text(encoding="utf-8").splitlines()
    row = json.loads(rows[-1])
    assert row["truth_label"] == "STIGMERGIC_HEARING_LEXICON_V1"
    assert row["normalized_text"] == "STIGMERGIC memory"
    assert row["stt_confidence"] == 0.42
