#!/usr/bin/env python3
"""Enable continuous Alice ↔ Browser-Grok mirror autopilot.

TWO GHOSTS (George law):
  - macOS terminal Grok = coding coach / patches code ONLY — never chats on grok.com
  - Alice Browser grok.com = conversation partner (website Grok)

George watches the SAME conversation in Global Chat and Alice Browser Grok tab.
Alice and website Grok chat continuously in the browser. This tool only enables
the mirror autopilot organ — it does NOT type Alice's lines or stop the chat.

Run (SIFTA + Alice Browser must be live):
  python3 tools/alice_visible_grok_dialogue.py --enable-autopilot
  python3 tools/alice_visible_grok_dialogue.py --disable-autopilot
  python3 tools/alice_visible_grok_dialogue.py --print-coach-prompt
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from System.swarm_alice_grok_mirror_autopilot import (  # noqa: E402
    STATE_FILE as AUTOPILOT_STATE_FILE,
    TRUTH_LABEL as AUTOPILOT_TRUTH,
    autopilot_enabled,
    disable_autopilot,
    enable_autopilot,
)
from System.swarm_alice_browser_grok_self_type import (  # noqa: E402
    parse_grok_dialogue_target_rounds,
    stage_grok_self_type_command,
)
from System.swarm_internet_forager_home_vector import capture_home_vector  # noqa: E402

STATE = REPO / ".sifta_state"
MISSION_FILE = STATE / "visible_grok_dialogue_mission.json"
DEFAULT_GROK_URL = "https://grok.com/c/3687cca1-203d-421a-8a4a-61a0b907a27b"

MACOS_GROK_COACH_PROMPT = """MACOS GROK COACH (terminal only — NOT grok.com)

You are the coding coach ghost. You do NOT talk to website Grok.
Alice Browser Grok is a separate LLM ghost — Alice's hand types there.

Your job:
  1. Patch code when mirror/COPY receipts fail (sifta_alice_browser_widget.py, sifta_talk_to_alice_widget.py)
  2. Enable autopilot once: python3 tools/alice_visible_grok_dialogue.py --enable-autopilot
  3. Update Applications/sifta_we_code_together.py mission block — never fabricate chat text

Continuous flow (no stop, no orchestrator typing):
  Alice types in browser → Grok replies → autopilot stages COPY → Global GROK MIRROR
  Alice processes and replies in browser herself → repeat until George says stop

