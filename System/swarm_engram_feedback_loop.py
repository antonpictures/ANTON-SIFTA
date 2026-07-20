#!/usr/bin/env python3
"""Engram feedback loop — closes the gap between memory and learning.

After each owner turn, this swimmer:
  1. Reads which engrams were active in the last prompt
  2. Scores whether the owner accepted or rejected the engram-guided behavior
  3. Reinforces successful engrams, decays failed ones
  4. Prunes engrams that have decayed below threshold

This is the missing organ: engrams sitting on disk are filing, not learning.
Learning means the organism is CHANGED by what it experienced.

Bio parallel: synaptic consolidation via long-term potentiation (LTP)
and long-term depression (LTD).  Repeated reinforcement strengthens the
synaptic trace; neglect weakens it.

Receipt truth: every reinforce/decay writes a row to
  .sifta_state/engram_feedback_receipts.jsonl

Authors: MiMo (cortex arm) for Alice, 2026-06-14
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked, read_write_json_locked
except ModuleNotFoundError:
    _SCRIPT_REPO = Path(__file__).resolve().parent.parent
    if str(_SCRIPT_REPO) not in sys.path:
        sys.path.insert(0, str(_SCRIPT_REPO))
    from System.jsonl_file_lock import append_line_locked, read_text_locked, read_write_json_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

ENGRAM_FEEDBACK_LEDGER = "engram_feedback_receipts.jsonl"
ACTIVE_ENGRAMS_FILE = "active_engrams.json"
MEMORY_FITNESS_FILE = "memory_fitness.json"
CONVERSATION_LEDGER = "alice_conversation.jsonl"

SCHEMA = "SIFTA_ENGRAM_FEEDBACK_V1"

# ── Signals that indicate owner acceptance ──
ACCEPTANCE_SIGNALS = [
    "yes", "good", "correct", "right", "perfect", "exactly",
    "nice", "well done", "got it", "thanks", "ok", "okay",
    "for the swarm", "that works", "keep going", "do it",
    "approved", "go ahead", "ship it", "landed",
]

# ── Signals that indicate owner rejection / correction ──
REJECTION_SIGNALS = [
    "no", "wrong", "incorrect", "fix", "stop", "delete",
    "revert", "undo", "that's not", "that is not", "don't",
    "do not", "never", "bad", "broken", "failed", "error",
    "horrible", "terrible", "worst", "redo",
]


def _state_dir(state_dir: Optional[Path] = None) -> Path:
    return state_dir if state_dir is not None else _STATE


def _coerce_engram_rule(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("abstract_rule", "rule", "text", "summary", "content"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    return ""


def _load_active_engrams(state_dir: Path) -> list[str]:
    path = state_dir / ACTIVE_ENGRAMS_FILE
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        raw = data.get("engrams", [])
        if not isinstance(raw, list):
            return []
        out = []
        for item in raw:
            rule = _coerce_engram_rule(item)
            if rule:
                out.append(rule)
        return out
    except Exception:
        return []


def _load_recent_conversation(state_dir: Path, n: int = 6) -> list[dict]:
    path = state_dir / CONVERSATION_LEDGER
    if not path.exists():
        return []
    rows = []
    try:
        text = read_text_locked(path, encoding="utf-8", errors="replace")
        for line in text.splitlines()[-n:]:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except Exception:
        pass
    return rows


def _score_owner_signal(text: str) -> float:
    """Score owner turn for acceptance (+1) or rejection (-1). 0 = neutral."""
    lower = text.lower()
    accept = sum(1 for s in ACCEPTANCE_SIGNALS if s in lower)
    reject = sum(1 for s in REJECTION_SIGNALS if s in lower)
    total = accept + reject
    if total == 0:
        return 0.0
    return (accept - reject) / total


def _match_engrams_to_turn(
    engrams: list[str], owner_text: str
) -> list[tuple[int, float]]:
    """Return (index, relevance) for engrams relevant to this turn."""
    matches = []
    owner_lower = owner_text.lower()
    for i, rule in enumerate(engrams):
        rule_lower = rule.lower()
        # Simple keyword overlap
        rule_words = set(rule_lower.split())
        owner_words = set(owner_lower.split())
        overlap = rule_words & owner_words
        if len(overlap) >= 2 or any(
            kw in owner_lower for kw in rule_lower.split()[:3]
        ):
            relevance = min(len(overlap) / max(len(rule_words), 1), 1.0)
            matches.append((i, relevance))
    return matches


def process_owner_turn(
    owner_text: str,
    *,
    state_dir: Optional[Path] = None,
    reinforce_amount: float = 0.3,
    decay_amount: float = 0.15,
    write: bool = True,
) -> dict[str, Any]:
    """Process an owner turn and reinforce/decay engrams accordingly.

    Call this after each owner turn in the conversation loop.

    Returns a receipt dict with actions taken.
    """
    state = _state_dir(state_dir)
    engrams = _load_active_engrams(state_dir=state)
    if not engrams:
        return {"schema": SCHEMA, "actions": [], "note": "no active engrams"}

    owner_signal = _score_owner_signal(owner_text)
    matches = _match_engrams_to_turn(engrams, owner_text)

    actions = []
    for idx, relevance in matches:
        rule = engrams[idx]
        if owner_signal > 0:
            # Owner accepted — reinforce
            reward = reinforce_amount * relevance * owner_signal
            actions.append({
                "rule": rule[:120],
                "action": "reinforce",
                "reward": round(reward, 4),
                "owner_signal": round(owner_signal, 4),
                "relevance": round(relevance, 4),
            })
            # Update fitness in memory_fitness.json
            _update_fitness(state, rule, reward)
        elif owner_signal < 0:
            # Owner rejected — decay
            penalty = decay_amount * relevance * abs(owner_signal)
            actions.append({
                "rule": rule[:120],
                "action": "decay",
                "penalty": round(-penalty, 4),
                "owner_signal": round(owner_signal, 4),
                "relevance": round(relevance, 4),
            })
            _update_fitness(state, rule, -penalty)

    # Write receipt
    receipt = {
        "ts": time.time(),
        "schema": SCHEMA,
        "truth_label": "ENGRAM_FEEDBACK_RECEIPT",
        "owner_turn_snippet": owner_text[:200],
        "owner_signal": round(owner_signal, 4),
        "engrams_active": len(engrams),
        "engrams_matched": len(matches),
        "actions": actions,
    }
    if write and actions:
        append_line_locked(
            state / ENGRAM_FEEDBACK_LEDGER,
            json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n",
        )
    return receipt


def _update_fitness(state: Path, rule: str, delta: float) -> None:
    """Update the fitness of an engram in memory_fitness.json."""
    import hashlib

    fitness_path = state / MEMORY_FITNESS_FILE
    rule_hash = hashlib.sha256(rule.encode()).hexdigest()[:16]
    now = time.time()

    def _mutate(fitness: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(fitness, dict):
            fitness = {}
        traces = fitness.get("traces", {})
        if not isinstance(traces, dict):
            traces = {}

        if rule_hash not in traces:
            traces[rule_hash] = {
                "source": SCHEMA,
                "rule_preview": rule[:80],
                "fitness": 0.5,
                "reinforcements": 0,
                "decays": 0,
                "created_ts": now,
            }

        entry = traces[rule_hash]
        if not isinstance(entry, dict):
            entry = traces[rule_hash] = {
                "source": SCHEMA,
                "rule_preview": rule[:80],
                "fitness": 0.5,
                "reinforcements": 0,
                "decays": 0,
                "created_ts": now,
            }
        entry.setdefault("source", SCHEMA)
        entry.setdefault("rule_preview", rule[:80])
        entry["fitness"] = max(0.0, min(1.0, float(entry.get("fitness", 0.5)) + delta))
        entry["last_update"] = now
        if delta > 0:
            entry["reinforcements"] = int(entry.get("reinforcements", 0)) + 1
        else:
            entry["decays"] = int(entry.get("decays", 0)) + 1

        fitness["traces"] = traces
        fitness["updated_ts"] = now
        return fitness

    try:
        read_write_json_locked(fitness_path, _mutate)
    except Exception:
        fitness = {}
        if fitness_path.exists():
            try:
                fitness = json.loads(fitness_path.read_text())
            except Exception:
                fitness = {}
        fitness = _mutate(fitness)
        fitness_path.parent.mkdir(parents=True, exist_ok=True)
        fitness_path.write_text(json.dumps(fitness, indent=2, ensure_ascii=False))


def _read_fitness(state: Path) -> dict[str, Any]:
    fitness_path = state / MEMORY_FITNESS_FILE
    if not fitness_path.exists():
        return {}
    try:
        data = json.loads(read_text_locked(fitness_path, encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _tail_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if limit <= 0 or not path.exists():
        return []
    try:
        text = read_text_locked(path, encoding="utf-8", errors="replace")
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def live_memory_snapshot(
    *,
    state_dir: Optional[Path] = None,
    limit: int = 8,
    receipt_limit: int = 5,
) -> dict[str, Any]:
    """Return the live engram fitness surface for a watcher panel/CLI."""
    state = _state_dir(state_dir)
    fitness = _read_fitness(state)
    traces = fitness.get("traces", {})
    if not isinstance(traces, dict):
        traces = {}

    items: list[dict[str, Any]] = []
    for rule_hash, entry in traces.items():
        if not isinstance(entry, dict):
            continue
        if not str(entry.get("rule_preview", "")).strip():
            continue
        items.append(
            {
                "hash": rule_hash,
                "rule_preview": entry.get("rule_preview", ""),
                "fitness": round(float(entry.get("fitness", 0.5)), 4),
                "reinforcements": int(entry.get("reinforcements", 0)),
                "decays": int(entry.get("decays", 0)),
                "last_update": float(entry.get("last_update") or entry.get("created_ts") or 0.0),
            }
        )
    items.sort(key=lambda row: row["last_update"], reverse=True)
    avg = sum(row["fitness"] for row in items) / len(items) if items else 0.0
    receipts = _tail_jsonl(state / ENGRAM_FEEDBACK_LEDGER, receipt_limit)
    return {
        "ts": time.time(),
        "schema": SCHEMA,
        "truth_label": "ENGRAM_LIVE_MEMORY_SNAPSHOT",
        "state_dir": str(state),
        "trace_count": len(items),
        "avg_fitness": round(avg, 4),
        "top_traces": items[: max(0, limit)],
        "recent_receipts": receipts,
        "receipt_ledger": ENGRAM_FEEDBACK_LEDGER,
        "fitness_file": MEMORY_FITNESS_FILE,
    }


def format_live_snapshot(snapshot: dict[str, Any]) -> str:
    """Human-readable live view for `watch` while George talks."""
    lines = [
        "ENGRAM LIVE MEMORY SNAPSHOT",
        f"- traces={snapshot.get('trace_count', 0)} avg_fitness={snapshot.get('avg_fitness', 0.0):.2f}",
        f"- fitness_file={snapshot.get('fitness_file')} receipts={snapshot.get('receipt_ledger')}",
        "- top fitness traces:",
    ]
    traces = snapshot.get("top_traces") or []
    if not traces:
        lines.append("  none yet")
    for row in traces:
        preview = str(row.get("rule_preview", "")).replace("\n", " ")[:100]
        lines.append(
            "  "
            f"{row.get('fitness', 0.0):.2f} "
            f"r={row.get('reinforcements', 0)} "
            f"d={row.get('decays', 0)} "
            f"{preview}"
        )

    receipts = snapshot.get("recent_receipts") or []
    lines.append("- recent feedback receipts:")
    if not receipts:
        lines.append("  none yet")
    for row in receipts:
        actions = row.get("actions") or []
        snippet = str(row.get("owner_turn_snippet", "")).replace("\n", " ")[:80]
        lines.append(
            "  "
            f"signal={row.get('owner_signal', 0.0)} "
            f"matched={row.get('engrams_matched', 0)} "
            f"actions={len(actions)} "
            f"text={snippet}"
        )
    return "\n".join(lines)


def prune_dead_engrams(
    *,
    state_dir: Optional[Path] = None,
    min_fitness: float = 0.1,
    write: bool = True,
) -> dict[str, Any]:
    """Remove engrams that have decayed below fitness threshold.

    This is the forgetting organ. Memories that are never reinforced
    and never used should fade, not accumulate forever.
    """
    state = _state_dir(state_dir)
    fitness_path = state / MEMORY_FITNESS_FILE
    if not fitness_path.exists():
        return {"pruned": 0, "note": "no fitness data"}

    try:
        fitness = _read_fitness(state)
    except Exception:
        return {"pruned": 0, "note": "corrupt fitness file"}

    traces = fitness.get("traces", {})
    pruned = []
    for rule_hash, entry in list(traces.items()):
        if not isinstance(entry, dict) or not str(entry.get("rule_preview", "")).strip():
            continue
        if entry.get("fitness", 0.5) < min_fitness:
            pruned.append(entry.get("rule_preview", rule_hash))
            del traces[rule_hash]

    fitness["traces"] = traces
    fitness["updated_ts"] = time.time()

    if write and pruned:
        try:
            read_write_json_locked(fitness_path, lambda _old: fitness)
        except Exception:
            fitness_path.write_text(json.dumps(fitness, indent=2, ensure_ascii=False))

    return {"pruned": len(pruned), "rules": pruned}


def summary_for_prompt(*, state_dir: Optional[Path] = None) -> str:
    """One-line summary for boot/prompt injection."""
    state = _state_dir(state_dir)
    fitness_path = state / MEMORY_FITNESS_FILE
    if not fitness_path.exists():
        return "Engram feedback: no fitness data yet"
    try:
        fitness = json.loads(fitness_path.read_text())
        traces = fitness.get("traces", {})
        engram_traces = [
            t for t in traces.values()
            if isinstance(t, dict) and str(t.get("rule_preview", "")).strip()
        ]
        total = len(engram_traces)
        avg = (
            sum(t.get("fitness", 0.5) for t in engram_traces) / max(total, 1)
        )
        return f"Engram feedback: {total} tracked engrams, avg fitness {avg:.2f}"
    except Exception:
        return "Engram feedback: introspection unavailable"


def cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Engram feedback loop")
    sub = parser.add_subparsers(dest="cmd")
    p_process = sub.add_parser("process", help="Process an owner turn")
    p_process.add_argument("text", help="Owner turn text")
    p_prune = sub.add_parser("prune", help="Prune dead engrams")
    p_prune.add_argument(
        "--min-fitness", type=float, default=0.1, help="Min fitness threshold"
    )
    p_snapshot = sub.add_parser("snapshot", help="Print the live memory snapshot")
    p_snapshot.add_argument("--limit", type=int, default=8, help="Fitness rows to show")
    p_snapshot.add_argument("--json", action="store_true", help="Emit machine JSON")
    p_watch = sub.add_parser("watch", help="Watch engram fitness while owner talks")
    p_watch.add_argument("--interval", type=float, default=1.0, help="Seconds between snapshots")
    p_watch.add_argument("--ticks", type=int, default=0, help="Number of snapshots; 0 means until Ctrl-C")
    p_watch.add_argument("--limit", type=int, default=8, help="Fitness rows to show")
    sub.add_parser("summary", help="Print summary")

    args = parser.parse_args()
    cmd = args.cmd or "summary"

    if cmd == "process":
        r = process_owner_turn(args.text)
        print(json.dumps(r, indent=2))
        return 0
    if cmd == "prune":
        r = prune_dead_engrams(min_fitness=args.min_fitness)
        print(json.dumps(r, indent=2))
        return 0
    if cmd == "summary":
        print(summary_for_prompt())
        return 0
    if cmd == "snapshot":
        snap = live_memory_snapshot(limit=args.limit)
        if args.json:
            print(json.dumps(snap, indent=2, ensure_ascii=False))
        else:
            print(format_live_snapshot(snap))
        return 0
    if cmd == "watch":
        ticks = max(0, int(args.ticks))
        seen = 0
        try:
            while True:
                print(format_live_snapshot(live_memory_snapshot(limit=args.limit)), flush=True)
                seen += 1
                if ticks and seen >= ticks:
                    return 0
                time.sleep(max(0.1, float(args.interval)))
                print("", flush=True)
        except KeyboardInterrupt:
            return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(cli())
