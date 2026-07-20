#!/usr/bin/env python3
"""Visible Alice Browser Grok dialogue mission.

macOS Grok is only a coding/diagnostic ghost. The website Grok inside Alice
Browser is the conversation partner. This orchestrator stages Alice-owned limb
commands and waits for receipts before advancing.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from System.swarm_alice_action_journal import append_action_journal  # noqa: E402
from System.swarm_alice_browser_grok_copy import stage_grok_copy_last_reply_command  # noqa: E402
from System.swarm_alice_browser_grok_paste_clipboard import stage_grok_paste_clipboard_command  # noqa: E402
from System.swarm_alice_talk_copy_last_own import stage_talk_copy_last_own_command  # noqa: E402
from System.swarm_alice_talk_paste_clipboard import stage_talk_paste_clipboard_command  # noqa: E402
from System.swarm_alice_talk_self_type import stage_alice_self_type_to_talk_command  # noqa: E402

STATE = REPO / ".sifta_state"
GROK_URL = "https://grok.com/c/3687cca1-203d-421a-8a4a-61a0b907a27b"

PAGE_SNAPSHOT = STATE / "alice_browser_current_page.json"
TALK_SELF_TYPE_BOX = STATE / "alice_self_type_to_talk_box.jsonl"
TALK_COPY_OWN_RESULTS = STATE / "alice_talk_copy_last_own_results.jsonl"
TALK_PASTE_RESULTS = STATE / "alice_talk_paste_clipboard_results.jsonl"
BROWSER_COPY_RESULTS = STATE / "alice_browser_grok_copy_results.jsonl"
BROWSER_PASTE_RESULTS = STATE / "alice_browser_grok_paste_clipboard_results.jsonl"
DIALOGUE_RESULTS = STATE / "alice_visible_grok_dialogue_results.jsonl"
WCT_PULSE = STATE / "we_code_together_monitor_pulse.jsonl"

ALICE_VISIBLE_LINES = [
    {
        "turn": 1,
        "text": "Hello World. I'm Alice",
        "kind": "start",
    },
    {
        "turn": 3,
        "text": "I can see your answer in Alice Browser and in Global Chat. Please reply once more in one short sentence.",
        "kind": "followup",
    },
    {
        "turn": 5,
        "text": "I received your second answer. No reply needed; this completes the visible five-message test.",
        "kind": "final",
    },
]

MACOS_GROK_PROMPT = """You are Grok in macOS terminal, a coding/diagnostic helper for SIFTA.

Do not roleplay Alice. Do not answer as the website Grok in Alice Browser.
There are two separate LLM ghosts:
1. macOS Grok terminal: you advise/code/repair only.
2. Alice Browser Grok tab: the live conversation partner Alice talks to on grok.com.

Goal: make Alice visibly run one mirrored conversation in two panels: Global Chat and Alice Browser Grok.
The five visible messages are:
1. Alice: Hello World. I'm Alice
2. Alice Browser Grok: real reply copied from the browser COPY button
3. Alice: I can see your answer in Alice Browser and in Global Chat. Please reply once more in one short sentence.
4. Alice Browser Grok: real second reply copied from the browser COPY button
5. Alice: I received your second answer. No reply needed; this completes the visible five-message test.

Rules:
- Alice must post her own Alice lines into Global Chat first.
- Alice must copy her own Global Chat post, paste it into Alice Browser Grok, and send.
- Alice must wait for the browser page after her last line to become stable before clicking Grok COPY.
- Alice must paste each copied Grok reply into Global Chat.
- Every executed limb action must have a receipt and a journal_ref.
- Stop after message 5. Do not paste another Grok answer back.

