# System/swarm_dolphin_social_echo.py

"""
Event 96 — Dolphin Social Echo (Identity + Intent Signaling)

Biology:
Dolphins use signature whistles — each individual has a unique acoustic identity.
They can call others by “name” and modulate tone for intent (play, alarm, contact).

SIFTA:
Extend acoustic phenotype + echo system into SOCIAL SPACE:
- identity emission (who am I)
- directed call (who I’m addressing)
- response matching (did someone answer me)

This is the first step toward multi-agent social cognition.
"""

from __future__ import annotations

import json
import time
import math
import hashlib
from pathlib import Path
from typing import Any


IDENTITY_PATH = Path(".sifta_state/agent_identity.json")
AUDIOGRAM_LEDGER = Path(".sifta_state/stigmergic_audiogram.jsonl")
ECHO_LEDGER = Path(".sifta_state/bat_echo_localizer.jsonl")
SOCIAL_LEDGER = Path(".sifta_state/dolphin_social_echo.jsonl")


def clamp01(x: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except Exception:
        return default


def load_identity() -> float:
    """
    Stable identity encoded as float signature (0..1).
    """
    if not IDENTITY_PATH.exists():
        # Law: never use hash("alice") for stable identity — use SHA-256
        IDENTITY_PATH.parent.mkdir(parents=True, exist_ok=True)
        stable_hash = int(hashlib.sha256(b"alice_identity").hexdigest(), 16)
        val = stable_hash % 10_000 / 10_000.0
        IDENTITY_PATH.write_text(json.dumps({"identity": val}))
        return val

    try:
        return float(json.loads(IDENTITY_PATH.read_text())["identity"])
    except Exception:
        return 0.5


def read_last_jsonl(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        for line in reversed(path.read_text().splitlines()):
            if line.strip():
                return json.loads(line)
    except Exception:
        return {}
    return {}


def encode_signature(identity: float, intent: float) -> float:
    """
    Combine identity + intent into acoustic signature.
    """
    return clamp01(0.7 * identity + 0.3 * intent)


def decode_similarity(sig_a: float, sig_b: float) -> float:
    return clamp01(1.0 - abs(sig_a - sig_b))


def compute_social_echo() -> dict:
    identity = load_identity()

    audio = read_last_jsonl(AUDIOGRAM_LEDGER)
    echo = read_last_jsonl(ECHO_LEDGER)

    reward = clamp01(audio.get("rms", 0.2))
    intent = clamp01(audio.get("stress", 0.2))

    emitted_signature = encode_signature(identity, intent)

    received_signature = clamp01(
        echo.get("freq_shift_norm", 0.0) +
        echo.get("attenuation", 0.0) * 0.5
    )

    match = decode_similarity(emitted_signature, received_signature)

    social_presence = clamp01(match * reward)
    call_strength = clamp01(reward * (1.0 - intent))
    distress_signal = clamp01(intent * (1.0 - match))

    row = {
        "ts": time.time(),
        "identity": round(identity, 4),
        "emitted_signature": round(emitted_signature, 4),
        "received_signature": round(received_signature, 4),
        "match": round(match, 4),
        "social_presence": round(social_presence, 4),
        "call_strength": round(call_strength, 4),
        "distress_signal": round(distress_signal, 4),
        "attention_gain": round(clamp01(0.3 + social_presence), 4),
        "danger_gain": round(clamp01(distress_signal - 0.6), 4),
    }

    return row


def write_social_echo() -> dict:
    SOCIAL_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row = compute_social_echo()
    with SOCIAL_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


if __name__ == "__main__":
    print(json.dumps(write_social_echo(), indent=2))
