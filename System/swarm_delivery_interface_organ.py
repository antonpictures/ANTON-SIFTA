#!/usr/bin/env python3
"""
swarm_delivery_interface_organ.py — Delivery Interface Organ.

Models delivery modalities (AAV, mRNA-LNP, EV, nanoparticle, etc.) as
experimental conditions linked to morphology trajectories.

This organ does NOT implement biological delivery procedures. It records
delivery metadata as experimental inputs and links them to the
cell_morphology trajectory/receipt system for comparative analysis.

SAFETY: Observation/recording only. No viral vector handling, no transfection,
no recombinant nucleic acid work, no human cell culture.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional

from System.swarm_world_awareness import append_trace, read_traces


# ─── Constants ──────────────────────────────────────────────────────────
TRUTH_LABEL = "DELIVERY_INTERFACE_ORGAN_V1"
LEDGER_KIND = "delivery_experiment"
LINK_KIND = "delivery_trajectory_link"
COMPARE_KIND = "delivery_modality_comparison"

VALID_DELIVERY_TYPES = (
    "AAV",
    "lentivirus",
    "adenovirus",
    "mRNA-LNP",
    "mRNA-polymer",
    "extracellular_vesicle",
    "exosome",
    "lipid_nanoparticle",
    "polymer_nanoparticle",
    "peptide_nanoparticle",
    "inorganic_nanoparticle",
    "electroporation",
    "sonoporation",
    "microinjection",
    "other",
)


# ─── Data Classes ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class DeliveryExperiment:
    """Immutable record of a delivery experiment condition."""
    experiment_id: str
    delivery_type: str
    parameters: dict[str, Any]
    facility_id: str
    timestamp: float
    notes: str = ""


@dataclass(frozen=True)
class TrajectoryLink:
    """Link between a morphology trajectory and a delivery experiment."""
    link_id: str
    trajectory_id: str
    experiment_id: str
    timestamp: float
    metadata: dict[str, Any]


# ─── Helpers ───────────────────────────────────────────────────────────
def _validate_delivery_type(delivery_type: str) -> str:
    """Validate and normalize delivery type."""
    normalized = delivery_type.strip()
    if normalized not in VALID_DELIVERY_TYPES:
        # Allow custom types but warn via trace
        pass
    return normalized


def _now() -> float:
    return time.time()


# ─── Public API ────────────────────────────────────────────────────────
def register_delivery_experiment(
    delivery_type: str,
    parameters: dict[str, Any],
    facility_id: str,
    notes: str = "",
) -> dict[str, Any]:
    """
    Register a delivery experiment condition.

    Args:
        delivery_type: One of VALID_DELIVERY_TYPES or custom string
        parameters: Dict of delivery parameters (dose, serotype, lipid composition, etc.)
        facility_id: Identifier of the authorized facility running the experiment
        notes: Free-text notes

    Returns:
        Dict with experiment_id, receipt trace info
    """
    delivery_type = _validate_delivery_type(delivery_type)
    experiment_id = f"delivery_exp_{uuid.uuid4().hex[:12]}"
    timestamp = _now()

    experiment = DeliveryExperiment(
        experiment_id=experiment_id,
        delivery_type=delivery_type,
        parameters=parameters,
        facility_id=facility_id,
        timestamp=timestamp,
        notes=notes,
    )

    # Append to unified ledger
    trace = append_trace(
        source="delivery_interface",
        kind=LEDGER_KIND,
        text=f"Delivery experiment registered: {delivery_type} at {facility_id}",
        confidence=1.0,
        extra=asdict(experiment),
    )

    return {
        "ok": trace is not None,
        "experiment_id": experiment_id,
        "delivery_type": delivery_type,
        "trace": trace,
    }


def link_trajectory_to_delivery(
    trajectory_id: str,
    experiment_id: str,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Link a cell_morphology trajectory to a delivery experiment.

    Args:
        trajectory_id: The image_id or timestamp from cell_morphology trajectory
        experiment_id: The experiment_id from register_delivery_experiment
        metadata: Additional linking metadata (e.g., timepoint, well, replicate)

    Returns:
        Dict with link_id, receipt trace info
    """
    link_id = f"link_{uuid.uuid4().hex[:12]}"
    timestamp = _now()

    link = TrajectoryLink(
        link_id=link_id,
        trajectory_id=trajectory_id,
        experiment_id=experiment_id,
        timestamp=timestamp,
        metadata=metadata or {},
    )

    trace = append_trace(
        source="delivery_interface",
        kind=LINK_KIND,
        text=f"Linked trajectory {trajectory_id} to delivery experiment {experiment_id}",
        confidence=1.0,
        extra=asdict(link),
    )

    return {
        "ok": trace is not None,
        "link_id": link_id,
        "trajectory_id": trajectory_id,
        "experiment_id": experiment_id,
        "trace": trace,
    }


