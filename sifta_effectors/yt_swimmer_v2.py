#!/usr/bin/env python3
"""YouTube co-watch swimmer v2 — pause → recall → speak → resume.

Extends the live Alice Browser pause-speak-resume loop with hybrid_recall
from the stigmergic memory bus so commentary cites ledger-backed moments.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

_SCHEMA = "YT_COMMENTARY_WITH_RECALL_V1"
_RECEIPT_LEDGER = "yt_commentary_with_recall.jsonl"
_DEFAULT_LABELS = frozenset({"OBSERVED", "ARCHITECT_DOCTRINE", "WORLD", "BELIEF"})


def _state_dir(state_dir: str | Path | None = None) -> Path:
    if state_dir is None:
        repo = Path(__file__).resolve().parents[1]
        return repo / ".sifta_state"
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def write_stgm_receipt(
    kind: str,
    payload: dict[str, Any],
    *,
    state_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Append one receipt row for a YT recall commentary effector."""
    sd = _state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    row = {
        "schema": _SCHEMA,
        "receipt_id": str(uuid.uuid4()),
        "ts": time.time(),
        "kind": str(kind or ""),
        "payload": dict(payload or {}),
        "truth_label": "OBSERVED",
    }
    path = sd / _RECEIPT_LEDGER
    line = json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(path, line)
    except Exception:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    return row


@dataclass
class YtEffectorHooks:
    """Injectable browser + speech hooks for tests and Talk wiring."""

    pause_yt: Callable[[], dict[str, Any]] = field(
        default_factory=lambda: (lambda: {"ok": False, "reason": "no_hook"})
    )
    resume_yt: Callable[[], dict[str, Any]] = field(
        default_factory=lambda: (lambda: {"ok": False, "reason": "no_hook"})
    )
    speak: Callable[[str], None] = field(default_factory=lambda: (lambda _t: None))


def _hybrid_recall_rows(
    query: str,
    *,
    labels: frozenset[str] | set[str] | None = None,
    limit: int = 3,
    state_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    import System.stigmergic_memory_bus as memory_bus

    sd = _state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    ledger = sd / "memory_ledger.jsonl"
    original_dir = memory_bus.LEDGER_DIR
    original_file = memory_bus.LEDGER_FILE
    original_log = memory_bus.STGM_LOG_FILE
    original_audit = memory_bus.MEMORY_EPISTEMOLOGY_AUDIT
    try:
        memory_bus.LEDGER_DIR = sd
        memory_bus.LEDGER_FILE = ledger
        memory_bus.STGM_LOG_FILE = sd / "stgm_memory_rewards.jsonl"
        memory_bus.MEMORY_EPISTEMOLOGY_AUDIT = sd / "memory_epistemology_audit.jsonl"
        bus = memory_bus.StigmergicMemoryBus(architect_id="IOAN_M5")
        ranked = bus.hybrid_recall(query, "youtube_cowatch", top_k=max(1, int(limit)) * 3)
    finally:
        memory_bus.LEDGER_DIR = original_dir
        memory_bus.LEDGER_FILE = original_file
        memory_bus.STGM_LOG_FILE = original_log
        memory_bus.MEMORY_EPISTEMOLOGY_AUDIT = original_audit

    allowed = set(labels or _DEFAULT_LABELS)
    out: list[dict[str, Any]] = []
    for score, trace, breakdown in ranked:
        label = str(getattr(trace, "epistemic_label", "") or "HYPOTHESIS")
        if label not in allowed:
            continue
        out.append(
            {
                "timestamp": float(getattr(trace, "timestamp", 0.0) or 0.0),
                "content": str(getattr(trace, "raw_text", "") or "").strip(),
                "epistemic_label": label,
                "trace_id": str(getattr(trace, "trace_id", "") or ""),
                "score": float(score or 0.0),
                "breakdown": dict(breakdown or {}),
            }
        )
        if len(out) >= max(1, int(limit)):
            break
    return out


def remember_and_comment(
    episode_id: str,
    *,
    hooks: YtEffectorHooks | None = None,
    state_dir: str | Path | None = None,
    labels: frozenset[str] | set[str] | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    """Pause YT, speak one ledger-backed recall line, resume, receipt."""
    hooks = hooks or YtEffectorHooks()
    episode = str(episode_id or "").strip() or "unknown_episode"
    recall = _hybrid_recall_rows(
        f"key moments {episode}",
        labels=labels,
        limit=limit,
        state_dir=state_dir,
    )
    pause_receipt = hooks.pause_yt() or {}
    spoken = ""
    if recall:
        top = recall[0]
        spoken = (
            f"From ledger entry {top.get('timestamp')}: {top.get('content')}. Continuing:"
        )
        hooks.speak(spoken)
    else:
        spoken = f"No OBSERVED/ARCHITECT_DOCTRINE recall for episode {episode}."
        hooks.speak(spoken)
    resume_receipt = hooks.resume_yt() or {}
    receipt = write_stgm_receipt(
        "yt_commentary_with_recall",
        {
            "recall_count": len(recall),
            "episode": episode,
            "spoken_preview": spoken[:240],
            "pause_ok": bool(pause_receipt.get("ok")),
            "resume_ok": bool(resume_receipt.get("ok")),
            "top_trace_id": (recall[0].get("trace_id") if recall else ""),
        },
        state_dir=state_dir,
    )
    return {
        "ok": True,
        "episode": episode,
        "recall": recall,
        "spoken": spoken,
        "pause_receipt": pause_receipt,
        "resume_receipt": resume_receipt,
        "receipt": receipt,
        "truth_label": "OBSERVED" if recall else "DEFAULT_NO_PRIOR",
    }


def parse_owner_effector_command(text: str) -> str | None:
    """Return effector verb for owner one-liners like ``fire yt_recall``."""
    low = " ".join((text or "").strip().lower().split())
    if low in {"fire yt_recall", "fire yt-recall", "yt_recall", "yt recall"}:
        return "fire_yt_recall"
    if low in {"audit cline now", "audit cline", "audit cline containment"}:
        return "audit_cline"
    if low in {"more effectors list", "more effectors", "effectors list"}:
        return "effectors_list"
    if low == "pause":
        return "pause"
    return None


def list_registered_effectors() -> list[dict[str, str]]:
    return [
        {
            "name": "yt_recall",
            "module": "sifta_effectors.yt_swimmer_v2",
            "flow": "pause_yt → hybrid_recall → speak → resume_yt → receipt",
            "ledger": _RECEIPT_LEDGER,
        },
        {
            "name": "cline_containment_audit",
            "module": "System.swarm_cline_containment_audit",
            "flow": "audit --organ=cline --mode=containment",
            "ledger": "cline_containment_audit.jsonl",
        },
    ]


__all__ = [
    "YtEffectorHooks",
    "remember_and_comment",
    "write_stgm_receipt",
    "parse_owner_effector_command",
    "list_registered_effectors",
]