#!/usr/bin/env python3
"""swarm_visual_token_swimmers.py — six visual swimmer species (P2).

Architect 2026-05-14 (Vision Optimization Tournament §6):
    Six swimmer species patrol the visual token stream, each with a
    focused detector and a typed pheromone.

      MotionSwimmer        → SURPRISE_TRAIL
      FaceMassSwimmer      → OWNER_PRESENCE_TRAIL
      FoveaSwimmer         → MICRO_BURST_REQUEST
      OCRGuardSwimmer      → OCR_PRIVACY_GATE
      RedundancyBowelSwimmer → VISUAL_RESIDUE_ELIMINATED
      CrossOrganBinder     → CROSS_ORGAN_BINDING

Each pheromone deposit lands in `.sifta_state/visual_token_pheromones.jsonl`
with a sha256 signature. The receipt is the persistent memory — raw
frames are NOT memory (§5 of the tournament doc).

Truth label: VISUAL_TOKEN_SWIMMERS_V1.
Truth class: OPERATIONAL — deterministic given the input token stream.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_visual_microburst import (
    BurstScheduler,
    MicroBurstPolicy,
    VisualBurstRequest,
    VisualToken,
)

TRUTH_LABEL = "VISUAL_TOKEN_SWIMMERS_V1"
LEDGER_NAME = "visual_token_pheromones.jsonl"
TRUTH_BOUNDARY = (
    "Six visual swimmer species patrolling the typed-token stream "
    "(MotionSwimmer, FaceMassSwimmer, FoveaSwimmer, OCRGuardSwimmer, "
    "RedundancyBowelSwimmer, CrossOrganBinder). Each emits a typed "
    "pheromone deposit. Engineering analogue only (§20.F ceiling). "
    "OCR is opt-in only — surprise alone never silently OCRs. Face "
    "mass increases for recurring entities; raw face frames are NOT "
    "stored."
)

# ── Pheromone-kind constants ─────────────────────────────────────
PK_SURPRISE_TRAIL = "SURPRISE_TRAIL"
PK_OWNER_PRESENCE = "OWNER_PRESENCE_TRAIL"
PK_MICRO_BURST_REQUEST = "MICRO_BURST_REQUEST"
PK_OCR_PRIVACY_GATE = "OCR_PRIVACY_GATE"
PK_VISUAL_RESIDUE_ELIMINATED = "VISUAL_RESIDUE_ELIMINATED"
PK_CROSS_ORGAN_BINDING = "CROSS_ORGAN_BINDING"

PHEROMONE_KINDS = frozenset({
    PK_SURPRISE_TRAIL, PK_OWNER_PRESENCE, PK_MICRO_BURST_REQUEST,
    PK_OCR_PRIVACY_GATE, PK_VISUAL_RESIDUE_ELIMINATED, PK_CROSS_ORGAN_BINDING,
})


# ──────────────────────────────────────────────────────────────────────
# Data
# ──────────────────────────────────────────────────────────────────────

@dataclass
class Pheromone:
    """One pheromone deposit emitted by a swimmer."""
    kind: str
    swimmer: str
    entity: str
    severity: float     # 0..1
    note: str
    truth_label: str = TRUTH_LABEL
    truth_class: str = "OPERATIONAL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────
# Base swimmer
# ──────────────────────────────────────────────────────────────────────

class VisualSwimmer:
    """Base class. Subclasses override `inspect(token, context)` and
    return a list of Pheromone deposits."""
    species: str = "BASE"
    emits_kind: str = ""

    def __init__(self, name: Optional[str] = None) -> None:
        self.name = name or type(self).__name__
        self.patrols_completed = 0
        self.deposits = 0

    def inspect(
        self, token: VisualToken,
        context: Optional[dict[str, Any]] = None,
    ) -> list[Pheromone]:
        """Override."""
        return []

    def patrol(
        self, tokens: Iterable[VisualToken],
        context: Optional[dict[str, Any]] = None,
    ) -> list[Pheromone]:
        out: list[Pheromone] = []
        for t in tokens:
            try:
                rows = self.inspect(t, context=context)
            except Exception as e:  # noqa: BLE001
                rows = [Pheromone(
                    kind=PK_OCR_PRIVACY_GATE,  # generic safety pheromone
                    swimmer=self.name,
                    entity="error",
                    severity=0.1,
                    note=f"{type(e).__name__}: {e}",
                )]
            for r in rows:
                out.append(r)
                self.deposits += 1
        self.patrols_completed += 1
        return out


# ──────────────────────────────────────────────────────────────────────
# 1. MotionSwimmer — follows delta spikes + temporal clusters
# ──────────────────────────────────────────────────────────────────────

class MotionSwimmer(VisualSwimmer):
    species = "MOTION"
    emits_kind = PK_SURPRISE_TRAIL

    def __init__(
        self, name: Optional[str] = None,
        *, surprise_floor: float = 0.55,
    ) -> None:
        super().__init__(name)
        self.surprise_floor = float(surprise_floor)

    def inspect(self, token: VisualToken, context=None) -> list[Pheromone]:
        delta = float(token.attrs.get("delta") or 0.0)
        if token.wake_reason in ("surprise", "high_delta") or delta >= self.surprise_floor:
            severity = min(1.0, max(token.mass, delta, 0.3))
            return [Pheromone(
                kind=PK_SURPRISE_TRAIL, swimmer=self.name,
                entity=token.entity, severity=severity,
                note=f"motion delta={delta:.2f} reason={token.wake_reason}",
            )]
        return []


# ──────────────────────────────────────────────────────────────────────
# 2. FaceMassSwimmer — recurrence → mass, NO raw frames stored
# ──────────────────────────────────────────────────────────────────────

class FaceMassSwimmer(VisualSwimmer):
    """Increases mass for recurring owner/face-like visual nodes
    WITHOUT storing raw face frames. The mass is a scalar; the receipt
    records the entity + visit count, never an image."""
    species = "FACE_MASS"
    emits_kind = PK_OWNER_PRESENCE

    def __init__(self, name: Optional[str] = None) -> None:
        super().__init__(name)
        # entity → visit count
        self._visit_counts: dict[str, int] = {}

    def inspect(self, token: VisualToken, context=None) -> list[Pheromone]:
        # Match face-like entities (heuristic; no facial recognition here)
        is_face = (
            token.entity.startswith(("owner_face:", "named_person:", "face:"))
            or token.attrs.get("kind") == "face"
        )
        if not is_face:
            return []
        n = self._visit_counts.get(token.entity, 0) + 1
        self._visit_counts[token.entity] = n
        severity = min(1.0, 0.3 + 0.1 * n)
        return [Pheromone(
            kind=PK_OWNER_PRESENCE, swimmer=self.name,
            entity=token.entity, severity=severity,
            note=f"recurring face entity, visit={n}, mass→{severity:.2f} "
                 f"(no raw frame stored)",
        )]


# ──────────────────────────────────────────────────────────────────────
# 3. FoveaSwimmer — requests micro-burst on high-mass regions
# ──────────────────────────────────────────────────────────────────────

class FoveaSwimmer(VisualSwimmer):
    """When a high-mass token appears, request a bounded micro-burst.
    Cooperates with BurstScheduler from swarm_visual_microburst so the
    cooldown gate prevents loops."""
    species = "FOVEA"
    emits_kind = PK_MICRO_BURST_REQUEST

    def __init__(
        self, name: Optional[str] = None,
        *,
        scheduler: Optional[BurstScheduler] = None,
    ) -> None:
        super().__init__(name)
        self.scheduler = scheduler or BurstScheduler()

    def inspect(self, token: VisualToken, context=None) -> list[Pheromone]:
        fire, reason = self.scheduler.should_burst(token)
        if not fire:
            return []
        req = self.scheduler.make_request(token, reason)
        self.scheduler.mark_fired(token.entity)
        return [Pheromone(
            kind=PK_MICRO_BURST_REQUEST, swimmer=self.name,
            entity=token.entity, severity=min(1.0, token.mass + 0.1),
            note=(f"fovea request: frames={req.frames} "
                  f"resolution={req.resolution} reason={reason} "
                  f"persist_raw={req.persist_raw} ocr={req.ocr_allowed}"),
        )]


# ──────────────────────────────────────────────────────────────────────
# 4. OCRGuardSwimmer — opt-in gate, never silent
# ──────────────────────────────────────────────────────────────────────

class OCRGuardSwimmer(VisualSwimmer):
    """Only triggers OCR when explicit opt-in is in the context, e.g.
    `context['ocr_opt_in'] == True` or task_need == 'ocr'. Surprise
    alone CANNOT silently OCR the desktop (§7 acceptance test)."""
    species = "OCR_GUARD"
    emits_kind = PK_OCR_PRIVACY_GATE

    def inspect(self, token: VisualToken, context=None) -> list[Pheromone]:
        ctx = context or {}
        opt_in = bool(ctx.get("ocr_opt_in"))
        task_need_ocr = ctx.get("task_need") == "ocr"
        looks_textual = (
            token.entity.startswith(("text:", "ocr:"))
            or token.attrs.get("kind") in ("text_region", "ocr_candidate")
        )
        if not looks_textual:
            return []
        if opt_in or task_need_ocr:
            return [Pheromone(
                kind=PK_OCR_PRIVACY_GATE, swimmer=self.name,
                entity=token.entity, severity=0.4,
                note="OCR permitted: opt-in/task-need observed in context",
            )]
        # Refuse — surprise alone is not permission
        return [Pheromone(
            kind=PK_OCR_PRIVACY_GATE, swimmer=self.name,
            entity=token.entity, severity=0.05,
            note="OCR REFUSED: no opt-in or task_need; surprise is "
                 "attention, not authorization",
        )]


# ──────────────────────────────────────────────────────────────────────
# 5. RedundancyBowelSwimmer — deletes low-info repeats from memory
# ──────────────────────────────────────────────────────────────────────

class RedundancyBowelSwimmer(VisualSwimmer):
    """When the same low-information token (low mass, no surprise)
    repeats, flag it for residue elimination. The actual deletion is
    the bowel's job; we just deposit the pheromone."""
    species = "REDUNDANCY_BOWEL"
    emits_kind = PK_VISUAL_RESIDUE_ELIMINATED

    def __init__(
        self, name: Optional[str] = None,
        *,
        mass_threshold: float = 0.20,
        repeat_threshold: int = 3,
    ) -> None:
        super().__init__(name)
        self.mass_threshold = mass_threshold
        self.repeat_threshold = repeat_threshold
        self._seen: dict[str, int] = {}

    def inspect(self, token: VisualToken, context=None) -> list[Pheromone]:
        if token.mass > self.mass_threshold or token.wake_reason in (
            "surprise", "high_delta",
        ):
            # High-info tokens are NOT residue — reset their counter
            self._seen[token.entity] = 0
            return []
        n = self._seen.get(token.entity, 0) + 1
        self._seen[token.entity] = n
        if n < self.repeat_threshold:
            return []
        return [Pheromone(
            kind=PK_VISUAL_RESIDUE_ELIMINATED, swimmer=self.name,
            entity=token.entity, severity=min(1.0, 0.2 + 0.1 * n),
            note=f"low-info repeat detected ({n}× at mass={token.mass:.2f}) — "
                 f"flag for bowel elimination",
        )]


