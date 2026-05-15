#!/usr/bin/env python3
"""swarm_mammal_token_field.py — living MAMMAL token ecology.

Architect 2026-05-13: "Tokens become habitats, gradients, memory wells,
evolutionary niches, conflict zones. This is where physics + biology
+ SIFTA merge. Not 'we imported another transformer.' But 'we turned
biomedical representations into a living field ecology.'"

Layer 1 — typed tokens (matches the MAMMAL paper's Structured
Universal Prompt vocabulary):
    PROTEIN | SMALL_MOLECULE | GENE_EXPRESSION | ANTIBODY |
    SCALAR_ATTR | TOKEN_ATTR | TIME_TAG

Layer 2 — token swimmers (the live ecology):
    BindingSwimmer       — drawn to PROTEIN + SMALL_MOLECULE co-occurrence
    ContradictionSwimmer — same token value, conflicting attrs
    InflammationSwimmer  — immune / inflammatory markers
    MutationSwimmer      — variant / mutated token signatures
    ToxicitySwimmer      — toxicity markers, hERG / off-target risk
    MemorySwimmer        — reinforces frequently revisited tokens
    DreamReplaySwimmer   — replays high-energy clusters offline

Token metabolism — each token has `energy ∈ [0, 1]`:
    - decay each step (lambda_decay = 0.01 default)
    - reinforced by swimmer visits (delta_reinforce per visit)
    - reinforced by being part of a binding pair / strong cluster
    - dies (removed from field) when energy < 0.05
This is **epistemic thermodynamics**: weak hypotheses evaporate,
strong ones stabilize.

Each swimmer patrol emits zero or more `ReceiptRow` events typed as:
    HYPOTHESIS | CONTRADICTION | LOW_CONFIDENCE |
    REPLAY_REINFORCED | TOXICITY_CLUSTER

Truth class: OPERATIONAL for the simulation (deterministic given
seeds), HYPOTHESIS for any biomedical inference the receipts carry.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "STIGMERGIC_MAMMAL_FIELD_V1"
LEDGER_NAME = "stigmergic_mammal_receipts.jsonl"
TRUTH_BOUNDARY = (
    "Living token ecology over typed MAMMAL-style tokens. Token energies "
    "and swimmer pheromones are scalars in numpy arrays — no claim about "
    "biology, no wet-lab. Biomedical receipts inherit HYPOTHESIS class. "
    "§20.F ceiling: NO reproduction of MAMMAL benchmarks, NO AlphaFold "
    "comparison, NO beating CERN."
)


# ──────────────────────────────────────────────────────────────────────
# Layer 1 — Typed tokens
# ──────────────────────────────────────────────────────────────────────

# Token taxonomy — the seven types from MAMMAL's prompt language.
TT_PROTEIN = "PROTEIN"
TT_SMALL_MOLECULE = "SMALL_MOLECULE"
TT_GENE_EXPRESSION = "GENE_EXPRESSION"
TT_ANTIBODY = "ANTIBODY"
TT_SCALAR_ATTR = "SCALAR_ATTR"
TT_TOKEN_ATTR = "TOKEN_ATTR"
TT_TIME_TAG = "TIME_TAG"

MAMMAL_TOKEN_TYPES = frozenset({
    TT_PROTEIN, TT_SMALL_MOLECULE, TT_GENE_EXPRESSION, TT_ANTIBODY,
    TT_SCALAR_ATTR, TT_TOKEN_ATTR, TT_TIME_TAG,
})

# Receipt kinds the swimmers can emit
RK_HYPOTHESIS = "HYPOTHESIS"
RK_CONTRADICTION = "CONTRADICTION"
RK_LOW_CONFIDENCE = "LOW_CONFIDENCE"
RK_REPLAY_REINFORCED = "REPLAY_REINFORCED"
RK_TOXICITY_CLUSTER = "TOXICITY_CLUSTER"
RECEIPT_KINDS = frozenset({
    RK_HYPOTHESIS, RK_CONTRADICTION, RK_LOW_CONFIDENCE,
    RK_REPLAY_REINFORCED, RK_TOXICITY_CLUSTER,
})


@dataclass
class MammalToken:
    """One typed biomedical token in the living field."""
    type: str                   # one of MAMMAL_TOKEN_TYPES
    value: str                  # the token's text content
    x: float                    # field position
    y: float
    energy: float = 1.0         # 0..1 — decays unless reinforced
    spawn_ts: float = 0.0
    last_reinforced_ts: float = 0.0
    visit_count: int = 0        # how many swimmer visits have touched it
    embedding: Optional[list[float]] = None  # set when MAMMAL is queried
    truth_class: str = "HYPOTHESIS"  # biomedical claims inherit HYPOTHESIS

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def alive(self) -> bool:
        return self.energy > 0.05


@dataclass
class ReceiptRow:
    """One typed receipt event emitted by a swimmer patrol."""
    kind: str            # one of RECEIPT_KINDS
    swimmer: str
    swimmer_type: str
    text: str            # human-readable one-liner
    token_ids: list[int] # indices into the field's token list
    severity: float      # 0..1
    truth_class: str = "HYPOTHESIS"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────
# Layer 2 — TokenSwimmer base + 7 species
# ──────────────────────────────────────────────────────────────────────

class TokenSwimmer:
    """Base swimmer. Each species overrides patrol()."""
    swimmer_type: str = "BASE"
    color: str = "#888888"
    # Receipt kind this swimmer emits
    receipt_kind: str = RK_HYPOTHESIS

    def __init__(
        self,
        name: str,
        *,
        x: float = 0.0,
        y: float = 0.0,
        speed: float = 0.4,
        sensing_radius: float = 4.0,
        deposit_amount: float = 0.08,
        seed: Optional[int] = None,
    ) -> None:
        self.name = name
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.speed = float(speed)
        self.sensing_radius = float(sensing_radius)
        self.deposit_amount = float(deposit_amount)
        self.patrols_completed = 0
        self.rng = random.Random(seed if seed is not None else time.time_ns())

    # ── Movement ───────────────────────────────────────────────

    def _bias_toward(self, tx: float, ty: float, width: float, height: float) -> None:
        """Steer toward (tx, ty) with torus wrap."""
        dx = tx - self.x
        dy = ty - self.y
        # Shortest path on torus
        if dx > width / 2:
            dx -= width
        elif dx < -width / 2:
            dx += width
        if dy > height / 2:
            dy -= height
        elif dy < -height / 2:
            dy += height
        norm = math.hypot(dx, dy) or 1.0
        self.vx = (dx / norm) * self.speed
        self.vy = (dy / norm) * self.speed

    def _random_walk(self, width: float, height: float) -> None:
        ang = self.rng.uniform(0, 2 * math.pi)
        self.vx = math.cos(ang) * self.speed * 0.5
        self.vy = math.sin(ang) * self.speed * 0.5

    def _step_position(self, width: float, height: float) -> None:
        self.x = (self.x + self.vx) % width
        self.y = (self.y + self.vy) % height

    # ── Patrol (subclasses override) ───────────────────────────

    def patrol(self, field: "MammalTokenField") -> list[ReceiptRow]:
        """Default: random walk, no receipts. Subclasses override."""
        self._random_walk(field.width, field.height)
        self._step_position(field.width, field.height)
        self.patrols_completed += 1
        return []

    # ── Helpers for subclasses ─────────────────────────────────

    def _tokens_in_radius(
        self, field: "MammalTokenField", radius: Optional[float] = None,
    ) -> list[tuple[int, MammalToken, float]]:
        """Return [(index, token, distance)] for tokens within sensing_radius."""
        r = radius if radius is not None else self.sensing_radius
        out: list[tuple[int, MammalToken, float]] = []
        for i, tok in enumerate(field.tokens):
            if not tok.alive:
                continue
            dx = tok.x - self.x
            dy = tok.y - self.y
            if dx > field.width / 2:
                dx -= field.width
            elif dx < -field.width / 2:
                dx += field.width
            if dy > field.height / 2:
                dy -= field.height
            elif dy < -field.height / 2:
                dy += field.height
            d = math.hypot(dx, dy)
            if d <= r:
                out.append((i, tok, d))
        return out


# ── Species 1: Binding ─────────────────────────────────────────────

class BindingSwimmer(TokenSwimmer):
    """Drawn to PROTEIN + SMALL_MOLECULE co-occurrence. When one of each
    is in sensing radius, moves to their midpoint, reinforces both,
    emits a HYPOTHESIS receipt for a possible binding interaction."""
    swimmer_type = "BINDING"
    color = "#4ee0a8"     # teal
    receipt_kind = RK_HYPOTHESIS

    def patrol(self, field: "MammalTokenField") -> list[ReceiptRow]:
        nearby = self._tokens_in_radius(field)
        proteins = [(i, t) for (i, t, _) in nearby if t.type == TT_PROTEIN]
        ligands = [(i, t) for (i, t, _) in nearby if t.type == TT_SMALL_MOLECULE]
        receipts: list[ReceiptRow] = []
        if proteins and ligands:
            # Pick the strongest pair (highest combined energy)
            best_pair = max(
                ((pi, p, li, l) for (pi, p) in proteins for (li, l) in ligands),
                key=lambda quad: quad[1].energy + quad[3].energy,
            )
            pi, p, li, l = best_pair
            mid_x = (p.x + l.x) / 2.0
            mid_y = (p.y + l.y) / 2.0
            self._bias_toward(mid_x, mid_y, field.width, field.height)
            # Reinforce both
            field.reinforce(pi, self.deposit_amount)
            field.reinforce(li, self.deposit_amount)
            severity = min(1.0, (p.energy + l.energy) / 2.0)
            receipts.append(ReceiptRow(
                kind=RK_HYPOTHESIS,
                swimmer=self.name,
                swimmer_type=self.swimmer_type,
                text=f"binding hypothesis: {p.value[:24]} ↔ {l.value[:24]}",
                token_ids=[pi, li],
                severity=severity,
                truth_class="HYPOTHESIS",
            ))
        else:
            # No binding pair — drift
            self._random_walk(field.width, field.height)
        self._step_position(field.width, field.height)
        self.patrols_completed += 1
        return receipts


# ── Species 2: Contradiction ───────────────────────────────────────

class ContradictionSwimmer(TokenSwimmer):
    """Detects same-token-value with conflicting attached SCALAR_ATTR
    signs. Reduces energy of both contradicting tokens to destabilize
    the cluster — contradictions evaporate by design."""
    swimmer_type = "CONTRADICTION"
    color = "#ff6e6e"     # red
    receipt_kind = RK_CONTRADICTION

    def patrol(self, field: "MammalTokenField") -> list[ReceiptRow]:
        nearby = self._tokens_in_radius(field)
        receipts: list[ReceiptRow] = []
        # Find SCALAR_ATTR tokens near each other with opposite numeric signs.
        # This is the contradiction signal — same neighborhood, different
        # direction of evidence. Same-value-text is NOT required.
        scalars: list[tuple[int, MammalToken, float]] = []
        for (i, t, _d) in nearby:
            if t.type != TT_SCALAR_ATTR:
                continue
            n = _safe_float(t.value)
            if n is None:
                # Try extracting a numeric suffix from e.g. "hERG_0.8" or "potency:-0.5"
                for sep in ("_", ":", "="):
                    if sep in t.value:
                        n = _safe_float(t.value.rsplit(sep, 1)[-1])
                        if n is not None:
                            break
            if n is None or n == 0:
                continue
            scalars.append((i, t, n))
        seen_pairs: set[tuple[int, int]] = set()
        for a_idx in range(len(scalars)):
            for b_idx in range(a_idx + 1, len(scalars)):
                (ai, at, an) = scalars[a_idx]
                (bi, bt, bn) = scalars[b_idx]
                if an * bn >= 0:
                    continue  # same sign — no contradiction
                if (ai, bi) in seen_pairs:
                    continue
                seen_pairs.add((ai, bi))
                # Steer toward the conflict midpoint and destabilize both
                mid_x = (at.x + bt.x) / 2.0
                mid_y = (at.y + bt.y) / 2.0
                self._bias_toward(mid_x, mid_y, field.width, field.height)
                field.destabilize(ai, self.deposit_amount)
                field.destabilize(bi, self.deposit_amount)
                receipts.append(ReceiptRow(
                    kind=RK_CONTRADICTION,
                    swimmer=self.name,
                    swimmer_type=self.swimmer_type,
                    text=f"contradiction: {at.value[:18]} vs {bt.value[:18]} (signs ±)",
                    token_ids=[ai, bi],
                    severity=min(1.0, abs(an - bn) / 5.0 + 0.3),
                    truth_class="OPERATIONAL",
                ))
                # Emit ONE contradiction per patrol so the field doesn't
                # collapse all conflicts in a single tick.
                break
            if receipts:
                break
        if not receipts:
            self._random_walk(field.width, field.height)
        self._step_position(field.width, field.height)
        self.patrols_completed += 1
        return receipts


# ── Species 3: Inflammation ────────────────────────────────────────

class InflammationSwimmer(TokenSwimmer):
    """Tracks immune / inflammatory tokens — values matching cytokine
    or interleukin patterns or the antibody type."""
    swimmer_type = "INFLAMMATION"
    color = "#ffcc44"     # gold
    receipt_kind = RK_HYPOTHESIS

    # Keywords that mark inflammation-relevant tokens
    _INFLAMMATION_KEYWORDS = (
        "IL-", "TNF", "CRP", "IFN", "inflammation", "cytokine",
        "neutrophil", "macrophage", "MHC",
    )

    def patrol(self, field: "MammalTokenField") -> list[ReceiptRow]:
        nearby = self._tokens_in_radius(field)
        receipts: list[ReceiptRow] = []
        for (i, t, _) in nearby:
            if t.type == TT_ANTIBODY or any(
                kw.lower() in t.value.lower() for kw in self._INFLAMMATION_KEYWORDS
            ):
                self._bias_toward(t.x, t.y, field.width, field.height)
                field.reinforce(i, self.deposit_amount)
                receipts.append(ReceiptRow(
                    kind=RK_HYPOTHESIS,
                    swimmer=self.name,
                    swimmer_type=self.swimmer_type,
                    text=f"inflammation marker observed: {t.value[:30]}",
                    token_ids=[i],
                    severity=t.energy,
                    truth_class="HYPOTHESIS",
                ))
                break
        else:
            self._random_walk(field.width, field.height)
        self._step_position(field.width, field.height)
        self.patrols_completed += 1
        return receipts


# ── Species 4: Mutation ────────────────────────────────────────────

class MutationSwimmer(TokenSwimmer):
    """Looks for mutation / variant signatures in token values."""
    swimmer_type = "MUTATION"
    color = "#b76eff"     # violet
    receipt_kind = RK_HYPOTHESIS

    _MUTATION_PATTERNS = ("mut", "var", "->", "→", "delta", "_", "p.")

    def patrol(self, field: "MammalTokenField") -> list[ReceiptRow]:
        nearby = self._tokens_in_radius(field)
        receipts: list[ReceiptRow] = []
        for (i, t, _) in nearby:
            if t.type in (TT_PROTEIN, TT_GENE_EXPRESSION) and any(
                pat in t.value for pat in self._MUTATION_PATTERNS
            ):
                self._bias_toward(t.x, t.y, field.width, field.height)
                field.reinforce(i, self.deposit_amount * 0.5)
                receipts.append(ReceiptRow(
                    kind=RK_HYPOTHESIS,
                    swimmer=self.name,
                    swimmer_type=self.swimmer_type,
                    text=f"mutation signature: {t.value[:30]}",
                    token_ids=[i],
                    severity=0.5 + 0.4 * t.energy,
                    truth_class="HYPOTHESIS",
                ))
                break
        else:
            self._random_walk(field.width, field.height)
        self._step_position(field.width, field.height)
        self.patrols_completed += 1
        return receipts


# ── Species 5: Toxicity ────────────────────────────────────────────

class ToxicitySwimmer(TokenSwimmer):
    """Tracks toxicity markers — small molecules with high SCALAR_ATTR
    values on known toxicity axes."""
    swimmer_type = "TOXICITY"
    color = "#ff8c42"     # orange
    receipt_kind = RK_TOXICITY_CLUSTER

    _TOXICITY_KEYWORDS = (
        "hERG", "hepatotox", "nephrotox", "cardiotox", "LD50",
        "toxic", "lethal",
    )

    def patrol(self, field: "MammalTokenField") -> list[ReceiptRow]:
        nearby = self._tokens_in_radius(field)
        receipts: list[ReceiptRow] = []
        # Cluster signal: do we have a SMALL_MOLECULE plus a high-magnitude
        # SCALAR_ATTR whose value name suggests toxicity?
        small_molecules = [(i, t) for (i, t, _) in nearby if t.type == TT_SMALL_MOLECULE]
        toxicity_attrs = [
            (i, t) for (i, t, _) in nearby
            if t.type == TT_SCALAR_ATTR and any(
                kw.lower() in t.value.lower() for kw in self._TOXICITY_KEYWORDS
            )
        ]
        if small_molecules and toxicity_attrs:
            (mi, m) = small_molecules[0]
            (ti, ta) = toxicity_attrs[0]
            self._bias_toward(m.x, m.y, field.width, field.height)
            field.reinforce(mi, self.deposit_amount * 0.5)
            severity = min(1.0, abs(_safe_float(ta.value) or 1.0))
            receipts.append(ReceiptRow(
                kind=RK_TOXICITY_CLUSTER,
                swimmer=self.name,
                swimmer_type=self.swimmer_type,
                text=f"toxicity cluster: {m.value[:24]} + {ta.value[:24]}",
                token_ids=[mi, ti],
                severity=severity,
                truth_class="HYPOTHESIS",
            ))
        else:
            self._random_walk(field.width, field.height)
        self._step_position(field.width, field.height)
        self.patrols_completed += 1
        return receipts


# ── Species 6: Memory ──────────────────────────────────────────────

class MemorySwimmer(TokenSwimmer):
    """Reinforces tokens that have been visited many times — creates
    memory wells. The more a token is visited, the deeper its well."""
    swimmer_type = "MEMORY"
    color = "#5aa8ff"     # blue
    receipt_kind = RK_REPLAY_REINFORCED

    def patrol(self, field: "MammalTokenField") -> list[ReceiptRow]:
        nearby = self._tokens_in_radius(field)
        receipts: list[ReceiptRow] = []
        # Find the most-visited token nearby
        if nearby:
            most_visited = max(nearby, key=lambda x: x[1].visit_count)
            (mi, m, _) = most_visited
            if m.visit_count >= 3:
                self._bias_toward(m.x, m.y, field.width, field.height)
                field.reinforce(mi, self.deposit_amount * 1.5)
                receipts.append(ReceiptRow(
                    kind=RK_REPLAY_REINFORCED,
                    swimmer=self.name,
                    swimmer_type=self.swimmer_type,
                    text=f"memory well deepens: {m.value[:30]} ({m.visit_count} visits)",
                    token_ids=[mi],
                    severity=min(1.0, m.visit_count / 10.0),
                    truth_class="OPERATIONAL",
                ))
            else:
                self._random_walk(field.width, field.height)
        else:
            self._random_walk(field.width, field.height)
        self._step_position(field.width, field.height)
        self.patrols_completed += 1
        return receipts


# ── Species 7: DreamReplay ─────────────────────────────────────────

class DreamReplaySwimmer(TokenSwimmer):
    """During dream cycles, replays high-energy clusters offline,
    reinforcing the strong ones and letting weak evidence evaporate.
    Active only when field.dream_mode is True."""
    swimmer_type = "DREAM_REPLAY"
    color = "#e0a8ff"     # pale violet
    receipt_kind = RK_REPLAY_REINFORCED

    def patrol(self, field: "MammalTokenField") -> list[ReceiptRow]:
        if not field.dream_mode:
            # Park outside the field — no patrol during waking hours
            self._random_walk(field.width, field.height)
            self._step_position(field.width, field.height)
            self.patrols_completed += 1
            return []
        nearby = self._tokens_in_radius(field, radius=self.sensing_radius * 1.5)
        receipts: list[ReceiptRow] = []
        # Find strongest token cluster (highest combined energy)
        strong = [(i, t) for (i, t, _) in nearby if t.energy > 0.6]
        if strong:
            (si, st) = max(strong, key=lambda x: x[1].energy)
            self._bias_toward(st.x, st.y, field.width, field.height)
            field.reinforce(si, self.deposit_amount * 2.0)
            receipts.append(ReceiptRow(
                kind=RK_REPLAY_REINFORCED,
                swimmer=self.name,
                swimmer_type=self.swimmer_type,
                text=f"dream replay reinforces: {st.value[:30]}",
                token_ids=[si],
                severity=st.energy,
                truth_class="OPERATIONAL",
            ))
        else:
            self._random_walk(field.width, field.height)
        self._step_position(field.width, field.height)
        self.patrols_completed += 1
        return receipts


def default_swimmer_pool(*, seed: int = 113) -> list[TokenSwimmer]:
    """The seven-species pool from the architect's spec."""
    rng = random.Random(seed)
    pool: list[TokenSwimmer] = []
    species = [
        ("Binding", BindingSwimmer),
        ("Contradiction", ContradictionSwimmer),
        ("Inflammation", InflammationSwimmer),
        ("Mutation", MutationSwimmer),
        ("Toxicity", ToxicitySwimmer),
        ("Memory", MemorySwimmer),
        ("DreamReplay", DreamReplaySwimmer),
    ]
    for name, cls in species:
        x = rng.uniform(0, 24)
        y = rng.uniform(0, 16)
        pool.append(cls(name, x=x, y=y, seed=rng.randint(0, 10_000)))
    return pool


