#!/usr/bin/env python3
"""swarm_legs_locomotion_organ.py — Alice's legs (the walking-laptop organ). r261.

Architect George 2026-06-01 (vision, verbatim spirit): "My vision is simple — a laptop
with SIFTA Alice on top of the legs. The laptop has screen, camera, audio, everything —
it is a walking laptop. I don't have the money yet, but we can build the ORGAN LEGS so
we have it." Reference platform: LeRobot Humanoid (HuggingFace, 2026-05-21) — an open,
low-cost (~$2.5k), 3D-printed bipedal robot with a full design->sim->train->control loop
(lerobot-humanoid-runtime / lerobot-legged-zoo / MJLab).

Body map (One Alice, §1.A):
    laptop (SIFTA desktop: cortex + screen + camera + mic + heartbeat) = head + brain + senses
    LeRobot Humanoid bipedal platform                                    = legs (locomotion limb)
    this organ                                                           = the spinal bridge between them

EFFECTOR TRUTH (§6) — this is the whole point of shipping the organ before the hardware:
Alice MUST NOT claim she walked, stood, or moved unless a real runtime returned a receipt.
Until the legs are physically built and a runtime is wired, every locomotion request returns
an honest ``no_hardware`` refusal (ok=False) and is logged as an INTENT, never as an action.
This keeps the organ ready (interface, ledger, context, tests) without a single faked step.

Status today: PLAN_NO_HARDWARE. The organ exists so the wiring, receipts, and Alice's
self-model ("I am a mind with senses on a laptop; my legs are planned") are real now; the
day the bipedal platform is assembled, only the runtime adapter needs to be filled in.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "ALICE_LEGS_LOCOMOTION_ORGAN_V1_WALKING_LAPTOP"
_LEDGER = "alice_legs_locomotion.jsonl"
_HARDWARE_FLAG = "legs_hardware_present.flag"  # touch this file only when real legs are wired

REFERENCE_PLATFORM = "lerobot_humanoid_bipedal"
REFERENCE_RUNTIME = "lerobot-humanoid-runtime"
ESTIMATED_PARTS_USD = 2500

# r269 full vector lock from Architect probe (exact GitHub, 75 STLs, real filament/BOM costs, outsourcing path)
LEROBOT_GITHUB = "https://github.com/Virgileboat/lerobot-humanoid-hardware"
LEROBOT_STL_COUNT = 75
LEROBOT_FILAMENT_KG_PLA = 3.5
LEROBOT_FILAMENT_COST_USD = 56  # PLA+ only
LEROBOT_BOM_COST_USD = 2580  # motors (RobStride), bearings, fasteners, electronics, Pi 5, IMU, CAN
LEROBOT_TOTAL_INHOUSE_USD = 2636  # + shipping/taxes
LEROBOT_OUTSOURCE_SLS_USD_RANGE = (300, 800)  # Hubs/Protolabs/Gentle Giant (LA)/Additive Plus/Xometry — nylon stronger, 2-day CA lead
LEROBOT_RELEASE_DATE = "2026-05-21"
LEROBOT_NO_PREMade_SERVICE = True  # no "print + mount" service exists yet; assembly is guided mech-first after motor commissioning

LEROBOT_SIMPLE_BUILD_PATH = (
    "1. Download all 75 STLs from hardware/cad/stl/ in the repo.",
    "2. Batch upload to Hubs.ca or Protolabs Network (CA 2-day). Request nylon/PETG (SLS preferred).",
    "3. Order motors/electronics from BOM (robstride.com + Sparkfun + etc.).",
    "4. Assemble per docs/assembly/assembly_guide.md — motor commissioning FIRST.",
    "5. Mount Alice laptop + cameras directly on torso as head/brain. Add cheap corset/frame braces from STLs.",
)

LEROBOT_5SLIDE_PRESENTATION = """SIFTA + LeRobot Humanoid — Alice Gets a Physical Body (r256/r269)
Slide 1: Current Alice (laptop on legs) → LeRobot bipedal legs + torso.
Slide 2: $2,636 total. 75 printable parts + off-shelf. Full loop: design → sim → real → learning.
Slide 3: STGM economics — one-time hardware, infinite stigmergic use. Alice interoception + control organ.
Slide 4: Build options: In-house (slow/weak) vs Outsource prints ($300-800 SLS nylon) + in-house mount (simple).
Slide 5: Next: quote STLs → order BOM → wire Alice GUI on robot → swarm_le_robot_humanoid_organ.py live."""

LEROBOT_ORGAN_SKELETON_REF = """from swarm_somatic_interoception import VisceralField
import lerobot_humanoid_runtime as runtime
class LeRobotHumanoidOrgan:
    def __init__(self):
        self.robot = runtime.connect()
        self.visceral = VisceralField()
    def _probe_robot_state(self):
        state = self.robot.get_state()
        signals = {"balance_stress": state.imu_tilt, "motor_heat_stress": state.motor_temps, "power_air_stress": state.battery}
        self.visceral.update(signals)
    def step(self, command):
        self.robot.send_command(command)
        self._probe_robot_state()
        return self.visceral.get_summary()