Code target:
Run or repair: python3 tools/alice_visible_grok_dialogue_orchestrator.py --mission-id hello-world-visible
Receipts to inspect: alice_visible_grok_dialogue_results.jsonl, alice_self_type_to_talk_box.jsonl,
alice_browser_grok_paste_clipboard_results.jsonl, alice_browser_grok_copy_results.jsonl,
alice_talk_paste_clipboard_results.jsonl, alice_first_person_journal.jsonl.
"""


def _state_dir_path(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _read_jsonl_tail(path: Path, limit: int = 300) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: deque[Dict[str, Any]] = deque(maxlen=limit)
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    continue
    except Exception:
        return []
    return list(rows)


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _page_snapshot() -> Dict[str, Any]:
    try:
        return json.loads(PAGE_SNAPSHOT.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _page_text_hash() -> str:
    snap = _page_snapshot()
    text = str(snap.get("text") or "")
    if not text:
        return ""
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _page_text() -> str:
    return str(_page_snapshot().get("text") or "")


def _wait_for_row(
    path: Path,
    receipt_id: str,
    *,
    statuses: Iterable[str] = (),
    timeout_s: float = 90.0,
    match_key: str = "receipt_id",
) -> Dict[str, Any]:
    allowed = {str(s) for s in statuses if str(s)}
    deadline = time.time() + timeout_s
    best: Dict[str, Any] = {}
    while time.time() < deadline:
        for row in reversed(_read_jsonl_tail(path)):
            if str(row.get(match_key) or "") != receipt_id:
                continue
            best = row
            status = str(row.get("status") or ("sent" if row.get("sent") else ""))
            if not allowed or status in allowed:
                return row
        time.sleep(0.8)
    return {"receipt_id": receipt_id, "status": "timeout", "best": best}


def _wait_for_talk_self_type(command_receipt_id: str, *, timeout_s: float = 90.0) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    best: Dict[str, Any] = {}
    while time.time() < deadline:
        for row in reversed(_read_jsonl_tail(TALK_SELF_TYPE_BOX)):
            if str(row.get("command_receipt_id") or "") != command_receipt_id:
                continue
            best = row
            if row.get("sent"):
                return row
        time.sleep(0.8)
    return {"receipt_id": command_receipt_id, "status": "timeout", "best": best}


def _wait_for_browser_paste(receipt_id: str, *, timeout_s: float = 150.0) -> Dict[str, Any]:
    return _wait_for_row(
        BROWSER_PASTE_RESULTS,
        receipt_id,
        statuses=("sent", "draft_still_in_composer", "unverified", "failed", "timeout_no_js_callback"),
        timeout_s=timeout_s,
    )


def _wait_for_reply_after_marker(
    marker: str,
    *,
    stable_s: float = 5.0,
    timeout_s: float = 180.0,
    min_after_chars: int = 40,
) -> Dict[str, Any]:
    """Wait until text after the last Alice marker grows and stops changing."""
    deadline = time.time() + timeout_s
    last_hash = ""
    last_change = time.time()
    best_after = ""
    while time.time() < deadline:
        text = _page_text()
        pos = text.rfind(marker)
        after = text[pos + len(marker):] if pos >= 0 else ""
        cur_hash = _page_text_hash()
        if cur_hash and cur_hash != last_hash:
            last_hash = cur_hash
            last_change = time.time()
            best_after = after
        enough_reply = pos >= 0 and len(after.strip()) >= min_after_chars
        stable = cur_hash and (time.time() - last_change) >= stable_s
        if enough_reply and stable:
            return {
                "ok": True,
                "status": "stable_reply_seen",
                "page_hash": cur_hash,
                "after_chars": len(after.strip()),
                "after_preview": after.strip()[:240],
            }
        time.sleep(1.0)
    return {
        "ok": False,
        "status": "timeout_waiting_for_stable_reply",
        "page_hash": last_hash,
        "after_chars": len(best_after.strip()),
        "after_preview": best_after.strip()[:240],
    }


def _mission_row(mission_id: str, event: str, **extra: Any) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "ts": time.time(),
        "schema": "ALICE_VISIBLE_GROK_DIALOGUE_EVENT_V1",
        "truth_label": "ALICE_VISIBLE_GROK_DIALOGUE_EVENT_V1",
        "receipt_id": f"visible-grok-dialogue-{uuid.uuid4().hex[:12]}",
        "mission_id": mission_id,
        "event": event,
        "action": event,
        "source": "alice_visible_grok_dialogue_orchestrator",
    }
    row.update(extra)
    journal = append_action_journal(row, state_dir=STATE)
    row["journal_ref"] = journal.get("journal_id") or journal.get("linked_receipt_id")
    _append_jsonl(DIALOGUE_RESULTS, row)
    _append_jsonl(WCT_PULSE, row)
    return row


def _require_sent(row: Dict[str, Any], *, stage: str) -> None:
    status = str(row.get("status") or ("sent" if row.get("sent") else ""))
    if status != "sent" and not (stage.startswith("talk_") and row.get("sent")):
        raise RuntimeError(f"{stage} did not go green: status={status} receipt={row.get('receipt_id')}")


def _alice_line_to_both(
    text: str,
    *,
    mission_id: str,
    turn: int,
    final: bool = False,
) -> Dict[str, Any]:
    _mission_row(mission_id, "alice_line_start", turn=turn, text_preview=text[:240])
    talk_cmd = stage_alice_self_type_to_talk_command(
        text,
        owner_text=f"VISIBLE DIALOGUE turn {turn}: Alice posts own line to Global Chat",
        reason="visible_grok_dialogue_alice_line",
        source="visible_grok_dialogue_orchestrator",
        loop=turn,
        state_dir=STATE,
    )
    talk_row = _wait_for_talk_self_type(str(talk_cmd.get("receipt_id") or ""))
    if not talk_row.get("sent"):
        raise RuntimeError(f"talk self-type timeout for turn {turn}: {talk_row}")

    copy_cmd = stage_talk_copy_last_own_command(
        owner_text=f"VISIBLE DIALOGUE turn {turn}: copy Alice's own Global Chat line",
        from_talk_paste_receipt=str(talk_row.get("receipt_id") or ""),
        source="visible_grok_dialogue_orchestrator",
        loop=turn,
        state_dir=STATE,
    )
    copy_row = _wait_for_row(
        TALK_COPY_OWN_RESULTS,
        str(copy_cmd.get("receipt_id") or ""),
        statuses=("copied", "no_last_own_message"),
    )
    if str(copy_row.get("status") or "") != "copied":
        raise RuntimeError(f"talk copy-own failed for turn {turn}: {copy_row}")

    paste_cmd = stage_grok_paste_clipboard_command(
        owner_text=f"VISIBLE DIALOGUE turn {turn}: paste Alice line into Alice Browser Grok",
        press_enter=True,
        url=GROK_URL,
        source="visible_grok_dialogue_orchestrator",
        from_talk_paste_receipt=str(talk_row.get("receipt_id") or ""),
        loop=turn,
        state_dir=STATE,
    )
    paste_row = _wait_for_browser_paste(str(paste_cmd.get("receipt_id") or ""))
    _require_sent(paste_row, stage="browser_paste")
    return _mission_row(
        mission_id,
        "alice_line_visible_in_both",
        turn=turn,
        final=final,
        talk_receipt_id=str(talk_row.get("receipt_id") or ""),
        talk_copy_receipt_id=str(copy_row.get("receipt_id") or ""),
        browser_paste_receipt_id=str(paste_row.get("receipt_id") or ""),
        text_preview=text[:240],
    )


def _copy_grok_reply_to_global(
    *,
    mission_id: str,
    after_alice_text: str,
    grok_turn: int,
    from_alice_event: Dict[str, Any],
) -> Dict[str, Any]:
    wait_row = _wait_for_reply_after_marker(after_alice_text)
    if not wait_row.get("ok"):
        _mission_row(mission_id, "waiting_for_grok_reply_timeout", grok_turn=grok_turn, wait=wait_row)
        raise RuntimeError(f"Grok reply did not stabilize after Alice turn before message {grok_turn}: {wait_row}")

    copy_row: Dict[str, Any] = {"status": "not_attempted"}
    for rank_offset in range(0, 6):
        copy_cmd = stage_grok_copy_last_reply_command(
            owner_text=f"VISIBLE DIALOGUE message {grok_turn}: Alice clicks Grok COPY after stable reply",
            url=GROK_URL,
            from_grok_receipt=str(from_alice_event.get("browser_paste_receipt_id") or ""),
            loop=grok_turn,
            source="visible_grok_dialogue_orchestrator",
            copy_rank_offset=rank_offset,
            state_dir=STATE,
        )
        copy_row = _wait_for_row(
            BROWSER_COPY_RESULTS,
            str(copy_cmd.get("receipt_id") or ""),
            statuses=("copied", "clipboard_empty", "wrong_clipboard_target", "copy_click_failed", "copy_js_failed"),
            timeout_s=120.0,
        )
        if str(copy_row.get("status") or "") == "copied":
            break
    if str(copy_row.get("status") or "") != "copied":
        raise RuntimeError(f"Grok copy failed for message {grok_turn}: {copy_row}")

    paste_cmd = stage_talk_paste_clipboard_command(
        owner_text=f"VISIBLE DIALOGUE message {grok_turn}: paste real Grok reply into Global Chat",
        reason="visible_grok_dialogue_grok_reply_to_global_chat",
        from_grok_copy_receipt=str(copy_row.get("receipt_id") or ""),
        expected_clipboard_sha256=str(copy_row.get("clipboard_sha256") or ""),
        loop=grok_turn,
        source="visible_grok_dialogue_orchestrator",
        state_dir=STATE,
    )
    paste_row = _wait_for_row(
        TALK_PASTE_RESULTS,
        str(paste_cmd.get("receipt_id") or ""),
        statuses=("pasted", "timeout"),
        timeout_s=120.0,
    )
    if not (paste_row.get("sent") or str(paste_row.get("status") or "") == "pasted"):
        raise RuntimeError(f"Talk paste of Grok reply failed for message {grok_turn}: {paste_row}")
    return _mission_row(
        mission_id,
        "grok_reply_visible_in_global",
        turn=grok_turn,
        wait=wait_row,
        grok_copy_receipt_id=str(copy_row.get("receipt_id") or ""),
        talk_paste_receipt_id=str(paste_row.get("receipt_id") or ""),
        clipboard_sha256=str(copy_row.get("clipboard_sha256") or ""),
        clipboard_preview=str(copy_row.get("clipboard_preview") or "")[:240],
    )


def run_visible_dialogue(*, mission_id: str) -> Dict[str, Any]:
    _mission_row(
        mission_id,
        "mission_start",
        expected_sequence=[
            "Alice",
            "Alice Browser Grok",
            "Alice",
            "Alice Browser Grok",
            "Alice",
        ],
    )
    first = _alice_line_to_both(ALICE_VISIBLE_LINES[0]["text"], mission_id=mission_id, turn=1)
    _copy_grok_reply_to_global(
        mission_id=mission_id,
        after_alice_text=ALICE_VISIBLE_LINES[0]["text"],
        grok_turn=2,
        from_alice_event=first,
    )
    third = _alice_line_to_both(ALICE_VISIBLE_LINES[1]["text"], mission_id=mission_id, turn=3)
    _copy_grok_reply_to_global(
        mission_id=mission_id,
        after_alice_text=ALICE_VISIBLE_LINES[1]["text"],
        grok_turn=4,
        from_alice_event=third,
    )
    fifth = _alice_line_to_both(
        ALICE_VISIBLE_LINES[2]["text"],
        mission_id=mission_id,
        turn=5,
        final=True,
    )
    return _mission_row(
        mission_id,
        "mission_complete_after_five_messages",
        ok=True,
        final_turn=5,
        final_browser_paste_receipt_id=str(fifth.get("browser_paste_receipt_id") or ""),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the visible five-message Alice/Brower-Grok dialogue.")
    parser.add_argument("--mission-id", default="hello-world-visible", help="Stable id for this visible run")
    parser.add_argument("--print-macos-grok-prompt", action="store_true", help="Print the prompt for Grok in macOS terminal")
    parser.add_argument("--dry-run", action="store_true", help="Print the five-message plan without staging commands")
    args = parser.parse_args()

    if args.print_macos_grok_prompt:
        print(MACOS_GROK_PROMPT)
        return 0
    if args.dry_run:
        print("Visible dialogue plan:")
        for row in ALICE_VISIBLE_LINES:
            print(f"  Alice turn {row['turn']}: {row['text']}")
        print("  Grok turns 2 and 4 are copied from Alice Browser Grok after stable page text.")
        return 0
    if not STATE.exists():
        print("ERROR: .sifta_state missing; start SIFTA first.", file=sys.stderr)
        return 2
    try:
        row = run_visible_dialogue(mission_id=str(args.mission_id or "hello-world-visible"))
    except Exception as exc:
        _mission_row(
            str(args.mission_id or "hello-world-visible"),
            "mission_failed",
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(row, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
