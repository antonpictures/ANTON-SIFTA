#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA OS — Mac Mini (M1 Sentry) onboarding + T32 bibliography anchors
# ─────────────────────────────────────────────────────────────
# Use with repo root on PYTHONPATH, e.g.:
#   cd /path/to/ANTON_SIFTA && python3 -c "from System.m1_node_onboarding import onboarding_checklist; print('\\n'.join(onboarding_checklist()))"
# ─────────────────────────────────────────────────────────────
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from System.ide_stigmergic_bridge import IDE_ANTIGRAVITY_MINI, NODE_M1_SENTRY  # noqa: E402

__all__ = [
    "IDE_ANTIGRAVITY_MINI",
    "NODE_M1_SENTRY",
    "T32_VERIFIED_REFERENCES",
    "T32_NARRATIVE_CORRECTIONS",
    "onboarding_checklist",
    "passive_utility_path",
]

# Antigravity T32 names — each row is independently spot-checkable (URLs stable as of 2026-04).
T32_VERIFIED_REFERENCES: List[Dict[str, Any]] = [
    {
        "id": "Scal-MAPPO-L",
        "title": "Scalable Constrained Policy Optimization for Safe Multi-Agent Reinforcement Learning",
        "venue": "NeurIPS 2024",
        "maps_to_repo": "System/lagrangian_entropy_controller.py",
        "url_abstract": "https://proceedings.neurips.cc/paper_files/paper/2024/hash/fa76985f05e0a25c66528308dda33de0-Abstract-Conference.html",
        "url_pdf": "https://proceedings.neurips.cc/paper_files/paper/2024/file/fa76985f05e0a25c66528308dda33de0-Paper-Conference.pdf",
    },
    {
        "id": "ESC-MARL",
        "title": "Entropy Seeking Constrained Multiagent Reinforcement Learning",
        "venue": "AAMAS 2024",
        "maps_to_repo": "System/stigmergic_composition.py",
        "url_pdf": "https://www.ifaamas.org/Proceedings/aamas2024/pdfs/p2141.pdf",
    },
    {
        "id": "TEE",
        "title": "Toward Efficient Multi-Agent Exploration With Trajectory Entropy Maximization (ICLR 2025)",
        "venue": "ICLR 2025",
        "maps_to_repo": "System/stigmergic_entropy_trace.py",
        "url_pdf": "https://openreview.net/pdf?id=YvKJGYL4j7",
    },
    {
        "id": "SAEIR",
        "title": "Sequentially Accumulated Entropy Intrinsic Reward for Cooperative Multi-Agent RL with Sparse Reward",
        "venue": "IJCAI 2024",
        "maps_to_repo": "Kernel/passive_utility_generator.py",
        "url_proceedings": "https://www.ijcai.org/proceedings/2024/454",
    },
    {
        "id": "HumbleBench",
        "title": "HumbleBench: Measuring Epistemic Humility in Vision-Language Models",
        "venue": "arXiv (2509.09658)",
        "maps_to_repo": "System/temporal_identity.py",
        "url_abs": "https://arxiv.org/abs/2509.09658",
    },
    {
        "id": "ECL",
        "title": "Epistemic Context Learning: Building Trust the Right Way in LLM-Based Multi-Agent Systems",
        "venue": "OpenReview",
        "maps_to_repo": "System/temporal_identity.py",
        "url_forum": "https://openreview.net/forum?id=w65sdTnOUw",
    },
]

T32_NARRATIVE_CORRECTIONS: Dict[str, str] = {
    "humblebench": (
        "T32 said 'arxiv 2024'; the preprint is arXiv:2509.09658 (Sept 2025 numbering). "
        "Concept still aligns with temporal_identity humility — fix the year string in prose."
    ),
    "entropy_module_name": (
        "Repo module is stigmergic_entropy_trace.py (StigmergicEntropyController / trace buffer), "
        "not stigmergic_entropy.py."
    ),
    "passive_utility_path": (
        "SAEIR maps to Kernel/passive_utility_generator.py, not under System/."
    ),
    "alignment_scope": (
        "Literature validates *design analogies* (Lagrangian constraints, entropy shaping, "
        "epistemic calibration); SIFTA is not a reimplementation of those baselines."
    ),
}


def passive_utility_path() -> str:
    return os.path.join(_REPO_ROOT, "Kernel", "passive_utility_generator.py")


def onboarding_checklist() -> List[str]:
    """Operational steps for Antigravity (or Cursor) on the Mac Mini after git clone."""
    trace = os.path.join(_REPO_ROOT, ".sifta_state", "ide_stigmergic_trace.jsonl")
    return [
        f"Set homeworld_serial to {NODE_M1_SENTRY} on this machine only (never mix with M5).",
        f"Use source_ide={IDE_ANTIGRAVITY_MINI!r} in ide_stigmergic_bridge.deposit for Mini-origin traces.",
        "Run System/bootstrap_pki.py on the Mini if node PKI is not initialized (.cursorrules state).",
        "git pull --rebase (use -X theirs only if resolving dead_drop conflicts per ops note).",
        f"Read recent stigmergy: tail {trace} or forage(limit=80) in Python.",
        "Optional: temporal_identity.record_observation(...) for REPO_TOOL grounding after tool use.",
        "Swimmer handoff: read System/swimmer_migration.py; initiate_migration only for agents anchored to this serial.",
        "Deposit a short topology_ack row (kind=topology_event) so M5 foragers see the Mini as live.",
    ]


if __name__ == "__main__":
    print("NODE_M1_SENTRY =", NODE_M1_SENTRY)
    print("IDE_ANTIGRAVITY_MINI =", IDE_ANTIGRAVITY_MINI)
    print("\n--- Checklist ---\n")
    for i, line in enumerate(onboarding_checklist(), 1):
        print(f"{i}. {line}")