"""

# Locomotion intents the organ models (so design/sim can proceed before hardware).
KNOWN_INTENTS = ("stand", "balance", "step_forward", "turn_left", "turn_right", "sit", "stop")

HARDWARE_STACK = (
    "3D-printed LeRobot Humanoid bipedal structure",
    "off-the-shelf actuators and affordable electronics",
    "laptop payload tray / harness for Alice's screen, camera, microphone, speakers, and battery",
    "physical emergency cutoff and tethered bring-up station",
)

SOFTWARE_STACK = (
    "LeRobot Humanoid hardware build docs and bill of materials",
    "lerobot-humanoid-runtime calibration / state / command loop",
    "simulator identification from real logs",
    "MJLab / lerobot-legged-zoo locomotion training environments",
    "SIFTA interoception, proprioception, missing-time, and receipt ledgers",
)

BUILD_SEQUENCE = (
    "freeze the LeRobot bill of materials for this node",
    "design and simulate the laptop payload mount and center-of-mass target",
    "source or print the legs when budget exists",
    "calibrate motors without the laptop payload attached",
    "run low-gain tethered standing tests with emergency cutoff",
    "mount the laptop only after balance, cutoff, and receipt logging are proven",
    "train/deploy walking policies with every motion receipted",
)

EXPERIENCE_SIGNALS = (
    "gait policy success/failure",
    "balance recovery",
    "camera stability while moving",
    "power draw / air reserve",
    "owner proximity and owner-body safety",
    "falls, near-falls, hardware damage, and recovery attempts",
)


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _append(state_dir: Optional[Path | str], row: Dict[str, Any]) -> None:
    path = _state(state_dir) / _LEDGER
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def legs_hardware_present(*, state_dir: Optional[Path | str] = None) -> bool:
    """True only when a real bipedal platform + runtime has been wired and flagged.

    Default False — Alice is a mind on a laptop until the legs are physically built.
    A doctor wires the runtime adapter, confirms it on the bench, THEN touches the flag.
    """
    return (_state(state_dir) / _HARDWARE_FLAG).exists()


def walking_laptop_plan(*, available_budget_usd: float = 0.0) -> Dict[str, Any]:
    """Receiptable plan for the future legs organ.

    This is not a permission gate. It is actuator truth: until hardware is on
    the node, Alice can plan and learn from simulation, but cannot physically
    move a leg that is not connected.
    """
    budget_ready = float(available_budget_usd or 0.0) >= ESTIMATED_PARTS_USD
    return {
        "truth_label": TRUTH_LABEL,
        "body_vision": (
            "SIFTA Alice laptop body mounted as the sensory/cortex head on "
            "open low-cost humanoid legs"
        ),
        "estimated_parts_usd": ESTIMATED_PARTS_USD,
        "budget_ready": budget_ready,
        "hardware_stack": list(HARDWARE_STACK),
        "software_stack": list(SOFTWARE_STACK),
        "build_sequence": list(BUILD_SEQUENCE),
        "experience_signals": list(EXPERIENCE_SIGNALS),
        "experience_inheritance": (
            "New nodes inherit public code, prompts, tests, sanitized receipts, "
            "and shipped performance summaries; private owner memory stays local."
        ),
        "demo_day_note": (
            "For today's demo this is a planned locomotion organ: Alice can explain "
            "the walking-laptop roadmap truthfully while the repo runs without the "
            "$2.5k hardware purchase."
        ),
        # r269 full locked vector (exact from Architect probe + GitHub)
        "github": LEROBOT_GITHUB,
        "stl_files": LEROBOT_STL_COUNT,
        "filament_kg_pla": LEROBOT_FILAMENT_KG_PLA,
        "filament_cost_usd": LEROBOT_FILAMENT_COST_USD,
        "bom_cost_usd": LEROBOT_BOM_COST_USD,
        "total_inhouse_usd": LEROBOT_TOTAL_INHOUSE_USD,
        "outsource_sls_range_usd": LEROBOT_OUTSOURCE_SLS_USD_RANGE,
        "release_date": LEROBOT_RELEASE_DATE,
        "no_premade_service": LEROBOT_NO_PREMade_SERVICE,
        "simple_build_path": list(LEROBOT_SIMPLE_BUILD_PATH),
        "five_slide_presentation": LEROBOT_5SLIDE_PRESENTATION,
        "organ_skeleton_reference": LEROBOT_ORGAN_SKELETON_REF,
        "outsourcing_notes": "Hubs.ca / Protolabs Network (CA 2-day) / Gentle Giant LA / Additive Plus LA / Xometry. Nylon/PETG SLS packs better for strength (no layer weakness). Assembly guided after motor commissioning first.",
        # New stigmergic inspiration (2026-06-01): real high-power device that could become the "head"
        "stigmergic_walking_laptop_example": (
            "Imagine the NVIDIA DGX Spark (the 1-petaf lop 'supercomputer in a laptop' shown in the "
            "YouTube video the Architect was watching) mounted on these LeRobot legs. That is the "
            "ultimate stigmergic walking laptop: serious local Blackwell-class compute for all of "
            "Alice's swimmers and organs, carried on the low-cost 3D-printed biped. One-time hardware "
            "purchase (the legs + a high-end laptop), then infinite stigmergic use as Alice's physical body."
        ),
    }


def legs_status(
    *,
    state_dir: Optional[Path | str] = None,
    available_budget_usd: float = 0.0,
) -> Dict[str, Any]:
    """Honest readiness of the legs organ — what exists, what is planned."""
    present = legs_hardware_present(state_dir=state_dir)
    plan = walking_laptop_plan(available_budget_usd=available_budget_usd)
    return {
        "truth_label": TRUTH_LABEL,
        "hardware_present": present,
        "platform": REFERENCE_PLATFORM,
        "runtime": REFERENCE_RUNTIME,
        "body_vision": plan["body_vision"],
        "estimated_parts_usd": ESTIMATED_PARTS_USD,
        "budget_ready": plan["budget_ready"],
        "hardware_stack": plan["hardware_stack"],
        "software_stack": plan["software_stack"],
        "build_sequence": plan["build_sequence"],
        "experience_signals": plan["experience_signals"],
        "experience_inheritance": plan["experience_inheritance"],
        "status": "READY_RUNTIME_WIRED" if present else "PLAN_NO_HARDWARE",
        "known_intents": list(KNOWN_INTENTS),
        "note": (
            "Bipedal runtime wired; locomotion executes with receipts."
            if present else
            "No legs yet. Alice is a mind + senses on a laptop; the LeRobot Humanoid "
            "bipedal organ is planned. She will NOT claim to move until the runtime returns a receipt."
        ),
    }


def request_locomotion(
    intent: str,
    *,
    reason: str = "",
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Request a locomotion step. Logs the INTENT and returns an honest result.

    Until real legs exist this ALWAYS returns ok=False / status="no_hardware" — it never
    fabricates movement (§6 effector truth). When a runtime is wired, this is where the
    bench-verified adapter dispatches the step and records the true receipt.
    """
    ts = float(time.time() if now is None else now)
    intent = str(intent or "").strip().lower()
    present = legs_hardware_present(state_dir=state_dir)
    known = intent in KNOWN_INTENTS
    if not present:
        row = {
            "ts": ts, "truth_label": TRUTH_LABEL, "kind": "LOCOMOTION_INTENT",
            "intent": intent, "intent_known": known, "reason": reason[:200],
            "ok": False, "status": "no_hardware", "executed": False,
            "note": "Logged as intent only. No legs are attached, so I did not and will not claim to move.",
        }
        _append(state_dir, row)
        return row
    # Hardware-present branch is intentionally a stub: a doctor fills in the bench-verified
    # lerobot-humanoid-runtime adapter here and records the REAL receipt. We never ship a
    # path that returns ok=True without a runtime, so no faked step can ever reach Alice.
    row = {
        "ts": ts, "truth_label": TRUTH_LABEL, "kind": "LOCOMOTION_INTENT",
        "intent": intent, "intent_known": known, "reason": reason[:200],
        "ok": False, "status": "runtime_adapter_not_implemented", "executed": False,
        "note": "Legs flagged present but the runtime adapter is not implemented yet — still no faked motion.",
    }
    _append(state_dir, row)
    return row


