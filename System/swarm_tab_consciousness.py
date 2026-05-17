#!/usr/bin/env python3
"""
System/swarm_tab_consciousness.py
=================================

Opt-in Safari Tab Consciousness organ for the local SIFTA organism.

This is a Python-first sense organ, not a browser escape hatch. It is inert by
default, writes append-only receipts when activated, and records Safari tab
titles only unless the owner explicitly enables URL collection.
"""
from __future__ import annotations

import json
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked, read_write_json_locked

try:
    from System.swarm_kernel_identity import owner_silicon
except Exception:  # pragma: no cover - defensive for standalone imports
    def owner_silicon() -> str:  # type: ignore
        return "UNKNOWN"


MODULE_VERSION = "2026-05-15.tab-consciousness.hardened.v1"
STATE_SCHEMA = "SIFTA_TAB_CONSCIOUSNESS_STATE_V1"
TRACE_SCHEMA = "SIFTA_TAB_CONSCIOUSNESS_TRACE_V1"

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE_DIR = _REPO / ".sifta_state"
_MAX_TABS = 80
_MAX_TITLE_CHARS = 220
_MAX_URL_CHARS = 600
_MIN_COST_TRACE = 0.0001


@dataclass
class TabConsciousnessState:
    schema: str = STATE_SCHEMA
    module_version: str = MODULE_VERSION
    active: bool = False
    activated_at: Optional[float] = None
    activated_by: str = "unknown"
    cost_per_hour: float = 0.65
    collect_urls: bool = False
    last_update: Optional[float] = None
    last_cost_at: Optional[float] = None
    accrued_stgm_cost: float = 0.0
    last_error: str = ""
    last_trace_id: str = ""


def _state_dir(state_dir: Optional[Path] = None) -> Path:
    root = Path(state_dir) if state_dir is not None else _DEFAULT_STATE_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _state_file(state_dir: Optional[Path] = None) -> Path:
    return _state_dir(state_dir) / "tab_consciousness_state.json"


def _trace_file(state_dir: Optional[Path] = None) -> Path:
    return _state_dir(state_dir) / "tab_consciousness.jsonl"


def _coerce_state(data: Dict[str, Any]) -> TabConsciousnessState:
    allowed = set(TabConsciousnessState.__dataclass_fields__)
    cleaned = {k: data.get(k) for k in allowed if k in data}
    state = TabConsciousnessState(**cleaned)
    state.schema = STATE_SCHEMA
    state.module_version = MODULE_VERSION
    state.active = bool(state.active)
    state.activated_by = str(state.activated_by or "unknown")[:80]
    state.cost_per_hour = max(0.0, min(100.0, float(state.cost_per_hour or 0.0)))
    state.collect_urls = bool(state.collect_urls)
    state.accrued_stgm_cost = max(0.0, float(state.accrued_stgm_cost or 0.0))
    state.last_error = str(state.last_error or "")[:500]
    state.last_trace_id = str(state.last_trace_id or "")[:80]
    return state


def _load_state(state_dir: Optional[Path] = None) -> TabConsciousnessState:
    return _coerce_state(_read_state_dict(state_dir))


def _read_state_dict(state_dir: Optional[Path] = None) -> Dict[str, Any]:
    path = _state_file(state_dir)
    if not path.exists():
        return asdict(TabConsciousnessState())
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return asdict(TabConsciousnessState(last_error="state_json_parse_failed"))
    return data if isinstance(data, dict) else asdict(TabConsciousnessState())


def _update_state(
    updater,
    *,
    state_dir: Optional[Path] = None,
) -> TabConsciousnessState:
    def _locked(data: Dict[str, Any]) -> Dict[str, Any]:
        state = _coerce_state(data)
        updated = updater(state)
        if isinstance(updated, TabConsciousnessState):
            state = updated
        return asdict(state)

    return _coerce_state(read_write_json_locked(_state_file(state_dir), _locked))


