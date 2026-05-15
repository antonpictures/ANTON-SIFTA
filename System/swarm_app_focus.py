#!/usr/bin/env python3
"""
System/swarm_app_focus.py — Stigmergic App-Focus Ledger
========================================================
Any SIFTA app can publish its current state here via `publish_focus()`.
Alice reads the latest state via `get_focus_context()` before responding.

Architecture:
  - Apps write: "I am [app_name], user is looking at [detail]"
  - Alice reads: latest focus entry → injects it into her system prompt
  - NO hardcoding per app — apps publish; Alice reads. Tool-based, not rule-based.

Stigmergic attention field (added 2026-05-11):
  Apps that receive focus deposit pheromone traces. The field accumulates
  which apps are focused on most often. get_focus_context() now returns
  field-weighted context when multiple recent entries exist — apps with
  stronger accumulated traces get priority in Alice's attention.

  Same mechanism as:
    Bell app: persistent field guides particle decisions
    Scheduler: routing field guides task allocation
    Hippocampus: salience field guides memory retrieval
    Here: attention field guides Alice's gaze

  Bio parallel: ant trail reinforcement to food sources.
  Apps = food sources. Focus = ant visits. Field = trail strength.

Ledger: .sifta_state/app_focus.jsonl  (append-only, compact)
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional

from System.jsonl_file_lock import append_line_locked
from System.stigmergic_field import FieldConfig, StigmergicField

_REPO  = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
LEDGER = _STATE / "app_focus.jsonl"
_ATTENTION_FIELD_PATH = _STATE / "app_focus_attention_field.json"
_ATTENTION_RECEIPTS = _STATE / "app_focus_attention_receipts.jsonl"
_ATTENTION_FIELD_CONFIG = FieldConfig(
    n_bins=256,
    n_channels=2,
    fast_decay=0.90,
    slow_decay=0.997,
    fast_weight=0.35,
    slow_weight=0.65,
    threshold=0.5,
)


def _focus_key(app_name: str, tab: str = "") -> str:
    app = (app_name or "unknown_app").strip().lower()
    t = (tab or "").strip().lower()
    return f"{app}|{t}" if t else app


def _focus_bin(app_name: str, tab: str = "") -> int:
    digest = hashlib.sha256(_focus_key(app_name, tab).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % _ATTENTION_FIELD_CONFIG.n_bins


def _load_attention_field() -> StigmergicField:
    return StigmergicField.load(_ATTENTION_FIELD_PATH, fallback_config=_ATTENTION_FIELD_CONFIG)


def publish_focus(
    app_name: str,
    detail: str,
    *,
    tab: str = "",
    selection: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Called by any SIFTA app when user interacts with something noteworthy.
    
    Args:
        app_name:  Human-readable app title (e.g. "Assembly Theory Lab")
        detail:    Short description of what the user is looking at / doing
        tab:       Current tab name if app has tabs
        selection: Specific selected item (e.g. question text, molecule name)
        metadata:  Optional extra data the app wants Alice to know
    """
    _STATE.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts":        time.time(),
        "app":       app_name,
        "detail":    detail,
        "tab":       tab,
        "selection": selection,
        "metadata":  metadata or {},
    }
    try:
        meta = metadata or {}
        amount = float(meta.get("salience_score", meta.get("attention_amount", 1.0)) or 1.0)
        receipt = deposit_attention_trace(
            app_name,
            tab=tab,
            success=True,
            amount=amount,
            reason=str(meta.get("source") or "publish_focus"),
        )
        entry["attention_score"] = receipt.get("attention_score", 0.0)
    except Exception:
        pass
    try:
        append_line_locked(LEDGER, json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # ledger write is best-effort, never crash an app


def deposit_attention_trace(
    app_name: str,
    *,
    tab: str = "",
    success: bool = True,
    amount: float = 1.0,
    reason: str = "focus_observed",
) -> dict[str, Any]:
    """Deposit pheromone trace for an app that received focus.

    Same mechanism as scheduler routing field and hippocampus salience.
    Apps that get focused on frequently accumulate stronger traces,
    biasing Alice's attention toward consistently important apps.
    """
    field = _load_attention_field()
    field.decay()
    bin_idx = _focus_bin(app_name, tab)
    channel = 0 if success else 1
    clean_amount = max(0.01, min(float(amount or 1.0), 5.0))
    field.deposit(bin_idx, channel, clean_amount)
    try:
        field.save(_ATTENTION_FIELD_PATH)
    except Exception:
        pass
    row = {
        "ts": time.time(),
        "schema": "SIFTA_APP_FOCUS_ATTENTION_TRACE_V1",
        "app": app_name,
        "tab": tab,
        "bin": bin_idx,
        "channel": "useful" if success else "noisy",
        "amount": round(clean_amount, 6),
        "reason": reason,
        "attention_score": focus_attention_score(app_name, tab=tab),
        "field_snapshot": field.snapshot(),
    }
    try:
        append_line_locked(_ATTENTION_RECEIPTS, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return row


def _deposit_attention_trace(app_name: str, amount: float = 1.0) -> None:
    """Backward-compatible wrapper for older callers."""
    deposit_attention_trace(app_name, amount=amount)


def focus_attention_score(app_name: str, *, tab: str = "") -> float:
    """Return learned attention score for one app/tab context."""
    field = _load_attention_field()
    score = field.read_correlation(_focus_bin(app_name, tab))
    return round(float(score or 0.0), 6)


def get_attention_field() -> dict[str, float]:
    """Read a compact attention-field view for compatibility/UI."""
    try:
        field = _load_attention_field()
        return {
            "energy": round(field.energy, 6),
            "fast_energy": round(field.fast_energy, 6),
            "slow_energy": round(field.slow_energy, 6),
            "deposits": field.snapshot().get("deposits", 0),
        }
    except Exception:
        pass
    return {}


def get_focus_context(max_age_s: float = 120.0) -> Optional[str]:
    """Read the most recent focus entry. Returns a prompt-ready string or None.
    
    Args:
        max_age_s: Ignore entries older than this many seconds.
    """
    if not LEDGER.exists():
        return None
    try:
        raw = LEDGER.read_text(encoding="utf-8").strip().split("\n")
        if not raw or not raw[-1]:
            return None
        entry = json.loads(raw[-1])
    except Exception:
        return None

    age = time.time() - entry.get("ts", 0)
    if age > max_age_s:
        return None

    try:
        from System.swarm_kernel_identity import owner_display_name

        who = owner_display_name("The primary operator")
    except Exception:
        who = "The primary operator"
    parts = [f"{who} has '{entry['app']}' open."]
    if entry.get("tab"):
        parts.append(f"Active tab: {entry['tab']}.")
    if entry.get("selection"):
        parts.append(f"Selected: {entry['selection']}.")
    if entry.get("detail"):
        parts.append(f"Context: {entry['detail']}.")
    try:
        score = float(entry.get("attention_score", focus_attention_score(entry.get("app", ""), tab=entry.get("tab", ""))))
        if abs(score) >= 0.05:
            parts.append(f"Attention field score: {score:+.2f}.")
    except Exception:
        pass
    meta = entry.get("metadata", {})
    if meta:
        for k, v in meta.items():
            parts.append(f"{k}: {v}")

    # Inject field-weighted attention context
    ranked = ranked_focus_history(n=3, max_age_s=max_age_s * 3)
    if ranked:
        attention_str = ", ".join(
            f"{r.get('app', '?')} ({float(r.get('attention_rank_score', 0.0)):+.2f})"
            for r in ranked
        )
        parts.append(f"[Attention field: {attention_str}]")

    return " ".join(parts)


def get_recent_focus_history(n: int = 5, max_age_s: float = 300.0) -> list[dict]:
    """Return last N focus entries within max_age_s. Useful for Alice's 
    short-term memory of what apps the Architect has been browsing."""
    if not LEDGER.exists():
        return []
    try:
        raw = LEDGER.read_text(encoding="utf-8").strip().split("\n")
    except Exception:
        return []
    now = time.time()
    recent = []
    for line in reversed(raw):
        if len(recent) >= n:
            break
        try:
            entry = json.loads(line)
            if now - entry.get("ts", 0) <= max_age_s:
                recent.append(entry)
        except Exception:
            continue
    recent.reverse()
    return recent


def ranked_focus_history(n: int = 5, max_age_s: float = 300.0) -> list[dict]:
    """Return recent focus entries ranked by field score plus recency."""
    now = time.time()
    rows = get_recent_focus_history(n=max(n * 3, n), max_age_s=max_age_s)
    scored: list[tuple[float, dict]] = []
    for entry in rows:
        age = max(0.0, now - float(entry.get("ts", now) or now))
        recency = max(0.0, 1.0 - age / max(max_age_s, 1.0))
        attention = focus_attention_score(entry.get("app", ""), tab=entry.get("tab", ""))
        score = (0.65 * attention) + (0.35 * recency)
        enriched = dict(entry)
        enriched["attention_score"] = attention
        enriched["attention_rank_score"] = round(score, 6)
        scored.append((score, enriched))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[:n]]


if __name__ == "__main__":
    # Self-test
    publish_focus(
        "Assembly Theory Lab",
        "Viewing molecule complexity chart",
        tab="Assembly Index",
        selection="Taxol (anti-cancer drug)",
        metadata={"assembly_index": 56, "verdict": "LIFE-REQUIRED"},
    )
    ctx = get_focus_context()
    print(f"Focus context: {ctx}")
    print(f"Recent history: {get_recent_focus_history()}")
