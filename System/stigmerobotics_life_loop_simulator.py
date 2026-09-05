#!/usr/bin/env python3
"""Receipted closed-loop simulation for Alice's virtual robotics limb.

The experiment deliberately proves a narrow claim: a simulated body can issue
an effector request, observe the resulting sensor echo, preserve body state
across a process restart, and recover a useful controller setting from an
evaporating stigmergic trace.  Every result remains truth-labeled SIMULATED.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.ledger_append import append_jsonl_line
from System.stigmerobotics_effector_bridge import (
    EffectorRequest,
    execute_request_stub,
)
from System.stigmerobotics_pheromone_field import field_report
from System.stigmerobotics_physical_space import build_physical_space_report
from System.stigmerobotics_virtual_physics_limb import simulate_limb_step

SIMULATION_TRUTH_LABEL = "SIMULATED"
BODY_ID = "virtual_physics_limb"
STATE_FILENAME = "body_state.json"
LEDGER_FILENAME = "life_loop_receipts.jsonl"
EXPERIMENT_LEDGER_FILENAME = "life_loop_experiments.jsonl"
DEFAULT_GAINS = (4.0, 5.0, 3.0)


def life_loop_evidence_lines(state_dir: Path | str | None = None) -> list[str]:
    """Bounded, read-only summary shared by the matrix and coding surface."""
    state = Path(state_dir) if state_dir is not None else _REPO / ".sifta_state"
    path = state / "stigmerobotics_life_loop_runs" / EXPERIMENT_LEDGER_FILENAME
    lines = ["Life Loop Lab | SIMULATED | latest recorded experiment"]
    try:
        with path.open("rb") as stream:
            size = stream.seek(0, os.SEEK_END)
            stream.seek(max(0, size - 65536))
            tail = stream.read().splitlines()
        row = json.loads(tail[-1])
        data = row["payload"]
        if row.get("kind") != "life_loop_experiment_result" or data.get("truth_label") != "SIMULATED":
            raise ValueError("unexpected experiment schema")
        verified = data.get("process_boundary_verified") is True
        status = "PASS" if data.get("passed") is True and verified else "FAIL / UNVERIFIED"
        recorded = datetime.fromtimestamp(float(row["ts"]), timezone.utc).isoformat()
        lines.extend([
            f"Recorded result: {status}; UTC {recorded}",
            f"Cold: {data['cold_activation']['steps']} steps; recovery: {data['resumed_activation']['steps']} steps; without trace: {data['counterfactual_cold_steps']} steps.",
            f"Fresh interpreter verified: {verified}; receipt pairing: {data.get('receipt_chain_ok') is True}.",
            f"Evidence directory: {data['run_dir']}",
        ])
    except FileNotFoundError:
        lines.append("NOT RUN: no local experiment index found.")
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        lines.append("UNAVAILABLE: latest experiment record could not be read or validated.")
    lines.extend([
        "Scope: one simulated joint and a programmed controller-gain update; generalization remains untested.",
        "Next experiment: compare retained versus erased traces across varied targets and disturbances; report failures too.",
        "Run from Stigmerobotics > Life Loop Lab. Physical robot validation remains pending.",
    ])
    return lines


@dataclass(frozen=True)
class ControllerGains:
    kp: float
    ki: float
    kd: float

    @classmethod
    def default(cls) -> "ControllerGains":
        return cls(*DEFAULT_GAINS)


@dataclass(frozen=True)
class ActivationResult:
    activation_id: str
    body_instance_id: str
    steps: int
    reached_target: bool
    disturbed: bool
    initial_error_rad: float
    peak_error_rad: float
    final_error_rad: float
    final_theta_rad: float
    final_omega_rad_s: float
    controller_gains: ControllerGains
    actuator_effort_nms: float
    estimated_work_j: float
    request_count: int
    receipt_count: int
    sensor_echo_count: int
    paired_receipts: bool
    sensor_grounded: bool
    collision_count: int
    truth_label: str = SIMULATION_TRUTH_LABEL

    def as_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["controller_gains"] = asdict(self.controller_gains)
        return row


@dataclass(frozen=True)
class LifeLoopExperimentResult:
    run_dir: str
    body_instance_id: str
    initial_process_pid: int
    resumed_process_pid: int
    process_boundary_verified: bool
    cold_activation: ActivationResult
    resumed_activation: ActivationResult
    counterfactual_cold_steps: int
    trace_loaded_after_restart: bool
    body_identity_persisted: bool
    physical_state_persisted: bool
    recovery_advantage_steps: int
    pheromone_evaporation_ok: bool
    receipt_chain_ok: bool
    passed: bool
    truth_label: str = SIMULATION_TRUTH_LABEL

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_dir": self.run_dir,
            "body_instance_id": self.body_instance_id,
            "initial_process_pid": self.initial_process_pid,
            "resumed_process_pid": self.resumed_process_pid,
            "process_boundary_verified": self.process_boundary_verified,
            "cold_activation": self.cold_activation.as_dict(),
            "resumed_activation": self.resumed_activation.as_dict(),
            "counterfactual_cold_steps": self.counterfactual_cold_steps,
            "trace_loaded_after_restart": self.trace_loaded_after_restart,
            "body_identity_persisted": self.body_identity_persisted,
            "physical_state_persisted": self.physical_state_persisted,
            "recovery_advantage_steps": self.recovery_advantage_steps,
            "pheromone_evaporation_ok": self.pheromone_evaporation_ok,
            "receipt_chain_ok": self.receipt_chain_ok,
            "passed": self.passed,
            "truth_label": self.truth_label,
        }

    def summary_lines(self) -> list[str]:
        cold = self.cold_activation
        resumed = self.resumed_activation
        return [
            "SIFTA Stigmerobotics Life Loop Simulation",
            f"Verdict: {'PASS' if self.passed else 'FAIL'} ({self.truth_label})",
            "",
            f"body_instance_id: {self.body_instance_id}",
            (
                "fresh interpreter: "
                f"pid {self.initial_process_pid} -> {self.resumed_process_pid}, "
                f"verified={self.process_boundary_verified}"
            ),
            f"cold activation: {cold.steps} steps, reached={cold.reached_target}",
            (
                "restart + disturbance: "
                f"{resumed.steps} steps, recovered={resumed.reached_target}"
            ),
            f"same-state replay without learned trace: {self.counterfactual_cold_steps} steps",
            f"trace advantage: {self.recovery_advantage_steps} steps",
            f"body identity persisted: {self.body_identity_persisted}",
            f"physical state persisted: {self.physical_state_persisted}",
            f"trace loaded after restart: {self.trace_loaded_after_restart}",
            f"request/receipt/sensor chain: {self.receipt_chain_ok}",
            f"pheromone evaporation: {self.pheromone_evaporation_ok}",
            "",
            "Boundary: this proves simulated closed-loop continuity only;",
            "it does not prove motion, safety, or autonomy on physical hardware.",
        ]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


class StigmeroboticsLifeLoopSimulator:
    """One simulated body whose controller skill lives in an external trace."""

    def __init__(self, state_dir: Path | str):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.state_dir / STATE_FILENAME
        self.ledger_path = self.state_dir / LEDGER_FILENAME
        self.loaded_existing_body = self.state_path.exists()
        self.body_instance_id = uuid.uuid4().hex
        self.physics_state = {"theta_rad": 0.0, "omega_rad_s": 0.0}
        self.activation_count = 0
        self.loaded_physics_state: dict[str, float] | None = None
        self._load_body_state()
        self.gains, self.trace_loaded = self._load_controller_trace()

    def _load_body_state(self) -> None:
        if not self.state_path.exists():
            return
        try:
            row = json.loads(self.state_path.read_text(encoding="utf-8"))
            body_id = str(row["body_instance_id"])
            theta = float(row["physics_state"]["theta_rad"])
            omega = float(row["physics_state"]["omega_rad_s"])
            activation_count = int(row.get("activation_count", 0))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return
        if not body_id or not all(math.isfinite(v) for v in (theta, omega)):
            return
        self.body_instance_id = body_id
        self.physics_state = {"theta_rad": theta, "omega_rad_s": omega}
        self.loaded_physics_state = dict(self.physics_state)
        self.activation_count = max(0, activation_count)

    def _load_controller_trace(self) -> tuple[ControllerGains, bool]:
        traces = [
            row
            for row in _read_jsonl(self.ledger_path)
            if row.get("kind") == "motor_skill_pheromone"
            and row.get("status") == "success"
        ]
        if not traces:
            return ControllerGains.default(), False
        latest = traces[-1]
        report = field_report(traces, now_ts=time.time(), dt_s=60.0)
        channel = "target:joint_target:+0.650"
        if report.field.get(channel, 0.0) <= 0.05:
            return ControllerGains.default(), False
        try:
            data = latest["payload"]["gains"]
            gains = ControllerGains(
                kp=float(data["kp"]), ki=float(data["ki"]), kd=float(data["kd"])
            )
        except (KeyError, TypeError, ValueError):
            return ControllerGains.default(), False
        return gains, True

    def _save_body_state(self) -> None:
        _atomic_json(
            self.state_path,
            {
                "schema": "SIFTA_STIGMEROBOTICS_SIM_BODY_V1",
                "truth_label": SIMULATION_TRUTH_LABEL,
                "body_id": BODY_ID,
                "body_instance_id": self.body_instance_id,
                "physics_state": dict(self.physics_state),
                "activation_count": self.activation_count,
                "saved_ts": time.time(),
            },
        )

    def _append(self, row: Mapping[str, Any]) -> None:
        enriched = dict(row)
        enriched.setdefault("truth_label", SIMULATION_TRUTH_LABEL)
        enriched.setdefault("body_instance_id", self.body_instance_id)
        append_jsonl_line(self.ledger_path, enriched)

    def run_activation(
        self,
        *,
        target_rad: float = 0.65,
        disturbance_rad: float | None = None,
        disturbance_omega_rad_s: float = -1.0,
        max_steps: int = 240,
        step_ms: float = 40.0,
        learn: bool = True,
    ) -> ActivationResult:
        activation_id = uuid.uuid4().hex
        self.activation_count += 1
        gains = self.gains
        state = dict(self.physics_state)
        initial_error = abs(target_rad - state["theta_rad"])
        peak_error = initial_error
        integral = 0.0
        settled = 0
        request_ids: list[str] = []
        paired_ids: list[str] = []
        sensor_count = 0
        all_grounded = True
        collision_count = 0
        effort_nms = 0.0
        work_j = 0.0
        disturbed = disturbance_rad is not None

        self._append(
            {
                "ts": time.time(),
                "kind": "activation_start",
                "trace_id": activation_id,
                "activation_id": activation_id,
                "target_body_id": BODY_ID,
                "payload": {
                    "target_rad": target_rad,
                    "gains": asdict(gains),
                    "trace_loaded": self.trace_loaded,
                },
            }
        )

        reached = False
        steps = 0
        for sequence in range(max_steps):
            if sequence == 0 and disturbance_rad is not None:
                state["theta_rad"] += disturbance_rad
                state["omega_rad_s"] += disturbance_omega_rad_s
                self._append(
                    {
                        "ts": time.time(),
                        "kind": "simulated_disturbance",
                        "trace_id": uuid.uuid4().hex,
                        "activation_id": activation_id,
                        "target_body_id": BODY_ID,
                        "payload": {
                            "delta_theta_rad": disturbance_rad,
                            "delta_omega_rad_s": disturbance_omega_rad_s,
                        },
                    }
                )

            error = target_rad - state["theta_rad"]
            peak_error = max(peak_error, abs(error))
            integral = _clamp(integral + error * step_ms / 1000.0, -1.0, 1.0)
            torque = _clamp(
                gains.kp * error + gains.ki * integral - gains.kd * state["omega_rad_s"],
                -12.0,
                12.0,
            )
            request_id = uuid.uuid4().hex
            request_row = {
                "ts": time.time(),
                "kind": "effector_request",
                "trace_id": request_id,
                "activation_id": activation_id,
                "sequence": sequence,
                "target_body_id": BODY_ID,
                "action_type": "apply_torque",
                "payload": {
                    "current_state": dict(state),
                    "torque_nm": torque,
                    "duration_ms": step_ms,
                },
                "source_ide": "stigmerobotics_life_loop_simulator",
                "homeworld_serial": "SIMULATED_SUBSTRATE",
            }
            self._append(request_row)
            request = EffectorRequest(
                trace_id=request_id,
                target_body_id=BODY_ID,
                action_type="apply_torque",
                payload=dict(request_row["payload"]),
                source_ide="stigmerobotics_life_loop_simulator",
                homeworld_serial="SIMULATED_SUBSTRATE",
                ts=float(request_row["ts"]),
            )
            receipt, sensor_echo = execute_request_stub(request, now_ts=time.time())
            receipt.update(
                {
                    "activation_id": activation_id,
                    "sequence": sequence,
                    "truth_label": SIMULATION_TRUTH_LABEL,
                    "body_instance_id": self.body_instance_id,
                }
            )
            self._append(receipt)
            request_ids.append(request_id)
            paired_ids.append(str(receipt.get("request_trace_id") or ""))

            if sensor_echo is None:
                all_grounded = False
                break
            sensor_echo.update(
                {
                    "activation_id": activation_id,
                    "sequence": sequence,
                    "truth_label": SIMULATION_TRUTH_LABEL,
                    "body_instance_id": self.body_instance_id,
                }
            )
            self._append(sensor_echo)
            sensor_count += 1
            physical = build_physical_space_report(
                [sensor_echo], now_ts=float(sensor_echo["ts"]) + 0.001, max_age_s=2.0
            )
            all_grounded = all_grounded and physical.grounded

            prior_omega = state["omega_rad_s"]
            state = {
                "theta_rad": float(sensor_echo["payload"]["theta_rad"]),
                "omega_rad_s": float(sensor_echo["payload"]["omega_rad_s"]),
            }
            collision_count += int(bool(sensor_echo["payload"].get("collision")))
            dt_s = step_ms / 1000.0
            effort_nms += abs(torque) * dt_s
            work_j += abs(torque * ((prior_omega + state["omega_rad_s"]) / 2.0) * dt_s)
            steps = sequence + 1

            final_error = abs(target_rad - state["theta_rad"])
            if final_error <= 0.025 and abs(state["omega_rad_s"]) <= 0.08:
                settled += 1
            else:
                settled = 0
            if settled >= 5:
                reached = True
                break

        self.physics_state = state
        self._save_body_state()
        paired = request_ids == paired_ids and len(request_ids) == sensor_count
        result = ActivationResult(
            activation_id=activation_id,
            body_instance_id=self.body_instance_id,
            steps=steps,
            reached_target=reached,
            disturbed=disturbed,
            initial_error_rad=initial_error,
            peak_error_rad=peak_error,
            final_error_rad=abs(target_rad - state["theta_rad"]),
            final_theta_rad=state["theta_rad"],
            final_omega_rad_s=state["omega_rad_s"],
            controller_gains=gains,
            actuator_effort_nms=effort_nms,
            estimated_work_j=work_j,
            request_count=len(request_ids),
            receipt_count=len(paired_ids),
            sensor_echo_count=sensor_count,
            paired_receipts=paired,
            sensor_grounded=all_grounded and sensor_count > 0,
            collision_count=collision_count,
        )

        self._append(
            {
                "ts": time.time(),
                "kind": "activation_result",
                "trace_id": uuid.uuid4().hex,
                "activation_id": activation_id,
                "status": "success" if reached else "failed",
                "target_body_id": BODY_ID,
                "payload": result.as_dict(),
            }
        )
        if learn and reached:
            learned = ControllerGains(
                gains.kp,
                min(12.0, gains.ki + (3.0 if steps > 80 else 0.0)),
                gains.kd,
            )
            self._append(
                {
                    "ts": time.time(),
                    "kind": "motor_skill_pheromone",
                    "trace_id": uuid.uuid4().hex,
                    "activation_id": activation_id,
                    "status": "success",
                    "source_ide": "stigmerobotics_life_loop_simulator",
                    "homeworld_serial": "SIMULATED_SUBSTRATE",
                    "payload": {
                        "target": "joint_target:+0.650",
                        "gains": asdict(learned),
                        "settling_steps": steps,
                    },
                    "meta": {"pheromone_strength": 1.0, "tau_s": 604800.0},
                }
            )
        return result


def _counterfactual_steps(
    initial_state: Mapping[str, float],
    *,
    target_rad: float,
    disturbance_rad: float,
    disturbance_omega_rad_s: float,
    max_steps: int = 240,
    step_ms: float = 40.0,
) -> int:
    state = {
        "theta_rad": float(initial_state["theta_rad"]) + disturbance_rad,
        "omega_rad_s": float(initial_state["omega_rad_s"]) + disturbance_omega_rad_s,
    }
    gains = ControllerGains.default()
    integral = 0.0
    settled = 0
    for sequence in range(max_steps):
        error = target_rad - state["theta_rad"]
        integral = _clamp(integral + error * step_ms / 1000.0, -1.0, 1.0)
        torque = _clamp(
            gains.kp * error + gains.ki * integral - gains.kd * state["omega_rad_s"],
            -12.0,
            12.0,
        )
        state, _ = simulate_limb_step(state, torque, step_ms)
        if abs(target_rad - state["theta_rad"]) <= 0.025 and abs(state["omega_rad_s"]) <= 0.08:
            settled += 1
        else:
            settled = 0
        if settled >= 5:
            return sequence + 1
    return max_steps


def _all_receipts_paired(rows: Iterable[Mapping[str, Any]]) -> bool:
    row_list = list(rows)
    request_ids = [
        str(row.get("trace_id"))
        for row in row_list
        if row.get("kind") == "effector_request"
    ]
    receipt_ids = [
        str(row.get("request_trace_id"))
        for row in row_list
        if row.get("kind") == "effector_receipt"
    ]
    return (
        bool(request_ids)
        and len(request_ids) == len(receipt_ids)
        and len(request_ids) == len(set(request_ids))
        and len(receipt_ids) == len(set(receipt_ids))
        and set(request_ids) == set(receipt_ids)
    )


def _activation_from_dict(payload: Mapping[str, Any]) -> ActivationResult:
    values = dict(payload)
    gains = values.pop("controller_gains")
    return ActivationResult(
        controller_gains=ControllerGains(
            kp=float(gains["kp"]),
            ki=float(gains["ki"]),
            kd=float(gains["kd"]),
        ),
        **values,
    )


def _resume_activation_payload(
    run_dir: Path,
    *,
    target_rad: float,
    disturbance_rad: float,
    disturbance_omega_rad_s: float,
) -> dict[str, Any]:
    simulator = StigmeroboticsLifeLoopSimulator(run_dir)
    activation = simulator.run_activation(
        target_rad=target_rad,
        disturbance_rad=disturbance_rad,
        disturbance_omega_rad_s=disturbance_omega_rad_s,
        learn=False,
    )
    return {
        "pid": os.getpid(),
        "body_instance_id": simulator.body_instance_id,
        "loaded_physics_state": simulator.loaded_physics_state,
        "trace_loaded": simulator.trace_loaded,
        "activation": activation.as_dict(),
    }


def _resume_in_fresh_interpreter(
    run_dir: Path,
    *,
    target_rad: float,
    disturbance_rad: float,
    disturbance_omega_rad_s: float,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--resume-run-dir",
        str(run_dir),
        "--target-rad",
        str(target_rad),
        "--disturbance-rad",
        str(disturbance_rad),
        "--disturbance-omega-rad-s",
        str(disturbance_omega_rad_s),
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=30.0,
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise ValueError("fresh interpreter returned a non-object result")
    return payload


def run_life_loop_experiment(output_root: Path | str) -> LifeLoopExperimentResult:
    """Run cold activation, interpreter restart, disturbance, and counterfactual."""
    output_root = Path(output_root)
    run_dir = output_root / f"run-{uuid.uuid4().hex[:12]}"
    initial_pid = os.getpid()
    first_process = StigmeroboticsLifeLoopSimulator(run_dir)
    cold = first_process.run_activation(target_rad=0.65)
    persisted_state = dict(first_process.physics_state)
    body_id = first_process.body_instance_id

    resumed_payload = _resume_in_fresh_interpreter(
        run_dir,
        target_rad=0.65,
        disturbance_rad=-0.5,
        disturbance_omega_rad_s=-1.0,
    )
    resumed_pid = int(resumed_payload["pid"])
    process_boundary_verified = resumed_pid != initial_pid
    identity_persisted = resumed_payload["body_instance_id"] == body_id
    state_persisted = resumed_payload["loaded_physics_state"] == persisted_state
    trace_loaded = bool(resumed_payload["trace_loaded"])
    resumed = _activation_from_dict(resumed_payload["activation"])
    counterfactual = _counterfactual_steps(
        persisted_state,
        target_rad=0.65,
        disturbance_rad=-0.5,
        disturbance_omega_rad_s=-1.0,
    )
    ledger_path = run_dir / LEDGER_FILENAME
    rows = _read_jsonl(ledger_path)
    trace_rows = [row for row in rows if row.get("kind") == "motor_skill_pheromone"]
    evaporation_ok = bool(trace_rows) and field_report(
        trace_rows, now_ts=time.time(), dt_s=60.0
    ).evaporation_ok
    receipt_chain_ok = _all_receipts_paired(rows)
    advantage = counterfactual - resumed.steps
    passed = all(
        (
            cold.reached_target,
            resumed.reached_target,
            cold.paired_receipts,
            resumed.paired_receipts,
            cold.sensor_grounded,
            resumed.sensor_grounded,
            identity_persisted,
            state_persisted,
            process_boundary_verified,
            trace_loaded,
            advantage > 0,
            evaporation_ok,
            receipt_chain_ok,
        )
    )
    result = LifeLoopExperimentResult(
        run_dir=str(run_dir),
        body_instance_id=body_id,
        initial_process_pid=initial_pid,
        resumed_process_pid=resumed_pid,
        process_boundary_verified=process_boundary_verified,
        cold_activation=cold,
        resumed_activation=resumed,
        counterfactual_cold_steps=counterfactual,
        trace_loaded_after_restart=trace_loaded,
        body_identity_persisted=identity_persisted,
        physical_state_persisted=state_persisted,
        recovery_advantage_steps=advantage,
        pheromone_evaporation_ok=evaporation_ok,
        receipt_chain_ok=receipt_chain_ok,
        passed=passed,
    )
    result_row = {
        "ts": time.time(),
        "kind": "life_loop_experiment_result",
        "trace_id": uuid.uuid4().hex,
        "truth_label": SIMULATION_TRUTH_LABEL,
        "body_instance_id": body_id,
        "status": "pass" if passed else "fail",
        "payload": result.as_dict(),
    }
    append_jsonl_line(ledger_path, result_row)
    append_jsonl_line(output_root / EXPERIMENT_LEDGER_FILENAME, result_row)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(".sifta_state/stigmerobotics_life_loop_runs"),
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--resume-run-dir", type=Path)
    parser.add_argument("--target-rad", type=float, default=0.65)
    parser.add_argument("--disturbance-rad", type=float, default=-0.5)
    parser.add_argument("--disturbance-omega-rad-s", type=float, default=-1.0)
    args = parser.parse_args()
    if args.resume_run_dir is not None:
        print(
            json.dumps(
                _resume_activation_payload(
                    args.resume_run_dir,
                    target_rad=args.target_rad,
                    disturbance_rad=args.disturbance_rad,
                    disturbance_omega_rad_s=args.disturbance_omega_rad_s,
                ),
                ensure_ascii=False,
            )
        )
        raise SystemExit(0)
    experiment = run_life_loop_experiment(args.output_root)
    if args.json:
        print(json.dumps(experiment.as_dict(), indent=2, ensure_ascii=False))
    else:
        print("\n".join(experiment.summary_lines()))
