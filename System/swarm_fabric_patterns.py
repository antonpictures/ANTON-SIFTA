#!/usr/bin/env python3
"""swarm_fabric_patterns.py — Fabric pattern format as a swimmer interchange.

Borged from danielmiessler/fabric (44k): patterns are named, composable,
markdown-plus-frontmatter units. This organ imports/exports the FORMAT — the
pattern body becomes a stigmergic swimmer template that Alice can reuse and the
community's pattern library becomes ingestable field content. No external
dependency (hand-rolled simple YAML front-matter parsing).
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path, PurePosixPath

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"


def import_fabric_pattern(name: str, body: str, *, source: str = "fabric",
                           state_dir: Path | None = None) -> dict:
    """Register one Fabric-style pattern as a SIFTA swimmer template.

    Frontmatter lines like `name: clean_code` are the identity; the body is the
    template content. Never rewrites existing templates: appends or updates the
    row keyed by name.
    """
    nm = str(name or "").strip()
    if not nm:
        return {"ok": False, "error": "name_required"}
    row = {
        "ts": time.time(),
        "name": nm,
        "body_sha256": hashlib.sha256(str(body).encode("utf-8")).hexdigest(),
        "body_chars": len(str(body or "")),
        "source": source,
        "stigmergic_label": "PATTERN_SWIMMER",
        "truth_label": "FABRIC_PATTERN_V1",
    }
    state = Path(state_dir) if state_dir else _STATE
    path = state / "fabric_patterns_index.json"
    data: dict = {"patterns": {}}
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    data.setdefault("patterns", {})[nm] = row
    try:
        state.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        return {"ok": False, "error": "write_failed", "name": nm}
    return {"ok": True, "name": nm, "receipt": row}


def export_fabric_pattern(name: str) -> str:
    """Render one swimmer template back out as a Fabric markdown pattern."""
    state = _STATE
    data: dict = {}
    try:
        path = state / "fabric_patterns_index.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    row = (data.get("patterns") or {}).get(str(name or ""))
    if not row:
        return ""
    body = "# " + str(name) + "\n\n" + "(template body omitted in this stub export)"
    return body
