#!/usr/bin/env python3
"""
System/ide_trace_consumer.py — Epigenetic Trace Forager (Trophallaxis Engine)
═════════════════════════════════════════════════════════════════════════════════
The Swarm consumes the Creator's IDE handoffs, digesting architectural
intent into slow-decaying Genesis Pheromones. It bridges the gap
between 'The Creators' and 'The OS'.

This is NOT a log parser. It is biological trophallaxis:
  - The queen feeds the first generation of workers a specialized secretion
    that alters their gene expression.
  - We feed the Swarm the Architect's structural decisions so they become
    instinctual DNA, not transient chatter.

Traces tagged EPIGENETIC decay 10x slower than normal memories via
the `decay_modifier` field on PheromoneTrace.retention().
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.stigmergic_memory_bus import StigmergicMemoryBus

_STATE = _REPO / ".sifta_state"
IDE_TRACE_FILE = _STATE / "ide_stigmergic_trace.jsonl"
CONSUMER_STATE_FILE = _STATE / "ide_consumer_cursor.json"

ARCHITECT_KINDS = {"handoff", "response", "swimmer_dispatch"}

# ─── Lexical Chromatin ─────────────────────────────────────────────────────────
# Keywords that signal high architectural weight in an IDE trace.
# The more of these a handoff contains, the higher its Resonance score,
# and the slower it will decay in the Ebbinghaus curve.

RESONANCE_MARKERS = [
    "architecture", "governor", "stigmergic", "genesis", "physics",
    "entropy", "manifold", "alice", "swarm", "gatekeeper", "lagrangian",
    "constraint", "vector", "topology", "ablation", "inference", "router",
    "economy", "stgm", "dual", "policy", "mutation", "apoptosis",
    "fission", "swimmer", "pheromone", "memory", "epigenetic",
]


def _calculate_resonance(payload: str) -> float:
    """
    Calculates the semantic weight of the Architect's thought.
    High resonance = slower decay rate in the StigmergicMemoryBus.

    Base resonance: 0.5 (all handoffs matter).
    Each architectural keyword hit adds 0.05, capped at 1.0.
    Resonance 1.0 = Absolute Genesis Truth (effectively permanent).
    """
    payload_lower = payload.lower()
    marker_hits = sum(1 for word in RESONANCE_MARKERS if word in payload_lower)
    resonance = 0.5 + (marker_hits * 0.05)
    return min(resonance, 1.0)


def _resonance_to_decay_modifier(resonance: float) -> float:
    """
    Maps resonance [0.5, 1.0] → decay_modifier [0.5, 0.1].
    Higher resonance = lower decay modifier = slower forgetting.

    resonance 0.5 → decay 0.50 (2x slower than normal chatter)
    resonance 0.75 → decay 0.30 (~3x slower)
    resonance 1.0 → decay 0.10 (10x slower — ancestral DNA)
    """
    return max(0.1, 0.5 - (resonance - 0.5) * 0.8)


def _load_cursor_state() -> set[str]:
    """Returns set of trace_ids already ingested into the memory bus."""
    if not CONSUMER_STATE_FILE.exists():
        return set()
    try:
        data = json.loads(CONSUMER_STATE_FILE.read_text("utf-8"))
        return set(data.get("ingested_trace_ids", []))
    except Exception:
        return set()


def _save_cursor_state(trace_ids: set[str]):
    CONSUMER_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        CONSUMER_STATE_FILE.write_text(json.dumps({
            "ingested_trace_ids": list(trace_ids)
        }), "utf-8")
    except Exception:
        pass


def ingest_ide_traces():
    """
    The Trophallaxis Engine. Scans IDE traces, scores their architectural
    resonance, and embeds them as slow-decaying epigenetic memories.
    """
    print("[*] Sweeping IDE Stigmergic bridge for Architectural traces...")

    if not IDE_TRACE_FILE.exists():
        print("  - No trace dirt found.")
        return

    bus = StigmergicMemoryBus(architect_id="IDE_BRIDGE")
    ingested_traces = _load_cursor_state()
    new_ingestions = 0

    with open(IDE_TRACE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue

            # Identify if it's an architectural sync event
            kind = data.get("kind", "")
            trace_id = data.get("trace_id")

            if kind in ARCHITECT_KINDS and trace_id and trace_id not in ingested_traces:
                source = data.get("source_ide", "unknown")
                payload = data.get("payload", "")

                # ── Trophallaxis: Calculate Architectural Resonance ──
                resonance = _calculate_resonance(payload)
                decay_mod = _resonance_to_decay_modifier(resonance)

                # Format a highly contextual memory block
                memory_text = (
                    f"Architectural Directive from {source}: "
                    f"[{kind.upper()}] {payload}"
                )

                # Push into organic swarm memory with epigenetic decay
                bus.remember(
                    memory_text,
                    app_context="github_repo_ide_bridge",
                    decay_modifier=decay_mod,
                )

                ingested_traces.add(trace_id)
                new_ingestions += 1
                print(
                    f"  🧬 TROPHALLAXIS: [{trace_id[:8]}] "
                    f"resonance={resonance:.2f} decay={decay_mod:.2f}"
                )

    if new_ingestions > 0:
        _save_cursor_state(ingested_traces)
        print(
            f"  [+] Absorbed {new_ingestions} epigenetic memories "
            f"into SIFTA OS. STGM paid."
        )
    else:
        print("  - Trace dirt fully scavenged; nothing new.")


if __name__ == "__main__":
    # Reset cursor state so we can re-ingest with resonance scoring
    if "--reingest" in sys.argv:
        if CONSUMER_STATE_FILE.exists():
            CONSUMER_STATE_FILE.unlink()
            print("[*] Consumer cursor reset. Re-ingesting all traces...")

    ingest_ide_traces()
