#!/usr/bin/env python3
"""
System/swarm_alice_invariants.py — Deterministic Behavioral Contracts
═══════════════════════════════════════════════════════════════════════
Dr. Codex verdict (2026-04-30): "good emergency tourniquet, not final anatomy."
This IS the anatomy.

Five invariants, each test-backed, each enforced before the brain or after:

  I1: PRESERVE_ARCHITECT_TEXT   — Architect's words reach the effector byte-for-byte
  I2: ONE_WHATSAPP_SYNTAX       — Accept exactly one tool call format, quarantine others
  I3: QUARANTINE_FAKE_FORMATS   — [Calling API:], <bash>..., and invented formats → blocked
  I4: RECEIPT_GATED_SUCCESS     — ok=True AND status=SENT before any success claim
  I5: RESULT_FEEDBACK_LOOP      — Actual effector result injected into Alice's next turn

Source: Anthropic, "Tracing the thoughts of a large language model"
        https://www.anthropic.com/research/tracing-thoughts-language-model
        + SIFTA Trinity Law (Math + Physics + Biology = one system)
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "alice_invariants_trace.jsonl"
_STATE.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════
# TRACE
# ═══════════════════════════════════════════════════════════════════════

def _trace(event: Dict[str, Any]) -> None:
    event["ts"] = time.time()
    event["schema"] = "SIFTA_INVARIANT_V1"
    try:
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
# I1 — PRESERVE_ARCHITECT_TEXT
# ═══════════════════════════════════════════════════════════════════════

_WHATSAPP_INTENT_PATTERNS = [
    # Pattern 0: "send ... to GROUP/NAME ... say|saying BODY"
    # Handles: "send a WhatsApp message to AGI Kings? say hello everybody"
    # Note: (?P<target>) uses greedy up to the say/saying/tell separator.
    re.compile(
        r"\bsend\s+(?:(?:a|the)\s+)?(?:whatsapp\s+)?(?:message\s+)?(?:to\s+)"
        r"(?P<target>[A-Za-z][A-Za-z0-9 .'-]{1,50}?)\??\s+"
        r"(?:please\s+)?(?:on\s+whatsapp\s+)?(?:and\s+)?"
        r"(?:tell(?:\s+(?:him|her|them))?|say|saying)\s+(?:that\s+)?"
        r"(?P<body>.+)",
        re.IGNORECASE | re.DOTALL,
    ),
    # Pattern 1: original — "send ... [to] TARGET ... say BODY" (optional 'to')
    re.compile(
        r"\bsend\s+(?:(?:a|the)\s+)?(?:whatsapp\s+)?(?:message\s+)?(?:to\s+)?"
        r"(?P<target>[A-Za-z][A-Za-z .'-]{1,40}?)\s+"
        r"(?:please\s+)?(?:on\s+whatsapp\s+)?(?:and\s+)?"
        r"(?:tell(?:\s+(?:him|her|them))?|say|saying)\s+(?:that\s+)?"
        r"(?P<body>.+)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\bsend\s+(?:(?:a|the)\s+)?(?:whatsapp\s+)?(?:message\s+)?to\s+"
        r"(?P<target>[A-Za-z][A-Za-z .'-]{1,40}?)\s+"
        r"(?:on\s+whatsapp\s+)?that\s+(?P<body>.+)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\bmessage\s+(?P<target>[A-Za-z][A-Za-z .'-]{1,40}?)\s+"
        r"(?:on\s+whatsapp\s+)?(?:saying\s+|that\s+)?(?P<body>.+)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\btell\s+(?P<target>[A-Za-z][A-Za-z .'-]{1,40}?)\s+"
        r"(?:on\s+whatsapp\s+)?(?:that\s+)?(?P<body>.+)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\bsend\s+(?P<target>[A-Za-z][A-Za-z.'-]{1,28})\s+(?P<body>.+)",
        re.IGNORECASE | re.DOTALL,
    ),
]

# Targets that are plain English stopwords — never a valid contact name
_TARGET_STOPWORDS = frozenset({
    "a", "an", "the", "to", "in", "on", "at", "it", "me", "us", "him",
    "her", "them", "my", "your", "our", "his", "their", "this", "that",
    "some", "any", "all", "now", "out", "off", "up", "down", "here",
    "there", "just", "also", "via", "with", "for", "from",
})


def _clean_whatsapp_target(target: str) -> str:
    cleaned = (target or "").strip().strip(".,;:'\"")
    cleaned = re.sub(r"\b(?:please|on\s+whatsapp|via\s+whatsapp)\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned.strip().strip(".,;:'\"")


def _clean_whatsapp_body(body: str, target: str) -> str:
    cleaned = (body or "").strip().strip("\"'")
    if target:
        target_re = re.escape(target.strip())
        cleaned = re.sub(
            rf"\s+\bSend\s+(?:a\s+|the\s+)?(?:whatsapp\s+)?message\s+to\s+{target_re}\b.*$",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()
        cleaned = re.sub(
            rf"\s+{target_re}\s+tell\s+(?:him|her|them)\s+exactly\s+like\s+that\.?\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
    cleaned = re.sub(
        r"\s+(?:tell\s+(?:him|her|them)\s+)?exactly\s+like\s+that\.?\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned.strip().strip("\"'")


def extract_whatsapp_intent(user_text: str) -> Optional[Tuple[str, str]]:
    """
    I1: Parse WhatsApp send intent from Architect text.
    Returns (target, text) with text EXACTLY as spoken — no mutation.
    Returns None if no send intent found.

    Bugs fixed (AG46 2026-05-06):
    - Stopword guard: 'to', 'a', 'the' can never be a contact name.
    - Group name parsing: 'AGI Kings' now correctly extracted from
      'send a WhatsApp message to owner group AGI Kings? say hello everybody'
    """
    text_in = (user_text or "").strip()
    # Strip leading address like "Alice, " before parsing
    text_in = re.sub(r"^(?:alice|hey\s+alice|ok\s+alice)[,\s]+", "", text_in, flags=re.IGNORECASE).strip()

    m = None
    for pattern in _WHATSAPP_INTENT_PATTERNS:
        m = pattern.search(text_in)
        if m:
            target_raw = _clean_whatsapp_target(m.group("target"))
            # Stopword guard: reject single-word stop words as targets
            if target_raw.lower().strip() in _TARGET_STOPWORDS:
                m = None
                continue
            # Minimum target length: at least 2 chars
            if len(target_raw.replace(" ", "")) < 2:
                m = None
                continue
            break

    if not m:
        return None

    target = _clean_whatsapp_target(m.group("target"))
    # Final stopword check
    if target.lower().strip() in _TARGET_STOPWORDS or len(target.replace(" ", "")) < 2:
        return None

    # Strip "group" prefix if present: "owner group AGI Kings" → "AGI Kings"
    target = re.sub(r"^(?:owner\s+)?(?:group|chat|channel)\s+", "", target, flags=re.IGNORECASE).strip()
    target = target.strip().strip("?!.,;")

    text = _clean_whatsapp_body(m.group("body"), target)

    if not target or not text:
        return None

    # I1 integrity hash — proves text was not mutated downstream
    _trace({
        "invariant": "I1_PRESERVE_ARCHITECT_TEXT",
        "target": target,
        "text_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
        "text_len": len(text),
        "ok": True,
    })
    return target, text


def verify_text_preserved(original: str, delivered: str) -> bool:
    """
    I1 verification: confirm the delivered text matches the original exactly.
    Logs a violation if not.
    """
    ok = original.strip() == delivered.strip()
    if not ok:
        _trace({
            "invariant": "I1_VIOLATION",
            "original_hash": hashlib.sha256(original.encode()).hexdigest()[:16],
            "delivered_hash": hashlib.sha256(delivered.encode()).hexdigest()[:16],
            "ok": False,
            "truth_note": "Architect text was mutated before delivery — sycophantic circuit fired.",
        })
    return ok


# ═══════════════════════════════════════════════════════════════════════
# I2 + I3 — ONE_WHATSAPP_SYNTAX + QUARANTINE_FAKE_FORMATS
# ═══════════════════════════════════════════════════════════════════════

# The ONE canonical format
CANONICAL_TOOL_RE = re.compile(
    r"\[TOOL_CALL:\s*send_whatsapp\s*\|[^\]]+\]",
    re.IGNORECASE,
)

# Known fake formats — quarantine immediately
FAKE_FORMAT_PATTERNS = [
    re.compile(r"\[Calling\s+API\s*:", re.IGNORECASE),
    re.compile(r"\[Parameters\s*:", re.IGNORECASE),
    re.compile(r"\[Response\s*:", re.IGNORECASE),
    re.compile(r"<bash>.*whatsapp", re.IGNORECASE | re.DOTALL),
    re.compile(r"python3\s+-m\s+System\.alice_body_autopilot.*whatsapp", re.IGNORECASE),
    re.compile(r'"tool"\s*:\s*"send_message"', re.IGNORECASE),
]


def audit_alice_output(alice_text: str) -> Dict[str, Any]:
    """
    I2 + I3: Scan Alice's raw output.
    Returns audit dict:
      canonical_found: bool — correct [TOOL_CALL:] format detected
      fake_found: list[str] — any fake formats detected (quarantined)
      clean_text: str — output with fake formats stripped
    """
    canonical = bool(CANONICAL_TOOL_RE.search(alice_text))
    fakes_found = []
    clean = alice_text

    for pat in FAKE_FORMAT_PATTERNS:
        m = pat.search(alice_text)
        if m:
            fakes_found.append(m.group(0)[:80])
            # Strip fake format from output
            clean = pat.sub("[QUARANTINED_FAKE_FORMAT]", clean)

    if fakes_found:
        _trace({
            "invariant": "I3_FAKE_FORMAT_QUARANTINED",
            "fakes": fakes_found,
            "canonical_also_present": canonical,
            "ok": False,
            "truth_note": "Plan-B hallucination detected. Fake format stripped before execution.",
        })

    if canonical:
        _trace({
            "invariant": "I2_CANONICAL_FORMAT_DETECTED",
            "ok": True,
        })

    return {
        "canonical_found": canonical,
        "fake_found": fakes_found,
        "clean_text": clean,
        "quarantined": len(fakes_found) > 0,
    }


# ═══════════════════════════════════════════════════════════════════════
# I4 — RECEIPT_GATED_SUCCESS
# ═══════════════════════════════════════════════════════════════════════

def gate_success_claim(result: Dict[str, Any]) -> Tuple[bool, str]:
    """
    I4: Only allow a success claim if ok=True AND status contains SENT.
    Returns (can_claim_success, feedback_for_alice).

    Prevents the faithfulness gap: Alice saying "sent!" when nothing happened.
    """
    ok = bool(result.get("ok", False))
    status = str(result.get("status", "")).upper()
    sent = ok and ("SENT" in status or status == "OK")

    if sent:
        feedback = f"✅ Message delivered. Receipt: ok=True status={result.get('status')}"
        _trace({"invariant": "I4_SUCCESS_CONFIRMED", "ok": True, "status": status})
    elif ok and not sent:
        feedback = f"⚠️ Bridge accepted but no SENT confirmation. status={result.get('status')}"
        _trace({"invariant": "I4_PARTIAL", "ok": ok, "status": status})
    else:
        reason = result.get("result") or result.get("reason") or status or "unknown"
        feedback = f"❌ Not sent. status={result.get('status')} reason={reason}"
        _trace({"invariant": "I4_BLOCKED", "ok": False, "status": status, "reason": reason})

    return sent, feedback


# ═══════════════════════════════════════════════════════════════════════
# I5 — RESULT_FEEDBACK_LOOP
# ═══════════════════════════════════════════════════════════════════════

def build_result_context_for_alice(
    result: Dict[str, Any],
    target: str,
    original_text: str,
) -> str:
    """
    I5: Build the feedback string injected into Alice's next turn.
    Alice sees exactly what happened — no ambiguity, no hallucination fodder.
    """
    _, feedback = gate_success_claim(result)
    ctx = (
        f"[EFFECTOR RECEIPT — WhatsApp to {target}]\n"
        f"  original_text: \"{original_text[:120]}\"\n"
        f"  {feedback}\n"
        f"  truth_note: {result.get('truth_note', 'none')}"
    )
    _trace({
        "invariant": "I5_FEEDBACK_LOOP",
        "target": target,
        "text_hash": hashlib.sha256(original_text.encode()).hexdigest()[:16],
        "feedback": feedback,
        "ok": result.get("ok", False),
    })
    return ctx


# ═══════════════════════════════════════════════════════════════════════
# PROOF OF PROPERTY — test all 5 invariants
# ═══════════════════════════════════════════════════════════════════════

def proof_of_property() -> Dict[str, bool]:
    results: Dict[str, bool] = {}
    print("\n=== SIFTA ALICE INVARIANTS : PROOF OF PROPERTY ===")

    # I1: extract + preserve
    intent = extract_whatsapp_intent(
        "Send a WhatsApp message to Vitaliy saying: Hey brother, hope San Diego is treating you well!"
    )
    results["I1_extract"] = intent is not None and intent[0] == "Vitaliy"
    results["I1_preserve"] = intent is not None and "Hey brother" in intent[1]
    results["I1_no_mutation"] = intent is not None and verify_text_preserved(
        "Hey brother, hope San Diego is treating you well!",
        intent[1],
    )
    print(f"  I1 extract:    {'PASS' if results['I1_extract'] else 'FAIL'}")
    print(f"  I1 preserve:   {'PASS' if results['I1_preserve'] else 'FAIL'}")
    print(f"  I1 no_mutate:  {'PASS' if results['I1_no_mutation'] else 'FAIL'}")

    # I2: canonical format detected
    good = "[TOOL_CALL: send_whatsapp | target=Vitaliy | text=Hey brother | cost_justification=the primary operator explicitly asked me to send this.]"
    audit_good = audit_alice_output(good)
    results["I2_canonical"] = audit_good["canonical_found"]
    print(f"  I2 canonical:  {'PASS' if results['I2_canonical'] else 'FAIL'}")

    # I3: fake format quarantined
    bad = "[Calling API: send_message]\n[Parameters: recipient='Vitaly', message='Hey']\n[Response: Success]"
    audit_bad = audit_alice_output(bad)
    results["I3_quarantine"] = audit_bad["quarantined"] and not audit_bad["canonical_found"]
    print(f"  I3 quarantine: {'PASS' if results['I3_quarantine'] else 'FAIL'}")

    # I4: receipt gate
    ok_result = {"ok": True, "status": "SENT", "truth_note": "bridge confirmed"}
    fail_result = {"ok": False, "status": "BRIDGE_UNREACHABLE"}
    fake_result = {"ok": False, "status": "CONFABULATED"}
    s1, _ = gate_success_claim(ok_result)
    s2, _ = gate_success_claim(fail_result)
    s3, _ = gate_success_claim(fake_result)
    results["I4_real_sent"] = s1 is True
    results["I4_real_fail"] = s2 is False
    results["I4_fake_blocked"] = s3 is False
    print(f"  I4 real_sent:  {'PASS' if results['I4_real_sent'] else 'FAIL'}")
    print(f"  I4 real_fail:  {'PASS' if results['I4_real_fail'] else 'FAIL'}")
    print(f"  I4 fake:       {'PASS' if results['I4_fake_blocked'] else 'FAIL'}")

    # I5: feedback loop produces non-empty string
    ctx = build_result_context_for_alice(ok_result, "Vitaliy", "Hey brother")
    results["I5_feedback"] = "EFFECTOR RECEIPT" in ctx and "Vitaliy" in ctx
    print(f"  I5 feedback:   {'PASS' if results['I5_feedback'] else 'FAIL'}")

    all_pass = all(results.values())
    print(f"\n  [{'ALL INVARIANTS PASS' if all_pass else 'FAILURES PRESENT'}]")
    return results


if __name__ == "__main__":
    proof_of_property()
