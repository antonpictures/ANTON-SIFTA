#!/usr/bin/env python3
"""Stigmergic taste + action consequence learning.

This organ is the first pure, file-backed brick for George's r178 correction:
Alice should be allowed to make reversible mistakes, learn from them, and
predict what an action will do to her field before she acts.

Design boundary:
- Reversible browsing/search can proceed in the active owner-driven session.
- High-impact actions still require explicit confirmation.
- Taste is not a fixed preference. Stable anchors and recent context are
  separate traces with different decay rates.
- Mistakes are not shame rows. They are correction rows that become future
  policy evidence.

IDE doctor trace only; no STGM claim.
"""
from __future__ import annotations

import json
import math
import time
import uuid
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TASTE_LEDGER = "stigmergic_taste_field.jsonl"
PREVIEW_LEDGER = "action_consequence_preview.jsonl"
OUTCOME_LEDGER = "action_consequence_outcome.jsonl"

TRUTH_LABEL = "STIGMERGIC_TASTE_CONSEQUENCE_V1"

STABLE_HALF_LIFE_S = 7 * 24 * 60 * 60
RECENT_HALF_LIFE_S = 30 * 60

HIGH_IMPACT_TERMS = {
    "pay", "payment", "purchase", "buy", "order", "checkout",
    "post", "publish", "send", "message", "email", "share",
    "delete", "remove", "follow", "like", "subscribe",
    "download", "upload", "account", "password", "security",
}

