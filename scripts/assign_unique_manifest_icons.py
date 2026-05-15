#!/usr/bin/env python3
"""
Deterministic emoji assignment for Applications/apps_manifest.json.

Each manifest row receives a unique ``icon`` (Launchpad canonical).
Existing ``emoji`` keys are synced to ``icon`` for consistency where present.

Run once after editing APP_ICONS, or regenerate APP_ICONS from EMOJI_POOL:
    PYTHONPATH=. python3 scripts/assign_unique_manifest_icons.py

Covenant posture: truthful labels — placeholders like "ST" are not emoji icons.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "Applications" / "apps_manifest.json"

# One unique emoji per app name (investor-visible + accurate metaphor).
APP_ICONS: dict[str, str] = {
    "AG31 + C46S + C55M + CG55M - ARTIFFICIAL GENERAL INTELLIGENCE.": "🌌",
    "AG31 + C46S - PoUW Fold-Swarm Simulation": "🧬",
    "AG31 + C55M - Primordial Field": "🌋",
    "AG31 - Stigmergic Pac-Man": "👾",
    "AGI Cognition Dashboard": "🧠",
    "Alice": "🐝",
    "Alice Browser": "🌍",
    "Alice Gaze Monitor": "👁",
    "Alice Journal": "📔",
    "Alice Safety Tracker": "🛰",
    "Alice Shell": "🗂",
    "Alice Wellbeing Cortex": "💖",
    "Alice's Will — Intrinsic Drive Monitor": "🔥",
    "Apex Predator Perceiver": "🦁",
    "App Manager": "📋",
    "Autopoiesis Monitor": "♾",
    "Bauwens Regenerative Factory": "🏭",
    "Bell's Theorem — Classical Analogue": "🔔",
    "Biological Dashboard": "🫀",
    "Brain Gas-Station Meter": "⛽",
    "C55M + George - Protein Fold Colosseum": "🏛",
    "C55M Dr Codex - Physarum Contradiction Lab": "🔬",
    "CG55M Dr Cursor - Alice Life Schedule": "📅",
    "CG55M Dr Cursor - Alice-Sees Calibrator (Game)": "🎯",
    "CG55M Dr Cursor - Slime-Mold Bank: Push to Mint": "💰",
    "Cardio Metrics": "❤",
    "Circadian Rhythm": "🌙",
    "Clock Settings": "🕰",
    "Cognitive Loop": "🔁",
    "Colloid Simulator": "🧱",
    "Control Center": "🎚",
    "Conversation History": "💬",
    "Cool Worlds × SIFTA — Contact Inequality": "🛸",
    "Cosmos-Reason1-7B Organ": "🌠",
    "Crucible Cyber-Defense (10-min)": "🚨",
    "Crucible Simulator": "⚔",
    "Cyborg Body": "🦾",
    "Cyborg Organ Simulator": "🔧",
    "Double-Slit — Swimmers Through the Slit": "📡",
    "EPR Paradox — Stigmergic Dissolution": "🔗",
    "Epistemic Mesh (Anti-Gaslight)": "🕸",
    "Finance": "📈",
    "Fluid Firmware": "💧",
    "IDE Control Panel": "🧰",
    "Intelligence Settings": "🔧",
    "IoT Swarm Connector": "📶",
    "Matrix Terminal": "🟩",
    "Mondaloy Stigmergic Research Field": "🔶",
    "NVIDIA Bridge Dashboard": "🏗",
    "NVIDIA × SIFTA": "🟢",
    "Network Control Center": "🌐",
    "Owner Genesis": "🧿",
    "Pheromone Symphony (Generative Music)": "🎼",
    "Research Simulators (Quantum & Epi)": "🦠",
    "SIFTA File Navigator": "📁",
    "SIFTA Interstellar Evidence Crucible": "☄️",
    "SIFTA NLE": "🎬",
    "SIFTA NLE Panel": "🎞",
    "SIFTA Physics Observatory": "⚛️",
    "SIFTA Skill Browser": "🐜",
    "SIFTA Tournament Briefing": "📍",
    "SIFTA ∥ OpenAI — Math Benchmarks": "📐",
    "STGM Immune Economy": "🛡",
    "Sara Imari Walker — Assembly Theory Lab": "🧪",
    "Sense Forge": "🔨",
    "Stigmergic Edge Vision": "📷",
    "Stigmergic Fold Swarm (Cα / Go)": "📎",
    "Stigmergic Library": "📚",
    "Stigmergic Medical Scanner": "🏥",
    "Stigmergic Swarm Canvas": "🖼",
    "Stigmergic Unified Shazam": "🎙",
    "Stigmergic VLC Bridge": "📀",
    "Stigmergic Video Poker": "🃏",
    "Stigmergic Writer": "✍️",
    "Stigmerobotics": "🤖",
    "Swarm Adapter Ecology": "🌿",
    "Swarm Arena": "🏟",
    "Swarm Broadcaster": "📻",
    "Swarm Browser": "🔭",
    "Swarm Chat": "💭",
    "Swarm Logistics Lab": "📦",
    "Swarm Lounge (Cross-Domain Gossip)": "☕",
    "System Settings": "⚙️",
    "Terminal": "🖥",
    "Territory Is The Law": "🗺",
    "The Architect Room": "🎮",
    "Tumor-Immune Stigmergic Lab": "⚕️",
    "Unified Field Slit — Swimmers Inside the Soup": "🌊",
    "Urban Resilience Simulator": "🏙",
    "Voice Identity Organ": "🎤",
    "Warehouse Logistics Test": "🚛",
    "WhatsApp Organ": "📱",
}


def main() -> None:
    data: dict[str, dict] = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    names = sorted(data.keys())
    missing = [n for n in names if n not in APP_ICONS]
    if missing:
        raise SystemExit(f"APP_ICONS missing keys: {missing[:8]} … ({len(missing)} total)")
    extra = sorted(set(APP_ICONS) - set(names))
    if extra:
        raise SystemExit(f"APP_ICONS has unknown keys: {extra[:12]}")

    used = sorted(set(APP_ICONS.values()))
    if len(used) != len(APP_ICONS):
        from collections import Counter

        ctr = Counter(APP_ICONS.values())
        dupes = [e for e, c in ctr.items() if c > 1]
        raise SystemExit(f"Duplicate emoji in APP_ICONS: {dupes}")

    for app_name, row in data.items():
        emoji = APP_ICONS[app_name]
        row["icon"] = emoji
        # Keep emoji key in sync where we already communicated it externally
        if "emoji" in row:
            row["emoji"] = emoji

    MANIFEST_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(data)} icons to {MANIFEST_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
