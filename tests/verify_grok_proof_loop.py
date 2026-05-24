#!/usr/bin/env python3
"""
verify_grok_proof_loop.py

Objective, receipt-grounded verifier for the full Grok delegation proof loop.

Owner acceptance (non-negotiable):
1. Alice sends the bounded task (GROK_DELEGATION in ledger).
2. Visible Grok in Matrix Terminal receives and prints answer.
3. Alice captures the actual text from the PTY transcript.
4. Alice posts it into global chat as GROK_RESULT.
5. The receipt contains captured_output_hash (or equivalent strong proof)
   AND a PTY transcript span / capture_id with meaningful length.

Dispatch receipt alone == FAIL.
"No readable Grok output" fallback == FAIL.
Real answer present but missing hash + span == FAIL.
Real captured answer + hash + span present in global chat == PASS.

This script reads live ledgers from .sifta_state/ and refuses to declare victory
on partial evidence. It is the objective gate.

Run from the ANTON_SIFTA project root:
    python3 tests/verify_grok_proof_loop.py

Self-test mode (synthetic ledgers) is always run first to prove the checker logic.
"""

import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = PROJECT_ROOT / ".sifta_state"

ALICE_CONVERSATION = STATE_DIR / "alice_conversation.jsonl"
GROK_DELEGATION_LEDGER = STATE_DIR / "grok_delegation_requests.jsonl"
TOOL_ROUTER_TRACE = STATE_DIR / "tool_router_trace.jsonl"  # if present


@dataclass
class ProofResult:
    passed: bool
    diagnosis: str
    details: Dict[str, Any]


def load_jsonl_tail(path: Path, max_lines: int = 500) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
    entries: List[Dict[str, Any]] = []
    for line in lines[-max_lines:]:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    return entries


def payload_of(entry: Dict[str, Any]) -> Dict[str, Any]:
    payload = entry.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    if isinstance(payload, dict):
        merged = dict(entry)
        merged.update(payload)
        return merged
    return entry


def action_of(entry: Dict[str, Any]) -> str:
    entry = payload_of(entry)
    meta = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
    routing = entry.get("routing_metadata") if isinstance(entry.get("routing_metadata"), dict) else {}
    return str(entry.get("action") or meta.get("action") or routing.get("action") or "").upper()


def text_of(entry: Dict[str, Any]) -> str:
    entry = payload_of(entry)
    return str(entry.get("text") or entry.get("content") or "")


def metadata_of(entry: Dict[str, Any]) -> Dict[str, Any]:
    entry = payload_of(entry)
    # SIFTA's ledger stores per-turn metadata under "routing_metadata" (see
    # sifta_talk_to_alice_widget._log_turn). Read that where "metadata" is absent.
    # This is a READER fix only — every strict hash/span check below is unchanged;
    # it does not relax the gate, it just looks where the proof actually lives
    # (action_of already reads routing_metadata; this makes metadata_of consistent).
    meta = entry.get("metadata")
    if not isinstance(meta, dict):
        meta = entry.get("routing_metadata")
    return meta if isinstance(meta, dict) else {}


def captured_body_from_text(text: str) -> str:
    body = str(text or "")
    if "Grok terminal transcript:" in body:
        body = body.split("Grok terminal transcript:", 1)[-1]
    elif "Grok result:" in body:
        body = body.split("Grok result:", 1)[-1]
    body = re.sub(r"\n+\[GROK_RESULT receipt:[^\]]+\]\s*$", "", body.strip(), flags=re.DOTALL)
    return body.strip()


