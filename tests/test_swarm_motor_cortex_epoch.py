import json

from System.swarm_epoch_sealer import (
    build_revival_proof,
    seal_epoch,
    verify_epoch_seal,
)
from System.swarm_motor_cortex import (
    emit,
    execute_motor_action,
    heart_period_s,
    propose_motor_action,
    recent_pulses,
    resolve_semantic_target,
    vocabulary,
)
from System.swarm_visual_confirmation import (
    record_visual_confirmation,
    required_stages_for_action,
    visual_confirmation_passed,
)


def test_legacy_motor_pulse_api_survives(tmp_path):
    row = emit("heartbeat", source="pytest", root=tmp_path)

    assert row["truth_label"] == "MOTOR_PULSE"
    assert row["kind"] == "heartbeat"
    assert row["led_blink_ms"] == 0
    assert "heartbeat" in vocabulary()
    assert heart_period_s(root=tmp_path) > 0
    assert recent_pulses(root=tmp_path)[-1]["source"] == "pytest"


def test_semantic_target_resolution_uses_candidate_labels():
    result = resolve_semantic_target(
        "search bar",
        candidates=[
            {"label": "send button", "coordinates": [10, 20], "confidence": 0.99},
            {"label": "browser search bar", "coordinates": [100.4, 42.2], "confidence": 0.93},
        ],
    )

    assert result.method == "candidate_match"
    assert result.resolved_coordinates == (100, 42)
    assert result.confidence > 0.80


def test_motor_action_logs_semantic_target_and_visual_tiers(tmp_path):
    decision = propose_motor_action(
        "CLICK",
        "search bar",
        "Search - Safari",
        "Safari",
        confidence=0.95,
        conservative_strength=0.1,
        root=tmp_path,
        candidates=[{"label": "search bar", "coordinates": [50, 60], "confidence": 0.95}],
    )

    assert decision.permitted
    assert decision.risk_tier == "LOW"
    assert decision.visual_confirmation_required == ("before",)
    row = json.loads((tmp_path / "motor_cortex_log.jsonl").read_text().splitlines()[-1])
    assert row["semantic_target"] == "search bar"
    assert row["resolved_coordinates"] == [50, 60]


def test_terminal_typing_blocks_without_owner_go(tmp_path):
    decision = propose_motor_action(
        "TYPE",
        "terminal prompt",
        "zsh",
        "Terminal",
        confidence=0.98,
        conservative_strength=0.0,
        root=tmp_path,
        text="rm -rf /",
    )

    assert not decision.permitted
    assert decision.risk_tier in {"HIGH", "HARD_PERIMETER"}
    assert decision.execution_status in {"BLOCKED_BY_RISK", "BLOCKED_BY_PERIMETER"}


def test_execute_motor_action_dry_run_without_env(tmp_path):
    decision = propose_motor_action(
        "CLICK",
        "send button",
        "SIFTA Talk",
        "SIFTA OS",
        confidence=0.9,
        conservative_strength=0.1,
        root=tmp_path,
        resolved_coordinates=(1, 2),
    )
    executed = execute_motor_action(decision, root=tmp_path, execute=False)

    assert executed.execution_status == "DRY_RUN"


def test_visual_confirmation_records_before_after_and_passes(tmp_path):
    before = record_visual_confirmation(
        semantic_target="Alice text box",
        stage="before",
        risk_tier="MEDIUM",
        observed=True,
        confidence=0.88,
        root=tmp_path,
        resolved_coordinates=(12, 34),
        screenshot_bytes=b"fake pixels",
    )
    after = record_visual_confirmation(
        semantic_target="Alice text box",
        stage="after",
        risk_tier="MEDIUM",
        observed=True,
        confidence=0.91,
        root=tmp_path,
    )

    assert before["screenshot_hash"]
    assert required_stages_for_action("MEDIUM", "TYPE") == ("before", "after")
    assert visual_confirmation_passed([before, after], required_stages=("before", "after"))


def test_epoch_seal_is_fossil_record_and_pqc_ready(tmp_path):
    (tmp_path / "identity_continuity.jsonl").write_text('{"kind":"IDENTITY"}\n', encoding="utf-8")
    (tmp_path / "regulatory_genome.jsonl").write_text('{"kind":"GENOME","v":1}\n', encoding="utf-8")

    row = seal_epoch(
        epoch_id=1,
        root=tmp_path,
        repo_root=tmp_path,
        ledger_names=("identity_continuity.jsonl", "regulatory_genome.jsonl"),
        owner_checkpoint="owner-ok",
        now=123.0,
    )

    assert row["truth_label"] == "EPOCH_SEAL"
    assert row["fossil_record_hash_alg"] == "SHA3-512"
    assert row["pq_signature_status"] == "pqc_ready_metadata_only"
    assert verify_epoch_seal(row)
    assert (tmp_path / "epoch_seals.jsonl").exists()


def test_revival_proof_references_latest_epoch(tmp_path):
    seal = seal_epoch(
        epoch_id=1,
        root=tmp_path,
        repo_root=tmp_path,
        ledger_names=("missing.jsonl",),
        now=123.0,
    )
    proof = build_revival_proof(root=tmp_path, revival_score=0.87, now=124.0)

    assert proof["truth_label"] == "REVIVAL_PROOF"
    assert proof["last_shutdown_hash"] == seal["fossil_record_hash"]
    assert proof["revival_score"] == 0.87
    assert proof["pq_signature_status"] == "pqc_ready_metadata_only"
