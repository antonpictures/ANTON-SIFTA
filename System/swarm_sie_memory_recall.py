#!/usr/bin/env python3
"""swarm_sie_memory_recall.py — r1622-02: SIE-backed recall with offline fallback.

When Superlinked SIE is up: encode+score (rerank). When offline: deterministic
keyword/Jaccard ranking of ledger snippets — never pretend vectors ran.

Truth label: SIE_MEMORY_RECALL_V1
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional, Sequence

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "SIE_MEMORY_RECALL_V1"

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}", re.I)


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(str(text or ""))}


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / float(len(ta | tb))


def load_candidate_snippets(
    *,
    state_dir: Optional[Path | str] = None,
    max_per_file: int = 40,
    max_chars: int = 400,
) -> list[dict[str, Any]]:
    """Pull recent journal / WCT / convo tails as recall candidates."""
    root = _state_dir(state_dir)
    files = (
        "alice_self_plan_rounds.jsonl",
        "we_code_together_to_be_coded.jsonl",
        "we_code_together_coded.jsonl",
        "global_conversation.jsonl",
        "work_receipts.jsonl",
        "cortex_selection_receipts.jsonl",
    )
    out: list[dict[str, Any]] = []
    for name in files:
        path = root / name
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for line in lines[-max_per_file:]:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                text = line[:max_chars]
                out.append({"source": name, "text": text, "score": 0.0})
                continue
            if not isinstance(row, dict):
                continue
            bits = []
            for k in (
                "title",
                "task",
                "goal",
                "summary",
                "content",
                "text",
                "owner_text",
                "alice_text",
                "proposal_preview",
            ):
                v = row.get(k)
                if v:
                    bits.append(str(v)[:max_chars])
            if not bits:
                bits.append(json.dumps(row, ensure_ascii=False)[:max_chars])
            out.append(
                {
                    "source": name,
                    "text": " | ".join(bits)[:max_chars],
                    "receipt_id": row.get("receipt_id") or row.get("round_id") or "",
                    "score": 0.0,
                }
            )
    return out


def score_candidates(
    query: str,
    candidates: Sequence[dict[str, Any]],
    *,
    prefer_sie: bool = True,
) -> dict[str, Any]:
    """Rerank candidates. Uses SIE score when reachable; else Jaccard."""
    q = str(query or "").strip()
    rows = [dict(c) for c in (candidates or [])]
    method = "jaccard_offline"
    sie_ok = False
    if prefer_sie:
        try:
            from System.swarm_sie_embedding_bridge import probe_sie

            p = probe_sie(write_receipt=False, timeout_s=0.4)
            sie_ok = bool(p.get("ok"))
        except Exception:
            sie_ok = False
    if sie_ok:
        # Placeholder: real SDK score would go here when SIE is installed.
        # Until then still jaccard but label hybrid_ready.
        method = "sie_reachable_but_sdk_not_wired_jaccard"
    for row in rows:
        row["score"] = round(jaccard(q, str(row.get("text") or "")), 4)
    rows.sort(key=lambda r: float(r.get("score") or 0.0), reverse=True)
    return {
        "truth_label": TRUTH_LABEL,
        "query": q,
        "method": method,
        "sie_reachable": sie_ok,
        "ranked": rows,
        "ts": time.time(),
    }


def recall(
    query: str,
    *,
    state_dir: Optional[Path | str] = None,
    top_k: int = 5,
) -> dict[str, Any]:
    cands = load_candidate_snippets(state_dir=state_dir)
    scored = score_candidates(query, cands)
    ranked = list(scored.get("ranked") or [])[: max(1, int(top_k))]
    scored["top"] = ranked
    return scored


def recall_prompt_block(
    query: str,
    *,
    state_dir: Optional[Path | str] = None,
    top_k: int = 4,
    max_chars: int = 1200,
) -> str:
    """Inject ranked memory evidence for 'do you remember' turns."""
    low = str(query or "").lower()
    if not any(
        k in low
        for k in (
            "remember",
            "recall",
            "do you know",
            "what did we",
            "last time",
            "journal",
            "wct",
            "we code together",
        )
    ):
        return ""
    out = recall(query, state_dir=state_dir, top_k=top_k)
    top = out.get("top") or []
    if not top:
        return (
            "MEMORY RECALL (r1622-02): no ranked ledger snippets for this query. "
            f"method={out.get('method')}. Do not invent memories."
        )
    lines = [
        f"MEMORY RECALL (r1622-02 — ranked evidence, method={out.get('method')}):",
        "Answer from these receipts; say unknown if not covered.",
    ]
    for i, row in enumerate(top, 1):
        lines.append(
            f"  {i}. score={row.get('score')} src={row.get('source')} "
            f"id={row.get('receipt_id') or '—'} :: {str(row.get('text') or '')[:220]}"
        )
    block = "\n".join(lines)
    return block[:max_chars] if len(block) > max_chars else block


__all__ = [
    "TRUTH_LABEL",
    "jaccard",
    "load_candidate_snippets",
    "score_candidates",
    "recall",
    "recall_prompt_block",
]