def find_latest_grok_delegation(entries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for e in reversed(entries):
        text = text_of(e).lower()
        action = action_of(e).lower()
        if "grok_delegation" in action or "grok_delegation" in text:
            return e
    return None


def find_grok_result_in_conversation(entries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Look for a recent turn where Alice posted a GROK_RESULT with actual content."""
    for e in reversed(entries):
        pay = payload_of(e)
        role = str(pay.get("role", "")).lower()
        content = text_of(e)
        action = action_of(e)
        meta = metadata_of(e)
        if role not in {"assistant", "alice"}:
            continue
        low = content.lower()
        if action == "GROK_RESULT_CAPTURE_FAILED" or "no readable grok output" in low:
            return {"type": "fallback", "entry": pay, "content": content}
        if (
            action == "GROK_RESULT"
            or "grok terminal transcript:" in low
            or "grok result" in low
            or "grok_result" in low
        ):
            # Check for real captured text vs fallback
            if "no readable grok output" in low:
                return {"type": "fallback", "entry": pay, "content": content}
            body = captured_body_from_text(content)
            span = meta.get("pty_transcript_span") or meta.get("transcript_span") or {}
            output_hash = str(meta.get("captured_output_hash") or "")
            computed_hash = hashlib.sha256(body.encode("utf-8")).hexdigest() if body else ""
            # The hash must ACTUALLY bind to the captured text. A bare "len == 64"
            # check let any random 64-char string pass and proved nothing. Require
            # the stored hash to be a genuine prefix (>=12 chars) of sha256(body).
            hash_ok = bool(output_hash) and len(output_hash) >= 12 and bool(computed_hash) and computed_hash.startswith(output_hash)
            chunk_count = int(meta.get("chunk_count") or 0) or int(span.get("chunk_count") or 0)
            span_ok = isinstance(span, dict) and (chunk_count > 0 or int(span.get("end_seq") or 0) > int(span.get("start_seq") or 0))
            return {
                "type": "candidate",
                "entry": pay,
                "content": content,
                "body": body,
                "metadata": meta,
                "has_strong_proof": hash_ok and span_ok,
                "hash_ok": hash_ok,
                "span_ok": span_ok,
            }
    return None


def check_live_proof_loop() -> ProofResult:
    delegations = load_jsonl_tail(GROK_DELEGATION_LEDGER)
    conversation = load_jsonl_tail(ALICE_CONVERSATION, max_lines=800)

    latest_del = find_latest_grok_delegation(delegations)
    if not latest_del:
        return ProofResult(False, "NO_DELEGATION_FOUND", {"searched": str(GROK_DELEGATION_LEDGER)})

    result = find_grok_result_in_conversation(conversation)
    if not result:
        return ProofResult(
            False,
            "NO_GROK_RESULT_IN_GLOBAL_CHAT",
            {
                "delegation_found": True,
                "message": "Step 1 succeeded (delegation dispatched). Steps 2-5 unproven. No GROK_RESULT posted by Alice in global chat.",
            },
        )

    if result["type"] == "fallback":
        return ProofResult(
            False,
            "ONLY_FALLBACK_MESSAGE",
            {
                "message": "Capture ran but returned the fallback. Real Grok output was not captured or extracted. Steps 3-5 failed.",
                "content_snippet": result["content"][:300],
            },
        )

    if result["type"] == "candidate":
        if result.get("has_strong_proof"):
            return ProofResult(
                True,
                "FULL_PROOF_LOOP_PASSED",
                {
                    "message": "Real captured Grok output found in global chat with evidence of hash / capture_id / transcript span.",
                    "content_snippet": result["content"][:400],
                },
            )
        else:
            return ProofResult(
                False,
                "REAL_ANSWER_BUT_MISSING_RICH_RECEIPT",
                {
                    "message": "Grok answer text is present in global chat, but captured_output_hash does not match and/or PTY transcript span is missing. Step 5 incomplete.",
                    "hash_ok": bool(result.get("hash_ok")),
                    "span_ok": bool(result.get("span_ok")),
                    "content_snippet": result["content"][:400],
                },
            )

    return ProofResult(False, "UNKNOWN_STATE", {})


def run_self_tests() -> List[ProofResult]:
    """REAL self-tests: actually run the checker logic against synthetic ledgers
    and assert it behaves. (The previous version returned hardcoded answers and
    proved nothing — a gate that fakes its own audit is no gate at all.)

    Each ProofResult.passed = whether the checker DID the right thing on that case.
    """
    body = ("Grok inspected the delegation path and proposes the smallest safe "
            "patch: wire _capture_grok_terminal_output into the PTY byte reader.")
    good_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    txt = "Grok result:\n" + body

    def gr(content: str, meta: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [{"payload": {"role": "alice", "action": "GROK_RESULT",
                             "text": content, "metadata": meta}}]

    checks: List[tuple] = []

    # 1. dispatch only: no GROK_RESULT row at all -> checker returns None (would FAIL live)
    r1 = find_grok_result_in_conversation([{"payload": {"role": "user", "text": "ask grok ..."}}])
    checks.append(("dispatch-only → no result row", r1 is None))

    # 2. fallback message -> classified as fallback (FAIL)
    r2 = find_grok_result_in_conversation(gr("Grok result: No readable Grok output captured before the timeout.", {}))
    checks.append(("fallback → FAIL", bool(r2) and r2.get("type") == "fallback"))

    # 3. real text but no hash/span -> candidate, NOT strong (FAIL)
    r3 = find_grok_result_in_conversation(gr(txt, {}))
    checks.append(("real answer, no proof → FAIL", bool(r3) and not r3.get("has_strong_proof")))

    # 4. THE CLOSED HOLE: real text + a bogus 64-char hash that does NOT match -> must FAIL
    r4 = find_grok_result_in_conversation(gr(txt, {"captured_output_hash": "0" * 64,
                                                   "pty_transcript_span": {"chunk_count": 3}}))
    checks.append(("real + bogus 64-char hash → FAIL (hole closed)", bool(r4) and not r4.get("has_strong_proof")))

    # 5. real text + MATCHING hash + real span -> PASS
    r5 = find_grok_result_in_conversation(gr(txt, {"captured_output_hash": good_hash,
                                                   "pty_transcript_span": {"chunk_count": 3}}))
    checks.append(("real + matching hash + span → PASS", bool(r5) and bool(r5.get("has_strong_proof"))))

    return [ProofResult(ok, label, {"actually_executed_checker": True}) for (label, ok) in checks]


def main() -> None:
    print("=== Grok Proof Loop Verifier (strict) ===")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Reading ledgers from: {STATE_DIR}\n")

    print("--- Self-tests (proving the checker is not gullible) ---")
    self_tests = run_self_tests()
    for i, r in enumerate(self_tests, 1):
        status = "PASS" if r.passed else "FAIL"
        print(f"  {i}. {r.diagnosis}  [{status}]")
    print()

    print("--- Live ledger check ---")
    live = check_live_proof_loop()
    status = "PASS" if live.passed else "FAIL"
    print(f"Live result: {live.diagnosis}  [{status}]")
    if live.details:
        print("Details:", json.dumps(live.details, indent=2)[:800])

    print("\n" + "=" * 60)
    if live.passed:
        print("FULL PROOF LOOP VERIFIED ON LIVE DATA.")
    else:
        print("PROOF LOOP NOT CLOSED ON LIVE DATA.")
        print("Dispatch + guardian may be working, but the capture → rich GROK_RESULT in global chat is not proven.")
    print("=" * 60)


if __name__ == "__main__":
    main()
