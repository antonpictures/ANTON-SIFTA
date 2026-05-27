#!/usr/bin/env python3
"""SIFTA Long-Horizon Memory Card Composer — Cowork branch.

Composes a compact "memory card" for injection into Alice's prompt before each
turn so her cortex sees long-horizon context (persistent facts, active projects,
episodic highlights, recent conversation tail) within a hard token budget. The
storage is already rich (`alice_conversation.jsonl`, `episodic_diary.jsonl`,
`work_receipts.jsonl`, owner facts); this module is the *scoop* that brings the
salient slice into the cortex's active context window.

Pure stdlib. No PyQt, no network. Never raises on malformed ledger rows —
best-effort, skip and count.

Ledger expectations (all JSONL, one row per line, malformed rows skipped):
  - alice_conversation.jsonl: {"ts": float, "role": "owner"|"alice", "text": str, ...}
  - episodic_diary.jsonl:     {"ts": float, "title": str, "salience": float?, ...}
  - work_receipts.jsonl:      {"ts": float, "event"|"kind": str, "status"?: str, ...}
  - owner_facts.jsonl:        {"fact": str, "owner_flag"?: bool, "ts"?: float, ...}

Ranking is deterministic:
  salience = W_RECENCY * recency_score + W_FLAG * is_owner_flagged + W_EPISODIC * episodic_weight

where ``recency_score = 1 / (1 + age_seconds / RECENCY_HALFLIFE_S)``. Weights are
documented as module-level constants and may be overridden via the function call.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

TRUTH_LABEL = "MEMORY_CARD_V1"

# Default ranking weights. Tunable per call via `weights=`.
W_RECENCY = 1.0
W_FLAG = 2.0
W_EPISODIC = 1.5
RECENCY_HALFLIFE_S = 3600.0  # one hour: row from one hour ago scores 0.5

# Default budget shares (used to allocate the token budget across sections
# before salience-pruning).
_DEFAULT_SHARES = {
    "recent_turns": 0.55,
    "persistent_facts": 0.15,
    "active_projects": 0.15,
    "episodic_highlights": 0.10,
    "last_seen_deltas": 0.05,
}

# Number of conversation turns to consider from the tail before ranking.
_TAIL_TURN_LIMIT = 40
# How long a work receipt is considered "active" if no explicit status.
_ACTIVE_PROJECT_WINDOW_S = 7 * 24 * 3600  # 7 days
# Last-seen state file (lives under the ledgers dir).
_LAST_SEEN_FILE = "memory_card_last_seen.json"


# ─────────────────────────── Data ──────────────────────────────


@dataclass(frozen=True)
class ConversationTurn:
    ts: float
    role: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"ts": self.ts, "role": self.role, "text": self.text}


@dataclass
class MemoryCard:
    recent_turns: list[ConversationTurn] = field(default_factory=list)
    persistent_facts: list[str] = field(default_factory=list)
    active_projects: list[str] = field(default_factory=list)
    episodic_highlights: list[str] = field(default_factory=list)
    last_seen_deltas: list[str] = field(default_factory=list)
    estimated_tokens: int = 0
    parse_errors: int = 0
    truth_label: str = TRUTH_LABEL

    def to_dict(self) -> dict[str, Any]:
        return {
            "recent_turns": [t.to_dict() for t in self.recent_turns],
            "persistent_facts": list(self.persistent_facts),
            "active_projects": list(self.active_projects),
            "episodic_highlights": list(self.episodic_highlights),
            "last_seen_deltas": list(self.last_seen_deltas),
            "estimated_tokens": self.estimated_tokens,
            "parse_errors": self.parse_errors,
            "truth_label": self.truth_label,
        }


# ─────────────────────────── Helpers ────────────────────────────


def _estimate_tokens(text: str) -> int:
    """Cheap, stable token estimate: ~4 chars per token, min 1 if non-empty."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    """Read a JSONL file, returning (rows, parse_error_count). Never raises."""
    if not path.exists():
        return [], 0
    rows: list[dict[str, Any]] = []
    errors = 0
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        rows.append(obj)
                    else:
                        errors += 1
                except (json.JSONDecodeError, UnicodeDecodeError):
                    errors += 1
    except OSError:
        return [], 0
    return rows, errors


def _recency_score(ts: float, now: float, halflife_s: float = RECENCY_HALFLIFE_S) -> float:
    age = max(0.0, now - float(ts or 0.0))
    if halflife_s <= 0:
        return 1.0
    return 1.0 / (1.0 + age / halflife_s)


def _salience(
    *,
    ts: float,
    now: float,
    owner_flagged: bool,
    episodic_weight: float,
    weights: dict[str, float],
    halflife_s: float,
) -> float:
    return (
        weights.get("recency", W_RECENCY) * _recency_score(ts, now, halflife_s)
        + weights.get("flag", W_FLAG) * (1.0 if owner_flagged else 0.0)
        + weights.get("episodic", W_EPISODIC) * float(episodic_weight or 0.0)
    )


def _load_last_seen(state_path: Path) -> float:
    if not state_path.exists():
        return 0.0
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return float(data.get("last_seen_ts", 0.0))
    except (json.JSONDecodeError, OSError, ValueError):
        return 0.0
    return 0.0


def _write_last_seen(state_path: Path, ts: float) -> None:
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"last_seen_ts": float(ts), "truth_label": TRUTH_LABEL}),
            encoding="utf-8",
        )
    except OSError:
        pass


# ─────────────────────────── Compose ────────────────────────────


def compose_memory_card(
    ledgers_dir: Path,
    *,
    token_budget: int = 2000,
    now: float | None = None,
    weights: dict[str, float] | None = None,
    halflife_s: float = RECENCY_HALFLIFE_S,
    persist_last_seen: bool = True,
) -> MemoryCard:
    """Compose a MemoryCard from the live SIFTA ledgers.

    Inputs are read live from JSONL files under ``ledgers_dir``. Salience is
    deterministic given the same inputs and weights. The returned card always
    satisfies ``estimated_tokens <= token_budget`` (truncating from the
    least-salient end if needed)."""
    ledgers_dir = Path(ledgers_dir)
    now = float(now) if now is not None else time.time()
    weights = weights or {"recency": W_RECENCY, "flag": W_FLAG, "episodic": W_EPISODIC}
    token_budget = max(0, int(token_budget))

    parse_errors = 0

    # 1. Conversation tail.
    conv_rows, e = _read_jsonl(ledgers_dir / "alice_conversation.jsonl")
    parse_errors += e
    conv_rows = [r for r in conv_rows if isinstance(r.get("text"), str)]
    conv_rows.sort(key=lambda r: float(r.get("ts") or 0.0))
    tail = conv_rows[-_TAIL_TURN_LIMIT:]

    scored_turns: list[tuple[float, ConversationTurn]] = []
    for r in tail:
        turn = ConversationTurn(
            ts=float(r.get("ts") or 0.0),
            role=str(r.get("role") or "unknown"),
            text=str(r.get("text") or ""),
        )
        score = _salience(
            ts=turn.ts,
            now=now,
            owner_flagged=bool(r.get("owner_flag")),
            episodic_weight=float(r.get("salience") or 0.0),
            weights=weights,
            halflife_s=halflife_s,
        )
        scored_turns.append((score, turn))

    # 2. Persistent facts (owner-tagged).
    fact_rows, e = _read_jsonl(ledgers_dir / "owner_facts.jsonl")
    parse_errors += e
    scored_facts: list[tuple[float, str]] = []
    for r in fact_rows:
        fact = str(r.get("fact") or "").strip()
        if not fact:
            continue
        score = _salience(
            ts=float(r.get("ts") or now),
            now=now,
            owner_flagged=bool(r.get("owner_flag", True)),  # facts default flagged
            episodic_weight=0.0,
            weights=weights,
            halflife_s=halflife_s,
        )
        scored_facts.append((score, fact))

    # 3. Active projects from work_receipts.
    receipt_rows, e = _read_jsonl(ledgers_dir / "work_receipts.jsonl")
    parse_errors += e
    scored_projects: list[tuple[float, str]] = []
    for r in receipt_rows:
        ts = float(r.get("ts") or 0.0)
        if ts and (now - ts) > _ACTIVE_PROJECT_WINDOW_S:
            continue
        status = str(r.get("status") or "").lower()
        if status in {"completed", "closed", "done"}:
            continue
        label = str(r.get("event") or r.get("kind") or r.get("title") or "").strip()
        if not label:
            continue
        score = _salience(
            ts=ts,
            now=now,
            owner_flagged=bool(r.get("owner_flag")),
            episodic_weight=0.0,
            weights=weights,
            halflife_s=halflife_s,
        )
        scored_projects.append((score, label))

    # 4. Episodic highlights.
    episodic_rows, e = _read_jsonl(ledgers_dir / "episodic_diary.jsonl")
    parse_errors += e
    scored_episodic: list[tuple[float, str]] = []
    for r in episodic_rows:
        title = str(r.get("title") or r.get("event") or "").strip()
        if not title:
            continue
        score = _salience(
            ts=float(r.get("ts") or 0.0),
            now=now,
            owner_flagged=bool(r.get("owner_flag")),
            episodic_weight=float(r.get("salience") or 0.5),
            weights=weights,
            halflife_s=halflife_s,
        )
        scored_episodic.append((score, title))

    # 5. last_seen_deltas — what's NEW since last call.
    state_path = ledgers_dir / _LAST_SEEN_FILE
    last_seen_ts = _load_last_seen(state_path)
    deltas: list[str] = []
    max_seen_ts = last_seen_ts
    for src_name, rows in (
        ("conv", conv_rows),
        ("diary", episodic_rows),
        ("receipts", receipt_rows),
    ):
        for r in rows:
            ts = float(r.get("ts") or 0.0)
            if ts > last_seen_ts:
                preview = (
                    str(r.get("text") or r.get("title") or r.get("event") or r.get("kind") or "")
                    .strip()
                    .replace("\n", " ")
                )
                if preview:
                    deltas.append(f"[{src_name}@{int(ts)}] {preview[:160]}")
                if ts > max_seen_ts:
                    max_seen_ts = ts
    deltas.sort()

    # Sort each section by salience descending, deterministic on ties via text.
    scored_turns.sort(key=lambda x: (-x[0], x[1].ts, x[1].text))
    scored_facts.sort(key=lambda x: (-x[0], x[1]))
    scored_projects.sort(key=lambda x: (-x[0], x[1]))
    scored_episodic.sort(key=lambda x: (-x[0], x[1]))

    # ─── per-section budget allocation + truncation ───
    # Each section gets a share of the total budget. Within a section, items
    # are packed in salience-descending order until that share is full. This
    # prevents one section (e.g. deltas) from starving the others on a tight
    # budget, and "drop lowest-salience until it fits" still holds inside each
    # section. Empty sections forfeit their share back to a global leftover
    # pool that the remaining sections may then consume.
    deltas_payload: list[tuple[float, Any]] = [
        # Deltas inherit a small constant salience so they don't compete on
        # rank — they're capped by their share, not by global salience.
        (1.0, s)
        for s in deltas
    ]
    sections: dict[str, list[tuple[float, Any]]] = {
        "recent_turns": list(scored_turns),
        "persistent_facts": list(scored_facts),
        "active_projects": list(scored_projects),
        "episodic_highlights": list(scored_episodic),
        "last_seen_deltas": deltas_payload,
    }

    section_budgets: dict[str, int] = {
        name: int(token_budget * share) for name, share in _DEFAULT_SHARES.items()
    }
    selected: dict[str, list[Any]] = {k: [] for k in sections}
    section_used: dict[str, int] = {k: 0 for k in sections}

    def _try_pack(section: str, lst: list[tuple[float, Any]], cap: int) -> int:
        """Pack ``lst`` into ``selected[section]`` up to ``cap`` tokens. Returns
        the tokens actually used in this pass."""
        used = section_used[section]
        for _score, payload in lst:
            text_for_estimate = (
                payload.text if isinstance(payload, ConversationTurn) else str(payload)
            )
            if not text_for_estimate:
                continue
            cost = _estimate_tokens(text_for_estimate)
            if used + cost > cap:
                continue
            # avoid duplicates if a second pass revisits an already-selected item
            if payload in selected[section]:
                continue
            selected[section].append(payload)
            used += cost
        delta = used - section_used[section]
        section_used[section] = used
        return delta

    # First pass: each section consumes only up to its own share.
    for name, lst in sections.items():
        _try_pack(name, lst, section_budgets[name])

    used_tokens = sum(section_used.values())

    # Second pass: distribute any leftover budget across sections that have
    # remaining ranked items, in fixed priority order (recent > facts > projects
    # > episodic > deltas). Keeps the global cap intact.
    leftover = token_budget - used_tokens
    if leftover > 0:
        priority_order = [
            "recent_turns",
            "persistent_facts",
            "active_projects",
            "episodic_highlights",
            "last_seen_deltas",
        ]
        for name in priority_order:
            if leftover <= 0:
                break
            cap = section_used[name] + leftover
            gained = _try_pack(name, sections[name], cap)
            leftover -= gained

    used_tokens = sum(section_used.values())

    card = MemoryCard(
        recent_turns=[p for p in selected["recent_turns"]],
        persistent_facts=[str(p) for p in selected["persistent_facts"]],
        active_projects=[str(p) for p in selected["active_projects"]],
        episodic_highlights=[str(p) for p in selected["episodic_highlights"]],
        last_seen_deltas=[str(p) for p in selected["last_seen_deltas"]],
        estimated_tokens=used_tokens,
        parse_errors=parse_errors,
        truth_label=TRUTH_LABEL,
    )

    if persist_last_seen and max_seen_ts > last_seen_ts:
        _write_last_seen(state_path, max_seen_ts)

    return card


__all__ = [
    "TRUTH_LABEL",
    "W_RECENCY",
    "W_FLAG",
    "W_EPISODIC",
    "RECENCY_HALFLIFE_S",
    "ConversationTurn",
    "MemoryCard",
    "compose_memory_card",
]
