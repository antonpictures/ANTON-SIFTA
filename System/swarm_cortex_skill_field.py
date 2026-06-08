#!/usr/bin/env python3
"""swarm_cortex_skill_field.py — per-cortex OBSERVED skills from field receipts. r641.

George 2026-06-06: "CLINE IS BLIND DOES NOT KNOW HOW TO USE TOOLS … EVERY CORTEX IS A
BIT DIFFERENT … THEY ARE DIFFERENT OAUTH DIFFERENT CLI, EVERY CORTEX AND ARM HAVE
THEIR OWN SETTINGS :) STIGMERGIC SKILLS LAYER :))"

`swarm_cortex_capabilities` holds the STATIC prior (what a model card/`ollama show`
claims). This sublayer holds the LIVED truth: per cortex, per skill, what actually
happened in the field — tool use that worked or didn't, searches that executed,
timeouts, empty outputs, gags. The router and the prompt read the OBSERVED rows so
Alice stops assuming every brain works the same. Pheromone register: counts decay
by recency window, never banned — a cortex that failed tool-use 4/4 is not deleted,
it is routed around and retried when its OAuth/CLI settings change.

No-duplicate boundary:
* NOT the generic SIFTA skill layer (`swarm_skill_library`, r549).
* NOT per-website browser habits/relearn (`swarm_browser_site_playbook`, r384).
* NOT diagnostic-arm selection/outcome (`swarm_parallel_cortex_arm_diagnostics`, r337).
* NOT browser skill teaching/SFT rows (`swarm_browser_skill_teaching`, r640).
This file is only the per-cortex observed-skill field that those organs and routers
can read.

Ledger: .sifta_state/cortex_skill_observations.jsonl (append-only).
Seed: `backfill_from_field()` scans EXISTING ledgers (cortex_timeout_recovery,
cortex_route_receipts) so the field is not empty on day one.
No canonical STGM is minted or spent by any reader here.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "cortex_skill_observations.jsonl"

SKILLS = (
    "tool_use",          # emitted a usable tool call / effector trigger
    "search_execute",    # owner search command actually executed
    "vision",            # described real pixels (not OCR-only fallback)
    "turn_completion",   # produced a non-empty reply within timeout
    "scaffold_clean",    # no thinking-leak/meta scaffold in the reply
)

DUPLICATE_BOUNDARY: Dict[str, Any] = {
    "role": "per_cortex_lived_skill_observation_overlay",
    "extends_existing_skill_ecology": True,
    "not_a_rival_to": {
        "generic_stigmergic_skill_layer": {
            "path": "System/swarm_skill_library.py",
            "round": "r549",
            "scope": "market/SIFTA skill -> swimmer -> organ -> organism contract",
        },
        "app_help_skill_consciousness": {
            "path": "System/swarm_app_help_skills.py",
            "round": "r549",
            "scope": "app-focused skill consciousness views and help surfaces",
        },
        "browser_site_playbook": {
            "path": "System/swarm_browser_site_playbook.py",
            "round": "r384",
            "scope": "per-site browser habits, category skills, and relearn-on-site-change",
        },
        "parallel_diagnostic_arm_learning": {
            "path": "System/swarm_parallel_cortex_arm_diagnostics.py",
            "round": "r337",
            "scope": "which outside arm diagnoses which stalled cortex/fault best",
        },
        "browser_skill_teaching": {
            "path": "System/swarm_browser_skill_teaching.py",
            "round": "r640",
            "scope": "Alice Browser procedural inventory, working prompt card, and SFT teaching pairs",
        },
    },
    "ledger": "cortex_skill_observations.jsonl",
}


def observe(cortex: str, skill: str, ok: bool, note: str = "",
            *, state_dir: Path | str | None = None) -> Dict[str, Any]:
    """Append one observed skill row for a cortex. The field learns; nothing is banned."""
    row = {
        "ts": time.time(),
        "kind": "CORTEX_SKILL_OBSERVATION",
        "cortex": str(cortex or "").strip(),
        "skill": str(skill or "").strip(),
        "ok": bool(ok),
        "note": str(note or "")[:300],
    }
    path = Path(state_dir) / _LEDGER.name if state_dir else _LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def _rows(path: Path | None = None, tail: int = 2000, *, raw: bool = False) -> List[Dict[str, Any]]:
    """raw=False filters to observation rows (cortex+skill); raw=True returns any dict rows
    (r646 fix: backfill sources like cortex_timeout_recovery carry `model`, not cortex/skill —
    the filtered reader silently seeded zero)."""
    p = path or _LEDGER
    out: List[Dict[str, Any]] = []
    try:
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]:
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if isinstance(r, dict) and (raw or (r.get("cortex") and r.get("skill"))):
                out.append(r)
    except Exception:
        pass
    return out


def skill_profile(cortex: str = "", *, max_age_s: float = 7 * 86400.0,
                  path: Path | None = None) -> Dict[str, Dict[str, Any]]:
    """Aggregate observed rows: {cortex: {skill: {ok, fail, rate, last_ts}}}.
    Recency window = soft pheromone decay (old rows fall out; nothing is banned)."""
    now = time.time()
    agg: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for r in _rows(path):
        if now - float(r.get("ts") or 0) > max_age_s:
            continue
        c = str(r["cortex"])
        if cortex and c != cortex:
            continue
        s = str(r["skill"])
        cell = agg[c].setdefault(s, {"ok": 0, "fail": 0, "last_ts": 0.0})
        cell["ok" if r.get("ok") else "fail"] += 1
        cell["last_ts"] = max(cell["last_ts"], float(r.get("ts") or 0))
    for c in agg:
        for s, cell in agg[c].items():
            total = cell["ok"] + cell["fail"]
            cell["rate"] = round(cell["ok"] / total, 3) if total else None
    return dict(agg[cortex]) if cortex else dict(agg)


def cortex_skill_block(max_chars: int = 900, *, path: Path | None = None) -> str:
    """Compact prompt card: each cortex's lived skill rates. Empty field = honest line."""
    prof = skill_profile(path=path)
    if not prof:
        return ("CORTEX SKILL FIELD: no observations yet — every cortex is different "
                "(own OAuth, own CLI, own settings); I learn each one from receipts.")
    lines = ["CORTEX SKILL FIELD (observed, 7d, from my own receipts — cortexes are NOT interchangeable):"]
    for c in sorted(prof):
        cells = []
        for s in SKILLS:
            cell = prof[c].get(s)
            if not cell:
                continue
            cells.append(f"{s} {cell['ok']}/{cell['ok'] + cell['fail']}")
        if cells:
            lines.append(f"- {c.split('/')[-1][:40]}: " + ", ".join(cells))
    block = "\n".join(lines)
    return block[: max(200, int(max_chars))]