def _write_trace(row: Dict[str, Any], *, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    out = {
        "ts": float(row.get("ts") or time.time()),
        "trace_id": str(row.get("trace_id") or uuid.uuid4()),
        "schema": TRACE_SCHEMA,
        "module_version": MODULE_VERSION,
        "node_serial": owner_silicon(),
        **row,
    }
    out["trace_id"] = str(out["trace_id"])
    append_line_locked(_trace_file(state_dir), json.dumps(out, ensure_ascii=False, sort_keys=True) + "\n")
    return out


def _clean_text(value: Any, max_chars: int) -> str:
    text = " ".join(str(value or "").replace("\x00", "").split())
    return text[:max_chars]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _jxa_script(collect_urls: bool) -> str:
    collect = "true" if collect_urls else "false"
    return f"""
const collectUrls = {collect};
function clean(v) {{
  return String(v || "").replace(/\\u0000/g, "").replace(/\\s+/g, " ").trim();
}}
function main() {{
try {{
  const se = Application("System Events");
  if (!se.processes.byName("Safari").exists()) {{
    return JSON.stringify({{ok: false, status: "safari_not_running", tabs: []}});
  }}
  const safari = Application("Safari");
  const wins = safari.windows();
  const tabs = [];
  for (let wi = 0; wi < wins.length; wi++) {{
    const winTabs = wins[wi].tabs();
    for (let ti = 0; ti < winTabs.length; ti++) {{
      const tab = winTabs[ti];
      const row = {{
        window_index: wi + 1,
        tab_index: ti + 1,
        title: clean(tab.name())
      }};
      if (collectUrls) {{
        row.url = clean(tab.url());
      }} else {{
        row.url = "";
      }}
      tabs.push(row);
    }}
  }}
  return JSON.stringify({{ok: true, status: "ok", tabs}});
}} catch (err) {{
  return JSON.stringify({{ok: false, status: "osascript_error", error: clean(err), tabs: []}});
}}
}}
main();
""".strip()


def probe_safari_tabs(
    *,
    collect_urls: bool = False,
    timeout_s: float = 4.0,
) -> Dict[str, Any]:
    """Return a receipt-safe Safari tab probe result."""
    try:
        proc = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", _jxa_script(collect_urls)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "timeout", "tabs": [], "error": "osascript_timeout"}
    except Exception as exc:
        return {"ok": False, "status": "exception", "tabs": [], "error": f"{type(exc).__name__}: {exc}"}

    if proc.returncode != 0:
        return {
            "ok": False,
            "status": "osascript_returncode",
            "tabs": [],
            "error": _clean_text(proc.stderr or proc.stdout, 500),
        }

    try:
        payload = json.loads((proc.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        return {
            "ok": False,
            "status": "json_parse_failed",
            "tabs": [],
            "error": _clean_text(proc.stdout, 500),
        }

    raw_tabs = payload.get("tabs") if isinstance(payload, dict) else []
    tabs: List[Dict[str, Any]] = []
    if isinstance(raw_tabs, list):
        for item in raw_tabs[:_MAX_TABS]:
            if not isinstance(item, dict):
                continue
            tabs.append(
                {
                    "window_index": _safe_int(item.get("window_index"), 0),
                    "tab_index": _safe_int(item.get("tab_index"), 0),
                    "title": _clean_text(item.get("title"), _MAX_TITLE_CHARS),
                    "url": _clean_text(item.get("url"), _MAX_URL_CHARS) if collect_urls else "",
                }
            )
    return {
        "ok": bool(payload.get("ok")) if isinstance(payload, dict) else False,
        "status": _clean_text(payload.get("status", "unknown") if isinstance(payload, dict) else "bad_payload", 80),
        "tabs": tabs,
        "tab_count": len(tabs),
        "collect_urls": bool(collect_urls),
        "error": _clean_text(payload.get("error", "") if isinstance(payload, dict) else "", 500),
    }


def activate(
    activated_by: str = "unknown",
    *,
    collect_urls: Optional[bool] = None,
    state_dir: Optional[Path] = None,
    now: Optional[float] = None,
) -> bool:
    ts = float(time.time() if now is None else now)

    def _updater(state: TabConsciousnessState) -> TabConsciousnessState:
        if collect_urls is not None:
            state.collect_urls = bool(collect_urls)
        if not state.active:
            state.active = True
            state.activated_at = ts
            state.last_cost_at = ts
            state.activated_by = _clean_text(activated_by, 80) or "unknown"
        state.last_update = ts
        state.last_error = ""
        return state

    state = _update_state(_updater, state_dir=state_dir)
    trace = _write_trace(
        {
            "type": "TAB_CONSCIOUSNESS_ACTIVATED",
            "ok": True,
            "status": "active",
            "activated_by": state.activated_by,
            "cost_per_hour": state.cost_per_hour,
            "collect_urls": state.collect_urls,
            "truth_note": "Opt-in Safari tab sense activated. URL collection remains off unless collect_urls is true.",
            "ts": ts,
        },
        state_dir=state_dir,
    )
    _update_state(lambda s: _set_last_trace(s, trace["trace_id"]), state_dir=state_dir)
    return True


def _set_last_trace(state: TabConsciousnessState, trace_id: str) -> TabConsciousnessState:
    state.last_trace_id = str(trace_id)
    return state


def deactivate(*, state_dir: Optional[Path] = None, now: Optional[float] = None) -> bool:
    ts = float(time.time() if now is None else now)
    state_before = _load_state(state_dir)
    cost = burn_active_cost(state_dir=state_dir, now=ts)

    def _updater(state: TabConsciousnessState) -> TabConsciousnessState:
        state.active = False
        state.last_update = ts
        state.last_cost_at = ts
        return state

    state = _update_state(_updater, state_dir=state_dir)
    session_seconds = 0.0
    if state_before.activated_at is not None:
        session_seconds = max(0.0, ts - float(state_before.activated_at))
    trace = _write_trace(
        {
            "type": "TAB_CONSCIOUSNESS_DEACTIVATED",
            "ok": True,
            "status": "inactive",
            "session_seconds": round(session_seconds, 3),
            "final_cost": round(float(cost), 6),
            "accrued_stgm_cost": round(state.accrued_stgm_cost, 6),
            "ts": ts,
        },
        state_dir=state_dir,
    )
    _update_state(lambda s: _set_last_trace(s, trace["trace_id"]), state_dir=state_dir)
    return True


def configure(
    *,
    cost_per_hour: Optional[float] = None,
    collect_urls: Optional[bool] = None,
    changed_by: str = "unknown",
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    def _updater(state: TabConsciousnessState) -> TabConsciousnessState:
        if cost_per_hour is not None:
            state.cost_per_hour = max(0.0, min(100.0, float(cost_per_hour)))
        if collect_urls is not None:
            state.collect_urls = bool(collect_urls)
        state.last_update = time.time()
        return state

    state = _update_state(_updater, state_dir=state_dir)
    trace = _write_trace(
        {
            "type": "TAB_CONSCIOUSNESS_CONFIGURED",
            "ok": True,
            "status": "configured",
            "changed_by": _clean_text(changed_by, 80),
            "cost_per_hour": state.cost_per_hour,
            "collect_urls": state.collect_urls,
        },
        state_dir=state_dir,
    )
    _update_state(lambda s: _set_last_trace(s, trace["trace_id"]), state_dir=state_dir)
    return asdict(state)


def is_active(*, state_dir: Optional[Path] = None) -> bool:
    return _load_state(state_dir).active


def get_status(*, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    return asdict(_load_state(state_dir))


def get_current_safari_tabs(collect_urls: bool = False) -> List[Dict[str, Any]]:
    return list(probe_safari_tabs(collect_urls=collect_urls).get("tabs") or [])


def write_current_state(
    reason: str = "periodic",
    *,
    state_dir: Optional[Path] = None,
    now: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    ts = float(time.time() if now is None else now)
    state = _load_state(state_dir)
    if not state.active:
        return None

    probe = probe_safari_tabs(collect_urls=state.collect_urls)
    row = _write_trace(
        {
            "type": "TAB_CONSCIOUSNESS_UPDATE",
            "ok": bool(probe.get("ok")),
            "status": probe.get("status", "unknown"),
            "reason": _clean_text(reason, 120),
            "tab_count": int(probe.get("tab_count") or 0),
            "tabs": probe.get("tabs") or [],
            "collect_urls": state.collect_urls,
            "error": _clean_text(probe.get("error", ""), 500),
            "ts": ts,
        },
        state_dir=state_dir,
    )

    def _updater(current: TabConsciousnessState) -> TabConsciousnessState:
        current.last_update = ts
        current.last_error = _clean_text(probe.get("error", ""), 500)
        current.last_trace_id = row["trace_id"]
        return current

    _update_state(_updater, state_dir=state_dir)
    return row


def burn_active_cost(*, state_dir: Optional[Path] = None, now: Optional[float] = None) -> float:
    ts = float(time.time() if now is None else now)
    charged = 0.0

    def _updater(state: TabConsciousnessState) -> TabConsciousnessState:
        nonlocal charged
        if not state.active or state.activated_at is None:
            return state
        last = float(state.last_cost_at if state.last_cost_at is not None else state.activated_at)
        elapsed = max(0.0, ts - last)
        charged = (elapsed / 3600.0) * float(state.cost_per_hour)
        if charged > 0:
            state.accrued_stgm_cost += charged
            state.last_cost_at = ts
            state.last_update = ts
        return state

    state = _update_state(_updater, state_dir=state_dir)
    if charged >= _MIN_COST_TRACE:
        trace = _write_trace(
            {
                "type": "TAB_CONSCIOUSNESS_STGM_COST",
                "ok": True,
                "status": "charged",
                "cost": round(charged, 6),
                "rate": state.cost_per_hour,
                "accrued_stgm_cost": round(state.accrued_stgm_cost, 6),
                "ts": ts,
            },
            state_dir=state_dir,
        )
        _update_state(lambda s: _set_last_trace(s, trace["trace_id"]), state_dir=state_dir)
    return float(charged)


__all__ = [
    "TabConsciousnessState",
    "activate",
    "burn_active_cost",
    "configure",
    "deactivate",
    "get_current_safari_tabs",
    "get_status",
    "is_active",
    "probe_safari_tabs",
    "write_current_state",
]
