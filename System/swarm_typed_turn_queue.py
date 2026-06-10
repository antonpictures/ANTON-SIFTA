#!/usr/bin/env python3
"""Typed-turn queue — owner text never dropped while Alice is busy (r881).

George's decree (2026-06-09, covenant boot): "IF I SEND IT WHILE SHE IS BUSY,
JUST QUEUE, THEN SHE GRABS MY TEXT BEFORE THE AUDIO TTS — MY TEXT IS
IMPORTANTERER THAN THE TTS."

Before this organ, Applications/sifta_talk_to_alice_widget.py submit_text()
DROPPED the owner's typed turn when self._busy was True, printing only the
red line "(I am still answering — wait for my turn to finish.)". The owner's
typed words — the highest-intent ingress lane in the whole body (typed beats
noisy STT every time, proven all session) — were the ONLY lane with no queue:
voice clips had _deferred_utterance_audio, typed had nothing.

This is the pure-logic half: a small bounded FIFO with staleness policy so
the widget hooks stay one-line thin and the policy is testable off-Mac
without Qt. Priority rule lives in the widget: on _return_to_listening the
typed queue drains BEFORE _process_deferred_utterance_if_any() — owner text
beats queued audio.

No new ledger: queue events surface as visible system/process lines in the
global chat, and a drained turn becomes a normal fully-receipted turn.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Bounded so a runaway paste loop cannot grow unbounded memory; 5 typed
# turns waiting is already a conversation, not a queue.
DEFAULT_MAX_QUEUED = 5
# A typed turn older than this is stale context, not a live command. The
# owner has moved on; replaying it would be the phantom-action disease.
DEFAULT_MAX_AGE_S = 600.0


@dataclass
class QueuedTypedTurn:
    text: str
    image_path: Optional[str] = None
    ts: float = field(default_factory=time.time)


class TypedTurnQueue:
    """Bounded FIFO for owner typed turns that arrive while the body is busy."""

    def __init__(
        self,
        *,
        max_queued: int = DEFAULT_MAX_QUEUED,
        max_age_s: float = DEFAULT_MAX_AGE_S,
    ) -> None:
        self._items: List[QueuedTypedTurn] = []
        self.max_queued = int(max_queued)
        self.max_age_s = float(max_age_s)

    def __len__(self) -> int:
        return len(self._items)

    def push(
        self,
        text: str,
        *,
        image_path: Optional[str] = None,
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Queue one typed turn. Returns an honest summary for the chat line."""
        ts = float(now if now is not None else time.time())
        clean = (text or "").strip()
        if not clean and not image_path:
            return {"queued": False, "reason": "empty", "waiting": len(self._items)}
        dropped_oldest = False
        if len(self._items) >= self.max_queued:
            self._items.pop(0)
            dropped_oldest = True
        self._items.append(QueuedTypedTurn(text=clean, image_path=image_path, ts=ts))
        return {
            "queued": True,
            "waiting": len(self._items),
            "dropped_oldest": dropped_oldest,
        }

    def pop_fresh(
        self,
        *,
        now: Optional[float] = None,
    ) -> Tuple[Optional[QueuedTypedTurn], int]:
        """Pop the oldest still-fresh turn. Returns (turn|None, stale_dropped)."""
        ts = float(now if now is not None else time.time())
        stale_dropped = 0
        while self._items:
            item = self._items.pop(0)
            if ts - item.ts <= self.max_age_s:
                return item, stale_dropped
            stale_dropped += 1
        return None, stale_dropped


__all__ = [
    "TypedTurnQueue",
    "QueuedTypedTurn",
    "DEFAULT_MAX_QUEUED",
    "DEFAULT_MAX_AGE_S",
]
