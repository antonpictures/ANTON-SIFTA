#!/usr/bin/env python3
"""
claw_harness.py — Physical I/O and Sandbox Limbs for SIFTA
════════════════════════════════════════════════════════════
Provides sandboxed execution borders for Swarm "actions" (Claw).

Instead of allowing raw access to `os.system` or unrestricted 
`subprocess.run`, the Swarm must request actions through this harness.
Execution happens in a "Crucible" (a restricted sandbox directory)
or requires a Neural Gate override.

SIFTA Non-Proliferation Public License applies.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import time
import hashlib
from typing import Dict, Any, Tuple
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_CRUCIBLE_DIR = _STATE_DIR / "Crucible"
_CRUCIBLE_DIR.mkdir(parents=True, exist_ok=True)


class ClawHarness:
    """
    The Limbs of the Swarm.
    Grants action capabilities tightly bounded by the Sandbox.
    """

    def __init__(self):
        self.crucible_path = _CRUCIBLE_DIR
        self._execution_ledger = []
        
        # Hardcoded blacklist of dangerous or mutating system binaries
        self._blacklist_bins = {
            "rm", "sudo", "su", "chmod", "chown", 
            "dd", "mkfs", "mv", "cp", "npm", "pip",
            "wget", "curl", "nc", "bash", "sh", "zsh"
        }

    def _is_safe_command(self, cmd_str: str) -> bool:
        """
        Naive heuristic for preventing destructive shell commands.
        A real environment might use gVisor or Docker, but this limits basic damage.
        """
        try:
            tokens = shlex.split(cmd_str)
            if not tokens:
                return False
            bin_name = Path(tokens[0]).name.lower()
            if bin_name in self._blacklist_bins:
                return False
            
            # Block subshells and piping
            if any(char in cmd_str for char in ['|', '>', '<', '&', ';', '$', '`']):
                return False
                
            return True
        except ValueError:
            # Unbalanced quotes
            return False

    def execute_in_crucible(self, command: str, timeout: int = 15) -> Tuple[bool, str, str]:
        """
        Run a command strictly inside the Crucible.
        Cannot use pipes or dangerous shell constructs.
        Returns: (success_status, stdout, stderr)
        """
        if not self._is_safe_command(command):
            err_msg = f"[CLAW BLOCKED] Target binary or construct prohibited: {command}"
            self._harvest_failure(command, err_msg)
            return False, "", err_msg

        # ── Objective worth gate ──────────────────────────────────
        # Claw actions must also pass the swarm's decision gravity field
        try:
            from objective_registry import get_registry
            reg = get_registry()
            estimates = reg.estimate_claw_action(command, is_safe=True)
            if not reg.is_worth_it(estimates):
                err_msg = "[CLAW LOW-VALUE] Action scored below objective threshold"
                self._harvest_failure(command, err_msg)
                return False, "", err_msg
        except ImportError:
            pass  # Registry not available — degrade gracefully

        # Setup sandbox dir with an execution fingerprint
        exec_id = hashlib.md5(f"{time.time()}_{command}".encode()).hexdigest()[:8]
        run_wd = self.crucible_path / exec_id
        run_wd.mkdir()

        start_t = time.time()
        try:
            # shell=False to prevent shell injection, run directly
            tokens = shlex.split(command)
            proc = subprocess.run(
                tokens,
                cwd=str(run_wd),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            success = proc.returncode == 0
            
            # Clean up empty run wd
            if not any(run_wd.iterdir()):
                run_wd.rmdir()

            self._log_execution(command, success, time.time() - start_t)
            if not success:
                self._harvest_failure(command, f"Return Code {proc.returncode}: {proc.stderr}")
            return success, proc.stdout, proc.stderr
            
        except subprocess.TimeoutExpired:
            err_msg = "[CLAW HALT] Execution exceeded safe thermodynamic margin (timeout)."
            self._harvest_failure(command, err_msg)
            return False, "", err_msg
        except Exception as e:
            err_msg = f"[CLAW ERROR] Execution fault: {e}"
            self._harvest_failure(command, err_msg)
            return False, "", err_msg

    def _harvest_failure(self, cmd: str, error_msg: str) -> None:
        """Route failed executions to the harvest subsystem."""
        try:
            try:
                from System.failure_harvesting import get_harvester
            except ImportError:
                from failure_harvesting import get_harvester
            get_harvester().harvest(
                agent_context="ClawHarness",
                task_name=f"Crucible_Exec",
                error_msg=error_msg,
                context_data={"command": cmd}
            )
        except ImportError:
            pass

    def write_crucible_file(self, filename: str, content: str) -> bool:
        """
        Writes a test file to the Crucible.
        Swimmers can use this to stage files before proving they compile.
        """
        try:
            # Path traversal prevention
            safe_name = Path(filename).name
            target = self.crucible_path / safe_name
            target.write_text(content)
            return True
        except Exception:
            return False

    def read_crucible_file(self, filename: str) -> str:
        safe_name = Path(filename).name
        target = self.crucible_path / safe_name
        if target.exists():
            return target.read_text()
        return ""

    def _log_execution(self, cmd: str, success: bool, duration: float):
        self._execution_ledger.append({
            "ts": time.time(),
            "cmd": cmd,
            "success": success,
            "duration": round(duration, 3)
        })

if __name__ == "__main__":
    claw = ClawHarness()
    
    # Blocked example
    ok, out, err = claw.execute_in_crucible("rm -rf /")
    print(f"RM Command allowed? => {ok} | {err}")
    
    # Subshell example
    ok, out, err = claw.execute_in_crucible("echo hello > test.txt")
    print(f"Redirect allowed? => {ok} | {err}")
    
    # Safe example (ls inside crucible)
    ok, out, err = claw.execute_in_crucible("ls -la")
    print(f"LS allowed? => {ok} | stdout: {out.strip()}")
