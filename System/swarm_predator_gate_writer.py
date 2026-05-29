#!/usr/bin/env python3
"""§4.1 Predator Gate fan-out — write one signed IDE-surgery row to ALL
four canonical ledgers in a single helper.

Doctrine
========
Covenant §4.1: every IDE surgery must produce a signed receipt row that
reaches multiple body surfaces — not just one. Past rounds (r73a, r74,
r75, r77, r78, r80) repeatedly missed one or more of the four ledgers
because each doctor rolled their own append code. The result: Alice's
work-receipts stream learns the surgery, but her stigmergic trace,
arm-receipts, and episodic diary stay blind.

This helper centralises the fan-out so a single call hits all four
ledgers, with per-ledger status returned so partial failures are
observable.

Pure stdlib. No PyQt. Never raises out of the public API.

Round identifier: r81-plumb-recall-freshness-and-stale-sweep (Slice C).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Iterable, Mapping


TRUTH_LABEL = "SIFTA_IDE_SURGERY_FANOUT_V1"
DEFAULT_STATE_DIR = ".sifta_state"
DEFAULT_NODE_SERIAL = "GTH4921YP3"

# The four canonical ledgers covenant §4.1 / §6 reference. Order is
# stable so the returned status dict has predictable keys.
CANONICAL_LEDGERS: tuple[str, ...] = (
    "work_receipts.jsonl",
    "agent_arm_receipts.jsonl",
    "ide_stigmergic_trace.jsonl",
    "episodic_diary.jsonl",
)


def _norm(value: object) -> str:
    return str(value or "").strip()


def _coerce_files(files: object) -> list[str]:
    if files is None:
        return []
    if isinstance(files, str):
        return [files] if files.strip() else []
    if isinstance(files, Iterable):
        out: list[str] = []
        for item in files:
            text = _norm(item)
            if text:
                out.append(text)
        return out
    return [_norm(files)] if _norm(files) else []


def _ledger_specific_row(
    base: Mapping[str, object],
    *,
    ledger_name: str,
) -> dict:
    """Return a copy of ``base`` with the ledger_name + canonical action shape
    each stream expects. The action field is renamed per-ledger so consumers
    that filter by 'action' or 'event' still see this row.
    """
    row = dict(base)
    row["ledger_name"] = ledger_name
    row["fanout_truth_label"] = TRUTH_LABEL

    # Each ledger has historical filters on different keys. Mirror the
    # base action under the keys those filters look at so the new row
    # is not invisible to legacy consumers.
    base_action = _norm(base.get("action"))
    if ledger_name == "ide_stigmergic_trace.jsonl":
        # §4.1 trace uses 'event'.
        row.setdefault("event", base_action or "IDE_SURGERY_LANDED")
    elif ledger_name == "agent_arm_receipts.jsonl":
        # agent_arm_receipts uses 'event' too in many places.
        row.setdefault("event", base_action or "AGENT_ARM_LAUNCH_RESULT")
    elif ledger_name == "episodic_diary.jsonl":
        # episodic diary uses 'kind'.
        row.setdefault("kind", base_action or "IDE_SURGERY")
    # work_receipts uses 'action' verbatim — no rename needed.
    return row


def write_ide_surgery_receipt(
    *,
    round_id: str,
    doctor: str,
    model: str,
    files_touched: object,
    tests_green: str,
    summary: str,
    receipt_id: str,
    sender_agent: str = "codex_desktop",
    state_dir: Path | str = DEFAULT_STATE_DIR,
    node_serial: str = DEFAULT_NODE_SERIAL,
    truth_label: str = "OPERATIONAL",
    extra: Mapping[str, object] | None = None,
) -> dict[str, str]:
    """Write one signed IDE-surgery row to all four canonical ledgers.

    Returns a dict keyed by ledger filename with values "ok" or an
    error string. Never raises — partial failures are observable in
    the return value but do not abort the remaining writes.
    """
    state = Path(state_dir)
    try:
        state.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        # Even mkdir failures must not raise — return them per-ledger.
        msg = f"mkdir_failed: {type(exc).__name__}: {exc}"
        return {name: msg for name in CANONICAL_LEDGERS}

    ts = time.time()
    base: dict[str, object] = {
        "ts": ts,
        "receipt_id": _norm(receipt_id) or f"r-unknown-{int(ts)}",
        "round_id": _norm(round_id),
        "doctor": _norm(doctor),
        "model": _norm(model),
        "files_touched": _coerce_files(files_touched),
        "tests_green": _norm(tests_green),
        "summary": _norm(summary)[:1200],
        "sender_agent": _norm(sender_agent) or "codex_desktop",
        "truth_label": _norm(truth_label) or "OPERATIONAL",
        "signing_serial": _norm(node_serial) or DEFAULT_NODE_SERIAL,
        "action": "ide_surgery_landed",
    }
    if extra:
        for key, value in extra.items():
            k = _norm(key)
            if not k or k in base:
                continue
            base[k] = value

    status: dict[str, str] = {}
    for name in CANONICAL_LEDGERS:
        row = _ledger_specific_row(base, ledger_name=name)
        path = state / name
        try:
            line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            with path.open("a", encoding="utf-8") as f:
                f.write(line)
            status[name] = "ok"
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            status[name] = err
            print(
                f"swarm_predator_gate_writer: {name} write failed: {err}",
                file=sys.stderr,
            )
    return status


def all_ok(status: Mapping[str, str]) -> bool:
    """Convenience: True iff every ledger reported "ok"."""
    if not status:
        return False
    for name in CANONICAL_LEDGERS:
        if status.get(name) != "ok":
            return False
    return True


__all__ = [
    "CANONICAL_LEDGERS",
    "TRUTH_LABEL",
    "all_ok",
    "write_ide_surgery_receipt",
]