def duplicate_boundary() -> Dict[str, Any]:
    """Return the no-duplicate map for doctors and matrix readers.

    George caught the risk: "stigmergic skills layer" already exists in several
    scoped organs. This function makes the boundary machine-readable so future
    doctors extend the right organ instead of creating another rival.
    """
    return json.loads(json.dumps(DUPLICATE_BOUNDARY))


def backfill_from_field(*, state_dir: Path | str | None = None) -> Dict[str, int]:
    """Seed observations from ledgers that already exist (no duplication of live writes:
    rows are tagged note='backfill' and the scan is idempotent per source row ts)."""
    state = Path(state_dir) if state_dir else _STATE
    seeded = {"timeouts": 0, "routes": 0}
    existing = {(r.get("note"), r.get("cortex"), r.get("skill")) for r in _rows(state / _LEDGER.name)}
    # 1) cortex timeout recoveries -> turn_completion failures for the stalled cortex
    for r in _rows(state / "cortex_timeout_recovery.jsonl", tail=400, raw=True):
        model = str(r.get("model") or "")
        ts = r.get("ts")
        note = f"backfill:timeout:{ts}"
        if model and (note, model, "turn_completion") not in existing:
            observe(model, "turn_completion", False, note, state_dir=state)
            seeded["timeouts"] += 1
    # 2) route receipts -> successful completions where recorded ok
    for r in _rows(state / "cortex_route_receipts.jsonl", tail=400, raw=True):
        model = str(r.get("chosen") or r.get("model") or "")
        ts = r.get("ts")
        ok = bool(r.get("ok", True))
        note = f"backfill:route:{ts}"
        if model and (note, model, "turn_completion") not in existing:
            observe(model, "turn_completion", ok, note, state_dir=state)
            seeded["routes"] += 1
    return seeded


__all__ = [
    "SKILLS",
    "DUPLICATE_BOUNDARY",
    "observe",
    "skill_profile",
    "cortex_skill_block",
    "duplicate_boundary",
    "backfill_from_field",
]
