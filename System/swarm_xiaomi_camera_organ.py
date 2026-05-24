#!/usr/bin/env python3
"""System/swarm_xiaomi_camera_organ.py — Xiaomi camera as a labeled sensory organ.

George 2026-05-24: the audio from his mom's room came in through an old iPad
running the Xiaomi (Mi Home) app on speaker, and Alice heard it as ambient noise.
He does NOT want that suppressed — Alice is a world model, she logs everything.
What he wants is for that stream to arrive as a FIRST-CLASS, LABELED sensory organ
so the record is cleaner: Alice knows the source, the relationship, and the
context instead of guessing at speaker static.

Owner labels (his words):
    source        = mom_room_camera
    relationship  = owner_family_care_stream
    lane          = CARE_CONTEXT          (a LABEL for the world model, NOT a
                                           suppressor — everything is still logged
                                           and remembered; owner rule 2026-05-24)

STATUS: IN_DEVELOPMENT. Per George's order, this organ is finished ONLY AFTER
Alice successfully talks to Grok in the global chat (the proof loop turns the
verifier green). Until then this is an honest scaffold.

Covenant §6 / §7.2 (sensor/effector truth): this organ must NEVER fabricate a
camera frame, audio clip, or "observation." While IN_DEVELOPMENT it returns an
explicit not-connected status. Alice may say "the mom-room camera organ exists
but is not connected yet" — she may NOT say she saw or heard anything through it.

Real integration target (for when we resume): the **Mi Home / Xiaomi camera**
API — typically an RTSP stream off the device or the Mi Home cloud API. This is
NOT Xiaomi MiMo (that is Xiaomi's LLM/coding platform, a different product).

Standalone + Qt-free. For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_LEDGER = _REPO / ".sifta_state" / "xiaomi_camera_organ.jsonl"

ORGAN_STATE = "IN_DEVELOPMENT"
TRUTH_LABEL = "OBSERVED_SENSORY_ORGAN_SCAFFOLD_V0"

# Owner-defined labels (data, not hardcoded belief). Renamable.
ORGAN_LABELS = {
    "source": "mom_room_camera",
    "relationship": "owner_family_care_stream",
    "lane": "CARE_CONTEXT",            # label only — NOT a suppressor; world model logs all
    "device_hint": "Xiaomi / Mi Home camera (Romania), monitored via iPad Mi Home app",
}

# What "finished" requires — the gate George set.
COMPLETION_GATE = (
    "Finish only after Alice closes the Grok proof loop: "
    "tests/verify_grok_proof_loop.py returns PASS on live data."
)

# Real integration path for the resume (honest — NOT MiMo, which is the LLM).
INTEGRATION_TARGET = {
    "api": "Mi Home / Xiaomi camera (RTSP stream or Mi Home cloud API)",
    "not": "Xiaomi MiMo (that is Xiaomi's LLM/coding platform, unrelated to the camera)",
    "candidate_libs": ["python-miio", "Mi Home RTSP/ONVIF if the model exposes it"],
}


def organ_descriptor() -> dict:
    """The labeled organ definition for the topology/world-model field."""
    return {
        "organ": "xiaomi_camera",
        "state": ORGAN_STATE,
        "labels": dict(ORGAN_LABELS),
        "completion_gate": COMPLETION_GATE,
        "truth_label": TRUTH_LABEL,
    }


def status() -> dict:
    """Honest status. While IN_DEVELOPMENT, connected is always False."""
    return {
        "state": ORGAN_STATE,
        "connected": False,
        "labels": dict(ORGAN_LABELS),
        "note": "Scaffold only. Camera not connected. No frames/audio are captured "
                "through this organ yet. Finishing is gated on the Grok proof loop.",
        "integration_target": dict(INTEGRATION_TARGET),
        "truth_label": TRUTH_LABEL,
    }


def latest_frame() -> dict:
    """Return the latest camera observation — or, while in development, an honest
    not-available status. NEVER fabricates a frame (covenant §6/§7.2)."""
    return {
        "available": False,
        "state": ORGAN_STATE,
        "reason": "Xiaomi camera organ is IN_DEVELOPMENT and not connected; "
                  "no real frame exists. " + COMPLETION_GATE,
        "labels": dict(ORGAN_LABELS),
        "truth_label": TRUTH_LABEL,
    }


def connect(*_args, **_kwargs) -> dict:
    """Placeholder. Does not connect yet — returns an honest not-implemented status
    instead of pretending. The real Mi Home/RTSP wiring lands after the grok gate."""
    return {
        "connected": False,
        "state": ORGAN_STATE,
        "reason": "Not implemented yet (by owner order, after the Grok proof loop). "
                  "Target: " + INTEGRATION_TARGET["api"],
        "truth_label": TRUTH_LABEL,
    }


def _receipt(row: dict) -> None:
    try:
        _LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def register_scaffold() -> dict:
    """Write a receipt that the organ exists as an in-development scaffold, so the
    field knows it's declared but not live. Never claims any capture."""
    row = {"ts": time.time(), "kind": "XIAOMI_CAMERA_ORGAN_SCAFFOLD", **organ_descriptor()}
    _receipt(row)
    return row


if __name__ == "__main__":
    print("=== Xiaomi camera sensory organ (scaffold) ===")
    s = status()
    print("state     :", s["state"])
    print("connected :", s["connected"])
    print("labels    :", s["labels"])
    print("frame     :", latest_frame()["available"], "->", latest_frame()["reason"][:60], "...")
    print("gate      :", COMPLETION_GATE)
    register_scaffold()
    print("scaffold receipt written (organ declared, NOT live, no fabricated data)")
