#!/usr/bin/env python3
"""Social reference tracking for Alice's shared conversation field.

This organ labels who an utterance is addressed to and who it is about. It is
not a speaker verifier and it does not decide consciousness. It gives the rest
of the system a bounded receipt for a hard case:

    George talks to another tab/tool about Alice, while Alice can hear it.

That is not the same thing as a direct command to Alice.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


_ALICE_NAME_RE = re.compile(r"\b(?:alice|sifta)\b", re.IGNORECASE)
_ALICE_DIRECT_RE = re.compile(
    r"^\s*(?:hey\s+|ok(?:ay)?\s+|please\s+|pls\s+)?(?:alice|sifta)\b[:,]?",
    re.IGNORECASE,
)
_ALICE_THIRD_PERSON_RE = re.compile(
    r"\b(?:she|her|herself|alice'?s|sifta'?s)\b",
    re.IGNORECASE,
)
_ABOUT_CUE_RE = re.compile(
    r"\b(?:about|hearing|heard|understand|understands|consciousness|"
    r"microphone|speaker|speakers|voice|third\s+person|chrome\s+tab|"
    r"another\s+chatbot|talking\s+to\s+you\s+about)\b",
    re.IGNORECASE,
)
_EXTERNAL_TOOL_RE = re.compile(
    r"\b(?:swarm\s*gpt|swarmgpt|chatgpt|openai|chrome\s+tab|browser\s+tab|"
    r"grok|hermes|codex|ide\s+doctor|another\s+chatbot|chatbot|llm)\b",
    re.IGNORECASE,
)
_PRIVATE_RE = re.compile(
    r"\b(?:private|do\s+not\s+answer|don't\s+answer|do\s+not\s+listen|"
    r"don't\s+listen|not\s+for\s+alice|owner\s+private)\b",
    re.IGNORECASE,
)
_DIRECT_OWNER_RE = re.compile(
    r"\b(?:i|i'm|i\s+am|me|my|we|we're|we\s+are|you|your)\b",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    return " ".join(str(text or "").split())


def classify_social_reference(
    text: str,
    *,
    role: str = "user",
    input_source: str = "",
    stt_conf: float = 0.0,
    focus_context: str = "",
    addressed_to: str = "",
    external_consciousness: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify the social geometry of one conversation/audio row.

    Returned lanes are intentionally small and stable:
      DIRECTED_TO_ALICE, ABOUT_ALICE, ADDRESSED_TO_EXTERNAL_TOOL,
      OVERHEARD_BACKGROUND, SELF_AUDIO_ECHO, OWNER_PRIVATE,
      DIRECT_OWNER_NO_ALICE, ALICE_SELF_OUTPUT, UNKNOWN.
    """
    clean = _clean(text)
    lower_context = str(focus_context or "").lower()
    role_s = str(role or "").lower()
    input_source_s = str(input_source or "").lower()
    external = dict(external_consciousness or {})
    source_class = str(external.get("source_class") or "").lower()
    route = str(external.get("route") or "").lower()
    evidence: list[str] = []

    try:
        conf = max(0.0, min(1.0, float(stt_conf or 0.0)))
    except Exception:
        conf = 0.0

    lane = "UNKNOWN"
    addressee = str(addressed_to or "").strip() or "unknown"
    subject = "unknown"
    policy = "store_context"

    if role_s == "alice" or input_source_s == "cortex":
        lane = "ALICE_SELF_OUTPUT"
        addressee = "owner"
        subject = "alice"
        policy = "record_alice_output"
        evidence.append("alice_role_or_cortex_source")
    elif _PRIVATE_RE.search(clean):
        lane = "OWNER_PRIVATE"
        addressee = "none"
        subject = "owner_private_context"
        policy = "store_minimal_no_reply"
        evidence.append("owner_private_language")
    elif source_class == "self_audio_echo":
        lane = "SELF_AUDIO_ECHO"
        addressee = "none"
        subject = "alice_audio_output"
        policy = "ignore_as_owner_command"
        evidence.append("self_audio_echo_source")
    else:
        alice_named = bool(_ALICE_NAME_RE.search(clean))
        alice_direct = bool(_ALICE_DIRECT_RE.search(clean))
        alice_about = bool(alice_named and (_ALICE_THIRD_PERSON_RE.search(clean) or _ABOUT_CUE_RE.search(clean)))
        external_tool = bool(_EXTERNAL_TOOL_RE.search(clean) or _EXTERNAL_TOOL_RE.search(lower_context))
        ambient = (
            route in {"ambient_media", "observed_media"}
            or source_class
            in {
                "screen_media_or_youtube",
                "screen_media_fiction",
                "ambient_phone_call",
                "room_or_visitor_conversation",
                "unknown_ambient_speech",
                "appliance_or_environmental_noise",
            }
        )

        if alice_direct:
            lane = "DIRECTED_TO_ALICE"
            addressee = "alice"
            subject = "alice"
            policy = "route_to_dialog_cortex"
            evidence.append("alice_direct_address")
        elif alice_about:
            lane = "ABOUT_ALICE"
            addressee = "external_tool" if external_tool else "none"
            subject = "alice"
            policy = "store_context_no_command" if external_tool or ambient else "route_as_contextual_owner_speech"
            evidence.append("alice_named_with_about_or_third_person")
            if external_tool:
                evidence.append("external_tool_context")
            if ambient:
                evidence.append("ambient_or_observed_source")
        elif external_tool:
            lane = "ADDRESSED_TO_EXTERNAL_TOOL"
            addressee = "external_tool"
            subject = "external_tool_or_tab"
            policy = "store_context_no_alice_command"
            evidence.append("external_tool_context")
        elif ambient:
            lane = "OVERHEARD_BACKGROUND"
            addressee = "none"
            subject = source_class or "ambient_world"
            policy = "store_context_no_reply"
            evidence.append("ambient_or_observed_source")
        elif _DIRECT_OWNER_RE.search(clean):
            lane = "DIRECT_OWNER_NO_ALICE"
            addressee = "alice"
            subject = "owner_context"
            policy = "route_to_dialog_cortex"
            evidence.append("owner_pronoun_direct_channel")

    confidence = 0.52
    if evidence:
        confidence += min(0.38, 0.12 * len(evidence))
    if conf:
        confidence += min(0.10, conf * 0.10)

    return {
        "truth_label": "SOCIAL_REFERENCE_TRACKER_V1",
        "reference_lane": lane,
        "addressee": addressee,
        "subject": subject,
        "dialog_policy": policy,
        "input_source": input_source_s or "unknown",
        "stt_confidence": round(conf, 3),
        "confidence": round(min(1.0, confidence), 3),
        "evidence": evidence[:8],
    }


__all__ = ["classify_social_reference"]
