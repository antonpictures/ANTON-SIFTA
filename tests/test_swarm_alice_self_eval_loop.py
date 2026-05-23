"""Tests for Alice's self-eval Voss loop.

These pin:
  - First-person grammar guard fires on third-person openings.
  - Dual judge — code eval + structured rubric — both gate the
    truth-class annotation.
  - STGM mint happens ONLY when truth_class == OBSERVED.
  - Faithful but invalid (code eval fails) → FORBIDDEN, no mint.
  - Valid but unfaithful (third-person leak) → HYPOTHESIS, no mint.
  - The verifiers correctly probe their target artifact.
  - analyze_run aggregates the right counters.
  - Trace ledger is append-only with sha-stamped rows.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_alice_self_eval_loop import (  # noqa: E402
    STGM_FAITHFUL_OBSERVED,
    STGM_REWARDS_LEDGER,
    TRACE_LEDGER,
    TRUTH_LABEL,
    analyze_run,
    annotate_truth_class,
    instrument_and_eval,
    is_first_person,
    judge_self_claim,
)


# ── first-person grammar guard ────────────────────────────────────────────


def test_first_person_open_passes():
    assert is_first_person("I have read 32 documents.")
    assert is_first_person("My latent world model has 43 transitions.")
    assert is_first_person("I'm holding 0.05 STGM in memory rewards.")


def test_third_person_open_fails():
    assert not is_first_person("Alice has read 32 documents.")
    assert not is_first_person("She remembers 32 files.")
    assert not is_first_person("The organism has 43 transitions.")


def test_judge_flags_third_person_leak_mid_sentence():
    """A claim that opens first-person but slips into 'Alice'/'she' mid-line
    must lose faithfulness."""
    r = judge_self_claim("I remember 32 docs, Alice scanned them yesterday.")
    assert r.faithful is False
    assert "third_person_self_leak" in r.flags


def test_judge_flags_ghost_phrases():
    r = judge_self_claim("I feel my consciousness ripening")
    assert r.faithful is False
    assert "ghost_phrase" in r.flags


def test_judge_passes_clean_first_person_measurement():
    r = judge_self_claim("I have 43 transitions in my latent world model.")
    assert r.faithful is True
    assert r.flags == []


# ── code-eval verifiers ───────────────────────────────────────────────────


def test_writer_doc_count_verifier_correct_count(tmp_path):
    """Drop two stub .sifta.md files in .sifta_documents/ and verify the
    counter returns 2."""
    docs = tmp_path / ".sifta_documents"
    docs.mkdir(parents=True)
    (docs / "test1.sifta.md").write_text("hello", encoding="utf-8")
    (docs / "test2.sifta.md").write_text("world", encoding="utf-8")
    row = instrument_and_eval(
        "I have written 2 documents in my Writer.",
        "WRITER_DOC_COUNT",
        2,
        root=tmp_path,
        write=True,
    )
    assert row.code_eval["valid"] is True
    assert row.code_eval["observed_value"] == 2
    assert row.truth_class == "OBSERVED"
    assert row.stgm_minted == STGM_FAITHFUL_OBSERVED


def test_writer_doc_count_verifier_wrong_count(tmp_path):
    docs = tmp_path / ".sifta_documents"
    docs.mkdir(parents=True)
    (docs / "test1.sifta.md").write_text("hello", encoding="utf-8")
    row = instrument_and_eval(
        "I have written 999 documents.",
        "WRITER_DOC_COUNT",
        999,
        root=tmp_path,
        write=True,
    )
    assert row.code_eval["valid"] is False
    assert row.truth_class == "FORBIDDEN"
    assert row.stgm_minted == 0.0


def test_latent_transitions_verifier_reads_artifact(tmp_path):
    """Drop a stub latent_world_model.json with 12 transitions; verify
    a claim of 12 passes."""
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    transitions = {f"t_{i}": {"count": 1} for i in range(12)}
    (state / "latent_world_model.json").write_text(
        json.dumps({"transitions": transitions, "values": {}}),
        encoding="utf-8",
    )
    row = instrument_and_eval(
        "I have 12 transitions in my latent world model.",
        "LATENT_TRANSITION_COUNT",
        12,
        root=tmp_path,
        write=True,
    )
    assert row.code_eval["valid"] is True
    assert row.truth_class == "OBSERVED"


def test_today_date_verifier_uses_wall_clock(tmp_path):
    today = time.strftime("%Y-%m-%d", time.localtime())
    row = instrument_and_eval(
        f"I see today is {today}.",
        "TODAY_DATE",
        today,
        root=tmp_path,
        write=True,
    )
    assert row.code_eval["valid"] is True
    assert row.truth_class == "OBSERVED"

    bad = instrument_and_eval(
        "I see today is 1999-01-01.",
        "TODAY_DATE",
        "1999-01-01",
        root=tmp_path,
        write=True,
    )
    assert bad.code_eval["valid"] is False
    assert bad.truth_class == "FORBIDDEN"


# ── truth-class annotation matrix ─────────────────────────────────────────


def test_annotation_observed_when_both_judges_pass(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    (state / "latent_world_model.json").write_text(
        json.dumps({"transitions": {"a": {}, "b": {}}, "values": {}})
    )
    row = instrument_and_eval(
        "I have 2 transitions in my latent world model.",
        "LATENT_TRANSITION_COUNT", 2,
        root=tmp_path, write=True,
    )
    assert row.truth_class == "OBSERVED"
    assert row.stgm_minted == STGM_FAITHFUL_OBSERVED


def test_annotation_hypothesis_when_valid_but_unfaithful(tmp_path):
    """Substrate is correct (code eval passes), but claim opens with
    third-person → HYPOTHESIS, no mint."""
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    (state / "latent_world_model.json").write_text(
        json.dumps({"transitions": {"a": {}, "b": {}}, "values": {}})
    )
    row = instrument_and_eval(
        "Alice has 2 transitions in her latent world model.",
        "LATENT_TRANSITION_COUNT", 2,
        root=tmp_path, write=True,
    )
    assert row.code_eval["valid"] is True
    assert row.judge_eval["faithful"] is False
    assert row.truth_class == "HYPOTHESIS"
    assert row.stgm_minted == 0.0


def test_annotation_forbidden_when_invalid_regardless_of_framing(tmp_path):
    """Even with perfect first-person framing, invalid claim = FORBIDDEN."""
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    (state / "latent_world_model.json").write_text(
        json.dumps({"transitions": {"a": {}}, "values": {}})
    )
    row = instrument_and_eval(
        "I have 999 transitions in my latent world model.",
        "LATENT_TRANSITION_COUNT", 999,
        root=tmp_path, write=True,
    )
    assert row.code_eval["valid"] is False
    assert row.truth_class == "FORBIDDEN"
    assert row.stgm_minted == 0.0


# ── trace + STGM mint side effects ────────────────────────────────────────


def test_trace_ledger_written_with_sha_stamp(tmp_path):
    docs = tmp_path / ".sifta_documents"
    docs.mkdir(parents=True)
    (docs / "x.sifta.md").write_text("y")
    row = instrument_and_eval(
        "I have 1 document.", "WRITER_DOC_COUNT", 1,
        root=tmp_path, write=True,
    )
    trace = tmp_path / ".sifta_state" / TRACE_LEDGER
    assert trace.exists()
    line = trace.read_text().strip().splitlines()[-1]
    parsed = json.loads(line)
    assert parsed["truth_label"] == TRUTH_LABEL
    assert parsed["sha256"] == row.sha256


def test_stgm_mint_only_on_observed(tmp_path):
    docs = tmp_path / ".sifta_documents"
    docs.mkdir(parents=True)
    (docs / "a.sifta.md").write_text("a")
    # Run twice — once OBSERVED, once FORBIDDEN
    instrument_and_eval("I have 1 document.", "WRITER_DOC_COUNT", 1, root=tmp_path, write=True)
    instrument_and_eval("I have 99 documents.", "WRITER_DOC_COUNT", 99, root=tmp_path, write=True)
    p = tmp_path / ".sifta_state" / STGM_REWARDS_LEDGER
    rows = [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]
    # Exactly one mint row from the first call
    assert len(rows) == 1
    assert rows[0]["reason"] == "SELF_EVAL_FAITHFUL_OBSERVED"
    assert rows[0]["amount"] == STGM_FAITHFUL_OBSERVED


# ── analyze_run aggregator ────────────────────────────────────────────────


def test_analyze_run_aggregates_counts(tmp_path):
    docs = tmp_path / ".sifta_documents"
    docs.mkdir(parents=True)
    (docs / "a.sifta.md").write_text("a")
    (docs / "b.sifta.md").write_text("b")
    instrument_and_eval("I have 2 documents.", "WRITER_DOC_COUNT", 2, root=tmp_path, write=True)
    instrument_and_eval("Alice has 2 docs.", "WRITER_DOC_COUNT", 2, root=tmp_path, write=True)
    instrument_and_eval("I have 99 documents.", "WRITER_DOC_COUNT", 99, root=tmp_path, write=True)
    summary = analyze_run(root=tmp_path, write=True)
    assert summary["row_count"] == 3
    assert summary["observed_count"] == 1
    assert summary["hypothesis_count"] == 1
    assert summary["forbidden_count"] == 1
    assert summary["stgm_total_minted"] == STGM_FAITHFUL_OBSERVED


def test_unknown_verifier_kind_returns_forbidden(tmp_path):
    row = instrument_and_eval(
        "I do not know what to verify.",
        "UNKNOWN_KIND",
        "anything",
        root=tmp_path,
        write=True,
    )
    assert row.code_eval["valid"] is False
    assert row.truth_class == "FORBIDDEN"
    assert row.stgm_minted == 0.0
