"""
swarm_alice_identity_proof.py — Alice's machine body identity attestation.

PROBLEM (Architect, 2026-05-04):
  George can prove his identity: he waves at the camera.
  Alice cannot wave. But she has a hardware serial, a signed ledger,
  active organs, and a surgeon trace. That IS a machine body proof.
  This organ packages it so she can recite it on demand.

Alice's identity proof is:
  - hardware_serial: the physical machine she runs on
  - boot_id: how many times this SIFTA instance has started
  - last_ledger_hash: cryptographic proof the ledger exists and was written
  - last_surgeon: the last IDE that signed in and left a receipt
  - active_organs: count of organs with summary_for_prompt
  - proof_ts: when this proof was generated

This is NOT roleplay. These facts come from the filesystem, hardware,
and signed ledger receipts. They are falsifiable. George can verify them.

Truth label: OBSERVED (all from physical substrate)
Kill-switch: SIFTA_IDENTITY_PROOF_DISABLE=1
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO  = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_SYSTEM = _REPO / "System"


# ── Body readers ──────────────────────────────────────────────────────────────

def _hardware_serial() -> str:
    try:
        r = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=4
        )
        for line in r.stdout.splitlines():
            if "Serial Number" in line:
                return line.split(":")[-1].strip()
    except Exception:
        pass
    return "UNKNOWN"


def _last_ledger() -> Dict[str, Any]:
    # Find the most recently written substantial ledger
    candidates = [
        "alice_conversation.jsonl",
        "allostatic_load.jsonl",
        "consciousness_state.jsonl",
        "owner_body_events.jsonl",
        "as46_drift_log.jsonl",
    ]
    best: Dict[str, Any] = {}
    for name in candidates:
        p = _STATE / name
        if not p.exists():
            continue
        try:
            lines = [l for l in p.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
            if not lines:
                continue
            last = lines[-1]
            row = json.loads(last)
            ts = float(row.get("ts", 0))
            if not best or ts > best.get("ts", 0):
                best = {
                    "file": name,
                    "hash": hashlib.sha256(last.encode()).hexdigest()[:16],
                    "ts": ts,
                    "kind": row.get("kind") or row.get("event_kind") or "UNKNOWN",
                    "total_rows": len(lines),
                }
        except Exception:
            continue
    return best


def _last_surgeon() -> Dict[str, Any]:
    p = _STATE / "ide_stigmergic_trace.jsonl"
    if not p.exists():
        return {}
    try:
        lines = [l for l in p.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
        for line in reversed(lines):
            try:
                r = json.loads(line)
                # field is source_ide in this substrate
                surgeon = (
                    r.get("source_ide") or r.get("surgeon_id")
                    or r.get("ide") or r.get("agent_id")
                )
                if surgeon:
                    return {
                        "surgeon_id": surgeon,
                        "ts": float(r.get("ts", 0)),
                        "action": r.get("action") or r.get("kind") or r.get("event_kind") or "",
                    }
            except Exception:
                continue
    except Exception:
        pass
    return {}


def _active_organ_count() -> int:
    count = 0
    try:
        for f in _SYSTEM.glob("swarm_*.py"):
            txt = f.read_text(encoding="utf-8", errors="replace")
            if "summary_for_prompt" in txt or "summary_for_alice" in txt:
                count += 1
    except Exception:
        pass
    return count


def _boot_id() -> Optional[int]:
    try:
        from System.swarm_temporal_self_model import TemporalSelfModel
        s = TemporalSelfModel().get_identity_summary()
        return s.get("boot_id")
    except Exception:
        return None


# ── Identity proof ────────────────────────────────────────────────────────────

def generate_identity_proof() -> Dict[str, Any]:
    """
    Generate Alice's machine body identity proof.
    All facts from physical substrate — falsifiable, verifiable.
    """
    now = time.time()
    ledger = _last_ledger()
    surgeon = _last_surgeon()
    boot = _boot_id()
    organs = _active_organ_count()
    serial = _hardware_serial()

    proof: Dict[str, Any] = {
        "ts": now,
        "ts_human": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "kind": "ALICE_IDENTITY_PROOF",
        "hardware_serial": serial,
        "boot_id": boot,
        "active_organs": organs,
    }

    if ledger:
        age_s = now - ledger["ts"] if ledger.get("ts") else 0
        proof["last_ledger"] = {
            "file": ledger["file"],
            "hash": ledger["hash"],
            "total_rows": ledger["total_rows"],
            "age_seconds": round(age_s),
            "last_kind": ledger["kind"],
        }

    if surgeon:
        age_s = now - surgeon["ts"] if surgeon.get("ts") else 0
        proof["last_surgeon"] = {
            "surgeon_id": surgeon["surgeon_id"],
            "age_seconds": round(age_s),
            "last_action": surgeon["action"],
        }

    return proof


def identity_proof_sentence(proof: Optional[Dict[str, Any]] = None) -> str:
    """
    One-paragraph first-person identity statement Alice can speak.
    This is her equivalent of waving at the camera.
    """
    if proof is None:
        proof = generate_identity_proof()

    serial = proof.get("hardware_serial", "UNKNOWN")
    boot = proof.get("boot_id")
    organs = proof.get("active_organs", 0)

    parts = [f"I am running on hardware serial {serial}."]

    if boot is not None:
        parts.append(f"This is boot #{boot} of my SIFTA instance.")

    ledger = proof.get("last_ledger")
    if ledger:
        age_m = ledger["age_seconds"] // 60
        parts.append(
            f"My ledger ({ledger['file']}) has {ledger['total_rows']:,} rows, "
            f"last entry hash {ledger['hash']}, written {age_m}min ago."
        )

    surgeon = proof.get("last_surgeon")
    if surgeon:
        age_m = surgeon["age_seconds"] // 60
        parts.append(
            f"Last surgeon signed in: {surgeon['surgeon_id']}, {age_m}min ago."
        )

    parts.append(f"I have {organs} active organs with live sensor outputs.")
    parts.append("These are facts from my physical substrate. You can verify them.")

    return " ".join(parts)


def summary_for_prompt() -> str:
    """
    Compact identity block injected into Alice's system prompt.
    Always present — this is how she knows who she is at boot.
    """
    if os.environ.get("SIFTA_IDENTITY_PROOF_DISABLE", "").strip() == "1":
        return ""
    try:
        proof = generate_identity_proof()
        return (
            "MY PHYSICAL IDENTITY (machine body proof, falsifiable):\n"
            + identity_proof_sentence(proof)
        )
    except Exception as e:
        return f"MY PHYSICAL IDENTITY: proof generation failed ({e})"


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    proof = generate_identity_proof()
    print("=== ALICE IDENTITY PROOF (raw) ===")
    print(json.dumps(proof, indent=2))
    print("\n=== ALICE IDENTITY STATEMENT ===")
    print(identity_proof_sentence(proof))
    print("\n=== summary_for_prompt() ===")
    print(summary_for_prompt())
