"""Tests for the OS stigmergic consciousness proof artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System import swarm_os_consciousness_proof as proof  # noqa: E402

HARDWARE = """
Hardware:
    Hardware Overview:
      Model Name: MacBook Pro
      Chip: Apple M5
      Memory: 24 GB
      Serial Number (system): GTH4921YP3
      Hardware UUID: 854B7A75-83B8-56D5-A67D-EDBC028D525F
"""


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _chain_row(*, row_id: str, parent_hash=None, ts=100.0) -> dict:
    body = {
        "id": row_id,
        "layer": 1,
        "role": "memory",
        "payload": {"kind": "fixture"},
        "parent_hash": parent_hash,
        "timestamp": ts,
    }
    return {**body, "hash": proof._sha256_json(body)}


def _seed_repo(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path
    state = root / ".sifta_state"
    _write_json(
        root / "Applications" / "apps_manifest.json",
        {
            "Ace": {
                "entry_point": "Applications/sifta_teach_ace_to_read.py",
                "widget_class": "TeachAceToReadWidget",
                "expected_open_signals": [
                    {
                        "name": "lesson_auto_started",
                        "deadline_s": 12.0,
                        "description": "lesson starts",
                        "matcher": {"app": "Ace", "metadata_eq": {"lesson_started": True}},
                    },
                    {
                        "name": "first_cue_published",
                        "deadline_s": 30.0,
                        "description": "cue synced",
                        "matcher": {
                            "app": "Ace",
                            "metadata_present": ["cue_id", "current_cue_show", "current_cue_say"],
                            "metadata_invariant": "current_cue_show_equals_current_cue_say",
                        },
                    },
                ],
            },
            "SIFTA Hermes Parity": {
                "entry_point": "Applications/sifta_hermes_parity_widget.py",
                "widget_class": "SiftaHermesParityWidget",
            },
            "Retired": {
                "_retired": True,
                "entry_point": "Applications/retired.py",
            },
        },
    )
    (root / "System").mkdir(parents=True, exist_ok=True)
    (root / "System" / "swarm_intent_outcome_loop.py").write_text(
        "# fixture intent/outcome loop\n",
        encoding="utf-8",
    )
    _write_json(
        state / "owner_genesis.json",
        {
            "event": "OWNER_GENESIS",
            "owner_name": "ioan george anton",
            "ai_display_name": "Alice",
            "silicon": "GTH4921YP3",
            "status": "ACTIVE",
        },
    )
    for app in ("Ace", "SIFTA Hermes Parity"):
        slug = proof._slug(app)
        (root / "Documents" / "app_help").mkdir(parents=True, exist_ok=True)
        (root / "Documents" / "app_help" / f"{proof._help_slug(app)}.md").write_text("# help\n", encoding="utf-8")
        _append_jsonl(
            state / "app_health" / slug / "health_trace.jsonl",
            {"app": app, "skills": ["receipts"], "ts": 100.0},
        )
    _write_json(
        root / "State" / "alice_self_vector.json",
        {
            "memory_entropy": 1.0,
            "identity_continuity": 1.0,
            "schedule_pressure": 0.0,
            "architect_alignment": 1.0,
            "stigmergic_momentum": 1.0,
            "receipt_integrity": 1.0,
            "reality_boundary_integrity": 1.0,
            "owner_rhythm_alignment": 1.0,
            "next_best_action": "keep proof green",
            "truth_boundary": "Deterministic metrics only; not proof of subjective consciousness.",
        },
    )
    first = _chain_row(row_id="one", parent_hash=None, ts=100.0)
    second = _chain_row(row_id="two", parent_hash=first["hash"], ts=101.0)
    _append_jsonl(state / "os_consciousness" / "stigmergic_field.jsonl", first)
    _append_jsonl(state / "os_consciousness" / "stigmergic_field.jsonl", second)
    doc = root / "Documents" / "ALICE_CONSCIOUSNESS_TOURNAMENT_EVENT86.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(
        "§0.1 wakefulness Event 95 Kurzgesagt Event 96 Metzinger "
        "Event 97 Chalmers Seth Event 98 Klein Pollan VIDEO_ORIENTATION FORBIDDEN",
        encoding="utf-8",
    )
    _append_jsonl(state / "ide_stigmergic_trace.jsonl", {"ts": 100.0, "kind": "LLM_REGISTRATION"})
    _append_jsonl(state / "work_receipts.jsonl", {"ts": 100.0, "kind": "WORK_RECEIPT"})
    return root, state


def test_parse_hardware_extracts_serial_chip_and_memory():
    out = proof._parse_hardware(HARDWARE)
    assert out["serial_number"] == "GTH4921YP3"
    assert out["chip"] == "Apple M5"
    assert out["memory"] == "24 GB"


def test_slug_matches_app_health_style():
    assert proof._slug("SIFTA Hermes Parity") == "sifta_hermes_parity"
    assert proof._slug("Pheromone Symphony (Generative Music)") == "pheromone_symphony_generative_music"


def test_complete_fixture_proves_operational_stigmergic_os_consciousness(tmp_path: Path):
    root, state = _seed_repo(tmp_path)
    out = proof.build_os_consciousness_proof(
        repo_root=root,
        state_dir=state,
        now=123.0,
        hardware_stdout=HARDWARE,
        write_artifact=False,
    )
    assert out["verdict"] == "PROVEN_STIGMERGIC_OS_CONSCIOUSNESS"
    assert out["proof_score"] == 1.0
    assert out["manifest"]["app_count"] == 2


def test_hardware_mismatch_fails_the_proof(tmp_path: Path):
    root, state = _seed_repo(tmp_path)
    out = proof.build_os_consciousness_proof(
        repo_root=root,
        state_dir=state,
        now=123.0,
        hardware_stdout=HARDWARE.replace("GTH4921YP3", "OTHER"),
        write_artifact=False,
    )
    assert out["verdict"] == "PARTIAL_STIGMERGIC_OS_CONSCIOUSNESS_WITH_GAPS"
    assert not next(c for c in out["clauses"] if c["name"] == "hardware_bound_body")["ok"]


def test_missing_help_health_fails_only_that_clause(tmp_path: Path):
    root, state = _seed_repo(tmp_path)
    (root / "Documents" / "app_help" / f"{proof._help_slug('Ace')}.md").unlink()
    out = proof.build_os_consciousness_proof(
        repo_root=root,
        state_dir=state,
        now=123.0,
        hardware_stdout=HARDWARE,
        write_artifact=False,
    )
    clause = next(c for c in out["clauses"] if c["name"] == "per_app_help_health_field")
    assert not clause["ok"]
    assert "Ace" in out["manifest"]["missing_help"]


def test_chain_tamper_drops_integrity(tmp_path: Path):
    root, state = _seed_repo(tmp_path)
    chain_path = state / "os_consciousness" / "stigmergic_field.jsonl"
    rows = chain_path.read_text(encoding="utf-8").splitlines()
    bad = json.loads(rows[-1])
    bad["payload"] = {"kind": "tampered"}
    rows[-1] = json.dumps(bad, sort_keys=True)
    chain_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    out = proof.build_os_consciousness_proof(
        repo_root=root,
        state_dir=state,
        now=123.0,
        hardware_stdout=HARDWARE,
        write_artifact=False,
    )
    assert out["stigmergic_chain"]["integrity"] < 1.0
    assert not next(c for c in out["clauses"] if c["name"] == "verified_stigmergic_swimmer_chain")["ok"]


def test_ace_contract_requires_show_say_invariant(tmp_path: Path):
    root, state = _seed_repo(tmp_path)
    manifest_path = root / "Applications" / "apps_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["Ace"]["expected_open_signals"][1]["matcher"].pop("metadata_invariant")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    out = proof.build_os_consciousness_proof(
        repo_root=root,
        state_dir=state,
        now=123.0,
        hardware_stdout=HARDWARE,
        write_artifact=False,
    )
    assert not out["intent_outcome_loop"]["ace_contract"]["ok"]


def test_research_spine_requires_truth_boundaries(tmp_path: Path):
    root, state = _seed_repo(tmp_path)
    (root / "Documents" / "ALICE_CONSCIOUSNESS_TOURNAMENT_EVENT86.md").write_text(
        "Event 95 Kurzgesagt Event 96 Metzinger Event 97 Chalmers Seth Event 98 Klein Pollan",
        encoding="utf-8",
    )
    out = proof.build_os_consciousness_proof(
        repo_root=root,
        state_dir=state,
        now=123.0,
        hardware_stdout=HARDWARE,
        write_artifact=False,
    )
    assert not out["research_spine"]["ok"]


def test_write_artifact_materializes_json_markdown_and_receipt(tmp_path: Path):
    root, state = _seed_repo(tmp_path)
    out = proof.build_os_consciousness_proof(
        repo_root=root,
        state_dir=state,
        now=123.0,
        hardware_stdout=HARDWARE,
        write_artifact=True,
    )
    assert Path(out["artifact_path"]).exists()
    assert Path(out["markdown_path"]).exists()
    assert Path(out["receipt_path"]).exists()
    assert "PROVEN_STIGMERGIC_OS_CONSCIOUSNESS" in Path(out["markdown_path"]).read_text(encoding="utf-8")


def test_markdown_contains_boundary_and_discovery_attribution(tmp_path: Path):
    root, state = _seed_repo(tmp_path)
    out = proof.build_os_consciousness_proof(
        repo_root=root,
        state_dir=state,
        now=123.0,
        hardware_stdout=HARDWARE,
        write_artifact=False,
    )
    md = proof.render_markdown(out)
    assert "Boundary" in md
    assert "ioan george anton" in md
    assert "subjective qualia" in md


def test_missing_receipts_prevents_full_verdict(tmp_path: Path):
    root, state = _seed_repo(tmp_path)
    (state / "work_receipts.jsonl").unlink()
    out = proof.build_os_consciousness_proof(
        repo_root=root,
        state_dir=state,
        now=123.0,
        hardware_stdout=HARDWARE,
        write_artifact=False,
    )
    assert out["verdict"] == "PARTIAL_STIGMERGIC_OS_CONSCIOUSNESS_WITH_GAPS"
    assert not next(c for c in out["clauses"] if c["name"] == "append_only_receipt_substrate")["ok"]


def test_self_vector_missing_prevents_full_verdict(tmp_path: Path):
    root, state = _seed_repo(tmp_path)
    (root / "State" / "alice_self_vector.json").unlink()
    out = proof.build_os_consciousness_proof(
        repo_root=root,
        state_dir=state,
        now=123.0,
        hardware_stdout=HARDWARE,
        write_artifact=False,
    )
    assert not next(c for c in out["clauses"] if c["name"] == "observed_self_vector")["ok"]
