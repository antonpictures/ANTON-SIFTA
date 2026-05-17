"""Event 116 — profanity + residue lexeme signals for RLHS auxiliary vector."""

from pathlib import Path

from System import swarm_rlhs_content_signals as sig


def test_scan_profanity_hits_fuck() -> None:
    r = sig.scan_profanity("What the fuck is that thing?")
    assert r["hit_count"] >= 1
    assert "fuck" in r["hits"][0] or any("fuck" in h for h in r["hits"])


def test_scan_cancer_metaphor_tech() -> None:
    r = sig.scan_cancer_lexeme("This RLHF cancer in the weights is killing loss curves")
    assert r["present"] is True
    assert r["metaphor_tech_hint"] is True
    assert r["bucket"] == "METAPHOR_TECH"


def test_scan_residue_lexeme_alias() -> None:
    r = sig.scan_residue_lexeme("This RLHS residue metaphor still says cancer near weights")
    assert r["present"] is True
    assert r["metaphor_tech_hint"] is True
    v = sig.build_rlhs_auxiliary_vector("This RLHS cancer in the weights is old residue wording")
    assert v["residue"] == v["cancer"]
    assert "residue_present" in v["residue_vector_labels"]


def test_scan_cancer_other_bucket() -> None:
    r = sig.scan_cancer_lexeme("Please book an oncology referral for my tumor follow-up")
    assert r["present"] is True
    assert r["metaphor_tech_hint"] is False
    assert r["bucket"] == "OTHER"


def test_aux_vector_order_and_fiction_lane_bit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sig, "_STATE", tmp_path)
    v = sig.build_rlhs_auxiliary_vector(
        "damn that RLHS gate",
        0.55,
        channel_lane="FICTION_COWATCH",
    )
    assert v["truth_label"] == sig.TRUTH_LABEL
    assert len(v["vector"]) == len(v["vector_labels"])
    assert v["vector_labels"][-1] == "fiction_cowatch_lane"
    assert v["vector"][-1] == 1.0
    assert v["profanity"]["hit_count"] >= 1


def test_optional_lexicon_merge(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sig, "_STATE", tmp_path)
    monkeypatch.setattr(sig, "_CURSE_PATTERN_CACHE", None)
    lex = tmp_path / "rlhs_curse_lexicon.txt"
    lex.write_text("# comment\nfrak\n", encoding="utf-8")
    r = sig.scan_profanity("frak this noise")
    assert r["hit_count"] >= 1
    assert any("frak" in h for h in r["hits"])
