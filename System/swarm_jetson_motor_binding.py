#!/usr/bin/env python3
"""
System/swarm_jetson_motor_binding.py
====================================

Hardware-safe Jetson motor binding for the SIFTA fast CPG layer.

On macOS or on Jetson without explicit arming, this module runs in simulation
and writes the exact same hash-chained receipts. Real PWM is sent only when:

  1. Jetson.GPIO imports successfully;
  2. `SIFTA_JETSON_MOTOR_ENABLE=1` is present;
  3. the requested joint is configured;
  4. the slow-field DFA state is not VETO.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from System.swarm_edge_receipts import append_chained_receipt
from System.swarm_field_to_cpg_modulator import load_latest_modulation

try:  # pragma: no cover - unavailable on the M5 dev node
    import Jetson.GPIO as GPIO  # type: ignore
    HARDWARE_AVAILABLE = True
except Exception:  # pragma: no cover - exercised as simulation in tests
    GPIO = None  # type: ignore
    HARDWARE_AVAILABLE = False


MODULE_VERSION = "2026-05-15.jetson-motor-binding.v1"
FAST_TRACE_LEDGER = "fast_layer_cpg.jsonl"
ENABLE_ENV = "SIFTA_JETSON_MOTOR_ENABLE"


@dataclass(frozen=True)
class MotorBindingConfig:
    pwm_pins: Dict[str, int] = field(
        default_factory=lambda: {
            "j0_shoulder": 32,
            "j1_elbow": 33,
            "j2_wrist": 35,
            "j3_gripper": 36,
        }
    )
    pwm_frequency_hz: float = 50.0
    neutral_duty: float = 7.5
    duty_span: float = 5.0
    min_duty: float = 2.5
    max_duty: float = 12.5
    board_mode: str = "BOARD"


_PWM_HANDLES: Dict[str, Any] = {}
_SETUP_DONE = False


def hardware_enabled() -> bool:
    return bool(HARDWARE_AVAILABLE and os.environ.get(ENABLE_ENV) == "1")


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def duty_cycle_for_value(value: float, cfg: Optional[MotorBindingConfig] = None) -> float:
    cfg = cfg or MotorBindingConfig()
    bounded = _clamp(value, -1.0, 1.0)
    duty = cfg.neutral_duty + bounded * cfg.duty_span
    return round(_clamp(duty, cfg.min_duty, cfg.max_duty), 4)


def setup(
    *,
    cfg: Optional[MotorBindingConfig] = None,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    global _SETUP_DONE
    cfg = cfg or MotorBindingConfig()
    armed = hardware_enabled()
    status = "simulation_no_jetson_gpio"
    if HARDWARE_AVAILABLE and not armed:
        status = "hardware_available_not_armed"

    if armed and not _SETUP_DONE:  # pragma: no cover - real Jetson path
        mode = getattr(GPIO, cfg.board_mode)
        GPIO.setmode(mode)
        for joint, pin in cfg.pwm_pins.items():
            GPIO.setup(pin, GPIO.OUT)
            handle = GPIO.PWM(pin, cfg.pwm_frequency_hz)
            handle.start(0)
            _PWM_HANDLES[joint] = handle
        _SETUP_DONE = True
        status = "hardware_armed"

    return append_chained_receipt(
        state_dir=state_dir,
        ledger_name=FAST_TRACE_LEDGER,
        source="swarm_jetson_motor_binding",
        event_type="FAST_LAYER_MOTOR_SETUP",
        status=status,
        ok=True,
        payload={
            "module_version": MODULE_VERSION,
            "hardware_available": HARDWARE_AVAILABLE,
            "hardware_enabled": armed,
            "pwm_frequency_hz": cfg.pwm_frequency_hz,
            "pwm_pins": cfg.pwm_pins,
            "truth_note": "Real PWM is disabled unless SIFTA_JETSON_MOTOR_ENABLE=1 and Jetson.GPIO is importable.",
        },
    )


def _send_pwm(joint: str, duty: float, cfg: MotorBindingConfig) -> None:
    if not hardware_enabled():  # pragma: no cover - guarded before call
        return
    if joint not in _PWM_HANDLES:  # pragma: no cover - real Jetson path
        setup(cfg=cfg)
    _PWM_HANDLES[joint].ChangeDutyCycle(duty)


def send_joint_command(
    joint: str,
    value: float,
    *,
    cfg: Optional[MotorBindingConfig] = None,
    state_dir: Optional[Path] = None,
    source: str = "swarm_jetson_motor_binding",
) -> Dict[str, Any]:
    cfg = cfg or MotorBindingConfig()
    bounded_value = round(_clamp(value, -1.0, 1.0), 6)
    modulation = load_latest_modulation(state_dir=state_dir)
    duty = duty_cycle_for_value(bounded_value, cfg)
    known_joint = joint in cfg.pwm_pins
    armed = hardware_enabled()
    vetoed = modulation.dfa_state == "VETO"

    intent = append_chained_receipt(
        state_dir=state_dir,
        ledger_name=FAST_TRACE_LEDGER,
        source=source,
        event_type="FAST_LAYER_MOTOR_CMD_INTENT",
        status="planned",
        ok=known_joint,
        payload={
            "module_version": MODULE_VERSION,
            "joint": joint,
            "requested_value": bounded_value,
            "duty": duty,
            "pin": cfg.pwm_pins.get(joint),
            "known_joint": known_joint,
            "hardware_available": HARDWARE_AVAILABLE,
            "hardware_enabled": armed,
            "modulation": modulation.as_dict(),
        },
    )

    if not known_joint:
        return append_chained_receipt(
            state_dir=state_dir,
            ledger_name=FAST_TRACE_LEDGER,
            source=source,
            event_type="FAST_LAYER_MOTOR_CMD",
            status="unknown_joint",
            ok=False,
            payload={
                "module_version": MODULE_VERSION,
                "parent_trace_id": intent["trace_id"],
                "joint": joint,
                "requested_value": bounded_value,
                "hardware_sent": False,
                "simulated": not armed,
                "reason": "joint_not_in_pwm_map",
            },
        )

    if vetoed:
        return append_chained_receipt(
            state_dir=state_dir,
            ledger_name=FAST_TRACE_LEDGER,
            source=source,
            event_type="FAST_LAYER_MOTOR_CMD",
            status="blocked_by_dfa_veto",
            ok=True,
            payload={
                "module_version": MODULE_VERSION,
                "parent_trace_id": intent["trace_id"],
                "joint": joint,
                "requested_value": bounded_value,
                "sent_value": 0.0,
                "duty": cfg.neutral_duty,
                "pin": cfg.pwm_pins[joint],
                "hardware_sent": False,
                "simulated": not armed,
                "modulation": modulation.as_dict(),
            },
        )

    hardware_sent = False
    send_error = ""
    if armed:
        try:  # pragma: no cover - real Jetson path
            _send_pwm(joint, duty, cfg)
            hardware_sent = True
            status = "hardware_sent"
        except Exception as exc:
            status = "hardware_send_failed"
            send_error = f"{type(exc).__name__}: {exc}"
    else:
        status = "simulated"

    return append_chained_receipt(
        state_dir=state_dir,
        ledger_name=FAST_TRACE_LEDGER,
        source=source,
        event_type="FAST_LAYER_MOTOR_CMD",
        status=status,
        ok=(not send_error),
        payload={
            "module_version": MODULE_VERSION,
            "parent_trace_id": intent["trace_id"],
            "joint": joint,
            "requested_value": bounded_value,
            "sent_value": bounded_value,
            "duty": duty,
            "pin": cfg.pwm_pins[joint],
            "hardware_sent": hardware_sent,
            "simulated": not hardware_sent,
            "error": send_error,
            "modulation": modulation.as_dict(),
        },
    )


def cleanup() -> None:
    global _SETUP_DONE
    if HARDWARE_AVAILABLE and _PWM_HANDLES:  # pragma: no cover - real Jetson path
        for handle in _PWM_HANDLES.values():
            try:
                handle.stop()
            except Exception:
                pass
        try:
            GPIO.cleanup()
        except Exception:
            pass
    _PWM_HANDLES.clear()
    _SETUP_DONE = False


__all__ = [
    "FAST_TRACE_LEDGER",
    "MotorBindingConfig",
    "cleanup",
    "duty_cycle_for_value",
    "hardware_enabled",
    "send_joint_command",
    "setup",
]


if __name__ == "__main__":
    import json

    setup_row = setup()
    cmd_row = send_joint_command("j2_wrist", 0.25)
    print(json.dumps({"setup": setup_row, "command": cmd_row}, indent=2, sort_keys=True))
