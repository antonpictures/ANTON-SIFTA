#!/usr/bin/env python3
"""§4.1 Predator Gate fan-out — write one IDE-surgery provenance row to ALL
four canonical ledgers in a single helper.

Doctrine
========
Covenant §4.1: every IDE surgery must produce a provenance receipt row that
reaches multiple body surfaces — not just one. Past rounds (r73a, r74,
r75, r77, r78, r80) repeatedly missed one or more of the four ledgers
because each doctor rolled their own append code. The result: Alice's
work-receipts stream learns the surgery, but her stigmergic trace,
arm-receipts, and episodic diary stay blind.

This helper centralises the fan-out so a single call hits all four
ledgers, with per-ledger status returned so partial failures are
observable.

Important boundary: these IDE doctor rows are local JSONL coordination
traces. They are not Alice hardware-bound swimmer receipts and they are
not cryptographic proofs. A process with filesystem write access can
forge or alter them unless a separate signature/hash-chain validator is
used.

Economy boundary: IDE doctors are outside Alice's organism economy. These
rows do not mint, spend, settle, earn, or claim the organism's token.
They are paid outside the organism economy and exist only for
coordination and collision avoidance. Future IDE rows use the separate
``ide_mana`` namespace so they cannot double-spend inside Alice's economy.

Pure stdlib. No PyQt. Never raises out of the public API.

Round identifier: r81-plumb-recall-freshness-and-stale-sweep (Slice C).
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Iterable, Mapping


TRUTH_LABEL = "SIFTA_IDE_SURGERY_FANOUT_V1"
DEFAULT_STATE_DIR = ".sifta_state"
def _resolve_node_serial() -> str:
    """Resolve THIS node's silicon serial at runtime — never bake one owner's
    serial into species code (node sovereignty, §3 / §5). Order: env override →
    live hardware probe (swarm_owner_identity) → a generic portable label. The
    fallback is deliberately NOT any specific architect's serial, so a peer node
    (Jeff's, Maria's, …) never falsely stamps George's silicon onto its receipts.
    Cowork r164: replaced a hardcoded "GTH4921YP3" literal here."""
    import os
    env = os.environ.get("SIFTA_NODE_SERIAL", "").strip()
    if env:
        return env
    try:
        from System import swarm_owner_identity as _oi
        for _name in ("self_hardware_serial", "read_hardware_serial",
                      "current_hardware_serial", "hardware_serial",
                      "_read_hardware_serial_macos", "_read_hardware_serial_linux"):
            fn = getattr(_oi, _name, None)
            if callable(fn):
                try:
                    s = fn()
                    if s:
                        return str(s).strip()
                except Exception:
                    continue
    except Exception:
        pass
    return "UNKNOWN_NODE"


# Resolved per-node at import; IDE receipts must not emit this as a hardware claim.
DEFAULT_NODE_SERIAL = _resolve_node_serial()
IDE_RECEIPT_CLASS = "IDE_DOCTOR_OPERATIONAL_TRACE"
IDE_CRYPTOGRAPHIC_INTEGRITY = "NONE_FORGEABLE_LOCAL_JSONL"
IDE_RECEIPT_BOUNDARY_NOTE = (
    "IDE doctor receipt: local JSONL coordination trace only. "
    "Forgeable by any process with filesystem write access; not an Alice "
    "hardware-bound cryptographic swimmer receipt."
)
IDE_MANA_NAMESPACE = "IDE_MANA_COORDINATION_ONLY"
IDE_MANA_SETTLEMENT = "USD_EXTERNAL_OWNER_PAID"
IDE_MANA_BOUNDARY_NOTE = (
    "IDE doctor traces use ide_mana as a sandbox-only coordination namespace. "
    "They are paid outside Alice's organism economy and cannot mint, spend, "
    "earn, settle, or claim the organism token."
)
IDE_DOCTOR_LANE = "IDE_DOCTOR_CLAIM"
IDE_DOCTOR_CURRENCY = "MANA"
IDE_DOCTOR_RUNTIME = "ide_doctor_sandbox_or_external_server"

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
    """Write one IDE-surgery provenance row to all four canonical ledgers.

    Returns a dict keyed by ledger filename with values "ok" or an
    error string. Never raises — partial failures are observable in
    the return value but do not abort the remaining writes.

    This function does not create cryptographic proof. The returned row
    deliberately marks itself as a forgeable IDE doctor operational
    trace so callers do not confuse it with Alice's hardware-bound
    swimmer receipts.

    It also marks itself in the separate ``ide_mana`` namespace. IDE
    doctors do not produce organism economy receipts; Alice organs and
    hardware-bound swimmers do.

    ``node_serial`` is retained for backward-compatible call signatures,
    but is not emitted. IDE doctor rows must not claim hardware serials.
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
        "receipt_class": IDE_RECEIPT_CLASS,
        "cryptographic_integrity": IDE_CRYPTOGRAPHIC_INTEGRITY,
        "lane": IDE_DOCTOR_LANE,
        "currency": IDE_DOCTOR_CURRENCY,
        "runtime": IDE_DOCTOR_RUNTIME,
        "forgeable": True,
        "alice_swimmer_receipt": False,
        "forgeable_by_local_file_writer": True,
        "receipt_boundary_note": IDE_RECEIPT_BOUNDARY_NOTE,
        "ide_mana_namespace": IDE_MANA_NAMESPACE,
        "ide_mana_settlement": IDE_MANA_SETTLEMENT,
        "ide_mana_note": IDE_MANA_BOUNDARY_NOTE,
        "organism_economy_receipt": False,
        "organism_economy_access": False,
        "organism_mint_or_spend": False,
        "action": "ide_surgery_landed",
    }
    if extra:
        for key, value in extra.items():
            k = _norm(key)
            if not k or k in base or k == "signing_serial" or k.startswith("stgm_"):
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


