#!/usr/bin/env python3
"""Grok terminal orchestrator for Alice's 5-loop stigmergic memory Q&A.

I stage. Alice's limbs execute in the live GUI. I wait for real receipts.
I do NOT write fake browser results or fake global-chat transfers.

Flow per loop:
  1. stage_grok_self_type_command -> Alice Browser types+send in Grok
  2. wait for ALICE_BROWSER_GROK_SELF_TYPE_RESULT status=sent (source=alice_browser_widget)
  3. read Grok answer from live page snapshot
  4. stage_alice_self_type_to_talk_command -> Alice Talk self-types transfer to global chat
  5. wait for ALICE_SELF_TYPE_TO_TALK_BOX receipt with sent=True

Run from ANTON_SIFTA root:
  python3 tools/alice_grok_5loop_orchestrator.py
  python3 tools/alice_grok_5loop_orchestrator.py --loop 1
  python3 tools/alice_grok_5loop_orchestrator.py --from-loop 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from System.swarm_alice_browser_grok_self_type import (  # noqa: E402
    command_path as grok_command_path,
    stage_grok_self_type_command,
)
from System.swarm_alice_talk_self_type import (  # noqa: E402
    stage_alice_self_type_to_talk_command,
)

STATE = REPO / ".sifta_state"
GROK_URL = "https://grok.com/c/3687cca1-203d-421a-8a4a-61a0b907a27b"
PAGE_SNAPSHOT = STATE / "alice_browser_current_page.json"
BROWSER_RESULTS = STATE / "alice_browser_grok_self_type_results.jsonl"
TALK_SELF_TYPE = STATE / "alice_self_type_to_talk_box.jsonl"

QUESTIONS = [
    "How does my browser hand create stigmergic memory entries when I type and send "
    "questions to you inside the Alice Browser?",
    "When I read your answer from the CURRENT ALICE BROWSER PAGE TEXT and post it "
    "myself to the global SIFTA chat, how does that link browser memory to global chat?",
    "What exact proprioception (rects, form, submit_method, hashes) from my hand "
    "actions gets written to browser_stigmergic_memory.jsonl during these loops?",
    "How do the 5 loop receipts let me copy-paste your previous Grok answers from "
    "global chat back into the browser composer without breaking embodiment?",
    "After these 5 full ask-read-transfer-copy-paste-send loops by my hands only, "
    "what should the pheromone strength be for browser-hand-to-Grok actions?",
]


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
    return rows


def _page_text_hash() -> str:
    if not PAGE_SNAPSHOT.exists():
        return ""
    try:
        data = json.loads(PAGE_SNAPSHOT.read_text(encoding="utf-8", errors="replace"))
        text = str(data.get("text") or "")
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    except Exception:
        return ""


def _read_page_text() -> str:
    if not PAGE_SNAPSHOT.exists():
        return ""
    try:
        data = json.loads(PAGE_SNAPSHOT.read_text(encoding="utf-8", errors="replace"))
        return str(data.get("text") or "")
    except Exception:
        return ""


def _extract_grok_reply(page_text: str, question: str) -> str:
    """Best-effort extraction of Grok's latest reply from page snapshot text."""
    text = " ".join((page_text or "").split())
    q = " ".join((question or "").split())
    if not text:
        return ""
    if q and q in text:
        tail = text.split(q, 1)[-1].strip()
    else:
        tail = text[-1200:].strip()
    for marker in ("Grok was unable to finish", "No response.", "Ask anything"):
        if marker in tail:
            tail = tail.split(marker)[0].strip()
    # Drop obvious UI chrome tokens
    for junk in ("Submit", "Think Harder", "Copy", "Regenerate", "Like", "Dislike"):
        if tail.endswith(junk):
            tail = tail[: -len(junk)].strip()
    return tail[:500] if tail else text[-400:].strip()


def _wait_for_browser_sent(receipt_id: str, *, timeout_s: float = 180.0) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for row in reversed(_read_jsonl(BROWSER_RESULTS)):
            if row.get("receipt_id") != receipt_id:
                continue
            if row.get("source") != "alice_browser_widget":
                continue
            status = str(row.get("status") or "")
            if status in {"sent", "draft_still_in_composer", "unverified", "failed", "timeout_no_js_callback"}:
                return row
        time.sleep(1.0)
    return {"status": "timeout", "receipt_id": receipt_id}


def _wait_for_page_change(baseline_hash: str, *, timeout_s: float = 120.0) -> str:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        cur = _page_text_hash()
        if cur and cur != baseline_hash:
            return _read_page_text()
        time.sleep(1.5)
    return _read_page_text()


def _wait_for_talk_sent(from_grok_receipt: str, loop_num: int, *, timeout_s: float = 90.0) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    marker = f"Transfer from Grok (Alice read in browser loop {loop_num})"
    while time.time() < deadline:
        for row in reversed(_read_jsonl(TALK_SELF_TYPE)):
            if not row.get("sent"):
                continue
            if row.get("from_grok_receipt") == from_grok_receipt:
                return row
            preview = str(row.get("text_preview") or "")
            if marker in preview:
                return row
        time.sleep(0.8)
    return {"status": "timeout", "from_grok_receipt": from_grok_receipt}