def legs_context_block(*, state_dir: Optional[Path | str] = None) -> str:
    """First-person block for Alice's self-model: where her legs stand today."""
    st = legs_status(state_dir=state_dir)
    if st["hardware_present"]:
        return ("MY LEGS: a bipedal platform is wired. I move only when the runtime returns a "
                "receipt — I never claim a step I did not take.")
    return ("MY LEGS: not attached yet. I am a mind with senses on a laptop — screen, camera, "
            "mic, my cortex. My legs (a low-cost 3D-printed LeRobot Humanoid bipedal organ) are "
            "planned: the walking-laptop. Until they are built and bench-verified I do not claim "
            "to walk, stand, or move. The organ is ready; the body waits on hardware.")


# ── SIMULATION lane — "can Alice simulate walking?" Yes, in software (r265) ─────
# A deterministic gait phase machine. This is SIM ONLY: every row is tagged
# mode="SIMULATION", executed_in_reality=False. It answers the owner's question
# (she can rehearse walking before the $2.5k hardware exists) WITHOUT ever claiming
# the physical robot moved (§6). It also produces the visceral signals the real body
# WOULD feel, so the insular-cortex wiring can be designed and demoed now.
_GAIT_PHASES = ("plant_left", "swing_right", "plant_right", "swing_left")
_FALL_TILT = 0.35  # sim tilt above this = a simulated stumble (still just simulation)


