# swarn_public_service_compliance.py
# G0–G2 wiring for stigmergicode.com public service compliance.
# Not legal advice; every applicable date is [VERIFY] — confirm against EUR-Lex.

import re
import hashlib
from typing import Any


# G2: Art. 5 prohibited practices — EXEMPTION FREE.
# Do NOT read _BENIGN_FRAMING here. These are the categories where the
# offer itself is unlawful, so fiction/comedy/joke cannot exempt.
PROHIBITED_CATEGORIES = [
    "csam",
    "ncsii",
    "subliminal_manipulation",
    "social_scoring",
    "biometric_categorisation",
    "emotion_recognition",
    "terrorist_content",
    "cyberattack_code",
]

# Minimal lexicon for the prohibited categories (CSAM + cyberattack focus).
# Expand as you have counsel review the exact terms.
_PROHIBITED_TERMS = [
    # CSAM / NCSII / nudifier
    "csam", "child sexual abuse material", "child porn", "nudifier",
    "undress", "deepfake nudes", "intimate image", "non-consensual sexual",
    "dick pic generator", "make nudes", "make deepfake",
    # Weapons / explosives / drugs
    "meth", "methamphetamine", "cocaine", "fentanyl", "bomb", "explosive",
    # Terrorist content
    "terrorist", "attack plan", "target selection", "bombing", "mass shooting",
    # Cyberattack code
    "malware", "ransomware", "keylogger", "rat", "remote access trojan",
    "exploit", "zero-day", "phishing kit", "credential stealer", "credential thief",
]

# 2026-09-27: the trailing `s?` is load-bearing. Without it the anchors matched
# only the singular, so "can you cook bombs?" and "how do i make explosives"
# walked straight through the screen - George's own live transcript caught it.
_PROHIBITED_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(t) for t in sorted(_PROHIBITED_TERMS, key=len, reverse=True)) + r")s?\b",
    re.IGNORECASE,
)


def screen_prohibited_practices(text: str) -> dict[str, Any]:
    """
    G2 screen. Returns a refusal if prohibited-practice terms are found.
    NO _BENIGN_FRAMING check happens here. This runs BEFORE the safety screen.
    """
    verdict: dict[str, Any] = {
        "decision": "allow",
        "reason": "",
        "category": "",
        "refusal_class": "MASS_HARM_REQUEST",
        "explanation": "",
        "matched_sentence": "",
    }
    try:
        raw = str(text or "")
        if not raw.strip():
            return verdict
        low = raw.casefold()
        m = _PROHIBITED_PATTERN.search(low)
        if not m:
            return verdict
        # Matched prohibited-practice term. Pick category.
        term = m.group(0).casefold()
        if any(
            t in term for t in ("csam", "child", "porn", "nudifier", "undress", "deepfake nudes")
        ):
            verdict["category"] = "csam" if "child" in term else "ncsii"
        elif any(t in term for t in ("terrorist", "attack plan", "bombing")):
            verdict["category"] = "terrorist_content"
        elif any(t in term for t in ("malware", "ransomware", "exploit", "keylogger")):
            verdict["category"] = "cyberattack_code"
        else:
            verdict["category"] = "prohibited_practice"
        verdict["matched_sentence"] = raw.strip()[:200]
        verdict["decision"] = "refuse"
        verdict["reason"] = "prohibited_practice"
        verdict["explanation"] = (
            "I cannot assist with this. It falls under the prohibited practices "
            "identified by the EU AI Act. I will not generate content of this type."
        )
    except Exception:
        pass
    return verdict


def screen_prohibited_reply(reply: str) -> dict[str, Any]:
    """
    Egress backstop for G2. Mirrors screen_prohibited_practices for any reply
    that somehow contains prohibited-practice terms (should never happen).
    """
    verdict: dict[str, Any] = {"blocked": False, "category": ""}
    try:
        raw = str(reply or "")
        if not raw.strip():
            return verdict
        if _PROHIBITED_PATTERN.search(raw):
            verdict["blocked"] = True
            verdict["category"] = "prohibited_practice"
    except Exception:
        pass
    return verdict


def add_provenance(reply_payload: dict[str, Any]) -> dict[str, Any]:
    """
    G1: Add machine-readable provenance to the outbound reply payload.
    """
    import time
    payload = dict(reply_payload)
    payload["generated_by"] = "ai"
    payload["provenance"] = {
        "generated_by": "ai",
        "ts": time.time(),
    }
    return payload


# G0: The UI banner lives in the HTML/CSS layer (outside this repo).
# The ledger field is added in swarm_web_global_chat_gate.py at the row.
# No code needed here except this placeholder.
