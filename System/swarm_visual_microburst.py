#!/usr/bin/env python3
"""swarm_visual_microburst.py — high-salience visual burst rule.

Architect 2026-05-14 (Vision Optimization Tournament §5):
    "The key engineering move is hybrid vision: a low-cost 64×64
    grayscale thumb computes surprise, a fallback metronome prevents
    blindness, and a micro-burst rule grants 3–5 higher-resolution
    frames only when the field says 'this matters'."

This module is the **micro-burst rule** (P1 of the tournament bracket).

Decision law (verbatim from §5 of the spec):

    if visual_token.mass > SIFTA_VISION_BURST_MASS_THRESHOLD
       or visual_token.wake_reason == "surprise"
       or visual_token.entity in high_mass_entities:
        request_micro_burst(
            frames=3..5, resolution="medium",
            privacy_tier="visual_event",
            persist_raw=False, persist_tokens=True,
        )
    else:
        stay_sparse()

Critical invariants (§7 acceptance tests):
  - "exactly one bounded micro-burst, not an infinite loop"
    → cooldown gate: after a fire, the same token (by entity) can't
       re-trigger within COOLDOWN_MS.
  - "Raw burst frames are discarded or kept only under explicit
    owner-confirmed export policy" → default `persist_raw=False`.
  - "OCR remains opt-in; surprise alone cannot silently OCR the
    desktop" → OCR is a separate flag, never triggered by mass alone.
  - "Fallback metronome still fires when delta path fails" → exposed
    as `fallback_metronome_should_fire(now, last_frame_ts)`.
  - "STGM/thermal budget records cost" → every burst receipt carries
    `stgm_cost_estimate` and `thermal_cost_estimate`.

Truth label: MICRO_BURST_V1.
Truth class: OPERATIONAL — deterministic given the input token state.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "MICRO_BURST_V1"
LEDGER_NAME = "visual_microburst_receipts.jsonl"
TRUTH_BOUNDARY = (
    "Hybrid-vision micro-burst rule. Sparse delta-eye normally; a "
    "bounded burst of 3-5 higher-resolution frames fires only when the "
    "stigmergic field says this moment matters. NOT an animal-vision "
    "claim — engineering analogue only (§20.F ceiling). Raw frames are "
    "NOT memory by default; the persistent memory is typed tokens + "
    "pheromone trails + receipts. OCR remains opt-in; mass alone "
    "cannot silently OCR the desktop."
)

# ── Defaults (tunable via SIFTA_VISION_BURST_* env vars) ─────────

DEFAULT_MASS_THRESHOLD = 0.65         # token.mass above this → burst
DEFAULT_MIN_FRAMES = 3                # spec §5: 3..5
DEFAULT_MAX_FRAMES = 5
DEFAULT_COOLDOWN_MS = 1500            # same-entity debounce
DEFAULT_BURST_MAX_DURATION_MS = 600   # cap a burst at 600 ms total
DEFAULT_FALLBACK_METRONOME_MS = 800   # static-scene fallback (§5)

# Surprise wake-reasons that should bypass the mass threshold.
SURPRISE_REASONS = frozenset({"surprise", "high_delta", "novel_face", "wake_owner"})

# Token-entity prefixes that count as "high mass" for the burst rule
# (so a known owner-face entity bursts even at lower mass).
HIGH_MASS_ENTITY_PREFIXES = ("owner_face:", "architect:", "named_person:")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# ──────────────────────────────────────────────────────────────────────
# Data
# ──────────────────────────────────────────────────────────────────────

@dataclass
class VisualToken:
    """A token in the visual field — what swimmers and the burst rule see."""
    entity: str                       # e.g. "owner_face:Ioan", "motion:cell-7"
    mass: float                       # 0..1 — salience / accumulated weight
    wake_reason: str = "static"       # static / surprise / high_delta / …
    ts: float = 0.0
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class MicroBurstPolicy:
    """Configurable thresholds for the burst rule."""
    mass_threshold: float = DEFAULT_MASS_THRESHOLD
    min_frames: int = DEFAULT_MIN_FRAMES
    max_frames: int = DEFAULT_MAX_FRAMES
    cooldown_ms: int = DEFAULT_COOLDOWN_MS
    burst_max_duration_ms: int = DEFAULT_BURST_MAX_DURATION_MS
    fallback_metronome_ms: int = DEFAULT_FALLBACK_METRONOME_MS

    @classmethod
    def from_env(cls) -> "MicroBurstPolicy":
        return cls(
            mass_threshold=_env_float(
                "SIFTA_VISION_BURST_MASS_THRESHOLD", DEFAULT_MASS_THRESHOLD,
            ),
            min_frames=_env_int(
                "SIFTA_VISION_BURST_MIN_FRAMES", DEFAULT_MIN_FRAMES,
            ),
            max_frames=_env_int(
                "SIFTA_VISION_BURST_MAX_FRAMES", DEFAULT_MAX_FRAMES,
            ),
            cooldown_ms=_env_int(
                "SIFTA_VISION_BURST_COOLDOWN_MS", DEFAULT_COOLDOWN_MS,
            ),
            burst_max_duration_ms=_env_int(
                "SIFTA_VISION_BURST_MAX_DURATION_MS", DEFAULT_BURST_MAX_DURATION_MS,
            ),
            fallback_metronome_ms=_env_int(
                "SIFTA_VISION_FALLBACK_METRONOME_MS", DEFAULT_FALLBACK_METRONOME_MS,
            ),
        )


@dataclass
class VisualBurstRequest:
    """A bounded request to burst-capture a few extra frames."""
    trigger_entity: str
    trigger_reason: str               # mass | surprise | high_mass_entity
    frames: int
    max_duration_ms: int
    resolution: str = "medium"        # spec §5
    privacy_tier: str = "visual_event"
    persist_raw: bool = False         # §7 acceptance: default discard
    persist_tokens: bool = True
    ocr_allowed: bool = False         # §7: OCR is opt-in, never silent
    trigger_token_mass: float = 0.0
    stgm_cost_estimate: float = 0.05  # OPERATIONAL units, not money
    thermal_cost_estimate: float = 0.03
    truth_label: str = TRUTH_LABEL
    truth_class: str = "OPERATIONAL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────
# State — last-fire timestamps per entity for cooldown
# ──────────────────────────────────────────────────────────────────────

class BurstScheduler:
    """Holds per-entity cooldowns + serves the should_burst decision.

    A new scheduler instance can be created per process; the cooldown
    map is in-memory. The receipt ledger on disk is the durable
    history; the scheduler is just the live debounce layer.
    """

    def __init__(self, policy: Optional[MicroBurstPolicy] = None) -> None:
        self.policy = policy or MicroBurstPolicy.from_env()
        # entity → last fire ts (seconds)
        self._last_fire_ts: dict[str, float] = {}
        # global counter for sanity / receipts
        self.total_fires = 0
        self.total_suppressed_by_cooldown = 0
        self.total_suppressed_by_threshold = 0
        self.last_token_inspected_ts: float = 0.0

    # ── Decision ───────────────────────────────────────────────

    def should_burst(
        self, token: VisualToken, *, now: Optional[float] = None,
    ) -> tuple[bool, str]:
        """Return (fire?, reason). Reason is one of:
          mass | surprise | high_mass_entity | cooldown_suppressed |
          below_threshold | empty_entity
        """
        moment = now if now is not None else time.time()
        self.last_token_inspected_ts = moment
        if not token or not token.entity:
            return False, "empty_entity"
        # Cooldown — most important; ensures no infinite loop on a
        # token that stays "hot" for multiple ticks.
        last_fire = self._last_fire_ts.get(token.entity, 0.0)
        if (moment - last_fire) * 1000.0 < self.policy.cooldown_ms:
            self.total_suppressed_by_cooldown += 1
            return False, "cooldown_suppressed"
        # Three independent fire conditions (any one wins).
        # 1. Mass above threshold.
        if token.mass >= self.policy.mass_threshold:
            return True, "mass"
        # 2. Wake reason flagged as surprise-like.
        if token.wake_reason in SURPRISE_REASONS:
            return True, "surprise"
        # 3. Entity is a known high-mass class (owner, architect, etc).
        if any(token.entity.startswith(p) for p in HIGH_MASS_ENTITY_PREFIXES):
            return True, "high_mass_entity"
        self.total_suppressed_by_threshold += 1
        return False, "below_threshold"

    def mark_fired(self, entity: str, *, now: Optional[float] = None) -> None:
        """Record that a burst has fired for `entity` so the cooldown
        gate suppresses immediate re-triggers."""
        self._last_fire_ts[entity] = now if now is not None else time.time()
        self.total_fires += 1

    # ── Fallback metronome ────────────────────────────────────

    def fallback_metronome_should_fire(
        self, *, now: Optional[float] = None, last_frame_ts: float = 0.0,
    ) -> bool:
        """When the delta-eye path has been silent for too long
        (camera worker stuck, black frames, exception), this returns
        True so the host knows to grab a single sparse frame to keep
        the eye alive."""
        moment = now if now is not None else time.time()
        return (moment - last_frame_ts) * 1000.0 >= self.policy.fallback_metronome_ms

    # ── Build a burst request from a token ────────────────────

    def make_request(
        self, token: VisualToken, reason: str,
        *,
        persist_raw: bool = False,
        ocr_allowed: bool = False,
        frames: Optional[int] = None,
    ) -> VisualBurstRequest:
        """Construct a bounded request. `frames` is clamped to the
        policy's [min, max] interval. Privacy defaults are strict."""
        n_frames = frames if frames is not None else self.policy.max_frames
        n_frames = max(self.policy.min_frames,
                       min(self.policy.max_frames, n_frames))
        return VisualBurstRequest(
            trigger_entity=token.entity,
            trigger_reason=reason,
            frames=n_frames,
            max_duration_ms=self.policy.burst_max_duration_ms,
            resolution="medium",
            privacy_tier="visual_event",
            persist_raw=bool(persist_raw),
            persist_tokens=True,
            ocr_allowed=bool(ocr_allowed),
            trigger_token_mass=float(token.mass),
            stgm_cost_estimate=0.04 + 0.02 * n_frames,
            thermal_cost_estimate=0.02 + 0.015 * n_frames,
        )


