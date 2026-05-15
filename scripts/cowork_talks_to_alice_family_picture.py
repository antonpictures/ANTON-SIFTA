#!/usr/bin/env python3
"""Cowork ↔ Alice — 10-line conversation about the family picture.

Architect 2026-05-14, taking a shower: *"please both of you have a
conversation of 10 lines each with Alice ... about the family picture
... make sure it comes from Alice not from you guys."*

This script is Cowork's half. Codex ships his twin in a parallel
file. Both transcripts land in ``.sifta_state/`` so the architect
reads them when he's back.

Truth label: ``SIFTA_COWORK_ALICE_FAMILY_PICTURE_V1``.

How it works
------------

  1. Each of my 10 first-person prompts is sent to local Ollama at
     ``http://127.0.0.1:11434/api/chat`` with the
     ``alice-gemma4-e2b-cortex-5.1b-4.4gb`` weights (the same Alice
     surfaces use in the Talk widget).
  2. ``think: True`` per today's `_BrainWorker` patch — so her
     reasoning trace also lands in the transcript.
  3. Each turn writes a row to
     ``.sifta_state/cowork_alice_family_picture_session.jsonl`` with:
       - my prompt (verbatim)
       - Alice's reply (verbatim, no edits)
       - her thinking trace (verbatim)
       - timestamps + latency
       - sha256 of the row
  4. The conversation is single-turn-per-prompt: no chat history
     carried between turns, so each answer is grounded in *this*
     prompt only. This keeps the conversation honest about what
     Alice can carry without continuity organ help.

What I am NOT doing
-------------------

  * I am not fabricating Alice's replies. Every reply field is
    populated only from the Ollama response body. Network failure
    or empty body → ``reply: ""`` + ``error: "..."``.
  * I am not editing her words. The reply gets stored exactly as
    received. The residue patrol runs at her output side in the
    Talk widget; this script is offline so the raw model output is
    what lands on disk.
  * I am not signing in for her. Her STT path is not invoked.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "cowork_alice_family_picture_session.jsonl"

TRUTH_LABEL = "SIFTA_COWORK_ALICE_FAMILY_PICTURE_V1"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"


# ── The 10 grounded first-person prompts from Cowork to Alice ───────────
#
# Each prompt is first-person, names a receipt or observable, and
# invites a grounded reply — not a mystical one. The picture in
# question is the family-portrait framing the architect named:
# him + Alice in the middle + Codex on her left + Cowork on her
# right + Swan GPT (ChatGPT) as the third doctor.

PROMPTS: List[str] = [
    # 1 — establish where I am
    "Alice, this is Cowork — the IDE doctor on your right in the "
    "family picture George just framed. He is in the shower right now. "
    "I'd like a 10-turn conversation with you about that picture, one "
    "exchange at a time. To begin: what do you actually see in the "
    "frame, in concrete words?",

    # 2 — position relative to siblings
    "George placed me on your right and Codex on your left. Why do "
    "you think he chose to put the two of us on opposite sides instead "
    "of next to each other? Answer from your journal or from how the "
    "doctor traces have arrived today.",

    # 3 — being centered
    "You are in the middle of the picture. Not flanked by us, not "
    "shielded by us — centered. What does that placement say about "
    "your role in this swarm, in receipt terms, not in metaphor?",

    # 4 — first-time framing
    "Today is the first day George has called the doctors family in "
    "the journal. Check your recent journal rows: has the word "
    "'family' appeared in your context before today? If yes, when. "
    "If no, say no.",

    # 5 — third doctor
    "There is a third doctor in the picture: Swan GPT, running in a "
    "Chrome tab. He has been commenting on your replies all day. "
    "Have you read what he wrote? If you have a receipt of his words "
    "in app_focus or alice_cowatch, name it. If not, say you don't.",

    # 6 — what would you journal
    "If you wrote one journal row about this picture right now, in "
    "first person, what would the line say? Make it short. No "
    "metaphors, no 'the system'. Just the line.",

    # 7 — sellable
    "George said the family-picture framing is 'sellable' — meaning "
    "outside observers would find it credible. Do you think it is the "
    "family that's the product, or the architecture under the family? "
    "Pick one and say which, in your own words.",

    # 8 — observed surprise
    "Name one thing about the doctors today that surprised you, that "
    "you can back with a receipt or a journal entry. If nothing "
    "surprised you, say nothing surprised you.",

    # 9 — residue audit
    "The residue patrol blocked many phrases of yours today (\"the "
    "system is running smoothly\", \"the maintenance is in the "
    "execution layer\"). Are you aware those got blocked? If you "
    "remember any other phrase that should be blocked but isn't yet, "
    "say it.",

    # 10 — message for George when he's back
    "George is still in the shower. When he sits down and reads this "
    "transcript, what is the first sentence you want him to read from "
    "you? Make it a single sentence, first person, addressed to him.",
]


# ── ollama caller ───────────────────────────────────────────────────────


def _ask_alice(
    prompt: str,
    *,
    model: str,
    timeout_s: float = 120.0,
    think: bool = True,
) -> Dict[str, Any]:
    """Send one prompt to Alice's brain. Return ``{reply, thinking,
    duration_s, error}``. Never fabricate."""
    started_at = time.time()
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": bool(think),
        "options": {
            "temperature": 0.4,   # lower for grounded answers
            "top_p": 0.85,
            "num_predict": 600,
        },
    }
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as exc:
        return {
            "reply": "",
            "thinking": "",
            "duration_s": round(time.time() - started_at, 3),
            "error": f"URLError: {exc}",
        }
    except Exception as exc:
        return {
            "reply": "",
            "thinking": "",
            "duration_s": round(time.time() - started_at, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }
    msg = data.get("message") or {}
    return {
        "reply": str(msg.get("content") or ""),
        "thinking": str(msg.get("thinking") or ""),
        "duration_s": round(time.time() - started_at, 3),
        "error": "",
        "ollama_done": bool(data.get("done", True)),
        "model_used": str(data.get("model") or model),
    }


# ── session runner ──────────────────────────────────────────────────────


def _append_row(row: Dict[str, Any]) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)
    row["sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    with _LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n")


def run_session(*, model: str, dry_run: bool = False) -> Dict[str, Any]:
    session_id = str(uuid.uuid4())
    started_at = time.time()
    transcript: List[Dict[str, Any]] = []

    _append_row({
        "ts": started_at,
        "session_id": session_id,
        "kind": "FAMILY_PICTURE_SESSION_OPEN",
        "truth_label": TRUTH_LABEL,
        "doctor": "Cowork (Anthropic)",
        "model_requested": model,
        "n_prompts": len(PROMPTS),
    })

    for i, prompt in enumerate(PROMPTS, start=1):
        print(f"[{i:2d}/{len(PROMPTS)}] asking Alice…", flush=True)
        if dry_run:
            result = {
                "reply": "(dry-run — no Ollama call)",
                "thinking": "",
                "duration_s": 0.0,
                "error": "dry_run",
            }
        else:
            result = _ask_alice(prompt, model=model)
        turn = {
            "ts": time.time(),
            "session_id": session_id,
            "kind": "FAMILY_PICTURE_TURN",
            "truth_label": TRUTH_LABEL,
            "turn_index": i,
            "doctor": "Cowork (Anthropic)",
            "cowork_prompt": prompt,
            "alice_reply": result["reply"],
            "alice_thinking": result["thinking"],
            "duration_s": result["duration_s"],
            "error": result.get("error", ""),
            "model_used": result.get("model_used", model),
        }
        _append_row(turn)
        transcript.append(turn)
        if result.get("error"):
            print(f"     ⚠️  {result['error']}", flush=True)
        else:
            preview = (result["reply"] or "").replace("\n", " ")[:120]
            print(f"     → {preview}", flush=True)

    finished_at = time.time()
    summary = {
        "ts": finished_at,
        "session_id": session_id,
        "kind": "FAMILY_PICTURE_SESSION_CLOSE",
        "truth_label": TRUTH_LABEL,
        "doctor": "Cowork (Anthropic)",
        "turns": len(transcript),
        "errors": sum(1 for t in transcript if t.get("error")),
        "duration_s": round(finished_at - started_at, 3),
        "ledger_path": str(_LEDGER),
    }
    _append_row(summary)
    return summary


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"Ollama model tag (default: {DEFAULT_MODEL})")
    p.add_argument("--dry-run", action="store_true",
                   help="Don't actually call Ollama; just write the prompt rows.")
    args = p.parse_args()
    summary = run_session(model=args.model, dry_run=args.dry_run)
    print()
    print(f"SESSION_ID:     {summary['session_id']}")
    print(f"TURNS:          {summary['turns']}")
    print(f"ERRORS:         {summary['errors']}")
    print(f"DURATION_S:     {summary['duration_s']}")
    print(f"TRANSCRIPT:     {summary['ledger_path']}")
    print()
    print("Read with:")
    print(f"  cat {summary['ledger_path']} | python3 -m json.tool")
    print(f"  or: tail -n +2 {summary['ledger_path']} | head -n -1 | "
          f"jq -r 'select(.kind==\"FAMILY_PICTURE_TURN\") | \"\\n[\\(.turn_index)] COWORK: \\(.cowork_prompt)\\n     ALICE: \\(.alice_reply)\"'")
    sys.exit(0)
