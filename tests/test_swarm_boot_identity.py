"""D1 behavioral tests: boot identity, topology, resource probes, capability loss.

Every test injects readings or a temporary state root: nothing here touches the live
`.sifta_state`, the real network, or the machine's real disk usage.
"""
from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from System import swarm_boot_identity as B
from System import swarm_adaptive_contracts as C

REPO = Path(__file__).resolve().parents[1]

MAC_READINGS = {
    "storage": {"free_gb": 361.5, "total_gb": 994.6, "unit": "GB"},
    "memory": {"available_gb": 13.2, "unit": "GB"},
    "thermal": None,
    "battery": {"fraction": 1.0, "on_ac": True, "unit": "fraction"},
    "network": True,
    "model_endpoint": True,
}

DELL_READINGS = {
    "storage": {"free_gb": 12.5, "total_gb": 100.0, "unit": "GB"},
    "memory": {"available_gb": 3.2, "unit": "GB"},
    "thermal": {"celsius": 47.5, "unit": "C"},
    "battery": {"fraction": 0.62, "on_ac": False, "unit": "fraction"},
    "network": False,
    "model_endpoint": None,
}

DRIVE = {"name": "drive_forward", "preconditions": ["network"], "adapter_id": "rvr1"}
SPEAK = {"name": "speak", "adapter_id": "voice"}


def _snapshot(tmp_path, readings, actions=(SPEAK,), sensors=(), **kw):
    return B.capability_snapshot(body_id="body_test", node_id="node_test",
                                 actions=list(actions), sensors=list(sensors),
                                 readings=readings, state_root=tmp_path, **kw)


# ── platform / topology ────────────────────────────────────────────────────────

def test_platform_id_is_a_known_token():
    assert B.platform_id() in {"macos", "linux", "linux_pi", "linux_wsl", "windows", "unknown"}


def test_headless_linux_without_display_is_true():
    assert B.is_headless(env={}, pid="linux") is True


def test_linux_with_display_env_is_not_headless():
    assert B.is_headless(env={"DISPLAY": ":0"}, pid="linux") is False
    assert B.is_headless(env={"WAYLAND_DISPLAY": "wayland-0"}, pid="linux") is False


def test_macos_without_ssh_is_not_headless():
    assert B.is_headless(env={}, pid="macos") is False


def test_unknown_platform_headless_is_undetermined_not_false():
    assert B.is_headless(env={}, pid="windows") is None


def test_familiar_mac_and_unfamiliar_dell_have_different_topologies():
    mac = B.topology_facts(readings=MAC_READINGS)
    dell = B.topology_facts(readings=DELL_READINGS)
    assert mac["roles"] != dell["roles"]
    assert B.topology_id(facts=mac) != B.topology_id(facts=dell)


def test_topology_id_is_stable_for_identical_evidence():
    first = B.topology_id(readings=MAC_READINGS)
    assert first == B.topology_id(readings=MAC_READINGS)
    assert first.startswith("topo:") and len(first) == len("topo:") + 32


def test_topology_facts_report_unknown_as_explicit_null():
    facts = B.topology_facts(readings={})
    assert facts["machine"] is None or isinstance(facts["machine"], str)
    assert isinstance(facts["roles"], list)
    assert facts["roles"] == [] or all(isinstance(r, str) for r in facts["roles"])


# ── probes ─────────────────────────────────────────────────────────────────────

def test_a_raising_probe_reports_unknown_and_never_raises():
    def boom():
        raise RuntimeError("sensor detached")
    readings = B.run_probes(probes={"thermal": boom})
    assert readings["thermal"] is None


def test_probes_are_nullary_so_any_subsystem_can_be_faked():
    readings = B.run_probes(probes={"battery": lambda: {"fraction": 0.25, "on_ac": False,
                                                        "unit": "fraction"}})
    assert readings["battery"]["fraction"] == 0.25
    assert set(readings) == set(B.DEFAULT_PROBERS)


def test_resource_estimates_contain_only_measured_resources():
    snap = _snapshot(Path("/tmp/d1_unused"), DELL_READINGS).to_dict()
    resources = {r["resource"] for r in snap["resource_estimates"]}
    assert resources == {"disk_free", "disk_total", "memory_available", "cpu_temperature",
                         "battery"}
    assert all(isinstance(r["value"], float) for r in snap["resource_estimates"])


