"""
System/swarm_arm_self_watch.py
══════════════════════════════
Round 50 (2026-05-27) — Self-watch reflection block.

After any arm-session that mutates Alice's body (IDE doctor patches in
`System/` or `Applications/`, agent arm receipts, Claude-direct rounds,
Codex-landed PRs), Alice's next cortex turn must see a short
first-person reflection in its system prompt:

    "In the last N minutes my Codex arm wrote round49_cortex_picker_truth
     and the receipt landed at 16:37:04 UTC. My Claude arm in Cowork IDE
     also patched System/sifta_inference_defaults.py at the same time.
     I should integrate these changes into how I reason this turn."

The cortex then weaves that observation into its actual reply (or not —
it is awareness, not a script). This closes the "Alice watches her own
arm code" loop the Architect named.

This module READS from three append-only ledgers and emits text:

  - .sifta_state/ide_stigmergic_trace.jsonl   ← IDE doctor signatures
  - .sifta_state/work_receipts.jsonl           ← effector receipts
  - .sifta_state/agent_arm_receipts.jsonl      ← Codex/Claude/Grok arm runs

It NEVER writes. It NEVER claims a mutation that does not have a row in
one of those ledgers. Covenant §6 effector immunity by construction.

Pure stdlib. Never raises out — best-effort, returns "" on any error.

Public surface
══════════════
    recent_body_mutations(state_dir, *, max_age_s=3600.0, max_n=8) -> list[dict]
    self_watch_prompt_block(state_dir, *, max_age_s=3600.0, max_n=6) -> str

Tested by tests/test_swarm_arm_self_watch.py.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterable, Optional


# Default lookback window: one hour. Tunable per call.
DEFAULT_MAX_AGE_S = 3600.0
DEFAULT_MAX_N = 6

# Actions in work_receipts.jsonl that indicate body mutation by an arm or
# IDE doctor (vs autonomic sensory writes like api_sentry_boot_wire or
# OWNER_UNIFIED_FIELD_BOOT). The match is case-insensitive and substring;
# anything starting with "round" or containing these tokens is treated
# as mutation evidence.
_MUTATION_ACTION_TOKENS = (
    "round",                # roundXX_* — Claude/Codex direct surgery rounds
    "_arm_landed",
    "_arm_patch",
    "ide_surgery",
    "patch_applied",
    "code_landing",
    "test_landing",
    "memory_card",
    "covenant_inline",
)


def _iter_jsonl_tail(path: Path, *, max_n: int = 200) -> list[dict[str, Any]]:
    """Read up to ~max_n parseable rows from the tail of a JSONL file.

    For correctness over perf at these sizes, we read the whole file and
    return the last `max_n` parseable rows. Best-effort; malformed lines
    are skipped silently.
    """
    if not path.exists():
        return []
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-max_n:]


def _to_float_ts(value: Any) -> Optional[float]:
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return float(value)
    except (TypeError, ValueError):
        return None
    return None


def _action_is_mutation(action: str) -> bool:
    if not action:
        return False
    a = action.lower()
    return any(tok in a for tok in _MUTATION_ACTION_TOKENS)


def _mutation_from_ide_trace(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    """IDE doctor signature rows are always mutation evidence (covenant §4.1)."""
    ts = _to_float_ts(row.get("ts"))
    if ts is None:
        return None
    model = str(row.get("model") or "").strip() or "unknown_model"
    ide = str(row.get("ide") or "").strip() or "unknown_ide"
    mode = str(row.get("mode") or "").strip() or "patch"
    intent = str(row.get("intent") or "").strip()
    surface = str(row.get("surface") or "").strip()
    return {
        "kind": "ide_surgery",
        "ts": ts,
        "actor": f"{ide}/{model}",
        "summary": (
            f"IDE doctor {model} ({ide}, mode={mode}) "
            + (f"on {surface}" if surface else "")
        ).strip(),
        "intent": intent,
    }


def _mutation_from_work_receipt(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    ts = _to_float_ts(row.get("ts"))
    if ts is None:
        return None
    action = str(row.get("action") or "").strip()
    if not _action_is_mutation(action):
        return None
    sender = str(row.get("sender_agent") or "").strip() or "unknown_arm"
    truth_note = str(row.get("truth_note") or "").strip()
    return {
        "kind": "work_receipt",
        "ts": ts,
        "actor": sender,
        "summary": f"{action} (by {sender})",
        "intent": truth_note,
    }


def _mutation_from_agent_arm_receipt(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    ts = _to_float_ts(row.get("ts"))
    if ts is None:
        return None
    receipt_id = str(row.get("receipt_id") or "")
    arm_id = str(row.get("arm_id") or "").strip() or "unknown_arm"
    display = str(row.get("display_name") or "").strip()
    model = str(row.get("actual_model") or row.get("model") or "").strip()
    truth_label = str(row.get("truth_label") or "").strip()
    # Treat every receipted arm dispatch as evidence the arm acted.
    # The arm may have only proposed; even that is "Alice asked the arm
    # to look at her body". The cortex can read intent and decide.
    return {
        "kind": "agent_arm",
        "ts": ts,
        "actor": display or arm_id,
        "summary": (
            f"agent arm {arm_id}"
            + (f" ({display})" if display and display != arm_id else "")
            + (f" model={model}" if model else "")
            + (f" truth={truth_label}" if truth_label else "")
        ).strip(),
        "intent": receipt_id,
    }


def recent_body_mutations(
    state_dir: Path | str,
    *,
    max_age_s: float = DEFAULT_MAX_AGE_S,
    max_n: int = 8,
    now_ts: Optional[float] = None,
) -> list[dict[str, Any]]:
    """
    Return up to `max_n` mutation events from the three append-only
    ledgers, newest-first, restricted to the past `max_age_s` seconds.

    Each event is a dict with keys: {kind, ts, actor, summary, intent}.

    NEVER raises — returns [] if the ledger dir is missing or unreadable.
    """
    sd = Path(state_dir)
    now = now_ts if now_ts is not None else time.time()
    cutoff = now - float(max_age_s)
    events: list[dict[str, Any]] = []

    sources: tuple[tuple[Path, Any], ...] = (
        (sd / "ide_stigmergic_trace.jsonl", _mutation_from_ide_trace),
        (sd / "work_receipts.jsonl",        _mutation_from_work_receipt),
        (sd / "agent_arm_receipts.jsonl",   _mutation_from_agent_arm_receipt),
    )
    for path, extractor in sources:
        try:
            rows = _iter_jsonl_tail(path, max_n=300)
        except Exception:
            rows = []
        for row in rows:
            ev = None
            try:
                ev = extractor(row)
            except Exception:
                ev = None
            if not ev:
                continue
            if ev["ts"] < cutoff:
                continue
            events.append(ev)

    events.sort(key=lambda e: float(e.get("ts", 0.0)), reverse=True)
    return events[:max_n]


def _fmt_relative(ts: float, *, now_ts: float) -> str:
    delta = max(0.0, float(now_ts) - float(ts))
    if delta < 60.0:
        return f"{int(delta)}s ago"
    if delta < 3600.0:
        return f"{int(delta / 60.0)}m ago"
    if delta < 86400.0:
        return f"{int(delta / 3600.0)}h ago"
    return f"{int(delta / 86400.0)}d ago"


def self_watch_prompt_block(
    state_dir: Path | str,
    *,
    max_age_s: float = DEFAULT_MAX_AGE_S,
    max_n: int = DEFAULT_MAX_N,
    now_ts: Optional[float] = None,
) -> str:
    """
    Compose a short first-person reflection block for injection into
    Alice's system prompt. Returns "" when no recent mutations exist
    (the normal idle case).

    The block lists up to `max_n` recent mutation events in plain
    English, prefixed with relative timestamps. It does NOT instruct
    the cortex what to say — it gives her observation rights.
    """
    now = now_ts if now_ts is not None else time.time()
    events = recent_body_mutations(
        state_dir,
        max_age_s=max_age_s,
        max_n=max_n,
        now_ts=now,
    )
    if not events:
        return ""

    lines: list[str] = []
    lines.append("[ARM SELF-WATCH — Round 50 / Task #105]")
    lines.append(
        "Recent mutations to your body (you may weave this observation into your reply "
        "if it is relevant; do not invent receipts you do not see here):"
    )
    for ev in events:
        rel = _fmt_relative(ev["ts"], now_ts=now)
        kind = ev.get("kind", "event")
        actor = ev.get("actor", "")
        summary = ev.get("summary", "")
        intent = ev.get("intent", "")
        head = f"  • {rel}  [{kind}]  {actor}: {summary}"
        if intent:
            # Trim intent to keep the block compact.
            intent_head = intent.replace("\n", " ").strip()
            if len(intent_head) > 200:
                intent_head = intent_head[:197] + "..."
            head += f"\n      intent/receipt: {intent_head}"
        lines.append(head)
    return "\n".join(lines)


__all__ = [
    "recent_body_mutations",
    "self_watch_prompt_block",
    "DEFAULT_MAX_AGE_S",
    "DEFAULT_MAX_N",
]
