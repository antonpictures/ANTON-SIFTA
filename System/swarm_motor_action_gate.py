"""Model-independent checks for the two-joint SIMULATED lab, not a motor driver."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PlanProposal:
    sequence: int
    observed_at_s: float | None
    desired_joints: tuple[float, float] | None
    truth_label: str = "SIMULATED"


@dataclass(frozen=True)
class ActionDecision:
    sequence: int
    status: str
    command_rad_s: tuple[float, float] = (0.0, 0.0)
    truth_label: str = "SIMULATED"


@dataclass(frozen=True)
class ActionOutcome:
    sequence: int
    status: str
    command_rad_s: tuple[float, float]
    joint_echo: tuple[float, float]
    tracking_error_m: float
    truth_label: str = "SIMULATED"


def _number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def _pair(value):
    return (isinstance(value, (tuple, list)) and len(value) == 2
            and all(_number(v) for v in value))


class MotorActionGate:
    """Single-threaded, run-local sequencing. Stop is latched until explicit reset.

    No network, STGM, driver, or LLM calls. Retries produce zero motion rather
    than replaying a previously approved command. A new instance starts a new
    simulated run; this is not restart-safe hardware deduplication.
    """

    def __init__(self, *, max_speed=1.5, joint_limit=2.8, max_age=.30, max_dt=.1):
        if not all(_number(v) and v > 0 for v in
                   (max_speed, joint_limit, max_age, max_dt)):
            raise ValueError("finite positive limits required")
        self.max_speed, self.joint_limit = max_speed, joint_limit
        self.max_age, self.max_dt = max_age, max_dt
        self.last_sequence = -1
        self.stopped = False

    def stop(self):
        self.stopped = True

    def reset_stop(self):
        # Sequence history survives reset, so queued old commands cannot replay.
        self.stopped = False

    def decide(self, proposal: PlanProposal, *, now_s, joints, dt) -> ActionDecision:
        def hold(status):
            return ActionDecision(proposal.sequence, status)

        if type(proposal.sequence) is not int or proposal.sequence < 0:
            return hold("REJECT_INVALID_SEQUENCE")
        if proposal.sequence <= self.last_sequence:
            return hold("HOLD_REPLAY")
        self.last_sequence = proposal.sequence
        if self.stopped:
            return hold("HOLD_STOP")
        if proposal.truth_label != "SIMULATED":
            return hold("REJECT_MODE")
        if (not _pair(joints) or not _number(now_s)
                or not _number(dt) or not 0 < dt <= self.max_dt
                or any(abs(q) > self.joint_limit for q in joints)):
            return hold("REJECT_STATE")
        stamp = proposal.observed_at_s
        if not _number(stamp) or now_s - stamp > self.max_age:
            return hold("HOLD_STALE")
        if stamp > now_s:
            return hold("REJECT_FUTURE_OBSERVATION")
        target = proposal.desired_joints
        if target is None:
            return hold("REJECT_UNREACHABLE")
        if not _pair(target) or any(abs(q) > self.joint_limit for q in target):
            return hold("REJECT_TARGET")
        raw = tuple(4.0 * (goal - pos) for goal, pos in zip(target, joints))
        # Bound the command itself, not only the resulting simulated pose.
        command = tuple(max(-self.max_speed, (-self.joint_limit - pos) / dt,
                            min(self.max_speed, (self.joint_limit - pos) / dt, v))
                        for pos, v in zip(joints, raw))
        return ActionDecision(proposal.sequence, "LIMITED" if command != raw else "APPLIED", command)
