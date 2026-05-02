"""Event 110 — LLM-bearing organism substrate manifest."""

import json
from pathlib import Path

from System import swarm_llm_organism_architecture as arch


def test_manifest_truth_label() -> None:
    m = arch.get_organism_manifest()
    assert m["truth_label"] == arch.TRUTH_LABEL
    assert "not a new pretrained" in m["truth_note"].lower()
    assert "append-only" in " ".join(m["core_principles"]).lower()


def test_deposit_organism_state_append_only(tmp_path: Path) -> None:
    row = arch.deposit_organism_state({"event": "110_organism_defined"}, state_dir=tmp_path)
    assert row["event"] == "110_organism_defined"
    assert row["schema_version"] == arch.SCHEMA_VERSION
    path = tmp_path / "llm_organism_state.jsonl"
    assert path.exists()
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["name"] == "SIFTA_LLM_BEARING_ORGANISM"


def test_regime_summary_reads_disk(tmp_path: Path) -> None:
    (tmp_path / "regime_state.json").write_text(
        json.dumps({"state": "CONSOLIDATION", "stigmergic_density": 0.33}),
        encoding="utf-8",
    )
    (tmp_path / "crystallized_skills.json").write_text(
        json.dumps({"a": {"pattern_signature": "x"}, "b": {"pattern_signature": "y"}}),
        encoding="utf-8",
    )
    s = arch.get_current_regime_summary(state_dir=tmp_path)
    assert s["regime"] == "CONSOLIDATION"
    assert s["stigmergic_density"] == 0.33
    assert s["crystallized_skills_count"] == 2
