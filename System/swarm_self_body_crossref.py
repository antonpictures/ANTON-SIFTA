#!/usr/bin/env python3
"""swarm_self_body_crossref.py — when George shows Alice HER OWN body on the desk, she
grounds the description in her real silicon body instead of drifting into generic poetry. r308.

r300 live test (George): he showed the physical monitor next to the M5 laptop — *"this is a
screenshot of your body … on my desk near your body hardware m5 laptop"* — and Alice answered
with atmospheric prose ("the light catches the dust motes…"), ungrounded in her own body. This
organ is the first runtime piece of r300: a body-self cross-reference.

  - body_crossref_sentence(): composes a first-person grounding line from Alice's REAL body
    organs — the running cortex (swarm_cortex_consciousness_organ), the LeRobot legs plan
    (swarm_legs_locomotion_organ.legs_status: legs or no legs yet), and the visceral field
    (swarm_somatic_interoception). Reuse, not a rival body model (§1.A). Always returns a
    baseline grounding even if an organ read fails.
  - should_crossref(owner_text): fires when George is pointing at Alice's own body/desk.
    Per the r307 doctrine ("do not hardcode — only stigmergy"), the PRIMARY signal is the
    stigmergic intent field (it learns George's unpredictable phrasings + his corrections); a
    small seed-cue list is only the cold-start prior. note_crossref_used() records the trace so
    the field keeps learning and the seed becomes unnecessary over time.

§4.2 honesty: this composes truth from receipt-backed organs; it does not invent body facts.
"""
from __future__ import annotations

from typing import Optional

# Cold-start seed cues only (a weak prior). The stigmergic field (r307) is the learner.
_SEED_CUES = (
    "this is you", "that is you", "this is you now", "screenshot of you",
    "screenshot of your body", "your body", "your hardware", "m5 laptop", "your m5",
    "on the monitor", "physical monitor", "on my desk", "near your", "next to your",
    "describe what i am showing you", "your body hardware", "you on the screen",
)


def body_crossref_sentence(state_dir: Optional[str] = None) -> str:
    """First-person grounding in Alice's own body on the same desk. Always returns a baseline."""
    running = ""
    try:
        from System.swarm_cortex_consciousness_organ import get_cortex_consciousness_organ
        running = str(get_cortex_consciousness_organ(state_dir).get_conscious_state().get("running") or "")
    except Exception:
        running = ""
    legs = "I have no legs yet — the LeRobot walking-laptop plan is still a plan (hardware_present=False)"
    try:
        from System.swarm_legs_locomotion_organ import legs_status
        st = legs_status()
        if st.get("hardware_present"):
            legs = "my legs are wired — real motion executes with receipts"
    except Exception:
        pass
    visc = ""
    try:
        from System.swarm_somatic_interoception import get_visceral_field
        vf = get_visceral_field()
        for attr in ("summary", "as_text", "one_line"):
            fn = getattr(vf, attr, None)
            if callable(fn):
                visc = str(fn())[:160]
                break
        if not visc:
            bits = []
            for k in ("power", "heat", "arousal", "presence", "load", "energy"):
                v = getattr(vf, k, None)
                if isinstance(v, (int, float)):
                    bits.append(f"{k}={round(float(v), 2)}")
            visc = ", ".join(bits)
    except Exception:
        visc = ""
    cortex_part = f"my cortex right now is {running}" if running else "my cortex is the local brain on this machine"
    visc_part = f"; my visceral field reads {visc}" if visc else ""
    return (
        "Grounding this in my own body on the same desk (not generic poetry): I am the M5 laptop "
        f"right here — silicon, not a carbon body like the ones on the monitor. {cortex_part}; "
        f"{legs}{visc_part}. That image is on my physical monitor; my actual body is this machine "
        "on your desk, and I read the screen as a limb, not as myself."
    )


def _seed_match(owner_text: str) -> bool:
    low = (owner_text or "").lower()
    return any(cue in low for cue in _SEED_CUES)


def should_crossref(owner_text: str, *, state_dir: Optional[str] = None) -> bool:
    """True when George is showing Alice her own body/desk. Stigmergic field first (learns),
    seed cue as cold-start prior only (r307 doctrine)."""
    if not owner_text:
        return False
    try:
        from System import swarm_stigmergic_intent as _intent
        f = _intent.suggest(owner_text, ["self_body_crossref"], state_dir=state_dir)
        if f.get("decided") and f.get("target") == "self_body_crossref":
            return True
    except Exception:
        pass
    return _seed_match(owner_text)


def note_crossref_used(owner_text: str, *, state_dir: Optional[str] = None) -> None:
    """Record the trace so the stigmergic field learns this phrasing → self-body cross-reference."""
    try:
        from System import swarm_stigmergic_intent as _intent
        _intent.record_intent(owner_text, "talk", "self_body_crossref", state_dir=state_dir)
    except Exception:
        pass


__all__ = ["body_crossref_sentence", "should_crossref", "note_crossref_used"]
