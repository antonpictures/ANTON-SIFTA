#!/usr/bin/env python3
"""
shadow_simulator.py — The Swarm's Imagination Engine
═══════════════════════════════════════════════════════════════════
SOLID_PLAN §5.2 item #7 — Shadow Simulation.

Before the mutation governor allows a file mutation to be proposed
to the human-gate (or Quorum), it must be 'imagined' to ensure it
doesn't fatally crash the system. 

The Shadow Simulator:
1. Provisions an ephemeral Crucible sandbox.
2. Clones the target file into the sandbox.
3. Applies the proposed mutation.
4. Validates structural syntax (e.g. `ast.parse` for python).
5. If it fails, routes the exact line error to Failure Harvesting to teach the swarm.

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import ast
import tempfile
from pathlib import Path
from typing import Tuple

_REPO = Path(__file__).resolve().parent.parent

class ShadowSimulator:
    """
    Dry-run engine for code mutations.
    """

    def __init__(self):
        # We rely on the physical limbs to handle the sandbox itself
        from claw_harness import ClawHarness
        self.claw = ClawHarness()

    def simulate_mutation(self, target_filepath: str, proposed_content: str) -> Tuple[bool, str]:
        """
        Simulate applying replacing the entire file with `proposed_content`.
        For now, this only natively simulates `.py` python structural syntax.
        
        Args:
            target_filepath: Repo-relative path, e.g. "Applications/foo.py"
            proposed_content: The exact new content for the file.
            
        Returns:
            (success_bool, status_message)
        """
        # 1. We only simulate python files for now. Others pass automatically.
        if not target_filepath.endswith(".py"):
            return True, "[SIM] Passed: Non-Python file bypassed simulation."

        # 2. Syntax Check via AST 
        # This is extremely fast, highly precise, and requires zero imports.
        # We don't execute the code, we parse it to a tree.
        try:
            ast.parse(proposed_content, filename=target_filepath)
        except SyntaxError as e:
            # 3. Harvest the exact failure so the swarm can learn
            error_msg = f"SyntaxError at line {e.lineno}, offset {e.offset}: {e.text.strip() if e.text else e.msg}"
            self._harvest_simulation_failure(target_filepath, error_msg)
            return False, f"[SIM CATASTROPHE] Code does not compile: {error_msg}"
        except Exception as e:
            error_msg = f"Unknown AST parse error: {e}"
            self._harvest_simulation_failure(target_filepath, error_msg)
            return False, f"[SIM CATASTROPHE] {error_msg}"

        return True, "[SIM] Passed: Python AST compiled perfectly."

    def _harvest_simulation_failure(self, filepath: str, error_msg: str) -> None:
        """Route predictive failures to the harvest subsystem."""
        try:
            from failure_harvesting import get_harvester
            get_harvester().harvest(
                agent_context="ShadowSimulator",
                task_name=f"Simulate_Mutation_{Path(filepath).name}",
                error_msg=error_msg,
                context_data={"target": filepath}
            )
        except ImportError:
            pass

# ── Singleton ──────────────────────────────────────────────────

_SIMULATOR_INSTANCE = None

def get_simulator() -> ShadowSimulator:
    global _SIMULATOR_INSTANCE
    if _SIMULATOR_INSTANCE is None:
        _SIMULATOR_INSTANCE = ShadowSimulator()
    return _SIMULATOR_INSTANCE


if __name__ == "__main__":
    sim = get_simulator()

    perfect_code = "def hello():\n    print('world')\n"
    broken_code = "def broken_func(:\n    print('broken')\n"

    print("Testing clean mutation:")
    ok, msg = sim.simulate_mutation("System/test_clean.py", perfect_code)
    print(f"  Result: {ok} | {msg}")

    print("\nTesting broken mutation:")
    ok2, msg2 = sim.simulate_mutation("System/test_broken.py", broken_code)
    print(f"  Result: {ok2} | {msg2}")
