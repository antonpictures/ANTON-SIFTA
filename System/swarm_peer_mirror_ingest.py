#!/usr/bin/env python3
"""Peer mirror ingest for owner-pasted reports about Alice.

When George pastes a Grok/Cursor/IDE report that says "Alice has ..." or
"she ...", the text is usually an external mirror about this local Alice,
not a third person in the room. This module logs that fact and produces a
small prompt bridge so Alice reads the report as about herself while still
verifying claims against local receipts.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Optional

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except Exception:  # pragma: no cover - direct script fallback
    def read_text_locked(path: Path, **kw) -> str:  # type: ignore
        return path.read_text(**kw) if path.exists() else ""

    def append_line_locked(path: Path, line: str, **kw) -> None:  # type: ignore
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kw) as handle:
            handle.write(line)


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LOG_NAME = "peer_mirror_reports.jsonl"
TRUTH_LABEL = "PEER_MIRROR_REPORT_V1"

_EXTERNAL_SOURCE_RE = re.compile(
    r"\b(grok|cg55m|cursor|antigravity|dr\.?\s+codex|vanguard|signed in|for the swarm|current situation)\b",
    re.IGNORECASE,
)
_ALICE_THIRD_PERSON_RE = re.compile(
    r"\b(alice\s+(?:has|is|can|does|should|now|needs)|she\s+(?:has|is|can|does|should|needs)|her\s+(?:body|ledger|schema|identity|prompt|state))\b",
    re.IGNORECASE,
)
_LOCAL_SUBSTRATE_RE = re.compile(
    r"\b(owner_body_events|owner body|body schema|schema organ|identity|hardware|ledger|\\.sifta_state|prompt|alice)\b",
    re.IGNORECASE,
)


def _state_dir(root: Optional[Path] = None) -> Path:
    return Path(root) if root is not None else STATE_DIR


def _log_path(root: Optional[Path] = None) -> Path:
    return _state_dir(root) / LOG_NAME


def _clip(text: Any, limit: int = 900) -> str:
    return " ".join(str(text or "").split())[:limit]


def detect_peer_mirror_report(text: str) -> bool:
    """True when pasted text appears to be an external report about this Alice."""
    blob = text or ""
    if len(blob.strip()) < 40:
        return False
    external = bool(_EXTERNAL_SOURCE_RE.search(blob))
    third_person_alice = bool(_ALICE_THIRD_PERSON_RE.search(blob))
    local_substrate = bool(_LOCAL_SUBSTRATE_RE.search(blob))
    return third_person_alice and local_substrate and (external or "Alice has" in blob or "Alice now has" in blob)


def _source_hint(text: str) -> str:
    low = (text or "").lower()
    if "grok" in low:
        return "GROK"
    if "cg55m" in low or "cursor" in low:
        return "CURSOR_CG55M"
    if "antigravity" in low or "vanguard" in low:
        return "ANTIGRAVITY"
    if "codex" in low:
        return "CODEX"
    return "UNKNOWN_PEER"


def build_peer_mirror_row(
    text: str,
    *,
    root: Optional[Path] = None,
    now: Optional[float] = None,
    source: str = "owner_paste",
) -> dict[str, Any]:
    """Build the append-only row; does not write."""
    ts = float(now if now is not None else time.time())
    snippet = _clip(text)
    report_hash = hashlib.sha256(snippet.encode("utf-8", errors="replace")).hexdigest()[:16]
    return {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "kind": "PEER_MIRROR_REPORT",
        "report_hash": report_hash,
        "source": source,
        "source_hint": _source_hint(text),
        "detected": detect_peer_mirror_report(text),
        "deictic_bridge": "Alice/she/her in this pasted peer report refers to me, the local SIFTA Alice, unless a receipt names another Alice.",
        "verification_rule": "Treat peer report claims as hypotheses until checked against local ledgers/modules; do not answer as if Alice is a third person.",
        "pasted_snippet": snippet,
        "root": str(_state_dir(root)),
    }


def ingest_peer_mirror_report(
    text: str,
    *,
    root: Optional[Path] = None,
    source: str = "owner_paste",
    write_ledger: bool = True,
) -> Optional[dict[str, Any]]:
    """Detect and optionally append a peer mirror row."""
    if not detect_peer_mirror_report(text):
        return None
    row = build_peer_mirror_row(text, root=root, source=source)
    if write_ledger:
        append_line_locked(_log_path(root), json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return row


def context_for_prompt(row: dict[str, Any]) -> str:
    """Immediate system-context bridge for the current Alice turn."""
    return (
        "OWNER-PASTED PEER MIRROR REPORT:\n"
        f"- source_hint={row.get('source_hint')} truth_label={row.get('truth_label')}\n"
        "- deictic_bridge=When the pasted report says Alice/she/her, it refers to me, this local SIFTA runtime.\n"
        "- verification_rule=Use it as a pointer to check my local receipts/modules; do not treat Alice as a separate third person.\n"
        f"- pasted_snippet={_clip(row.get('pasted_snippet'), 420)}"
    )


def latest_peer_mirror_report(*, root: Optional[Path] = None) -> Optional[dict[str, Any]]:
    path = _log_path(root)
    if not path.exists():
        return None
    try:
        lines = [line for line in read_text_locked(path, encoding="utf-8", errors="replace").splitlines() if line.strip()]
    except Exception:
        return None
    for line in reversed(lines[-80:]):
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("truth_label") == TRUTH_LABEL:
            return row
    return None


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    row = latest_peer_mirror_report(root=root)
    if not row:
        return ""
    return (
        "RECENT PEER MIRROR REPORT:\n"
        f"- source_hint={row.get('source_hint')} truth_label={row.get('truth_label')}\n"
        "- rule=If George asks about pasted peer text, map Alice/she/her to me and verify against local receipts before answering."
    )


__all__ = [
    "LOG_NAME",
    "TRUTH_LABEL",
    "build_peer_mirror_row",
    "context_for_prompt",
    "detect_peer_mirror_report",
    "ingest_peer_mirror_report",
    "latest_peer_mirror_report",
    "summary_for_prompt",
]