# ──────────────────────────────────────────────────────────────────────
# 6. CrossOrganBinder — binds visual events to Talk/Journal/Work tokens
# ──────────────────────────────────────────────────────────────────────

class CrossOrganBinder(VisualSwimmer):
    """Binds visual tokens to non-visual organ tokens (Talk / Journal /
    Work) when they appear in the same context window. Records the
    cross-organ co-occurrence as a pheromone."""
    species = "CROSS_ORGAN_BINDER"
    emits_kind = PK_CROSS_ORGAN_BINDING

    def inspect(self, token: VisualToken, context=None) -> list[Pheromone]:
        ctx = context or {}
        peer_organs = ctx.get("peer_organs") or []
        # peer_organs is expected to be a list of (organ_name, entity_id) tuples
        if not peer_organs:
            return []
        # Take up to 3 closest peers
        peers = peer_organs[:3]
        peers_str = ", ".join(f"{o}:{e}" for o, e in peers)
        return [Pheromone(
            kind=PK_CROSS_ORGAN_BINDING, swimmer=self.name,
            entity=token.entity, severity=min(1.0, 0.3 + 0.1 * len(peers)),
            note=f"binds {token.entity} ↔ {peers_str}",
        )]


# ──────────────────────────────────────────────────────────────────────
# Default pool
# ──────────────────────────────────────────────────────────────────────

