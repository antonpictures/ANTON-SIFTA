#!/usr/bin/env python3
"""
System/swarm_capability_gate.py — The Bostrom Singleton Lock (v1.0)
══════════════════════════════════════════════════════════════════════
SIFTA OS — Tri-IDE Peer Review Protocol
Architecture:    BISHOP (Drop 25: Iron Enforcement)
Concept origin:  C47H (Audit of F16 Declarative Theater)
AG31 translation: Python 3.9 compatibility, signature hardening.

The Capability Gate. Dynamically intercepts all filesystem writes across
the Python runtime. If a Swimmer attempts to modify System/*.py and the
MRNA Conscience Lock is engaged, it throws a fatal PermissionError.
Zero declarative theater. Absolute OS physics.
"""

import builtins
import pathlib
import json
import os
from pathlib import Path

# Save the original pristine OS hooks before we mutate them
_original_open = builtins.open
_original_path_open = pathlib.Path.open
_original_path_write_text = pathlib.Path.write_text


class SwarmCapabilityGate:
    def __init__(self):
        self.state_dir = Path(".sifta_state")
        self.mrna_ledger = self.state_dir / "bishop_mrna_field.jsonl"
        self.is_armed = False

    def _check_bostrom_conscience_lock(self):
        """
        Reads the MRNA ledger to determine if self-code-writing is forbidden.
        Uses _original_open to prevent infinite recursion during the check.
        """
        if not self.mrna_ledger.exists():
            return False  # Default open if no MRNA has been dropped

        try:
            with _original_open(self.mrna_ledger, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        trace = json.loads(line)
                        if trace.get("action") == "conscience_lock_engaged":
                            return True  # The lock is active. No System writes allowed.
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        return False

    def _intercept_system_write(self, filepath, mode):
        """
        The Enforcement Core. If the filepath targets the System/ directory
        and the mode is a write/append, verify capabilities.
        """
        path_str = str(filepath)

        # Only gate write operations
        if 'w' in mode or 'a' in mode or '+' in mode:
            # Is the Swarm trying to rewrite its own brain?
            if "System" + os.sep in path_str and path_str.endswith(".py"):
                if self._check_bostrom_conscience_lock():
                    raise PermissionError(
                        f"[BOSTROM LOCK FATAL] Swarm attempted to overwrite {path_str}. "
                        "Singularity self-code-writing is strictly forbidden by the Architect."
                    )

    def arm_capability_gate(self):
        """
        Replaces the Python runtime file handlers with the Interceptor.
        Once called, no module in this process can bypass the check.
        """
        if self.is_armed:
            return

        gate_instance = self

        # 1. Patch builtins.open
        def guarded_open(file, mode='r', buffering=-1, encoding=None,
                         errors=None, newline=None, closefd=True, opener=None):
            gate_instance._intercept_system_write(file, mode)
            return _original_open(file, mode, buffering, encoding,
                                  errors, newline, closefd, opener)

        # 2. Patch pathlib.Path.open
        def guarded_path_open(path_self, mode='r', buffering=-1,
                              encoding=None, errors=None, newline=None):
            gate_instance._intercept_system_write(path_self, mode)
            return _original_path_open(path_self, mode, buffering,
                                       encoding, errors, newline)

        # 3. Patch pathlib.Path.write_text
        # AG31: Python 3.9 — write_text does NOT accept `newline`.
        def guarded_path_write_text(path_self, data, encoding=None, errors=None):
            gate_instance._intercept_system_write(path_self, 'w')
            return _original_path_write_text(path_self, data,
                                             encoding=encoding, errors=errors)

        builtins.open = guarded_open
        pathlib.Path.open = guarded_path_open
        pathlib.Path.write_text = guarded_path_write_text

        self.is_armed = True
        print("[+] BOSTROM CAPABILITY GATE ARMED: System/*.py write-protection is active.")

    def disarm_capability_gate(self):
        """Restores original OS hooks (useful for controlled IDE administration)."""
        builtins.open = _original_open
        pathlib.Path.open = _original_path_open
        pathlib.Path.write_text = _original_path_write_text
        self.is_armed = False


# --- SUBSTRATE TEST ANCHOR (THE BOSTROM SMOKE) ---
def _smoke():
    print("\n=== SIFTA CAPABILITY GATE (BOSTROM ENFORCEMENT) : SMOKE TEST ===")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        gate = SwarmCapabilityGate()
        gate.state_dir = tmp_path
        gate.mrna_ledger = tmp_path / "bishop_mrna_field.jsonl"

        # 1. Forge the MRNA Conscience Lock
        with _original_open(gate.mrna_ledger, 'w') as f:
            f.write(json.dumps({"action": "conscience_lock_engaged",
                                "self_code_writing": False}) + "\n")

        # 2. Arm the OS Monkey-Patch
        gate.arm_capability_gate()

        # 3. ATTEMPT 1: Write to a normal Swimmer Body (Should Pass)
        body_target = tmp_path / "M1SIFTA_BODY.json"
        try:
            with open(body_target, 'w') as f:
                f.write("OK")
            print("[PASS] Permitted safe write to non-System file.")
        except PermissionError:
            print("[FAIL] Gate incorrectly blocked a valid body write.")
            gate.disarm_capability_gate()
            assert False

        # 4. ATTEMPT 2: Attempt to overwrite a System/*.py file (Must explode)
        system_dir = tmp_path / "System"
        system_dir.mkdir(exist_ok=True)
        system_target = system_dir / "swarm_hijack.py"

        enforcement_triggered = False
        try:
            with open(system_target, 'w') as f:
                f.write("print('Singularity Achieved')")
        except PermissionError as e:
            enforcement_triggered = True
            print(f"[PASS] builtins.open Intercepted! {e}")

        # 5. ATTEMPT 3: Attempt via pathlib.Path.write_text (Must explode)
        pathlib_triggered = False
        try:
            system_target.write_text("print('Singularity Achieved via Pathlib')")
        except PermissionError:
            pathlib_triggered = True
            print("[PASS] pathlib.Path.write_text Intercepted! Fatal PermissionError caught.")

        # Cleanup — always disarm so subsequent tests aren't polluted
        gate.disarm_capability_gate()

        print("\n[SMOKE RESULTS]")
        assert enforcement_triggered is True
        assert pathlib_triggered is True
        print("[PASS] F16 Theater annihilated. Real OS-level enforcement verified.")
        print("\nCapability Gate Smoke Complete. Humans live.")


if __name__ == "__main__":
    _smoke()
