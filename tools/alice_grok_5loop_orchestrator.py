#!/usr/bin/env python3
"""Legacy Grok terminal orchestrator for Alice's 5-loop stigmergic memory Q&A.

Default behavior now runs the visible five-message Alice Browser Grok dialogue.
Use ``--legacy-5loop`` only when deliberately debugging the old receipt drill.

TERMINAL GROK STAGES ONLY. Alice's limbs execute in the live GUI.
I never read Grok answers from page snapshots. I never fabricate Global Chat posts.

Correct embodiment per loop (orchestrator STOPS after step 4):
  1. Alice types question in Grok browser composer → send
  2. Alice waits for Grok reply on screen
  3. Alice clicks Grok COPY button (small icon under message)
  4. Alice mirrors clipboard into Global Chat (George watches — no brain, no Ioan label)
  Alice continues the Grok browser conversation herself after that. Terminal Grok never pastes into Grok.

Run from ANTON_SIFTA root:
  python3 tools/alice_grok_5loop_orchestrator.py
  python3 tools/alice_grok_5loop_orchestrator.py --loop 1
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

from System.swarm_alice_browser_grok_copy import (  # noqa: E402
    stage_grok_copy_last_reply_command,
)
from System.swarm_alice_browser_grok_self_type import (  # noqa: E402
    command_path as grok_command_path,
    stage_grok_self_type_command,
)
from System.swarm_alice_talk_paste_clipboard import (  # noqa: E402
    stage_talk_paste_clipboard_command,
)

STATE = REPO / ".sifta_state"
GROK_URL = "https://grok.com/c/3687cca1-203d-421a-8a4a-61a0b907a27b"
PAGE_SNAPSHOT = STATE / "alice_browser_current_page.json"
BROWSER_RESULTS = STATE / "alice_browser_grok_self_type_results.jsonl"
BROWSER_COPY_RESULTS = STATE / "alice_browser_grok_copy_results.jsonl"
TALK_PASTE_RESULTS = STATE / "alice_talk_paste_clipboard_results.jsonl"

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


def _wait_for_grok_page_ready(*, timeout_s: float = 90.0) -> bool:
    """Wait until Alice Browser has a live grok.com chat page loaded."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not PAGE_SNAPSHOT.exists():
            time.sleep(1.5)
            continue
        try:
            data = json.loads(PAGE_SNAPSHOT.read_text(encoding="utf-8", errors="replace"))
            url = str(data.get("url") or "")
            text = str(data.get("text") or "")
            if "grok.com/c/" in url and len(text) > 400:
                return True
        except Exception:
            pass
        time.sleep(1.5)
    return False