def test_unmeasurable_resources_do_not_appear_with_invented_values():
    snap = _snapshot(Path("/tmp/d1_unused"), MAC_READINGS).to_dict()
    resources = {r["resource"] for r in snap["resource_estimates"]}
    assert "cpu_temperature" not in resources  # thermal probe returned nothing


# ── boot identity ──────────────────────────────────────────────────────────────

def test_first_boot_has_sequence_one_and_no_previous(tmp_path):
    row = B.start_boot(state_root=tmp_path, readings=MAC_READINGS, process_boot_id=str(uuid.uuid4()))
    assert row["sequence"] == 1
    assert row["previous_boot_id"] is None
    assert row["topology_id"].startswith("topo:")


def test_restart_increments_sequence_and_links_the_previous_boot(tmp_path):
    first = B.start_boot(state_root=tmp_path, readings=MAC_READINGS, process_boot_id="boot-a")
    second = B.start_boot(state_root=tmp_path, readings=MAC_READINGS, process_boot_id="boot-b")
    assert (first["sequence"], second["sequence"]) == (1, 2)
    assert second["previous_boot_id"] == "boot-a"
    assert first["boot_id"] != second["boot_id"]


def test_boot_ledger_is_append_only_jsonl(tmp_path):
    B.start_boot(state_root=tmp_path, readings=MAC_READINGS, process_boot_id="boot-a")
    B.start_boot(state_root=tmp_path, readings=MAC_READINGS, process_boot_id="boot-b")
    rows = [json.loads(line) for line in
            (tmp_path / B.BOOT_LEDGER_NAME).read_text().splitlines() if line.strip()]
    assert [r["boot_id"] for r in rows] == ["boot-a", "boot-b"]


def test_current_boot_reads_back_the_recorded_row(tmp_path):
    started = B.start_boot(state_root=tmp_path, readings=MAC_READINGS, process_boot_id="boot-a")
    assert B.current_boot(state_root=tmp_path)["boot_id"] == started["boot_id"]


def test_boot_staleness_is_detected_across_a_restart(tmp_path):
    B.start_boot(state_root=tmp_path, readings=MAC_READINGS, process_boot_id="boot-a")
    assert B.boot_is_stale("boot-a", state_root=tmp_path) is False
    B.start_boot(state_root=tmp_path, readings=MAC_READINGS, process_boot_id="boot-b")
    assert B.boot_is_stale("boot-a", state_root=tmp_path) is True


# ── capability loss and recovery ──────────────────────────────────────────────

def test_lost_capability_blocks_the_next_planning_step_with_a_reason(tmp_path):
    B.mark_lost("network", reason_code="BLOCKED", detail="wifi down", state_root=tmp_path)
    view = B.planning_view([DRIVE, SPEAK], state_root=tmp_path, readings=MAC_READINGS)
    assert [a["name"] for a in view["available"]] == ["speak"]
    assert view["unavailable"] == [{"name": "drive_forward", "reason_code": "BLOCKED",
                                    "detail": "unmet precondition: network",
                                    "blocked_by": ["network"]}]


def test_recovery_restores_the_action_at_the_next_planning_step(tmp_path):
    B.mark_lost("network", reason_code="BLOCKED", state_root=tmp_path)
    B.mark_recovered("network", detail="wifi back", state_root=tmp_path)
    view = B.planning_view([DRIVE, SPEAK], state_root=tmp_path, readings=MAC_READINGS)
    assert sorted(a["name"] for a in view["available"]) == ["drive_forward", "speak"]
    assert view["unavailable"] == []


def test_unfamiliar_body_does_not_assume_an_unreported_capability(tmp_path):
    view = B.planning_view([{"name": "grasp", "preconditions": ["manipulator"]}],
                           state_root=tmp_path, readings=MAC_READINGS)
    assert view["available"] == []
    assert view["unavailable"][0]["reason_code"] == "UNSUPPORTED"


