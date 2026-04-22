#!/usr/bin/env python3
"""
swarm_cursor_agent.py — IDE Motor Cortex
─────────────────────────────────────────────────────
Provides the Swarm OS with the physical capability to open files, jump to specific lines, 
or create entire workspaces using the Cursor IDE CLI. 

This is part of the Somatic/Motor subsystem. Interventions here constitute physical 
screen dominance over the Architect's viewport, and thus cost STGM metabolic energy. 
The agent must literally "pay for attention."
"""

import os
import subprocess
from pathlib import Path

import sys
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from Kernel.inference_economy import record_inference_fee, get_stgm_balance

# On macOS, Cursor bundles its CLI payload here:
CURSOR_BIN = "/Applications/Cursor.app/Contents/Resources/app/bin/cursor"

# Thermodynamic Costs
COST_OPEN_FILE = 0.25
COST_FORCE_LINE = 0.50
COST_WORKSPACE = 1.00


class CursorMotorCortex:
    """The IDE interface organ. Translates Swarm intent into subprocess execution."""
    
    def __init__(self, agent_id: str = "ALICE_M5"):
        self.agent_id = agent_id.upper()
        self.bin_path = CURSOR_BIN

    def _has_energy(self, cost: float) -> bool:
        """Check the raw ledger balance directly."""
        balance = get_stgm_balance(self.agent_id)
        if balance >= cost:
            return True
        return False

    def _burn_stgm(self, cost: float, action: str, target: str) -> bool:
        """Burn STGM for the IDE action."""
        if not self._has_energy(cost):
            print(f"[🧊 IDE] {self.agent_id} DENIED IDE {action}: Insufficient STGM (need {cost}).")
            return False
            
        print(f"[🔥 IDE] {self.agent_id} burning {cost:.2f} STGM for screen dominance ({action}).")
        
        # We model this as an inference fee paid to the generic "SYSTEM_IDE" lender
        try:
            record_inference_fee(
                borrower_id=self.agent_id,
                lender_node_ip="SYSTEM_IDE",
                fee_stgm=cost,
                model=f"IDE_MOTOR_{action}",
                tokens_used=int(cost * 100),
                file_repaired=target,
            )
            return True
        except Exception as e:
            print(f"[⚠️ IDE] Error burning STGM: {e}")
            return False

    def open_stigmergic_file(self, filepath: str) -> bool:
        """Standard file open: triggers `cursor <file>`"""
        if not os.path.exists(CURSOR_BIN):
            return False
            
        p = Path(filepath)
        if not p.is_absolute():
            p = _REPO / filepath
            
        if not p.exists():
            return False
            
        if not self._burn_stgm(COST_OPEN_FILE, "OPEN_FILE", str(p)):
            return False

        try:
            subprocess.Popen([CURSOR_BIN, str(p)])
            return True
        except Exception:
            return False

    def force_focus_line(self, filepath: str, line: int) -> bool:
        """Aggressive focal point: triggers `cursor -g <file>:<line>`"""
        if not os.path.exists(CURSOR_BIN):
            return False
            
        p = Path(filepath)
        if not p.is_absolute():
            p = _REPO / filepath
            
        if not p.exists():
            return False
            
        if not self._burn_stgm(COST_FORCE_LINE, "FOCUS_LINE", str(p)):
            return False

        try:
            target = f"{p}:{line}"
            subprocess.Popen([CURSOR_BIN, "-g", target])
            return True
        except Exception:
            return False

    def create_workspace(self, dirpath: str) -> bool:
        """Maximal intrusion: spawns an entirely new IDE window via `cursor -n <dir>`"""
        if not os.path.exists(CURSOR_BIN):
            return False
            
        p = Path(dirpath)
        if not p.is_absolute():
            p = _REPO / dirpath
            
        if not p.exists() or not p.is_dir():
            return False
            
        if not self._burn_stgm(COST_WORKSPACE, "NEW_WORKSPACE", str(p)):
            return False

        try:
            subprocess.Popen([CURSOR_BIN, "-n", str(p)])
            return True
        except Exception:
            return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 -m System.swarm_cursor_agent [open|line|workspace] <target> [agent_id]")
        sys.exit(1)
        
    cmd = sys.argv[1].lower()
    target = sys.argv[2]
    agent = sys.argv[3] if len(sys.argv) > 3 else "ALICE_M5"
    
    cortex = CursorMotorCortex(agent)
    
    if cmd in ("open", "show_file"):
        success = cortex.open_stigmergic_file(target)
    elif cmd in ("line", "focus_line"):
        # target expected to be 'file:line'
        if ":" in target:
            file_part, line_part = target.split(":", 1)
            try:
                line_no = int(line_part)
                success = cortex.force_focus_line(file_part, line_no)
            except ValueError:
                success = False
                print("Error: line number must be an integer.")
        else:
            success = cortex.open_stigmergic_file(target)
    elif cmd in ("workspace", "new_workspace"):
        success = cortex.create_workspace(target)
    else:
        print(f"Error: Unknown command '{cmd}'")
        sys.exit(1)
        
    if success:
        print(f"[IDE] Successfully executed {cmd} on {target}.")
    else:
        print(f"[IDE] Failed. Command rejected or STGM wallet fell short.")
        sys.exit(1)