REVERSIBLE_KINDS = {
    "browser.search",
    "browser.navigate",
    "browser.open_url",
    "browser.open_profile",
    "site.search",
    "site.navigate",
}


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _append(path: Path, row: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def _read(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    except Exception:
        return []
    return rows


def _decay(age_s: float, half_life_s: float) -> float:
    if age_s <= 0:
        return 1.0
    if half_life_s <= 0:
        return 0.0
    return math.pow(0.5, age_s / half_life_s)


def _action_kind(action: dict[str, Any]) -> str:
    return str(
        action.get("kind")
        or action.get("type")
        or action.get("name")
        or action.get("tool")
        or "unknown"
    ).strip().lower()


def _action_text(action: dict[str, Any]) -> str:
    try:
        return json.dumps(action, sort_keys=True, default=str).lower()
    except Exception:
        return str(action).lower()


def _domain(action: dict[str, Any]) -> str:
    from System.swarm_browser_site_playbook import site_category

    return site_category(
        str(action.get("domain") or action.get("site") or action.get("url") or "unknown")
    )


def _search_url(domain: str, query: str) -> str:
    if domain == "tiktok.com":
        return f"https://www.tiktok.com/search?q={query}"
    if domain == "google.com":
        try:
            from System.swarm_search_engine_registry import search_url as _reg_search
            return _reg_search(query) or f"https://www.google.com/search?q={query}"
        except Exception:
            return f"https://www.google.com/search?q={query}"
    return f"https://{domain}/search?q={query}" if domain != "unknown" else ""


def is_high_impact(action: dict[str, Any]) -> bool:
    text = _action_text(action)
    return any(term in text for term in HIGH_IMPACT_TERMS)


def record_taste_trace(
    category: str,
    item: str,
    *,
    valence: float = 1.0,
    strength: float = 1.0,
    stable: bool = False,
    source: str = "unknown",
    owner_confirmed: bool = False,
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
    write: bool = True,
) -> dict[str, Any]:
    """Record a taste trace.

    Stable traces decay slowly; recent traces decay quickly. Owner confirmation
    upgrades a trace to stable because two bodies agreed on it.
    """
    ts = float(now if now is not None else time.time())
    row = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "memory_kind": "stigmergic_taste_trace",
        "category": str(category or "unknown"),
        "item": str(item or "unknown"),
        "valence": float(max(-1.0, min(1.0, valence))),
        "strength": float(max(0.0, strength)),
        "stable": bool(stable or owner_confirmed),
        "source": str(source or "unknown"),
        "owner_confirmed": bool(owner_confirmed),
    }
    if write:
        _append(_state(state_dir) / TASTE_LEDGER, row)
    return row


def taste_profile(
    category: Optional[str] = None,
    *,
    now: Optional[float] = None,
    limit: int = 8,
    state_dir: Optional[Path | str] = None,
) -> list[dict[str, Any]]:
    """Aggregate taste traces into stable and recent components."""
    ts = float(now if now is not None else time.time())
    rows = _read(_state(state_dir) / TASTE_LEDGER)
    if category:
        rows = [r for r in rows if str(r.get("category")) == str(category)]
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        cat = str(row.get("category") or "unknown")
        item = str(row.get("item") or "unknown")
        key = (cat, item)
        age = max(0.0, ts - float(row.get("ts", ts)))
        stable = bool(row.get("stable"))
        half_life = STABLE_HALF_LIFE_S if stable else RECENT_HALF_LIFE_S
        score = (
            float(row.get("valence", 0.0))
            * float(row.get("strength", 1.0))
            * _decay(age, half_life)
        )
        slot = by_key.setdefault(
            key,
            {
                "category": cat,
                "item": item,
                "stable_score": 0.0,
                "recent_score": 0.0,
                "total_score": 0.0,
                "latest_ts": 0.0,
                "trace_count": 0,
            },
        )
        if stable:
            slot["stable_score"] += score
        else:
            slot["recent_score"] += score
        slot["total_score"] += score
        slot["latest_ts"] = max(float(slot["latest_ts"]), float(row.get("ts", 0.0)))
        slot["trace_count"] += 1
    out = list(by_key.values())
    out.sort(key=lambda r: (float(r["total_score"]), float(r["latest_ts"])), reverse=True)
    return out[: max(0, int(limit))]


def taste_block(
    category: Optional[str] = None,
    *,
    state_dir: Optional[Path | str] = None,
    limit: int = 6,
) -> str:
    profile = taste_profile(category=category, state_dir=state_dir, limit=limit)
    if not profile:
        return ""
    lines = ["STIGMERGIC TASTE (stable anchors + drifting context):"]
    for row in profile:
        lines.append(
            f"- {row['category']} / {row['item']}: total={row['total_score']:.3f}, "
            f"stable={row['stable_score']:.3f}, recent={row['recent_score']:.3f}, "
            f"traces={row['trace_count']}"
        )
    lines.append("Rule: stable anchors guide identity; recent context can change quickly without rewriting identity.")
    return "\n".join(lines)


def predict_action_consequence(
    action: dict[str, Any],
    *,
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
    write: bool = True,
) -> dict[str, Any]:
    """Predict likely field consequences for an action before executing it."""
    ts = float(now if now is not None else time.time())
    action = dict(action or {})
    kind = _action_kind(action)
    domain = _domain(action)
    query = str(action.get("query") or "").strip()
    high_impact = is_high_impact(action)
    reversible = (kind in REVERSIBLE_KINDS) and not high_impact
    confirmation_required = bool(high_impact)
    risk = "HIGH" if high_impact else ("LOW" if reversible else "MEDIUM")
    expected: list[str] = []
    taste_deltas: list[dict[str, Any]] = []
    ledgers: list[str] = []

    if kind in {"browser.search", "site.search"}:
        expected.append(f"navigate browser to search results on {domain}")
        if query:
            expected.append(f"record recent search interest: {query}")
            taste_deltas.append(
                {
                    "category": domain,
                    "item": query,
                    "valence": 0.25,
                    "strength": 1.0,
                    "stable": False,
                    "source": "predicted_browser_search",
                }
            )
        target_url = _search_url(domain, query) if query else ""
        ledgers.extend(["browser_site_search_history.jsonl", TASTE_LEDGER])
    elif kind in {"browser.navigate", "browser.open_url", "site.navigate", "browser.open_profile"}:
        expected.append(f"change current browser page within {domain}")
        target_url = str(action.get("url") or "")
        ledgers.append("browser_stigmergic_memory.jsonl")
    elif high_impact:
        expected.append("high-impact external state may change if confirmed")
        target_url = str(action.get("url") or "")
    else:
        expected.append("unknown or mixed action; observe outcome before strengthening policy")
        target_url = str(action.get("url") or "")

    row = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "memory_kind": "action_consequence_preview",
        "preview_id": uuid.uuid4().hex,
        "action": action,
        "kind": kind,
        "category": domain,
        "target_url": target_url,
        "expected_effects": expected,
        "expected_ledgers": ledgers,
        "taste_deltas": taste_deltas,
        "risk": risk,
        "reversible": reversible,
        "confirmation_required": confirmation_required,
        "mistake_allowed": bool(reversible and not confirmation_required),
        "mistake_policy": (
            "Reversible mistakes are learning traces: record outcome, correction, and update future prediction."
            if reversible and not confirmation_required
            else "Do not deliberately risk this action without explicit owner confirmation."
        ),
    }
    if write:
        _append(_state(state_dir) / PREVIEW_LEDGER, row)
    return row