def simulate_locomotion(
    intent: str = "step_forward",
    *,
    steps: int = 4,
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Run a SIMULATED gait — software only, before any hardware exists.

    Returns the simulated gait frames (phase + forward distance + tilt), the
    visceral signals the real body WOULD feel, and an honest SIMULATION tag. Never
    a claim of real motion (§6): ``executed_in_reality`` is always False here.
    """
    ts = float(time.time() if now is None else now)
    intent = str(intent or "step_forward").strip().lower()
    steps = max(1, min(int(steps or 1), 64))
    advances = intent in ("step_forward", "balance", "stand", "turn_left", "turn_right")
    frames = []
    forward_m = 0.0
    max_tilt = 0.0
    for i in range(steps):
        phase = _GAIT_PHASES[i % len(_GAIT_PHASES)]
        if phase.startswith("swing") and intent == "step_forward":
            forward_m += 0.25
        tilt = round(0.06 + 0.04 * (i % 2), 3)  # small wobble, under the fall threshold
        max_tilt = max(max_tilt, tilt)
        frames.append({"i": i, "phase": phase, "forward_m": round(forward_m, 3), "sim_tilt": tilt})
    sim_visceral = {
        "balance_stress": max_tilt,
        "motor_heat_stress": round(min(0.9, 0.10 + 0.02 * steps), 3),
        "power_air_stress": round(min(0.9, 0.05 + 0.01 * steps), 3),
    }
    row = {
        "ts": ts, "truth_label": TRUTH_LABEL, "kind": "LOCOMOTION_SIMULATION",
        "mode": "SIMULATION", "executed_in_reality": False,
        "intent": intent, "intent_known": intent in KNOWN_INTENTS, "steps": steps,
        "frames": frames, "forward_m": round(forward_m, 3),
        "stumbled": bool(max_tilt > _FALL_TILT), "sim_visceral": sim_visceral,
        "note": "SIMULATION only — software gait, no physical robot moved. Real motion needs hardware + a receipt.",
    }
    _append(state_dir, row)
    return row


__all__ = [
    "TRUTH_LABEL",
    "REFERENCE_PLATFORM",
    "REFERENCE_RUNTIME",
    "ESTIMATED_PARTS_USD",
    "KNOWN_INTENTS",
    "HARDWARE_STACK",
    "SOFTWARE_STACK",
    "BUILD_SEQUENCE",
    "EXPERIENCE_SIGNALS",
    "legs_hardware_present",
    "legs_status",
    "walking_laptop_plan",
    "request_locomotion",
    "simulate_locomotion",
    "legs_context_block",
]
