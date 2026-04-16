#!/usr/bin/env python3
"""
regenerative_factory.py — Stigmergic Decentralized Manufacturing Engine
════════════════════════════════════════════════════════════════════════════
"Crypto for real... coordination software for regenerative production,
 not just moving labor and capital, but actual things." — Michel Bauwens

The Swarm coordinates physical reality.

Model: a decentralized 3D-printing farm producing Open Dynamic Robot
Initiative (ODRI) components.  Swimmers don't move capital — they move
filament, power, and assembly intent.  STGM is minted ONLY when raw
material is successfully converted into a functional kinetic part.

Architecture:
  Factory floor = 2D grid of cells
  Cell types:
    • SOURCE     — raw filament spool / power station
    • PRINTER    — 3D printer producing a specific component
    • QC         — quality control station (inspection)
    • ASSEMBLY   — assembly point (components → functional part)
    • FLOOR      — open floor (transport corridor)

Swimmer species:
  • ResourceForager   — carries filament from SOURCE to PRINTER
  • AssemblySwimmer   — carries printed components to ASSEMBLY
  • QualitySentinel   — inspects completed parts, flags defects
  • PowerCourier      — keeps printers energized from power stations

STGM minting events (Proof of Useful Physical Work):
  • COMPONENT_PRINTED   — 0.1 STGM when printer completes a part
  • QC_PASSED           — 0.05 STGM when quality inspection passes
  • UNIT_ASSEMBLED      — 0.5 STGM when parts combine into a robot joint
  • DEFECT_CAUGHT       — 0.02 STGM when sentinel catches a bad part

ODRI Components:
  • actuator_housing   — the outer shell of the joint
  • motor_bracket      — motor mounting plate
  • bearing_sleeve     — low-friction rotation sleeve
  • encoder_cap        — sensor cap for position feedback
  • linkage_arm        — the kinematic link between joints
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
STATE_DIR = REPO / ".sifta_state"
FACTORY_LEDGER = STATE_DIR / "factory_ledger.jsonl"

# ── ODRI component catalog ──────────────────────────────────────

COMPONENTS = [
    "actuator_housing",
    "motor_bracket",
    "bearing_sleeve",
    "encoder_cap",
    "linkage_arm",
]

ASSEMBLY_RECIPE = {
    "ODRI Joint Module": {
        "actuator_housing": 1,
        "motor_bracket": 1,
        "bearing_sleeve": 2,
        "encoder_cap": 1,
        "linkage_arm": 1,
    }
}

STGM_REWARDS = {
    "COMPONENT_PRINTED": 0.10,
    "QC_PASSED": 0.05,
    "UNIT_ASSEMBLED": 0.50,
    "DEFECT_CAUGHT": 0.02,
}


class CellType(Enum):
    FLOOR = "floor"
    SOURCE = "source"
    PRINTER = "printer"
    QC = "qc"
    ASSEMBLY = "assembly"


@dataclass
class FactoryCell:
    row: int
    col: int
    cell_type: CellType = CellType.FLOOR
    label: str = ""

    # Printer state
    component_type: str = ""     # what this printer makes
    filament_level: float = 0.0  # 0-100 units
    power_level: float = 100.0   # 0-100
    print_progress: float = 0.0  # 0-1 (1 = part done)
    printing: bool = False
    parts_produced: int = 0
    defect_rate: float = 0.03    # 3% chance of defect

    # Assembly state
    inventory: Dict[str, int] = field(default_factory=dict)
    units_assembled: int = 0

    # QC state
    parts_inspected: int = 0
    defects_caught: int = 0

    # Pheromone layers
    resource_pheromone: float = 0.0    # "I need filament here"
    assembly_pheromone: float = 0.0    # "component ready for pickup"
    power_pheromone: float = 0.0       # "I need power here"
    quality_pheromone: float = 0.0     # "QC approval / defect flag"


@dataclass
class StgmEvent:
    timestamp: float
    event_type: str
    stgm: float
    detail: str
    cell_row: int = 0
    cell_col: int = 0


class FactoryFloor:
    """The decentralized manufacturing grid."""

    def __init__(self, rows: int = 20, cols: int = 30):
        self.rows = rows
        self.cols = cols
        self.cells: List[List[FactoryCell]] = [
            [FactoryCell(row=r, col=c) for c in range(cols)] for r in range(rows)
        ]
        self.tick = 0
        self.total_stgm = 0.0
        self.events: List[StgmEvent] = []
        self._setup_layout()

    def _setup_layout(self):
        """Place sources, printers, QC stations, and assembly points."""
        r, c = self.rows, self.cols

        # Sources (filament spools) — left side
        sources = [(2, 1), (6, 1), (10, 1), (14, 1), (18, 1)]
        for sr, sc in sources:
            if sr < r and sc < c:
                cell = self.cells[sr][sc]
                cell.cell_type = CellType.SOURCE
                cell.label = "Filament"
                cell.filament_level = 100.0

        # Power stations — top and bottom edges
        power_locs = [(0, 8), (0, 16), (0, 24), (r - 1, 8), (r - 1, 16), (r - 1, 24)]
        for pr, pc in power_locs:
            if pr < r and pc < c:
                cell = self.cells[pr][pc]
                cell.cell_type = CellType.SOURCE
                cell.label = "Power"
                cell.power_level = 100.0

        # 3D Printers — center-left cluster
        printer_positions = [
            (3, 6, "actuator_housing"),
            (7, 6, "motor_bracket"),
            (11, 6, "bearing_sleeve"),
            (15, 6, "encoder_cap"),
            (3, 12, "linkage_arm"),
            (7, 12, "bearing_sleeve"),
            (11, 12, "actuator_housing"),
            (15, 12, "motor_bracket"),
        ]
        for pr, pc, comp in printer_positions:
            if pr < r and pc < c:
                cell = self.cells[pr][pc]
                cell.cell_type = CellType.PRINTER
                cell.label = f"Print: {comp}"
                cell.component_type = comp
                cell.filament_level = 50.0
                cell.defect_rate = random.uniform(0.02, 0.08)

        # QC stations — center
        qc_positions = [(5, 18), (10, 18), (15, 18)]
        for qr, qc_ in qc_positions:
            if qr < r and qc_ < c:
                cell = self.cells[qr][qc_]
                cell.cell_type = CellType.QC
                cell.label = "QC Station"

        # Assembly points — right side
        assembly_positions = [(8, 24), (12, 24)]
        for ar, ac in assembly_positions:
            if ar < r and ac < c:
                cell = self.cells[ar][ac]
                cell.cell_type = CellType.ASSEMBLY
                cell.label = "Assembly: ODRI Joint"
                cell.inventory = {comp: 0 for comp in COMPONENTS}

    def get(self, r: int, c: int) -> Optional[FactoryCell]:
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return self.cells[r][c]
        return None

    def neighbors(self, r: int, c: int) -> List[FactoryCell]:
        nbrs = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            cell = self.get(r + dr, c + dc)
            if cell is not None:
                nbrs.append(cell)
        return nbrs

    def cells_of_type(self, ct: CellType) -> List[FactoryCell]:
        return [self.cells[r][c] for r in range(self.rows) for c in range(self.cols)
                if self.cells[r][c].cell_type == ct]

    def mint_stgm(self, event_type: str, detail: str, row: int = 0, col: int = 0) -> float:
        reward = STGM_REWARDS.get(event_type, 0.0)
        self.total_stgm += reward
        ev = StgmEvent(
            timestamp=time.time(), event_type=event_type,
            stgm=reward, detail=detail, cell_row=row, cell_col=col)
        self.events.append(ev)
        if len(self.events) > 500:
            self.events = self.events[-300:]
        return reward


# ── Factory Swimmers ─────────────────────────────────────────────

@dataclass
class FactorySwimmer:
    species: str       # "forager", "assembler", "sentinel", "courier"
    row: int = 0
    col: int = 0
    carrying: str = "" # what the swimmer is carrying ("filament", component name, "power")
    target_row: int = -1
    target_col: int = -1
    deliveries: int = 0
    alive: bool = True

    @property
    def color(self) -> str:
        return {
            "forager": "#00ccff",
            "assembler": "#ff8800",
            "sentinel": "#cc44ff",
            "courier": "#ffdd00",
        }.get(self.species, "#ffffff")

    @property
    def marker(self) -> str:
        return {
            "forager": "o",
            "assembler": "D",
            "sentinel": "^",
            "courier": "s",
        }.get(self.species, "o")


def spawn_factory_swimmers(floor: FactoryFloor) -> List[FactorySwimmer]:
    swimmers = []
    for _ in range(12):
        swimmers.append(FactorySwimmer(
            species="forager",
            row=random.randint(0, floor.rows - 1),
            col=random.randint(0, floor.cols - 1)))
    for _ in range(8):
        swimmers.append(FactorySwimmer(
            species="assembler",
            row=random.randint(0, floor.rows - 1),
            col=random.randint(0, floor.cols - 1)))
    for _ in range(4):
        swimmers.append(FactorySwimmer(
            species="sentinel",
            row=random.randint(0, floor.rows - 1),
            col=random.randint(0, floor.cols - 1)))
    for _ in range(6):
        swimmers.append(FactorySwimmer(
            species="courier",
            row=random.randint(0, floor.rows - 1),
            col=random.randint(0, floor.cols - 1)))
    return swimmers


# ── Simulation step ──────────────────────────────────────────────

def step_factory(floor: FactoryFloor, swimmers: List[FactorySwimmer]) -> List[str]:
    """Advance one tick. Returns list of event messages."""
    floor.tick += 1
    messages: List[str] = []

    # Printers tick
    for printer in floor.cells_of_type(CellType.PRINTER):
        if printer.filament_level > 2.0 and printer.power_level > 5.0:
            if not printer.printing:
                printer.printing = True
            printer.print_progress += 0.02
            printer.filament_level -= 0.3
            printer.power_level -= 0.15

            if printer.print_progress >= 1.0:
                printer.printing = False
                printer.print_progress = 0.0
                printer.parts_produced += 1

                is_defect = random.random() < printer.defect_rate
                if not is_defect:
                    printer.assembly_pheromone = min(1.0, printer.assembly_pheromone + 0.3)
                    reward = floor.mint_stgm("COMPONENT_PRINTED",
                                             f"{printer.component_type} printed",
                                             printer.row, printer.col)
                    messages.append(
                        f"PRINTED: {printer.component_type} (+{reward:.2f} STGM)")
                else:
                    printer.quality_pheromone = min(1.0, printer.quality_pheromone + 0.4)
                    messages.append(f"DEFECT: {printer.component_type} failed QC pre-screen")
        else:
            if printer.filament_level < 10:
                printer.resource_pheromone = min(1.0, printer.resource_pheromone + 0.05)
            if printer.power_level < 20:
                printer.power_pheromone = min(1.0, printer.power_pheromone + 0.05)

    # Assembly stations check if they can assemble a unit
    for asm in floor.cells_of_type(CellType.ASSEMBLY):
        recipe = ASSEMBLY_RECIPE.get("ODRI Joint Module", {})
        can_build = all(asm.inventory.get(comp, 0) >= qty for comp, qty in recipe.items())
        if can_build:
            for comp, qty in recipe.items():
                asm.inventory[comp] -= qty
            asm.units_assembled += 1
            reward = floor.mint_stgm("UNIT_ASSEMBLED",
                                     "ODRI Joint Module assembled",
                                     asm.row, asm.col)
            messages.append(
                f"ASSEMBLED: ODRI Joint Module #{asm.units_assembled} (+{reward:.2f} STGM)")

    # Swimmer movement
    for sw in swimmers:
        if not sw.alive:
            continue
        _step_swimmer(sw, floor, messages)

    # Pheromone evaporation
    for r in range(floor.rows):
        for c in range(floor.cols):
            cell = floor.cells[r][c]
            cell.resource_pheromone *= 0.985
            cell.assembly_pheromone *= 0.990
            cell.power_pheromone *= 0.985
            cell.quality_pheromone *= 0.988

    # Filament sources regenerate slowly
    for src in floor.cells_of_type(CellType.SOURCE):
        if src.label == "Filament":
            src.filament_level = min(100.0, src.filament_level + 0.5)
        elif src.label == "Power":
            src.power_level = min(100.0, src.power_level + 0.8)

    return messages


def _step_swimmer(sw: FactorySwimmer, floor: FactoryFloor, messages: List[str]):
    """Move one swimmer based on species behavior."""
    cell = floor.get(sw.row, sw.col)
    if cell is None:
        return
    nbrs = floor.neighbors(sw.row, sw.col)
    if not nbrs:
        return

    if sw.species == "forager":
        _step_forager(sw, cell, nbrs, floor, messages)
    elif sw.species == "assembler":
        _step_assembler(sw, cell, nbrs, floor, messages)
    elif sw.species == "sentinel":
        _step_sentinel(sw, cell, nbrs, floor, messages)
    elif sw.species == "courier":
        _step_courier(sw, cell, nbrs, floor, messages)


def _step_forager(sw, cell, nbrs, floor, messages):
    """ResourceForager: carries filament from SOURCE to hungry PRINTERs."""
    if not sw.carrying:
        if cell.cell_type == CellType.SOURCE and cell.label == "Filament" and cell.filament_level > 10:
            sw.carrying = "filament"
            cell.filament_level -= 8.0
            _move_toward_pheromone(sw, nbrs, "resource_pheromone")
            return
        _move_toward_type(sw, nbrs, CellType.SOURCE, floor, fallback_phero="resource_pheromone")
    else:
        if cell.cell_type == CellType.PRINTER and cell.filament_level < 60:
            cell.filament_level = min(100.0, cell.filament_level + 8.0)
            sw.carrying = ""
            sw.deliveries += 1
            cell.resource_pheromone *= 0.5
            return
        _move_toward_type(sw, nbrs, CellType.PRINTER, floor, fallback_phero="resource_pheromone")


def _step_assembler(sw, cell, nbrs, floor, messages):
    """AssemblySwimmer: picks up printed components and delivers to ASSEMBLY."""
    if not sw.carrying:
        if cell.cell_type == CellType.PRINTER and cell.assembly_pheromone > 0.1 and cell.parts_produced > 0:
            sw.carrying = cell.component_type
            cell.assembly_pheromone *= 0.3
            _move_toward_type(sw, nbrs, CellType.ASSEMBLY, floor, fallback_phero="assembly_pheromone")
            return
        _move_toward_pheromone(sw, nbrs, "assembly_pheromone")
    else:
        if cell.cell_type == CellType.ASSEMBLY:
            cell.inventory[sw.carrying] = cell.inventory.get(sw.carrying, 0) + 1
            sw.carrying = ""
            sw.deliveries += 1
            return
        _move_toward_type(sw, nbrs, CellType.ASSEMBLY, floor, fallback_phero="assembly_pheromone")


def _step_sentinel(sw, cell, nbrs, floor, messages):
    """QualitySentinel: inspects printers with quality_pheromone, catches defects."""
    if cell.cell_type == CellType.PRINTER and cell.quality_pheromone > 0.15:
        cell.quality_pheromone *= 0.2
        cell.defect_rate = max(0.01, cell.defect_rate - 0.005)
        cell.parts_inspected = getattr(cell, '_sentinel_inspections', 0) + 1
        floor.mint_stgm("DEFECT_CAUGHT", f"sentinel inspection at ({cell.row},{cell.col})",
                        cell.row, cell.col)
        messages.append(f"QC: sentinel improved printer at ({cell.row},{cell.col})")
        _move_random(sw, nbrs)
    elif cell.cell_type == CellType.QC:
        reward = floor.mint_stgm("QC_PASSED", "QC routine inspection", cell.row, cell.col)
        cell.parts_inspected += 1
        _move_toward_pheromone(sw, nbrs, "quality_pheromone")
    else:
        _move_toward_pheromone(sw, nbrs, "quality_pheromone")


def _step_courier(sw, cell, nbrs, floor, messages):
    """PowerCourier: carries power from power stations to hungry printers."""
    if not sw.carrying:
        if cell.cell_type == CellType.SOURCE and cell.label == "Power" and cell.power_level > 20:
            sw.carrying = "power"
            cell.power_level -= 10.0
            _move_toward_pheromone(sw, nbrs, "power_pheromone")
            return
        power_sources = [n for n in nbrs if n.cell_type == CellType.SOURCE and n.label == "Power"]
        if power_sources:
            target = random.choice(power_sources)
            sw.row, sw.col = target.row, target.col
        else:
            _move_toward_pheromone(sw, nbrs, "power_pheromone")
    else:
        if cell.cell_type == CellType.PRINTER and cell.power_level < 50:
            cell.power_level = min(100.0, cell.power_level + 10.0)
            sw.carrying = ""
            sw.deliveries += 1
            cell.power_pheromone *= 0.5
            return
        _move_toward_type(sw, nbrs, CellType.PRINTER, floor, fallback_phero="power_pheromone")


# ── Movement helpers ─────────────────────────────────────────────

def _move_toward_pheromone(sw, nbrs, phero_attr):
    best = max(nbrs, key=lambda n: getattr(n, phero_attr, 0) + random.uniform(-0.02, 0.02))
    sw.row, sw.col = best.row, best.col


def _move_toward_type(sw, nbrs, target_type, floor, fallback_phero="resource_pheromone"):
    typed = [n for n in nbrs if n.cell_type == target_type]
    if typed:
        target = random.choice(typed)
        sw.row, sw.col = target.row, target.col
        return
    # If not adjacent, take a step closer to the nearest cell of that type
    all_targets = floor.cells_of_type(target_type)
    if all_targets:
        nearest = min(all_targets, key=lambda t: abs(t.row - sw.row) + abs(t.col - sw.col))
        best = min(nbrs, key=lambda n: abs(n.row - nearest.row) + abs(n.col - nearest.col)
                   + random.uniform(-0.5, 0.5))
        sw.row, sw.col = best.row, best.col
    else:
        _move_toward_pheromone(sw, nbrs, fallback_phero)


def _move_random(sw, nbrs):
    target = random.choice(nbrs)
    sw.row, sw.col = target.row, target.col


# ── Telemetry ────────────────────────────────────────────────────

def factory_telemetry(floor: FactoryFloor, swimmers: List[FactorySwimmer]) -> Dict:
    printers = floor.cells_of_type(CellType.PRINTER)
    assemblies = floor.cells_of_type(CellType.ASSEMBLY)

    total_printed = sum(p.parts_produced for p in printers)
    total_assembled = sum(a.units_assembled for a in assemblies)
    avg_filament = sum(p.filament_level for p in printers) / max(1, len(printers))
    avg_power = sum(p.power_level for p in printers) / max(1, len(printers))
    active_printers = sum(1 for p in printers if p.printing)
    active_swimmers = sum(1 for s in swimmers if s.alive)
    total_deliveries = sum(s.deliveries for s in swimmers)

    inv_totals: Dict[str, int] = {}
    for asm in assemblies:
        for comp, qty in asm.inventory.items():
            inv_totals[comp] = inv_totals.get(comp, 0) + qty

    return {
        "tick": floor.tick,
        "total_stgm": floor.total_stgm,
        "total_printed": total_printed,
        "total_assembled": total_assembled,
        "active_printers": active_printers,
        "printer_count": len(printers),
        "avg_filament": avg_filament,
        "avg_power": avg_power,
        "active_swimmers": active_swimmers,
        "total_deliveries": total_deliveries,
        "inventory": inv_totals,
    }


def persist_ledger(floor: FactoryFloor) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(FACTORY_LEDGER, "a") as f:
        for ev in floor.events[-50:]:
            f.write(json.dumps({
                "ts": ev.timestamp, "type": ev.event_type,
                "stgm": ev.stgm, "detail": ev.detail,
            }) + "\n")


def credit_architect_factory_mint(delta_stgm: float, tick: int = 0) -> Optional[float]:
    """
    Mirror simulated factory STGM into repair_log.jsonl as a signed UTILITY_MINT so
    ledger_balance() and the OS HUD credit the local canonical agent (owner-bound).

    Applies the same halving multiplier as other swarm mints. Disable with
    SIFTA_FACTORY_LEDGER_SYNC=0 to keep rewards simulation-only (returns None).

    Returns:
        float > 0 — amount written to repair_log
        0.0 — nothing written (rounding / transient failure; caller may retry)
        None — ledger sync disabled; caller should advance local cursor without writing
    """
    if os.environ.get("SIFTA_FACTORY_LEDGER_SYNC", "1").strip().lower() in (
        "0", "false", "no", "off",
    ):
        return None
    d = float(delta_stgm)
    if d <= 1e-12:
        return 0.0
    try:
        if str(REPO) not in sys.path:
            sys.path.insert(0, str(REPO))
        from datetime import datetime, timezone

        from inference_economy import get_current_halving_multiplier

        if str(REPO / "System") not in sys.path:
            sys.path.insert(0, str(REPO / "System"))
        from body_state import SwarmBody
        from crypto_keychain import get_silicon_identity, sign_block
        from ledger_append import append_ledger_line

        mult = get_current_halving_multiplier()
        amount = round(d * mult, 4)
        if amount <= 0:
            return 0.0

        sn_agent = SwarmBody.get_local_serial()
        miner_id = SwarmBody.resolve_agent_from_serial(sn_agent)
        if not miner_id:
            miner_id = "ALICE_M5"
        miner_id = str(miner_id).upper()

        ts_iso = datetime.now(timezone.utc).isoformat()
        ts_wall = int(time.time())
        signing = get_silicon_identity()
        reason = f"BAUWENS_FACTORY_SIM tick={tick}"
        body = f"UTILITY_MINT::{miner_id}::{amount}::{ts_iso}::{reason}::NODE[{signing}]"
        sig = sign_block(body)

        event = {
            "event": "UTILITY_MINT",
            "timestamp": ts_wall,
            "ts": ts_iso,
            "miner_id": miner_id,
            "amount_stgm": amount,
            "reason": reason,
            "hash": str(uuid.uuid4()),
            "ed25519_sig": sig,
            "signing_node": signing,
        }
        append_ledger_line(REPO / "repair_log.jsonl", event)
        return amount
    except Exception as e:
        print(f"[FACTORY] Ledger credit failed: {e}")
        return 0.0
