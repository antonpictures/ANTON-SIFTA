#!/usr/bin/env python3
"""
System/swarm_skill_extract.py
=============================
Trace-to-skill extraction (Lane 3).

Thin wrapper around the extraction logic in swarm_skill_library.
"""

from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from System import swarm_skill_library as lib
except Exception:
    import swarm_skill_library as lib

_REPO = Path(__file__).resolve().parent.parent
_STATE = Path(__file__).resolve().parent.parent / ".sifta_state"
_RECEIPTS = _STATE / "skill_extract.jsonl"


def _state_dir() -> Path:
    cwd_state = Path.cwd() / ".sifta_state"
    return cwd_state if cwd_state.exists() else _STATE


def _receipt_path() -> Path:
    return _state_dir() / "skill_extract.jsonl"


def _log_receipt(row: Dict[str, Any]) -> None:
    state = _state_dir()
    state.mkdir(parents=True, exist_ok=True)
    row = dict(row)
    row.setdefault("type", str(row.get("action") or "SKILL_EXTRACT").upper())
    row.setdefault("ts", time.time())
    canonical = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)
    row["hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    with _receipt_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def _log_ingest_receipt(row: Dict[str, Any]) -> None:
    try:
        import swarm_skill_ingest as ingest
    except Exception:
        from System import swarm_skill_ingest as ingest  # type: ignore
    ingest._log_receipt(row)


def extract_skill_from_trace(trace: Any = None, name: str = "",
                             description: str = "", when_to_use: str = "",
                             **kwargs) -> Dict[str, Any]:
    """Turn a successful trace into a SKILL.md with full provenance."""
    if isinstance(trace, dict):
        result = lib.extract_skill_from_successful_trace(trace, **kwargs)
        _log_receipt({
            "type": "SKILL_EXTRACT",
            "action": "extract_skill_from_trace",
            "trace_id": trace.get("trace_id"),
            "result": result,
        })
        return result

    trace_hash = str(kwargs.pop("trace_hash", "") or trace or "")
    if not name:
        name = str(kwargs.pop("skill_name", "") or "trace skill")
    found = find_trace_by_hash(trace_hash)
    if found is None:
        return {"ok": False, "error": f"trace not found: {trace_hash}", "trace_hash": trace_hash}

    slug = lib._safe_skill_slug(name)
    tool = str(found.get("tool_name") or found.get("tool") or found.get("type") or "trace_action")
    desc = description or f"Repeat or adapt the successful receipted action `{tool}`."
    trigger = when_to_use or desc
    observed = json.dumps(found, indent=2, sort_keys=True, default=str)
    meta = {
        "name": slug,
        "description": desc,
        "when_to_use": trigger,
        "swimmer_type": "TRACE_LEARNED_SWIMMER",
        "action_type": "learn",
        "affect_lanes": ["SEEKING", "CARE"],
        "stgm_mint": 4.0,
        "pouw_label": slug.upper().replace("-", "_"),
        "version": "0.1.0-extracted",
        "source_trace_hash": trace_hash,
    }
    markdown = f"""{lib._frontmatter_block(meta)}

# {slug}

## Trigger
{trigger}

## Procedure
1. Match the current request to the observed successful trace.
2. Reuse the same tool boundary only when the intent still matches.
3. Execute through the SIFTA router and write a fresh receipt.

## Observed Successful Trace
Trace hash: `{trace_hash}`

```json
{observed[:5000]}
```
"""
    try:
        import swarm_skill_ingest as ingest
    except Exception:
        from System import swarm_skill_ingest as ingest  # type: ignore
    result = ingest.install_skill(markdown, source_url=f"trace:{trace_hash}")
    result = dict(result)
    result["trace_hash"] = trace_hash
    result.setdefault("slug", result.get("skill_name") or slug)
    _log_receipt({
        "type": "SKILL_EXTRACT",
        "action": "extract_skill_from_trace",
        "trace_hash": trace_hash,
        "status": result.get("status"),
        "skill_name": result.get("skill_name"),
    })
    _log_ingest_receipt({
        "type": "SKILL_EXTRACT",
        "action": "extract_skill_from_trace",
        "trace_hash": trace_hash,
        "status": result.get("status"),
        "skill_name": result.get("skill_name"),
    })
    return result


def find_trace_by_hash(hash_prefix: str) -> Optional[Dict[str, Any]]:
    """Scan all ledgers for a trace matching the hash."""
    state = _state_dir()
    if not state.exists():
        return None
    for path in sorted(state.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if hash_prefix in line:
                return json.loads(line)
    return None


def extract_skill_from_trace_ref(*, trace_file: str = "tool_router_trace.jsonl",
                                 trace_id: str = "", name: str = "",
                                 life_context: Optional[str] = None,
                                 allow_overwrite: bool = False,
                                 installed_by: str = "alice_tool_router") -> Dict[str, Any]:
    """Receipted trace->skill extraction used by the tool router.

    Delegates to swarm_skill_library.extract_skill_from_trace (the same
    behavior the router used directly) and writes a skill_extract.jsonl
    receipt so the action is traceable through this organ.
    """
    result = lib.extract_skill_from_trace(
        trace_file=trace_file,
        trace_id=trace_id,
        name=name,
        life_context=life_context,
        allow_overwrite=allow_overwrite,
        installed_by=installed_by,
    )
    _log_receipt({
        "action": "extract_skill_from_trace_ref",
        "trace_id": trace_id,
        "status": result.get("status") if isinstance(result, dict) else None,
    })
    return result
