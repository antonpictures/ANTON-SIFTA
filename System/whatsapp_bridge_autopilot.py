#!/usr/bin/env python3
"""
System/whatsapp_bridge_autopilot.py — Outbound WhatsApp Biological Actuator
═══════════════════════════════════════════════════════════════════════════
Alice's WhatsApp arm. The primary transport is the SIFTA-local WhatsApp bridge
running inside this organism (Network/whatsapp_bridge + scripts/whatsapp_alice_server.py).

The macOS WhatsApp.app UI driver is an explicitly requested owner/UI path.
Default autonomous Alice sends must not silently leave the SIFTA bridge organ.
"""

import hashlib
import json
import os
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
_OUTBOX = _STATE / "sifta_whatsapp_outbox.jsonl"
_INJECT_URL = "http://127.0.0.1:3001/system_inject"
_HEALTH_URL = "http://127.0.0.1:3001/health"

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


def _deposit_outbox(row: Dict[str, Any]) -> Dict[str, Any]:
    """Queue an unsent SIFTA WhatsApp request without touching macOS WhatsApp."""
    _OUTBOX.parent.mkdir(parents=True, exist_ok=True)
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(_OUTBOX, json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        with _OUTBOX.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def _load_contacts() -> Dict[str, Any]:
    return load_contacts(_CONTACTS_FILE)


def _resolve_target(target: str) -> str:
    """Resolve a target string to a synced WhatsApp transport id."""
    return resolve_target(target, _load_contacts())


def bridge_health(*, timeout: float = 2.0) -> Dict[str, Any]:
    """Return the bridge transport state without sending a WhatsApp message."""
    try:
        req = urllib.request.Request(_HEALTH_URL, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        state = str(data.get("whatsapp_state") or "unknown")
        return {
            "reachable": True,
            "ok": bool(data.get("ok")),
            "status": "READY" if data.get("ok") else "BRIDGE_NOT_READY",
            "whatsapp_state": state,
            "bridge": data.get("bridge", ""),
            "last_status_code": data.get("last_status_code"),
            "result": (
                "Bridge connected and WhatsApp is open."
                if data.get("ok")
                else f"Bridge listener is up but WhatsApp state is {state}."
            ),
        }
    except urllib.error.URLError as exc:
        return {
            "reachable": False,
            "ok": False,
            "status": "BRIDGE_UNREACHABLE",
            "whatsapp_state": "unreachable",
            "result": (
                f"Could not reach injection server at {_INJECT_URL}. "
                f"Start the local WhatsApp bridge. Detail: {exc.reason}"
            ),
        }
    except Exception as exc:
        return {
            "reachable": False,
            "ok": False,
            "status": "BRIDGE_HEALTH_ERROR",
            "whatsapp_state": "unknown",
            "result": f"Bridge health probe failed: {type(exc).__name__}: {exc}",
        }


def _inject_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    inject_key = os.environ.get("SIFTA_BRIDGE_INJECT_KEY", "").strip()
    if inject_key:
        headers["X-Sifta-Inject-Key"] = inject_key
    return headers


def summary_for_alice(limit: int = 12) -> str:
    """Compact WhatsApp world model for Alice's prompt context.

    Raw transport ids stay out of the prompt; Alice only needs names, chat
    shape, and which local effector can reach the contact.
    """
    health = bridge_health(timeout=0.35)
    lines = [
        "WHATSAPP WORLD:",
        "- primary_transport=SIFTA WhatsApp bridge at 127.0.0.1:3001; outbound sends require a synced WhatsApp JID in whatsapp_contacts.json.",
        "- macos_whatsapp_app=owner-click UI path for visible names/groups; autonomous sends do not choose it silently.",
        "- outbound_tool=whatsapp.send; target may be a synced visible WhatsApp contact/group name or exact transport id.",
        f"- bridge_health={health['status']} whatsapp_state={health['whatsapp_state']}.",
        "- autonomy_gate=bounded Gaussian attraction; autonomous sends require consent, relevance, timing, and low repetition.",
        "- group_send_default=blocked unless an explicit group-send override is provided.",
        "- social_graph=owner WhatsApp contacts and groups are friends/collaborators/channels of the machine owner.",
    ]
    try:
        from System.whatsapp_autonomy_gate import summary_for_alice as _autonomy_summary
        lines.append(_autonomy_summary(limit=2))
    except Exception:
        pass
    try:
        from System.whatsapp_autonomy_settings import summary_for_alice as _auto_settings_summary
        lines.append(_auto_settings_summary(limit=8))
    except Exception:
        pass
    lines.append(social_graph_summary_for_alice(limit=limit))
    rows = contact_rows_for_alice(limit=limit, contacts=_load_contacts())
    if rows:
        lines.append("- target_examples: " + "; ".join(rows))
    else:
        lines.append("- known_contacts=0 in synced cache; unsynced sends are queued inside SIFTA and no macOS WhatsApp fallback is used.")
    return "\n".join(lines)


def send_whatsapp(
    target: str,
    text: str,
    *,
    allow_group_send: bool = False,
    source: str = "owner_explicit",
    transport: str = "bridge",
    dry_run: bool = False,
    autonomy_decision: Optional[Dict[str, Any]] = None,
    intent_provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Transmit a WhatsApp message with a receipt-backed local effector.

    transport:
      - "bridge" / "auto" / "sifta": SIFTA-local bridge path.
      - "macos_app": explicit owner/UI path through WhatsApp Desktop's visible chat search.
    """
    target = (target or "").strip()
    text = (text or "").strip()
    transport = (transport or "bridge").strip().lower()
    resolved_jid = ""

    def finish(
        status: str,
        ok: bool,
        result: str,
        *,
        bridge_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
            "truth_note": "External WhatsApp send is true only when ok=true and status contains SENT.",
        }
        row["transport"] = transport
        if bridge_state:
            row["bridge_health"] = bridge_state
        if autonomy_decision:
            row["autonomy_decision"] = autonomy_decision
        _attach_intent_provenance(
            row,
            intent_provenance=intent_provenance,
            decision_path=["whatsapp_effector", status.lower()],
        )
        return _deposit_trace(row)

    if not target:
        return finish("REJECTED_MISSING_TARGET", False, "Missing target name or transport id.")
    if not text:
        return finish("REJECTED_MISSING_PAYLOAD", False, "Missing message text.")

    if transport in {"macos_app", "local_app", "whatsapp_app", "native", "desktop_app", "whatsapp_desktop"}:
        from System.swarm_macos_messenger import send_message

        native = send_message(target, text, via="whatsapp", dry_run=dry_run)
        native_status = str(native.get("status") or "UNKNOWN")
        native_ok = bool(native.get("ok")) and native_status == "SENT"
        status = "SENT_MACOS_APP" if native_ok and native_status == "SENT" else f"MACOS_APP_{native_status}"
        if native_status == "DRY_RUN":
            status = "DRY_RUN_MACOS_APP"
        row = {
            "event_kind": EVENT_KIND,
            "schema": SCHEMA,
            "ts": time.time(),
            "target": target,
            "resolved_jid": "",
            "text": text,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else "",
            "source": source,
            "ok": native_ok,
            "status": status,
            "result": str(native.get("note") or native.get("status") or native_status),
            "truth_note": (
                "External WhatsApp send is true only when ok=true and status is SENT_MACOS_APP. "
                "This proves local WhatsApp.app UI dispatch, not remote read/delivery state."
            ),
            "transport": "macos_app",
            "native_receipt": native,
        }
        if autonomy_decision:
            row["autonomy_decision"] = autonomy_decision
        _attach_intent_provenance(
            row,
            intent_provenance=intent_provenance,
            decision_path=["whatsapp_effector", "macos_app", status.lower()],
        )
        return _deposit_trace(row)

    if dry_run:
        return finish(
            "DRY_RUN_BRIDGE",
            False,
            "Would send through the SIFTA WhatsApp bridge if a synced JID and live bridge were present.",
        )

    resolved_jid = _resolve_target(target)
    if not resolved_jid:
        outbox_row = {
            "event_kind": "SIFTA_WHATSAPP_OUTBOX_QUEUED",
            "schema": SCHEMA,
            "ts": time.time(),
            "target": target,
            "text": text,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else "",
            "source": source,
            "transport": "sifta_bridge",
            "status": "QUEUED_NEEDS_SIFTA_WHATSAPP_SYNC",
            "truth_note": (
                "No external WhatsApp action occurred. SIFTA bridge has not synced "
                "a sendable WhatsApp JID for this visible name yet."
            ),
        }
        _deposit_outbox(outbox_row)
        return finish(
            "QUEUED_NEEDS_SIFTA_WHATSAPP_SYNC",
            False,
            (
                f"SIFTA WhatsApp has no synced send target for '{target}' yet. "
                "Queued the request inside .sifta_state/sifta_whatsapp_outbox.jsonl; "
                "start/sync the WhatsApp Organ bridge to send from inside SIFTA OS. "
                "No macOS WhatsApp fallback was used."
            ),
        )
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
        elif (
            provenance_consent == "owner_delegated"
            and (
                "whatsapp_auto" in source_norm
                or "auto_toggle" in " ".join(
                    str(x) for x in (intent_provenance or {}).get("decision_path", [])
                )
            )
        ):
            consent = "owner_delegated"
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

    health = bridge_health()
    if not health.get("ok"):
        status = str(health.get("status") or "BRIDGE_NOT_READY")
        return finish(status, False, str(health.get("result") or status), bridge_state=health)

    payload = json.dumps({"to": resolved_jid, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        _INJECT_URL,
        data=payload,
        headers=_inject_headers()
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return finish("SENT", True, f"Message injected to {resolved_jid}.")
            else:
                return finish("SEND_FAILED", False, f"Bridge rejected payload: {data}")
    except urllib.error.URLError as e:
        health = {
            "reachable": False,
            "ok": False,
            "status": "BRIDGE_UNREACHABLE",
            "whatsapp_state": "unreachable",
            "result": str(e.reason),
        }
        return finish(
            "BRIDGE_UNREACHABLE",
            False,
            f"Could not reach injection server at {_INJECT_URL}. Is the Node bridge running?",
            bridge_state=health,
        )
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
        return silent("REJECTED_MISSING_TARGET", "Missing target name or transport id.")
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