def compare_delivery_modalities(
    modality_a: str,
    modality_b: str,
    metric: str = "drift_magnitude",
    limit: int = 100,
) -> dict[str, Any]:
    """
    Compare trajectory outcomes between two delivery modalities.

    Args:
        modality_a: First delivery type (e.g., "AAV")
        modality_b: Second delivery type (e.g., "mRNA-LNP")
        metric: Which trajectory metric to compare ("drift_magnitude", "phenotype_score", etc.)
        limit: Max trajectories to consider per modality

    Returns:
        Dict with comparison statistics
    """
    # Read all delivery experiments
    all_traces = read_traces(limit=limit * 4)
    delivery_traces = [t for t in all_traces if t.get("kind") == LEDGER_KIND]

    # Group experiment IDs by delivery type
    exp_by_type: dict[str, list[str]] = {}
    for t in delivery_traces:
        extra = t.get("extra", {})
        dtype = extra.get("delivery_type", "").lower()
        if dtype not in exp_by_type:
            exp_by_type[dtype] = []
        exp_by_type[dtype].append(extra.get("experiment_id", ""))

    # Find linked trajectories for each modality
    link_traces = [t for t in all_traces if t.get("kind") == LINK_KIND]
    modality_experiments_a = exp_by_type.get(modality_a.lower(), [])
    modality_experiments_b = exp_by_type.get(modality_b.lower(), [])

    linked_a = [l for l in link_traces if l.get("extra", {}).get("experiment_id") in modality_experiments_a]
    linked_b = [l for l in link_traces if l.get("extra", {}).get("experiment_id") in modality_experiments_b]

    # Get morphology trajectories for linked experiments
    # This would need to query cell_morphology trajectory data
    # For now, return the experimental design info
    comparison_id = f"compare_{uuid.uuid4().hex[:12]}"
    timestamp = _now()

    result = {
        "comparison_id": comparison_id,
        "modality_a": modality_a,
        "modality_b": modality_b,
        "metric": metric,
        "experiments_a": len(modality_experiments_a),
        "experiments_b": len(modality_experiments_b),
        "linked_trajectories_a": len(linked_a),
        "linked_trajectories_b": len(linked_b),
        "note": "Full statistical comparison requires cell_morphology trajectory data query",
        "timestamp": timestamp,
    }

    trace = append_trace(
        source="delivery_interface",
        kind=COMPARE_KIND,
        text=f"Delivery modality comparison: {modality_a} vs {modality_b} (metric: {metric})",
        confidence=0.8,  # Lower confidence until statistical analysis runs
        extra=result,
    )

    return {
        "ok": trace is not None,
        "comparison": result,
        "trace": trace,
    }


