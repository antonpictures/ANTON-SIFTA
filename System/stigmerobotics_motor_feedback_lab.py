"""Two-joint perception/control benchmark. SIMULATED; no hardware or LLM calls.

Visual input is a synthetic 2-D target feature, not image pixels. A cheap
synthetic novelty detector requests expensive feature refreshes. Counts are
perception proxies, not measured token savings or electrical energy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from System.ledger_append import append_jsonl_line
from System.swarm_motor_action_gate import ActionOutcome, MotorActionGate, PlanProposal

ROOT = Path(__file__).resolve().parents[1]
LABEL = "SIMULATED"
SCENARIOS = ("static", "moving", "dropout", "disturbance", "unreachable")


@dataclass(frozen=True)
class MotorConfig:
    dt: float = 0.02
    steps: int = 400
    max_speed: float = 1.5
    joint_limit: float = 2.8
    max_observation_age: float = 0.30
    refresh_age: float = 0.20
    change_threshold: float = 0.04
    tracking_tolerance: float = 0.09

    def __post_init__(self):
        values = (self.dt, self.max_speed, self.joint_limit,
                  self.max_observation_age, self.refresh_age,
                  self.change_threshold, self.tracking_tolerance)
        if not all(math.isfinite(x) and x > 0 for x in values):
            raise ValueError("finite positive configuration required")
        if not isinstance(self.steps, int) or not 1 <= self.steps <= 10000:
            raise ValueError("steps must be an integer from 1 to 10000")
        if self.refresh_age >= self.max_observation_age:
            raise ValueError("refresh must precede stale observation cutoff")


def forward(q):
    return (math.cos(q[0]) + math.cos(q[0] + q[1]),
            math.sin(q[0]) + math.sin(q[0] + q[1]))


def inverse(target, limit):
    x, y = target
    if not all(math.isfinite(v) for v in target):
        return None
    cosine = (x*x + y*y - 2) / 2
    if not -1 <= cosine <= 1:
        return None
    q2 = math.acos(cosine)
    q1 = math.atan2(y, x) - math.atan2(math.sin(q2), 1 + math.cos(q2))
    return (q1, q2) if max(abs(q1), abs(q2)) <= limit else None


def target_at(scenario, t, offset):
    if scenario == "unreachable":
        return (3.0, 0.0)
    return (1.1 + offset + (0.15 * math.sin(t) if scenario == "moving" else 0),
            0.6 + (0.12 * math.cos(t) if scenario == "moving" else 0))


def run_trial(policy, scenario, seed=0, config=None):
    if policy not in {"continuous", "event"} or scenario not in SCENARIOS:
        raise ValueError("unknown policy or scenario")
    c = config or MotorConfig()
    gate = MotorActionGate(max_speed=c.max_speed, joint_limit=c.joint_limit,
                           max_age=c.max_observation_age, max_dt=c.dt)
    offset = random.Random(seed).uniform(-0.08, 0.08)
    q = [0.0, 0.5]
    seen, observed_t = None, -math.inf
    rows, errors, timings = [], [], []
    refreshes = novelty_checks = stale_holds = rejected = 0
    effort = 0.0
    recovery_t = None
    had_stale = False
    for step in range(c.steps):
        started = time.perf_counter()
        t = step * c.dt
        target = target_at(scenario, t, offset)
        available = not (scenario == "dropout" and 2 <= t < 3)
        if scenario == "disturbance" and step == 120:
            q[0] += 0.25
        refresh = False
        if policy == "event":
            novelty_checks += int(available)
        if available and (policy == "continuous" or seen is None
                          or t-observed_t >= c.refresh_age - 1e-9
                          or math.dist(target, seen) >= c.change_threshold):
            seen, observed_t = target, t
            refreshes += 1
            refresh = True
        age = t - observed_t
        desired = inverse(seen, c.joint_limit) if seen is not None else None
        before = list(q)
        proposal = PlanProposal(step, observed_t if seen is not None else None, desired)
        decision = gate.decide(proposal, now_s=t, joints=q, dt=c.dt)
        command, status = list(decision.command_rad_s), decision.status
        if status == "HOLD_STALE":
            stale_holds += 1
            had_stale = True
        elif status.startswith("REJECT_"):
            rejected += 1
        q = [max(-c.joint_limit, min(c.joint_limit, pos + c.dt*vel))
             for pos, vel in zip(q, command)]
        error = math.dist(forward(q), target)
        outcome = ActionOutcome(step, status, decision.command_rad_s, tuple(q), error)
        errors.append(error)
        effort += sum(v*v for v in command) * c.dt
        if had_stale and available and error <= c.tracking_tolerance and recovery_t is None:
            recovery_t = max(0, t-3.0)
        elapsed = (time.perf_counter()-started)*1000
        timings.append(elapsed)
        rows.append({"tick": step, "time_s": t, "truth_label": LABEL,
                     "observation_refreshed": refresh, "observation_available": available,
                     "observation_age_s": age if math.isfinite(age) else None,
                     "observed_target": seen, "actual_target": target,
                     "joint_before": before, "command_rad_s": command,
                     "joint_echo": list(q), "tracking_error_m": error,
                     "proposal": asdict(proposal), "outcome": asdict(outcome),
                     "status": status, "control_compute_ms": elapsed})
    tail_error = max(errors[-min(50, c.steps):])
    return {"policy": policy, "scenario": scenario, "seed": seed,
            "truth_label": LABEL, "rows": rows,
            "metrics": {"steps": c.steps, "visual_feature_refreshes": refreshes,
                        "cheap_novelty_checks": novelty_checks,
                        "llm_inference_calls": 0, "stale_holds": stale_holds,
                        "rejected_actions": rejected,
                        "rms_tracking_error_m": math.sqrt(sum(e*e for e in errors)/len(errors)),
                        "final_error_m": errors[-1], "tail_max_error_m": tail_error,
                        "recovery_after_sensor_return_s": recovery_t,
                        "command_effort_rad2_per_s": effort,
                        "control_compute_p95_ms": sorted(timings)[int(.95*(len(timings)-1))]}}


def run_benchmark(state_dir=None):
    state = Path(state_dir) if state_dir is not None else ROOT / ".sifta_state"
    run_id = "motor-" + uuid.uuid4().hex
    folder = state / "motor_feedback_runs" / run_id
    folder.mkdir(parents=True, exist_ok=False)
    config = MotorConfig()
    # Real host clock/location availability are context, never synthetic sensors.
    from System.swarm_body_snapshot import body_snapshot
    body_context = body_snapshot(state_dir=state)
    trials = []
    for seed in (0, 1, 2):
        for scenario in SCENARIOS:
            for policy in ("continuous", "event"):
                result = run_trial(policy, scenario, seed, config)
                for row in result.pop("rows"):
                    # One immutable command/echo pair per tick; physical outputs do not exist.
                    row.update(receipt_id=f"{run_id}:{seed}:{scenario}:{policy}:{row['tick']}",
                               run_id=run_id, scenario=scenario, policy=policy, seed=seed)
                    append_jsonl_line(folder / "actions.jsonl", row)
                trials.append(result)
    matched = [(trials[i], trials[i+1]) for i in range(0, len(trials), 2)]
    checks = {
        "event_reduces_feature_refreshes": all(b["metrics"]["visual_feature_refreshes"] < a["metrics"]["visual_feature_refreshes"] for a, b in matched),
        "reachable_targets_tracked": all(r["metrics"]["tail_max_error_m"] <= config.tracking_tolerance for r in trials if r["scenario"] != "unreachable"),
        "dropout_holds_and_recovers": all(r["metrics"]["stale_holds"] > 0 and r["metrics"]["recovery_after_sensor_return_s"] is not None for r in trials if r["scenario"] == "dropout"),
        "unreachable_rejected": all(r["metrics"]["rejected_actions"] == config.steps and r["metrics"]["command_effort_rad2_per_s"] == 0 for r in trials if r["scenario"] == "unreachable"),
    }
    summary = {"run_id": run_id, "ts": time.time(), "truth_label": LABEL,
               "body_context": body_context,
               "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
               "trials": trials, "action_count": len(trials)*config.steps,
               "actions_sha256": hashlib.sha256((folder / "actions.jsonl").read_bytes()).hexdigest(),
               "run_dir": str(folder),
               "scope": "Synthetic target features and kinematic two-joint plant; no pixels, LLM, physical robot, or electrical energy measurement."}
    (folder / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    append_jsonl_line(state / "motor_feedback_experiments.jsonl", summary)
    return summary


def motor_feedback_evidence_lines(state_dir=None):
    state = Path(state_dir) if state_dir is not None else ROOT / ".sifta_state"
    lines = ["Motor Feedback Lab | SIMULATED"]
    try:
        with (state / "motor_feedback_experiments.jsonl").open("rb") as f:
            size = f.seek(0, 2)
            f.seek(max(0, size-131072))
            summary = json.loads(f.read().splitlines()[-1])
        if summary["truth_label"] != LABEL or summary["status"] not in {"PASS", "FAIL"}:
            raise ValueError("unsupported result")
        lines.append(f"Recorded: {summary['status']} | {len(summary['trials'])} trials | {summary['action_count']} command/echo pairs")
        lines.extend(f"{key}: {'PASS' if value else 'FAIL'}" for key, value in summary["checks"].items())
        lines.append("Evidence: " + summary["run_dir"])
        context = summary.get("body_context", {})
        if context:
            lines.append("Host sampled: " + str(context.get("clock", {}).get("local_iso", "unknown")))
            lines.append("Host context, not physical motor proof: location="
                         + str(context.get("location", {}).get("status", "UNAVAILABLE"))
                         + "; health=" + str(context.get("organ_health", {}).get("status", "UNAVAILABLE")))
        lines.append(summary["scope"])
    except FileNotFoundError:
        lines.append("NOT RUN")
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        lines.append("UNAVAILABLE: invalid result record")
    return lines


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=ROOT / ".sifta_state")
    args = parser.parse_args()
    result = run_benchmark(args.state_dir)
    print(json.dumps({k: result[k] for k in ("run_id", "status", "checks", "run_dir")}, indent=2))
