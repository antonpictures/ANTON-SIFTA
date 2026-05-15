#!/usr/bin/env python3
"""swarm_mammal_token_ecology.py — typed-token ecology for SIFTA.

MAMMAL's useful idea for SIFTA is not "another transformer." It is the
structured universal prompt: typed heterogeneous entities plus scalar
attributes in one aligned stream. `swarm_organ_tokenizer.py` already creates
that stream for SIFTA organs. This module makes the stream alive:

  typed tokens -> scalar projection -> swimmer pheromones -> token metabolism

No biomedical inference happens here. This is a deterministic SIFTA-native
field layer for research visualization and receipt-backed experiments.

Truth label: MAMMAL_TOKEN_ECOLOGY_V1.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from System.swarm_organ_tokenizer import (
    TT_GENERAL,
    TT_ORGAN,
    TT_SCALAR,
    TT_TIME,
    TT_TOKEN,
    OrganToken,
    tokenize_recent,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "MAMMAL_TOKEN_ECOLOGY_V1"
LEDGER_NAME = "mammal_token_ecology_receipts.jsonl"
TRUTH_BOUNDARY = (
    "SIFTA token ecology over typed organ tokens. Deterministic scalar "
    "projection and swimmer pheromones only. Not medical advice, not clinical "
    "prediction, not learned MAMMAL inference."
)


@dataclass(frozen=True)
class ScalarProjection:
    field: str
    value: float
    vector: tuple[float, ...]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["vector"] = list(self.vector)
        return d


class ScalarProjector:
    """Deterministic scalar -> fixed-dim projection.

    This mimics the role of a learned scalar projection layer without training:
    every numeric attribute produces a stable signed feature vector.
    """

    def __init__(self, dim: int = 8, scale: float = 1.0) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim
        self.scale = scale

    def project(self, field: str, value: float) -> ScalarProjection:
        x = float(value)
        seed = hashlib.sha256(field.encode("utf-8")).digest()
        out: list[float] = []
        log_mag = math.log1p(abs(x))
        sign = -1.0 if x < 0 else 1.0
        for i in range(self.dim):
            byte = seed[i % len(seed)]
            phase = (byte / 255.0) * math.tau
            basis = math.sin(log_mag * (i + 1) + phase)
            out.append(round(sign * self.scale * basis, 6))
        return ScalarProjection(field=field, value=x, vector=tuple(out))


@dataclass(frozen=True)
class TokenPheromone:
    swimmer: str
    pheromone_type: str
    token_index: int
    organ: str
    field: str
    strength: float
    note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TokenEcologySwimmer:
    pheromone_type = "BASE"

    def patrol(self, tokens: list[OrganToken], projections: dict[int, ScalarProjection]) -> list[TokenPheromone]:
        raise NotImplementedError

    def _deposit(self, i: int, tok: OrganToken, strength: float, note: str) -> TokenPheromone:
        return TokenPheromone(
            swimmer=type(self).__name__,
            pheromone_type=self.pheromone_type,
            token_index=i,
            organ=tok.organ,
            field=tok.field,
            strength=round(max(0.0, min(1.0, strength)), 4),
            note=note,
        )


class BindingSwimmer(TokenEcologySwimmer):
    pheromone_type = "BINDING_TRAIL"

    def patrol(self, tokens: list[OrganToken], projections: dict[int, ScalarProjection]) -> list[TokenPheromone]:
        out: list[TokenPheromone] = []
        for i, tok in enumerate(tokens):
            if tok.type != TT_SCALAR or i not in projections:
                continue
            left = tokens[max(0, i - 3): i]
            has_context = any(t.type in {TT_ORGAN, TT_TOKEN} for t in left)
            if has_context:
                magnitude = min(1.0, math.log1p(abs(float(tok.value))) / 8.0)
                out.append(self._deposit(i, tok, 0.45 + 0.55 * magnitude, "scalar bound to nearby typed context"))
        return out


class ContradictionSwimmer(TokenEcologySwimmer):
    pheromone_type = "CONTRADICTION_STORM"

    def patrol(self, tokens: list[OrganToken], projections: dict[int, ScalarProjection]) -> list[TokenPheromone]:
        markers = ("contradiction", "forbidden", "blocked", "conflict", "failed", "regression")
        return [
            self._deposit(i, tok, 0.9, "contradiction/conflict marker")
            for i, tok in enumerate(tokens)
            if str(tok.value).lower().find("no issue marker impossible") < 0
            and any(m in str(tok.value).lower() for m in markers)
        ]


class InflammationSwimmer(TokenEcologySwimmer):
    pheromone_type = "INFLAMMATION_SIGNAL"

    def patrol(self, tokens: list[OrganToken], projections: dict[int, ScalarProjection]) -> list[TokenPheromone]:
        markers = ("error", "wound", "sick", "degraded", "critical", "crash", "exception")
        return [
            self._deposit(i, tok, 0.82, "health/error marker")
            for i, tok in enumerate(tokens)
            if any(m in f"{tok.field} {tok.value}".lower() for m in markers)
        ]


class MutationSwimmer(TokenEcologySwimmer):
    pheromone_type = "MUTATION_ZONE"

    def patrol(self, tokens: list[OrganToken], projections: dict[int, ScalarProjection]) -> list[TokenPheromone]:
        markers = ("patch", "edit", "variant", "mutation", "changed", "surgery", "diff")
        return [
            self._deposit(i, tok, 0.68, "code/change marker")
            for i, tok in enumerate(tokens)
            if any(m in f"{tok.field} {tok.value}".lower() for m in markers)
        ]


class ToxicitySwimmer(TokenEcologySwimmer):
    pheromone_type = "TOXICITY_CLUSTER"

    def patrol(self, tokens: list[OrganToken], projections: dict[int, ScalarProjection]) -> list[TokenPheromone]:
        markers = ("tox", "clintox", "poison", "unsafe", "harm", "contraind")
        return [
            self._deposit(i, tok, 0.86, "toxicity/safety marker")
            for i, tok in enumerate(tokens)
            if any(m in f"{tok.field} {tok.value}".lower() for m in markers)
        ]


class MemorySwimmer(TokenEcologySwimmer):
    pheromone_type = "MEMORY_WELL"

    def patrol(self, tokens: list[OrganToken], projections: dict[int, ScalarProjection]) -> list[TokenPheromone]:
        counts: dict[str, int] = {}
        for tok in tokens:
            key = str(tok.value).lower()[:80]
            counts[key] = counts.get(key, 0) + 1
        out: list[TokenPheromone] = []
        for i, tok in enumerate(tokens):
            key = str(tok.value).lower()[:80]
            repeated = counts.get(key, 0)
            if repeated >= 3 or tok.organ in {"JOURNAL", "WORK", "STGM"}:
                out.append(self._deposit(i, tok, min(1.0, 0.35 + repeated / 10.0), "repeated or memory-ledger token"))
        return out


class DreamReplaySwimmer(TokenEcologySwimmer):
    pheromone_type = "REPLAY_REINFORCED"

    def patrol(self, tokens: list[OrganToken], projections: dict[int, ScalarProjection]) -> list[TokenPheromone]:
        markers = ("dream", "replay", "sleep", "consolidat", "compress")
        return [
            self._deposit(i, tok, 0.76, "dream/replay consolidation marker")
            for i, tok in enumerate(tokens)
            if any(m in f"{tok.field} {tok.value}".lower() for m in markers)
        ]


def default_token_swimmers() -> list[TokenEcologySwimmer]:
    return [
        BindingSwimmer(),
        ContradictionSwimmer(),
        InflammationSwimmer(),
        MutationSwimmer(),
        ToxicitySwimmer(),
        MemorySwimmer(),
        DreamReplaySwimmer(),
    ]


def token_metabolism(tokens: list[OrganToken], pheromones: list[TokenPheromone], *, base_decay: float = 0.08) -> dict[str, Any]:
    """Compute stabilized vs evaporating token energy.

    Tokens decay by default. Pheromone reinforcement reduces evaporation.
    """
    reinforcement: dict[int, float] = {}
    for p in pheromones:
        reinforcement[p.token_index] = reinforcement.get(p.token_index, 0.0) + p.strength
    energies: list[float] = []
    for i, tok in enumerate(tokens):
        base = {
            TT_ORGAN: 0.55,
            TT_TIME: 0.35,
            TT_TOKEN: 0.50,
            TT_SCALAR: 0.62,
            TT_GENERAL: 0.42,
        }.get(tok.type, 0.4)
        reinforced = min(1.0, reinforcement.get(i, 0.0))
        energy = max(0.0, min(1.0, base * (1.0 - base_decay) + reinforced * 0.45))
        energies.append(round(energy, 4))
    stabilized = sum(1 for e in energies if e >= 0.65)
    evaporating = sum(1 for e in energies if e < 0.35)
    return {
        "n_tokens": len(tokens),
        "stabilized_tokens": stabilized,
        "evaporating_tokens": evaporating,
        "mean_energy": round(sum(energies) / max(1, len(energies)), 4),
        "preview_energy": energies[:24],
    }


def run_token_ecology(
    tokens: Iterable[OrganToken],
    *,
    projector: ScalarProjector | None = None,
    swimmers: list[TokenEcologySwimmer] | None = None,
) -> dict[str, Any]:
    toks = list(tokens)
    projector = projector or ScalarProjector()
    swimmers = swimmers or default_token_swimmers()
    projections: dict[int, ScalarProjection] = {
        i: projector.project(tok.field, float(tok.value))
        for i, tok in enumerate(toks)
        if tok.type == TT_SCALAR
    }
    pheromones: list[TokenPheromone] = []
    for swimmer in swimmers:
        pheromones.extend(swimmer.patrol(toks, projections))
    by_type: dict[str, int] = {}
    for p in pheromones:
        by_type[p.pheromone_type] = by_type.get(p.pheromone_type, 0) + 1
    metabolism = token_metabolism(toks, pheromones)
    return {
        "truth_label": TRUTH_LABEL,
        "truth_class": "OPERATIONAL",
        "truth_boundary": TRUTH_BOUNDARY,
        "n_tokens": len(toks),
        "n_scalar_projections": len(projections),
        "n_pheromones": len(pheromones),
        "pheromones_by_type": dict(sorted(by_type.items())),
        "metabolism": metabolism,
        "projection_preview": [p.to_dict() for p in list(projections.values())[:8]],
        "pheromone_preview": [p.to_dict() for p in pheromones[:32]],
    }


def run_mammal_token_ecology(
    state_root: str | Path | None = None,
    *,
    last_n_per_ledger: int = 15,
    write: bool = True,
) -> dict[str, Any]:
    tokens = tokenize_recent(state_root=state_root, last_n_per_ledger=last_n_per_ledger)
    result = run_token_ecology(tokens)
    if write:
        row = write_token_ecology_receipt(result, state_root=state_root)
        result = {**result, "receipt_trace_id": row["trace_id"], "receipt_sha256": row["sha256"]}
    return result


def write_token_ecology_receipt(
    result: dict[str, Any],
    *,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    state = Path(state_root) if state_root is not None else _STATE
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "MAMMAL_TOKEN_ECOLOGY",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--last-n", type=int, default=12)
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()
    print(json.dumps(
        run_mammal_token_ecology(last_n_per_ledger=args.last_n, write=not args.no_write),
        indent=2,
        sort_keys=True,
    ))
