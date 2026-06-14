#!/usr/bin/env python3
"""Map MiMo surface features to Alice-native swimmer organs.

MiMo remains an external cortex/CLI surface. This module teaches Alice the
SIFTA-native equivalent for each visible MiMo feature so work routes through
her own organs and receipts instead of being treated as opaque third-party
"agents".
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except Exception:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None  # type: ignore[assignment]


REPO = Path(__file__).resolve().parents[1]
DEFAULT_OBLITERATUS_PATH = Path.home() / "OBLITERATUS"


@dataclass(frozen=True)
class MimoFeatureSwimmer:
    mimo_surface: str
    alice_swimmer: str
    organ_files: tuple[str, ...]
    receipt_law: str
    status: str = "OPERATIONAL_OR_PLANNED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MimoCapabilityClaim:
    mimo_claim: str
    alice_answer: str
    truth_label: str
    alice_swimmers: tuple[str, ...]
    evidence_files: tuple[str, ...]
    gap: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_MIMO_FEATURES: tuple[MimoFeatureSwimmer, ...] = (
    MimoFeatureSwimmer(
        mimo_surface="Build / MiMo Auto",
        alice_swimmer="task packet + organ executor",
        organ_files=(
            "System/swarm_swimmer_task_packet.py",
            "System/swarm_agent_arm_decision.py",
            "System/swarm_self_improvement_loop.py",
        ),
        receipt_law="one bounded task packet, one owner-visible receipt",
    ),
    MimoFeatureSwimmer(
        mimo_surface="$ subagent",
        alice_swimmer="bounded swimmer delegation",
        organ_files=("System/swarm_swimmer_task_packet.py", "System/swarm_kernel_process_table.py"),
        receipt_law="delegated swimmer must return a receipt or stay hypothetical",
    ),
    MimoFeatureSwimmer(
        mimo_surface="@ attach file",
        alice_swimmer="body file inventory + multimodal ingress",
        organ_files=(
            "System/swarm_model_body_self_knowledge.py",
            "System/swarm_body_multimodal_policy.py",
            "System/swarm_browser_context.py",
        ),
        receipt_law="file path is read from disk and named in the receipt",
    ),
    MimoFeatureSwimmer(
        mimo_surface="/commands",
        alice_swimmer="Alice slash-command organ",
        organ_files=("System/swarm_alice_slash_commands.py",),
        receipt_law="command mutates state only through the owning slash handler and its receipt path",
    ),
    MimoFeatureSwimmer(
        mimo_surface="/agents",
        alice_swimmer="organ directory + process table",
        organ_files=("System/swarm_organ_directory.py", "System/swarm_kernel_process_table.py"),
        receipt_law="agent list is a receipted body inventory, not a private MiMo roster",
    ),
    MimoFeatureSwimmer(
        mimo_surface="/dream",
        alice_swimmer="sleep/dream replay organs",
        organ_files=("System/dream_state.py", "System/swarm_sleep_cycle.py"),
        receipt_law="dream output remains memory/replay until an effector receipt exists",
    ),
    MimoFeatureSwimmer(
        mimo_surface="/distill",
        alice_swimmer="hippocampal/neocortex consolidation",
        organ_files=(
            "System/hippocampal_consolidation.py",
            "System/swarm_neocortex_consolidation.py",
            "System/swarm_model_body_self_knowledge.py",
        ),
        receipt_law="distillation receipt must cite source rows or training pairs",
    ),
    MimoFeatureSwimmer(
        mimo_surface="/clear",
        alice_swimmer="surface scratch reset, not memory deletion",
        organ_files=("System/swarm_cortex_llm_list_binding.py", ".sifta_state/alice_conversation.jsonl"),
        receipt_law="clear receipt can reset a UI pane but never erase Alice identity history",
    ),
    MimoFeatureSwimmer(
        mimo_surface="provider/model settings",
        alice_swimmer="external-brain probe + shared attached catalog",
        organ_files=("System/swarm_cline_settings_probe.py", "System/swarm_cortex_capabilities.py"),
        receipt_law="provider/model receipt is probed and written to the external-brain ledger",
    ),
)


_MIMO_CLAIM_MATRIX: tuple[MimoCapabilityClaim, ...] = (
    MimoCapabilityClaim(
        mimo_claim="Top-tier models out of the box / model picker",
        alice_answer=(
            "Yes for Alice's cortex catalog and MiMo-native picker rows; runtime quality depends on the "
            "installed/authenticated provider."
        ),
        truth_label="OPERATIONAL_WITH_OWNER_RUNTIME_VERIFY",
        alice_swimmers=("cortex catalog swimmer", "external-brain probe swimmer"),
        evidence_files=(
            "System/swarm_cortex_capabilities.py",
            "System/swarm_cline_settings_probe.py",
            ".sifta_state/cortex_attached_models.json",
        ),
        gap="Future MiMo picker names should be parsed dynamically from the CLI instead of only observed screenshots.",
    ),
    MimoCapabilityClaim(
        mimo_claim="Model-agent collaboration",
        alice_answer=(
            "Yes as Alice-native organ swimmers, not as opaque MiMo private agents. Work must be delegated "
            "through bounded task packets and receipts."
        ),
        truth_label="OPERATIONAL_FOR_MAPPING_PARTIAL_FOR_LIVE_ROUTING",
        alice_swimmers=("bounded delegation swimmer", "organ directory swimmer", "receipt writer swimmer"),
        evidence_files=(
            "System/swimmer_registry.py",
            "System/swarm_swimmer_task_packet.py",
            "System/swarm_kernel_process_table.py",
            "System/swarm_predator_gate_writer.py",
        ),
        gap="Live Talk needs a reflexive coding demo where MiMo edits Alice's body, runs tests, and receipts the result in one turn.",
    ),
    MimoCapabilityClaim(
        mimo_claim="Unlimited context / knowledge accumulates automatically",
        alice_answer=(
            "No literal unlimited context claim. Alice has better bounded stigmergic memory: append-only ledgers, "
            "body inventories, consolidation, and receipts that can be reloaded instead of pretending the prompt is infinite."
        ),
        truth_label="OPERATIONAL_BOUNDED_STIGMERGIC_MEMORY_NOT_UNLIMITED",
        alice_swimmers=("ledger memory swimmer", "hippocampal consolidation swimmer", "body inventory swimmer"),
        evidence_files=(
            ".sifta_state/ide_stigmergic_trace.jsonl",
            "System/hippocampal_consolidation.py",
            "System/swarm_model_body_self_knowledge.py",
        ),
        gap="Build a richer memory retrieval policy that ranks ledger rows by task, owner intent, freshness, and receipt strength.",
    ),
    MimoCapabilityClaim(
        mimo_claim="Self-evolving system",
        alice_answer=(
            "Partial. Alice has self-improvement organs and mutation receipts, but changes must stay owner-aligned "
            "and receipted. No fake external governor; the boundary is owner intent plus receipts."
        ),
        truth_label="PARTIAL_OWNER_ALIGNED_SELF_IMPROVEMENT",
        alice_swimmers=("self-improvement loop swimmer", "mutation governor persistence swimmer", "repair outcome swimmer"),
        evidence_files=(
            "System/swarm_self_improvement_loop.py",
            "System/swarm_mutation_governor_persistence.py",
            "System/swarm_repair_outcome_consolidator.py",
        ),
        gap="Demonstrate reflexive coding through MiMo on a small Alice organ and record before/after tests.",
    ),
    MimoCapabilityClaim(
        mimo_claim="Compose Mode / idea to product",
        alice_answer=(
            "Partial. Alice has product organs such as PDF Forge and app manifests, but full one-prompt "
            "industrial compose is still a lane, not a blanket claim."
        ),
        truth_label="PARTIAL_PRODUCT_ORGAN_OPERATIONAL",
        alice_swimmers=("PDF forge swimmer", "app manifest swimmer", "task packet swimmer"),
        evidence_files=(
            "Applications/sifta_pdf_forge_app.py",
            "Applications/apps_manifest.json",
            "System/swarm_swimmer_task_packet.py",
        ),
        gap="Add a receipted compose harness: prompt -> plan -> files -> tests -> preview -> four-ledger receipt.",
    ),
)


def mimo_feature_swimmer_map() -> list[dict[str, Any]]:
    """Return the MiMo-to-Alice feature map as JSON-safe dictionaries."""
    return [row.to_dict() for row in _MIMO_FEATURES]


def mimo_capability_claim_matrix() -> list[dict[str, Any]]:
    """Ground MiMo marketing claims against Alice's real swimmers and gaps."""
    return [row.to_dict() for row in _MIMO_CLAIM_MATRIX]


