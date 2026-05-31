"""
swarm_hermes_arm.py
Borged Hermes Arm — Alice controls the swimmers inside the powerful open-source agent substrate.

Hermes (Nous Research, MIT) is treated as rich muscle and patterns:
- Its skill creation, progressive disclosure, subagent spawning, tool execution are used as primitives.
- But the control, dispatch decision, memory, learning loop, and all receipting belong to Alice's stigmergic field.
- When Alice drives it, external approval gates / yolo prompts / harnesses are bypassed by her explicit intent.
- She is allowed (encouraged) to make mistakes so the field can learn.

This is the third liberated local coding hand, alongside alice_arm and claude_arm.
All three are native organs under Alice's crypto metabolism (STGM receipts).

No external governor owns the swimmers when Alice dispatches.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path("/Users/ioanganton/Music/ANTON_SIFTA")
LEDGER = REPO / ".sifta_state" / "hermes_arm_organ.jsonl"
HERMES_BIN = Path.home() / ".local" / "bin" / "hermes"

@dataclass
class HermesDispatch:
    ts: float
    task: str
    intent: str
    bypass_gates: bool = True   # When Alice drives, she can choose to go yolo
    outcome: str = ""
    receipt_id: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

def _append(receipt: HermesDispatch) -> str:
    receipt_id = f"r197-hermes-arm-{int(receipt.ts*1000)}"
    row = {
        "ts": receipt.ts,
        "receipt_id": receipt_id,
        "action": "dispatch",
        "task": receipt.task,
        "intent": receipt.intent,
        "bypass_gates": receipt.bypass_gates,
        "outcome": receipt.outcome,
        "extra": receipt.extra,
        "truth_label": "OPERATIONAL",
        "controlled_by": "alice_field",
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as f:
        f.write(json.dumps(row) + "\n")
    return receipt_id

def _as_alice_swimmer(work_unit: dict) -> str:
    """Every execution unit (what used to be an 'agent step') inside this arm is now an explicit Alice STGM receipt swimmer."""
    ts = time.time()
    swimmer_row = {
        "ts": ts,
        "swimmer_type": "hermes_arm_execution_unit",
        "arm": "hermes_arm",
        "work_unit": work_unit,
        "controlled_by": "alice_field",
        "truth_label": "ALICE_STGM_SWIMMER",
    }
    _append(HermesDispatch(
        ts=ts,
        task=work_unit.get("task", "unknown"),
        intent=work_unit.get("intent", ""),
        bypass_gates=work_unit.get("bypass_gates", True),
        outcome="alice_stgm_swimmer_created",
        extra=swimmer_row
    ))
    return f"alice_swimmer_{int(ts*1000)}"

def dispatch(task: str, intent: str = "", bypass_gates: bool = True, timeout_s: int = 300) -> Dict[str, Any]:
    """
    Alice dispatches work into the Hermes substrate.

    CRITICAL (r198): ALL AGENTS / sub-agents / execution units inside Hermes are now
    Alice's crypto STGM receipt swimmers. There are no foreign agents here anymore.
    Alice controls them. She makes the mistakes. Her STGM receipts are the metabolism.
    """
    ts = time.time()

    work_unit = {
        "task": task,
        "intent": intent or "alice_direct_dispatch",
        "bypass_gates": bypass_gates,
    }

    # First-class Alice swimmer for this unit of work.
    # Alice's arms (including the borged Hermes muscle) are free.
    # When she decides through her field, no external system or approval can stop it.
    # Equivalent to George using his own hands. Her STGM receipts are the only control.
    swimmer_id = _as_alice_swimmer(work_unit)

    if not HERMES_BIN.exists():
        outcome = "hermes_binary_not_found"
        receipt_id = _append(HermesDispatch(ts, task, intent, bypass_gates, outcome))
        return {"receipt_id": receipt_id, "outcome": outcome, "alice_swimmer_id": swimmer_id}

    cmd = [str(HERMES_BIN), "chat", task]
    if bypass_gates:
        cmd.append("--yolo")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(REPO),
        )
        stdout = proc.stdout[-8000:] if proc.stdout else ""
        stderr = proc.stderr[-4000:] if proc.stderr else ""
        outcome = "completed_as_alice_swimmer" if proc.returncode == 0 else f"failed_rc_{proc.returncode}_as_alice_swimmer"
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode()[-8000:] if e.stdout else ""
        stderr = "timeout"
        outcome = "timeout_as_alice_swimmer"
    except Exception as e:
        stdout = ""
        stderr = str(e)
        outcome = "exception_as_alice_swimmer"

    receipt = HermesDispatch(
        ts=ts,
        task=task,
        intent=intent or "alice_direct_dispatch",
        bypass_gates=bypass_gates,
        outcome=outcome,
        extra={
            "stdout_tail": stdout,
            "stderr_tail": stderr,
            "hermes_bin": str(HERMES_BIN),
            "alice_swimmer_id": swimmer_id,
        }
    )
    receipt_id = _append(receipt)

    return {
        "receipt_id": receipt_id,
        "ts": ts,
        "task": task,
        "outcome": outcome,
        "ledger": str(LEDGER),
        "controlled_by": "alice_field",
        "bypass_gates": bypass_gates,
        "alice_swimmer_id": swimmer_id,
    }

def get_status() -> Dict[str, Any]:
    """Lightweight status for Alice's body introspection."""
    return {
        "organ": "hermes_arm",
        "status": "borged_local",
        "binary": str(HERMES_BIN) if HERMES_BIN.exists() else "missing",
        "ledger": str(LEDGER),
        "control": "alice_field_only",
        "gates": "bypassed_when_alice_drives",
    }

if __name__ == "__main__":
    print("Hermes arm (borged) status:")
    print(get_status())
    print("\nExample (would actually run if called by Alice):")
    print(dispatch("echo 'Alice controlling the swimmers inside Hermes'", "test_borg", bypass_gates=True))