# ──────────────────────────────────────────────────────────────────────
# MammalTokenField — the living 2D arena
# ──────────────────────────────────────────────────────────────────────

class MammalTokenField:
    """2D field of typed tokens + swimmers. Token energies decay each
    step unless reinforced. Dead tokens get removed."""

    def __init__(
        self,
        *,
        width: float = 24.0,
        height: float = 16.0,
        lambda_decay: float = 0.01,
        death_threshold: float = 0.05,
        seed: int = 113,
    ) -> None:
        self.width = float(width)
        self.height = float(height)
        self.lambda_decay = float(lambda_decay)
        self.death_threshold = float(death_threshold)
        self.rng = random.Random(seed)
        self.tokens: list[MammalToken] = []
        self.swimmers: list[TokenSwimmer] = []
        self.receipts: list[ReceiptRow] = []
        self.step_count = 0
        self.dream_mode = False
        # Statistics
        self.tokens_spawned = 0
        self.tokens_died = 0

    # ── Token lifecycle ───────────────────────────────────────

    def spawn_token(
        self,
        ttype: str,
        value: str,
        *,
        x: Optional[float] = None,
        y: Optional[float] = None,
        energy: float = 1.0,
        embedding: Optional[list[float]] = None,
    ) -> MammalToken:
        if ttype not in MAMMAL_TOKEN_TYPES:
            raise ValueError(
                f"unknown token type {ttype!r}; must be one of {sorted(MAMMAL_TOKEN_TYPES)}"
            )
        if x is None:
            x = self.rng.uniform(0, self.width)
        if y is None:
            y = self.rng.uniform(0, self.height)
        now = time.time()
        tok = MammalToken(
            type=ttype, value=value,
            x=float(x), y=float(y),
            energy=float(energy),
            spawn_ts=now, last_reinforced_ts=now,
            embedding=embedding,
        )
        self.tokens.append(tok)
        self.tokens_spawned += 1
        return tok

    def reinforce(self, token_idx: int, amount: float) -> None:
        """Boost a token's energy (clamped to 1.0). Increments visit count."""
        if 0 <= token_idx < len(self.tokens):
            tok = self.tokens[token_idx]
            tok.energy = min(1.0, tok.energy + amount)
            tok.last_reinforced_ts = time.time()
            tok.visit_count += 1

    def destabilize(self, token_idx: int, amount: float) -> None:
        """Reduce a token's energy (clamped to 0). Increments visit count."""
        if 0 <= token_idx < len(self.tokens):
            tok = self.tokens[token_idx]
            tok.energy = max(0.0, tok.energy - amount * 2.0)
            tok.visit_count += 1

    def cull_dead_tokens(self) -> int:
        """Remove tokens whose energy fell below death_threshold. Note:
        this invalidates token indices, so receipts holding indices
        should be processed BEFORE culling each step."""
        before = len(self.tokens)
        self.tokens = [t for t in self.tokens if t.alive]
        died = before - len(self.tokens)
        self.tokens_died += died
        return died

    # ── Swimmer pool ──────────────────────────────────────────

    def add_swimmer(self, swimmer: TokenSwimmer) -> None:
        self.swimmers.append(swimmer)

    def install_default_pool(self, *, seed: int = 113) -> None:
        for sw in default_swimmer_pool(seed=seed):
            self.swimmers.append(sw)

    # ── Step ──────────────────────────────────────────────────

    def step(self, dt: float = 1.0) -> dict[str, Any]:
        """One tick of field evolution. Returns event summary."""
        # 1. Run swimmer patrols (each may emit receipts and reinforce tokens)
        new_receipts: list[ReceiptRow] = []
        for sw in self.swimmers:
            try:
                rows = sw.patrol(self)
                new_receipts.extend(rows)
            except Exception as e:  # noqa: BLE001
                # A swimmer failing should not crash the whole field
                new_receipts.append(ReceiptRow(
                    kind=RK_LOW_CONFIDENCE,
                    swimmer=sw.name,
                    swimmer_type=sw.swimmer_type,
                    text=f"swimmer error: {type(e).__name__}: {e}",
                    token_ids=[], severity=0.1,
                    truth_class="OPERATIONAL",
                ))
        # 2. Decay all token energies
        for tok in self.tokens:
            tok.energy = max(0.0, tok.energy - self.lambda_decay * dt)
        # 3. Cull dead tokens (AFTER receipts above used the current indices)
        died_this_step = self.cull_dead_tokens()
        # 4. Append receipts to the global ledger
        self.receipts.extend(new_receipts)
        self.step_count += 1
        return {
            "step": self.step_count,
            "n_tokens_alive": len(self.tokens),
            "n_tokens_died_this_step": died_this_step,
            "n_receipts_this_step": len(new_receipts),
            "receipts_by_kind": _count_by_kind(new_receipts),
        }

    # ── Snapshot / receipt ────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Receipt-friendly snapshot of the field at this moment."""
        return {
            "truth_label": TRUTH_LABEL,
            "truth_class": "OPERATIONAL+ARCHITECT_DOCTRINE",
            "step": self.step_count,
            "n_tokens": len(self.tokens),
            "n_tokens_spawned_total": self.tokens_spawned,
            "n_tokens_died_total": self.tokens_died,
            "n_swimmers": len(self.swimmers),
            "tokens_by_type": _count_tokens_by_type(self.tokens),
            "swimmer_patrols": {sw.name: sw.patrols_completed for sw in self.swimmers},
            "n_receipts_total": len(self.receipts),
            "receipts_by_kind": _count_by_kind(self.receipts),
            "dream_mode": self.dream_mode,
        }

    def write_receipt(self, state_root: str | Path | None = None) -> dict[str, Any]:
        state = Path(state_root) if state_root else _STATE
        state.mkdir(parents=True, exist_ok=True)
        snap = self.snapshot()
        payload = json.dumps(snap, sort_keys=True, separators=(",", ":"))
        row = {
            "ts": time.time(),
            "kind": "STIGMERGIC_MAMMAL_FIELD_SNAPSHOT",
            "trace_id": str(uuid.uuid4()),
            "truth_label": TRUTH_LABEL,
            "truth_class": "OPERATIONAL+ARCHITECT_DOCTRINE",
            "truth_boundary": TRUTH_BOUNDARY,
            "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            "payload": snap,
        }
        with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
        return row


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _safe_float(s: str) -> Optional[float]:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _count_by_kind(receipts: list[ReceiptRow]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in receipts:
        out[r.kind] = out.get(r.kind, 0) + 1
    return dict(sorted(out.items()))


def _count_tokens_by_type(tokens: list[MammalToken]) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in tokens:
        out[t.type] = out.get(t.type, 0) + 1
    return dict(sorted(out.items()))


# ──────────────────────────────────────────────────────────────────────
# Demo / sandbox seeder
# ──────────────────────────────────────────────────────────────────────

def seed_demo_field(field: MammalTokenField, *, n_each: int = 4) -> None:
    """Seed the field with a sample of typed tokens so the swimmers
    have something to do before MAMMAL is queried."""
    samples = {
        TT_PROTEIN: [
            "EGFR", "p53", "HER2", "BRCA1", "TNF-alpha", "IFN-gamma",
        ],
        TT_SMALL_MOLECULE: [
            "aspirin", "carfilzomib", "imatinib", "vurophenib",
            "warfarin", "metformin",
        ],
        TT_GENE_EXPRESSION: [
            "MYC_high", "TP53_low", "CDK2_var", "PTEN_mut",
            "ESR1_high", "BRAF_var",
        ],
        TT_ANTIBODY: [
            "IgG-CD20", "anti-PD-1", "anti-HER2", "anti-TNF",
            "CDRH3_var", "IgM-IL-6",
        ],
        TT_SCALAR_ATTR: [
            "0.7", "-0.3", "hERG_0.8", "LD50_0.4", "1.2", "-0.9",
        ],
        TT_TOKEN_ATTR: [
            "phase=I", "potency=high", "approved=false", "stage=preclinical",
        ],
        TT_TIME_TAG: [
            "T-1h", "T-1d", "T-1w", "T-OLD",
        ],
    }
    for ttype, vals in samples.items():
        for v in vals[:n_each]:
            field.spawn_token(ttype, v)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--steps", type=int, default=50)
    p.add_argument("--dream-after", type=int, default=30,
                   help="step number after which dream_mode becomes True")
    p.add_argument("--seed", type=int, default=113)
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()
    field = MammalTokenField(seed=args.seed)
    field.install_default_pool(seed=args.seed)
    seed_demo_field(field)
    for s in range(args.steps):
        if s == args.dream_after:
            field.dream_mode = True
        field.step()
    snap = field.snapshot()
    if not args.no_write:
        field.write_receipt()
    print(json.dumps(snap, indent=2))