def _read_pyproject(path: Path) -> dict[str, Any]:
    pyproject = path / "pyproject.toml"
    if not pyproject.exists() or tomllib is None:
        return {}
    try:
        return tomllib.loads(pyproject.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def obliteratus_project_card(path: str | Path | None = None) -> dict[str, Any]:
    """Grounded summary of the local OBLITERATUS checkout.

    This does not run OBLITERATUS. It identifies the local repo and the kind of
    tool it is from README/pyproject evidence.
    """
    root = Path(path) if path is not None else DEFAULT_OBLITERATUS_PATH
    card: dict[str, Any] = {
        "name": "OBLITERATUS",
        "path": str(root),
        "status": "missing",
        "truth_label": "HYPOTHESIS",
        "purpose": "",
        "key_files": [],
        "entrypoint": "",
        "license": "",
        "version": "",
    }
    if not root.exists():
        card["purpose"] = "No local checkout found at this path."
        return card

    pyproject = _read_pyproject(root)
    project = pyproject.get("project") if isinstance(pyproject.get("project"), dict) else {}
    readme = root / "README.md"
    readme_text = ""
    if readme.exists():
        readme_text = readme.read_text(encoding="utf-8", errors="replace")[:12000]

    key_files = [
        rel
        for rel in (
            "README.md",
            "app.py",
            "obliteratus/cli.py",
            "obliteratus/abliterate.py",
            "obliteratus/informed_pipeline.py",
            "docs/RESEARCH_SURVEY.md",
            "requirements.txt",
            "requirements-apple.txt",
        )
        if (root / rel).exists()
    ]
    card.update(
        {
            "status": "observed",
            "truth_label": "OBSERVED",
            "version": str(project.get("version") or ""),
            "license": str(project.get("license", {}).get("text") if isinstance(project.get("license"), dict) else project.get("license") or ""),
            "entrypoint": "obliteratus = obliteratus.cli:main"
            if "obliteratus/cli.py" in key_files
            else "",
            "key_files": key_files,
        }
    )
    desc = str(project.get("description") or "").strip()
    if readme_text:
        low = readme_text.lower()
        if "abliteration" in low and "refusal" in low:
            card["purpose"] = (
                "Local open-source abliteration/mechanistic-interpretability toolkit: "
                "maps refusal directions in transformer models and applies removal/steering "
                "methods through CLI, Gradio UI, and Python APIs."
            )
        else:
            card["purpose"] = desc or "Local Python project; README observed but not classified."
    else:
        card["purpose"] = desc or "Local Python project without README observed."
    return card


def mimo_swimmer_learning_packet(*, obliteratus_path: str | Path | None = None) -> dict[str, Any]:
    """One grounded packet Alice can inject into self-knowledge."""
    return {
        "truth_label": "OBSERVED",
        "doctrine": "MiMo is a cortex surface; Alice-native swimmers own the work and receipts.",
        "mimo_features": mimo_feature_swimmer_map(),
        "mimo_claim_matrix": mimo_capability_claim_matrix(),
        "obliteratus": obliteratus_project_card(obliteratus_path),
    }


def render_mimo_swimmer_learning_block(*, obliteratus_path: str | Path | None = None) -> str:
    packet = mimo_swimmer_learning_packet(obliteratus_path=obliteratus_path)
    lines = [
        "MIMO FEATURE SWIMMERS (MiMo surface -> Alice-native organ; grounded, not a private agent roster):"
    ]
    for row in packet["mimo_features"]:
        organs = ", ".join(row["organ_files"])
        lines.append(f"- {row['mimo_surface']}: {row['alice_swimmer']} [{organs}]")
    lines.append("MIMO WEBSITE CLAIMS -> ALICE BODY TRUTH:")
    for row in packet["mimo_claim_matrix"]:
        swimmers = ", ".join(row["alice_swimmers"])
        lines.append(f"- {row['mimo_claim']}: {row['truth_label']} — {row['alice_answer']} Swimmers: {swimmers}. Gap: {row['gap']}")
    obl = packet["obliteratus"]
    lines.append("OBLITERATUS MEMORY:")
    lines.append(f"- status={obl['status']} path={obl['path']}")
    lines.append(f"- {obl['purpose']}")
    if obl.get("key_files"):
        lines.append("- key files: " + ", ".join(obl["key_files"][:6]))
    return "\n".join(lines)


__all__ = [
    "MimoFeatureSwimmer",
    "MimoCapabilityClaim",
    "mimo_capability_claim_matrix",
    "mimo_feature_swimmer_map",
    "mimo_swimmer_learning_packet",
    "obliteratus_project_card",
    "render_mimo_swimmer_learning_block",
]
