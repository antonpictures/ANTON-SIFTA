#!/usr/bin/env python3
"""Canonical organ registry for SIFTA.

This module gives Alice a deterministic, receipt-backed map of local organs:
module path, owned ledgers, input lanes, effector surface, and lightweight
health. It does not import or run organ modules during discovery.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import ast
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Iterable

from System.jsonl_file_lock import append_line_locked, read_text_locked, rewrite_text_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

REGISTRY_LEDGER = "organ_registry.jsonl"
ORGAN_MAP = "organ_map.json"
REGISTRY_SCHEMA = "SIFTA_ORGAN_REGISTRY_V1"

_LEDGER_NAME_RE = re.compile(r'([A-Z_]*(?:LEDGER|LOG|RECEIPT|JOURNAL|SNAPSHOT|LATEST)[A-Z_]*)\s*=\s*["\']([^"\']+)["\']')
_JSONL_RE = re.compile(r'["\']([^"\']+\.(?:jsonl|json))["\']')
_QUERY_STOPWORDS = {
    "the", "and", "for", "with", "what", "which", "that", "this", "right",
    "now", "help", "can", "alice", "organ", "organs", "use", "from",
}


@dataclass(frozen=True)
class OrganSpec:
    organ_id: str
    module: str
    module_path: str
    owned_ledgers: tuple[str, ...]
    input_lanes: tuple[str, ...]
    effector_surface: tuple[str, ...]
    health_probe: str
    capabilities: tuple[str, ...]
    status: str = "discovered"


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _sha(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _short(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").split())[:limit]


def _module_name(path: Path) -> str:
    return f"System.{path.stem}"


def _module_path(path: Path) -> str:
    try:
        return str(path.relative_to(_REPO))
    except ValueError:
        return str(path)


def _organ_id(path: Path) -> str:
    name = path.stem
    if name.startswith("swarm_"):
        name = name[len("swarm_"):]
    return name.replace("__", "_")


def _tokens(text: str) -> tuple[str, ...]:
    found = re.findall(r"[a-z][a-z0-9_]{2,}", (text or "").casefold())
    return tuple(sorted({t for t in found if t not in _QUERY_STOPWORDS}))


def _safe_parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _docstring(path: Path) -> str:
    tree = _safe_parse(path)
    if tree is None:
        return ""
    return ast.get_docstring(tree) or ""


def _owned_ledgers(path: Path) -> tuple[str, ...]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ()
    ledgers = {m.group(2) for m in _LEDGER_NAME_RE.finditer(text)}
    ledgers.update(m.group(1) for m in _JSONL_RE.finditer(text))
    return tuple(sorted(v for v in ledgers if v.endswith((".jsonl", ".json"))))


def _infer_lanes(path: Path, doc: str, ledgers: Iterable[str]) -> tuple[str, ...]:
    text = " ".join([path.stem, doc, " ".join(ledgers)]).casefold()
    lanes: set[str] = set()
    for lane, needles in {
        "vision": ("vision", "visual", "camera", "gaze", "retina", "face"),
        "audio": ("audio", "acoustic", "voice", "microphone", "broca", "wernicke"),
        "memory": ("memory", "engram", "journal", "hippocampus", "replay"),
        "economy": ("stgm", "economy", "metabolic", "wallet", "profit"),
        "tool": ("tool", "effector", "whatsapp", "calendar", "browser", "arm"),
        "identity": ("identity", "owner", "genesis", "sovereignty"),
        "training": ("lora", "dpo", "training", "dataset", "cortex", "weight"),
        "sensor": ("sensor", "ble", "gps", "window", "focus"),
    }.items():
        if any(n in text for n in needles):
            lanes.add(lane)
    return tuple(sorted(lanes or {"general"}))


def _infer_effectors(path: Path, doc: str) -> tuple[str, ...]:
    text = f"{path.stem} {doc}".casefold()
    effectors = set()
    for surface, needles in {
        "whatsapp": ("whatsapp", "message", "messenger"),
        "browser": ("browser", "webengine", "open_url"),
        "calendar": ("calendar", "schedule", "remind"),
        "camera": ("camera", "switch_camera", "saccade"),
        "model_runtime": ("ollama", "lora", "cortex", "model"),
        "filesystem": ("file", "jsonl", "ledger", "journal"),
    }.items():
        if any(n in text for n in needles):
            effectors.add(surface)
    return tuple(sorted(effectors))


def discover_organs(*, system_dir: Path | str | None = None) -> list[OrganSpec]:
    """Discover System/swarm_*.py modules as organ candidates."""

    root = Path(system_dir) if system_dir is not None else _REPO / "System"
    specs: list[OrganSpec] = []
    for path in sorted(root.glob("swarm_*.py")):
        doc = _docstring(path)
        ledgers = _owned_ledgers(path)
        lanes = _infer_lanes(path, doc, ledgers)
        text_for_caps = " ".join([path.stem, doc, " ".join(ledgers), " ".join(lanes)])
        specs.append(
            OrganSpec(
                organ_id=_organ_id(path),
                module=_module_name(path),
                module_path=_module_path(path),
                owned_ledgers=ledgers,
                input_lanes=lanes,
                effector_surface=_infer_effectors(path, doc),
                health_probe="module_exists_plus_recent_owned_ledger",
                capabilities=_tokens(text_for_caps)[:32],
            )
        )
    return specs


def _ledger_health(owned_ledgers: Iterable[str], *, state: Path, now: float) -> dict[str, Any]:
    fresh = 0
    existing = 0
    newest_age = None
    checked: list[str] = []
    for name in owned_ledgers:
        path = state / name
        checked.append(name)
        if not path.exists():
            continue
        existing += 1
        age = max(0.0, now - path.stat().st_mtime)
        newest_age = age if newest_age is None else min(newest_age, age)
        if age <= 3600:
            fresh += 1
    if not checked:
        status = "MODULE_ONLY"
        score = 0.5
    elif existing == 0:
        status = "NO_LEDGER_SEEN"
        score = 0.35
    elif fresh:
        status = "RECENT_RECEIPTS"
        score = 1.0
    else:
        status = "STALE_RECEIPTS"
        score = 0.65
    return {
        "status": status,
        "score": score,
        "owned_ledgers_checked": checked,
        "owned_ledgers_existing": existing,
        "newest_ledger_age_s": None if newest_age is None else round(newest_age, 3),
    }


def build_organ_map(
    *,
    state_dir: Path | str | None = None,
    system_dir: Path | str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Build a compact snapshot without writing append-only rows."""

    state = _state_dir(state_dir)
    ts = time.time() if now is None else float(now)
    organs = []
    for spec in discover_organs(system_dir=system_dir):
        data = asdict(spec)
        data["health"] = _ledger_health(spec.owned_ledgers, state=state, now=ts)
        organs.append(data)
    return {
        "schema": REGISTRY_SCHEMA,
        "truth_label": "ORGAN_MAP_SNAPSHOT",
        "ts": ts,
        "organ_count": len(organs),
        "organs": organs,
    }