def record_action_outcome(
    preview: dict[str, Any],
    observed: dict[str, Any],
    *,
    mistake: bool = False,
    correction: str = "",
    owner_feedback: str = "",
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Record what actually happened after a predicted action.

    Successful reversible actions reinforce taste. Mistakes become correction
    traces, not failures to hide.
    """
    ts = float(now if now is not None else time.time())
    row = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "memory_kind": "action_consequence_outcome",
        "preview_id": preview.get("preview_id"),
        "kind": preview.get("kind"),
        "category": preview.get("category"),
        "action": preview.get("action", {}),
        "observed": observed or {},
        "mistake": bool(mistake),
        "correction": str(correction or ""),
        "owner_feedback": str(owner_feedback or ""),
        "learning_status": (
            "MISTAKE_ACCEPTED_LEARNING_TRACE"
            if mistake
            else "PREDICTION_REINFORCED"
        ),
    }
    _append(_state(state_dir) / OUTCOME_LEDGER, row)
    if not mistake:
        for delta in preview.get("taste_deltas", []) or []:
            record_taste_trace(
                str(delta.get("category") or preview.get("category") or "unknown"),
                str(delta.get("item") or "unknown"),
                valence=float(delta.get("valence", 0.0)),
                strength=float(delta.get("strength", 1.0)),
                stable=bool(delta.get("stable")),
                source=str(delta.get("source") or "consequence_outcome"),
                now=ts,
                state_dir=state_dir,
            )
    return row


def recent_mistakes(
    *,
    limit: int = 5,
    state_dir: Optional[Path | str] = None,
) -> list[dict[str, Any]]:
    rows = [
        r for r in _read(_state(state_dir) / OUTCOME_LEDGER)
        if r.get("mistake") is True
    ]
    rows.sort(key=lambda r: float(r.get("ts", 0)), reverse=True)
    return rows[: max(0, int(limit))]


def mistake_learning_block(
    *,
    limit: int = 5,
    state_dir: Optional[Path | str] = None,
) -> str:
    rows = recent_mistakes(limit=limit, state_dir=state_dir)
    if not rows:
        return ""
    lines = ["MISTAKE LEARNING (allowed reversible errors become corrections):"]
    for row in rows:
        lines.append(
            f"- {row.get('kind')} on {row.get('category')}: correction={row.get('correction') or 'none'}"
        )
    return "\n".join(lines)


def taste_consequence_block(state_dir: Optional[Path | str] = None) -> str:
    parts = [taste_block(state_dir=state_dir), mistake_learning_block(state_dir=state_dir)]
    return "\n\n".join(p for p in parts if p)


__all__ = [
    "TRUTH_LABEL",
    "TASTE_LEDGER",
    "PREVIEW_LEDGER",
    "OUTCOME_LEDGER",
    "is_high_impact",
    "record_taste_trace",
    "taste_profile",
    "taste_block",
    "predict_action_consequence",
    "record_action_outcome",
    "recent_mistakes",
    "mistake_learning_block",
    "taste_consequence_block",
]