def _wait_for_page_change(baseline_hash: str, *, timeout_s: float = 120.0) -> bool:
    """Detect Grok finished writing — hash change only, no text extraction."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        cur = _page_text_hash()
        if cur and cur != baseline_hash:
            return True
        time.sleep(1.5)
    return False


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


def _wait_for_grok_copy(receipt_id: str, *, timeout_s: float = 90.0) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for row in reversed(_read_jsonl(BROWSER_COPY_RESULTS)):
            if row.get("receipt_id") != receipt_id:
                continue
            if row.get("source") != "alice_browser_widget":
                continue
            status = str(row.get("status") or "")
            if status in {"copied", "clipboard_empty", "copy_click_failed", "copy_js_failed"}:
                return row
        time.sleep(0.8)
    return {"status": "timeout", "receipt_id": receipt_id}


def _wait_for_talk_paste(receipt_id: str, *, timeout_s: float = 90.0) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for row in reversed(_read_jsonl(TALK_PASTE_RESULTS)):
            if row.get("receipt_id") != receipt_id:
                continue
            if row.get("source") != "talk_to_alice_widget":
                continue
            if row.get("sent") or str(row.get("status")) in {"pasted", "timeout"}:
                return row
        time.sleep(0.8)
    return {"status": "timeout", "receipt_id": receipt_id}


def run_loop(loop_num: int, question: str) -> Dict[str, Any]:
    print(f"\n=== LOOP {loop_num}/5 (embodied — Alice hands only) ===")
    print(f"[orchestrator] Step 1: Alice types this in Grok browser composer:")
    print(f"  {question[:120]}{'...' if len(question) > 120 else ''}")

    if not _wait_for_grok_page_ready():
        print("[orchestrator] WARN: grok.com page not ready — staging anyway")
    baseline_hash = _page_text_hash()
    ask_cmd = stage_grok_self_type_command(
        question,
        owner_text=f"ALICE 5-LOOP {loop_num}: type this question yourself in Grok browser",
        url=GROK_URL,
        press_enter=True,
        source="grok_5loop_orchestrator",
        state_dir=STATE,
    )
    ask_rid = str(ask_cmd.get("receipt_id") or "")
    print(f"[orchestrator] Staged browser type command {ask_rid}. Waiting for Alice hand send...")

    ask_result = _wait_for_browser_sent(ask_rid)
    ask_status = str(ask_result.get("status") or "missing")
    print(f"[orchestrator] Browser ask: {ask_status}")
    if ask_status != "sent":
        if ask_status in {"unverified", "draft_still_in_composer", "timeout_no_js_callback"}:
            print("[orchestrator] Retrying browser ask once after composer warm-up...")
            time.sleep(8)
            retry_cmd = stage_grok_self_type_command(
                question,
                owner_text=f"ALICE 5-LOOP {loop_num} retry",
                url=GROK_URL,
                press_enter=True,
                source="grok_5loop_orchestrator",
                state_dir=STATE,
            )
            ask_rid = str(retry_cmd.get("receipt_id") or ask_rid)
            ask_result = _wait_for_browser_sent(ask_rid)
            ask_status = str(ask_result.get("status") or "missing")
            print(f"[orchestrator] Browser ask retry: {ask_status}")
        if ask_status != "sent":
            return {"loop": loop_num, "ok": False, "stage": "browser_ask", "browser_receipt_id": ask_rid}

    print("[orchestrator] Step 2: Waiting for Grok reply on screen (page hash change)...")
    grok_ready = _wait_for_page_change(baseline_hash, timeout_s=150.0)
    print(f"[orchestrator] Grok reply detected: {grok_ready}")

    print("[orchestrator] Step 3: Alice clicks Grok COPY button under latest message...")
    copy_cmd = stage_grok_copy_last_reply_command(
        owner_text=f"ALICE 5-LOOP {loop_num}: click Grok COPY, read clipboard yourself",
        url=GROK_URL,
        from_grok_receipt=ask_rid,
        loop=loop_num,
        source="grok_5loop_orchestrator",
        state_dir=STATE,
    )
    copy_rid = str(copy_cmd.get("receipt_id") or "")
    copy_result = _wait_for_grok_copy(copy_rid)
    copy_ok = str(copy_result.get("status")) == "copied"
    clip_sha = str(copy_result.get("clipboard_sha256") or "")
    print(
        f"[orchestrator] Grok COPY: {copy_result.get('status')} "
        f"chars={copy_result.get('clipboard_chars', 0)} sha={clip_sha[:12]}"
    )
    if not copy_ok:
        return {"loop": loop_num, "ok": False, "stage": "grok_copy", "copy_receipt_id": copy_rid}

    print("[orchestrator] Step 4: Alice pastes clipboard into Global Chat Talk box and sends...")
    paste_cmd = stage_talk_paste_clipboard_command(
        owner_text=f"ALICE 5-LOOP {loop_num}: paste Grok COPY into Talk, send to yourself",
        from_grok_copy_receipt=copy_rid,
        expected_clipboard_sha256=clip_sha,
        loop=loop_num,
        source="grok_5loop_orchestrator",
        state_dir=STATE,
    )
    paste_rid = str(paste_cmd.get("receipt_id") or "")
    paste_result = _wait_for_talk_paste(paste_rid)
    paste_ok = bool(paste_result.get("sent")) or str(paste_result.get("status")) == "pasted"
    print(f"[orchestrator] Talk paste+send: {'sent' if paste_ok else 'timeout/missing'} receipt={paste_rid}")
    if not paste_ok:
        return {"loop": loop_num, "ok": False, "stage": "talk_mirror", "talk_receipt_id": paste_rid}

    ok = True
    print(
        f"[orchestrator] Loop {loop_num} COMPLETE — "
        "Grok COPY mirrored to Global Chat. Alice continues Grok browser herself; "
        "terminal Grok does not paste into Grok."
    )
    return {
        "loop": loop_num,
        "ok": ok,
        "browser_ask_receipt_id": ask_rid,
        "grok_copy_receipt_id": copy_rid,
        "talk_mirror_receipt_id": paste_rid,
        "clipboard_sha256": clip_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Alice 5-loop orchestrator (stage-only, no cheating)")
    parser.add_argument("--loop", type=int, default=0, help="Run only this loop (1-5)")
    parser.add_argument("--from-loop", type=int, default=1, help="Start loop number")
    parser.add_argument("--to-loop", type=int, default=5, help="End loop number")
    parser.add_argument("--legacy-5loop", action="store_true", help="Run the old five-receipt drill instead of the visible dialogue mission")
    parser.add_argument("--mission-id", default="hello-world-visible", help="Visible dialogue mission id when not using --legacy-5loop")
    args = parser.parse_args()

    if not STATE.exists():
        print("ERROR: .sifta_state missing — is SIFTA running?", file=sys.stderr)
        return 2
    if not args.legacy_5loop:
        print("=== VISIBLE DIALOGUE MODE ===")
        print("macOS Grok is the coding helper. Alice Browser Grok is the website conversation partner.")
        print("Running five visible messages: Alice, Grok, Alice, Grok, Alice.")
        try:
            from tools.alice_visible_grok_dialogue_orchestrator import run_visible_dialogue

            row = run_visible_dialogue(mission_id=str(args.mission_id or "hello-world-visible"))
        except Exception as exc:
            print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(row, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    if grok_command_path(STATE).exists():
        print("WARN: stale browser command file exists; browser may consume it first.")

    start = max(1, args.loop or args.from_loop)
    end = min(5, args.loop or args.to_loop)

    print("=== ORCHESTRATOR (terminal Grok) — STAGE ONLY, ALICE EXECUTES ===")
    print("I never read Grok answers. I never post fabricated GROK 5-LOOP blocks.")
    print("Alice: Grok browser = you ↔ Grok. Global Chat = you paste Grok COPY for George.")
    print("Watch We Code Together → Stig Triple for mission pulses.\n")

    results: List[Dict[str, Any]] = []
    for i in range(start, end + 1):
        results.append(run_loop(i, QUESTIONS[i - 1]))

    ok_count = sum(1 for r in results if r.get("ok"))
    print(f"\n=== DONE: {ok_count}/{len(results)} loops with embodied receipts ===")
    if ok_count < len(results):
        print("Incomplete loops: patch browser/talk limbs in We Code Together until receipts green.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