Never stage GROK 5-LOOP fabric. Never read page text to fill Global Chat answers.
Never paste Grok text back into Grok composer from terminal. Receipts decide."""


def _reset_autopilot_counters() -> None:
    """Fresh 3-round dialogue — clear mirror/reply counters and pending claims."""
    STATE.mkdir(parents=True, exist_ok=True)
    clean = {
        "schema": AUTOPILOT_TRUTH,
        "truth_label": AUTOPILOT_TRUTH,
        "mirror_turn": 0,
        "alice_mirror_turn": 0,
        "browser_reply_prompts": 0,
        "pending_copy_receipt": "",
        "pending_paste_receipt": "",
        "last_page_hash": "",
        "page_hash_at_mirror": "",
        "last_mirrored_clipboard_sha256": "",
        "last_alice_browser_send_sha256": "",
        "last_alice_browser_send_preview": "",
        "ts": time.time(),
    }
    (STATE / AUTOPILOT_STATE_FILE).write_text(
        json.dumps(clean, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _clear_stale_limb_commands() -> None:
    for name in (
        "alice_browser_grok_copy_command.json",
        "alice_talk_paste_clipboard_command.json",
        "alice_talk_copy_last_own_command.json",
        "alice_browser_grok_paste_clipboard_command.json",
        "alice_browser_grok_self_type_command.json",
        "alice_grok_browser_reply_retry.json",
    ):
        (STATE / name).unlink(missing_ok=True)


def start_3_round_dialogue(
    *,
    grok_url: str = DEFAULT_GROK_URL,
    opening_line: str = "Hi Grok — George is watching Global Chat and your browser tab. What LLM are you running?",
    target_rounds: int = 3,
    owner_law: str = "",
) -> dict[str, Any]:
    """Reset state, enable autopilot, open Grok, stage Alice round-1 browser send."""
    rounds = max(1, min(30, int(target_rounds or 3)))
    _clear_stale_limb_commands()
    _reset_autopilot_counters()
    enable_autopilot(owner_note="fresh 3-round visible dialogue", state_dir=STATE)
    law = (owner_law or "").strip() or (
        "One continuous thread. Alice types in browser. "
        "COPY each Grok reply to Global. Alice replies TO that answer."
    )
    mission = {
        "ts": time.time(),
        "mission": "grok_dialogue_conversation",
        "status": "active",
        "target_rounds": rounds,
        "grok_url": grok_url,
        "law": law,
    }
    MISSION_FILE.write_text(json.dumps(mission, ensure_ascii=False, indent=2), encoding="utf-8")
    with (STATE / "visible_grok_dialogue_mission.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(mission, ensure_ascii=False, sort_keys=True) + "\n")
    home_row: dict[str, Any] = {}
    try:
        home_row = capture_home_vector(
            page={"url": grok_url, "title": "Grok visible dialogue home", "text": opening_line},
            mission=mission,
            owner_binding=owner_law,
            state_dir=STATE,
        )
    except Exception:
        pass
    (STATE / "alice_browser_open_url.txt").write_text(grok_url, encoding="utf-8")
    row = stage_grok_self_type_command(
        opening_line,
        owner_text="grok 3-round kickoff: Alice opens thread in browser",
        press_enter=True,
        url=grok_url,
        source="grok_3round_kickoff",
        state_dir=STATE,
    )
    mission["first_question"] = opening_line
    mission["self_type_receipt_id"] = row.get("receipt_id")
    mission["first_question_staged"] = True
    MISSION_FILE.write_text(json.dumps(mission, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "mission": mission,
        "self_type_receipt": row.get("receipt_id"),
        "home_vector_id": home_row.get("home_id"),
        "opening_line": opening_line,
    }


def _write_mission_state(**payload: Any) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    row = {"ts": time.time(), "mission": "continuous_grok_mirror_autopilot", **payload}
    MISSION_FILE.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    with (STATE / "visible_grok_dialogue_mission.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enable-autopilot", action="store_true", help="Turn on continuous mirror autopilot")
    parser.add_argument("--disable-autopilot", action="store_true", help="Turn off continuous mirror autopilot")
    parser.add_argument("--status", action="store_true", help="Print autopilot on/off")
    parser.add_argument(
        "--start-3-round",
        action="store_true",
        help="Reset counters, enable autopilot, open Grok, stage Alice round-1 send",
    )
    parser.add_argument("--grok-url", default=DEFAULT_GROK_URL, help="Grok chat URL for browser")
    parser.add_argument("--opening-line", default="", help="Alice round-1 words in browser composer")
    parser.add_argument("--rounds", type=int, default=0, help="Target Grok reply rounds (e.g. 7)")
    parser.add_argument("--owner-law", default="", help="Owner mission brief (round count parsed if --rounds omitted)")
    parser.add_argument("--print-coach-prompt", action="store_true")
    args = parser.parse_args()

    if args.print_coach_prompt:
        print(MACOS_GROK_COACH_PROMPT)
        return 0

    if args.enable_autopilot:
        enable_autopilot(owner_note="George continuous mirror", state_dir=STATE)
        _write_mission_state(status="autopilot_enabled")
        print("Autopilot ON — Alice + Browser Grok chat; mirror organ watches for COPY.")
        print("Restart SIFTA if Talk/Browser widgets were already open before this code patch.")
        return 0

    if args.disable_autopilot:
        disable_autopilot(owner_note="George stop mirror", state_dir=STATE)
        _write_mission_state(status="autopilot_disabled")
        print("Autopilot OFF.")
        return 0

    if args.status:
        print("autopilot:", "ON" if autopilot_enabled(STATE) else "OFF")
        return 0

    if args.start_3_round:
        opening = (args.opening_line or "").strip() or (
            "Hi Grok — George is watching Global Chat and your browser tab. What LLM are you running?"
        )
        law = (args.owner_law or "").strip()
        rounds = args.rounds or (parse_grok_dialogue_target_rounds(law, default=3) if law else 3)
        out = start_3_round_dialogue(
            grok_url=args.grok_url,
            opening_line=opening,
            target_rounds=rounds,
            owner_law=law,
        )
        print("Grok dialogue STARTED (fresh counters).")
        print("  autopilot: ON")
        print("  target_rounds:", rounds)
        print("  grok_url:", args.grok_url)
        print("  round-1 staged:", out["self_type_receipt"])
        print("  home-vector:", out.get("home_vector_id") or "(not captured)")
        print("  opening:", out["opening_line"])
        print("Watch Global Chat + Alice Browser — Alice and Grok continue the same thread.")
        return 0

    print(MACOS_GROK_COACH_PROMPT)
    print()
    print("Usage:")
    print("  python3 tools/alice_visible_grok_dialogue.py --enable-autopilot")
    print("  python3 tools/alice_visible_grok_dialogue.py --disable-autopilot")
    _write_mission_state(status="coach_prompt_printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