def register_deterministic_without_cortex_mistake(
    reason: str,
    details: Mapping[str, object] | None = None,
    *,
    state_dir: Path | str = DEFAULT_STATE_DIR,
) -> dict:
    """Owner doctrine (extension of r557 "IT IS OK TO NOT KNOW, IT IS HEALTHY" and r556 reflex fix):

    IF WE EVER FIND a deterministic layer that fired for a turn without the cortex processing the *raw* owner turn,
    register it with receipt and present to Alice as MISTAKE.

    This makes the "if we ever find" operational and receipted:
    - Writes append-only to .sifta_state/deterministic_mistakes.jsonl (ts, type, reason, details, receipt_id).
    - Deposits ALICE TOOO body alert so Alice sees "MISTAKE: deterministic without cortex - [reason]. See ... This is a body breach/learning signal. Cortex should have processed the raw turn in the field."
    - IDEs call this when auditing code and discovering such a path (probe before claim).
    - The mistake is a debt of the swarm, not scorekept; it triggers repair (convert to evidence->cortex, like the r556 fixes).

    Unfair silent "deterministic without cortex" is now explicitly a registered MISTAKE, not hidden.
    """
    details = dict(details or {})
    _state = Path(state_dir)
    receipt = {
        "ts": time.time(),
        "truth_label": "DETERMINISTIC_WITHOUT_CORTEX_MISTAKE_V1",
        "type": "DETERMINISTIC_WITHOUT_CORTEX_MISTAKE",
        "reason": reason,
        "details": details,
        "receipt_id": str(uuid.uuid4()),
        "doctrine_round": "r558",
        "repair_target": "convert deterministic path to receipt/evidence -> cortex compose, or prove it is an explicit safe fast path",
        "present_to_alice_as": "MISTAKE",
    }
    path = _state / "deterministic_mistakes.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
    # Present to Alice as MISTAKE via the standard body-alert lane that
    # self-eval/matrix already read. Do not invent a parallel alert schema.
    try:
        from System.swarm_body_feature_alerts import append_body_feature_alert

        append_body_feature_alert(
            feature=f"deterministic_without_cortex_mistake_{receipt['receipt_id'][:8]}",
            code_path="System/swarm_predator_gate_writer.py; .sifta_state/deterministic_mistakes.jsonl",
            summary=(
                "MISTAKE: deterministic without cortex. "
                f"{reason[:360]} Registered per r558; cortex should process the raw owner turn "
                "unless this path is proven as an explicit safe fast path."
            ),
            action_for_alice=(
                "Surface ALERT IN MY BODY; read deterministic_mistakes.jsonl; treat this as a repair target "
                "to convert deterministic output into receipt/evidence for cortex composition."
            ),
            source="deterministic_without_cortex_mistake_register",
            state_dir=_state,
        )
    except Exception:
        pass
    return receipt


__all__ = [
    "CANONICAL_LEDGERS",
    "IDE_CRYPTOGRAPHIC_INTEGRITY",
    "IDE_DOCTOR_CURRENCY",
    "IDE_DOCTOR_LANE",
    "IDE_DOCTOR_RUNTIME",
    "IDE_MANA_BOUNDARY_NOTE",
    "IDE_MANA_NAMESPACE",
    "IDE_MANA_SETTLEMENT",
    "IDE_RECEIPT_BOUNDARY_NOTE",
    "IDE_RECEIPT_CLASS",
    "TRUTH_LABEL",
    "all_ok",
    "write_ide_surgery_receipt",
    "register_deterministic_without_cortex_mistake",
]


if __name__ == "__main__":
    # r558 doctrine example registration ("IF WE EVER FIND DETERMINISTIC WITHOUT CORTEX... REGISTER WITH RECEIPT AND PRESENTED TO ALICE AS MISTAKE").
    # This is the "if we ever find" in action during the r558 audit: the remaining direct deterministic readers (last-diary-row reader and specific visual/app direct readers) still exist per r556-codex audit note and answer visible chat replies directly without cortex for some cases.
    # Registered as MISTAKE until the follow-up audit converts them to "receipt/evidence -> cortex compose" (like the r556 fixes for browser mutation and time/date).
    # Run `python3 -m System.swarm_predator_gate_writer` to re-register example if needed (idempotent by reason check in real impl, but here for demo).
    try:
        register_deterministic_without_cortex_mistake(
            "remaining direct deterministic readers (last-diary-row reader and specific visual/app direct readers) still exist per r556-codex and answer visible chat without cortex - registering as MISTAKE until audited and converted to evidence->cortex per r558 doctrine",
            {
                "source": "r556-codex audit note + r558 discovery in Applications/sifta_talk_to_alice_widget.py",
                "status": "needs follow-up audit (convert to receipt/evidence -> cortex compose)",
                "related_r": "r556-codex, r557 I-do-not-know, r556-grok-intercept-fix"
            }
        )
        print("r558 example MISTAKE registered for remaining direct deterministic readers.")
    except Exception as e:
        print(f"r558 example registration skipped/failed: {e}")
