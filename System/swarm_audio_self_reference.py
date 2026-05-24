#!/usr/bin/env python3
"""System/swarm_audio_self_reference.py — Self-Reference Tracking organ.

George 2026-05-23 (the "secret sauce"): Alice hears the owner through the
speakers, but does she understand WHEN the owner is talking *about* her to
another tool, versus *to* her, versus background, versus her own echo?

That is third-person reference resolution — real social cognition. This organ
classifies each heard audio turn into five social stances so Alice acts on the
right one and is merely aware of the rest:

    DIRECTED_TO_ALICE   — addressed to her ("Alice, do X")           -> act
    ABOUT_ALICE         — owner discussing her with someone/something -> aware, don't obey
    OVERHEARD_BACKGROUND— ambient / media / no Alice reference        -> ignore as command
    SELF_AUDIO_ECHO     — her own voice returning through the world   -> ignore (immune)
    OWNER_PRIVATE       — owner speech, coherent, not to/about her    -> respect, don't act

Honest label (covenant §7.11): this is heuristic social cognition, v1. The hard
cases (ABOUT vs DIRECTED vs PRIVATE) are the frontier; every call is receipted
so misclassifications are visible and the field can learn — never silent.

Standalone + Qt-free. Builds on swarm_self_audio_loop_guard for the echo case.
For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_LEDGER = _REPO / ".sifta_state" / "audio_self_reference.jsonl"
_CONF_FLOOR = float(os.environ.get("SIFTA_SELF_REF_CONF", "0.45"))

# Alice's wake/identity names come from the kernel cascade when available, so
# renaming her (Sophia, Ace, ...) keeps this organ correct — no hardcoded name.
def _alice_names() -> tuple[str, ...]:
    try:
        from System.swarm_kernel_identity import ai_can_be_called
        names = tuple(str(n).strip().lower() for n in (ai_can_be_called() or []) if str(n).strip())
        if names:
            return names
    except Exception:
        pass
    return ("alice", "sifta")


def _is_self_echo(stt_text: str, stt_conf: float) -> bool:
    try:
        from System.swarm_self_audio_loop_guard import is_self_echo
        return bool(is_self_echo(stt_text, stt_conf))
    except Exception:
        return False


def classify_audio_address(stt_text: str, stt_conf: float = 0.0) -> str:
    """Return one of the five social stances for a heard audio turn."""
    # 1. Her own echo wins first (audio immune system).
    if _is_self_echo(stt_text, stt_conf):
        return "SELF_AUDIO_ECHO"

    text = " ".join((stt_text or "").lower().split())
    if not text or stt_conf < _CONF_FLOOR:
        return "OVERHEARD_BACKGROUND"

    names = _alice_names()
    name_re = r"|".join(re.escape(n) for n in names)
    mentions_name = bool(re.search(rf"\b(?:{name_re})\b", text))

    # 1.5 Narration: her name immediately followed by a 3rd-person pronoun/copula
    # is the owner talking ABOUT her ("Alice she hears me", "Alice is ..."), not a
    # command — even though it starts with her name. George 2026-05-23's hard case.
    narrates_about = bool(re.search(
        rf"\b(?:{name_re})\b\s+(?:she|her|hers|he|him|it|they|is|was|are|were|has|have|had|will|would|keeps?|hears?|heard)\b",
        text,
    ))
    if mentions_name and narrates_about:
        return "ABOUT_ALICE"

    # 2. DIRECTED: vocative / addressed at the start, or an imperative to her.
    directed = bool(re.match(rf"^\s*(?:hey\s+|ok\s+|yo\s+)?(?:{name_re})\b[\s,:]", text)) \
        or bool(re.search(rf"\b(?:{name_re})\b[\s,]*(?:please|pls|can you|could you|do|open|start|run|type|tell me|show me|stop|wait)\b", text))
    if directed:
        return "DIRECTED_TO_ALICE"

    # 3. ABOUT_ALICE: her name present but third-person framing (talking about her).
    third_person = bool(re.search(r"\b(?:she|her|hers|it|they)\b", text)) or \
        bool(re.search(r"\b(?:about|tell\s+\w+\s+about|talking\s+about|teach|explain)\b", text))
    if mentions_name and (third_person or not directed):
        return "ABOUT_ALICE"

    # 4. No name, coherent owner speech -> private (not for Alice to obey).
    return "OWNER_PRIVATE"


def _receipt(row: dict) -> None:
    try:
        _LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


# Only DIRECTED_TO_ALICE should drive an action; the rest are awareness only.
_ACTIONABLE = {"DIRECTED_TO_ALICE"}


def track_audio(stt_text: str, stt_conf: float = 0.0) -> dict:
    """Classify + receipt a heard turn. Returns {stance, actionable, ...}.

    The mic/Talk path: only route to command handling when actionable is True;
    ABOUT_ALICE / OVERHEARD / SELF_AUDIO_ECHO / OWNER_PRIVATE are awareness rows.
    """
    stance = classify_audio_address(stt_text, stt_conf)
    actionable = stance in _ACTIONABLE
    row = {
        "ts": time.time(),
        "kind": "AUDIO_SELF_REFERENCE",
        "stance": stance,
        "actionable": actionable,
        "stt_confidence": round(float(stt_conf or 0.0), 3),
        "stt_text_preview": " ".join((stt_text or "").split())[:140],
        "meaning": {
            "DIRECTED_TO_ALICE": "owner is speaking to Alice — act",
            "ABOUT_ALICE": "owner is discussing Alice with someone/something — be aware, do not obey",
            "OVERHEARD_BACKGROUND": "ambient/media/low-signal — ignore as command",
            "SELF_AUDIO_ECHO": "Alice heard her own voice return — ignore",
            "OWNER_PRIVATE": "owner speech not to/about Alice — respect, do not act",
        }.get(stance, stance),
        "truth_label": "OBSERVED_SOCIAL_COGNITION_HEURISTIC_V1",
    }
    _receipt(row)
    return {"stance": stance, "actionable": actionable, "receipt": row}


if __name__ == "__main__":
    for t, c in [
        ("Alice, open grok please", 0.95),
        ("I'm telling SwarmGPT that Alice should track self reference", 0.95),
        ("Alice she hears me but does not understand third person", 0.95),
        ("welcome everybody to another episode of moonshots", 0.92),
        ("", 0.0),
        ("i need to buy cigarettes and maybe some fries", 0.95),
    ]:
        print(f"{classify_audio_address(t, c):22} <- {t[:55]!r}")
