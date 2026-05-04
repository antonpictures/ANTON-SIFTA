#!/usr/bin/env python3
"""
System/swarm_horizontal_stigmergy.py
══════════════════════════════════════════════════════════════════════
Pheromonal Federation / Node Sovereignty

This module handles Horizontal Stigmergy between nodes (e.g., M5 vs M1).
Instead of sharing raw memory loops, nodes broadcast highly stable
crystallized skills and engrams as "boundary summaries".

Foreign boundary engrams are ingested into the local context without
triggering local execution costs.
"""
from __future__ import annotations

import json
import time
import uuid
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_COMPRESSION_DB = _STATE_DIR / "crystallized_skills.json"
_BOUNDARY_LEDGER = _STATE_DIR / "boundary_engrams.jsonl"
_FOREIGN_ENGRAMS_CACHE = _STATE_DIR / "foreign_boundary_engrams.json"

SCHEMA_VERSION = "event101.horizontal_stigmergy.v1"


def _get_node_serial() -> str:
    """Return hardware serial or UNKNOWN fallback."""
    try:
        res = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=2
        )
        for line in res.stdout.splitlines():
            if "Serial Number" in line:
                return line.split(":")[-1].strip()
    except Exception:
        pass
    return "UNKNOWN_NODE"


@dataclass(frozen=True)
class BoundaryEngram:
    kind: str
    schema_version: str
    boundary_id: str
    ts: float
    node_serial: str
    source_type: str  # "skill_primitive" or "dream_engram"
    signature: str
    stability: float
    usage_count: int
    payload: Dict[str, Any]
    truth_label: str = "BOUNDARY_SUMMARY"

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HorizontalStigmergyEngine:
    def __init__(self, state_dir: Optional[Path] = None):
        self.state_dir = Path(state_dir) if state_dir is not None else _STATE_DIR
        self.compression_db = self.state_dir / _COMPRESSION_DB.name
        self.boundary_ledger = self.state_dir / _BOUNDARY_LEDGER.name
        self.foreign_cache = self.state_dir / _FOREIGN_ENGRAMS_CACHE.name
        self.node_serial = _get_node_serial()

    def export_stable_skills(self, stability_threshold: float = 0.8) -> int:
        """Read local skills, broadcast the most stable ones to the boundary ledger."""
        if not self.compression_db.exists():
            return 0
            
        try:
            data = json.loads(self.compression_db.read_text(encoding="utf-8"))
        except Exception:
            return 0
            
        exported = 0
        for skill_id, skill_data in data.items():
            stability = float(skill_data.get("stability", 0.0))
            if stability >= stability_threshold and not skill_data.get("quarantined"):
                engram = BoundaryEngram(
                    kind="boundary_engram",
                    schema_version=SCHEMA_VERSION,
                    boundary_id=str(uuid.uuid4()),
                    ts=time.time(),
                    node_serial=self.node_serial,
                    source_type="skill_primitive",
                    signature=skill_data.get("pattern_signature", ""),
                    stability=stability,
                    usage_count=int(skill_data.get("usage_count", 0)),
                    payload=skill_data.get("example_payload", {}),
                )
                append_line_locked(self.boundary_ledger, json.dumps(engram.as_dict(), sort_keys=True) + "\n")
                exported += 1
                
        return exported

    def import_foreign_engrams(self) -> int:
        """Read the boundary ledger and cache engrams from other nodes."""
        if not self.boundary_ledger.exists():
            return 0
            
        foreign_engrams: Dict[str, Dict[str, Any]] = {}
        
        # Keep previously cached foreign engrams
        if self.foreign_cache.exists():
            try:
                foreign_engrams = json.loads(self.foreign_cache.read_text(encoding="utf-8"))
            except Exception:
                pass
                
        imported = 0
        try:
            lines = self.boundary_ledger.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("node_serial") != self.node_serial:
                    sig = row.get("signature")
                    if sig and sig not in foreign_engrams:
                        foreign_engrams[sig] = row
                        imported += 1
        except Exception:
            pass
            
        if imported > 0:
            self.foreign_cache.write_text(json.dumps(foreign_engrams, indent=2, sort_keys=True))
            
        return imported


if __name__ == "__main__":
    engine = HorizontalStigmergyEngine()
    print("Exporting highly stable skills to boundary ledger...")
    num_exported = engine.export_stable_skills()
    print(f"Exported: {num_exported}")
    
    print("Importing foreign engrams...")
    num_imported = engine.import_foreign_engrams()
    print(f"Imported: {num_imported}")
