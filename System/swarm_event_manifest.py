"""
Generated Event-ID registry (§10.14.14).

Scans ``System/swarm_*.py`` for ``Event NNN`` tokens (docstrings + body) and
emits a JSON-serializable manifest. Intended for CI / clean-build hooks.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_EVENT_RE = re.compile(r"Event\s+(\d+)\b")


def scan_swarm_event_ids(*, repo_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    base = repo_root or Path(__file__).resolve().parent.parent
    sys_dir = base / "System"
    rows: List[Dict[str, Any]] = []
    for path in sorted(sys_dir.glob("swarm_*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        ids = sorted({int(m) for m in _EVENT_RE.findall(text)})
        if ids:
            rows.append({"file": path.name, "event_ids": ids})
    return rows


def build_event_manifest(*, repo_root: Optional[Path] = None) -> Dict[str, Any]:
    return {
        "truth_label": "EVENT_MANIFEST",
        "kind": "EVENT_MANIFEST",
        "ts": time.time(),
        "modules": scan_swarm_event_ids(repo_root=repo_root),
    }


def write_event_manifest(
    out_path: Optional[Path] = None,
    *,
    repo_root: Optional[Path] = None,
) -> Path:
    root = repo_root or Path(__file__).resolve().parent.parent
    path = out_path or (root / ".sifta_state" / "event_manifest.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_event_manifest(repo_root=root)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    import sys

    r = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    p = write_event_manifest(repo_root=r)
    print(str(p))
