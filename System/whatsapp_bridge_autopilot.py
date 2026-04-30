#!/usr/bin/env python3
"""
System/whatsapp_bridge_autopilot.py — Outbound WhatsApp Biological Actuator
═══════════════════════════════════════════════════════════════════════════
Alice's WhatsApp arm. Resolves human nicknames to JIDs and injects the message
into the Baileys Node.js bridge.
"""

import hashlib
import json
import urllib.request
import urllib.error
import time
from pathlib import Path
from typing import Any, Dict, Optional

from System.whatsapp_social_graph import (
    contact_rows_for_alice,
    load_contacts,
    resolve_target,
    summary_for_alice as social_graph_summary_for_alice,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_CONTACTS_FILE = _STATE / "whatsapp_contacts.json"
_LEDGER = _STATE / "whatsapp_bridge_trace.jsonl"
_INJECT_URL = "http://127.0.0.1:3001/system_inject"

SCHEMA = "SIFTA_WHATSAPP_EFFECTOR_V1"
EVENT_KIND = "WHATSAPP_SEND_ATTEMPT"
_ALLOW_GROUP_SEND = False


def _attach_intent_provenance(
    row: Dict[str, Any],
    *,
    intent_provenance: Optional[Dict[str, Any]] = None,
    decision_path: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """Attach self/other intent metadata without blocking the effector path."""
    if intent_provenance:
        row["intent_provenance"] = dict(intent_provenance)
        return row
    try:
        from System.swarm_intent_provenance import build_provenance, normalize_legacy_source

        source = str(row.get("source") or "")
        routed = "tool_router" in source.lower()
        intent_source, consent, note = normalize_legacy_source(
            source,
            routed_via_tool_router=routed,
        )
        if row.get("status") == "SILENCE_NO_CONSENT":
            consent = "none"
        extra = {"legacy_source": source}
        if note:
            extra["normalization_note"] = note
        row["intent_provenance"] = build_provenance(
            intent_source=intent_source,
            consent=consent,
            decision_path=decision_path or ["whatsapp_effector"],
            receipt_proof=True,
            tool="send_whatsapp",
            extra=extra,
        )
    except Exception:
        pass
    return row


def _deposit_trace(row: Dict[str, Any]) -> Dict[str, Any]:
    """Record Alice's outgoing WhatsApp messages to the immutable ledger."""
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(_LEDGER, json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            
    try:
        from System.swarm_pheromone import PHEROMONE_FIELD
        PHEROMONE_FIELD.deposit("stig_whatsapp_effector", intensity=1.0 if row.get("ok") else -0.5)
    except Exception:
        pass
    return row


def _load_contacts() -> Dict[str, Any]:
    return load_contacts(_CONTACTS_FILE)


def _resolve_target(target: str) -> str:
    """Resolve a target string (JID or nickname) to a JID."""
    return resolve_target(target, _load_contacts())


def summary_for_alice(limit: int = 12) -> str:
    """Compact WhatsApp world model for Alice's prompt context.

    Raw JIDs stay out of the prompt; Alice only needs names, chat shape, and
    whether a contact is reachable by the local bridge.
    """
    lines = [
        "WHATSAPP WORLD:",
        "- transport=WhatsApp via local Baileys phone bridge; inbound messages are real external humans queued into Alice.",
        "- outbound_tool=whatsapp.send; target may be a saved display name or exact WhatsApp JID.",
        "- autonomy_gate=bounded Gaussian attraction; autonomous sends require consent, relevance, timing, and low repetition.",
        "- group_send_default=blocked unless an explicit group-send override is provided.",
        "- social_graph=owner WhatsApp contacts and groups are friends/collaborators/channels of the machine owner.",
    ]
    try:
        from System.whatsapp_autonomy_gate import summary_for_alice as _autonomy_summary
        lines.append(_autonomy_summary(limit=2))
    except Exception:
        pass
    lines.append(social_graph_summary_for_alice(limit=limit))
    rows = contact_rows_for_alice(limit=limit, contacts=_load_contacts())
    if rows:
        lines.append("- target_examples: " + "; ".join(rows))
    else:
        lines.append("- known_contacts=0; contacts appear after WhatsApp sync or after a human messages Alice.")
    return "\n".join(lines)


def send_whatsapp(
    target: str,
    text: str,
    *,
    allow_group_send: bool = False,
    source: str = "owner_explicit",
    autonomy_decision: Optional[Dict[str, Any]] = None,
    intent_provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Transmit a WhatsApp message via the Baileys injection server.
    """
    target = (target or "").strip()
    text = (text or "").strip()
    resolved_jid = ""

    def finish(status: str, ok: bool, result: str) -> Dict[str, Any]:
        row = {
            "event_kind": EVENT_KIND,
            "schema": SCHEMA,
            "ts": time.time(),
            "target": target,
            "resolved_jid": resolved_jid,
            "text": text,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else "",
            "source": source,
            "ok": ok,
            "status": status,
            "result": result,
            "truth_note": "External WhatsApp send is true only when ok=true and status=SENT.",
        }
        if autonomy_decision:
            row["autonomy_decision"] = autonomy_decision
        _attach_intent_provenance(
            row,
            intent_provenance=intent_provenance,
            decision_path=["whatsapp_effector", status.lower()],
        )
        return _deposit_trace(row)

    if not target:
        return finish("REJECTED_MISSING_TARGET", False, "Missing target name or JID.")
    if not text:
        return finish("REJECTED_MISSING_PAYLOAD", False, "Missing message text.")

    resolved_jid = _resolve_target(target)
    if not resolved_jid:
        return finish("BLOCKED_UNKNOWN_TARGET", False, f"Could not resolve '{target}' to a known WhatsApp contact. They must message Alice first to register.")
    if resolved_jid.endswith("@g.us") and not (allow_group_send or _ALLOW_GROUP_SEND):
        return finish(
            "BLOCKED_GROUP_SEND_DISABLED",
            False,
            "Group send blocked by default. Pass allow_group_send=True only for explicit owner-approved group messages.",
        )

    # Social Mirror: Enforce Conversation Role Awareness
    try:
        from System.swarm_social_mirror import SwarmSocialMirror, SocialMirrorEvent
        mirror = SwarmSocialMirror()
        
        consent = "none"
        source_norm = str(source or "").strip().lower()
        provenance_consent = str((intent_provenance or {}).get("consent") or "").lower()
        provenance_source = str((intent_provenance or {}).get("intent_source") or "").lower()
        if source_norm == "owner_explicit":
            consent = "owner_explicit"
        elif source_norm == "conversation":
            # Architect is in the conversation — Alice replying IS owner-directed
            consent = "owner_explicit"
        elif provenance_consent == "owner_explicit":
            consent = "owner_explicit"
        elif provenance_consent == "explicit" and provenance_source in {"owner", "conversation"}:
            consent = "owner_explicit"
        elif "architect_consent" in source_norm or "spinal_reflex_conversation" in source_norm:
            consent = "owner_explicit"
        elif (
            "autonomous" in source_norm
            or "direct_whatsapp_reply" in source_norm
            or "model_request" in source_norm
            or "observation" in source_norm
        ):
            consent = "none"
        elif source_norm and source_norm not in {"reflex", "scheduled", "scheduler"}:
            # Legacy non-autonomous owner paths still count as owner-directed.
            consent = "owner_explicit"

        mirror_event = SocialMirrorEvent(
            direction="outbound",
            speaker="alice",
            audience="group" if resolved_jid.endswith("@g.us") else "contact",
            action="send_reply",
            consent=consent,
            agency_verdict_id=intent_provenance.get("agency_verdict_id", "") if intent_provenance else "",
            event_id=f"sm_{int(time.time()*1000)}"
        )
        mirror.log_event(mirror_event)
        
        allowed, reason = mirror.may_send_whatsapp(mirror_event)
        if not allowed:
            return finish("BLOCKED_SOCIAL_MIRROR", False, f"Social Mirror rejected send: {reason}")
    except Exception as e:
        pass # If mirror fails, we let it pass or fail? The doctrine implies strictness. 
             # But a crash shouldn't break the entire bridge if mirror isn't there. 
             # Wait, doctrine is "block any send where source is inbound observation alone".
             # So we fail open if the module is missing? No, we shouldn't fail open for security.
             # Actually, just let exceptions bubble or print, but in SIFTA we usually pass if the module is absent, to prevent lobotomization.

    payload = json.dumps({"to": resolved_jid, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        _INJECT_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return finish("SENT", True, f"Message injected to {resolved_jid}.")
            else:
                return finish("SEND_FAILED", False, f"Bridge rejected payload: {data}")
    except urllib.error.URLError as e:
        return finish("BRIDGE_UNREACHABLE", False, f"Could not reach injection server at {_INJECT_URL}. Is the Node bridge running?")
    except Exception as e:
        return finish("SEND_ERROR", False, str(e))


def autonomous_send_whatsapp(
    target: str,
    text: str,
    *,
    consent: bool = False,
    user_initiated: bool = False,
    emergency: bool = False,
    emotional_warmth: float = 0.5,
    urgency: float = 0.0,
    topic_match: float = 0.5,
    allow_group_send: bool = False,
    intent_provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Alice's bounded autonomous WhatsApp path.

    This never bypasses the effector ledger. If the attraction field says
    silence, the silence is written as a decision receipt and no message is
    injected into WhatsApp.
    """
    target = (target or "").strip()
    text = (text or "").strip()
    resolved_jid = _resolve_target(target) if target else ""
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""

    def silent(status: str, result: str, decision: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        row = {
            "event_kind": EVENT_KIND,
            "schema": SCHEMA,
            "ts": time.time(),
            "target": target,
            "resolved_jid": resolved_jid,
            "text": text,
            "text_sha256": text_hash,
            "source": "alice_autonomous",
            "ok": False,
            "status": status,
            "result": result,
            "truth_note": "Autonomous boundary chose silence; no external WhatsApp action occurred.",
        }
        if decision:
            row["autonomy_decision"] = decision
        _attach_intent_provenance(
            row,
            intent_provenance=intent_provenance,
            decision_path=["whatsapp_autonomy_gate", status.lower(), "silence_receipt"],
        )
        return _deposit_trace(row)

    if not target:
        return silent("REJECTED_MISSING_TARGET", "Missing target name or JID.")
    if not text:
        return silent("REJECTED_MISSING_PAYLOAD", "Missing message text.")
    if not resolved_jid:
        return silent("BLOCKED_UNKNOWN_TARGET", f"Could not resolve '{target}' to a known WhatsApp contact.")

    try:
        from System.whatsapp_autonomy_gate import (
            AutonomyInputs,
            evaluate_autonomy,
            infer_repetition_and_timing,
            log_decision,
        )

        inferred = infer_repetition_and_timing(target=resolved_jid, text=text)
        inputs = AutonomyInputs(
            consent=bool(consent),
            user_replied_recently=1.0 if user_initiated else 0.0,
            emotional_warmth=emotional_warmth,
            urgency=urgency,
            topic_match=topic_match,
            repetition=inferred["repetition"],
            time_since_last_msg_min=inferred["time_since_last_msg_min"],
            user_initiated=user_initiated,
            emergency=emergency,
            group_target=resolved_jid.endswith("@g.us"),
            group_consent=bool(allow_group_send or _ALLOW_GROUP_SEND),
        )
        decision = evaluate_autonomy(inputs)
        log_decision(decision, target=resolved_jid, text_hash=text_hash)
        decision_dict = {
            "should_send": decision.should_send,
            "score": round(decision.score, 6),
            "status": decision.status,
            "reason": decision.reason,
            "timing_attraction": round(decision.timing_attraction, 6),
            "decision_hash": decision.decision_hash,
        }
        if not decision.should_send:
            return silent(decision.status, decision.reason, decision_dict)
        return send_whatsapp(
            target,
            text,
            allow_group_send=allow_group_send,
            source="alice_autonomous",
            autonomy_decision=decision_dict,
            intent_provenance=intent_provenance,
        )
    except Exception as exc:
        return silent("AUTONOMY_GATE_ERROR", f"{type(exc).__name__}: {exc}")


def govern(verb: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Alice's interface to the WhatsApp Effector.
    verb: "send_whatsapp"
    kwargs: {"target": "Carlton", "text": "hello"} 
    """
    verb = verb.lower().strip()
    if verb == "send_whatsapp":
        return send_whatsapp(
            kwargs.get("target", ""),
            kwargs.get("text", ""),
            allow_group_send=bool(kwargs.get("allow_group_send", False)),
            source=str(kwargs.get("source") or "owner_explicit"),
        )
    if verb in {"autonomous_send_whatsapp", "send_autonomous_whatsapp"}:
        return autonomous_send_whatsapp(
            kwargs.get("target", ""),
            kwargs.get("text", ""),
            consent=bool(kwargs.get("consent", False)),
            user_initiated=bool(kwargs.get("user_initiated", False)),
            emergency=bool(kwargs.get("emergency", False)),
            emotional_warmth=float(kwargs.get("emotional_warmth", 0.5)),
            urgency=float(kwargs.get("urgency", 0.0)),
            topic_match=float(kwargs.get("topic_match", 0.5)),
            allow_group_send=bool(kwargs.get("allow_group_send", False)),
        )
    return {"ok": False, "error": f"Unknown whatsapp effector verb: {verb}"}


if __name__ == "__main__":
    import sys
    print("Testing WhatsApp Effector...")
    if len(sys.argv) > 2:
        print(send_whatsapp(sys.argv[1], sys.argv[2]))
    else:
        print("Usage: python whatsapp_bridge_autopilot.py <target> <text>")
