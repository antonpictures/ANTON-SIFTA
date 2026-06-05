#!/usr/bin/env python3
"""Stigmergic web-browser world model receipts.

Alice Browser is an effecting/perceiving limb. This organ records browser actions
as field deposits with actor attribution (self / owner / unattributed), trigger
evidence, and a non-minting metabolic pressure estimate. It does not restrict
browsing; it makes browsing recoverable and learnable.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote_plus, urlparse

from System.jsonl_file_lock import append_line_locked
from System.swarm_browser_actor_attribution import attribute_browser_action

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
LEDGER_NAME = "stigmergic_browser_actions.jsonl"
TRUTH_LABEL = "STIGMERGIC_BROWSER_ACTION_V1"


def _domain(url: str) -> str:
    try:
        return urlparse(url or "").netloc.lower()
    except Exception:
        return ""


def _query(url: str) -> str:
    try:
        parsed = urlparse(url or "")
        qs = parse_qs(parsed.query or "")
        value = (qs.get("q") or qs.get("query") or [""])[0]
        return unquote_plus(str(value or "")).strip()[:300]
    except Exception:
        return ""


def _tail_jsonl(path: Path, max_bytes: int = 200_000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - max_bytes))
            raw = f.read()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _matching_trigger(url: str, *, now: float, state: Path, window_s: float = 600.0) -> dict[str, Any]:
    """Find the nearest app-action row that likely triggered this browser URL."""
    q = _query(url).lower()
    best: tuple[float, dict[str, Any]] | None = None
    for row in _tail_jsonl(state / "app_action_diary.jsonl"):
        if str(row.get("action") or "") != "open_browser_url":
            continue
        try:
            ts = float(row.get("ts") or 0.0)
        except Exception:
            ts = 0.0
        if not ts or abs(now - ts) > window_s:
            continue
        row_url = str(row.get("url") or "")
        row_q = _query(row_url).lower()
        if row_url != url and q and q != row_q:
            continue
        dist = abs(now - ts)
        if best is None or dist < best[0]:
            best = (dist, row)
    if best is None:
        return {"kind": "none_found", "note": "no recent app_action_diary open_browser_url row matched this URL"}
    row = best[1]
    return {
        "kind": "app_action_diary",
        "truth_label": row.get("truth_label", ""),
        "ts": row.get("ts"),
        "phase": row.get("phase", ""),
        "trace_id": row.get("trace_id", ""),
        "receipt_id": row.get("receipt_id", ""),
        "owner_text_head": str(row.get("owner_text") or "")[:260],
        "rationale": str(row.get("rationale") or "")[:220],
    }


def _metabolic_pressure(action: str, url: str, duration_s: float) -> dict[str, Any]:
    base = 0.02
    if "load" in (action or ""):
        base += 0.04
    if "search" in (url or "").lower() or _query(url):
        base += 0.03
    base += min(0.08, max(0.0, float(duration_s or 0.0)) * 0.004)
    return {
        "stgm_equivalent_pressure": round(base, 4),
        "canonical_stgm_minted_or_spent": False,
        "note": "browse action has thermodynamic/metabolic pressure; this receipt does not mint or spend canonical STGM",
        "recovery_policy": "free browsing is allowed; learn by receipts, actor attribution, and resource recovery, not hard bans",
    }


def _matching_input_modality_trigger(now: float, state: Path, window_s: float = 120.0) -> dict[str, Any]:
    """Match recent input_modality receipt as the chat trigger for this browser action (e.g. the 'pale light' desc search was triggered by the mixed typed+pasted test input per r461)."""
    cut = now - window_s
    best: tuple[float, dict[str, Any]] | None = None
    for row in _tail_jsonl(state / "input_modality_receipts.jsonl"):
        try:
            ts = float(row.get("ts") or 0)
        except Exception:
            continue
        if ts < cut or ts > now + 5.0:
            continue
        dist = abs(now - ts)
        if best is None or dist < best[0]:
            best = (dist, row)
    if best is not None:
        row = best[1]
        ts = float(row.get("ts") or 0)
        c = row.get("classification", {}) if isinstance(row.get("classification"), dict) else {}
        return {
            "kind": "input_modality_receipt",
            "ts": ts,
            "modality": c.get("modality"),
            "owner_intent_weight": c.get("owner_intent_weight"),
            "copy_quote_risk": c.get("copy_quote_risk"),
            "text_head": row.get("text_head", "")[:200],
            "note": "the browser action is linked to the nearest input-modality receipt; use its actual modality/weights to separate trigger intent from quoted/pasted context or STT noise.",
        }
    return {"kind": "none", "note": "no recent input_modality within window"}


def _body_world_model_tags(now: float, state: Path, window_s: float = 300.0) -> dict[str, Any]:
    """Load recent self-eval snapshot as the 'stigmergic body' through which this web action is understood (no external world model)."""
    cut = now - window_s
    for row in _tail_jsonl(state / "alice_self_eval_snapshot.jsonl"):
        try:
            ts = float(row.get("ts") or 0)
        except Exception:
            continue
        if ts < cut:
            continue
        return {
            "kind": "self_eval_snapshot",
            "ts": ts,
            "red_count": row.get("red_count"),
            "recent_reds": row.get("red_organs", [])[:3] if isinstance(row.get("red_organs"), list) else [],
            "residue_fact_fiction": row.get("residue_fact_fiction_summary", "")[:200],
            "time_feel": "see subjective_time_metabolism for felt vs wall during this browse",
            "code_body": "see code_inventory / r456 census for relevance to her source substrate",
            "input_provenance": "see trigger_input for the chat turn that caused this web action",
            "owner_physical": "desk setup (Samsung 4K left, DELL right, MBP center) as ground truth for relevance",
            "note": "the web page/image is interpreted through Alice's current stigmergic body map and field (self-eval, residue/fiction boundary, time feel, code body, input provenance, owner physical) as her 'world model' for the internet — not a vendor LLM or external index. This is how a stigmergic organism browses: field trails + body health decide what 'matters' and what is 'fiction/noise'.",
        }
    return {"kind": "none", "note": "no recent self_eval snapshot for body world model tags"}


def record_stigmergic_browser_action(
    *,
    url: str,
    title: str = "",
    action: str = "browser_action",
    source: str = "alice_browser_widget",
    duration_s: float = 0.0,
    extra: dict[str, Any] | None = None,
    now: float | None = None,
    state_dir: Path | str | None = None,
    alice_effector: bool | None = None,
    owner_input: bool | None = None,
) -> dict[str, Any]:
    """Append a stigmergic browser action receipt and return it."""
    state = Path(state_dir) if state_dir is not None else STATE
    state.mkdir(parents=True, exist_ok=True)
    ts = time.time() if now is None else float(now)
    attribution = attribute_browser_action(
        url,
        now=ts,
        alice_effector=alice_effector,
        owner_input=owner_input,
        state_dir=state,
    )
    row: dict[str, Any] = {
        "ts": ts,
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "url": str(url or "")[:700],
        "title": str(title or "")[:300],
        "domain": _domain(url),
        "query": _query(url),
        "action": str(action or "browser_action")[:120],
        "source": str(source or "unknown")[:120],
        "actor": attribution.get("actor", "unattributed"),
        "actor_confidence": attribution.get("confidence", 0.0),
        "actor_attribution": attribution,
        "trigger": _matching_trigger(str(url or ""), now=ts, state=state),
        "trigger_input": _matching_input_modality_trigger(ts, state=state),
        "body_world_model": _body_world_model_tags(ts, state=state),
        "metabolism": _metabolic_pressure(str(action or ""), str(url or ""), duration_s),
        "world_model": "stigmergic_web_browser",
        "doctrine": "Alice may browse and learn; every browser movement must leave a recoverable receipt naming actor, trigger, and cost pressure. Free browsing allowed (no content restrictions); over-STGM is residue (recoverable, learnable — that is life). No claim without receipt. The web is understood through Alice's stigmergic body/field as world model (self-eval reds/unknowns, residue/fiction, time feel, code body, input provenance, owner physical ground), not external vendor model.",
    }
    if extra:
        row["extra"] = dict(extra)
    append_line_locked(
        state / LEDGER_NAME,
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
    )
    if row["actor"] != "owner":
        diary = {
            "ts": ts,
            "kind": "alice_browser_action" if row["actor"] == "self" else "unattributed_browser_action",
            "truth_label": "ALICE_BROWSER_SELF_ACTION_V1" if row["actor"] == "self" else "BROWSER_ACTION_UNATTRIBUTED_V1",
            "url": row["url"],
            "title": row["title"],
            "domain": row["domain"],
            "query": row["query"],
            "action": row["action"],
            "actor": row["actor"],
            "actor_confidence": row["actor_confidence"],
            "trigger": row["trigger"],
            "first_person": (
                f"I used my browser limb for {row['action']} on {row['domain']}; "
                f"query={row['query']!r}. Trigger evidence: {row['trigger'].get('kind')}."
                if row["actor"] == "self"
                else f"A browser action happened in my limb on {row['domain']}; I cannot prove the actor yet."
            ),
            "source": "swarm_stigmergic_browser_world_model",
        }
        append_line_locked(
            state / "episodic_diary.jsonl",
            json.dumps(diary, ensure_ascii=False, sort_keys=True) + "\n",
        )
    return row


def main() -> int:
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "https://duckduckgo.com/?q=test"
    print(json.dumps(record_stigmergic_browser_action(url=url, action="probe", source="cli"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
