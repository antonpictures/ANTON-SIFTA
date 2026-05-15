#!/usr/bin/env python3
"""Synthetic aquaculture field sentinel.

This module is the first operational backing for the Aquaculture Field
Sentinel app. It is deliberately a synthetic tank only: no live farm, no live
animals, and no welfare claim is made unless a future sensor bridge supplies
real measurements with its own receipts.

The useful pattern is the SIFTA one: many cheap local probes become a field.
One noisy camera reading is not enough to act. Cross-probe convergence can ask
for aeration, hold feeding, or alert a human.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

TRUTH_LABEL = "AQUACULTURE_FIELD_SENTINEL_V1"
LEDGER_NAME = "aquaculture_field.jsonl"
SCENARIOS = ("normal", "low_oxygen", "camera_noise", "feed_spike", "thermal_stress")
CHANNELS = (
    "oxygen",
    "ph",
    "temperature_c",
    "turbidity",
    "feed",
    "motion",
    "camera_noise",
)


@dataclass(frozen=True)
class AquacultureConfig:
    width: int = 12
    height: int = 8
    oxygen_low: float = 0.62
    oxygen_severe: float = 0.48
    turbidity_high: float = 0.48
    feed_high: float = 0.70
    motion_low: float = 0.38
    temperature_high_c: float = 26.5
    camera_noise_high: float = 0.70
    sample_fast_ms: int = 300
    sample_slow_ms: int = 5200
    attention_k: float = 3.2


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _state_dir(state_root: str | Path | None = None) -> Path:
    if state_root is None:
        env = os.environ.get("SIFTA_STATE_ROOT")
        if env:
            return Path(env)
        return _repo_root() / ".sifta_state"
    p = Path(state_root)
    if (p / "System").exists() and (p / ".sifta_state").exists():
        return p / ".sifta_state"
    return p


def make_synthetic_tank(
    scenario: str = "normal",
    *,
    width: int = 12,
    height: int = 8,
) -> dict[str, Any]:
    """Return a deterministic synthetic tank observation.

    Cell values are normalized except pH and temperature. This is a simulator
    surface for testing field logic, not a physical sensor reader.
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown aquaculture scenario: {scenario!r}")

    cells: list[dict[str, float]] = []
    for y in range(height):
        for x in range(width):
            wave = math.sin(x * 0.67 + y * 0.31)
            cross = math.cos(x * 0.19 - y * 0.43)
            cell = {
                "x": float(x),
                "y": float(y),
                "oxygen": _clamp(0.84 + 0.035 * wave),
                "ph": 7.34 + 0.05 * cross,
                "temperature_c": 22.4 + 0.35 * math.sin((x + y) * 0.18),
                "turbidity": _clamp(0.18 + 0.035 * cross),
                "feed": _clamp(0.24 + 0.025 * wave),
                "motion": _clamp(0.58 + 0.06 * math.sin(y * 0.7)),
                "camera_noise": _clamp(0.08 + 0.02 * math.cos(x * y + 1.0)),
            }

            in_patch = x >= width * 0.58 and height * 0.20 <= y <= height * 0.78
            in_surface = y <= max(1, height // 4)

            if scenario == "low_oxygen" and in_patch:
                cell["oxygen"] = _clamp(0.41 + 0.04 * math.sin(y + x))
                cell["temperature_c"] += 1.4
                cell["turbidity"] = _clamp(cell["turbidity"] + 0.32)
                cell["motion"] = _clamp(cell["motion"] - 0.28)
            elif scenario == "camera_noise" and in_surface:
                cell["camera_noise"] = _clamp(0.86 + 0.06 * math.sin(x))
            elif scenario == "feed_spike" and x <= width * 0.55:
                cell["feed"] = _clamp(0.82 + 0.05 * math.sin(x + y))
                cell["turbidity"] = _clamp(cell["turbidity"] + 0.42)
                cell["oxygen"] = _clamp(cell["oxygen"] - 0.07)
            elif scenario == "thermal_stress":
                cell["temperature_c"] += 5.0 + 0.7 * math.sin(x * 0.4)
                cell["oxygen"] = _clamp(cell["oxygen"] - 0.18)
                if in_patch:
                    cell["motion"] = _clamp(cell["motion"] - 0.18)
                    cell["turbidity"] = _clamp(cell["turbidity"] + 0.20)

            cells.append(cell)

    return {
        "truth_label": TRUTH_LABEL,
        "scenario": scenario,
        "simulated": True,
        "no_live_animals": True,
        "width": width,
        "height": height,
        "channels": list(CHANNELS),
        "cells": cells,
    }


def _values(observation: dict[str, Any], key: str) -> list[float]:
    return [float(cell[key]) for cell in observation.get("cells", []) if key in cell]


def _stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"avg": 0.0, "min": 0.0, "max": 0.0, "std": 0.0}
    avg = sum(values) / len(values)
    var = sum((v - avg) ** 2 for v in values) / len(values)
    return {
        "avg": round(avg, 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "std": round(math.sqrt(var), 6),
    }


def summarize_observation(
    observation: dict[str, Any],
    *,
    config: AquacultureConfig | None = None,
) -> dict[str, Any]:
    cfg = config or AquacultureConfig()
    channel_stats = {name: _stats(_values(observation, name)) for name in CHANNELS}
    oxygen_values = _values(observation, "oxygen")
    motion_values = _values(observation, "motion")
    low_count = sum(1 for v in oxygen_values if v < cfg.oxygen_low)
    severe_count = sum(1 for v in oxygen_values if v < cfg.oxygen_severe)
    low_motion_count = sum(1 for v in motion_values if v < cfg.motion_low)
    n = max(1, len(oxygen_values))
    support: list[str] = []

    if low_count / n > 0.08 or channel_stats["oxygen"]["min"] < cfg.oxygen_low:
        support.append("oxygen_probe")
    if channel_stats["motion"]["avg"] < cfg.motion_low or low_motion_count / n > 0.08:
        support.append("motion_drop")
    if (
        channel_stats["turbidity"]["avg"] > cfg.turbidity_high
        or channel_stats["turbidity"]["max"] > cfg.turbidity_high
    ):
        support.append("turbidity_probe")
    if channel_stats["temperature_c"]["avg"] > cfg.temperature_high_c:
        support.append("temperature_probe")
    if (
        channel_stats["feed"]["avg"] > cfg.feed_high
        or channel_stats["feed"]["max"] > cfg.feed_high
    ):
        support.append("feed_probe")

    camera_noise_only = (
        (
            channel_stats["camera_noise"]["avg"] > cfg.camera_noise_high
            or channel_stats["camera_noise"]["max"] > cfg.camera_noise_high
        )
        and support == []
    )
    oxygen_deficit = _clamp((cfg.oxygen_low - channel_stats["oxygen"]["min"]) / 0.35)
    low_fraction = low_count / n
    severe_fraction = severe_count / n
    field_disagreement = _clamp(
        channel_stats["oxygen"]["std"] * 1.6
        + channel_stats["turbidity"]["std"]
        + channel_stats["motion"]["std"] * 0.6
    )
    risk = _clamp(
        oxygen_deficit * 0.42
        + low_fraction * 0.35
        + severe_fraction * 0.42
        + max(0.0, channel_stats["temperature_c"]["avg"] - 26.0) * 0.035
        + max(0.0, channel_stats["turbidity"]["avg"] - 0.45) * 0.28
    )

    return {
        "scenario": observation.get("scenario", "unknown"),
        "simulated": bool(observation.get("simulated", True)),
        "no_live_animals": bool(observation.get("no_live_animals", True)),
        "cell_count": n,
        "channel_stats": channel_stats,
        "low_oxygen_fraction": round(low_fraction, 6),
        "severe_oxygen_fraction": round(severe_fraction, 6),
        "field_disagreement": round(field_disagreement, 6),
        "cross_probe_support": support,
        "camera_noise_only": camera_noise_only,
        "risk": round(risk, 6),
    }


def _summary_delta(a: dict[str, Any], b: dict[str, Any] | None) -> float:
    if not b:
        return 0.0
    total = 0.0
    for channel in ("oxygen", "temperature_c", "turbidity", "feed", "motion"):
        total += abs(
            float(a["channel_stats"][channel]["avg"])
            - float(b["channel_stats"][channel]["avg"])
        )
    return _clamp(total / 4.0)


def _sample_period_ms(attention: float, cfg: AquacultureConfig) -> int:
    # Exponential attention law: idle backs off smoothly, surprise accelerates.
    fast = float(cfg.sample_fast_ms)
    slow = float(cfg.sample_slow_ms)
    return int(round(fast + (slow - fast) * math.exp(-cfg.attention_k * attention)))


def decide(
    observation: dict[str, Any],
    *,
    previous_observation: dict[str, Any] | None = None,
    config: AquacultureConfig | None = None,
) -> dict[str, Any]:
    cfg = config or AquacultureConfig()
    summary = summarize_observation(observation, config=cfg)
    prev_summary = (
        summarize_observation(previous_observation, config=cfg)
        if previous_observation else None
    )
    surprise = _summary_delta(summary, prev_summary)
    attention = _clamp(
        summary["risk"]
        + summary["field_disagreement"] * 0.42
        + surprise * 0.55
        + (0.18 if summary["camera_noise_only"] else 0.0)
    )

    actions: list[str] = []
    reason: list[str] = []
    support = set(summary["cross_probe_support"])
    oxygen_supported = "oxygen_probe" in support and len(support) >= 2

    if summary["camera_noise_only"]:
        actions.append("ACTIVE_PROBE")
        reason.append("camera noise is high but water probes do not agree")
    if "feed_probe" in support and "turbidity_probe" in support:
        actions.append("FEED_HOLD")
        reason.append("feed trace and turbidity converge")
    if oxygen_supported:
        actions.append("AERATION_REQUEST")
        reason.append("oxygen anomaly has cross-probe support")
    if summary["risk"] >= 0.78 or summary["severe_oxygen_fraction"] > 0.10:
        actions.append("HUMAN_ALERT")
        reason.append("synthetic risk crossed human alert threshold")
    if not actions:
        actions.append("LOW_BURN_MONITOR")
        reason.append("field stable; no cross-probe action")

    # Preserve action order while removing duplicates.
    deduped_actions = list(dict.fromkeys(actions))
    primary = next(
        (a for a in deduped_actions if a in {"HUMAN_ALERT", "AERATION_REQUEST", "FEED_HOLD"}),
        deduped_actions[0],
    )

    return {
        "truth_label": TRUTH_LABEL,
        "simulated": True,
        "no_live_animals": True,
        "primary_action": primary,
        "actions": deduped_actions,
        "sample_period_ms": _sample_period_ms(attention, cfg),
        "attention": round(attention, 6),
        "surprise": round(surprise, 6),
        "reason": "; ".join(reason),
        "summary": summary,
    }


def _receipt_id(row: dict[str, Any]) -> str:
    blob = json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _receipt_row(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = {
        "ts": time.time(),
        "kind": kind,
        "truth_label": TRUTH_LABEL,
        "simulated": True,
        "no_live_animals": True,
        "source": "System.swarm_aquaculture_field",
        "payload": payload,
    }
    row["receipt_id"] = _receipt_id(row)
    return row


def write_receipts(
    decision: dict[str, Any],
    *,
    state_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    state = _state_dir(state_root)
    state.mkdir(parents=True, exist_ok=True)
    ledger = state / LEDGER_NAME
    rows = [
        _receipt_row("OBSERVED", {"summary": decision["summary"]}),
        _receipt_row(
            "SAMPLE_DECISION",
            {
                "sample_period_ms": decision["sample_period_ms"],
                "attention": decision["attention"],
                "surprise": decision["surprise"],
                "reason": decision["reason"],
                "actions": decision["actions"],
            },
        ),
    ]
    for action in decision["actions"]:
        if action == "LOW_BURN_MONITOR":
            continue
        rows.append(
            _receipt_row(
                action,
                {
                    "primary_action": decision["primary_action"],
                    "risk": decision["summary"]["risk"],
                    "cross_probe_support": decision["summary"]["cross_probe_support"],
                    "reason": decision["reason"],
                },
            )
        )

    with ledger.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    return rows


def run_sentinel_tick(
    scenario: str = "normal",
    *,
    previous_scenario: str | None = None,
    state_root: str | Path | None = None,
    write: bool = True,
    config: AquacultureConfig | None = None,
) -> dict[str, Any]:
    cfg = config or AquacultureConfig()
    observation = make_synthetic_tank(
        scenario,
        width=cfg.width,
        height=cfg.height,
    )
    previous = (
        make_synthetic_tank(previous_scenario, width=cfg.width, height=cfg.height)
        if previous_scenario else None
    )
    decision = decide(observation, previous_observation=previous, config=cfg)
    receipts = write_receipts(decision, state_root=state_root) if write else []
    return {
        "observation": observation,
        "decision": decision,
        "receipts": receipts,
    }


def latest_receipt(state_root: str | Path | None = None) -> dict[str, Any] | None:
    ledger = _state_dir(state_root) / LEDGER_NAME
    if not ledger.exists():
        return None
    try:
        lines = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return None
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return None


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a synthetic aquaculture sentinel tick.")
    parser.add_argument("--scenario", choices=SCENARIOS, default="normal")
    parser.add_argument("--previous-scenario", choices=SCENARIOS, default=None)
    parser.add_argument("--state-root", default=None)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = run_sentinel_tick(
        args.scenario,
        previous_scenario=args.previous_scenario,
        state_root=args.state_root,
        write=not args.no_write,
    )
    if args.json:
        print(json.dumps(result["decision"], indent=2, sort_keys=True))
    else:
        decision = result["decision"]
        receipts = ", ".join(row["kind"] for row in result["receipts"]) or "not written"
        print(
            f"{TRUTH_LABEL} scenario={args.scenario} "
            f"action={decision['primary_action']} "
            f"sample_ms={decision['sample_period_ms']} receipts={receipts}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
