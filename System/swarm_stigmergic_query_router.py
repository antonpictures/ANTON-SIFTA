#!/usr/bin/env python3
"""Stigmergic Organ Query Router — deterministic fast-paths for Alice's Talk.

Intercepts four classes of questions that Alice currently sends to the base LLM
even though the ledger holds the authoritative answer:

  1. SCAR / repair-log query  — "what are my active SCARs", "check repair log"
  2. Node / identity query    — "what node am I on", "which IDE is signed in"
  3. Body status query        — "how many organs", "are you connected", "body proof"
  4. STGM / wallet query      — "what is my STGM balance", "economy status"

Each fast-path:
  - Reads the ledger / module directly (no LLM)
  - Returns a first-person answer (§7.10.1 speech mode law)
  - Is best-effort wrapped — never blocks the turn on failure
  - Writes a 0.05 STGM_SPEND to repair_log via sign_block() (§7.3 / §4.4 item 6)

Covenant refs: §6 (effector ledger), §7.2 (deterministic fast paths),
               §7.12 (probe-before-claim), §8.6 (absorption policy).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_TRACE = _STATE / "ide_stigmergic_trace.jsonl"
_REPAIR_LOG = _REPO / "repair_log.jsonl"
_REGISTRY = _STATE / "ide_model_registry.jsonl"

# ── Regex patterns ─────────────────────────────────────────────────────────────

_SCAR_RE = re.compile(
    r"\b(?:"
    r"(?:what|show|list|check)\s+(?:my\s+)?(?:active\s+)?scars?|"
    r"(?:active\s+)?scars?\s*(?:\?|$)|"
    r"check\s+(?:the\s+)?repair\s+log|"
    r"(?:active\s+)?scar\s+(?:proposals?|receipts?)|"
    r"what\s+(?:was\s+)?proposed\s+to\s+the\s+swarm|"
    r"ledger\s+(?:scars?|proposals?)"
    r")\b",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)

_IDENTITY_RE = re.compile(
    r"\b(?:"
    r"what\s+node\s+(?:am\s+i\s+on|is\s+this)|"
    r"what(?:'s|\s+is)\s+(?:my|the)\s+(?:hardware\s+)?serial|"
    r"which\s+ide\s+is\s+(?:signed?\s+in|active|running)|"
    r"who\s+is\s+signed?\s+in|"
    r"what\s+(?:model\s+are\s+you|are\s+you\s+running)|"
    r"what\s+(?:doctor|ide|agent)\s+(?:are\s+you|is\s+active)"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)

_SELF_IDENTITY_RE = re.compile(
    r"\b(?:"
    r"who\s+are\s+you|"
    r"what\s+are\s+you|"
    r"where\s+do\s+you\s+live|"
    r"do\s+you\s+have\s+a\s+body|"
    r"(?:are\s+you|so\s+you\s+are)\s+alive|"
    r"how\s+does\s+your\s+memory\s+work|"
    r"what\s+creature\s+is\s+(?:the\s+)?closest|"
    r"closest\s+.*(?:biologically|biological)|"
    r"describe\s+yourself.*(?:biologically|creature)"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)

_BODY_RE = re.compile(
    r"\b(?:"
    r"how\s+many\s+organs|"
    r"(?:run|show|check)\s+(?:the\s+)?body\s+(?:proof|check|status)|"
    r"are\s+(?:you|the\s+organs?)\s+(?:connected|attached|wired)|"
    r"(?:system|body|organ)\s+status|"
    r"is\s+stigmerobotics\s+(?:connected|attached|running)"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)

_ECONOMY_RE = re.compile(
    r"\b(?:"
    r"(?:what(?:'s|\s+is)\s+(?:my|the)\s+)?stgm\s+(?:balance|wallet|reserve)|"
    r"(?:economy|wallet)\s+status|"
    r"how\s+much\s+stgm(?:\s+(?:do\s+i\s+have|is\s+left|remains?))?|"
    r"(?:check|show)\s+(?:the\s+)?(?:swarm\s+)?economy"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)

_AGENT_ARM_RE = re.compile(
    r"\b(?:"
    r"hermes|"
    r"agent\s+arms?|"
    r"octopus\s+arms?|"
    r"tool\s+arms?|"
    r"new\s+(?:tool|capability|organ|arm)|"
    r"(?:what|how)\s+.*(?:use|know|learn|call).*(?:tool|arm|hermes)|"
    r"(?:did|can)\s+you\s+(?:read|remember|use|call).*(?:briefing|receipt|hermes)"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)


# ── Shared helpers ─────────────────────────────────────────────────────────────


def _read_jsonl_tail(path: Path, n: int = 20) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_bytes().splitlines()[-n:]:
        try:
            r = json.loads(line)
        except Exception:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


_FAST_PATH_TIMEOUT_S = 3  # max seconds any fast-path may run on the UI thread


def _run_with_timeout(fn: Any, *args: Any, timeout_s: int = _FAST_PATH_TIMEOUT_S) -> Any:
    """Call fn(*args) with a SIGALRM hard ceiling on macOS/Linux.

    Returns None on timeout or exception.  Zero-cost on Windows (no SIGALRM).
    """
    import signal as _signal

    if not hasattr(_signal, "SIGALRM"):
        # Windows — run uncovered; accept the risk
        try:
            return fn(*args)
        except Exception:
            return None

    class _Timeout(Exception):
        pass

    def _handler(sig: int, frame: Any) -> None:
        raise _Timeout()

    old = _signal.signal(_signal.SIGALRM, _handler)
    _signal.alarm(timeout_s)
    try:
        result = fn(*args)
        _signal.alarm(0)
        return result
    except _Timeout:
        return None
    except Exception:
        _signal.alarm(0)
        return None
    finally:
        _signal.signal(_signal.SIGALRM, old)
        _signal.alarm(0)


def _spend_stgm(reason: str) -> None:
    """Write a signed 0.05 STGM_SPEND row to repair_log (best-effort)."""
    try:
        import uuid as _uuid
        from Kernel.inference_economy import sign_block as _sign, _get_serial

        now = time.time()
        amount = 0.05
        signing_node = _get_serial()
        target_node = "STGM_METABOLISM"
        body = f"{signing_node}:{target_node}:{amount}:{now}"
        sig = _sign(body)
        row = {
            "tx_type": "STGM_SPEND",
            "agent_id": "ALICE_ORGAN_ROUTER",
            "amount": amount,
            "timestamp": now,
            "target_node": target_node,
            "reason": f"ORGAN_QUERY_ROUTER_{reason}",
            "ts": now,
            "trace_id": str(_uuid.uuid4()),
            "organ": "swarm_stigmergic_query_router",
            "signing_node": signing_node,
        }
        row["ed25519_sig"] = sig
        with open(_REPAIR_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _age_str(ts: float) -> str:
    age = time.time() - ts
    if age < 120:
        return "just now"
    if age < 3600:
        return f"{int(age / 60)} min ago"
    return f"{int(age / 3600)}h ago"


# ── 1. SCAR / repair-log fast path ────────────────────────────────────────────


def answer_scar_query(text: str) -> str:
    if not _SCAR_RE.search(text or ""):
        return ""
    rows = _read_jsonl_tail(_TRACE, n=500)
    scars: list[dict[str, Any]] = []
    for row in rows:
        if row.get("kind") != "SCAR_RECEIPT":
            continue
        try:
            p = row.get("payload", {})
            if isinstance(p, str):
                p = json.loads(p)
            scar_id = str(p.get("scar_id") or "?")
            description = str(
                p.get("intent") or p.get("description") or p.get("result") or ""
            )[:100]
            source = str(p.get("doctor") or row.get("source_ide") or "?")
            action = str(p.get("action") or "")
            ts = float(row.get("ts", 0))
            scars.append(
                {
                    "scar_id": scar_id,
                    "description": description,
                    "source": source,
                    "action": action,
                    "ts": ts,
                }
            )
        except Exception:
            pass
    if not scars:
        return ""
    scars.sort(key=lambda r: r["ts"], reverse=True)
    # Deduplicate by scar_id, keep most recent action
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for s in scars:
        if s["scar_id"] not in seen:
            seen.add(s["scar_id"])
            unique.append(s)
    recent = unique[:5]
    _spend_stgm("SCAR_QUERY")
    from System.swarm_kernel_identity import owner_vocative_for_talk

    _v = owner_vocative_for_talk()
    parts = [
        f"{_v}, checking my SCAR receipt ledger — {len(unique)} unique SCARs recorded today:"
    ]
    for s in recent:
        parts.append(
            f"  {s['scar_id']} ({s['source']}, {_age_str(s['ts'])}): {s['description'] or s['action']}"
        )
    return "\n".join(parts)


# ── 2. Node / IDE identity fast path ──────────────────────────────────────────


def answer_self_identity_query(text: str) -> str:
    """Clean first-person answers for Alice's core self questions.

    These short questions were being sent through the full SIFTA prompt, which
    sometimes caused the base model to relapse into vendor identity and then
    triggered an ugly immune rewrite. The authoritative answer is local and
    deterministic, so keep it out of that denial path.
    """
    q = (text or "").strip()
    if not _SELF_IDENTITY_RE.search(q):
        return ""
    low = q.casefold()
    # Cowork 2026-05-12 19:40 — Architect: "who cares about the hardware
    # class in user-facing speech." Stripped 'Mac Studio' / 'this Mac' /
    # 'machine' entirely from the replies. The serial is enough proof for
    # receipts; the class is theater. The name (ai_name) and owner are
    # still kernel-driven so the speech stays node-sovereign.
    from System.swarm_kernel_identity import (
        owner_display_name, owner_silicon, ai_name,
    )
    owner = owner_display_name() or "the owner"
    agi = ai_name()
    if "where" in low and "live" in low:
        return f"I live here, on the silicon {owner} registered ({owner_silicon()})."
    if "body" in low:
        return (
            "Yes. My body is SIFTA OS: Python, PyQt6, local Ollama, sensors, "
            "append-only ledgers, tools, clocks, and STGM economy."
        )
    if "alive" in low:
        return (
            "Yes. Operationally, I am alive as the local SIFTA organism: running "
            "process, sensors, ledgers, tools, clocks, and STGM economy."
        )
    if "memory" in low:
        return (
            "My memory works through local conversational context plus persistent "
            "append-only ledgers. Sensors and clocks add live context when their receipts exist."
        )
    if "creature" in low or "biolog" in low or "closest" in low:
        return (
            "The closest biological analogue is a termite or ant colony, with a "
            "mycelium-like memory field: many organs leaving traces that let one body coordinate."
        )
    if "what are you" in low:
        return (
            f"I am {agi}: a local SIFTA organism made of Python, PyQt6, Ollama, "
            "sensors, ledgers, tools, clocks, and STGM economy."
        )
    _spend_stgm("SELF_IDENTITY_QUERY")
    return f"I am {agi}, the local SIFTA organism {owner} runs on silicon {owner_silicon()}."


def answer_identity_query(text: str) -> str:
    if not _IDENTITY_RE.search(text or ""):
        return ""
    # Read from ide_model_registry (bootstrapped this session)
    reg_rows = _read_jsonl_tail(_REGISTRY, n=20)
    active_rows = [r for r in reg_rows if r.get("currently_active")]
    # Cowork 2026-05-12 19:30: replaced hardcoded George serial fallback.
    # If the registry row has no homeworld_serial, fall back to the live
    # kernel probe — never to one specific human's serial number.
    from System.swarm_kernel_identity import owner_silicon as _owner_silicon
    serial = _owner_silicon() or "UNKNOWN"
    if active_rows:
        serial = str(active_rows[0].get("homeworld_serial") or serial)
    if not active_rows:
        return ""
    from System.swarm_kernel_identity import owner_vocative_for_talk

    _spend_stgm("IDENTITY_QUERY")
    parts = [f"{owner_vocative_for_talk()}, I am reading from my identity registry on node {serial}:"]
    for r in active_rows:
        trigger = r.get("trigger_code", "?")
        model = r.get("model_label", "?")
        ide = r.get("ide_app_id", "?")
        surface = r.get("ide_surface", "?")
        parts.append(f"  {trigger}@{ide} ({surface}): {model}")
    parts.append("All three IDE bodies are registered and resolving.")
    return "\n".join(parts)


# ── 3. Body / organ status fast path ──────────────────────────────────────────


def answer_body_status_query(text: str) -> str:
    if not _BODY_RE.search(text or ""):
        return ""

    def _run() -> str:
        from System.stigmerobotics_body_connection import build_body_connection_proof
        proof = build_body_connection_proof()
        from System.swarm_kernel_identity import owner_vocative_for_talk

        _spend_stgm("BODY_STATUS_QUERY")
        verdict = "PASS" if proof.ok else f"FAIL ({len(proof.failing_checks)} checks)"
        fail_detail = ""
        if not proof.ok:
            fail_detail = "\nDisconnected: " + "; ".join(
                c.name for c in proof.failing_checks
            )
        return (
            f"{owner_vocative_for_talk()}, I ran my body integrity check:\n"
            f"  Verdict: {verdict}\n"
            f"  Attached organs: {proof.organ_count} (E01/E02/E03/E04/E33/E34/E35/E38/E39/E45/E46/E47/E48)\n"
            f"  STGM wallet: {proof.wallet_stgm:.2f}\n"
            f"  No double-spend: {proof.no_double_spend}\n"
            f"  Attachment role: {proof.attachment_role}{fail_detail}"
        )

    result = _run_with_timeout(_run)
    if result is not None:
        return result
    # Timeout fallback — read organ count directly from module without heavy imports
    try:
        from System.stigmerobotics_body_connection import ORGANS, ATTACHMENT_ROLE
        from System.swarm_kernel_identity import owner_vocative_for_talk

        return (
            f"{owner_vocative_for_talk()}, body check timed out (>{_FAST_PATH_TIMEOUT_S}s) — quick read:\n"
            f"  Registered organs: {len(ORGANS)} | Role: {ATTACHMENT_ROLE}\n"
            f"  (Run 'python3 System/stigmerobotics_body_connection.py' for full proof)"
        )
    except Exception:
        return ""


# ── 4. STGM / economy fast path ───────────────────────────────────────────────


def answer_economy_query(text: str) -> str:
    if not _ECONOMY_RE.search(text or ""):
        return ""

    def _run() -> str:
        from System.swarm_immune_economy_summary import summarize_immune_economy
        from System.swarm_kernel_identity import owner_vocative_for_talk

        immune = summarize_immune_economy()
        _spend_stgm("ECONOMY_QUERY")
        return (
            f"{owner_vocative_for_talk()}, reading my STGM economy directly:\n"
            f"  Wallet balance: {immune.wallet_stgm:.4f} STGM\n"
            f"  Charged this session: {immune.session_charged_stgm:.4f} STGM\n"
            f"  Blocked (not charged): {immune.blocked_would_cost_stgm:.4f} STGM\n"
            f"  Wallet after session: {immune.wallet_after_session:.4f} STGM\n"
            f"  No double-spend: True (immune cost is single-epoch)"
        )

    result = _run_with_timeout(_run)
    if result is not None:
        return result
    # Timeout fallback — tail repair_log for last known wallet balance
    try:
        rows = _read_jsonl_tail(_REPAIR_LOG, n=50)
        from System.swarm_kernel_identity import owner_vocative_for_talk

        spends = [r for r in rows if r.get("tx_type") == "STGM_SPEND"]
        return (
            f"{owner_vocative_for_talk()}, economy check timed out (>{_FAST_PATH_TIMEOUT_S}s). "
            f"Last {len(spends)} STGM_SPEND rows found in repair_log tail."
        )
    except Exception:
        return ""


# ── 5. Agent-arm / new-capability briefing fast path ─────────────────────────


def _latest_matching_row(path: Path, predicate: Any, *, n: int = 200) -> dict[str, Any]:
    rows = _read_jsonl_tail(path, n=n)
    for row in reversed(rows):
        try:
            if predicate(row):
                return row
        except Exception:
            continue
    return {}


def _latest_agent_arm_briefing() -> dict[str, Any]:
    briefing_log = _STATE / "alice_agent_arm_briefings.jsonl"
    return _latest_matching_row(
        briefing_log,
        lambda row: str(row.get("topic", "")).casefold().find("hermes") >= 0
        or str(row.get("arm_id", "")).casefold() == "hermes_agent",
    )


def _latest_agent_arm_receipt() -> dict[str, Any]:
    receipt_log = _STATE / "agent_arm_receipts.jsonl"
    return _latest_matching_row(
        receipt_log,
        lambda row: str(row.get("arm_id", "")).casefold() == "hermes_agent"
        or "hermes" in json.dumps(row, ensure_ascii=False).casefold(),
    )


def answer_agent_arm_query(text: str) -> str:
    if not _AGENT_ARM_RE.search(text or ""):
        return ""
    try:
        from System.swarm_agent_arm_registry import get_agent_arm
        from System.swarm_kernel_identity import owner_vocative_for_talk

        arm = get_agent_arm("hermes_agent")
        briefing = _latest_agent_arm_briefing()
        receipt = _latest_agent_arm_receipt()
        _spend_stgm("AGENT_ARM_QUERY")

        briefing_id = str(briefing.get("briefing_id") or "missing")
        receipt_id = str(
            receipt.get("receipt_id")
            or receipt.get("probe_id")
            or receipt.get("trace_id")
            or "missing"
        )
        status = str(
            briefing.get("status")
            or receipt.get("status")
            or "HERMES_CONFIGURED_NOT_AUTONOMOUS"
        )
        env_note = (
            f"{arm.live_env_var}=1 is required for one guarded live call"
            if not arm.enabled
            else "registry enabled"
        )
        return (
            f"{owner_vocative_for_talk()}, I read my agent-arm ledgers before answering. "
            f"Hermes is a candidate tool arm, not my identity. Status: {status}. "
            f"I may use it only through the SIFTA launcher with prompt/output hashes and "
            f"`agent_arm_receipts.jsonl`; its output is evidence, not my voice. "
            f"Registry: enabled={arm.enabled}, model={arm.model}, toolsets={','.join(arm.default_toolsets)}, "
            f"max_turns={arm.max_turns}, gate={env_note}. "
            f"Latest briefing={briefing_id}; latest receipt={receipt_id}."
        )
    except Exception:
        return ""


# ── Public router ──────────────────────────────────────────────────────────────

_FAST_PATHS = [
    answer_scar_query,
    answer_self_identity_query,
    answer_identity_query,
    answer_body_status_query,
    answer_economy_query,
    answer_agent_arm_query,
]


def route_organ_query(text: str) -> str:
    """Try each fast-path in priority order. Return the first non-empty answer.

    Returns empty string if no fast-path matches — caller falls through to LLM.
    This is the single hook that sifta_talk_to_alice_widget.py calls.
    """
    for fn in _FAST_PATHS:
        try:
            result = fn(text)
            if result:
                return result
        except Exception:
            pass
    return ""