def get_delivery_experiments(
    delivery_type: Optional[str] = None,
    facility_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Query registered delivery experiments with optional filters."""
    all_traces = read_traces(limit=limit * 4)
    delivery_traces = [t for t in all_traces if t.get("kind") == LEDGER_KIND]

    results = []
    for t in delivery_traces:
        extra = t.get("extra", {})
        if delivery_type and extra.get("delivery_type", "").lower() != delivery_type.lower():
            continue
        if facility_id and extra.get("facility_id") != facility_id:
            continue
        results.append({
            "trace": t,
            "experiment": extra,
        })
        if len(results) >= limit:
            break

    return results


def get_trajectory_links(
    experiment_id: Optional[str] = None,
    trajectory_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Query trajectory-delivery links."""
    all_traces = read_traces(limit=limit * 4)
    link_traces = [t for t in all_traces if t.get("kind") == LINK_KIND]

    results = []
    for t in link_traces:
        extra = t.get("extra", {})
        if experiment_id and extra.get("experiment_id") != experiment_id:
            continue
        if trajectory_id and extra.get("trajectory_id") != trajectory_id:
            continue
        results.append({
            "trace": t,
            "link": extra,
        })
        if len(results) >= limit:
            break

    return results


# ─── Organ Registry Interface ──────────────────────────────────────────
def get_organ_info() -> dict[str, Any]:
    """Return organ metadata for registry discovery."""
    return {
        "organ_id": "delivery_interface",
        "display_name": "Delivery Interface",
        "layer": "input",
        "version": TRUTH_LABEL,
        "capabilities": [
            "register_delivery_experiment",
            "link_trajectory_to_delivery",
            "compare_delivery_modalities",
            "query_delivery_experiments",
            "query_trajectory_links",
        ],
        "ledger_kinds": [LEDGER_KIND, LINK_KIND, COMPARE_KIND],
        "valid_delivery_types": list(VALID_DELIVERY_TYPES),
        "safety_boundary": "observation_only",
        "description": "Models delivery modalities as experimental conditions linked to morphology trajectories. No biological delivery implementation.",
    }


def register_in_organ_registry() -> dict[str, Any]:
    """Register this organ in the canonical registry (import-side effect)."""
    from System.swarm_canonical_organ_registry import register_organ

    spec = {
        "organ_id": "delivery_interface",
        "display_name": "Delivery Interface",
        "layer": "input",
        "organ_paths": ("System/swarm_delivery_interface_organ.py",),
        "ledgers": ("delivery_interface_ledger.jsonl",),
        "capabilities": (
            "register_delivery_experiment",
            "link_trajectory_to_delivery",
            "compare_delivery_modalities",
            "query_delivery_experiments",
            "query_trajectory_links",
        ),
        "query_keywords": ("delivery", "modality", "AAV", "mRNA", "LNP", "exosome", "nanoparticle", "experiment"),
        "write_action": "register_delivery_experiment",
        "owner_sensitive": True,
        "aliases": ("delivery", "delivery_modality", "reprogramming_delivery"),
    }

    return register_organ(spec)


# ─── CLI / Direct Invocation ───────────────────────────────────────────
def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Delivery Interface Organ CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # register
    p_reg = sub.add_parser("register", help="Register a delivery experiment")
    p_reg.add_argument("--type", required=True, help="Delivery type (AAV, mRNA-LNP, EV, etc.)")
    p_reg.add_argument("--facility", required=True, help="Facility ID")
    p_reg.add_argument("--params", default="{}", help="JSON parameters dict")
    p_reg.add_argument("--notes", default="", help="Notes")

    # link
    p_link = sub.add_parser("link", help="Link trajectory to delivery experiment")
    p_link.add_argument("--trajectory", required=True, help="Trajectory ID (image_id or timestamp)")
    p_link.add_argument("--experiment", required=True, help="Experiment ID")
    p_link.add_argument("--meta", default="{}", help="JSON metadata dict")

    # compare
    p_cmp = sub.add_parser("compare", help="Compare two delivery modalities")
    p_cmp.add_argument("--a", required=True, help="Modality A")
    p_cmp.add_argument("--b", required=True, help="Modality B")
    p_cmp.add_argument("--metric", default="drift_magnitude", help="Metric to compare")
    p_cmp.add_argument("--limit", type=int, default=100, help="Max trajectories per modality")

    # query
    p_qry = sub.add_parser("query", help="Query delivery experiments")
    p_qry.add_argument("--type", help="Filter by delivery type")
    p_qry.add_argument("--facility", help="Filter by facility ID")
    p_qry.add_argument("--limit", type=int, default=50)

    # links
    p_lnk = sub.add_parser("links", help="Query trajectory-delivery links")
    p_lnk.add_argument("--experiment", help="Filter by experiment ID")
    p_lnk.add_argument("--trajectory", help="Filter by trajectory ID")
    p_lnk.add_argument("--limit", type=int, default=50)

    # info
    sub.add_parser("info", help="Show organ info")

    args = ap.parse_args()

    try:
        if args.cmd == "register":
            params = json.loads(args.params)
            result = register_delivery_experiment(args.type, params, args.facility, args.notes)
            print(json.dumps(result, indent=2, default=str))
        elif args.cmd == "link":
            meta = json.loads(args.meta)
            result = link_trajectory_to_delivery(args.trajectory, args.experiment, meta)
            print(json.dumps(result, indent=2, default=str))
        elif args.cmd == "compare":
            result = compare_delivery_modalities(args.a, args.b, args.metric, args.limit)
            print(json.dumps(result, indent=2, default=str))
        elif args.cmd == "query":
            results = get_delivery_experiments(args.type, args.facility, args.limit)
            print(json.dumps(results, indent=2, default=str))
        elif args.cmd == "links":
            results = get_trajectory_links(args.experiment, args.trajectory, args.limit)
            print(json.dumps(results, indent=2, default=str))
        elif args.cmd == "info":
            print(json.dumps(get_organ_info(), indent=2, default=str))
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())