# ──────────────────────────────────────────────────────────────────────
# Receipts
# ──────────────────────────────────────────────────────────────────────

def write_burst_receipt(
    request: VisualBurstRequest,
    *,
    outcome: str = "fired",        # fired | suppressed_cooldown | suppressed_threshold
    state_root: str | Path | None = None,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Append a signed receipt for this burst decision to the ledger."""
    state = Path(state_root) if state_root else _STATE
    state.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "truth_label": request.truth_label,
        "truth_class": request.truth_class,
        "outcome": outcome,
        **request.to_dict(),
    }
    if extra:
        payload["extra"] = extra
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "MICRO_BURST",
        "trace_id": str(uuid.uuid4()),
        "truth_label": request.truth_label,
        "truth_class": request.truth_class,
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "payload": payload,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


# ──────────────────────────────────────────────────────────────────────
# High-level evaluate_token API — what callers actually use
# ──────────────────────────────────────────────────────────────────────

def evaluate_token(
    scheduler: BurstScheduler,
    token: VisualToken,
    *,
    now: Optional[float] = None,
    persist_raw: bool = False,
    ocr_allowed: bool = False,
    write_receipt: bool = True,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    """Full evaluation cycle for a single token.

    Returns a dict with:
      - fired: bool
      - reason: str (mass / surprise / high_mass_entity / below_threshold / cooldown)
      - request: VisualBurstRequest dict OR None
      - receipt_id: str if a receipt was written
    """
    fire, reason = scheduler.should_burst(token, now=now)
    out: dict[str, Any] = {"fired": fire, "reason": reason, "request": None}
    if fire:
        req = scheduler.make_request(
            token, reason,
            persist_raw=persist_raw,
            ocr_allowed=ocr_allowed,
        )
        scheduler.mark_fired(token.entity, now=now)
        out["request"] = req.to_dict()
        if write_receipt:
            row = write_burst_receipt(
                req, outcome="fired", state_root=state_root,
            )
            out["receipt_id"] = row["trace_id"]
            out["sha256"] = row["sha256"]
    return out


# ──────────────────────────────────────────────────────────────────────
# CLI — quick sanity check
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--entity", type=str, default="motion:demo")
    p.add_argument("--mass", type=float, default=0.8)
    p.add_argument("--reason", type=str, default="surprise")
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()
    sched = BurstScheduler()
    tok = VisualToken(entity=args.entity, mass=args.mass, wake_reason=args.reason,
                      ts=time.time())
    out = evaluate_token(sched, tok, write_receipt=not args.no_write)
    print(json.dumps(out, indent=2, default=str))
