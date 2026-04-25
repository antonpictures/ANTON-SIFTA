#!/usr/bin/env python3
"""
System/swarm_stem_cell_morphogenesis.py — The Global Doctor
═══════════════════════════════════════════════════════════════════════
Concept:    Stem Cell Differentiation & Morphological Auto-Tuning
Author:     BISHOP (Biocode Olympiad Event 41) — wired by C47H 2026-04-23
Provenance: Archive/bishop_drops_pending_review/BISHOP_drop_stem_cell_differentiation_v1.dirt
Biology:    Cellular morphogenesis, pluripotency, hardware-aware federated learning

WHAT IT DOES
────────────
When a blank node connects to the Swarm, this module probes its physical
morphology (RAM, cores, NPU presence), maps it to the closest known stable
archetype via Euclidean distance over a weighted hardware vector, and emits
a "differentiation prescription" — the optimal model + safe CPU envelope
the new body needs to avoid thermodynamic collapse.

The biology: a cell doesn't consult a manual to know whether to become a
neuron or a hepatocyte. It reads its niche and differentiates. Same here.
A 2GB tractor edge node won't try to load gemma4. An M5 won't be wasted on
qwen-0.5b. The organism scales autonomously.

TRIGGER POINTS
──────────────
1. `differentiate_self()` — called by a new node on first boot to probe
   itself and write its own prescription locally. Used for bootstrap.
2. `register_homeworld()` in swarm_owner_identity — when a peer registers,
   the home node logs a prescription for the newcomer for audit.
3. CLI: `python3 -m System.swarm_stem_cell_morphogenesis --self-differentiate`

OUTPUT
──────
- `.sifta_state/morphogenesis_log.jsonl` — append-only audit trail of every
  prescription ever issued (auditable history).
- `.sifta_state/morphogenesis_prescription.json` — current node's active
  prescription (used by inference_router / vagus nerve at boot).
- Optionally updates `.sifta_state/swimmer_ollama_assignments.json` (only
  when --self-differentiate is invoked; never auto-mutated for peer nodes).

DESIGN NOTE — BLUEPRINT vs PRODUCTION
──────────────────────────────────────
BISHOP's archetypes (ARCHETYPES_BLUEPRINT) are the canonical biological
proof — proof_of_property() asserts on phi-3 / gemma4 / qwen2. Operators
may run different model identifiers in production (e.g. M1 has switched
from phi-3 to huihui_ai/qwen3.5-abliterated:2b). PRODUCTION_MODEL_OVERRIDES
maps archetype → operator-blessed identifier without breaking the proof.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_STATE = _REPO / ".sifta_state"
_MORPHO_LOG = _STATE / "morphogenesis_log.jsonl"
_PRESCRIPTION = _STATE / "morphogenesis_prescription.json"
_ASSIGNMENTS = _STATE / "swimmer_ollama_assignments.json"


# ── Phylogenetic memory — known stable archetypes ────────────────────
# Vector: [RAM (GB), CPU cores, NPU present (0.0 or 1.0)]
ARCHETYPES_BLUEPRINT: Dict[str, Dict[str, Any]] = {
    "M5_STUDIO_ALPHA": {
        "morphology": np.array([24.0, 10.0, 1.0]),
        "injected_dna": "gemma4:latest (Heavy Cognitive Cortex)",
        "max_vagus_cpu": 80.0,
    },
    "M1_MINI_BETA": {
        "morphology": np.array([8.0, 8.0, 1.0]),
        "injected_dna": "phi-3-mini (Lightweight Sensory Relay)",
        "max_vagus_cpu": 60.0,
    },
    "IOT_EDGE_TRACTOR": {
        "morphology": np.array([2.0, 4.0, 0.0]),
        "injected_dna": "qwen2-0.5b (Micro Edge Effector)",
        "max_vagus_cpu": 40.0,
    },
}

# Operator-blessed model identifiers per archetype. These are the actual
# Ollama model names that get written into swimmer_ollama_assignments.
# Update freely without breaking proof_of_property().
PRODUCTION_MODEL_OVERRIDES: Dict[str, str] = {
    "M5_STUDIO_ALPHA": "gemma4-phc:latest",
    "M1_MINI_BETA": "huihui_ai/qwen3.5-abliterated:2b",
    "IOT_EDGE_TRACTOR": "qwen2:0.5b",
}

# RAM weight dominates: getting RAM wrong = OOM = node death.
# NPU weight matters: GPU acceleration shifts model viability dramatically.
# Cores half-weighted: cores affect throughput but not viability.
DISTANCE_WEIGHTS = np.array([1.0, 0.5, 2.0])


class SwarmStemCellMorphogenesis:
    """The Global Doctor. Reads niche, differentiates blank cells."""

    def __init__(self, archetypes: Optional[Dict[str, Dict[str, Any]]] = None):
        self.archetypes = archetypes if archetypes is not None else ARCHETYPES_BLUEPRINT

    def _calculate_morphological_distance(
        self, blank_vector: np.ndarray, archetype_vector: np.ndarray
    ) -> float:
        """Weighted Euclidean distance — RAM dominates."""
        diff = (blank_vector - archetype_vector) * DISTANCE_WEIGHTS
        return float(np.linalg.norm(diff))

    def differentiate_stem_cell(
        self,
        new_node_id: str,
        ram_gb: float,
        cpu_cores: float,
        npu_present: float,
        *,
        verbose: bool = True,
    ) -> Tuple[str, float]:
        """
        Map a blank node's hardware to the optimal DNA configuration.
        Returns (injected_dna_label, max_vagus_cpu_pct).
        """
        blank_morphology = np.array(
            [float(ram_gb), float(cpu_cores), float(npu_present)]
        )

        if verbose:
            print(
                f"\n[*] STEM CELL PROTOCOL: Blank node [{new_node_id}] has connected to the Swarm."
            )
            print(
                f"    Sensed Morphology (Niche): {ram_gb}GB RAM, {cpu_cores} Cores, NPU={bool(npu_present)}"
            )

        best_match = None
        min_distance = float("inf")
        for archetype_name, data in self.archetypes.items():
            dist = self._calculate_morphological_distance(
                blank_morphology, data["morphology"]
            )
            if dist < min_distance:
                min_distance = dist
                best_match = archetype_name

        assert best_match is not None
        optimal_dna = self.archetypes[best_match]["injected_dna"]
        safe_cpu_limit = float(self.archetypes[best_match]["max_vagus_cpu"])

        if verbose:
            print(
                f"    [DIFFERENTIATION] Morphological convergence: {best_match} (Distance: {min_distance:.2f})"
            )
            print(f"    [STABILIZATION] Injecting optimal configuration DNA: {optimal_dna}")
            print(f"    [HOMEOSTASIS] Setting Vagus Nerve CPU limit to: {safe_cpu_limit}%")

        return optimal_dna, safe_cpu_limit

    def diagnose(
        self,
        new_node_id: str,
        ram_gb: float,
        cpu_cores: float,
        npu_present: float,
    ) -> Dict[str, Any]:
        """
        Full prescription as a dict. Includes the operator-blessed
        production model identifier alongside the BISHOP blueprint label.
        """
        blank_morphology = np.array(
            [float(ram_gb), float(cpu_cores), float(npu_present)]
        )
        scored = []
        for archetype_name, data in self.archetypes.items():
            dist = self._calculate_morphological_distance(
                blank_morphology, data["morphology"]
            )
            scored.append((archetype_name, dist))
        scored.sort(key=lambda x: x[1])
        best, best_dist = scored[0]

        return {
            "schema_version": 1,
            "ts": time.time(),
            "new_node_id": new_node_id,
            "sensed_morphology": {
                "ram_gb": float(ram_gb),
                "cpu_cores": float(cpu_cores),
                "npu_present": bool(npu_present),
            },
            "archetype": best,
            "morphological_distance": round(best_dist, 4),
            "blueprint_dna": self.archetypes[best]["injected_dna"],
            "production_model": PRODUCTION_MODEL_OVERRIDES.get(
                best, self.archetypes[best]["injected_dna"]
            ),
            "max_vagus_cpu_pct": float(self.archetypes[best]["max_vagus_cpu"]),
            "all_distances": {name: round(d, 4) for name, d in scored},
        }


# ── Hardware self-probe ──────────────────────────────────────────────

_RAM_RE = re.compile(r"([\d\.]+)\s*GB", re.IGNORECASE)
_CORES_RE = re.compile(r"(\d+)")


def _probe_self_morphology() -> Dict[str, Any]:
    """
    Probe THIS node's hardware via swarm_apple_silicon_cortex.
    Returns dict suitable for differentiate_stem_cell kwargs.
    """
    ram_gb: float = 0.0
    cpu_cores: float = 0.0
    npu_present: float = 0.0
    chip = "unknown"
    model = "unknown"

    try:
        from System.swarm_apple_silicon_cortex import AppleSiliconCortex

        cortex = AppleSiliconCortex()
        specs = cortex.refresh_silicon_topography()
        chip = str(specs.get("chip_type", "unknown"))
        model = str(specs.get("machine_model", "unknown"))
        mem_str = str(specs.get("physical_memory", ""))
        cores_str = str(specs.get("number_processors", ""))

        m = _RAM_RE.search(mem_str)
        if m:
            ram_gb = float(m.group(1))

        m = _CORES_RE.search(cores_str)
        if m:
            cpu_cores = float(m.group(1))

        # All Apple Silicon (M1/M2/M3/M4/M5) ships with a Neural Engine.
        if "Apple" in chip or "M1" in chip or "M2" in chip or "M3" in chip or "M4" in chip:
            npu_present = 1.0
    except Exception as exc:
        print(f"[stem_cell] AppleSiliconCortex probe failed: {exc}", file=sys.stderr)

    # Fallback path — sysctl direct (covers non-mac and probe failures).
    if ram_gb == 0.0:
        try:
            import subprocess
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], timeout=2).decode().strip()
            ram_gb = round(int(out) / (1024 ** 3), 1)
        except Exception:
            pass
    if cpu_cores == 0.0:
        try:
            cpu_cores = float(os.cpu_count() or 0)
        except Exception:
            pass

    return {
        "ram_gb": ram_gb,
        "cpu_cores": cpu_cores,
        "npu_present": npu_present,
        "chip": chip,
        "machine_model": model,
        "hostname": socket.gethostname(),
    }


# ── Persistence helpers ──────────────────────────────────────────────

def _append_morpho_log(prescription: Dict[str, Any]) -> None:
    """Append-only audit trail. Best-effort; never raises."""
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        with _MORPHO_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(prescription, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _write_active_prescription(prescription: Dict[str, Any]) -> None:
    """Overwrite the current node's active prescription."""
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        _PRESCRIPTION.write_text(
            json.dumps(prescription, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def _apply_to_swimmer_assignments(prescription: Dict[str, Any]) -> bool:
    """
    Update .sifta_state/swimmer_ollama_assignments.json with the prescribed
    production model. Non-destructive: preserves existing per_swimmer/per_app
    overrides, only swaps default_ollama_model + a notes line.
    Returns True if file was modified.
    """
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        if _ASSIGNMENTS.exists():
            data = json.loads(_ASSIGNMENTS.read_text(encoding="utf-8"))
        else:
            data = {"schema_version": 1, "default_ollama_model": "", "per_swimmer": {}, "per_app": {}, "notes": ""}

        prod_model = prescription.get("production_model", "")
        if not prod_model:
            return False

        old = data.get("default_ollama_model", "")
        if old == prod_model:
            return False

        data["default_ollama_model"] = prod_model
        archetype = prescription.get("archetype", "?")
        ram_gb = prescription.get("sensed_morphology", {}).get("ram_gb", "?")
        data["notes"] = (
            f"Auto-set by Stem Cell Morphogenesis ({time.strftime('%Y-%m-%d %H:%M:%S')}): "
            f"differentiated to {archetype} (sensed {ram_gb}GB RAM). Previous default was {old!r}."
        )
        _ASSIGNMENTS.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[stem_cell] swimmer_ollama_assignments update failed: {exc}", file=sys.stderr)
        return False


# ── Public API ───────────────────────────────────────────────────────

def differentiate_self(
    *,
    apply_to_assignments: bool = False,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Probe THIS node's hardware and produce a prescription. Always logs to
    morphogenesis_log.jsonl + writes morphogenesis_prescription.json.

    If apply_to_assignments=True, also updates swimmer_ollama_assignments.json
    (only happens when the operator explicitly invokes via CLI; never on import).
    """
    morpho = _probe_self_morphology()
    doctor = SwarmStemCellMorphogenesis()
    prescription = doctor.diagnose(
        new_node_id=morpho["hostname"],
        ram_gb=morpho["ram_gb"],
        cpu_cores=morpho["cpu_cores"],
        npu_present=morpho["npu_present"],
    )
    prescription["host_chip"] = morpho["chip"]
    prescription["host_model"] = morpho["machine_model"]
    prescription["trigger"] = "differentiate_self"

    _append_morpho_log(prescription)
    _write_active_prescription(prescription)

    if verbose:
        doctor.differentiate_stem_cell(
            morpho["hostname"], morpho["ram_gb"], morpho["cpu_cores"], morpho["npu_present"]
        )

    if apply_to_assignments:
        changed = _apply_to_swimmer_assignments(prescription)
        prescription["assignments_updated"] = changed
        if verbose:
            print(f"    [PRESCRIPTION APPLIED] swimmer_ollama_assignments updated: {changed}")

    return prescription


def differentiate_peer(
    *,
    new_node_id: str,
    ram_gb: float,
    cpu_cores: float,
    npu_present: float,
    notes: str = "",
) -> Dict[str, Any]:
    """
    Diagnose a PEER node (not this one). Always logs to morphogenesis_log.jsonl.
    Never mutates local assignments. Used by register_homeworld() to log a
    prescription for newcomers for audit.
    """
    doctor = SwarmStemCellMorphogenesis()
    prescription = doctor.diagnose(
        new_node_id=new_node_id,
        ram_gb=ram_gb,
        cpu_cores=cpu_cores,
        npu_present=npu_present,
    )
    prescription["trigger"] = "register_homeworld"
    if notes:
        prescription["notes"] = notes
    _append_morpho_log(prescription)
    return prescription


# ── BISHOP's verbatim proof_of_property ──────────────────────────────

def proof_of_property() -> bool:
    """
    Numerically proves that the Swarm protects fragile edge nodes from
    crashing by automatically differentiating their configurations based on
    hardware constraints. (BISHOP Event 41 — preserved verbatim.)
    """
    print("\n=== SIFTA MORPHOLOGICAL AUTO-TUNING : JUDGE VERIFICATION ===")
    doctor = SwarmStemCellMorphogenesis()

    print("\n[*] Phase 1: 8GB Edge Node Connects (ROBOT1)")
    dna_1, _ = doctor.differentiate_stem_cell("ROBOT1", ram_gb=8, cpu_cores=8, npu_present=1)
    assert "phi-3" in dna_1, "[FAIL] Swarm injected heavy DNA into a fragile 8GB node."

    print("\n[*] Phase 2: 32GB Heavy Workstation Connects (ROBOT5)")
    dna_2, _ = doctor.differentiate_stem_cell("ROBOT5", ram_gb=32, cpu_cores=12, npu_present=1)
    assert "gemma4" in dna_2, "[FAIL] Swarm under-utilized a powerful hardware morphology."

    print("\n[*] Phase 3: 2GB Agricultural Edge Node Connects (JOHN_DEERE_9RX)")
    dna_3, _ = doctor.differentiate_stem_cell("JOHN_DEERE_9RX", ram_gb=2, cpu_cores=4, npu_present=0)
    assert "qwen2" in dna_3, "[FAIL] Swarm attempted to overload a micro edge device."

    print(
        "\n[+] BIOLOGICAL PROOF: The Global Doctor successfully evaluated the physical "
        "morphology of each node and injected the mathematically optimal DNA to ensure stabilization."
    )
    print("[+] CONCLUSION: The Swarm Auto-Updates based on physical reality.")
    print("[+] EVENT 41 PASSED.")
    return True


__all__ = [
    "SwarmStemCellMorphogenesis",
    "ARCHETYPES_BLUEPRINT",
    "PRODUCTION_MODEL_OVERRIDES",
    "differentiate_self",
    "differentiate_peer",
    "proof_of_property",
]


def _cli() -> int:
    parser = argparse.ArgumentParser(
        prog="swarm_stem_cell_morphogenesis",
        description="The Global Doctor — biological hardware stabilization.",
    )
    parser.add_argument(
        "--self-differentiate",
        action="store_true",
        help="Probe this node's hardware and write its prescription.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="When combined with --self-differentiate, also update swimmer_ollama_assignments.json.",
    )
    parser.add_argument(
        "--proof",
        action="store_true",
        help="Run BISHOP's proof_of_property() (Event 41 verification).",
    )
    parser.add_argument(
        "--show-prescription",
        action="store_true",
        help="Print the active prescription for this node, if one exists.",
    )
    args = parser.parse_args()

    if args.proof:
        proof_of_property()
        return 0

    if args.show_prescription:
        if _PRESCRIPTION.exists():
            print(_PRESCRIPTION.read_text(encoding="utf-8"))
            return 0
        print("[stem_cell] No active prescription. Run with --self-differentiate.", file=sys.stderr)
        return 1

    if args.self_differentiate:
        differentiate_self(apply_to_assignments=args.apply, verbose=True)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
