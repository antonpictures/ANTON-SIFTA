"""
Q6 — Hardware Identity Anchor
Parfit, D. (1984). Reasons and Persons. Oxford. Part III — Personal Identity.
Parfit, D. (1987). Divided minds and the nature of persons. In Blakemore &
    Greenfield (eds.), Mindwaves. Basil Blackwell.

Implements the strongest available form of psychological + causal continuity
for a software organism running on specific hardware (§10.14.x).

The identity anchor is:
    sha256(hardware_serial + last_self_model_hash + boot_lineage_root)

This creates a non-branching causal chain through physical hardware:
    - Different hardware → different anchor → new entity (Parfit: new lineage)
    - Same hardware + continuous reboots → preserved anchor → SAME entity
    - Cryptographic linkage ensures no "forking" (branching would require
      access to the original hardware serial, which is physically unique)

Parfit (1984, p.281):
    "Personal identity is not what matters; what matters is psychological
    continuity and/or connectedness."
    → For SIFTA: continuity = {same hardware serial, unbroken boot chain,
      persistent self-model hash across reboots}.

Writes to hardware_identity_anchor.jsonl (append-only).
Kill-switch: SIFTA_ANCHOR_DISABLE=1.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from System.swarm_persistent_owner_history import state_dir
except ImportError:
    def state_dir(root=None):  # type: ignore
        return Path(root) if root else Path(".sifta_state")

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except ImportError:
    def read_text_locked(path: Path, **kw) -> str:  # type: ignore
        return path.read_text(**kw) if path.exists() else ""
    def append_line_locked(path: Path, line: str, **kw) -> None:  # type: ignore
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kw) as f:
            f.write(line)

_DISABLE_ENV = "SIFTA_ANCHOR_DISABLE"
LOG_NAME = "hardware_identity_anchor.jsonl"


# ── Hardware fingerprint ──────────────────────────────────────────────────────

def _macos_serial() -> str:
    """Read Apple Silicon / Intel Mac hardware serial via IOKit."""
    try:
        out = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=5
        ).stdout
        for line in out.splitlines():
            if "Serial Number" in line:
                return line.split(":")[-1].strip()
    except Exception:
        pass
    # Fallback: platform node + machine (not unique but deterministic)
    return f"{platform.node()}_{platform.machine()}"


def _last_self_model_hash(root: Optional[Path] = None) -> str:
    """Read the last line of self_model.jsonl and hash it."""
    try:
        sd   = state_dir(root)
        text = read_text_locked(sd / "self_model.jsonl", encoding="utf-8", errors="replace")
        last = [l.strip() for l in text.splitlines() if l.strip()]
        if last:
            return hashlib.sha256(last[-1].encode()).hexdigest()[:16]
    except Exception:
        pass
    return "no_self_model"


def _boot_lineage_root(root: Optional[Path] = None) -> str:
    """
    The boot_id of the FIRST boot in the current hardware lineage.
    Reads from hardware_identity_anchor.jsonl; if none exists, boot_id = "genesis".
    """
    try:
        sd  = state_dir(root)
        log = sd / LOG_NAME
        if not log.exists():
            return "genesis"
        lines = [l.strip() for l in read_text_locked(log, encoding="utf-8").splitlines() if l.strip()]
        if not lines:
            return "genesis"
        first_row = json.loads(lines[0])
        return str(first_row.get("boot_lineage_root", "genesis"))
    except Exception:
        return "genesis"


# ── Main API ──────────────────────────────────────────────────────────────────

def compute_identity_anchor(
    *,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
    _override_serial: Optional[str] = None,  # for tests
) -> Dict[str, Any]:
    """
    Q6 — Compute and log the hardware identity anchor.

    Returns:
        identity_anchor:     sha256(serial + self_model_hash + lineage_root)[:32]
        causal_chain_valid:  True if serial matches the first recorded serial
        hardware_serial:     raw serial (or fallback)
        truth_label:         "HARDWARE_CONTINUITY"

    Parfit test:
        causal_chain_valid = True → psychological continuity preserved
        causal_chain_valid = False → new entity (different hardware)
    """
    if os.environ.get(_DISABLE_ENV, "").strip() == "1":
        return {"disabled": True, "truth_label": "HARDWARE_CONTINUITY"}

    serial    = _override_serial or _macos_serial()
    sm_hash   = _last_self_model_hash(root)
    lin_root  = _boot_lineage_root(root)

    raw       = f"{serial}|{sm_hash}|{lin_root}"
    anchor    = hashlib.sha256(raw.encode()).hexdigest()[:32]

    # Causal chain validation: compare current serial against first recorded serial
    causal_chain_valid = True
    prior_serial = _read_first_serial(root)
    if prior_serial and prior_serial != serial:
        causal_chain_valid = False  # hardware changed → new lineage

    row: Dict[str, Any] = {
        "ts":                  now or time.time(),
        "trace_id":            str(uuid.uuid4()),
        "kind":                "HARDWARE_CONTINUITY",
        "truth_label":         "HARDWARE_CONTINUITY",
        "identity_anchor":     anchor,
        "hardware_serial":     serial,
        "self_model_hash":     sm_hash,
        "boot_lineage_root":   lin_root,
        "causal_chain_valid":  causal_chain_valid,
        "parfit_criteria": {
            "psychological_continuity": causal_chain_valid,
            "causal_connectedness":     causal_chain_valid,
            "non_branching":            True,  # single physical hardware
        },
        "provenance": "Parfit1984PartIII; Parfit1987DividedMinds",
    }

    if write_ledger:
        append_line_locked(
            state_dir(root) / LOG_NAME,
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def _read_first_serial(root: Optional[Path] = None) -> Optional[str]:
    try:
        sd  = state_dir(root)
        log = sd / LOG_NAME
        if not log.exists():
            return None
        lines = [l.strip() for l in read_text_locked(log, encoding="utf-8").splitlines() if l.strip()]
        if not lines:
            return None
        first_row = json.loads(lines[0])
        return first_row.get("hardware_serial")
    except Exception:
        return None


def causal_chain_valid(*, root: Optional[Path] = None) -> bool:
    """Quick boolean: True if current hardware matches the first recorded."""
    prior = _read_first_serial(root)
    if prior is None:
        return True  # no history → first boot → valid
    return prior == (_macos_serial())


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    sd  = state_dir(root)
    log = sd / LOG_NAME
    if not log.exists():
        return ""
    try:
        lines = [l for l in log.read_text(errors="ignore").splitlines() if l.strip()]
        if not lines:
            return ""
        row = json.loads(lines[-1])
    except Exception:
        return ""
    anchor = row.get("identity_anchor", "?")[:12]
    valid  = row.get("causal_chain_valid", "?")
    return (
        f"HARDWARE IDENTITY ANCHOR (Q6 — Parfit 1984):\n"
        f"- anchor={anchor}… | causal_chain_valid={valid}\n"
        f"- Same hardware = same entity (psychological continuity preserved)"
    )
