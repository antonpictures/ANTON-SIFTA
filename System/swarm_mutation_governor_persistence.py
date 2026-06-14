"""Mutation governor allowlist persistence + self-improvement gate hook (r1021 C2)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_ALLOWLIST_NAME = "reviewer_allowlist.json"
_REVOKED_NAME = "revoked_keys.json"
_TRUTH = "MUTATION_GOVERNOR_PERSISTENCE_V1"


def _state_dir(state_dir: Path | str | None) -> Path:
    if state_dir is None:
        return Path(__file__).resolve().parents[1] / ".sifta_state"
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def load_reviewer_allowlist(*, state_dir: Path | str | None = None) -> List[str]:
    sd = _state_dir(state_dir)
    path = sd / _ALLOWLIST_NAME
    if not path.exists():
        return []
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    keys = obj.get("reviewers") if isinstance(obj, dict) else obj
    if not isinstance(keys, list):
        return []
    revoked = set(load_revoked_keys(state_dir=sd))
    return [str(k) for k in keys if str(k) not in revoked]


def load_revoked_keys(*, state_dir: Path | str | None = None) -> List[str]:
    sd = _state_dir(state_dir)
    path = sd / _REVOKED_NAME
    if not path.exists():
        return []
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    keys = obj.get("revoked") if isinstance(obj, dict) else obj
    return [str(k) for k in keys] if isinstance(keys, list) else []


def save_reviewer_allowlist(
    reviewers: List[str],
    *,
    state_dir: Path | str | None = None,
    note: str = "",
) -> Dict[str, Any]:
    sd = _state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    row = {
        "schema": _TRUTH,
        "ts": time.time(),
        "reviewers": sorted({str(r) for r in reviewers if r}),
        "note": (note or "")[:500],
    }
    (sd / _ALLOWLIST_NAME).write_text(json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")
    return row


def hydrate_mutation_governor(governor: Any, *, state_dir: Path | str | None = None) -> int:
    """Load persisted allowlist into a MutationGovernor instance."""
    for key in load_reviewer_allowlist(state_dir=state_dir):
        governor.add_reviewer(key)
    return len(governor._reviewer_allowlist)  # noqa: SLF001 — intentional wiring


def gate_self_improvement_proposal(
    proposal: Dict[str, Any],
    *,
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    """Run mutation_governor friction gate before self-improvement APPLY."""
    target = str(proposal.get("target_file") or "")
    try:
        from System.mutation_governor import MutationGovernor

        gov = MutationGovernor()
        hydrate_mutation_governor(gov, state_dir=state_dir)
        content = ""
        repo = Path(__file__).resolve().parents[1]
        path = repo / target
        if path.exists():
            content = path.read_text(encoding="utf-8", errors="replace")
        allowed = gov.allow(target, content)
        return {
            "ok": bool(allowed),
            "reason": gov.last_reject_reason or ("allowed" if allowed else "rejected"),
            "target_file": target,
            "allowlist_size": len(gov._reviewer_allowlist),  # noqa: SLF001
        }
    except Exception as exc:
        return {"ok": True, "reason": f"governor_degraded:{type(exc).__name__}", "degraded": True}