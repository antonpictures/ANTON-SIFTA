import json
import time

from System.swarm_body_attention_policy import (
    BodyEconomy,
    TerminalActivity,
    collect_terminal_activity,
    decide_attention_policy,
    summary_for_alice,
)


def _append(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_active_terminal_with_nominal_resources_keeps_dual_attention():
    policy = decide_attention_policy(
        terminal=TerminalActivity(active=True, action="agent_arm_live", focused_cli="claude"),
        economy=BodyEconomy(thermal_warning_level=0, power_source="AC Power", memory_pressure=0.42),
    )

    assert policy.mode == "dual_terminal_world_attention"
    assert policy.terminal_focus == "primary"
    assert policy.real_world_lane == "normal_safety_watch"
    assert "resources_allow_dual_attention" in policy.reasons


def test_active_terminal_with_thermal_pressure_prioritizes_terminal_without_blinding_safety():
    policy = decide_attention_policy(
        terminal=TerminalActivity(active=True, action="grok_framebuffer_snapshot", focused_cli="grok"),
        economy=BodyEconomy(
            thermal_warning_level=3,
            performance_warning_level=1,
            power_source="AC Power",
            memory_pressure=0.55,
        ),
    )

    assert policy.mode == "terminal_priority_conserve"
    assert policy.terminal_focus == "primary"
    assert policy.real_world_lane == "reduced_safety_watch"
    assert "thermal_level_3" in policy.reasons
    assert "performance_warning_1" in policy.reasons


def test_low_battery_without_terminal_conserves_world_attention():
    policy = decide_attention_policy(
        terminal=TerminalActivity(active=False),
        economy=BodyEconomy(power_source="Battery Power", charge_pct=12, memory_pressure=0.2),
    )

    assert policy.mode == "body_conserve_world_attention"
    assert policy.terminal_focus == "idle"
    assert policy.real_world_lane == "reduced_safety_watch"
    assert "battery_12%" in policy.reasons


def test_terminal_activity_reads_live_trace_and_ignores_done_rows(tmp_path):
    now = time.time()
    trace = tmp_path / "matrix_terminal_process_trace.jsonl"
    _append(trace, {"ts": now - 4, "action": "agent_arm_live", "focused_cli": "claude", "text": "coding..."})
    active = collect_terminal_activity(state_dir=tmp_path, now=now)
    assert active.active
    assert active.focused_cli == "claude"

    _append(trace, {"ts": now - 1, "action": "agent_arm_live_done", "focused_cli": "claude", "text": "finished"})
    done = collect_terminal_activity(state_dir=tmp_path, now=now)
    assert not done.active
    assert done.action == "agent_arm_live_done"


def test_summary_surfaces_body_economy_policy_and_diary(tmp_path):
    now = time.time()
    _append(
        tmp_path / "matrix_terminal_process_trace.jsonl",
        {"ts": now, "action": "agent_arm_heartbeat", "focused_cli": "codex", "text": "20s elapsed"},
    )
    (tmp_path / "thermal_cortex_state.json").write_text(
        json.dumps({"thermal_warning_level": 2, "thermal_warning_name": "MODERATE"}),
        encoding="utf-8",
    )
    (tmp_path / "energy_cortex_state.json").write_text(
        json.dumps({"power_source": "AC Power", "charge_pct": 88, "low_power_mode": False}),
        encoding="utf-8",
    )
    (tmp_path / "body_resource_state.json").write_text(
        json.dumps({"memory_pressure": 0.2}),
        encoding="utf-8",
    )

    summary = summary_for_alice(state_dir=tmp_path, now=now)

    assert "BODY ECONOMY ATTENTION:" in summary
    assert "mode=terminal_priority_conserve" in summary
    assert "terminal_stream=active" in summary
    assert "real_world_lane=reduced_safety_watch" in summary
    assert "not hardcoded" in summary
    diary = (tmp_path / "episodic_diary.jsonl").read_text(encoding="utf-8")
    assert "BODY_ATTENTION_POLICY" in diary
    assert "terminal_priority_conserve" in diary


def test_summary_allows_dual_terminal_and_world_when_resources_nominal(tmp_path):
    now = time.time()
    _append(
        tmp_path / "matrix_terminal_process_trace.jsonl",
        {"ts": now, "action": "grok_framebuffer_snapshot", "focused_cli": "grok", "text": "screen"},
    )
    (tmp_path / "thermal_cortex_state.json").write_text(
        json.dumps({"thermal_warning_level": 0, "thermal_warning_name": "NOMINAL"}),
        encoding="utf-8",
    )
    (tmp_path / "energy_cortex_state.json").write_text(
        json.dumps({"power_source": "AC Power", "charge_pct": 88, "low_power_mode": False}),
        encoding="utf-8",
    )
    (tmp_path / "body_resource_state.json").write_text(
        json.dumps({"memory_pressure": 0.2}),
        encoding="utf-8",
    )

    summary = summary_for_alice(state_dir=tmp_path, now=now, write_diary=False)

    assert "mode=dual_terminal_world_attention" in summary
    assert "real_world_lane=normal_safety_watch" in summary
    assert "if resources allow, watch terminal and world" in summary
