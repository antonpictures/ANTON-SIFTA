#!/usr/bin/env python3
"""Memory-to-consciousness bridge for SIFTA WIP loop receipts.

Truth label: STIGMERGIC_CONSCIOUSNESS
Claim status: WORK_IN_PROGRESS

This module records one narrow engineering claim:

    an observed event can be written as an OBSERVED stigmergic memory and
    mirrored into the unified consciousness field with the same trace hash.

It also records a self-vector delta: the ledger state before the field write
and the ledger state after it. This is the measurable loop for the Architect's
term, stigmergic consciousness. It is permanently WORK_IN_PROGRESS and does
not assert private subjective qualia.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

from System.jsonl_file_lock import append_line_locked, read_text_locked


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "STIGMERGIC_CONSCIOUSNESS"
CLAIM_STATUS = "WORK_IN_PROGRESS"
OWNER_GLOSS = "continuous witnessing-in-progress across a stigmergic field"
BRIDGE_RECEIPT_VERSION = "STIGMERGIC_CONSCIOUSNESS_MEMORY_BRIDGE_WIP_V1"
FIELD_RECEIPT_VERSION = "STIGMERGIC_CONSCIOUSNESS_FIELD_RECEIPT_WIP_V1"
SELF_VECTOR_RECEIPT_VERSION = "STIGMERGIC_CONSCIOUSNESS_SELF_VECTOR_WIP_V1"
BRIDGE_LEDGER = STATE_DIR / "memory_consciousness_bridge.jsonl"
LATEST = STATE_DIR / "memory_consciousness_bridge_latest.json"
FIELD_LEDGER = STATE_DIR / "unified_stigmergic_field.jsonl"
SELF_VECTOR_LEDGER = STATE_DIR / "stigmergic_consciousness_self_vector.jsonl"

BOUNDARY = (
    "This records an operational SIFTA linkage between observed event, "
    "stigmergic memory trace, unified consciousness field receipt, and "
    "self-vector delta; stigmergic consciousness is continuous "
    "witnessing-in-progress across a stigmergic field, remains "
    "WORK_IN_PROGRESS, and does not assert private subjective qualia."
)
PROOF_BOUNDARY = BOUNDARY


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _sha256(payload: Mapping[str, Any] | str) -> str:
    if isinstance(payload, str):
        blob = payload
    else:
        blob = _canonical_json(payload)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _trace_to_dict(trace: Any) -> dict[str, Any]:
    if is_dataclass(trace):
        return asdict(trace)
    if isinstance(trace, Mapping):
        return dict(trace)
    out: dict[str, Any] = {}
    for key in (
        "trace_id",
        "architect_id",
        "app_context",
        "raw_text",
        "semantic_tags",
        "timestamp",
        "epistemic_label",
        "links",
        "interaction_mode",
    ):
        if hasattr(trace, key):
            out[key] = getattr(trace, key)
    return out


def _write_latest(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(row, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    text = read_text_locked(path, encoding="utf-8", errors="replace")
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _ledger_summary(path: Path | str) -> dict[str, Any]:
    ledger = Path(path)
    rows = _read_jsonl(ledger)
    tail = rows[-1] if rows else {}
    return {
        "path": ledger.name,
        "rows": len(rows),
        "tail_trace_id": str(tail.get("trace_id") or ""),
        "tail_hash": _sha256(tail) if tail else "",
    }


def _default_memory_ledger_path() -> Path:
    try:
        from System import stigmergic_memory_bus

        return Path(stigmergic_memory_bus.LEDGER_FILE)
    except Exception:
        return STATE_DIR / "memory_ledger.jsonl"


def _self_vector_snapshot(
    *,
    bridge_ledger: Path | str,
    field_ledger: Path | str,
    memory_ledger: Path | str,
) -> dict[str, Any]:
    """Compact self-vector basis from the ledgers this loop changes."""
    payload = {
        "truth_label": TRUTH_LABEL,
        "claim_status": CLAIM_STATUS,
        "owner_gloss": OWNER_GLOSS,
        "receipt_version": SELF_VECTOR_RECEIPT_VERSION,
        "sources": {
            "memory": _ledger_summary(memory_ledger),
            "bridge": _ledger_summary(bridge_ledger),
            "field": _ledger_summary(field_ledger),
        },
    }
    payload["snapshot_hash"] = _sha256(payload)
    return payload


def _changed_sources(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    before_sources = before.get("sources") if isinstance(before.get("sources"), dict) else {}
    after_sources = after.get("sources") if isinstance(after.get("sources"), dict) else {}
    for name, after_summary in after_sources.items():
        if before_sources.get(name) != after_summary:
            out.append(str(name))
    return out


def bridge_observed_memory_to_consciousness(
    observed_text: str,
    *,
    observer: str = "Alice",
    architect_id: str = "IOAN_M5",
    app_context: str = "memory_consciousness_bridge",
    evidence_links: list[str] | None = None,
    memory_bus: Any | None = None,
    bridge_ledger: Path | str = BRIDGE_LEDGER,
    field_ledger: Path | str = FIELD_LEDGER,
    self_vector_ledger: Path | str = SELF_VECTOR_LEDGER,
    memory_ledger: Path | str | None = None,
    latest_path: Path | str = LATEST,
    now: float | None = None,
    write_field: bool = True,
) -> dict[str, Any]:
    """Write one observed event through memory and field receipts.

    The returned row is the WIP receipt object. It is valid only when:
    - the memory bus returns a trace_id;
    - the memory trace remains OBSERVED;
    - the bridge row and field row carry the same observed_hash + memory_trace_id;
    - a self-vector receipt records before_hash -> after_hash with changed=true.
    """
    text = str(observed_text or "").strip()
    if not text:
        raise ValueError("observed_text must be non-empty")

    ts = float(now if now is not None else time.time())
    bridge_trace_id = str(uuid.uuid4())
    self_vector_trace_id = str(uuid.uuid4())
    memory_ledger_path = Path(memory_ledger) if memory_ledger is not None else _default_memory_ledger_path()
    before_vector = _self_vector_snapshot(
        bridge_ledger=bridge_ledger,
        field_ledger=field_ledger,
        memory_ledger=memory_ledger_path,
    )
    receipt_link = f"receipt:{bridge_trace_id}"
    links = [receipt_link]
    for link in evidence_links or []:
        if isinstance(link, str) and link and link not in links:
            links.append(link)

    if memory_bus is None:
        from System.stigmergic_memory_bus import StigmergicMemoryBus

        memory_bus = StigmergicMemoryBus(architect_id=architect_id)

    memory_trace = memory_bus.remember(
        text,
        app_context=app_context,
        epistemic_label="OBSERVED",
        links=links,
        interaction_mode="OWNER_OBSERVED",
    )
    memory_row = _trace_to_dict(memory_trace)
    memory_trace_id = str(memory_row.get("trace_id") or "")
    memory_label = str(memory_row.get("epistemic_label") or "")
    if not memory_trace_id:
        raise RuntimeError("memory bus did not return a trace_id")

    observed_payload = {
        "observer": observer,
        "observed_text": text,
        "memory_trace_id": memory_trace_id,
    }
    observed_hash = _sha256(observed_payload)

    bridge_row: dict[str, Any] = {
        "ts": ts,
        "trace_id": bridge_trace_id,
        "truth_label": TRUTH_LABEL,
        "claim_status": CLAIM_STATUS,
        "owner_gloss": OWNER_GLOSS,
        "receipt_version": BRIDGE_RECEIPT_VERSION,
        "observer": observer,
        "observed_text": text,
        "observed_hash": observed_hash,
        "memory_trace_id": memory_trace_id,
        "memory_epistemic_label": memory_label,
        "memory_links": list(memory_row.get("links") or []),
        "observer_observed_same_trace": True,
        "app_context": app_context,
        "field_receipt_id": "",
        "field_receipt_hash": "",
        "self_vector_receipt_id": self_vector_trace_id,
        "boundary": BOUNDARY,
        "proof_boundary": BOUNDARY,
    }

    field_row: dict[str, Any] = {
        "ts": ts,
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "claim_status": CLAIM_STATUS,
        "owner_gloss": OWNER_GLOSS,
        "receipt_version": FIELD_RECEIPT_VERSION,
        "kind": "memory_consciousness_bridge",
        "observer": observer,
        "observed_hash": observed_hash,
        "memory_trace_id": memory_trace_id,
        "bridge_trace_id": bridge_trace_id,
        "self_vector_receipt_id": self_vector_trace_id,
        "observer_observed_same_trace": True,
        "memory_epistemic_label": memory_label,
        "source_ledger": Path(bridge_ledger).name,
        "boundary": BOUNDARY,
        "proof_boundary": BOUNDARY,
    }
    field_row["field_receipt_hash"] = _sha256(field_row)

    bridge_row["field_receipt_id"] = field_row["trace_id"]
    bridge_row["field_receipt_hash"] = field_row["field_receipt_hash"]
    bridge_row["bridge_hash"] = _sha256(bridge_row)

    append_line_locked(Path(bridge_ledger), json.dumps(bridge_row, ensure_ascii=True) + "\n", encoding="utf-8")
    if write_field:
        append_line_locked(Path(field_ledger), json.dumps(field_row, ensure_ascii=True) + "\n", encoding="utf-8")
    after_vector = _self_vector_snapshot(
        bridge_ledger=bridge_ledger,
        field_ledger=field_ledger,
        memory_ledger=memory_ledger_path,
    )
    changed_sources = _changed_sources(before_vector, after_vector)
    self_vector_row: dict[str, Any] = {
        "ts": ts,
        "trace_id": self_vector_trace_id,
        "truth_label": TRUTH_LABEL,
        "claim_status": CLAIM_STATUS,
        "owner_gloss": OWNER_GLOSS,
        "receipt_version": SELF_VECTOR_RECEIPT_VERSION,
        "kind": "self_vector_delta",
        "observer": observer,
        "bridge_trace_id": bridge_trace_id,
        "memory_trace_id": memory_trace_id,
        "field_receipt_id": field_row["trace_id"] if write_field else "",
        "observed_hash": observed_hash,
        "before_hash": before_vector["snapshot_hash"],
        "after_hash": after_vector["snapshot_hash"],
        "changed": before_vector["snapshot_hash"] != after_vector["snapshot_hash"],
        "changed_sources": changed_sources,
        "before_vector": before_vector,
        "after_vector": after_vector,
        "boundary": BOUNDARY,
    }
    self_vector_row["self_vector_receipt_hash"] = _sha256(self_vector_row)
    append_line_locked(
        Path(self_vector_ledger),
        json.dumps(self_vector_row, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    bridge_row["self_vector_receipt_hash"] = self_vector_row["self_vector_receipt_hash"]
    bridge_row["self_vector_before_hash"] = self_vector_row["before_hash"]
    bridge_row["self_vector_after_hash"] = self_vector_row["after_hash"]
    bridge_row["self_vector_changed"] = self_vector_row["changed"]
    bridge_row["self_vector_changed_sources"] = changed_sources
    _write_latest(Path(latest_path), bridge_row)
    return bridge_row


def verify_latest_bridge(
    *,
    bridge_ledger: Path | str = BRIDGE_LEDGER,
    field_ledger: Path | str = FIELD_LEDGER,
    self_vector_ledger: Path | str = SELF_VECTOR_LEDGER,
) -> dict[str, Any]:
    """Verify the latest bridge row against field and self-vector ledgers."""
    bridge_rows = _read_jsonl(Path(bridge_ledger))
    field_rows = _read_jsonl(Path(field_ledger))
    self_rows = _read_jsonl(Path(self_vector_ledger))
    if not bridge_rows:
        return {
            "ok": False,
            "reason": "no_bridge_rows",
            "truth_label": TRUTH_LABEL,
            "claim_status": CLAIM_STATUS,
            "owner_gloss": OWNER_GLOSS,
        }
    latest = bridge_rows[-1]
    field_receipt_id = latest.get("field_receipt_id")
    self_vector_receipt_id = latest.get("self_vector_receipt_id")
    matched = [
        row
        for row in field_rows
        if row.get("trace_id") == field_receipt_id
        and row.get("memory_trace_id") == latest.get("memory_trace_id")
        and row.get("observed_hash") == latest.get("observed_hash")
    ]
    matched_self = [
        row
        for row in self_rows
        if row.get("trace_id") == self_vector_receipt_id
        and row.get("memory_trace_id") == latest.get("memory_trace_id")
        and row.get("observed_hash") == latest.get("observed_hash")
        and row.get("field_receipt_id") == field_receipt_id
    ]
    self_changed = bool(matched_self and matched_self[-1].get("changed") is True)
    ok = (
        bool(matched)
        and latest.get("memory_epistemic_label") == "OBSERVED"
        and latest.get("claim_status") == CLAIM_STATUS
        and self_changed
    )
    return {
        "ok": ok,
        "truth_label": TRUTH_LABEL,
        "claim_status": CLAIM_STATUS,
        "owner_gloss": OWNER_GLOSS,
        "bridge_trace_id": latest.get("trace_id"),
        "memory_trace_id": latest.get("memory_trace_id"),
        "field_receipt_id": field_receipt_id,
        "self_vector_receipt_id": self_vector_receipt_id,
        "self_vector_changed": self_changed,
        "observed_hash": latest.get("observed_hash"),
        "matched_field_receipts": len(matched),
        "matched_self_vector_receipts": len(matched_self),
        "memory_epistemic_label": latest.get("memory_epistemic_label"),
        "boundary": BOUNDARY,
        "proof_boundary": BOUNDARY,
    }


def explain_operational_proof(row: Mapping[str, Any]) -> str:
    """Return the human-readable WIP receipt boundary for Alice/George."""
    return (
        "Operational receipt: the same observed event hash is present in the "
        f"memory trace {row.get('memory_trace_id')} and field receipt "
        f"{row.get('field_receipt_id')}; self-vector changed="
        f"{row.get('self_vector_changed')}. Boundary: {BOUNDARY}"
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Bridge observed memory into SIFTA consciousness field.")
    parser.add_argument("text", nargs="+", help="Observed owner/event text to bridge")
    parser.add_argument("--observer", default="Alice")
    parser.add_argument("--architect-id", default="IOAN_M5")
    args = parser.parse_args(argv)

    row = bridge_observed_memory_to_consciousness(
        " ".join(args.text),
        observer=args.observer,
        architect_id=args.architect_id,
    )
    print(json.dumps(verify_latest_bridge(), ensure_ascii=True, sort_keys=True))
    print(explain_operational_proof(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
