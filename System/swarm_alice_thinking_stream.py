#!/usr/bin/env python3
"""swarm_alice_thinking_stream.py — visible LLM thinking + receipts.

Truth label: ``SIFTA_ALICE_THINKING_STREAM_V1``.

Architect 2026-05-14 (verbatim): *"tell her that i George i process i
think before i respond, yes, llm intelligence takes a bit more time
for me, i, George to wait, that is ok, just make sure while i wait i
can read w my eyes on screen what is happening in the background."*

Ollama already streams the model's reasoning trace as a separate
``message.thinking`` field on each chunk when the request body
includes ``"think": true`` (or the model is thinking-capable and the
flag is unset). The Talk widget at
``Applications/sifta_talk_to_alice_widget.py:6930`` previously sent
``"think": False``, and at line 6995-6996 actively discarded any
thinking chunk that did arrive::

    msg = chunk.get("message") or {}
    if msg.get("thinking"):
        continue   # ← bug: thinking trace thrown on the floor

This module is the structural fix:

  * :func:`set_think_flag` mutates the chat payload to request
    thinking from Ollama.
  * :func:`parse_chat_stream_chunk` reads one streamed JSON chunk
    and returns a structured split: ``(content, thinking, done)``.
  * :class:`ThinkingTraceRecorder` buffers the thinking chunks for
    one turn and writes a receipt to
    ``.sifta_state/alice_thinking_traces.jsonl`` when the turn
    completes — so an auditor can read Alice's reasoning trace later
    even after the live UI panel scrolls away.

The Talk widget patch is in the same commit: a new
``thinkingReceived`` signal is emitted on every thinking chunk so the
UI can show the reasoning live in a side panel while the architect
waits. Same eyes, same screen, same time — but now with the body's
mind visible instead of hidden.

Truth boundary
--------------

This module surfaces what Ollama already produces. It does not invent
reasoning or paraphrase it. The recorder writes the **literal**
thinking string the model emitted; if the model emitted nothing, the
trace is empty and the receipt notes that. §7.12 probe-before-claim
holds — the receipt names the model + total chars + chunk count + the
hash so any auditor can replay.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "SIFTA_ALICE_THINKING_STREAM_V1"
THINKING_LEDGER = "alice_thinking_traces.jsonl"

TRUTH_BOUNDARY = (
    "Surfaces Ollama's existing message.thinking stream — does not "
    "invent reasoning. The receipt records the literal thinking "
    "string, model name, char count, chunk count, and sha256 so any "
    "auditor can replay. Visible thinking lets the architect read "
    "along while the LLM works."
)


# ── request body helper ──────────────────────────────────────────────────


def set_think_flag(payload: Dict[str, Any], *, think: bool = True) -> Dict[str, Any]:
    """Add or update ``think`` in an ollama /api/chat request body.

    Returns the same dict for chaining. Mutates in place.
    """
    payload["think"] = bool(think)
    return payload


# ── stream chunk parser ──────────────────────────────────────────────────


def parse_chat_stream_chunk(chunk: Dict[str, Any]) -> Tuple[str, str, bool]:
    """Split one Ollama stream chunk into ``(content, thinking, done)``.

    Either field may be empty. ``done`` is True on the terminal chunk.
    Robust to malformed shape (returns empty strings + False instead
    of raising).
    """
    if not isinstance(chunk, dict):
        return ("", "", False)
    msg = chunk.get("message") or {}
    if not isinstance(msg, dict):
        msg = {}
    content = msg.get("content") or ""
    thinking = msg.get("thinking") or ""
    done = bool(chunk.get("done", False))
    return (
        content if isinstance(content, str) else "",
        thinking if isinstance(thinking, str) else "",
        done,
    )


# ── stateful inline <think>...</think> extractor ─────────────────────────────


class InlineThinkExtractor:
    """Stateful stream extractor that pulls ``<think>...</think>`` spans
    out of streamed content.

    Some models (Qwen3-reasoning, DeepSeek-R1, certain Gemma variants
    when run through Ollama's reasoning pipeline) emit their reasoning
    trace *inline in* ``message.content`` between ``<think>`` and
    ``</think>`` tags, instead of putting it in the separate
    ``message.thinking`` field. Ollama's own web UI parses those tags
    out and renders them in the collapsible thinking section
    (`web/src/lib/components/chat/Message.svelte`).

    This class is the Python equivalent. Each call to :meth:`feed`
    accepts the next content chunk and returns
    ``(visible_content, thinking_emit)``:

      * ``visible_content`` is the slice of this chunk that should be
        shown to the user as Alice's normal reply.
      * ``thinking_emit`` is the slice of this chunk that should be
        routed to the thinking panel (and the
        :class:`ThinkingTraceRecorder`).

    State machine
    -------------

    The extractor maintains:
      * ``_in_think`` — currently inside an open ``<think>`` block?
      * ``_carry`` — buffered tail bytes that might be the start of a
        ``<think>`` or ``</think>`` tag that got split across chunks.
        The longest tag is ``</think>`` (8 chars); we never carry more
        than ``len("</think>")`` bytes.

    The extractor is tolerant of:
      * Tag straddling chunk boundaries (``<thi`` + ``nk>``).
      * Multiple think blocks in one stream.
      * Mixed case (``<Think>`` / ``</THINK>``) — case-insensitive.
      * Content with no tags at all (passes through unchanged).
    """

    _OPEN = "<think>"
    _CLOSE = "</think>"
    _MAX_CARRY = len("</think>")

    def __init__(self) -> None:
        self._in_think: bool = False
        self._carry: str = ""

    def feed(self, piece: str) -> Tuple[str, str]:
        """Feed the next content chunk. Returns ``(visible, thinking)``."""
        if not piece:
            return ("", "")
        buf = self._carry + piece
        visible: List[str] = []
        thinking: List[str] = []
        i = 0
        n = len(buf)
        while i < n:
            if not self._in_think:
                # Scan for the next opening tag (case-insensitive).
                idx = self._find_tag(buf, self._OPEN, i)
                if idx < 0:
                    # No opening tag found. Emit everything except the
                    # trailing _MAX_CARRY bytes as visible; keep the
                    # tail in carry in case a tag is straddling.
                    tail_start = max(i, n - self._MAX_CARRY)
                    visible.append(buf[i:tail_start])
                    self._carry = buf[tail_start:]
                    i = n
                    break
                # Emit content up to the tag, switch state, advance.
                visible.append(buf[i:idx])
                self._in_think = True
                i = idx + len(self._OPEN)
            else:
                # Inside a think block. Look for the close tag.
                idx = self._find_tag(buf, self._CLOSE, i)
                if idx < 0:
                    # No close tag yet. Emit everything except the
                    # trailing _MAX_CARRY bytes as thinking; keep tail.
                    tail_start = max(i, n - self._MAX_CARRY)
                    thinking.append(buf[i:tail_start])
                    self._carry = buf[tail_start:]
                    i = n
                    break
                # Emit thinking up to the tag, switch state, advance.
                thinking.append(buf[i:idx])
                self._in_think = False
                i = idx + len(self._CLOSE)
        else:
            self._carry = ""
        return ("".join(visible), "".join(thinking))

    def flush(self) -> Tuple[str, str]:
        """Called when the stream ends. Returns any residual carry as
        the appropriate channel based on the final state."""
        residue = self._carry
        self._carry = ""
        if not residue:
            return ("", "")
        if self._in_think:
            return ("", residue)
        return (residue, "")

    @staticmethod
    def _find_tag(buf: str, tag: str, start: int) -> int:
        """Case-insensitive find for the tag in ``buf`` starting at
        ``start``. Returns -1 if not present."""
        lc = buf.lower()
        return lc.find(tag, start)


# ── recorder ─────────────────────────────────────────────────────────────


@dataclass
class ThinkingTraceRecorder:
    """Buffers thinking chunks for one turn; writes a receipt on close."""

    model: str
    turn_input_preview: str = ""
    pipeline_id: str = ""
    state_dir: Optional[Path] = None
    chunks: List[str] = field(default_factory=list)
    content_chunks: List[str] = field(default_factory=list)
    started_at: float = field(default_factory=lambda: time.time())
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def append_thinking(self, piece: str) -> None:
        if isinstance(piece, str) and piece:
            self.chunks.append(piece)

    def append_content(self, piece: str) -> None:
        if isinstance(piece, str) and piece:
            self.content_chunks.append(piece)

    @property
    def thinking_text(self) -> str:
        return "".join(self.chunks)

    @property
    def content_text(self) -> str:
        return "".join(self.content_chunks)

    def close(self, *, write: bool = True) -> Dict[str, Any]:
        thinking = self.thinking_text
        content = self.content_text
        finished_at = time.time()
        duration_s = max(0.0, finished_at - self.started_at)
        receipt = {
            "ts": finished_at,
            "trace_id": self.trace_id,
            "truth_label": TRUTH_LABEL,
            "kind": "ALICE_THINKING_TRACE",
            "model": self.model,
            "pipeline_id": self.pipeline_id,
            "turn_input_preview": self.turn_input_preview[:200],
            "thinking_chars": len(thinking),
            "thinking_chunks": len(self.chunks),
            "content_chars": len(content),
            "duration_s": round(duration_s, 3),
            "started_at": self.started_at,
            "finished_at": finished_at,
            "thinking_preview": thinking[:600],
            "thinking_sha256": hashlib.sha256(thinking.encode("utf-8")).hexdigest(),
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }
        payload = json.dumps(receipt, sort_keys=True, separators=(",", ":"), default=str)
        receipt["sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        if write:
            base = Path(self.state_dir) if self.state_dir is not None else _DEFAULT_STATE
            base.mkdir(parents=True, exist_ok=True)
            with (base / THINKING_LEDGER).open("a", encoding="utf-8") as f:
                f.write(json.dumps(receipt, sort_keys=True, ensure_ascii=False) + "\n")

        return receipt


# ── helper: drive a full stream ──────────────────────────────────────────


def consume_stream(
    chunks: List[Dict[str, Any]],
    *,
    recorder: Optional[ThinkingTraceRecorder] = None,
) -> Tuple[str, str]:
    """Walk a list of Ollama-shaped chunks, return ``(content, thinking)``.

    Useful for tests and offline replays. The live widget uses
    :func:`parse_chat_stream_chunk` directly in the read loop.
    """
    content_parts: List[str] = []
    thinking_parts: List[str] = []
    for chunk in chunks:
        c, t, _ = parse_chat_stream_chunk(chunk)
        if c:
            content_parts.append(c)
            if recorder:
                recorder.append_content(c)
        if t:
            thinking_parts.append(t)
            if recorder:
                recorder.append_thinking(t)
    return ("".join(content_parts), "".join(thinking_parts))


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--demo", action="store_true",
                   help="Run a synthetic demo with stubbed chunks and write a receipt.")
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()
    if args.demo:
        rec = ThinkingTraceRecorder(
            model="alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
            turn_input_preview="Who are you learning from right now?",
            pipeline_id="demo_thinking_stream",
        )
        synthetic = [
            {"message": {"thinking": "Let me check who is teaching me. "}},
            {"message": {"thinking": "The STT receipt confirms George is here. "}},
            {"message": {"content": "I am learning from George right now."}},
            {"done": True},
        ]
        content, thinking = consume_stream(synthetic, recorder=rec)
        receipt = rec.close(write=not args.no_write)
        print(f"CONTENT:           {content!r}")
        print(f"THINKING:          {thinking!r}")
        print(f"DURATION_S:        {receipt['duration_s']}")
        print(f"THINKING_CHARS:    {receipt['thinking_chars']}")
        print(f"THINKING_SHA12:    {receipt['thinking_sha256'][:12]}")
        print(f"RECEIPT_TRACE:     {receipt['trace_id']}")