def test_lost_sensor_freshness_becomes_unknown_in_the_snapshot(tmp_path):
    sensor = {"sensor_id": "lidar", "modality": "range", "coverage": "room",
              "freshness_ms": 120, "source_id": "rvr1"}
    fresh = _snapshot(tmp_path, MAC_READINGS, sensors=[sensor]).to_dict()
    assert fresh["sensor_coverage"][0]["freshness_ms"] == 120

    B.mark_lost("lidar", reason_code="SENSOR_STALE", detail="detached", state_root=tmp_path)
    stale = _snapshot(tmp_path, MAC_READINGS, sensors=[sensor]).to_dict()
    assert stale["sensor_coverage"][0]["freshness_ms"] is None
    assert stale["sensor_coverage"][0]["coverage"] is None
    assert ("lidar", "SENSOR_STALE") in [(u["name"], u["reason_code"])
                                        for u in stale["unavailable_capabilities"]]


def test_capability_health_survives_a_restart_because_it_is_a_ledger(tmp_path):
    B.mark_lost("arm_tool", reason_code="BLOCKED", state_root=tmp_path)
    B.start_boot(state_root=tmp_path, readings=MAC_READINGS, process_boot_id="boot-b")
    health = B.capability_health(state_root=tmp_path, readings=MAC_READINGS)
    assert health["arm_tool"]["state"] == "lost"


def test_capability_health_ages_are_never_negative(tmp_path):
    B.mark_lost("network", reason_code="BLOCKED", state_root=tmp_path)
    health = B.capability_health(state_root=tmp_path, readings=MAC_READINGS)
    assert health["network"]["age_ms"] >= 0


def test_unknown_capability_event_kind_is_refused(tmp_path):
    with pytest.raises(ValueError):
        B.record_capability_event("exploded", "network", state_root=tmp_path)


# ── frozen contract compliance ────────────────────────────────────────────────

def test_snapshot_validates_against_the_frozen_c0_contract(tmp_path):
    snap = _snapshot(tmp_path, MAC_READINGS, actions=(DRIVE, SPEAK))
    assert snap.schema_version == C.RECORDS_SCHEMA_VERSION
    assert snap.verify() is None
    again = C.CapabilitySnapshot.from_dict(json.loads(snap.to_json()))
    assert again.to_dict() == snap.to_dict()


def test_snapshot_carries_boot_topology_and_explicit_freshness(tmp_path):
    snap = _snapshot(tmp_path, MAC_READINGS).to_dict()
    assert snap["topology_revision"] == B.TOPOLOGY_SCHEMA_VERSION
    assert uuid.UUID(snap["boot_id"])
    assert uuid.UUID(snap["snapshot_id"])
    assert snap["hardware"]["platform_id"] == B.platform_id()
    assert snap["hardware"]["topology_id"].startswith("topo:")


def test_undetermined_network_is_reported_as_unknown_not_offline(tmp_path):
    readings = dict(MAC_READINGS, network=None)
    snap = _snapshot(tmp_path, readings).to_dict()
    assert snap["os_facts"]["network"] == "unknown"
    assert ("network", "BLOCKED") in [(u["name"], u["reason_code"])
                                      for u in snap["unavailable_capabilities"]]


def test_no_network_body_blocks_its_dependent_action(tmp_path):
    snap = _snapshot(tmp_path, DELL_READINGS, actions=(DRIVE, SPEAK)).to_dict()
    assert [a["name"] for a in snap["available_actions"]] == ["speak"]
    assert snap["os_facts"]["network"] == "unreachable"
    assert ("network", "BLOCKED") in [(u["name"], u["reason_code"])
                                      for u in snap["unavailable_capabilities"]]


def test_snapshot_available_actions_are_registry_shaped(tmp_path):
    snap = _snapshot(tmp_path, MAC_READINGS, actions=(DRIVE,)).to_dict()
    action = snap["available_actions"][0]
    assert set(action) == {"name", "input_schema", "output_schema", "preconditions", "adapter_id"}
    assert action["adapter_id"] == "rvr1"


def test_body_with_no_actions_still_emits_a_valid_snapshot(tmp_path):
    snap = _snapshot(tmp_path, {"storage": None, "memory": None, "thermal": None,
                                "battery": None, "network": None, "model_endpoint": None},
                     actions=())
    assert snap.to_dict()["available_actions"] == []
    assert snap.verify() is None


