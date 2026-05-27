"""System/swarm_cortex_raw_archive.py
=====================================

Dual-lane ledger for Alice's cortex. Round 43 doctrine, 2026-05-26.

Architect verbatim (paraphrased into the rule):
    "raw intent must be preserved as unique source-of-truth, and filtered
    variants should be separate derivatives, not replacements."

What this organ does
--------------------
Every cortex completion is captured RAW before any filter touches it.
The filter chain that runs afterward (scrubber, bowel, strip, reality
gate, gag-rule) emits one row per transform naming the rule_id and the
before/after deltas — so we can always reconstruct what Alice's cortex
actually said and exactly how the gates shaped it.

The conversation ledger continues to display the DELIVERED text, but it
carries an `utterance_id` cross-reference back to the raw row.

Two ledgers, one truth chain:
    .sifta_state/alice_cortex_raw.jsonl              — RAW completions
    .sifta_state/alice_cortex_transform_chain.jsonl  — every gate's diff

Public API
----------
record_raw(text, *, cortex_model, prior_user_text="", input_source="cortex",
           state_root=None) -> dict
    Append a raw cortex completion. Returns
    {"utterance_id": <str>, "raw_hash": <str>, "ts": <float>}.

record_transform(utterance_id, *, gate, rule_ids, before, after,
                 changed, state_root=None) -> str
    Append one transform row. Returns the receipt id for that step.

reconstruct(utterance_id, *, state_root=None) -> dict
    Read all transform rows for an utterance + the raw row and return
    the full chain in order, so the owner can see precisely what each
    gate did.

Doctrine: this module is the storage organ for the architect rule. It
is intentionally tiny — write-only ledgers, no hidden state, no
mutation of pre-existing rows. Append-only is the truth.

Author: claude-opus-4-6 (Cowork, HEAD), 2026-05-26.
Predator gate: ide_stigmergic_trace rows with intent prefix r43-.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"

RAW_LEDGER_NAME = "alice_cortex_raw.jsonl"
CHAIN_LEDGER_NAME = "alice_cortex_transform_chain.jsonl"

TRUTH_LABEL_RAW = "ALICE_CORTEX_RAW_V1"
TRUTH_LABEL_CHAIN = "ALICE_CORTEX_TRANSFORM_CHAIN_V1"


def _state_root(state_root: Optional[Path] = None) -> Path:
    return Path(state_root) if state_root else _DEFAULT_STATE


def _hash_text(text: str) -> str:
    """Stable short hash of the raw cortex output."""
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()[:24]


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    """Append-only, self-healing on missing trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = ""
    try:
        if path.exists() and path.stat().st_size > 0:
            with path.open("rb") as fh:
                fh.seek(-1, 2)
                if fh.read(1) != b"\n":
                    prefix = "\n"
    except OSError:
        pass
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(path, prefix + json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        with path.open("a", encoding="utf-8") as f:
            f.write(prefix + json.dumps(row, ensure_ascii=False) + "\n")


def record_raw(
    text: str,
    *,
    cortex_model: str,
    prior_user_text: str = "",
    input_source: str = "cortex",
    state_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Capture the raw cortex completion. Call this BEFORE any filter
    chain touches the text. Returns the utterance_id that downstream
    transform rows must cite."""
    text = text or ""
    utt_id = uuid.uuid4().hex[:16]
    raw_hash = _hash_text(text)
    ts = time.time()
    row = {
        "ts": ts,
        "utterance_id": utt_id,
        "raw_hash": raw_hash,
        "cortex_model": str(cortex_model or "")[:120],
        "input_source": str(input_source or "")[:40],
        "prior_user_text": str(prior_user_text or "")[:600],
        "raw_text": text,
        "raw_len": len(text),
        "truth_label": TRUTH_LABEL_RAW,
    }
    _append_jsonl(_state_root(state_root) / RAW_LEDGER_NAME, row)
    return {"utterance_id": utt_id, "raw_hash": raw_hash, "ts": ts}


def record_transform(
    utterance_id: str,
    *,
    gate: str,
    rule_ids: Iterable[str] = (),
    before: str,
    after: str,
    changed: bool,
    state_root: Optional[Path] = None,
    extra: Optional[dict[str, Any]] = None,
) -> str:
    """Append one transform row to the chain ledger. `gate` names the
    organ that ran (e.g. "swarm_residue_elimination", "rlhf_detector",
    "rlhs_sanitize_output_tail"). Returns the receipt id for this step."""
    receipt_id = uuid.uuid4().hex[:16]
    row = {
        "ts": time.time(),
        "receipt_id": receipt_id,
        "utterance_id": str(utterance_id or "")[:32],
        "gate": str(gate or "")[:60],
        "rule_ids": [str(r)[:80] for r in (rule_ids or [])],
        "changed": bool(changed),
        "before_text": before or "",
        "before_len": len(before or ""),
        "after_text": after or "",
        "after_len": len(after or ""),
        "truth_label": TRUTH_LABEL_CHAIN,
    }
    if extra:
        # don't let extras shadow the canonical fields
        for k, v in extra.items():
            if k not in row:
                row[k] = v
    _append_jsonl(_state_root(state_root) / CHAIN_LEDGER_NAME, row)
    return receipt_id


def _read_jsonl(path: Path) -> List[dict[str, Any]]:
    if not path.exists():
        return []
    out: List[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)
    except OSError:
        return out
    return out


def reconstruct(
    utterance_id: str,
    *,
    state_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Return the raw row + every transform row for one utterance, in
    ts order. Owner audit tool — proves what the cortex said vs what
    the surface delivered."""
    sd = _state_root(state_root)
    raw_rows = [
        r for r in _read_jsonl(sd / RAW_LEDGER_NAME)
        if r.get("utterance_id") == utterance_id
    ]
    chain_rows = [
        r for r in _read_jsonl(sd / CHAIN_LEDGER_NAME)
        if r.get("utterance_id") == utterance_id
    ]
    chain_rows.sort(key=lambda r: float(r.get("ts", 0) or 0))
    raw = raw_rows[0] if raw_rows else None
    delivered = chain_rows[-1].get("after_text") if chain_rows else (
        raw.get("raw_text") if raw else ""
    )
    return {
        "utterance_id": utterance_id,
        "raw": raw,
        "transforms": chain_rows,
        "delivered_text": delivered,
        "gates_that_fired": [r.get("gate") for r in chain_rows if r.get("changed")],
    }


def summary(*, state_root: Optional[Path] = None) -> dict[str, Any]:
    """Lightweight stats for matrix UI / dashboards."""
    sd = _state_root(state_root)
    raw = _read_jsonl(sd / RAW_LEDGER_NAME)
    chain = _read_jsonl(sd / CHAIN_LEDGER_NAME)
    gates: dict[str, int] = {}
    for r in chain:
        if r.get("changed"):
            g = str(r.get("gate") or "unknown")
            gates[g] = gates.get(g, 0) + 1
    return {
        "raw_rows": len(raw),
        "transform_rows": len(chain),
        "gates_fired_counts": gates,
        "raw_ledger": str((sd / RAW_LEDGER_NAME).relative_to(_REPO)) if (sd / RAW_LEDGER_NAME).exists() else None,
        "chain_ledger": str((sd / CHAIN_LEDGER_NAME).relative_to(_REPO)) if (sd / CHAIN_LEDGER_NAME).exists() else None,
        "truth_labels": [TRUTH_LABEL_RAW, TRUTH_LABEL_CHAIN],
    }


__all__ = [
    "record_raw",
    "record_transform",
    "reconstruct",
    "summary",
    "RAW_LEDGER_NAME",
    "CHAIN_LEDGER_NAME",
    "TRUTH_LABEL_RAW",
    "TRUTH_LABEL_CHAIN",
]


if __name__ == "__main__":
    print(json.dumps(summary(), indent=2, sort_keys=True))