def default_visual_swimmer_pool(
    *, scheduler: Optional[BurstScheduler] = None,
) -> list[VisualSwimmer]:
    return [
        MotionSwimmer(),
        FaceMassSwimmer(),
        FoveaSwimmer(scheduler=scheduler or BurstScheduler()),
        OCRGuardSwimmer(),
        RedundancyBowelSwimmer(),
        CrossOrganBinder(),
    ]


# ──────────────────────────────────────────────────────────────────────
# Patrol over a token stream, write pheromone receipts
# ──────────────────────────────────────────────────────────────────────

def patrol_visual_tokens(
    tokens: Iterable[VisualToken],
    *,
    swimmers: Optional[list[VisualSwimmer]] = None,
    context: Optional[dict[str, Any]] = None,
    state_root: str | Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Run every swimmer against the token stream. Returns a summary
    dict + the list of pheromones. If `write` is True, every pheromone
    is appended to `.sifta_state/visual_token_pheromones.jsonl`."""
    if swimmers is None:
        swimmers = default_visual_swimmer_pool()
    tokens_list = list(tokens)
    all_pheromones: list[Pheromone] = []
    for sw in swimmers:
        all_pheromones.extend(sw.patrol(tokens_list, context=context))
    by_kind: dict[str, int] = {}
    by_swimmer: dict[str, int] = {}
    for p in all_pheromones:
        by_kind[p.kind] = by_kind.get(p.kind, 0) + 1
        by_swimmer[p.swimmer] = by_swimmer.get(p.swimmer, 0) + 1
    summary = {
        "truth_label": TRUTH_LABEL,
        "truth_class": "OPERATIONAL",
        "truth_boundary": TRUTH_BOUNDARY,
        "n_tokens_inspected": len(tokens_list),
        "n_pheromones": len(all_pheromones),
        "pheromones_by_kind": dict(sorted(by_kind.items())),
        "pheromones_by_swimmer": dict(sorted(by_swimmer.items())),
        "pheromones": [p.to_dict() for p in all_pheromones[:32]],  # preview
    }
    if write:
        state = Path(state_root) if state_root else _STATE
        state.mkdir(parents=True, exist_ok=True)
        with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
            for p in all_pheromones:
                row = {
                    "ts": time.time(),
                    "kind": p.kind,
                    "trace_id": str(uuid.uuid4()),
                    "truth_label": p.truth_label,
                    "truth_class": p.truth_class,
                    "swimmer": p.swimmer,
                    "entity": p.entity,
                    "severity": p.severity,
                    "note": p.note,
                    "sha256": hashlib.sha256(
                        json.dumps(p.to_dict(), sort_keys=True).encode()
                    ).hexdigest(),
                }
                f.write(json.dumps(row, sort_keys=True) + "\n")
    return summary


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()
    demo_tokens = [
        VisualToken(entity="motion:cell-7", mass=0.6, wake_reason="surprise",
                    attrs={"delta": 0.72}),
        VisualToken(entity="owner_face:Ioan", mass=0.55, wake_reason="static",
                    attrs={"kind": "face"}),
        VisualToken(entity="text:url-bar", mass=0.4, wake_reason="static",
                    attrs={"kind": "text_region"}),
        VisualToken(entity="bg:cell-12", mass=0.05, wake_reason="static"),
        VisualToken(entity="bg:cell-12", mass=0.05, wake_reason="static"),
        VisualToken(entity="bg:cell-12", mass=0.05, wake_reason="static"),
    ]
    out = patrol_visual_tokens(
        demo_tokens,
        context={"peer_organs": [("TALK", "ioan-utterance-9"),
                                  ("JOURNAL", "9:12-AM")]},
        write=not args.no_write,
    )
    print(json.dumps({k: v for k, v in out.items() if k != "pheromones"},
                     indent=2))
    print("\nfirst few pheromones:")
    for ph in out["pheromones"][:8]:
        print(f"  [{ph['kind']:<25}] {ph['entity']:<22} sev={ph['severity']:.2f}  {ph['note'][:60]}")