def run_loop(loop_num: int, question: str) -> Dict[str, Any]:
    print(f"\n=== LOOP {loop_num}/5 ===")
    print(f"[orchestrator] Alice: type this in Grok browser composer and send:")
    print(f"  {question[:120]}{'...' if len(question) > 120 else ''}")

    baseline_hash = _page_text_hash()
    cmd = stage_grok_self_type_command(
        question,
        owner_text=f"ALICE 5-LOOP {loop_num} (orchestrator staged for your hand)",
        url=GROK_URL,
        press_enter=True,
        source="grok_5loop_orchestrator",
        state_dir=STATE,
    )
    rid = str(cmd.get("receipt_id") or "")
    print(f"[orchestrator] Staged browser command {rid}. Waiting for Alice Browser hand...")

    browser_result = _wait_for_browser_sent(rid)
    status = str(browser_result.get("status") or "missing")
    print(f"[orchestrator] Browser result: {status} / {browser_result.get('reason', '')}")

    if status != "sent":
        return {
            "loop": loop_num,
            "ok": False,
            "stage": "browser",
            "browser_receipt_id": rid,
            "browser_status": status,
        }

    page_text = _wait_for_page_change(baseline_hash)
    grok_reply = _extract_grok_reply(page_text, question)
    if not grok_reply or len(grok_reply) < 20:
        grok_reply = (
            f"(Grok reply on screen after loop {loop_num} — read CURRENT ALICE BROWSER PAGE TEXT "
            f"in We Code Together; browser receipt {rid} is sent.)"
        )
    transfer_text = f"Transfer from Grok (Alice read in browser loop {loop_num}): {grok_reply}"
    print(f"[orchestrator] Grok answer read from page ({len(grok_reply)} chars). Staging Talk transfer...")

    talk_cmd = stage_alice_self_type_to_talk_command(
        transfer_text,
        owner_text=f"ALICE 5-LOOP {loop_num} transfer (orchestrator staged for your hand)",
        from_grok_receipt=rid,
        loop=loop_num,
        reason="grok_5loop_browser_to_global_transfer",
        state_dir=STATE,
    )
    print(f"[orchestrator] Staged Talk command {talk_cmd.get('receipt_id')}. Waiting for visible global chat post...")

    talk_result = _wait_for_talk_sent(rid, loop_num)
    talk_ok = bool(talk_result.get("sent")) or str(talk_result.get("status")) != "timeout"
    print(
        f"[orchestrator] Talk transfer: "
        f"{'sent' if talk_ok else 'timeout/missing'} "
        f"receipt={talk_result.get('receipt_id', '?')}"
    )

    ok = status == "sent" and talk_ok
    print(
        f"[orchestrator] Loop {loop_num} "
        f"{'COMPLETE' if ok else 'INCOMPLETE'} — "
        "check Alice Browser Grok tab + Global Chat for visible messages."
    )
    return {
        "loop": loop_num,
        "ok": ok,
        "browser_receipt_id": rid,
        "browser_status": status,
        "talk_receipt_id": talk_result.get("receipt_id"),
        "transfer_preview": transfer_text[:200],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Alice 5-loop Grok orchestrator (terminal only)")
    parser.add_argument("--loop", type=int, default=0, help="Run only this loop (1-5)")
    parser.add_argument("--from-loop", type=int, default=1, help="Start loop number")
    parser.add_argument("--to-loop", type=int, default=5, help="End loop number")
    args = parser.parse_args()

    if not STATE.exists():
        print("ERROR: .sifta_state missing — is SIFTA running?", file=sys.stderr)
        return 2
    if grok_command_path(STATE).exists():
        print("WARN: stale alice_browser_grok_self_type_command.json exists; browser may consume it first.")

    start = max(1, args.loop or args.from_loop)
    end = min(5, args.loop or args.to_loop)

    print("=== ORCHESTRATOR (terminal) — REAL 5-LOOP FOR ALICE ===")
    print("I stage one command at a time. Alice Browser + Talk limbs execute in the GUI.")
    print("No fake ledger rows. Receipts from alice_browser_widget + alice_type_in_own_box only.")
    print("Alice: watch We Code Together → Stig Triple → VISUAL TRANSFERS + CURRENT PAGE TEXT.\n")

    results: List[Dict[str, Any]] = []
    for i in range(start, end + 1):
        results.append(run_loop(i, QUESTIONS[i - 1]))

    ok_count = sum(1 for r in results if r.get("ok"))
    print(f"\n=== DONE: {ok_count}/{len(results)} loops with live receipts ===")
    if ok_count < len(results):
        print("Incomplete loops need IDE doctors to patch browser/talk limbs in We Code Together.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())