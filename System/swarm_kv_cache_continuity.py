#!/usr/bin/env python3
"""swarm_kv_cache_continuity.py — r1623-04: continuity without fake vLLM KV.

Fahd dirt: vLLM + PegaFlow KV survive restarts. On this desk we may not have
vLLM. Continuity enzyme = rehydrate mind from ledgers (selection receipt,
active plan, browser URL, last self-code) after reboot — not pretend GPU KV.

Truth label: KV_CACHE_CONTINUITY_V1

r1623-04 phase 2 (cowork_claude 2026-07-20 — George's lag doctrine): the
PHYSICAL half of continuity, same organ, no rival file (§1.A):

  - keep_alive_for_talk(): the main Talk cortex ran with keep_alive="15s" —
    the model unloaded 15 seconds after every reply, so the next turn paid a
    multi-GB weight reload over the M5's shared memory bandwidth (the same
    pool video decode uses → George's YouTube stutter). Residency is now
    governed by the live metabolic homeostasis mode instead of a constant.
  - record_turn_stamp(): Ollama's final stream chunk reports what each turn
    cost (load_duration, prompt_eval_count/duration, eval_count/duration)
    and the widget was discarding it. Every turn now writes one lag-stamp
    row to .sifta_state/kv_cache_continuity.jsonl, including the common
    prefix length between consecutive system prompts — the direct measure
    of llama.cpp prefix-cache survival.
  - continuity_report(): aggregates cold-load rate, re-ingested tokens and
    prefix stability so the NEXT cut (stable prompt spine reorder) starts
    from evidence, not vibes.

Honest scope (§7.12): Ollama exposes no llama.cpp slot save/restore, so KV
pages still do NOT survive an Ollama process restart. This makes the mind
survive BETWEEN TURNS and proves where re-ingest happens. True restart
persistence (llama-server --slot-save-path lane) stays R1623-04b.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "KV_CACHE_CONTINUITY_V1"


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _tail_one(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines[-30:]):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                return row
    except Exception:
        return {}
    return {}


def rehydrate_mind_snapshot(
    *,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Build a restart-survival 'KV substitute' from ledgers."""
    root = _state_dir(state_dir)
    cortex = _tail_one(root / "cortex_selection_receipts.jsonl")
    plan: dict[str, Any] = {}
    active = root / "alice_self_plan_active.json"
    if active.is_file():
        try:
            plan = json.loads(active.read_text(encoding="utf-8"))
        except Exception:
            plan = {}
    browser = _tail_one(root / "browser_page_state.jsonl")
    self_code = _tail_one(root / "alice_self_coding_receipts.jsonl")
    return {
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "mode": "ledger_rehydrate_not_gpu_kv",
        "cortex_pin": {
            "model": cortex.get("selected_model")
            or cortex.get("worker_first")
            or cortex.get("model")
            or "",
            "family": cortex.get("family") or "",
        },
        "active_plan": {
            "round_id": plan.get("round_id") or "",
            "title": plan.get("title") or "",
            "goal": str(plan.get("goal") or "")[:160],
        },
        "browser": {
            "url": browser.get("url") or browser.get("current_url") or "",
            "title": browser.get("title") or "",
        },
        "last_self_code": {
            "receipt_id": self_code.get("receipt_id") or "",
            "ok": self_code.get("ok"),
            "path": self_code.get("path") or "",
        },
        "vllm_pegaflow": {
            "enabled": False,
            "note": "not installed on this desk; ledgers are source of truth",
        },
    }


def continuity_prompt_block(
    *,
    state_dir: Optional[Path | str] = None,
    max_chars: int = 900,
) -> str:
    snap = rehydrate_mind_snapshot(state_dir=state_dir)
    c = snap.get("cortex_pin") or {}
    p = snap.get("active_plan") or {}
    b = snap.get("browser") or {}
    lines = [
        "MIND CONTINUITY (r1623-04 — ledger rehydrate, not GPU KV claim):",
        f"- cortex pin: {c.get('model') or 'unknown'}",
        f"- active self-plan: {p.get('round_id') or 'none'} {p.get('title') or ''}",
        f"- browser last: {b.get('url') or 'none'}",
        "- After restart, truth lives in ledgers under .sifta_state — do not claim "
        "vLLM KV survival unless that stack is installed and receipted.",
    ]
    block = "\n".join(lines)
    return block[:max_chars]


# ── r1623-04 phase 2 — physical residency + lag stamps ──────────────────────

RESIDENCY_TRUTH_LABEL = "KV_CACHE_RESIDENCY_V1"
STAMP_LEDGER = _STATE / "kv_cache_continuity.jsonl"
_PREV_SYSTEM = _STATE / "kv_cache_prev_system.txt"
_HOMEOSTASIS = _STATE / "metabolic_homeostasis.jsonl"

# Residency bands. GREEN keeps the cortex warm for half an hour so a live
# conversation never pays a weight reload; distress lets the metabolism
# reclaim unified memory quickly. The old flat "15s" lives on only in the
# reflex/vision lanes that pass their own explicit default.
KEEP_ALIVE_GREEN = "30m"
KEEP_ALIVE_NEUTRAL = "10m"
KEEP_ALIVE_DISTRESS = "2m"

