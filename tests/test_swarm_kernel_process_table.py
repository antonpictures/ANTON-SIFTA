import json
import time

import pytest

import System.swarm_kernel_process_table as kernel_module
from System.swarm_kernel_process_table import (
    KernelBudgetError,
    KernelProcessTable,
    KernelRegistrationError,
    OrganProcess,
)


def _process(pid: str = "desktop_body_001", ring: int = 1, location: str = "desk") -> OrganProcess:
    return OrganProcess(
        pid=pid,
        organ_id="sifta_os_desktop",
        ring=ring,
        health=1.0,
        stgm_balance=0.0,
        current_job="boot",
        last_receipt_id="",
        failure_count=0,
        last_heartbeat_ts=time.time(),
        location=location,
        bodies_present=["george", "alice_body"],
        metadata={"kind": "desktop"},
    )


def test_register_writes_snapshot_and_receipt(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)

    pid = table.register(_process(), receipt_id="boot_receipt_1")

    assert pid == "desktop_body_001"
    assert (tmp_path / "kernel_process_table.json").exists()
    assert (tmp_path / "kernel_process_table.jsonl").exists()
    snapshot = json.loads((tmp_path / "kernel_process_table.json").read_text(encoding="utf-8"))
    assert snapshot["truth_label"] == "SIFTA_KERNEL_PROCESS_TABLE_V1"
    assert snapshot["processes"][pid]["organ_id"] == "sifta_os_desktop"
    assert snapshot["processes"][pid]["ring"] == 1
    receipts = (tmp_path / "kernel_process_table.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(receipts) == 1
    assert json.loads(receipts[0])["action"] == "register"


def test_register_receipt_carries_signature_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(
        kernel_module,
        "_sign_receipt_payload",
        lambda payload: {
            "signature_alg": "Ed25519",
            "signature_payload": payload,
            "signature_hex": "a" * 128,
            "signing_serial": "GTH4921YP3",
        },
    )
    table = KernelProcessTable(state_root=tmp_path)

    table.register(_process(), receipt_id="signed_boot")

    receipt = json.loads((tmp_path / "kernel_process_table.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert receipt["signature_alg"] == "Ed25519"
    assert receipt["signature_hex"] == "a" * 128
    assert receipt["signing_serial"] == "GTH4921YP3"


def test_heartbeat_updates_budget_grounding_and_health(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process())

    proc = table.heartbeat(
        "desktop_body_001",
        health=0.82,
        stgm_delta=2.5,
        current_job="vision_tick",
        location="desk",
        bodies_present=["george"],
        receipt_id="vision_receipt",
    )

    assert proc.health == 0.82
    assert proc.stgm_balance == 2.5
    assert proc.current_job == "vision_tick"
    assert proc.bodies_present == ["george"]
    assert proc.last_receipt_id == "vision_receipt"
    assert table.aggregate_organism_health() == 0.82


def test_heartbeat_receipt_has_canonical_type_score_and_signature(tmp_path, monkeypatch):
    monkeypatch.setattr(
        kernel_module,
        "_sign_receipt_payload",
        lambda payload: {
            "signature_alg": "Ed25519",
            "signature_payload": payload,
            "signature_hex": "b" * 128,
            "signing_serial": "GTH4921YP3",
        },
    )
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process())

    table.heartbeat(
        "desktop_body_001",
        stgm_delta=0.5,
        receipt_id="heartbeat_receipt",
        metadata={"tokens_per_sec": "12.5", "latency_ms": "80.0", "used_mtp": "true"},
    )

    rows = [
        json.loads(line)
        for line in (tmp_path / "kernel_process_table.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    heartbeat = rows[-1]
    assert heartbeat["type"] == "KERNEL_HEARTBEAT"
    assert isinstance(heartbeat["score"], float)
    assert heartbeat["signature"] == "b" * 128
    assert heartbeat["tokens_per_sec"] == 12.5
    assert heartbeat["latency_ms"] == 80.0
    assert heartbeat["used_mtp"] is True


def test_unregistered_heartbeat_is_rejected(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)

    with pytest.raises(KernelRegistrationError):
        table.heartbeat("missing", health=1.0)


def test_invalid_ring_is_rejected(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)

    with pytest.raises(KernelRegistrationError):
        table.register(_process(ring=7))


def test_budget_enforcement_blocks_negative_spend(tmp_path):
    table = KernelProcessTable(state_root=tmp_path, enforce_budget=True)
    table.register(_process())

    with pytest.raises(KernelBudgetError):
        table.heartbeat("desktop_body_001", stgm_delta=-1.0)


def test_missing_physical_grounding_decays_health_and_flags_metadata(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    proc = _process("ungrounded", ring=2)
    proc.location = "unknown"
    proc.bodies_present = []
    table.register(proc)

    updated = table.heartbeat("ungrounded", health=1.0, current_job="agent_tick")

    assert updated.health == 0.85
    assert updated.failure_count == 1
    assert updated.metadata["physical_grounding_status"] == "missing_decay"
    assert "ungrounded" in {p.pid for p in table.list_unhealthy()}


def test_negative_stgm_contributor_gets_health_penalty_and_unhealthy_flag(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process("spender", ring=2))

    updated = table.heartbeat("spender", health=1.0, stgm_delta=-6.0)

    assert updated.stgm_balance == -6.0
    assert updated.health == 0.65
    assert updated.failure_count == 1
    assert updated.metadata["stgm_budget_status"] == "negative_contributor"
    assert updated.metadata["stgm_negative_spend_penalty"] == str(kernel_module.NEGATIVE_SPEND_HEALTH_PENALTY)
    assert "spender" in {p.pid for p in table.list_unhealthy()}


def test_severe_negative_stgm_blocks_budget_and_deepens_penalty(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process("severe", ring=2))

    updated = table.heartbeat("severe", health=1.0, stgm_delta=-13.0)

    assert updated.stgm_balance == -13.0
    assert updated.health == 0.4
    assert updated.metadata["stgm_status"] == "severe_negative_contributor"
    assert table.budget_state_for("severe") == "BLOCK"


def test_budget_state_throttles_unhealthy_process(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process())
    table.heartbeat("desktop_body_001", health=0.2, failure_delta=1)

    assert table.budget_state_for("desktop_body_001") == "THROTTLE"


def test_list_unhealthy_includes_low_health_and_terminated(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process("healthy", ring=1))
    table.register(_process("sick", ring=2))
    table.heartbeat("sick", health=0.4, failure_delta=1)
    table.terminate("healthy", reason="test shutdown")

    unhealthy = {p.pid for p in table.list_unhealthy()}

    assert unhealthy == {"healthy", "sick"}
    assert [p.pid for p in table.list_by_ring(2)] == ["sick"]


def test_snapshot_reload_preserves_existing_process_balance(tmp_path):
    first = KernelProcessTable(state_root=tmp_path)
    first.register(_process())
    first.heartbeat("desktop_body_001", stgm_delta=3.0, current_job="first_run")

    second = KernelProcessTable(state_root=tmp_path)
    proc = second.get("desktop_body_001")

    assert proc is not None
    assert proc.stgm_balance == 3.0
    assert proc.current_job == "first_run"


def test_re_register_does_not_reset_stgm_balance(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process())
    table.heartbeat("desktop_body_001", stgm_delta=2.0)

    table.register(_process())

    assert table.get("desktop_body_001").stgm_balance == 2.0


def test_heartbeat_uses_recent_e35_physical_context(tmp_path):
    now = time.time()
    (tmp_path / "face_detection_events.jsonl").write_text(
        json.dumps(
            {
                "ts": now,
                "event": "FACE_DETECTION",
                "body_id": "george",
                "distance_m": 0.7,
                "confidence": 0.92,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "unified_stigmergic_field.jsonl").write_text(
        json.dumps(
            {
                "ts": now,
                "kind": "UNIFIED_FIELD_SEGMENT_V1",
                "location_segment": "desk",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process(location="unknown", ring=1))

    proc = table.heartbeat("desktop_body_001", current_job="physical_tick")

    assert proc.location == "desk"
    assert "george" in proc.bodies_present
    assert proc.metadata["physical_context_source"] == "E35_physical_space_report"


def test_jsonl_tail_reader_reads_from_eof_without_full_ledger_scan(monkeypatch):
    class TrackingBinaryFile:
        def __init__(self, data: bytes):
            self.data = data
            self.pos = 0
            self.bytes_read = 0

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def seek(self, offset: int, whence: int = 0):
            if whence == 2:
                self.pos = len(self.data) + offset
            elif whence == 1:
                self.pos += offset
            else:
                self.pos = offset

        def tell(self) -> int:
            return self.pos

        def read(self, size: int = -1) -> bytes:
            if size < 0:
                size = len(self.data) - self.pos
            end = min(len(self.data), self.pos + size)
            chunk = self.data[self.pos:end]
            self.pos = end
            self.bytes_read += len(chunk)
            return chunk

    class FakePath:
        def __init__(self, file_obj: TrackingBinaryFile):
            self.file_obj = file_obj

        def exists(self) -> bool:
            return True

        def open(self, mode: str):
            assert mode == "rb"
            self.file_obj.pos = 0
            return self.file_obj

    monkeypatch.setattr(kernel_module, "TAIL_READ_CHUNK_BYTES", 128)
    monkeypatch.setattr(kernel_module, "TAIL_READ_MAX_BYTES", 1024)
    old_rows = b"".join(
        json.dumps({"seq": i, "old": "x" * 80}).encode("utf-8") + b"\n"
        for i in range(5000)
    )
    new_rows = b"".join(
        json.dumps({"seq": i}).encode("utf-8") + b"\n"
        for i in range(5000, 5005)
    )
    backing = TrackingBinaryFile(old_rows + new_rows)

    rows = kernel_module._read_jsonl_tail(FakePath(backing), n=5)

    assert [row["seq"] for row in rows] == [5000, 5001, 5002, 5003, 5004]
    assert backing.bytes_read < len(backing.data) * 0.05


def test_self_maintenance_tick_flags_repair_and_receipts(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process("spender", ring=2))
    table.heartbeat("spender", health=1.0, stgm_delta=-6.0)

    actions = table.self_maintenance_tick(max_actions=1)

    spender = table.get("spender")
    kernel_proc = table.get("kernel:self_maintenance")
    receipts = [
        json.loads(line)
        for line in (tmp_path / "kernel_process_table.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert actions == 1
    assert spender.metadata["repair_needed"] == "true"
    assert spender.metadata["repair_reason"] == "negative_stgm_contributor"
    assert float(spender.metadata["repair_priority"]) > 0.0
    assert spender.metadata["repair_budget_stgm"] == "0.001000"
    assert kernel_proc is not None
    assert kernel_proc.metadata["last_self_maintenance_actions"] == "1"
    maintenance = next(row for row in receipts if row["action"] == "self_maintenance_tick")
    assert maintenance["type"] == "KERNEL_SELF_MAINTENANCE"
    assert isinstance(maintenance["score"], float)


def test_self_maintenance_tick_respects_max_actions(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    for pid in ("bad1", "bad2"):
        table.register(_process(pid, ring=2))
        table.heartbeat(pid, health=1.0, stgm_delta=-6.0)

    actions = table.self_maintenance_tick(max_actions=1)

    repaired = [
        pid
        for pid in ("bad1", "bad2")
        if table.get(pid).metadata.get("repair_needed") == "true"
    ]
    assert actions == 1
    assert len(repaired) == 1


def test_scheduler_utility_applies_repair_bonus_scout_floor_and_missing_pid(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    scout = _process("scout", ring=2)
    scout.metadata["scout_mode"] = "true"
    scout.current_job = "repair scout pass"
    table.register(scout)
    table.heartbeat("scout", health=0.3, location="desk", bodies_present=["alice_body"])

    score = table.scheduler_utility(
        "scout",
        evidence_gain=-1.0,
        stgm_delta=-1.0,
        thermal=2.0,
        interrupt_risk=1.0,
    )

    assert score == 0.05
    assert table.scheduler_utility("missing") == -999.0


def test_self_maintenance_tick_feeds_ambient_context_into_scheduler(tmp_path):
    now = time.time()
    diary = tmp_path / "episodic_diary.jsonl"
    rows = [
        {
            "ts": now - 20,
            "truth_label": "AMBIENT_WORLD_DIARY_TRACE_V1",
            "event_type": "ambient_world_observation",
            "route": "ambient_media",
            "reason": "owner_declared_background_phone_call",
            "summary": "phone call kept silent",
            "text_preview": "I can call back after the meeting.",
        },
        {
            "ts": now - 10,
            "truth_label": "AMBIENT_WORLD_DIARY_TRACE_V1",
            "event_type": "ambient_world_observation",
            "route": "ambient_media",
            "reason": "nearfield_voice_likely owner_voice",
            "summary": "recent owner voice detected in ambient lane",
            "text_preview": "Alice, hold that context.",
        },
    ]
    diary.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    table = KernelProcessTable(state_root=tmp_path)
    owner_proc = _process("owner_scheduler", ring=1)
    owner_proc.current_job = "owner task planning"
    neutral_proc = _process("batch_worker", ring=2)
    neutral_proc.current_job = "batch background pass"
    table.register(owner_proc)
    table.register(neutral_proc)

    table.self_maintenance_tick(max_actions=0)

    kernel_proc = table.get("kernel:self_maintenance")
    context = json.loads(kernel_proc.metadata["current_ambient_context"])
    assert context["active"] is True
    assert context["phone_call_active"] is True
    assert context["high_ambient_noise"] is True
    assert context["recent_owner_voice"] is True
    assert context["recent_owner_voice_detected"] is True
    assert context["dominant_activity"] == "conversation"
    assert context["sampling_policy"] == "engage"
    assert context["salience_score"] > 0.5
    assert context["novelty_score"] > 0.0
    assert context["last_update_ts"] == context["latest_ts"]
    assert kernel_proc.metadata["ambient_context_query_hint"] == "ambient_noise_or_phone_call"
    assert table.scheduler_utility("owner_scheduler", evidence_gain=1.0) > table.scheduler_utility(
        "batch_worker",
        evidence_gain=1.0,
    )


def test_sys_spend_writes_receipt_and_rejects_ring2(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process("economy", ring=1))

    rid = table.sys_spend("economy", 0.125, "unit_test")

    rows = [
        json.loads(line)
        for line in (tmp_path / "kernel_process_table.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert rid.startswith("receipt_")
    assert table.get("economy").stgm_balance == -0.125
    assert any(row["trace_id"] == rid and row["action"] == "heartbeat" for row in rows)

    table.register(_process("arm", ring=2))
    with pytest.raises(PermissionError):
        table.sys_spend("arm", 0.01, "forbidden")


def test_sys_schedule_is_ring1_or_kernel_only(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process("scheduler", ring=1))
    table.register(_process("talk_ui", ring=3))

    rid = table.sys_schedule("scheduler", {"task": "journal tick"})

    assert rid.startswith("receipt_")
    assert table.get("scheduler").metadata["last_schedule_receipt_id"] == rid
    with pytest.raises(PermissionError):
        table.sys_schedule("talk_ui", {"task": "bypass"})


def test_enforce_action_blocks_ring3_effector(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process("router", ring=2))
    table.register(_process("ui", ring=3))

    assert table.enforce_action("router", "effector", requested_spend=0.01)["state"] == "ALLOW"
    with pytest.raises(PermissionError):
        table.enforce_action("ui", "effector", requested_spend=0.01)


def test_check_ring_helper_covers_registration_and_syscall_limits(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process("kernel", ring=0))
    table.register(_process("router", ring=2))
    table.register(_process("ui", ring=3))

    table._check_ring("kernel", "kernel_maintenance")
    table._check_ring("router", "effector")

    with pytest.raises(PermissionError):
        table._check_ring("router", "spend")
    with pytest.raises(PermissionError):
        table._check_ring("ui", "effector")
    with pytest.raises(KernelRegistrationError):
        table._check_ring("ghost", "effector")


def test_sys_effector_request_allows_ring2_and_spends_visible_stgm(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process("router", ring=2))

    gate = table.sys_effector_request(
        "router",
        "physical_effector_demo",
        0.03,
        evidence_gain=0.7,
        stgm_delta=0.2,
        thermal=0.0,
        interrupt_risk=0.0,
    )

    rows = [
        json.loads(line)
        for line in (tmp_path / "kernel_process_table.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert gate["allow"] is True
    assert gate["decision"] == "ALLOW"
    assert gate["receipt_id"].startswith("receipt_")
    assert table.get("router").stgm_balance == pytest.approx(-0.03)
    assert any(
        row["trace_id"] == gate["receipt_id"]
        and row["current_job"] == "effector_request:physical_effector_demo:ALLOW"
        and row["extra"]["stgm_delta"] == -0.03
        for row in rows
    )


def test_sys_effector_request_read_only_grok_lane_has_final_receipt_fields(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process("router", ring=2))

    gate = table.sys_effector_request(
        "router",
        "matrix_pty",
        0.25,
        evidence_gain=0.92,
        stgm_delta=-0.25,
        thermal=0.0,
        interrupt_risk=0.01,
        metadata={
            "clearance_lane": "READ_ONLY_GROK_DELEGATION",
            "effector_decision": "SHOULD_NOT_SURVIVE_METADATA_MERGE",
            "read_only_grok_delegation": "true",
            "tool": "matrix_pty",
        },
    )

    rows = [
        json.loads(line)
        for line in (tmp_path / "kernel_process_table.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    receipt = next(row for row in rows if row["trace_id"] == gate["receipt_id"])
    assert gate["allow"] is True
    assert gate["decision"] == "ALLOW"
    assert receipt["current_job"] == "effector_request:matrix_pty:ALLOW"
    proc = table.get("router")
    assert proc.metadata["effector_decision"] == "ALLOW"
    assert proc.metadata["clearance_lane"] == "READ_ONLY_GROK_DELEGATION"
    assert "safe read-only inspection" in proc.metadata["lane_note"]


def test_sys_effector_request_throttles_low_utility_without_spend(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process("router", ring=2))

    gate = table.sys_effector_request(
        "router",
        "too_expensive",
        0.03,
        evidence_gain=0.0,
        stgm_delta=-1.0,
        thermal=2.0,
        interrupt_risk=1.0,
    )

    assert gate["allow"] is False
    assert gate["decision"] == "THROTTLE"
    assert table.get("router").stgm_balance == pytest.approx(0.0)


def test_sys_memory_query_returns_filtered_process_rows(tmp_path):
    table = KernelProcessTable(state_root=tmp_path)
    table.register(_process("core", ring=1))
    table.register(_process("arm", ring=2))

    rows = table.sys_memory_query({"ring": 2})

    assert [row["pid"] for row in rows] == ["arm"]
