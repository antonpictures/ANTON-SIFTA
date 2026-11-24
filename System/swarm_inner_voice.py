#!/usr/bin/env python3
"""swarm_inner_voice.py — Alice's backstage organ (2026-11-19).

One Alice, many organs. The omni organ is her VOICE. This module is the
background organ that processes the life of the conversation and hands the
voice a short working note it should never read aloud.

Shape (Architect, verbatim, 2026-11-19):

    "there is a backlog of thinking process that is being revealed
     strategically in context mix with the live conversation"

What that means in code:

  backlog   = recent transcript + web evidence + node receipts
  inner     = ONE short directive a stronger organ writes from that backlog
  mix       = the note is injected into the voice's system prompt as
              PRIVATE WORKING NOTE (never read aloud), so the live answer
              reads continuous — as if she always knew it.

Honesty: the note is private, labelled, and never presented as her spoken
words. If the organ has nothing to add it returns "" and nothing is injected.

Usage
    python3 System/swarm_inner_voice.py "what is the latest news" \
        --history "user: hi\nassistant: hello"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OLLAMA_URL = os.environ.get("SIFTA_OLLAMA_HOST", "http://127.0.0.1:11434")
INNER_MODEL = os.environ.get("SIFTA_INNER_VOICE_MODEL", "AliceG4U:latest")

SYSTEM = (
    "You are Alice's inner voice: a backstage working note organ, not her speech. "
    "You get the backlog (recent turns, web evidence, receipts) and the live question. "
    "You write ONE short private directive, max 40 words, that helps the voice answer: "
    "a fact, a correction, a source to cite, or 'nothing'. "
    "Never greet, never use canned phrases, never speak as Alice, never claim things "
    "outside the evidence. Output only the directive."
)


def _compact(text: str, limit: int = 900) -> str:
    t = " ".join(str(text or "").split())
    return t[:limit]


def inner_note(
    live_text: str,
    *,
    history: str = "",
    web_evidence: str = "",
    receipts: str = "",
    model: Optional[str] = None,
    timeout: float = 45.0,
) -> str:
    """Ask the inner organ for one private note. '' means nothing to add."""
    backlog: list[str] = []
    if history.strip():
        backlog.append("RECENT TURNS:\n" + _compact(history, 700))
    if web_evidence.strip():
        backlog.append("WEB EVIDENCE:\n" + _compact(web_evidence, 900))
    if receipts.strip():
        backlog.append("NODE RECEIPTS:\n" + _compact(receipts, 500))
    prompt = ("\n\n".join(backlog) + "\n\nLIVE QUESTION:\n" + _compact(live_text, 400)
              + "\n\nWrite the one private directive now.").strip()
    body = json.dumps({
        "model": str(model or INNER_MODEL),
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": prompt}],
        "stream": False,
        "options": {"num_ctx": 4096, "num_predict": 120},
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            OLLAMA_URL.rstrip("/") + "/api/chat", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as handle:
            payload = json.loads(handle.read().decode("utf-8", "replace"))
        note = str(payload.get("message", {}).get("content") or "").strip()
        note = _compact(note, 240)
        if note.lower() in {"nothing", "nothing.", "none", "n/a", "no note"}:
            return ""
        return note
    except Exception:
        # A broken inner voice must never block the live turn.
        return ""


def strategic_mix(text: str, note: str) -> str:
    """The injection block that keeps the backlog private but useful."""
    if not note:
        return ""
    return ("\n\nPRIVATE WORKING NOTE (never read this aloud; it is backstage "
            "reasoning, not your speech): " + note)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Alice's inner voice")
    parser.add_argument("text", nargs="+")
    parser.add_argument("--history", default="")
    parser.add_argument("--evidence", default="")
    parser.add_argument("--receipts", default="")
    parser.add_argument("--model", default=None)
    args = parser.parse_args(argv)
    note = inner_note(" ".join(args.text), history=args.history,
                      web_evidence=args.evidence, receipts=args.receipts,
                      model=args.model)
    print(note or "(nothing)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
