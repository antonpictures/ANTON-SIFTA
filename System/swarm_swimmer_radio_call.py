"""
System/swarm_swimmer_radio_call.py — heal-not-ban escalation organ.

George's doctrine (2026-06-03, agreed by the IDE doctors): "BANNING SOMEBODY IS
MUCH LIKE KILLING THAT BODY'S ABILITY ... DON'T BAN, GIVE IT A RECEIPT, LET'S SEE
WHAT IT DOES ... IF BODIES START DOING WEIRD BEHAVIOUR REPEATEDLY, THE STIGMERGIC
EVAL MATRIX INTROSPECTION DETECTS IT AND WE HEAL, WE DON'T BAN, WE DON'T KILL — WE
FIX ... SOME SWIMMERS, IF THEY HIT AN ERROR THEY COULD NOT FIX BASED ON PAST
STIGMERGIC MEMORY, THEY RADIO-CALL ANOTHER SWIMMER WHO CAN — GETS SCHEDULED."

This organ implements exactly that. When a swimmer investigating a red organ
cannot fix it (judged by the PAST STIGMERGIC MEMORY of prior dispatches/proposals
on that organ that did not turn it green), it does NOT give up and the organ is
NOT banned/killed. Instead the swimmer RADIO-CALLS for a swimmer with a different
capability, and the job is SCHEDULED into a field lane that another body can pick
up like an ant reading a marked trail.

Stigmergic, not deterministic: the escalation emerges from the field state
(how many times this organ was already worked + still red), not a hardcoded gate.
Append-only field deposits. No code mutation, no model, no network.

For the Swarm. 🐜⚡ One Alice. One field. We heal, we don't ban; if one body can't,
another can — the field routes the work.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_DISPATCH = _STATE / "self_eval_swimmer_dispatch.jsonl"
_PROPOSALS = _STATE / "self_eval_swimmer_proposals.jsonl"
_RADIO_CALLS = _STATE / "self_eval_radio_calls.jsonl"
_SCHEDULED = _STATE / "self_eval_scheduled_jobs.jsonl"

# Capabilities the field can radio for — a different body for a different job.
_CAPABILITY_LADDER = (
    "local_audit_swimmer",      # cheap: read receipts + code on the organ
    "research_swimmer",         # pull papers / cross-reference the briefs
    "cortex_proposal_swimmer",  # ask a cortex arm for a patch candidate
    "owner_help_swimmer",       # escalate to George — "I need help coding this"
)


def _paths(state_dir: str | Path | None = None) -> tuple[Path, Path, Path, Path]:
    state = Path(state_dir) if state_dir is not None else _STATE
    return (
        state / "self_eval_swimmer_dispatch.jsonl",
        state / "self_eval_swimmer_proposals.jsonl",
        state / "self_eval_radio_calls.jsonl",
        state / "self_eval_scheduled_jobs.jsonl",
    )


def _count_prior_attempts(organ_name: str, *, state_dir: str | Path | None = None) -> int:
    """Past stigmergic memory: how many times has the field already worked this organ?"""
    n = 0
    key = (organ_name or "").strip().lower()
    dispatch, proposals, _radio_calls, _scheduled = _paths(state_dir)
    for p in (dispatch, proposals):
        if not p.exists():
            continue
        try:
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if str(row.get("organ", "")).strip().lower() == key:
                    n += 1
        except Exception:
            continue
    return n


def _next_capability(prior_attempts: int) -> str:
    """The more times a body already tried and the organ stayed red, the further up
    the ladder we radio — ending at the owner. Stigmergic: emerges from the trail."""
    idx = min(prior_attempts, len(_CAPABILITY_LADDER) - 1)
    return _CAPABILITY_LADDER[idx]


def should_escalate(organ_name: str, threshold: int = 2, *, state_dir: str | Path | None = None) -> bool:
    """Escalate when the field has already worked this organ >= threshold times and
    it is still red — the current swimmer cannot fix it from past memory."""
    return _count_prior_attempts(organ_name, state_dir=state_dir) >= threshold


def radio_call_for_help(organ_name: str, module: str = "", reason: str = "",
                        tried_by: str = "self_eval_swimmer",
                        state_dir: str | Path | None = None) -> dict:
    """Deposit a radio-call + schedule the job for a swimmer who CAN do it.

    Never bans or kills the organ or the swimmer — routes the work to a different
    body. Returns the radio-call row (also written to the field).
    """
    prior = _count_prior_attempts(organ_name, state_dir=state_dir)
    capability = _next_capability(prior)
    ts = time.time()
    call = {
        "ts": ts,
        "kind": "SWIMMER_RADIO_CALL",
        "organ": organ_name,
        "module": module,
        "tried_by": tried_by,
        "prior_attempts": prior,
        "reason": (reason or "could not fix from past stigmergic memory")[:200],
        "radio_for": capability,
        "request": (
            f"Need a {capability}: this organ stayed red after {prior} prior field passes. "
            "Schedule it; a body with the right capability picks it up from the trail."
        ),
        "heal_not_ban": True,
        "covenant": "George 2026-06-03 heal-not-ban: we don't ban/kill a body for failing; we receipt + route the work",
        "truth_label": "SWIMMER_RADIO_CALL_V1",
        "source": "swarm_swimmer_radio_call",
    }
    job = {
        "ts": ts,
        "kind": "SELF_EVAL_SCHEDULED_JOB",
        "organ": organ_name,
        "module": module,
        "assigned_capability": capability,
        "status": "scheduled",
        "from_radio_call": True,
        "prior_attempts": prior,
        "truth_label": "SELF_EVAL_SCHEDULED_JOB_V1",
    }
    _dispatch, _proposals, radio_calls, scheduled = _paths(state_dir)
    for path, row in ((radio_calls, call), (scheduled, job)):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass
    return call


def escalate_if_stuck(
    organ_name: str,
    module: str = "",
    threshold: int = 2,
    *,
    state_dir: str | Path | None = None,
) -> dict | None:
    """The healing loop: if the organ is stuck red after repeated passes, radio-call;
    otherwise return None (a fresh swimmer can still try). Heal, never ban."""
    if should_escalate(organ_name, threshold=threshold, state_dir=state_dir):
        return radio_call_for_help(
            organ_name, module=module,
            reason=f"stuck red after >= {threshold} field passes; current capability insufficient",
            state_dir=state_dir,
        )
    return None


def main():
    import sys
    organ = sys.argv[1] if len(sys.argv) > 1 else "Vocal Cords"
    print(f"prior attempts on {organ!r}: {_count_prior_attempts(organ)}")
    print(f"should escalate: {should_escalate(organ)}")
    call = radio_call_for_help(organ, module="swarm_vocal_cords", reason="demo run")
    print("radio call:", json.dumps(call, ensure_ascii=False)[:300])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
