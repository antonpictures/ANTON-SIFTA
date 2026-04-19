#!/usr/bin/env python3
"""
stigmergic_science_research_map.py — execution plan + literature ↔ SIFTA code map

This module is the **DYOR anchor** for “which science problems does stigmergic
code address?”  Each ``reference`` entry should be openable in a browser; when
we only have a book or paywalled article, we still cite a stable landing page.

**Not** a claim that SIFTA reimplements each paper — analogies and design
pressure are explicit in ``relation_note``.

Run::

    python3 System/stigmergic_science_research_map.py summary
    python3 System/stigmergic_science_research_map.py json | head

See also: ``System/m1_node_onboarding.T32_VERIFIED_REFERENCES`` (MARL / entropy
/ epistemics row set), ``Documents/RESEARCH_CODE_FISSION_STIGMERGIC_SUBSTRATE.md``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# Re-use verified MARL / entropy / epistemics URLs from Mini onboarding module.
try:
    from System.m1_node_onboarding import T32_VERIFIED_REFERENCES
except ImportError:  # pragma: no cover
    T32_VERIFIED_REFERENCES = []  # type: ignore[assignment]


EXECUTION_PLAN_STEPS: List[str] = [
    "Phase 0 — Inventory: enumerate all modules touching stigmergy (this file’s ``RESEARCH_MAP`` + repo grep).",
    "Phase 1 — Substrate hardening: keep append-only JSONL under POSIX flock (``ide_stigmergic_bridge``, entropy events, anchors).",
    "Phase 2 — Identity: every deposit and migration bundle carries ``homeworld_serial`` + ``source_ide``; never mix M5/M1 serials.",
    "Phase 3 — Epistemics: route high-impact claims through ``temporal_identity`` + ``stigmergic_epistemic_recorder`` (anchors, not chat).",
    "Phase 4 — Entropy dual-track: trainer choke-point calls ``swarmrl_entropy_hooks.refresh_entropy_dual_track`` + composition (``stigmergic_composition``).",
    "Phase 5 — Manifold pressure: Lagrangian λ feeds ``lagrangian_entropy_controller`` and metabolic throttle (``stgm_metabolic``).",
    "Phase 6 — Collective traces: ring buffer + optional ``stigmergic_entropy_events.jsonl`` for flock-level adaptation.",
    "Phase 7 — Regime physics: ``phase_transition_control`` / ``swarm_capacity_theorem`` expose ρ (stigmergic density) for gating.",
    "Phase 8 — Economics: STGM mint/store stays Ed25519-signed via ``crypto_keychain``; metabolic math never bypasses the ledger.",
    "Phase 9 — Cross-app memory: ``stigmergic_memory_bus`` for UI/process handoff; IDE dirt remains separate from Swarm chat.",
    "Phase 10 — Topology: Mac Mini uses ``IDE_ANTIGRAVITY_MINI``; migrations use ``swimmer_migration`` consent artifacts.",
    "Phase 11 — SwarmRL fork: wire ``Archive/swarmrl_upstream`` trainer hooks without bloating vendored tree.",
    "Phase 12 — Telemetry: ``telemetry_snapshot.py`` + exoskeleton clients as human-facing observability.",
    "Phase 13 — Science validation: pick 1–2 benchmark environments; log traces + anchors for reproducible ablations.",
    "Phase 14 — Documentation delta: when literature mapping changes, update this module (executable) first, prose docs second.",
]


# Keys: problem, sifta_mechanism, repo_paths, relation_note, references[{title,url,venue?,year?}]
RESEARCH_MAP: List[Dict[str, Any]] = [
    {
        "cluster": "foundations_stigmergy",
        "problem": "How do collectives coordinate complex labour without central control?",
        "sifta_mechanism": "Indirect coordination via shared filesystem traces, append-only logs, and UI pheromones instead of pairwise chat.",
        "repo_paths": [
            "System/ide_stigmergic_bridge.py",
            "System/stigmergic_wm.py",
            "Network/stigmergi_chat_bridge.py",
        ],
        "relation_note": "Biological stigmergy motivates the substrate shape; SIFTA instantiates *digital* traces.",
        "references": [
            {
                "title": "Grassé — La théorie de la stigmergie (termite nest reconstruction)",
                "venue": "Insectes Sociaux (1959)",
                "url": "https://link.springer.com/article/10.1007/BF02223791",
                "year": 1959,
            },
            {
                "title": "Bonabeau, Dorigo, Theraulaz — Swarm Intelligence: From Natural to Artificial Systems",
                "venue": "Oxford University Press (1999)",
                "url": "https://jmvidal.cse.sc.edu/lib/bonabeau99a.html",
                "year": 1999,
            },
        ],
    },
    {
        "cluster": "digital_pheromones_marl",
        "problem": "Decentralized MARL / multi-robot systems need scalable coordination signals.",
        "sifta_mechanism": "Virtual pheromone fields = JSONL traces + entropy buffers + telemetry snapshots consumed by training hooks.",
        "repo_paths": [
            "System/stigmergic_entropy_trace.py",
            "System/swarmrl_entropy_hooks.py",
            "System/swarm_entropy_bridge.py",
        ],
        "relation_note": "MARL papers below inform λ/entropy shaping; SIFTA composes tracks rather than copying full algorithms.",
        "references": [
            {
                "title": "Scalable MARL methods inspired by stigmergy and ant colonies",
                "venue": "arXiv",
                "url": "https://arxiv.org/abs/2105.03546",
                "year": 2021,
            },
            {
                "title": "Collective-behavior algorithms atlas (multi-agent coordination)",
                "venue": "arXiv",
                "url": "https://arxiv.org/abs/2103.11067",
                "year": 2021,
            },
        ],
    },
    {
        "cluster": "marl_safety_entropy_t32",
        "problem": "Constrained cooperative learning with exploration pressure (entropy) under safety or budget constraints.",
        "sifta_mechanism": "Lagrangian pressure on entropy coefficient + trace-buffer adaptation + harmonic/min composition.",
        "repo_paths": [
            "System/lagrangian_entropy_controller.py",
            "System/stigmergic_composition.py",
            "System/stigmergic_entropy_trace.py",
            "Kernel/passive_utility_generator.py",
        ],
        "relation_note": "Rows imported as ``T32_VERIFIED_REFERENCES`` (see ``m1_node_onboarding``) — URLs spot-checked 2026-04.",
        "references": [],  # filled at runtime from T32_VERIFIED_REFERENCES
    },
    {
        "cluster": "epistemic_multi_agent_llm",
        "problem": "LLM-based multi-agent stacks hallucinate, sycophant, and mis-trust peers.",
        "sifta_mechanism": "Grounding levels, observation log, epistemic anchors mirroring to IDE trace.",
        "repo_paths": [
            "System/temporal_identity.py",
            "System/stigmergic_epistemic_recorder.py",
        ],
        "relation_note": "Humility / peer-reliability literature informs ``temporal_identity`` policy, not model weights.",
        "references": [
            {
                "title": "HumbleBench — epistemic humility in vision-language models",
                "venue": "arXiv:2509.09658",
                "url": "https://arxiv.org/abs/2509.09658",
                "year": 2025,
            },
            {
                "title": "Epistemic Context Learning (ECL) — trust in LLM multi-agent systems",
                "venue": "OpenReview",
                "url": "https://openreview.net/forum?id=w65sdTnOUw",
                "year": 2024,
            },
        ],
    },
    {
        "cluster": "resource_allocation_dual",
        "problem": "Online resource allocation and primal–dual views of ‘prices’ under load.",
        "sifta_mechanism": "Metabolic mint/store curves keyed by normalized λ pressure (stigmergic economy throttle).",
        "repo_paths": ["System/stgm_metabolic.py", "System/value_field.py"],
        "relation_note": "Dual / shadow-price intuition aligns with metabolic throttling; ledger remains cryptographically grounded.",
        "references": [
            {
                "title": "Balseiro et al. — Dual mirror descent for online allocation",
                "venue": "PMLR / ICML proceedings",
                "url": "https://proceedings.mlr.press/v119/balseiro20a.html",
                "year": 2020,
            },
            {
                "title": "Primal-dual learning for online allocation (arxiv)",
                "venue": "arXiv",
                "url": "https://arxiv.org/abs/2411.01899",
                "year": 2024,
            },
        ],
    },
    {
        "cluster": "append_only_shared_logs",
        "problem": "Multi-writer coordination needs durable, replayable ordering semantics.",
        "sifta_mechanism": "Locked JSONL append + deterministic readers; blackboard/fission narrative in research doc.",
        "repo_paths": [
            "System/jsonl_file_lock.py",
            "Documents/RESEARCH_CODE_FISSION_STIGMERGIC_SUBSTRATE.md",
        ],
        "relation_note": "FuzzyLog is **partial-order shared log** research (OSDI’18), not arXiv:2202.10445.",
        "references": [
            {
                "title": "The FuzzyLog — partially ordered shared log (OSDI 2018)",
                "venue": "Microsoft Research",
                "url": "https://www.microsoft.com/en-us/research/publication/the-fuzzylog-a-partially-ordered-shared-log/",
                "year": 2018,
            },
            {
                "title": "A Grounded Theory of Coordination in Remote-First Software Teams",
                "venue": "arXiv:2202.10445",
                "url": "https://arxiv.org/abs/2202.10445",
                "year": 2022,
            },
        ],
    },
    {
        "cluster": "distributed_topology_trust",
        "problem": "Multi-node agent systems need acceptance cues and provenance-friendly handoffs.",
        "sifta_mechanism": "Migration consent bundles (Ed25519), node serial registry, Mini onboarding checklist.",
        "repo_paths": [
            "System/swimmer_migration.py",
            "System/crypto_keychain.py",
            "System/m1_node_onboarding.py",
            "System/ide_stigmergic_bridge.py",
        ],
        "relation_note": "Socio-technical ‘acceptance’ parallels TAM/trust literature cited in live trace; ops remain cryptographic.",
        "references": [
            {
                "title": "Davis — Technology Acceptance Model (1989) — perceived usefulness / ease of use",
                "venue": "classic MIS (use secondary summaries)",
                "url": "https://en.wikipedia.org/wiki/Technology_acceptance_model",
                "year": 1989,
            },
        ],
    },
    {
        "cluster": "regime_gating_science_models",
        "problem": "Detect congestion / early-warning signals in coupled multi-agent flows (incl. compartmental models).",
        "sifta_mechanism": "ρ stigmergic density, EWS scores, optional epidemic-style demos in desktop simulators.",
        "repo_paths": [
            "System/phase_transition_control.py",
            "System/swarm_capacity_theorem.py",
            "System/stress_test_thermodynamics.py",
            "System/graph_dual_aggregator.py",
            "System/dream_engine.py",
            "Applications/sifta_quantum_epi_sim.py",
        ],
        "relation_note": "Bridges control-theory / compartmental thinking to UI and policy gating — calibrate against domain science separately.",
        "references": [
            {
                "title": "Multi-agent coordination and control using stigmergy (robotics)",
                "venue": "ScienceDirect / Robotics and Autonomous Systems",
                "url": "https://www.sciencedirect.com/science/article/abs/pii/S0166361503001234",
                "year": 2004,
            },
        ],
    },
    {
        "cluster": "lifecycle_pruning_autopoiesis",
        "problem": "Adaptive systems must retire low-utility structure (apoptosis) while maintaining identity.",
        "sifta_mechanism": "Apoptosis engines, failure harvesting, genome/mycelial metaphors tied to fitness pressure.",
        "repo_paths": [
            "System/apoptosis.py",
            "System/apoptosis_engine.py",
            "System/failure_harvesting.py",
            "System/mycelial_genome.py",
        ],
        "relation_note": "Biological autopoiesis/apoptosis are analogies for policy; cite classics, do not claim biological fidelity.",
        "references": [
            {
                "title": "Autopoiesis — Maturana & Varela (overview)",
                "venue": "Wikipedia (entry point to primary literature)",
                "url": "https://en.wikipedia.org/wiki/Autopoiesis",
                "year": None,
            },
        ],
    },
    {
        "cluster": "fission_governance_chorus",
        "problem": "When should work split, merge, or route across subsystems under constraints?",
        "sifta_mechanism": "Fission core, governor, chorus, Lagrangian manifold, graph dual aggregation, consigliere routing.",
        "repo_paths": [
            "System/fission_core.py",
            "System/lagrangian_constraint_manifold.py",
            "System/graph_dual_aggregator.py",
            "System/chorus_engine.py",
            "Kernel/repair_loop_suppressor.py",
            "Network/sifta_consigliere.py",
        ],
        "relation_note": "Connects to ‘code fission’ research note; formal proofs are environment-specific.",
        "references": [],
    },
]

# Code paths that mention stigmergy / pheromone field (repo audit); not every row has a 1:1 paper.
REPO_WIDE_STIGMERGIC_TOUCHPOINTS: List[Dict[str, str]] = [
    {"path": "Applications/epistemic_mesh_sim.py", "role": "Epistemic mesh simulation"},
    {"path": "Applications/epistemic_mesh_widget.py", "role": "Epistemic mesh UI"},
    {"path": "Applications/sifta_canvas_widget.py", "role": "Canvas / stigmergic visualization"},
    {"path": "Applications/sifta_cartography_widget.py", "role": "Territorial / map metaphors"},
    {"path": "Applications/sifta_crucible_swarm_sim.py", "role": "Crucible swarm sim UI"},
    {"path": "Applications/sifta_cyborg_body.py", "role": "Body metaphor + swarm hooks"},
    {"path": "Applications/sifta_nle.py", "role": "NLE app layer"},
    {"path": "Applications/sifta_quantum_epi_sim.py", "role": "Epidemic / stigmergic tracing demo"},
    {"path": "Applications/sifta_swarm_browser.py", "role": "Swarm browser shell"},
    {"path": "Applications/sifta_swarm_chat.py", "role": "Swarm chat + memory bus integration"},
    {"path": "Applications/sifta_urban_resilience_sim.py", "role": "Urban resilience simulation"},
    {"path": "Applications/sifta_writer_widget.py", "role": "Writer + stigmergic doc"},
    {"path": "Kernel/repair_loop_suppressor.py", "role": "Governance / suppression signals"},
    {"path": "Kernel/pheromone.py", "role": "Pheromone field kernel primitive"},
    {"path": "Network/sifta_consigliere.py", "role": "Routing / advisory wormhole"},
    {"path": "Network/stigmergi_chat_bridge.py", "role": "Web chat ↔ repo stigmergy"},
    {"path": "Utilities/repair.py", "role": "Repair / healing utilities"},
    {"path": "sifta_exoskeleton/lib/src/infrastructure/stigmergic_telemetry_client.dart", "role": "Flutter telemetry client"},
    {"path": "sifta_os_desktop.py", "role": "Desktop shell (stigmergic WM hooks)"},
    {"path": "System/apoptosis.py", "role": "Apoptosis policy hooks"},
    {"path": "System/apoptosis_engine.py", "role": "Apoptosis engine"},
    {"path": "System/casino_vault.py", "role": "Vault / economic substrate"},
    {"path": "System/chorus_engine.py", "role": "Chorus / multi-voice coordination"},
    {"path": "System/constraint_memory_selector.py", "role": "Constraint-aware memory selection"},
    {"path": "System/context_preloader.py", "role": "Context preload + swarm hints"},
    {"path": "System/diagnostic_swarm.py", "role": "Diagnostic swarm runner"},
    {"path": "System/dream_engine.py", "role": "Dream / regime narrative engine"},
    {"path": "System/event_density_clock.py", "role": "Temporal event density"},
    {"path": "System/failure_harvesting.py", "role": "Failure → evolutionary pressure"},
    {"path": "System/fission_core.py", "role": "Code / task fission core"},
    {"path": "System/fluid_firmware.py", "role": "Stigmergic routing / swimmers"},
    {"path": "System/global_cognitive_interface.py", "role": "Global cognitive I/O"},
    {"path": "System/graph_dual_aggregator.py", "role": "Graph dual + ρ gating"},
    {"path": "System/ide_trace_consumer.py", "role": "IDE trace consumption"},
    {"path": "System/lagrangian_constraint_manifold.py", "role": "Constraint manifold geometry"},
    {"path": "System/mycelial_genome.py", "role": "Genome / mycelial memory metaphor"},
    {"path": "System/sensory_cortex.py", "role": "Sensory integration"},
    {"path": "System/stigmergic_canvas.py", "role": "Stigmergic canvas helper"},
    {"path": "System/stigmergic_entropy.py", "role": "Environment-conditioned entropy (parallel to trace)"},
    {"path": "System/stigmergic_science_research_map.py", "role": "This DYOR / plan map"},
    {"path": "System/stigmergic_vision.py", "role": "Vision / edge stigmergy"},
    {"path": "System/stress_test_thermodynamics.py", "role": "Thermodynamic stress + ρ"},
    {"path": "System/swarm_boot.py", "role": "Logical swarm registry bootstrap"},
    {"path": "System/swarm_experience.py", "role": "Swarm experience buffer"},
    {"path": "System/tab_heartbeat.py", "role": "Tab / session heartbeat"},
    {"path": "System/telemetry_snapshot.py", "role": "Unified telemetry snapshot"},
    {"path": "System/territory_consciousness.py", "role": "Territory awareness"},
    {"path": "System/vision_processor_worker.py", "role": "Vision worker stigmergy"},
    {"path": "tests/test_stigmergic_economy.py", "role": "Stigmergic economy tests"},
    {"path": "tests/test_vision_processor_worker.py", "role": "Vision worker tests"},
]


def _hydrate_t32_rows() -> None:
    for row in RESEARCH_MAP:
        if row.get("cluster") == "marl_safety_entropy_t32":
            refs: List[Dict[str, Any]] = []
            for p in T32_VERIFIED_REFERENCES:
                u = p.get("url_pdf") or p.get("url_abstract") or p.get("url_abs") or p.get("url_proceedings") or p.get("url_forum")
                if not u:
                    continue
                refs.append(
                    {
                        "title": f"{p.get('id')}: {p.get('title', '')}",
                        "venue": p.get("venue", ""),
                        "url": u,
                        "maps_to_repo": p.get("maps_to_repo"),
                    }
                )
            row["references"] = refs
            break


def summary_text() -> str:
    _hydrate_t32_rows()
    lines = ["=== EXECUTION PLAN ===", *EXECUTION_PLAN_STEPS, "", "=== RESEARCH CLUSTERS ==="]
    for block in RESEARCH_MAP:
        lines.append(f"- [{block['cluster']}] {block['problem']}")
        lines.append(f"    mechanism: {block['sifta_mechanism']}")
        lines.append(f"    repo: {', '.join(block['repo_paths'])}")
        lines.append(f"    note: {block['relation_note']}")
        for ref in block.get("references", [])[:6]:
            lines.append(f"    • {ref.get('title')} — {ref.get('url')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def as_jsonable() -> Dict[str, Any]:
    _hydrate_t32_rows()
    return {
        "execution_plan": EXECUTION_PLAN_STEPS,
        "research_map": RESEARCH_MAP,
        "repo_wide_touchpoints": REPO_WIDE_STIGMERGIC_TOUCHPOINTS,
    }


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
    if cmd == "json":
        print(json.dumps(as_jsonable(), indent=2))
    elif cmd == "touchpoints":
        for row in sorted(REPO_WIDE_STIGMERGIC_TOUCHPOINTS, key=lambda r: r["path"]):
            print(f"{row['path']}\t{row['role']}")
    else:
        print(summary_text(), end="")
