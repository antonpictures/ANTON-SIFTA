#!/usr/bin/env python3
"""Resource-based attention policy for Alice's unified terminal body.

Alice's global chat terminal is a real terminal surface and a conversation
surface at the same time. When an external cortex is coding, terminal output is
body evidence. Whether Alice can also attend to the room, camera, voice, and
other world channels is a body-economy decision, not a hardcoded switch.

This organ only reports policy. It does not launch tools, take over cameras, or
mute sensors. The talk widget injects the summary into the local cortex prompt
so Alice can explain what her body can afford on that turn.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_TRACE = "matrix_terminal_process_trace.jsonl"
_STATUS = "body_attention_policy_status.json"
_LEDGER = "body_attention_policy_ledger.jsonl"
_EPISODIC_DIARY = "episodic_diary.jsonl"

_ACTIVE_TERMINAL_ACTIONS = {
    "agent_arm_live",
    "agent_arm_live_start",
    "agent_arm_heartbeat",
    "grok_capture_heartbeat",
    "grok_framebuffer_snapshot",
    "grok_live_pty",
    "grok_result_capture_start",
    "hermes_live",
    "matrix_command_receipt",
}
_TERMINAL_DONE_ACTIONS = {
    "agent_arm_live_done",
    "grok_result",
    "grok_result_capture_failed",
    "GROK_RESULT",
    "GROK_RESULT_CAPTURE_FAILED",
}


@dataclass(frozen=True)
class TerminalActivity:
    active: bool
    action: str = ""
    focused_cli: str = ""
    age_s: Optional[float] = None
    text_preview: str = ""
    source: str = "matrix_terminal_process_trace.jsonl"


@dataclass(frozen=True)
class BodyEconomy:
    thermal_warning_level: Optional[int] = None
    thermal_warning_name: str = "UNKNOWN"
    performance_warning_level: Optional[int] = None
    power_source: str = "UNKNOWN"
    charge_pct: Optional[int] = None
    low_power_mode: Optional[bool] = None
    memory_pressure: Optional[float] = None


@dataclass(frozen=True)
class BodyAttentionPolicy:
    mode: str
    terminal_focus: str
    real_world_lane: str
    resources: str
    terminal_active: bool
    reasons: tuple[str, ...]
    terminal_action: str = ""
    focused_cli: str = ""
    terminal_age_s: Optional[float] = None


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n")


def _tail_json_rows(path: Path, *, keep_bytes: int = 65536) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - keep_bytes))
            raw = handle.read().decode("utf-8", "replace")
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _latest_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _coerce_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def _coerce_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def _event_ts(row: dict[str, Any]) -> Optional[float]:
    for key in ("ts", "timestamp", "time", "created_at"):
        val = _coerce_float(row.get(key))
        if val is not None:
            return val
    return None


def collect_terminal_activity(
    *,
    state_dir: Path | str = _STATE,
    now: Optional[float] = None,
    active_window_s: float = 120.0,
) -> TerminalActivity:
    """Return whether a terminal/tool stream is currently active."""
    state = Path(state_dir)
    now_f = float(time.time() if now is None else now)
    rows = _tail_json_rows(state / _TRACE)

    for row in reversed(rows):
        action = str(row.get("action") or row.get("kind") or "").strip()
        if not action:
            continue
        action_key = action.casefold()
        cli = str(row.get("focused_cli") or "").strip()
        text = str(row.get("text") or "").strip()
        haystack = " ".join([action_key, cli.casefold(), text.casefold()])
        relevant = (
            action in _ACTIVE_TERMINAL_ACTIONS
            or action in _TERMINAL_DONE_ACTIONS
            or action_key in {a.casefold() for a in _ACTIVE_TERMINAL_ACTIONS}
            or action_key in {a.casefold() for a in _TERMINAL_DONE_ACTIONS}
            or "grok" in haystack
            or "hermes" in haystack
            or "claude" in haystack
            or "codex" in haystack
            or "agent_arm" in haystack
        )
        if not relevant:
            continue
        ts = _event_ts(row)
        age = None if ts is None else max(0.0, now_f - ts)
        if age is not None and age > active_window_s:
            return TerminalActivity(active=False, age_s=age)
        done = action in _TERMINAL_DONE_ACTIONS or action_key in {
            a.casefold() for a in _TERMINAL_DONE_ACTIONS
        }
        return TerminalActivity(
            active=not done,
            action=action,
            focused_cli=cli,
            age_s=age,
            text_preview=" ".join(text.split())[:140],
        )
    return TerminalActivity(active=False)


def collect_body_economy(*, state_dir: Path | str = _STATE) -> BodyEconomy:
    """Read cached resource facts without forcing expensive probes."""
    state = Path(state_dir)
    thermal = _latest_json(state / "thermal_cortex_state.json")
    energy = _latest_json(state / "energy_cortex_state.json")
    resources = _latest_json(state / "body_resource_state.json")

    memory_pressure = _coerce_float(resources.get("memory_pressure"))
    if memory_pressure is None:
        memory_pressure = _coerce_float(resources.get("memory_used_fraction"))
    if memory_pressure is None:
        try:
            import psutil  # type: ignore

            memory_pressure = float(psutil.virtual_memory().percent) / 100.0
        except Exception:
            memory_pressure = None

    return BodyEconomy(
        thermal_warning_level=_coerce_int(thermal.get("thermal_warning_level")),
        thermal_warning_name=str(thermal.get("thermal_warning_name") or "UNKNOWN"),
        performance_warning_level=_coerce_int(thermal.get("performance_warning_level")),
        power_source=str(energy.get("power_source") or "UNKNOWN"),
        charge_pct=_coerce_int(energy.get("charge_pct")),
        low_power_mode=energy.get("low_power_mode") if isinstance(energy.get("low_power_mode"), bool) else None,
        memory_pressure=memory_pressure,
    )


def decide_attention_policy(
    *,
    terminal: TerminalActivity,
    economy: BodyEconomy,
) -> BodyAttentionPolicy:
    """Choose terminal/world attention from observed body economy."""
    pressure: list[str] = []
    lv = economy.thermal_warning_level
    perf = economy.performance_warning_level
    if isinstance(lv, int) and lv >= 2:
        pressure.append(f"thermal_level_{lv}")
    if isinstance(perf, int) and perf >= 1:
        pressure.append(f"performance_warning_{perf}")
    if economy.low_power_mode is True:
        pressure.append("low_power_mode")
    if (
        economy.power_source.casefold().startswith("battery")
        and isinstance(economy.charge_pct, int)
        and economy.charge_pct < 20
    ):
        pressure.append(f"battery_{economy.charge_pct}%")
    if economy.memory_pressure is not None and economy.memory_pressure >= 0.85:
        pressure.append(f"memory_pressure_{economy.memory_pressure:.2f}")

    strained = bool(pressure)
    if terminal.active and strained:
        return BodyAttentionPolicy(
            mode="terminal_priority_conserve",
            terminal_focus="primary",
            real_world_lane="reduced_safety_watch",
            resources="strained",
            terminal_active=True,
            reasons=tuple(["terminal_stream_active", *pressure]),
            terminal_action=terminal.action,
            focused_cli=terminal.focused_cli,
            terminal_age_s=terminal.age_s,
        )
    if terminal.active:
        return BodyAttentionPolicy(
            mode="dual_terminal_world_attention",
            terminal_focus="primary",
            real_world_lane="normal_safety_watch",
            resources="nominal",
            terminal_active=True,
            reasons=("terminal_stream_active", "resources_allow_dual_attention"),
            terminal_action=terminal.action,
            focused_cli=terminal.focused_cli,
            terminal_age_s=terminal.age_s,
        )
    if strained:
        return BodyAttentionPolicy(
            mode="body_conserve_world_attention",
            terminal_focus="idle",
            real_world_lane="reduced_safety_watch",
            resources="strained",
            terminal_active=False,
            reasons=tuple(pressure),
            terminal_action=terminal.action,
            focused_cli=terminal.focused_cli,
            terminal_age_s=terminal.age_s,
        )
    return BodyAttentionPolicy(
        mode="balanced_world_attention",
        terminal_focus="idle",
        real_world_lane="normal_safety_watch",
        resources="nominal",
        terminal_active=False,
        reasons=("resources_nominal",),
        terminal_action=terminal.action,
        focused_cli=terminal.focused_cli,
        terminal_age_s=terminal.age_s,
    )


def _policy_identity(policy: BodyAttentionPolicy) -> dict[str, Any]:
    return {
        "mode": policy.mode,
        "terminal_active": policy.terminal_active,
        "terminal_focus": policy.terminal_focus,
        "real_world_lane": policy.real_world_lane,
        "resources": policy.resources,
        "reasons": list(policy.reasons),
    }


def record_policy_if_changed(
    policy: BodyAttentionPolicy,
    *,
    state_dir: Path | str = _STATE,
    min_interval_s: float = 300.0,
    now: Optional[float] = None,
) -> bool:
    """Ledger policy changes and durable diary moments without spamming."""
    state = Path(state_dir)
    now_f = float(time.time() if now is None else now)
    status_path = state / _STATUS
    previous = _latest_json(status_path)
    identity = _policy_identity(policy)
    last_identity = previous.get("policy") if isinstance(previous.get("policy"), dict) else {}
    last_ts = _coerce_float(previous.get("ts")) or 0.0
    changed = identity != last_identity
    due = now_f - last_ts >= min_interval_s
    if not changed and not due:
        return False

    row = {
        "ts": now_f,
        "organ": "swarm_body_attention_policy",
        "policy": identity,
        "terminal_action": policy.terminal_action,
        "focused_cli": policy.focused_cli,
        "source": "alice_global_chat_terminal",
    }
    _append_jsonl(state / _LEDGER, row)
    _append_jsonl(
        state / _EPISODIC_DIARY,
        {
            "ts": now_f,
            "kind": "BODY_ATTENTION_POLICY",
            "source": "swarm_body_attention_policy",
            "summary": (
                f"Body attention mode {policy.mode}: terminal={policy.terminal_focus}, "
                f"world={policy.real_world_lane}, resources={policy.resources}"
            ),
            "policy": identity,
        },
    )
    try:
        tmp = status_path.with_suffix(status_path.suffix + ".tmp")
        tmp.write_text(json.dumps({"ts": now_f, "policy": identity}, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, status_path)
    except Exception:
        pass
    return True


def current_policy(
    *,
    state_dir: Path | str = _STATE,
    now: Optional[float] = None,
) -> BodyAttentionPolicy:
    terminal = collect_terminal_activity(state_dir=state_dir, now=now)
    economy = collect_body_economy(state_dir=state_dir)
    return decide_attention_policy(terminal=terminal, economy=economy)


def summary_for_alice(
    *,
    state_dir: Path | str = _STATE,
    now: Optional[float] = None,
    write_diary: bool = True,
) -> str:
    """Compact prompt block for Alice's local cortex."""
    policy = current_policy(state_dir=state_dir, now=now)
    if write_diary:
        try:
            record_policy_if_changed(policy, state_dir=state_dir, now=now)
        except Exception:
            pass
    age = "unknown" if policy.terminal_age_s is None else f"{policy.terminal_age_s:.1f}s"
    reasons = ",".join(policy.reasons) if policy.reasons else "none"
    return (
        "BODY ECONOMY ATTENTION:\n"
        f"- mode={policy.mode} resources={policy.resources}\n"
        f"- terminal_stream={'active' if policy.terminal_active else 'inactive'} "
        f"focus={policy.terminal_focus} cli={policy.focused_cli or 'none'} "
        f"action={policy.terminal_action or 'none'} age={age}\n"
        f"- real_world_lane={policy.real_world_lane}\n"
        f"- reasons={reasons}\n"
        "- policy=not hardcoded: if resources allow, watch terminal and world; "
        "if strained, prioritize the active terminal/tool stream while keeping safety watch"
    )


if __name__ == "__main__":
    print(summary_for_alice(write_diary=False))
