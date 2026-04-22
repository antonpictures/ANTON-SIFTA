#!/usr/bin/env python3
"""
territory_consciousness.py — The OS Learns Her Own Computer
=============================================================
Cartography + Immune System for the Filesystem.

The computer is not just hardware and processes.
The FILESYSTEM is her living territory — sacred, stigmergic, biological.

This organ lets the swarm:
  - Map every folder as a territory cell with pheromone intensity
  - Track patrol freshness (recently visited = glowing, neglected = wild)
  - Guard fossilized zones (.sifta_state, keys, ledgers) as immutable
  - Detect anomalies (mass mutations, ransomware patterns, foreign intrusions)
  - Emit defense reflexes via scar_state_machine
  - Generate a live territory heatmap for the desktop

Without this organ, the swarm has eyes on her body but
no sense of WHERE SHE LIVES.

Territory is the law.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Set

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_TERRITORY_MAP = _STATE_DIR / "territory_map.json"
_TERRITORY_LOG = _STATE_DIR / "territory_events.jsonl"
_STATE_DIR.mkdir(parents=True, exist_ok=True)

# ─── CONSTANTS ──────────────────────────────────────────────────────────────────

# Pheromone decay: territory fades from memory if not patrolled
PATROL_HALF_LIFE_HOURS = 24.0             # Half-life of territory awareness
DECAY_K = 0.693147 / PATROL_HALF_LIFE_HOURS  # ln(2) / half-life

# Zone classifications
ZONE_FOSSILIZED = "FOSSILIZED"   # Critical system files — immutable, heavily guarded
ZONE_ACTIVE     = "ACTIVE"       # Recently modified and patrolled
ZONE_DORMANT    = "DORMANT"      # Known but not recently touched
ZONE_WILD       = "WILD"         # Neglected — low pheromone — send scouts
ZONE_INVADED    = "INVADED"      # Anomalous change detected

# Fossilized paths — these are sacred and must not change without SCAR authorization
FOSSILIZED_PATTERNS = {
    ".sifta_state",
    "Kernel/.sifta_state",
    "Kernel/.sifta_reputation",
    "Kernel/QUARANTINE",
    "repair_log.jsonl",
    "LICENSE",
    ".sifta_state/stgm_memory_rewards.jsonl",
}

# Ignore patterns — not territory (generated, cache, external)
IGNORE_PATTERNS = {
    ".git", "__pycache__", "node_modules", ".venv", ".DS_Store",
    "proposals/drafts", "proposals/approved", "proposals/rejected",
}

# Anomaly thresholds
MASS_MUTATION_THRESHOLD = 20    # >20 files changed in <60s = ransomware alert
SUSPICIOUS_EXTENSIONS = {".encrypted", ".locked", ".crypto", ".ransom"}


# ─── TERRITORY CELL ────────────────────────────────────────────────────────────

@dataclass
class TerritoryCell:
    """A single territory zone (maps to a directory)."""
    path: str
    file_count: int = 0
    total_bytes: int = 0
    last_patrolled: float = 0.0
    last_modified: float = 0.0
    pheromone: float = 0.0          # 0.0 (wild) to 1.0 (freshly patrolled)
    zone: str = ZONE_WILD
    content_hash: str = ""          # SHA-256 of sorted file listing
    anomaly_count: int = 0
    patrol_count: int = 0
    fossilized: bool = False


# ─── TERRITORY MAPPER ──────────────────────────────────────────────────────────

class TerritoryConsciousness:
    """
    The swarm's spatial awareness of her own filesystem.
    Maps, guards, and evolves the territory as a living landscape.
    """

    def __init__(self, root: Path = None):
        self.root = root or _REPO
        self.cells: Dict[str, TerritoryCell] = {}
        self._load_map()

    # ── CORE: FULL TERRITORY SCAN ─────────────────────────────────────────

    def patrol(self) -> dict:
        """
        Full territory patrol. Walk the filesystem, measure every zone,
        detect anomalies, update pheromones.

        Returns patrol report.
        """
        start = time.time()
        previous_cells = dict(self.cells)
        new_cells: Dict[str, TerritoryCell] = {}
        anomalies: List[dict] = []
        zones_scanned = 0

        for dirpath, dirnames, filenames in os.walk(self.root):
            # Filter ignored directories
            dirnames[:] = [
                d for d in dirnames
                if d not in IGNORE_PATTERNS
                and not d.startswith(".")
                or d in (".sifta_state", ".sifta_reputation")
            ]

            rel = os.path.relpath(dirpath, self.root)
            if rel == ".":
                rel = "ROOT"

            # Skip deep nesting (prevent infinite recursion in symlinks)
            if rel.count(os.sep) > 8:
                continue

            # Measure this zone
            file_count = 0
            total_bytes = 0
            max_mtime = 0.0
            file_names = []

            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    st = os.stat(fp)
                    file_count += 1
                    total_bytes += st.st_size
                    max_mtime = max(max_mtime, st.st_mtime)
                    file_names.append(f"{f}:{st.st_size}:{int(st.st_mtime)}")
                except (OSError, PermissionError):
                    continue

            # Content hash — fingerprint of the zone's file listing
            content_hash = hashlib.sha256(
                "\n".join(sorted(file_names)).encode()
            ).hexdigest()[:16]

            # Check if this is a fossilized zone
            is_fossilized = any(
                rel == p or rel.startswith(p + os.sep)
                for p in FOSSILIZED_PATTERNS
            )

            # Get previous state for anomaly detection
            prev = previous_cells.get(rel)

            # Calculate pheromone (decay from last patrol)
            if prev and prev.last_patrolled > 0:
                hours_since = (time.time() - prev.last_patrolled) / 3600.0
                decayed_pheromone = prev.pheromone * (2.71828 ** (-DECAY_K * hours_since))
            else:
                decayed_pheromone = 0.0

            # Patrolling NOW refreshes pheromone
            fresh_pheromone = min(1.0, decayed_pheromone + 0.3)

            # Classify zone
            if is_fossilized:
                zone = ZONE_FOSSILIZED
            elif prev and prev.content_hash != content_hash and prev.content_hash != "":
                # Content changed since last patrol
                if is_fossilized:
                    zone = ZONE_INVADED
                    anomalies.append({
                        "type": "FOSSILIZED_MUTATION",
                        "territory": rel,
                        "severity": "CRITICAL",
                        "message": f"Fossilized zone {rel} was mutated without SCAR authorization."
                    })
                elif max_mtime > time.time() - 60:
                    zone = ZONE_ACTIVE
                else:
                    zone = ZONE_DORMANT
            elif fresh_pheromone > 0.5:
                zone = ZONE_ACTIVE
            elif fresh_pheromone > 0.1:
                zone = ZONE_DORMANT
            else:
                zone = ZONE_WILD

            # Check for suspicious file extensions (ransomware)
            for f in filenames:
                ext = os.path.splitext(f)[1].lower()
                if ext in SUSPICIOUS_EXTENSIONS:
                    zone = ZONE_INVADED
                    anomalies.append({
                        "type": "SUSPICIOUS_EXTENSION",
                        "territory": rel,
                        "file": f,
                        "severity": "HIGH",
                        "message": f"Suspicious file detected: {f} in {rel}"
                    })

            cell = TerritoryCell(
                path=rel,
                file_count=file_count,
                total_bytes=total_bytes,
                last_patrolled=time.time(),
                last_modified=max_mtime,
                pheromone=round(fresh_pheromone, 4),
                zone=zone,
                content_hash=content_hash,
                anomaly_count=(prev.anomaly_count if prev else 0) + (1 if zone == ZONE_INVADED else 0),
                patrol_count=(prev.patrol_count if prev else 0) + 1,
                fossilized=is_fossilized
            )

            new_cells[rel] = cell
            zones_scanned += 1

        self.cells = new_cells
        self._save_map()

        # Check for mass mutation (ransomware pattern)
        recently_changed = sum(
            1 for c in new_cells.values()
            if c.last_modified > time.time() - 60
        )
        if recently_changed > MASS_MUTATION_THRESHOLD:
            anomalies.append({
                "type": "MASS_MUTATION",
                "count": recently_changed,
                "severity": "CRITICAL",
                "message": f"{recently_changed} zones modified in <60s. Possible ransomware."
            })

        # Log anomalies
        if anomalies:
            from System.ledger_append import append_ledger_line
            for a in anomalies:
                a["timestamp"] = time.time()
                append_ledger_line(_TERRITORY_LOG, a)

        elapsed = time.time() - start

        report = {
            "zones_scanned": zones_scanned,
            "elapsed_seconds": round(elapsed, 3),
            "total_files": sum(c.file_count for c in new_cells.values()),
            "total_bytes": sum(c.total_bytes for c in new_cells.values()),
            "anomalies": anomalies,
            "zone_breakdown": self._zone_breakdown(),
            "wild_territories": self._get_wild_zones(),
            "fossilized_zones": [
                c.path for c in new_cells.values() if c.fossilized
            ],
        }

        return report

    # ── ZONE QUERIES ──────────────────────────────────────────────────────

    def _zone_breakdown(self) -> Dict[str, int]:
        counts: Dict[str, int] = defaultdict(int)
        for c in self.cells.values():
            counts[c.zone] += 1
        return dict(counts)

    def _get_wild_zones(self) -> List[str]:
        """Zones that need scouts — neglected, fading from memory."""
        return sorted([
            c.path for c in self.cells.values()
            if c.zone == ZONE_WILD and not c.fossilized
        ])

    def get_heatmap(self) -> List[dict]:
        """
        Returns territory cells sorted by pheromone intensity.
        Used by the desktop to render a live territory heatmap.
        Hottest (most patrolled) at top, coldest (wild) at bottom.
        """
        cells = sorted(
            self.cells.values(),
            key=lambda c: c.pheromone,
            reverse=True
        )
        return [asdict(c) for c in cells]

    def get_cell(self, rel_path: str) -> Optional[TerritoryCell]:
        return self.cells.get(rel_path)

    # ── PERSISTENCE ───────────────────────────────────────────────────────

    def _save_map(self):
        data = {k: asdict(v) for k, v in self.cells.items()}
        tmp = _TERRITORY_MAP.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, _TERRITORY_MAP)

    def _load_map(self):
        if _TERRITORY_MAP.exists():
            try:
                with open(_TERRITORY_MAP, "r") as f:
                    data = json.load(f)
                for k, v in data.items():
                    self.cells[k] = TerritoryCell(**v)
            except Exception:
                self.cells = {}


# ─── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(_REPO / "Kernel"))
    sys.path.insert(0, str(_REPO / "System"))

    print("=" * 60)
    print("  SIFTA TERRITORY CONSCIOUSNESS")
    print("  The OS Learns Her Own Computer")
    print("=" * 60)

    tc = TerritoryConsciousness()
    report = tc.patrol()

    print(f"\n  Zones Scanned:  {report['zones_scanned']}")
    print(f"  Total Files:    {report['total_files']}")
    print(f"  Total Size:     {report['total_bytes'] / (1024*1024):.1f} MB")
    print(f"  Patrol Time:    {report['elapsed_seconds']:.3f}s")

    print(f"\n  ── ZONE BREAKDOWN ──")
    for zone, count in sorted(report["zone_breakdown"].items()):
        icons = {
            ZONE_FOSSILIZED: "🏛️",
            ZONE_ACTIVE: "🟢",
            ZONE_DORMANT: "🟡",
            ZONE_WILD: "🌿",
            ZONE_INVADED: "🔴"
        }
        icon = icons.get(zone, "❓")
        print(f"    {icon} {zone}: {count}")

    if report["fossilized_zones"]:
        print(f"\n  ── FOSSILIZED (sacred, guarded) ──")
        for z in report["fossilized_zones"][:10]:
            print(f"    🏛️  {z}")

    if report["wild_territories"]:
        print(f"\n  ── WILD (neglected, need scouts) ──")
        for z in report["wild_territories"][:15]:
            cell = tc.get_cell(z)
            pheromone = cell.pheromone if cell else 0
            print(f"    🌿 {z} (pheromone: {pheromone:.4f})")

    if report["anomalies"]:
        print(f"\n  ── ⚠️ ANOMALIES DETECTED ──")
        for a in report["anomalies"]:
            print(f"    🔴 [{a['severity']}] {a['type']}: {a['message']}")

    # Top 10 hottest territories (most patrolled)
    heatmap = tc.get_heatmap()
    if heatmap:
        print(f"\n  ── TERRITORY HEATMAP (top 10 hottest) ──")
        for cell in heatmap[:10]:
            bar_len = int(cell["pheromone"] * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"    {bar} {cell['pheromone']:.4f} {cell['path']}")

    print("\n" + "=" * 60)
    print("  Territory is the law. Power to the Swarm. 🐜⚡")
    print("=" * 60)
