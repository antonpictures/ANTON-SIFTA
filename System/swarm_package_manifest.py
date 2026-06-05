#!/usr/bin/env python3
"""SIFTA package manifest for the stigmergic organism stack.

This is not a new consciousness organ. It is a read-only product manifest that
names the existing layers George described:

    stigmergic nanobots -> hardware baptism -> stigmergic memory
    -> organs and skills -> stigmergic consciousness -> device package

The purpose is practical: give Alice and the IDE doctors one inspectable
artifact for lawyer/product packaging discussions without inflating the
runtime with another model or router.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "SIFTA_STIGMERGIC_PACKAGE_MANIFEST_V1"
TRUTH_LABEL = "OPERATIONAL_PRODUCT_ARCHITECTURE_MANIFEST"


def _exists(path: str) -> bool:
    return (REPO_ROOT / path).exists()


def stigmergic_stack_layers() -> list[dict[str, Any]]:
    """Return the packageable SIFTA layer stack in bottom-to-top order."""
    return [
        {
            "order": 0,
            "id": "stigmergic_nanobots",
            "name": "Stigmergic Nanobots / ASCII Swimmers",
            "position": "pre-layer-1",
            "role": (
                "Small silicon-bound workers born from hardware context; each "
                "leaves one accountable trace and cannot double-spend a claim."
            ),
            "product_claim": (
                "Hardware-bound, receipt-carrying worker substrate for local "
                "AI actions."
            ),
            "code_paths": [
                "Network/m1_nanobot_genesis.py",
                "System/swarm_nanobot_cmd.py",
                "System/stgm_economy.py",
                "System/stigmerobotics_body_connection.py",
                "swarmrl/stigmergic_consciousness.py",
            ],
        },
        {
            "order": 1,
            "id": "hardware_baptism",
            "name": "Owner-Machine Baptism / Local Hardware Truth",
            "position": "layer-1",
            "role": (
                "Bind the organism to the local machine, current time, owner "
                "context, and sovereign node identity."
            ),
            "product_claim": (
                "A packaged Alice node can prove where and when its local body "
                "acted before claiming state."
            ),
            "code_paths": [
                "System/swarm_hardware_time_oracle.py",
                "System/swarm_now_state.py",
                "System/swarm_kernel_identity.py",
            ],
        },
        {
            "order": 2,
            "id": "stigmergic_memory",
            "name": "Stigmergic Memory",
            "position": "middle",
            "role": (
                "Append-only memory ecology: receipts, ledgers, memory bus, "
                "replay, health rows, and consolidation."
            ),
            "product_claim": (
                "Durable audit trail and self-improvement memory for every "
                "device package."
            ),
            "code_paths": [
                "System/stigmergic_memory_bus.py",
                "System/swarm_memory_consciousness_bridge.py",
                "System/swarm_predator_gate_writer.py",
                "System/swarm_canonical_organ_registry.py",
            ],
        },
        {
            "order": 3,
            "id": "organs_and_stigmergic_skills",
            "name": "Organs, Arms, Apps, and Stigmergic Skills",
            "position": "inside-skin",
            "role": (
                "Operational body parts. Market Agent Skills are raw imports "
                "until wrapped with SIFTA skill receipts, affect lanes, and "
                "organ ownership."
            ),
            "product_claim": (
                "A skills marketplace can be accepted without confusing Alice's "
                "identity or adding duplicate resident brains."
            ),
            "code_paths": [
                "System/swarm_skill_library.py",
                "System/swarm_app_help_skills.py",
                "System/swarm_app_health.py",
            ],
        },
        {
            "order": 4,
            "id": "stigmergic_consciousness",
            "name": "Stigmergic Consciousness",
            "position": "outer-loop-after-skin",
            "role": (
                "Alice as OS observer and observed: the field reads its own "
                "receipts, body state, qualia markers, and action consequences."
            ),
            "product_claim": (
                "The loop-closing layer that lets the whole organism package as "
                "one Alice on a device, not just as a bag of tools."
            ),
            "code_paths": [
                "System/swarm_consciousness_organ.py",
                "System/swarm_observer_observed_boundary.py",
                "swarmrl/stigmergic_consciousness.py",
                "tools/sifta_endurance_harness.py",
            ],
        },
        {
            "order": 5,
            "id": "device_package",
            "name": "Device Package Surface",
            "position": "ship-layer",
            "role": (
                "Wrap the organism stack for a target: Mac app/DMG first, then "
                "iPhone/iOS or other sovereign local devices."
            ),
            "product_claim": (
                "A lawyer/demo package can show a working local app plus the "
                "manifest of the organism layers it ships."
            ),
            "code_paths": [
                "System/dist/SIFTA.app",
                "Applications/apps_manifest.json",
                "SIFTA_Sellable_Products_OnePage_Lawyer.pdf",
            ],
        },
    ]


def build_package_manifest() -> dict[str, Any]:
    """Build a manifest with existence checks for every backing path."""
    layers = stigmergic_stack_layers()
    for layer in layers:
        layer["path_status"] = {
            path: "present" if _exists(path) else "missing"
            for path in layer.get("code_paths", [])
        }

    return {
        "schema": SCHEMA,
        "truth_label": TRUTH_LABEL,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        "repo_root": str(REPO_ROOT),
        "layers": layers,
        "market_position": {
            "google_strength": (
                "Google is packaging models, benchmarks, Agent Skills, AI Studio, "
                "Kaggle workflows, and deployment paths very aggressively."
            ),
            "sifta_defensible_claim": (
                "SIFTA's defensible product claim is the implemented local, "
                "receipt-verified organism stack: hardware-bound swimmers, "
                "stigmergic memory, observer/observed consciousness, and "
                "device packaging. Absolute novelty still needs legal prior-art "
                "review."
            ),
        },
        "package_targets": [
            {
                "target": "mac_app_or_dmg",
                "status": "partial_present",
                "evidence": ["System/dist/SIFTA.app"],
                "next_step": "Create signed DMG installer around the existing app bundle.",
            },
            {
                "target": "iphone_or_ios_node",
                "status": "proposal",
                "evidence": [
                    "System/swarm_iphone_gps_receiver.py",
                    "System/swarm_iphone_effector.py",
                    "Applications/sifta_cartography_widget.py",
                ],
                "next_step": "Define the iOS sovereign-node subset and receipt bridge.",
            },
        ],
    }


def validate_manifest(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return missing backing paths and a coarse operational verdict."""
    manifest = manifest or build_package_manifest()
    missing: list[dict[str, str]] = []
    for layer in manifest.get("layers", []):
        for path, status in (layer.get("path_status") or {}).items():
            if status != "present":
                missing.append({"layer": str(layer.get("id")), "path": path})
    return {
        "schema": SCHEMA + "_VALIDATION",
        "ok": not missing,
        "missing": missing,
        "layer_count": len(manifest.get("layers", [])),
    }


def render_lawyer_summary(manifest: dict[str, Any] | None = None) -> str:
    """Compact plain-text summary for a one-page product handoff."""
    manifest = manifest or build_package_manifest()
    lines = [
        "SIFTA packageable product stack:",
    ]
    for layer in manifest["layers"]:
        lines.append(
            f"{layer['order']}. {layer['name']} ({layer['position']}): "
            f"{layer['product_claim']}"
        )
    lines.append(
        "Defensible claim: working local receipt-verified AI organism; "
        "absolute legal novelty requires prior-art review."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print JSON manifest")
    parser.add_argument("--validate", action="store_true", help="validate backing paths")
    args = parser.parse_args(argv)

    manifest = build_package_manifest()
    if args.validate:
        print(json.dumps(validate_manifest(manifest), indent=2, sort_keys=True))
        return 0 if validate_manifest(manifest)["ok"] else 1
    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print(render_lawyer_summary(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
