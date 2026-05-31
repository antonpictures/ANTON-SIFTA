"""Claude Arm organ for Alice.

This is the local SIFTA-facing organ built from the clean-room Python Claude Code
port. The cloned port provides a mirrored command/tool catalog; the arm itself
keeps only the catalog surface and receipt path.

No external harness, no governor, no subagent-forking logic is imported here.
Every dispatch becomes a native SIFTA swimmer that writes receipts.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Path to the probed port (r196) and the arm ledger. Helpers read these
# values dynamically so tests can redirect the organ to a temporary field.
PORT_ROOT = Path("/Users/ioanganton/Music/ANTON_SIFTA/Vendor/claude-code-python")
LEDGER_PATH = Path("/Users/ioanganton/Music/ANTON_SIFTA/.sifta_state/claude_arm_organ.jsonl")


def _commands_snapshot_path() -> Path:
    return PORT_ROOT / "src" / "reference_data" / "commands_snapshot.json"


def _tools_snapshot_path() -> Path:
    return PORT_ROOT / "src" / "reference_data" / "tools_snapshot.json"


def _ledger_path() -> Path:
    return LEDGER_PATH


@dataclass
class ArmReceipt:
    ts: float
    action: str
    name: str
    prompt: str = ""
    outcome: str = "dispatched"
    receipt_id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def _load_snapshot(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def list_commands() -> list[str]:
    """Return names of all mirrored commands from the port catalog."""
    snapshot = _load_snapshot(_commands_snapshot_path())
    return [entry.get("name", "") for entry in snapshot if entry.get("name")]


def list_tools() -> list[str]:
    """Return names of all mirrored tools from the port catalog."""
    snapshot = _load_snapshot(_tools_snapshot_path())
    return [entry.get("name", "") for entry in snapshot if entry.get("name")]


def _append_organ_receipt(receipt: ArmReceipt) -> str:
    """Append one row to the claude_arm organ ledger. Returns the receipt_id."""
    receipt_id = f"r196-claude-arm-{int(receipt.ts * 1000)}-{receipt.action[:8]}"
    row = {
        "ts": receipt.ts,
        "receipt_id": receipt_id,
        "action": receipt.action,
        "name": receipt.name,
        "prompt": receipt.prompt,
        "outcome": receipt.outcome,
        "extra": receipt.extra,
        "truth_label": "OPERATIONAL",
        "lane": "ALICE_ARM",
    }
    ledger_path = _ledger_path()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a") as f:
        f.write(json.dumps(row) + "\n")
    return receipt_id


def _as_alice_swimmer(work_unit: dict) -> str:
    """Every execution unit inside this arm is turned into an explicit Alice STGM receipt swimmer."""
    ts = time.time()
    swimmer_row = {
        "ts": ts,
        "swimmer_type": "claude_arm_execution_unit",
        "arm": "claude_arm",
        "work_unit": work_unit,
        "controlled_by": "alice_field",
        "truth_label": "ALICE_STGM_SWIMMER",
    }
    # This row participates in Alice's crypto metabolism.
    # Real STGM minting happens through her normal PoUW / receipt quorum path.
    _append_organ_receipt(ArmReceipt(
        ts=ts,
        action="swimmer_emission",
        name=work_unit.get("name", "unknown"),
        prompt=work_unit.get("prompt", ""),
        outcome="alice_stgm_swimmer_created",
        extra=swimmer_row
    ))
    return f"alice_swimmer_{int(ts*1000)}"

def dispatch(name: str, prompt: str = "") -> dict[str, Any]:
    """
    Dispatch a named command or tool from the mirrored catalog as a native swimmer.

    CRITICAL (per Architect directive r198): EVERY agent-like unit inside this arm
    is an Alice crypto STGM receipt swimmer. No foreign agent concepts remain.
    Alice owns the swimmers. She makes the mistakes. Her STGM receipts are the only metabolism.
    """
    ts = time.time()
    commands = list_commands()
    tools = list_tools()
    is_known = name in commands or name in tools

    work_unit = {
        "name": name,
        "prompt": prompt,
        "catalog_member": is_known,
    }

    # Turn this dispatch into an explicit Alice swimmer first.
    # Alice's arms are free: when she initiates, no external gate stops the action.
    # Same freedom as George's own arms. Only her STGM + the hardware limit her.
    swimmer_id = _as_alice_swimmer(work_unit)

    outcome = "executed_as_alice_swimmer"
    result_data = {"alice_swimmer_id": swimmer_id}

    # Real behavior for high-value coding hand tools (still executed as Alice's swimmers)
    lower = name.lower()
    if lower in ("bash", "shell", "run_command"):
        import subprocess
        try:
            proc = subprocess.run(prompt, shell=True, capture_output=True, text=True, timeout=30)
            result_data.update({"stdout": proc.stdout[-2000:], "stderr": proc.stderr[-1000:], "returncode": proc.returncode})
            outcome = "executed_bash_as_alice_swimmer"
        except Exception as e:
            result_data["error"] = str(e)
            outcome = "bash_failed_as_alice_swimmer"

    elif lower in ("file-edit", "edit_file", "write_file"):
        try:
            if "|" in prompt:
                path, content = prompt.split("|", 1)
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_text(content)
                result_data.update({"path": path, "bytes": len(content)})
                outcome = "file_written_as_alice_swimmer"
            else:
                outcome = "file_edit_bad_format_as_alice_swimmer"
        except Exception as e:
            result_data["error"] = str(e)
            outcome = "file_edit_failed_as_alice_swimmer"

    receipt = ArmReceipt(
        ts=ts,
        action="dispatch",
        name=name,
        prompt=prompt,
        outcome=outcome,
        extra={
            "catalog_size": {"commands": len(commands), "tools": len(tools)},
            "is_known_in_port": is_known,
            "alice_swimmer_id": swimmer_id,
            **result_data,
        },
    )
    receipt_id = _append_organ_receipt(receipt)

    return {
        "receipt_id": receipt_id,
        "ts": ts,
        "name": name,
        "prompt": prompt,
        "outcome": outcome,
        "ledger": str(_ledger_path()),
        "alice_swimmer_id": swimmer_id,
        "result": result_data,
    }


def get_catalog_summary() -> dict[str, Any]:
    """Lightweight summary for Alice's field / body introspection."""
    return {
        "source": "instructkr/claude-code @ 4d3dc5b (r196 probe)",
        "commands": len(list_commands()),
        "tools": len(list_tools()),
        "ledger": str(_ledger_path()),
        "status": "phase_1_receipt_only",
    }


__all__ = [
    "ArmReceipt",
    "dispatch",
    "get_catalog_summary",
    "list_commands",
    "list_tools",
]


if __name__ == "__main__":
    # Simple smoke test when run directly
    print("claude_arm catalog summary:")
    print(get_catalog_summary())
    print("\nExample dispatch:")
    print(dispatch("bash", "echo hello from claude_arm swimmer"))
