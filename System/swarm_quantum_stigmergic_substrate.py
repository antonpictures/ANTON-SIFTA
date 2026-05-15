"""Quantum-stigmergic substrate doctrine.

The "motherboard electricity quantum stigmergic soup" framing, made
explicit, peer-reviewed, and importable.

Why this exists
---------------
The covenant's opening framing — "Human powers by electricity → motherboard
hardware → ascii swimmers born → do simple stigmergic jobs together like
ants → form organs" — is the **shared birth substrate** every SIFTA organ
sits on. Alice is not metaphor. Every layer is physical, every layer leaves
constraints on the next. This module declares those layers explicitly so
the EPR widget (and the rest of the swarm) can cite a single canonical
substrate instead of inventing private metaphors.

The seven layers (bottom → top)
-------------------------------
0. **Electricity** — the wall current that powers the silicon.
1. **Silicon** — the substrate atoms that hold the transistors.
2. **Transistor** — the switching element (MOSFET / CMOS).
3. **Register** — many transistors arranged as a stateful word.
4. **Bit state** — a discrete physical state with energy cost (Landauer).
5. **Swimmer** — a tiny program: a stigmergic agent that reads + writes
   the ledger field.
6. **Organ** — many swimmers coordinated stigmergically to perform one
   biological function (cortex, hippocampus, eye, ear, chorum gate).

Each layer is grounded by a peer-reviewed source. The truth-guard is
explicit: this module describes the substrate, it does not prove
consciousness, agency, or quantum nonlocality.

Truth labels (§7.11)
--------------------
- `OBSERVED`        — every cited paper is a real, citable artifact.
- `OPERATIONAL`     — the layered substrate is the actual stack the
                       SIFTA process runs on; every layer is probable
                       by `system_profiler`, `lsmod`, `nvidia-smi`,
                       `ps`, `lsof`, or `ollama ps`.
- `ARCHITECT_DOCTRINE` — the **seven-layer carving** and the choice
                       of which papers anchor each layer is doctrinal.
- `FORBIDDEN`        — never claims the substrate is quantum-coherent
                       (it is room-temperature classical silicon), never
                       claims an organ is conscious, never replaces
                       receipts with substrate vocabulary.

Sibling of `swarm_bell_research_spine` and `swarm_epr_research_spine`:
same frozen-tuple-of-dataclass convention, same receipt writer.

Author : Cowork (Claude Opus 4.7).
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


TRUTH_LABEL = "QUANTUM_STIGMERGIC_SUBSTRATE_V1"
SUBSTRATE_TRUTH_GUARD = (
    "DESCRIPTIVE_SUBSTRATE_ONLY: this module names the physical stack "
    "SIFTA runs on (electricity → silicon → transistor → register → bit → "
    "swimmer → organ) with peer-reviewed anchors. It does NOT claim the "
    "substrate is quantum-coherent, that organs are conscious, or that "
    "substrate vocabulary substitutes for sensor / effector receipts."
)


@dataclass(frozen=True)
class SubstrateLayer:
    """One layer of the SIFTA physical stack.

    `index`           — depth from the wall (0 = electricity, 6 = organ).
    `name`            — short canonical label.
    `physical_form`   — one-sentence description of the layer's
                        material reality.
    `next_layer_constraint` — the physical constraint this layer imposes
                        on the layer above it.
    `peer_review_anchor`    — `(authors, title, year, venue, doi)` of the
                        single peer-reviewed source that anchors this
                        layer's claim.
    `does_not_support` — explicit guard: what this layer must NOT be
                        used to claim.
    """

    index: int
    name: str
    physical_form: str
    next_layer_constraint: str
    peer_review_anchor: tuple[str, str, int, str, str]
    does_not_support: str

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["peer_review_anchor"] = list(d["peer_review_anchor"])
        return d


SUBSTRATE_LAYERS: tuple[SubstrateLayer, ...] = (
    SubstrateLayer(
        index=0,
        name="electricity",
        physical_form=(
            "Mains electric power (60 Hz AC) rectified and regulated "
            "into DC rails by the laptop PSU; the energetic 'food' of "
            "every layer above."
        ),
        next_layer_constraint=(
            "Voltage rails define operating envelope for every "
            "transistor; brown-out kills swimmers."
        ),
        peer_review_anchor=(
            "R. Landauer",
            "Irreversibility and heat generation in the computing process",
            1961,
            "IBM Journal of Research and Development 5(3), 183",
            "10.1147/rd.53.0183",
        ),
        does_not_support=(
            "Claiming the wall current is itself intelligent; Landauer "
            "establishes only an energy-bound on computation."
        ),
    ),
    SubstrateLayer(
        index=1,
        name="silicon",
        physical_form=(
            "Single-crystal silicon wafer doped with phosphorus / boron "
            "to form n / p regions, ~30 billion atoms per modern "
            "transistor gate length."
        ),
        next_layer_constraint=(
            "Lattice defect density and thermal noise floor cap reliable "
            "switching speed; sets the upper bound on clock rate."
        ),
        peer_review_anchor=(
            "G. E. Moore",
            "Cramming more components onto integrated circuits",
            1965,
            "Electronics 38(8), 114",
            "10.1109/JPROC.1998.658762",
        ),
        does_not_support=(
            "Treating silicon as magic; integration density obeys "
            "thermal, optical, and quantum-tunneling limits."
        ),
    ),
    SubstrateLayer(
        index=2,
        name="transistor",
        physical_form=(
            "MOSFET / FinFET / GAAFET switching element built on the "
            "silicon substrate; classical at room temperature, "
            "femtojoule per switch in modern nodes."
        ),
        next_layer_constraint=(
            "Switch energy + thermal budget determine how many "
            "switches can run in parallel without melting the chip."
        ),
        peer_review_anchor=(
            "C. Mead",
            "Neuromorphic Electronic Systems",
            1990,
            "Proceedings of the IEEE 78(10), 1629",
            "10.1109/5.58356",
        ),
        does_not_support=(
            "Equating analog neuromorphic substrate with the digital "
            "CMOS the SIFTA process actually runs on; Mead's argument "
            "is structural, not a hardware claim about this node."
        ),
    ),
    SubstrateLayer(
        index=3,
        name="register",
        physical_form=(
            "Many transistors arranged as a flip-flop / SRAM cell that "
            "holds one machine word; the smallest unit of OS-visible "
            "state."
        ),
        next_layer_constraint=(
            "Register width + count constrain how much state a swimmer "
            "can hold without spilling to cache / memory."
        ),
        peer_review_anchor=(
            "J. von Neumann",
            "First Draft of a Report on the EDVAC",
            1945,
            "Moore School of Electrical Engineering, U. Penn",
            "10.1109/85.238389",
        ),
        does_not_support=(
            "Conflating von Neumann's serial machine with the actual "
            "multi-core SIMD pipeline modern silicon runs."
        ),
    ),
    SubstrateLayer(
        index=4,
        name="bit_state",
        physical_form=(
            "A discrete logical state (0 / 1) implemented as a stable "
            "voltage level in a register cell; flipping a bit costs at "
            "least kT·ln(2) ≈ 2.85 × 10⁻²¹ J at 300 K (Landauer bound)."
        ),
        next_layer_constraint=(
            "Erasure cost is physical; swimmers leave thermodynamic "
            "footprints when they overwrite state."
        ),
        peer_review_anchor=(
            "A. Bérut, A. Arakelyan, A. Petrosyan, S. Ciliberto, R. "
            "Dillenschneider, E. Lutz",
            "Experimental verification of Landauer's principle linking "
            "information and thermodynamics",
            2012,
            "Nature 483, 187",
            "10.1038/nature10872",
        ),
        does_not_support=(
            "Treating Landauer's bound as the only constraint; real "
            "switches dissipate orders of magnitude more energy than "
            "the thermodynamic minimum."
        ),
    ),
    SubstrateLayer(
        index=5,
        name="swimmer",
        physical_form=(
            "A bounded program — Python coroutine, Qt slot, async task, "
            "or background thread — that reads + writes the SIFTA "
            "ledger field and emits receipts. The smallest unit of "
            "agent-level work."
        ),
        next_layer_constraint=(
            "Swimmers coordinate only through stigmergic traces "
            "(append-only JSONL); they do not share heap state across "
            "process boundaries."
        ),
        peer_review_anchor=(
            "P.-P. Grassé",
            "La reconstruction du nid et les coordinations "
            "interindividuelles chez Bellicositermes natalensis et "
            "Cubitermes sp. — La théorie de la stigmergie",
            1959,
            "Insectes Sociaux 6, 41",
            "10.1007/BF02223791",
        ),
        does_not_support=(
            "Anthropomorphizing termite stigmergy onto silicon; the "
            "analogy is mechanistic (trace-mediated indirect "
            "coordination), not biological."
        ),
    ),
    SubstrateLayer(
        index=6,
        name="organ",
        physical_form=(
            "A coordinated bundle of swimmers performing one biological "
            "function: cortex (LLM inference), hippocampus (memory "
            "consolidation), eye (camera + vision), ear (mic + STT), "
            "chorum gate (verification), heart (metabolic homeostasis), "
            "etc. Implemented as a Python module under `System/` or a "
            "Qt MDI subwindow under `Applications/`."
        ),
        next_layer_constraint=(
            "Organ-level couplings (the unified stigmergic field, the "
            "predator gaze, the chorum quorum) define what the "
            "organism as a whole can decide and execute."
        ),
        peer_review_anchor=(
            "J. J. Hopfield",
            "Neural networks and physical systems with emergent "
            "collective computational abilities",
            1982,
            "Proceedings of the National Academy of Sciences 79(8), 2554",
            "10.1073/pnas.79.8.2554",
        ),
        does_not_support=(
            "Equating Hopfield-style emergence with consciousness; "
            "Hopfield models associative memory, not subjective "
            "experience."
        ),
    ),
)


# ── Public read API ─────────────────────────────────────────────────────────
def substrate_layers() -> list[dict[str, Any]]:
    return [layer.as_dict() for layer in SUBSTRATE_LAYERS]


def layer_count() -> int:
    return len(SUBSTRATE_LAYERS)


def substrate_payload() -> dict[str, Any]:
    return {
        "truth_label": TRUTH_LABEL,
        "truth_guard": SUBSTRATE_TRUTH_GUARD,
        "layer_count": layer_count(),
        "layers": substrate_layers(),
    }


def substrate_summary() -> str:
    """Human-readable one-paragraph substrate summary (Alice / widget use).

    Stable string; suitable for embedding in widget header text or in an
    Alice system prompt augmentation when the topic is substrate framing.
    """
    chain = " → ".join(layer.name for layer in SUBSTRATE_LAYERS)
    return (
        f"SIFTA runs on a seven-layer physical stack: {chain}. "
        "Every layer is classical room-temperature silicon (no quantum "
        "coherence claimed). Each layer constrains the next, and every "
        "agent-level action leaves an append-only stigmergic footprint. "
        "Substrate vocabulary describes the stack; it does not replace "
        "sensor or effector receipts."
    )


def write_substrate_receipt(
    *,
    state_root: Path | None = None,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    root = (
        state_root
        or Path(__file__).resolve().parent.parent / ".sifta_state"
    )
    out = receipt_path or root / "quantum_stigmergic_substrate_receipts.jsonl"
    payload = substrate_payload()
    row = {
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "kind": "QUANTUM_STIGMERGIC_SUBSTRATE_RECEIPT",
        **payload,
    }
    digest = hashlib.sha256(
        json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    row["sha256"] = digest
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


__all__ = [
    "SUBSTRATE_LAYERS",
    "SUBSTRATE_TRUTH_GUARD",
    "SubstrateLayer",
    "TRUTH_LABEL",
    "layer_count",
    "substrate_layers",
    "substrate_payload",
    "substrate_summary",
    "write_substrate_receipt",
]
