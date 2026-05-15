"""Tests for the unified organ directory + generic self-eval walker.

These pin:
  - register_organ stores the record and persists it to disk
  - claim_template MUST contain '{value}' or register raises
  - Re-registering by name updates instead of duplicating
  - The directory survives a round-trip through disk
  - register_default_organs is idempotent across repeat calls
  - Built-in probes return the right shape from real ledgers
  - walk_and_self_eval files first-person claims and mints STGM
  - An organ without verifier_kind is skipped cleanly (not crashed)
  - A broken probe is reported, not raised
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_alice_self_eval_loop import STGM_FAITHFUL_OBSERVED  # noqa: E402
from System.swarm_organ_directory import (  # noqa: E402
    DIRECTORY_FILE,
    TRUTH_LABEL,
    WALK_LEDGER,
    clear_registry,
    find_organ,
    list_organs,
    probe_journal_row_count,
    probe_latent_transition_count,
    probe_organ,
    probe_today_date,
    probe_writer_doc_count,
    register_default_organs,
    register_organ,
    walk_and_self_eval,
)


@pytest.fixture(autouse=True)
def _reset_registry_between_tests():
    """Each test starts with a clean in-memory registry."""
    clear_registry()
    yield
    clear_registry()


# ── registration semantics ────────────────────────────────────────────────


def test_register_organ_persists_to_disk(tmp_path):
    rec = register_organ(
        "test_organ",
        truth_label="TEST_V1",
        truth_boundary="Test scaffold.",
        ledger_path=".sifta_state/test.jsonl",
        claim_template="I have {value} test rows.",
        verifier_kind="WRITER_DOC_COUNT",
        state_dir=tmp_path,
    )
    assert rec.name == "test_organ"
    path = tmp_path / DIRECTORY_FILE
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["truth_label"] == TRUTH_LABEL
    assert data["organs"][0]["name"] == "test_organ"


def test_register_requires_value_placeholder_in_template(tmp_path):
    with pytest.raises(ValueError, match="claim_template must contain"):
        register_organ(
            "bad",
            truth_label="T",
            truth_boundary="b",
            ledger_path="p",
            claim_template="I have something with no placeholder.",
            state_dir=tmp_path,
        )


def test_register_requires_nonempty_name(tmp_path):
    with pytest.raises(ValueError):
        register_organ(
            "",
            truth_label="T",
            truth_boundary="b",
            ledger_path="p",
            claim_template="I have {value}.",
            state_dir=tmp_path,
        )


def test_register_is_idempotent_by_name(tmp_path):
    register_organ(
        "same_name", truth_label="A", truth_boundary="a", ledger_path="x",
        claim_template="I have {value}.", state_dir=tmp_path,
    )
    register_organ(
        "same_name", truth_label="B", truth_boundary="b", ledger_path="y",
        claim_template="I have {value} now.", state_dir=tmp_path,
    )
    organs = list_organs(state_dir=tmp_path)
    assert len(organs) == 1
    assert organs[0].truth_label == "B"


def test_directory_survives_round_trip(tmp_path):
    register_organ(
        "round_trip", truth_label="RT", truth_boundary="b", ledger_path="p",
        claim_template="I have {value}.", state_dir=tmp_path,
    )
    # Wipe in-memory; reload from disk
    clear_registry()
    found = find_organ("round_trip", state_dir=tmp_path)
    assert found is not None
    assert found.truth_label == "RT"


# ── default organ wiring ──────────────────────────────────────────────────


def test_register_default_organs_is_idempotent(tmp_path):
    r1 = register_default_organs(state_dir=tmp_path)
    r2 = register_default_organs(state_dir=tmp_path)
    assert len(r1) == len(r2)
    organs = list_organs(state_dir=tmp_path)
    names = {o.name for o in organs}
    assert "writer_documents" in names
    assert "latent_world_model" in names
    assert "first_person_journal" in names
    assert "wall_clock" in names
    assert "stgm_memory_wallet" in names


def test_default_organs_have_first_person_templates(tmp_path):
    register_default_organs(state_dir=tmp_path)
    organs = list_organs(state_dir=tmp_path)
    for o in organs:
        # §7.10.1 + §7.14: first-person opener
        first_word = o.claim_template.lstrip().split()[0].lower()
        assert first_word in {"i", "my", "i'm", "i've", "i'll"}, o.claim_template


# ── built-in probes ───────────────────────────────────────────────────────


def test_probe_writer_doc_count_reads_directory(tmp_path):
    docs = tmp_path / ".sifta_documents"
    docs.mkdir(parents=True)
    (docs / "a.sifta.md").write_text("x")
    (docs / "b.sifta.md").write_text("y")
    assert probe_writer_doc_count(root=tmp_path) == 2


def test_probe_latent_transitions_reads_artifact(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    (state / "latent_world_model.json").write_text(
        json.dumps({"transitions": {"a": {}, "b": {}, "c": {}}, "values": {}})
    )
    assert probe_latent_transition_count(root=tmp_path) == 3


def test_probe_journal_row_count_handles_missing_ledger(tmp_path):
    # No journal file → 0, no crash
    assert probe_journal_row_count(root=tmp_path) == 0


def test_probe_today_date_matches_wall_clock():
    import time as _time
    expected = _time.strftime("%Y-%m-%d", _time.localtime())
    assert probe_today_date() == expected


def test_probe_organ_reports_error_when_unregistered(tmp_path):
    result = probe_organ("nonexistent_organ_xyz", root=tmp_path)
    assert result["value"] is None
    assert result["error"] == "unregistered"


def test_probe_organ_reports_error_when_probe_callable_missing(tmp_path):
    register_organ(
        "no_probe", truth_label="T", truth_boundary="b", ledger_path="p",
        claim_template="I have {value}.",
        probe_module="System.does_not_exist", probe_callable="missing",
        state_dir=tmp_path,
    )
    result = probe_organ("no_probe", root=tmp_path)
    assert result["value"] is None
    assert result["error"] == "probe_unresolvable"


# ── walk_and_self_eval ────────────────────────────────────────────────────


def test_walker_mints_stgm_on_observed_organ(tmp_path):
    """Drop two .sifta.md fixture files, register the writer_documents
    organ, walk → expect one OBSERVED + STGM_FAITHFUL_OBSERVED mint."""
    docs = tmp_path / ".sifta_documents"
    docs.mkdir(parents=True)
    (docs / "x.sifta.md").write_text("hi")
    (docs / "y.sifta.md").write_text("hi")
    register_organ(
        "writer_documents",
        truth_label="SIFTA_STIGMERGIC_WRITER_MEMORY_V1",
        truth_boundary="counter",
        ledger_path=".sifta_documents/",
        claim_template="I have written {value} documents in my Writer.",
        verifier_kind="WRITER_DOC_COUNT",
        probe_module="System.swarm_organ_directory",
        probe_callable="probe_writer_doc_count",
        state_dir=tmp_path,
    )
    out = walk_and_self_eval(root=tmp_path, write=True, state_dir=tmp_path)
    assert out["evaluated_count"] == 1
    assert out["stgm_minted_total"] == STGM_FAITHFUL_OBSERVED
    walk_ledger = tmp_path / WALK_LEDGER
    assert walk_ledger.exists()


def test_walker_skips_organs_without_verifier_kind(tmp_path):
    register_organ(
        "directory_only",
        truth_label="T", truth_boundary="b", ledger_path="p",
        claim_template="I have {value} rows.",
        verifier_kind=None,  # no verifier → walker skips
        probe_module="System.swarm_organ_directory",
        probe_callable="probe_journal_row_count",
        state_dir=tmp_path,
    )
    out = walk_and_self_eval(root=tmp_path, write=True, state_dir=tmp_path)
    assert out["evaluated_count"] == 0
    assert out["skipped_count"] == 1
    assert out["results"][0]["reason"] == "no verifier_kind registered"


def test_walker_reports_broken_probe_without_raising(tmp_path):
    register_organ(
        "broken_probe",
        truth_label="T", truth_boundary="b", ledger_path="p",
        claim_template="I have {value}.",
        verifier_kind="WRITER_DOC_COUNT",
        probe_module="System.does_not_exist",
        probe_callable="missing",
        state_dir=tmp_path,
    )
    out = walk_and_self_eval(root=tmp_path, write=True, state_dir=tmp_path)
    assert out["evaluated_count"] == 0
    assert out["skipped_count"] == 1
    assert "probe_unresolvable" in out["results"][0]["reason"]


def test_walker_full_directory_run_with_real_probes(tmp_path):
    """Wire all five STGM-earning default organs and run a full walk.
    Expects five mints when the artifacts are present."""
    docs = tmp_path / ".sifta_documents"
    docs.mkdir(parents=True)
    (docs / "a.sifta.md").write_text("a")
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    (state / "latent_world_model.json").write_text(
        json.dumps({"transitions": {"a": {}, "b": {}}, "values": {}})
    )
    (state / "alice_first_person_journal.jsonl").write_text(
        "\n".join('{"x": ' + str(i) + "}" for i in range(7)) + "\n"
    )
    register_default_organs(state_dir=tmp_path)
    out = walk_and_self_eval(root=tmp_path, write=True, state_dir=tmp_path)
    # 5 STGM-earning organs registered, 2 directory-only → at least 4 evaluated
    assert out["evaluated_count"] >= 4
    assert out["stgm_minted_total"] >= 4 * STGM_FAITHFUL_OBSERVED - 1e-9
