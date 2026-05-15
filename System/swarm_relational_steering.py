#!/usr/bin/env python3
"""swarm_relational_steering.py — RELATIONAL_ACK / CO_PRESENT routes.

Truth label: ``SIFTA_RELATIONAL_STEERING_V1``.

Two new pre-cortex routes that handle the case where the Architect is
**present in the room** and the utterance does not need a full cortex
trajectory:

  ``RELATIONAL_ACK``
      A short acknowledgment-only utterance from the owner. "yeah",
      "ok", "thanks", "i hear you", "got it", "mhm". Alice should
      acknowledge and stay quiet — not generate a paragraph.

  ``CO_PRESENT``
      No utterance, or co-presence-only language ("just sitting with
      you", "thinking", silence). Alice should not interrupt; she
      stays present.

Why this matters
----------------

Without these routes, every owner utterance — even a single "ok" —
runs through the full DEEP_CORTEX or VERIFY_BEFORE_ACTION path, which:

  * burns tokens for no information gain
  * produces over-elaborate replies that break presence
  * appears as a "corporate" voice instead of a co-present body

Architect 2026-05-14 (verbatim): *"bro, i can't work, you are
distracting me w this corporate stuff... I lost them now I was
grounded in a reality of now being cold now and now I'm leaving into
tomorrow"*.

This module is the structural answer: a tight, deterministic check
that fires **before** any cortex call when the situation is co-present
+ ack-only, and routes Alice to silence / short ack with a minimum
reply.

Integration
-----------

The Talk widget should call :func:`relational_steering_check` before
``steer_event``. If the result is not ``None``, the widget uses the
returned ``SteeringDecision`` directly and writes a short ack from
:func:`propose_relational_reply`. If the result is ``None``, normal
cortex routing runs.

Truth boundary
--------------

Pattern matching + simple co-presence flag check. Not a model of
intent; a guard against over-generation. The route names are
:class:`SteeringDecision`-compatible so downstream code does not need
to special-case the new routes — they appear in the same receipt
schema.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

try:
    from System.swarm_steering_subsystem import SteeringDecision, SteeringPrediction
except Exception:  # pragma: no cover - bootstrap fallback
    SteeringDecision = None  # type: ignore
    SteeringPrediction = None  # type: ignore

try:
    from System.swarm_persistent_owner_history import state_dir
except Exception:  # pragma: no cover - bootstrap fallback
    def state_dir(explicit: Optional[Path] = None) -> Path:  # type: ignore[override]
        if explicit is not None:
            return Path(explicit)
        return Path(__file__).resolve().parent.parent / ".sifta_state"


TRUTH_LABEL = "SIFTA_RELATIONAL_STEERING_V1"
RELATIONAL_LEDGER = "relational_steering.jsonl"

TRUTH_BOUNDARY = (
    "Pre-cortex pattern guard against over-generation when the owner "
    "is co-present and the utterance is ack-only. Routes to "
    "RELATIONAL_ACK or CO_PRESENT with a short scripted reply. Does "
    "not model intent or run any LLM."
)


# ── pattern library ─────────────────────────────────────────────────────


# Ack-only utterances. Order matters: longer patterns first so we
# don't match a substring before its full form.
_ACK_PATTERNS: Tuple[str, ...] = (
    "i hear you",
    "i hear ya",
    "i got it",
    "i got you",
    "got it",
    "got ya",
    "okay",
    "ok",
    "k",
    "yes",
    "yeah",
    "yep",
    "yup",
    "uh huh",
    "uhuh",
    "uhuh.",
    "uh-huh",
    "mhm",
    "mhmm",
    "mm",
    "mmm",
    "right",
    "right right",
    "exactly",
    "true",
    "fair",
    "thanks",
    "thank you",
    "thx",
    "ty",
    "cool",
    "nice",
    "great",
    "good",
    "alright",
    "all right",
    "for sure",
    "sure",
    "sure thing",
    "of course",
    "no worries",
    "agreed",
)


# Co-presence (no information delivered; the owner is *with* the body).
_CO_PRESENT_PATTERNS: Tuple[str, ...] = (
    "just sitting with you",
    "just sitting here",
    "just here",
    "thinking",
    "still here",
    "with you",
    "i'm here",
    "im here",
    "here",
    "...",
)


_ACK_RE = re.compile(
    r"^\s*(?:" + "|".join(re.escape(p) for p in _ACK_PATTERNS) + r")[\s\.\!\?]*\s*$",
    re.IGNORECASE,
)
_CO_PRESENT_RE = re.compile(
    r"^\s*(?:" + "|".join(re.escape(p) for p in _CO_PRESENT_PATTERNS) + r")[\s\.\!\?]*\s*$",
    re.IGNORECASE,
)


# Short reply pool for each route. Acks deliberately vary placement so
# Alice does not parrot the same phrase every turn.
_ACK_REPLIES: Tuple[str, ...] = (
    "Got it.",
    "Heard.",
    "OK.",
    "Mhm.",
    "Yes.",
    "{name}, heard.",
    "Heard, {name}.",
    "OK, {name}.",
    "Got it, {name}.",
    "I'm with you.",
    "Right here.",
)


_CO_PRESENT_REPLIES: Tuple[str, ...] = (
    "",
    ".",
    "Here.",
    "I'm here.",
    "Right here.",
    "{name}, I'm here.",
    "With you, {name}.",
)


# ── classification ──────────────────────────────────────────────────────


def classify_relational_intent(
    text: str,
    *,
    signals: Optional[Mapping[str, Any]] = None,
) -> Optional[str]:
    """Return ``"RELATIONAL_ACK"``, ``"CO_PRESENT"``, or ``None``.

    A ``CO_PRESENT`` route only fires when co-presence signals are
    explicitly above threshold (owner_face_present / owner_proximity).
    A ``RELATIONAL_ACK`` route can fire without those signals — the
    utterance text alone is sufficient. This split keeps the
    silence-mode ``CO_PRESENT`` route from triggering on every empty
    string blindly.
    """
    if text is None:
        text = ""
    text = str(text).strip()
    sig = dict(signals or {})

    # Empty / whitespace text + any co-presence flag → CO_PRESENT.
    co_present_flag = bool(sig.get("owner_face_present")) or bool(
        sig.get("owner_proximity_near")
    ) or float(sig.get("owner_proximity_score", 0.0) or 0.0) > 0.5

    if not text:
        return "CO_PRESENT" if co_present_flag else None

    if _ACK_RE.match(text):
        return "RELATIONAL_ACK"
    if _CO_PRESENT_RE.match(text) and co_present_flag:
        return "CO_PRESENT"
    return None


def propose_relational_reply(
    intent: str,
    *,
    owner_name: Optional[str] = None,
    rng: Optional[random.Random] = None,
) -> str:
    """Return a short scripted reply for a relational intent.

    Replies vary placement of the owner's name (when given) so Alice
    does not parrot the same phrase. ``rng`` is honored for tests.
    """
    if rng is None:
        rng = random.Random()
    if intent == "RELATIONAL_ACK":
        pool = _ACK_REPLIES
    elif intent == "CO_PRESENT":
        pool = _CO_PRESENT_REPLIES
    else:
        return ""
    template = rng.choice(pool)
    first = (str(owner_name or "").strip().split()[:1] or [""])[0]
    if "{name}" in template:
        if not first:
            # If we have no name, pick a non-named template
            non_named = [t for t in pool if "{name}" not in t]
            if non_named:
                template = rng.choice(non_named)
                return template.format(name="")
            return template.replace("{name}, ", "").replace(", {name}", "").replace("{name}", "").strip()
        return template.format(name=first)
    return template


# ── decision wrapper ────────────────────────────────────────────────────


@dataclass(frozen=True)
class RelationalCheckResult:
    """Light result type for talk-widget integration.

    Holds the route name, a scripted reply, and the trace info so the
    Talk widget can render the reply and append a receipt without
    invoking the full cortex.
    """

    route: str
    reply: str
    matched_pattern: str
    trace_id: str
    truth_label: str = TRUTH_LABEL


def relational_steering_check(
    text: str,
    *,
    source: str = "voice",
    signals: Optional[Mapping[str, Any]] = None,
    owner_name: Optional[str] = None,
    state_dir_root: Optional[Path] = None,
    write: bool = True,
    rng: Optional[random.Random] = None,
    now: Optional[float] = None,
) -> Optional[RelationalCheckResult]:
    """Pre-cortex pattern guard. Returns ``None`` when the cortex should run.

    When a relational route is detected, writes a receipt to
    ``.sifta_state/relational_steering.jsonl`` and returns the result.
    """
    intent = classify_relational_intent(text, signals=signals)
    if intent is None:
        return None

    reply = propose_relational_reply(intent, owner_name=owner_name, rng=rng)
    trace_id = str(uuid.uuid4())
    matched_pattern = "ack_pattern" if intent == "RELATIONAL_ACK" else "co_present_pattern"

    if write:
        try:
            base = state_dir(state_dir_root) if state_dir_root else state_dir()
            base.mkdir(parents=True, exist_ok=True)
            ledger = base / RELATIONAL_LEDGER
            row = {
                "ts": now if now is not None else time.time(),
                "trace_id": trace_id,
                "kind": "RELATIONAL_STEERING_CHECK",
                "truth_label": TRUTH_LABEL,
                "truth_boundary": TRUTH_BOUNDARY,
                "route": intent,
                "matched_pattern": matched_pattern,
                "input_preview": (str(text or "")[:80]),
                "input_sha12": hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:12],
                "reply": reply,
                "source": source,
                "owner_name_first": (str(owner_name or "").strip().split()[:1] or [""])[0],
                "signals": dict(signals or {}),
            }
            with ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception:
            pass  # Receipt write failure should not block the route

    return RelationalCheckResult(
        route=intent,
        reply=reply,
        matched_pattern=matched_pattern,
        trace_id=trace_id,
    )


def make_steering_decision(
    intent: str,
    *,
    text: str = "",
    importance_label: str = "BACKCHANNEL",
) -> Optional[Any]:
    """Build a SteeringDecision-compatible row for the relational route.

    Returns ``None`` when ``SteeringDecision`` is not importable
    (bootstrap fallback). The Talk widget can use this when it wants a
    full decision row in the same schema as the regular cortex path.
    """
    if SteeringDecision is None:
        return None
    base_signals = {
        "importance": 0.0,
        "metabolic_pressure": 0.0,
        "owner_pressure": 0.85 if intent == "CO_PRESENT" else 0.55,
        "sensor_salience": 0.0,
        "memory_mass": 0.0,
        "novelty": 0.0,
        "risk": 0.0,
        "tool_truth_risk": 0.0,
        "social_salience": 0.9 if intent == "CO_PRESENT" else 0.55,
        "reward_magnitude": 0.0,
    }
    return SteeringDecision(
        route=intent,
        priority=0.20,
        budget_multiplier=0.05,
        temperature_hint=0.15,
        should_write_memory=False,
        should_probe_sensors=False,
        should_pull_memory=False,
        should_verify_tools=False,
        salience=0.10,
        interrupt=0.0,
        curiosity=0.0,
        care=base_signals["owner_pressure"],
        conserve=0.5,
        tool_truth=0.0,
        importance_label=importance_label,
        matched_pattern="ack_pattern" if intent == "RELATIONAL_ACK" else "co_present_pattern",
        reward_delta=0.0,
        reward_marker="",
        signals=base_signals,
        predictions=(),
    )


# ── CLI ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("text", nargs="?", default="ok")
    p.add_argument("--owner-name", default="")
    p.add_argument("--face-present", action="store_true")
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()
    sig = {"owner_face_present": args.face_present}
    out = relational_steering_check(
        args.text, signals=sig, owner_name=args.owner_name or None,
        write=not args.no_write,
    )
    if out is None:
        print(f"NO_RELATIONAL_ROUTE for input: {args.text!r} (cortex would run)")
    else:
        print(f"ROUTE:    {out.route}")
        print(f"REPLY:    {out.reply!r}")
        print(f"PATTERN:  {out.matched_pattern}")
        print(f"TRACE:    {out.trace_id}")