def refresh_organ_registry(
    *,
    state_dir: Path | str | None = None,
    system_dir: Path | str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Append one registry refresh receipt and update organ_map.json."""

    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    snapshot = build_organ_map(state_dir=state, system_dir=system_dir, now=now)
    row = {
        "ts": snapshot["ts"],
        "schema": REGISTRY_SCHEMA,
        "truth_label": "ORGAN_REGISTRY_REFRESH",
        "organ_count": snapshot["organ_count"],
        "snapshot_sha256": _sha(snapshot),
    }
    append_line_locked(state / REGISTRY_LEDGER, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    rewrite_text_locked(
        state / ORGAN_MAP,
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return snapshot


def load_organ_map(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    path = _state_dir(state_dir) / ORGAN_MAP
    try:
        data = json.loads(read_text_locked(path, encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def summary_for_prompt(*, state_dir: Path | str | None = None, max_organs: int = 8) -> str:
    snapshot = load_organ_map(state_dir=state_dir)
    organs = snapshot.get("organs") if isinstance(snapshot.get("organs"), list) else []
    if not organs:
        return ""
    live = [o for o in organs if (o.get("health") or {}).get("status") == "RECENT_RECEIPTS"]
    top = sorted(organs, key=lambda o: float((o.get("health") or {}).get("score") or 0.0), reverse=True)[:max_organs]
    lines = [
        "ORGAN REGISTRY:",
        f"- organs={snapshot.get('organ_count')} recent_receipt_organs={len(live)}",
    ]
    for organ in top:
        lines.append(
            f"- {organ.get('organ_id')} lanes={','.join(organ.get('input_lanes') or [])} "
            f"health={(organ.get('health') or {}).get('status')}"
        )
    return "\n".join(lines)


__all__ = [
    "OrganSpec",
    "REGISTRY_SCHEMA",
    "build_organ_map",
    "discover_organs",
    "load_organ_map",
    "refresh_organ_registry",
    "summary_for_prompt",
]