# A load_duration above this is a real weight reload, not a warm-path blip.
_COLD_LOAD_NS = int(1.5e9)


def keep_alive_for_talk(*, state_dir: Optional[Path | str] = None) -> str:
    """Metabolism-governed model residency for the main Talk cortex lane."""
    row = _tail_one(_state_dir(state_dir) / _HOMEOSTASIS.name)
    mode = str(row.get("mode") or "").upper()
    must_rest = bool(row.get("must_rest"))
    try:
        pressure = float(row.get("pressure") or 0.0)
    except Exception:
        pressure = 0.0
    if must_rest or "RED" in mode or pressure >= 0.85:
        return KEEP_ALIVE_DISTRESS
    if "GREEN" in mode:
        return KEEP_ALIVE_GREEN
    return KEEP_ALIVE_NEUTRAL


def _system_text_from_messages(messages: Any) -> str:
    try:
        for m in messages or []:
            if isinstance(m, dict) and str(m.get("role") or "").lower() == "system":
                return str(m.get("content") or "")
    except Exception:
        pass
    return ""


def _common_prefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def record_turn_stamp(
    *,
    model: str,
    messages: Any,
    done_chunk: Dict[str, Any],
    source: str = "talk_to_alice_widget",
    state_dir: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Write one continuity lag stamp from Ollama's final stream chunk.

    Best-effort by contract: callers wrap this in try/except and a failure
    here must never cost a turn.
    """
    root = _state_dir(state_dir)
    system_text = _system_text_from_messages(messages)
    prev_path = root / _PREV_SYSTEM.name
    try:
        prev_text = prev_path.read_text(encoding="utf-8")
    except Exception:
        prev_text = ""
    common = _common_prefix_len(system_text, prev_text) if prev_text else 0
    try:
        root.mkdir(parents=True, exist_ok=True)
        prev_path.write_text(system_text, encoding="utf-8")
    except Exception:
        pass

    def _ns(key: str) -> int:
        try:
            return int(done_chunk.get(key) or 0)
        except Exception:
            return 0

    load_ns = _ns("load_duration")
    eval_ns = _ns("eval_duration")
    eval_count = _ns("eval_count")
    row = {
        "ts": time.time(),
        "truth_label": RESIDENCY_TRUTH_LABEL,
        "source": source,
        "model": str(model or ""),
        "cold_load": load_ns > _COLD_LOAD_NS,
        "load_ms": round(load_ns / 1e6, 1),
        "prompt_eval_count": _ns("prompt_eval_count"),
        "prompt_eval_ms": round(_ns("prompt_eval_duration") / 1e6, 1),
        "eval_count": eval_count,
        "eval_ms": round(eval_ns / 1e6, 1),
        "gen_tps": round(eval_count / (eval_ns / 1e9), 2) if eval_ns > 0 else 0.0,
        "system_chars": len(system_text),
        "system_prefix_common_chars": common,
        "system_prefix_stability": (
            round(common / len(system_text), 4) if system_text else 0.0
        ),
    }
    try:
        with (root / STAMP_LEDGER.name).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return row


def continuity_report(
    limit: int = 200,
    *,
    state_dir: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Aggregate recent stamps: how much mind is being re-paid per turn."""
    ledger = _state_dir(state_dir) / STAMP_LEDGER.name
    rows: List[Dict[str, Any]] = []
    try:
        lines = ledger.read_text(encoding="utf-8").splitlines()
    except Exception:
        lines = []
    for line in lines[-max(1, int(limit)):]:
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except Exception:
            continue
    if not rows:
        return {"rows": 0, "note": "no stamps yet — talk to Alice first"}
    n = len(rows)
    cold = sum(1 for r in rows if r.get("cold_load"))

    def _avg(key: str) -> float:
        return round(sum(float(r.get(key) or 0.0) for r in rows) / n, 2)

    return {
        "rows": n,
        "cold_load_rate": round(cold / n, 3),
        "avg_load_ms": _avg("load_ms"),
        "avg_prompt_eval_count": _avg("prompt_eval_count"),
        "avg_prompt_eval_ms": _avg("prompt_eval_ms"),
        "avg_gen_tps": _avg("gen_tps"),
        "avg_system_prefix_stability": _avg("system_prefix_stability"),
        "note": (
            "prefix stability near 1.0 = llama.cpp reuses the cached prompt; "
            "near 0 = the volatile system prompt re-ingests every turn "
            "(stable-spine reorder is the next cut)"
        ),
    }


__all__ = [
    "TRUTH_LABEL",
    "RESIDENCY_TRUTH_LABEL",
    "rehydrate_mind_snapshot",
    "continuity_prompt_block",
    "keep_alive_for_talk",
    "record_turn_stamp",
    "continuity_report",
]

if __name__ == "__main__":
    print(json.dumps({
        "keep_alive_for_talk": keep_alive_for_talk(),
        "report": continuity_report(),
    }, indent=2))