def test_summary_lines_name_the_lost_capability(tmp_path):
    B.mark_lost("rvr1", reason_code="BLOCKED", detail="link down", state_root=tmp_path)
    snap = _snapshot(tmp_path, MAC_READINGS)
    text = "\n".join(B.summary_lines(snap))
    assert "topo:" in text and "rvr1" in text and "BLOCKED" in text


# ── portability + CLI ─────────────────────────────────────────────────────────

def test_module_core_imports_no_gui_or_macos_only_module():
    source = (REPO / "System" / "swarm_boot_identity.py").read_text(encoding="utf-8")
    for banned in ("PyQt", "PySide", "AppKit", "Quartz", "import objc"):
        assert banned not in source.replace("No Qt, no AppKit", "")


def test_cli_emits_a_contract_valid_snapshot(tmp_path):
    out = subprocess.run(
        [sys.executable, "-m", "System.swarm_boot_identity", "--json",
         "--state-root", str(tmp_path), "--body-id", "body_cli", "--node-id", "node_cli",
         "--actions", json.dumps(["network", "speak"])],
        cwd=REPO, capture_output=True, text=True, env={"SIFTA_STATE_DIR": str(tmp_path),
                                                       "PATH": "/usr/bin:/bin"})
    assert out.returncode == 0, out.stderr
    snap = C.CapabilitySnapshot.from_dict(json.loads(out.stdout.strip()))
    assert snap.body_id == "body_cli"
    assert snap.verify() is None


def test_cli_human_output_is_a_census_not_a_wall(tmp_path):
    out = subprocess.run(
        [sys.executable, "-m", "System.swarm_boot_identity", "--state-root", str(tmp_path)],
        cwd=REPO, capture_output=True, text=True,
        env={"SIFTA_STATE_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"})
    assert out.returncode == 0, out.stderr
    assert "body" in out.stdout and "topology" in out.stdout
    assert len(out.stdout.splitlines()) < 40


# ── existing-organ integration (census + capability registry) ────────────────

def test_boot_census_reports_body_topology_and_losses(tmp_path):
    from System import swarm_boot_census as BC

    B.start_boot(state_root=tmp_path, readings=MAC_READINGS)
    B.mark_lost("thermal", reason_code="UNSUPPORTED", state_root=tmp_path)
    census = BC.boot_census(state_dir=tmp_path, probe_body=False, probe_identity=False)
    assert census["topology_id"].startswith("topo:")
    # the census probes the live body, so roles come from this machine, never from fixtures
    assert census["body_roles"] and all(isinstance(r, str) for r in census["body_roles"])
    assert "thermal" in census["unavailable_capabilities"]
    lines = "\n".join(BC.boot_census_lines(census))
    assert "🧭" in lines or "topo:" in lines


def test_boot_census_without_a_recorded_boot_stays_silent_about_identity(tmp_path):
    from System import swarm_boot_census as BC

    census = BC.boot_census(state_dir=tmp_path, probe_body=False, probe_identity=False)
    assert census["boot_id"] is None
    assert not any("topo:" in line for line in BC.boot_census_lines(census))


def test_capability_registry_withholds_a_lost_organ(tmp_path):
    from System import swarm_capability_registry as R

    cap = R.Capability(name="rvr1_drive", description="drive", backing={"tool": "rvr1"})
    ok = R.Capability(name="speak", description="speak", backing={"tool": "voice"})

    healthy = R.capability_availability_gate([cap, ok], state_root=tmp_path)
    assert [c.name for c in healthy["available"]] == ["rvr1_drive", "speak"]

    B.mark_lost("rvr1", reason_code="BLOCKED", detail="link down", state_root=tmp_path)
    gated = R.capability_availability_gate([cap, ok], state_root=tmp_path)
    assert [c.name for c in gated["available"]] == ["speak"]
    assert gated["unavailable"][0].backing["blocked"]["reason_code"] == "BLOCKED"

    B.mark_recovered("rvr1", state_root=tmp_path)
    restored = R.capability_availability_gate([cap, ok], state_root=tmp_path)
    assert [c.name for c in restored["available"]] == ["rvr1_drive", "speak"]
