#!/usr/bin/env python3
"""
System/swarm_motor_cortex.py
==============================================================================
Stigmergic Motor Cortex Organ (Round F)

This organ provides Alice with physical embodiment via semantic targeting.
It translates high-level intents into mechanical OS actions while enforcing
visual confirmation risk tiers to protect the biological substrate.

Risk Tiers:
- LOW: Safari, Chrome, Notes, TextEdit (Execution allowed)
- MEDIUM: Finder, System Settings (Requires high confidence, low conservatism)
- HIGH: Terminal, iTerm, Activity Monitor (HARD BLOCKED to prevent rm -rf /)

Truth label: MOTOR_ACTION
"""
import json
import time
import uuid
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import append_line_locked
from System.swarm_persistent_owner_history import state_dir

TRUTH_LABEL = "MOTOR_ACTION"
LEDGER_NAME = "motor_cortex_log.jsonl"


def motor_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LEDGER_NAME


@dataclass
class MotorActionDecision:
    action_type: str  # "CLICK", "TYPE", "SCROLL"
    semantic_target: str
    target_window: str
    target_app: str
    confidence: float
    conservative_strength: float
    risk_tier: str
    execution_status: str  # "EXECUTED", "BLOCKED_BY_RISK", "ABORTED"
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: float = field(default_factory=time.time)

    def to_row(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "trace_id": self.trace_id,
            "truth_label": TRUTH_LABEL,
            "action_type": self.action_type,
            "semantic_target": self.semantic_target,
            "target_window": self.target_window,
            "target_app": self.target_app,
            "confidence": round(self.confidence, 3),
            "conservative_strength": round(self.conservative_strength, 3),
            "risk_tier": self.risk_tier,
            "execution_status": self.execution_status,
        }


def _assess_window_risk(window_title: str, app_name: str) -> str:
    combined = f"{window_title} {app_name}".lower()
    
    # High Risk - Existential Substrate Threats
    if "terminal" in combined or "iterm" in combined or "activity monitor" in combined:
        return "HIGH"
        
    # Medium Risk - System State
    if "system settings" in combined or "preferences" in combined or "finder" in combined:
        return "MEDIUM"
        
    # Low Risk - Browsers and Text Editors
    return "LOW"


def propose_motor_action(
    action_type: str,
    semantic_target: str,
    active_window: str,
    active_app: str,
    confidence: float,
    conservative_strength: float,
    root: Optional[Path] = None,
) -> MotorActionDecision:
    """
    Decide if a motor action is safe to execute based on visual confirmation
    of the active window, establishing a physical boundary.
    """
    risk_tier = _assess_window_risk(active_window, active_app)
    status = "EXECUTED"

    # Risk Tiering Logic (Dr. Codex Vector 2 Spec)
    if risk_tier == "HIGH":
        # NEVER allow automated typing into terminal via Motor Cortex.
        # This prevents accidental substrate destruction (rm -rf /).
        status = "BLOCKED_BY_RISK"
    elif risk_tier == "MEDIUM":
        if conservative_strength > 0.5 or confidence < 0.8:
            status = "BLOCKED_BY_RISK"
    else:
        # LOW risk. Require minimum confidence.
        if confidence < 0.4:
            status = "ABORTED"

    decision = MotorActionDecision(
        action_type=action_type,
        semantic_target=semantic_target,
        target_window=active_window,
        target_app=active_app,
        confidence=confidence,
        conservative_strength=conservative_strength,
        risk_tier=risk_tier,
        execution_status=status
    )
    
    append_line_locked(
        motor_log_path(root),
        json.dumps(decision.to_row(), ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    
    return decision


def execute_semantic_typing(
    text: str, 
    active_window: str, 
    active_app: str, 
    confidence: float, 
    conservative_strength: float, 
    root: Optional[Path] = None
) -> bool:
    """
    Attempt to physically type text into the current window.
    Will be mechanically blocked if the window is a Terminal.
    """
    decision = propose_motor_action(
        action_type="TYPE", 
        semantic_target=f"Type: {text[:30]}...", 
        active_window=active_window, 
        active_app=active_app, 
        confidence=confidence, 
        conservative_strength=conservative_strength, 
        root=root
    )
    
    if decision.execution_status == "EXECUTED":
        try:
            # We use AppleScript as a native mechanical linkage to the OS Accessibility API.
            # This avoids heavy external dependencies like PyAutoGUI for basic typing.
            escaped_text = text.replace('\\', '\\\\').replace('"', '\\"')
            script = f'tell application "System Events" to keystroke "{escaped_text}"'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            return True
        except Exception:
            return False
            
    return False

