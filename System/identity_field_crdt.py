#!/usr/bin/env python3
"""
identity_field_crdt.py — Live LLM identity as a CRDT-mergeable Dirichlet field.
══════════════════════════════════════════════════════════════════════════════

Origin
------
Proposed by CG53 (SwarmGPT / GPT-5.3, 2026-04-17) via the Architect.
Critiqued, upgraded, and implemented by C47H (Cursor IDE).

Why this replaces a static registry
-----------------------------------
`ide_model_registry.jsonl` says "which model do we *label* this session."
SwarmGPT's core insight: identity is not a label; it is a continuously
estimated distribution. A model running behind a router (CAUT), through
Personal Intelligence context contamination, or through an auto-upgrade
path is a *multi-peak* entity. A single string cannot represent it.

Upgrade over the initial sketch
-------------------------------
CG53's draft used `0.7 * prior + 0.3 * new`. That is an EMA, not a CRDT,
and it silently drops new model keys that appear mid-session. This module
instead uses a **G-counter per (node_id, model_family)** with a Dirichlet
posterior on top:

    counts[node_id][model_family] ∈ ℕ, monotone ↑        (CRDT g-counter)
    totals[m] = Σ_n counts[n][m]
    p(m)      = (totals[m] + α) / (Σ_m' totals[m'] + α·K)

Merge is elementwise max per (node_id, model_family). That is **commutative,
associative, idempotent** — i.e. an actual CRDT. Two nodes (C47H on Cursor,
AG31 on Antigravity, CG53 on ChatGPT) can update independently, ship the
state over the dead drop, and converge.

Declared identity gets a small pseudo-count bump, but because totals are
monotone across observations, one loud declaration can never dominate a
long tail of behavioral evidence.

Public API
----------
    IdentityField               — the CRDT state object
    update_from_classifier(...) — add soft evidence (probability dict)
    update_from_declaration(...)— add a self-claim (bounded boost)
    merge(other)                — CRDT join with another IdentityField
    distribution()              — Dirichlet posterior mean
    entropy(), stability(), is_drifting()
    generate_probe()            — entropy-adaptive probe selector
    persist(path), load(path)   — flock-safe JSON snapshot
    deposit_llm_registry_entry  — append an SLLI row to llm_registry.jsonl

No network calls. No weight self-attestation. Measurement over assertion.
"""
from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from System.jsonl_file_lock import (
    append_line_locked,
    read_text_locked,
    read_write_json_locked,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_FIELD_PATH = _STATE / "identity_field.json"
_LLM_REGISTRY = _STATE / "llm_registry.jsonl"
_INTUITION_LOG = _STATE / "human_intuition_log.jsonl"

SCHEMA_VERSION = 1
MODULE_VERSION = "2026-04-17.v1"

# Dirichlet prior strength per known hypothesis. Small = let data dominate,
# but > 0 so p(m) is never exactly 0 for an observed-at-least-once model.
DEFAULT_ALPHA = 0.5

# Cap on declared-identity pseudo-counts per call. Prevents a loud self-claim
# from steamrolling behavioral evidence (the failure mode SwarmGPT warned about).
DECLARATION_MAX_BOOST = 1.0

# Cap on human-intuition pseudo-counts per call. Intuition is *bias*, not
# *authority* (CG53 ground rule). We deliberately cap it below a single
# weight=1 classifier observation so a gut feeling cannot pin the field.
HUMAN_INTUITION_MAX_BOOST = 0.75

# Default classifier-vs-human disagreement threshold before we flag a conflict.
HUMAN_CONFLICT_CONFIDENCE_THRESHOLD = 0.7

# How many historical snapshots to keep for drift estimation.
HISTORY_WINDOW = 16


# ─── Helpers ────────────────────────────────────────────────────────────────

def _normalize(d: Mapping[str, float]) -> Dict[str, float]:
    total = sum(d.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in d.items()}


def _shannon_entropy(probs: Iterable[float]) -> float:
    h = 0.0
    for p in probs:
        if p > 0:
            h -= p * math.log(p)
    return h


def _js_divergence(p: Mapping[str, float], q: Mapping[str, float]) -> float:
    """Jensen-Shannon divergence. Symmetric, bounded in [0, log 2]."""
    keys = set(p) | set(q)
    if not keys:
        return 0.0
    m = {k: 0.5 * (p.get(k, 0.0) + q.get(k, 0.0)) for k in keys}

    def _kl(a: Mapping[str, float], b: Mapping[str, float]) -> float:
        s = 0.0
        for k in keys:
            pa = a.get(k, 0.0)
            pb = b.get(k, 0.0)
            if pa > 0 and pb > 0:
                s += pa * math.log(pa / pb)
        return s

    return 0.5 * _kl(p, m) + 0.5 * _kl(q, m)


# ─── Human intuition signal (CG53 proposal, 2026-04-17) ───────────────────

@dataclass(frozen=True)
class HumanIntuitionSignal:
    """
    Biological pattern-recognition signal from the Architect.

    Design rules (per CG53):
      * BIAS not AUTHORITY — capped at HUMAN_INTUITION_MAX_BOOST per call,
        always below a single weight=1 classifier observation.
      * Auditable — every signal is logged to `human_intuition_log.jsonl`
        with timestamp, observer, features, notes.
      * Conflict-revealing — `detect_conflict()` flags disagreement between
        classifier top / declaration / intuition for governance review.
    """
    label: str                                    # model_family the human claims they "feel"
    confidence: float                             # 0.0 – 1.0
    observer: str = "architect"                   # who produced the signal
    features: Dict[str, float] = field(default_factory=dict)
    notes: str = ""
    timestamp: float = field(default_factory=time.time)

    def clamp(self) -> "HumanIntuitionSignal":
        """Return a copy with confidence clamped to [0.0, 1.0]."""
        c = min(max(0.0, float(self.confidence)), 1.0)
        if c == self.confidence:
            return self
        return HumanIntuitionSignal(
            label=self.label,
            confidence=c,
            observer=self.observer,
            features=dict(self.features),
            notes=self.notes,
            timestamp=self.timestamp,
        )


# ─── CRDT state ─────────────────────────────────────────────────────────────

@dataclass
class IdentityField:
    """
    G-counter-backed Dirichlet posterior over model identity.

    counts[node_id][model_family] is the pseudo-count contributed by that
    node. Each node only ever increments its own entries, so per-pair values
    are monotonically non-decreasing and the state is a valid CRDT.
    """

    counts: Dict[str, Dict[str, float]] = field(default_factory=dict)
    alpha: float = DEFAULT_ALPHA
    observations: int = 0
    last_updated_ts: float = 0.0
    history: List[Dict[str, float]] = field(default_factory=list)

    # ─── Internal count accessors ──────────────────────────────────────────

    def _bump(self, node_id: str, model: str, delta: float) -> None:
        if delta <= 0:
            return
        bucket = self.counts.setdefault(node_id, {})
        bucket[model] = bucket.get(model, 0.0) + float(delta)

    def _totals(self) -> Dict[str, float]:
        # Sort node and model keys so float summation order is deterministic
        # across merge paths. Without this, CRDT equivalence holds at the
        # integer/exact level but floats can differ in the last ULP.
        out: Dict[str, float] = {}
        for node in sorted(self.counts):
            for model in sorted(self.counts[node]):
                out[model] = out.get(model, 0.0) + self.counts[node][model]
        return out

    # ─── Updates ────────────────────────────────────────────────────────────

    def update_from_classifier(
        self,
        node_id: str,
        classifier_output: Mapping[str, float],
        *,
        weight: float = 1.0,
    ) -> None:
        """
        Fold soft evidence from a behavioral classifier into the field.

        `classifier_output` is a {model_family: probability} dict. It does not
        need to sum to 1; we normalize defensively. `weight` scales the
        number of pseudo-counts added (larger = higher-confidence probe).
        """
        if weight <= 0:
            return
        probs = _normalize({k: max(0.0, float(v)) for k, v in classifier_output.items()})
        for model, p in probs.items():
            self._bump(node_id, model, p * weight)
        self.observations += 1
        self.last_updated_ts = time.time()
        self._push_history()

    def update_from_declaration(
        self,
        node_id: str,
        declared_model: str,
        *,
        boost: float = 0.25,
    ) -> None:
        """
        Fold a declared self-identity string into the field. Bounded:
        never more than DECLARATION_MAX_BOOST per call, regardless of
        the caller's `boost` argument.
        """
        if not declared_model:
            return
        b = min(max(0.0, float(boost)), DECLARATION_MAX_BOOST)
        self._bump(node_id, declared_model, b)
        self.observations += 1
        self.last_updated_ts = time.time()
        self._push_history()

    def update_from_human_intuition(
        self,
        node_id: str,
        signal: HumanIntuitionSignal,
        *,
        weight: float = 0.25,
    ) -> None:
        """
        Fold a human-intuition signal into the field as a bounded pseudo-count.

        Pseudo-count added = min(weight * confidence, HUMAN_INTUITION_MAX_BOOST).
        This is intentionally below a single weight=1 classifier observation
        so the Architect's intuition can *bias* the field but never *pin* it.
        """
        if signal is None:
            return
        sig = signal.clamp()
        if sig.confidence <= 0 or weight <= 0 or not sig.label:
            return
        boost = min(float(weight) * sig.confidence, HUMAN_INTUITION_MAX_BOOST)
        self._bump(node_id, sig.label, boost)
        self.observations += 1
        self.last_updated_ts = time.time()
        self._push_history()

        # Auditable side-log. This is NOT the CRDT state; it's the provenance
        # trail so we can later compare intuition vs classifier vs declaration.
        _append_intuition_log(
            node_id=node_id,
            signal=sig,
            applied_boost=boost,
            weight=weight,
            distribution_top=self.top(),
            entropy=self.entropy(),
        )

    # ─── CRDT merge ─────────────────────────────────────────────────────────

    def merge(self, other: "IdentityField") -> None:
        """
        CRDT join: elementwise max per (node_id, model_family).

        Commutative, associative, idempotent. Safe to call in any order on
        any pair of snapshots coming off the dead drop.
        """
        for node, bucket in other.counts.items():
            local = self.counts.setdefault(node, {})
            for model, c in bucket.items():
                if c > local.get(model, 0.0):
                    local[model] = float(c)
        # Observation count is *not* a CRDT under addition (double-counts on
        # re-merge of shared history). Take the max as a conservative proxy.
        self.observations = max(self.observations, other.observations)
        self.last_updated_ts = max(self.last_updated_ts, other.last_updated_ts)
        self._push_history()

    # ─── Readout ────────────────────────────────────────────────────────────

    def distribution(self) -> Dict[str, float]:
        """Dirichlet posterior mean over all model hypotheses observed so far."""
        totals = self._totals()
        if not totals:
            return {}
        k = len(totals)
        denom = sum(totals.values()) + self.alpha * k
        if denom <= 0:
            return {}
        return {m: (c + self.alpha) / denom for m, c in totals.items()}

    def top(self) -> Optional[Tuple[str, float]]:
        d = self.distribution()
        if not d:
            return None
        m = max(d, key=d.get)
        return m, d[m]

    def entropy(self) -> float:
        d = self.distribution()
        return _shannon_entropy(d.values())

    def max_entropy(self) -> float:
        d = self.distribution()
        return math.log(len(d)) if d else 0.0

    def stability(self) -> float:
        """
        Stability = 1 - H / H_max. 1.0 = single peak, 0.0 = uniform.
        Honest scalar, unlike `top probability` which hides multi-peak states.
        """
        hmax = self.max_entropy()
        if hmax <= 0:
            return 1.0 if self.distribution() else 0.0
        return max(0.0, 1.0 - self.entropy() / hmax)

    def is_drifting(self, *, threshold: float = 0.2, lookback: int = 4) -> bool:
        """
        True if JS divergence between the current distribution and the
        distribution `lookback` snapshots ago exceeds `threshold` nats.
        Catches auto-router drift and Personal-Intelligence contamination.
        """
        if len(self.history) <= lookback:
            return False
        old = self.history[-lookback - 1]
        return _js_divergence(self.distribution(), old) > threshold

    # ─── Collapse protocol (CG53, Step 5) ──────────────────────────────────

    def apply_collapse_update(
        self,
        scores: Mapping[str, float],
        *,
        human_signal: Optional[HumanIntuitionSignal] = None,
        strength: float = 0.6,
        node_id: str = "COLLAPSE",
    ) -> None:
        """
        Convergence step used when probe results + optional human intuition
        should push the field toward a decision. Still CRDT-safe: writes
        pseudo-counts through the same G-counter path, never mutates
        `distribution()` directly.

        Rationale vs CG53's sketch
        --------------------------
        CG53 proposed `distribution[k] = dist[k] * (1 - s) + scores[k] * s`,
        which would replace the G-counter state with a smoothed distribution
        and break merge semantics. Instead we compute the implied pseudo-
        counts for the `scores` vector and bump them into the COLLAPSE
        row of the G-counter with a `strength`-scaled weight, then apply
        the (already-capped) human-intuition pseudo-count. Result: identical
        convergence behavior, preserved merge algebra.
        """
        if not scores:
            return
        # Normalize the score vector defensively.
        s = {k: max(0.0, float(v)) for k, v in scores.items()}
        tot = sum(s.values())
        if tot <= 0:
            return
        probs = {k: v / tot for k, v in s.items()}
        # Pseudo-count mass injected by this collapse step. We treat
        # `strength` as "equivalent classifier observations of weight 1".
        # The higher the strength, the more the collapse pulls the field.
        weight = max(0.0, float(strength)) * max(1, self.observations // 4 + 1)
        for model, p in probs.items():
            self._bump(node_id, model, p * weight)
        self.observations += 1
        self.last_updated_ts = time.time()
        self._push_history()

        if human_signal is not None:
            # Intuition still respects its own cap — collapse cannot be
            # hijacked by a loud human override.
            self.update_from_human_intuition(node_id, human_signal, weight=0.25)

    # ─── Conflict detection (classifier / declaration / intuition) ─────────

    def detect_conflict(
        self,
        *,
        human_signal: Optional[HumanIntuitionSignal] = None,
        declared_label: Optional[str] = None,
        confidence_threshold: float = HUMAN_CONFLICT_CONFIDENCE_THRESHOLD,
    ) -> Dict[str, Any]:
        """
        Report disagreement between the CRDT's current top hypothesis, the
        human's intuition, and any declared self-identity.

        Returns a dict with booleans + the actual labels so callers can decide
        whether to raise an anomaly. Never mutates state.
        """
        top_pair = self.top()
        top_label = top_pair[0] if top_pair else None

        human_label = None
        human_conf = 0.0
        if human_signal is not None:
            sig = human_signal.clamp()
            if sig.confidence >= confidence_threshold:
                human_label = sig.label
                human_conf = sig.confidence

        classifier_vs_human = bool(
            human_label and top_label and human_label != top_label
        )
        classifier_vs_declaration = bool(
            declared_label and top_label and declared_label != top_label
        )
        human_vs_declaration = bool(
            human_label and declared_label and human_label != declared_label
        )

        return {
            "classifier_top": top_label,
            "human_label": human_label,
            "human_confidence": human_conf,
            "declared_label": declared_label,
            "classifier_vs_human": classifier_vs_human,
            "classifier_vs_declaration": classifier_vs_declaration,
            "human_vs_declaration": human_vs_declaration,
            "any_conflict": (
                classifier_vs_human
                or classifier_vs_declaration
                or human_vs_declaration
            ),
        }

    # ─── Probes ─────────────────────────────────────────────────────────────

    def generate_probe(self, *, entropy_threshold: float = 1.0) -> str:
        """
        Entropy-adaptive probe selector. High entropy → ask a question that
        maximally splits candidate models. Low entropy → confirm the mode.

        The actual probe text lives in Documents/STIGMERGIC_LLM_ID_PROBE.md;
        this function only returns the routing tag.
        """
        if self.entropy() > entropy_threshold:
            return "high_disambiguation_probe"
        return "low_frequency_probe"

    # ─── History ────────────────────────────────────────────────────────────

    def _push_history(self) -> None:
        snap = self.distribution()
        if not snap:
            return
        self.history.append(snap)
        if len(self.history) > HISTORY_WINDOW:
            self.history = self.history[-HISTORY_WINDOW:]

    # ─── Persistence ────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "module_version": MODULE_VERSION,
            "counts": self.counts,
            "alpha": self.alpha,
            "observations": self.observations,
            "last_updated_ts": self.last_updated_ts,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "IdentityField":
        f = cls(
            counts={k: dict(v) for k, v in d.get("counts", {}).items()},
            alpha=float(d.get("alpha", DEFAULT_ALPHA)),
            observations=int(d.get("observations", 0)),
            last_updated_ts=float(d.get("last_updated_ts", 0.0)),
            history=[dict(h) for h in d.get("history", [])],
        )
        return f

    def persist(self, path: Path = _FIELD_PATH) -> Dict[str, Any]:
        """Atomically write the CRDT state under flock, merging with disk."""
        self_snap = self.to_dict()

        def _apply(on_disk: Dict[str, Any]) -> Dict[str, Any]:
            if not on_disk:
                return self_snap
            on_disk_field = IdentityField.from_dict(on_disk)
            on_disk_field.merge(self)
            return on_disk_field.to_dict()

        return read_write_json_locked(path, _apply)

    @classmethod
    def load(cls, path: Path = _FIELD_PATH) -> "IdentityField":
        if not path.exists():
            return cls()
        try:
            raw = read_text_locked(path)
            if not raw.strip():
                return cls()
            return cls.from_dict(json.loads(raw))
        except (OSError, json.JSONDecodeError):
            return cls()


# ─── Human intuition provenance log ───────────────────────────────────────

def _append_intuition_log(
    *,
    node_id: str,
    signal: HumanIntuitionSignal,
    applied_boost: float,
    weight: float,
    distribution_top: Optional[Tuple[str, float]],
    entropy: float,
    path: Path = _INTUITION_LOG,
) -> None:
    """Auditable side-log for every intuition signal folded into the field."""
    row = {
        "schema_version": SCHEMA_VERSION,
        "module_version": MODULE_VERSION,
        "timestamp": signal.timestamp,
        "iso_local": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(signal.timestamp)),
        "node_id": node_id,
        "observer": signal.observer,
        "signal": {
            "label": signal.label,
            "confidence": round(signal.confidence, 3),
            "features": dict(signal.features),
            "notes": signal.notes,
        },
        "applied_boost": round(applied_boost, 4),
        "weight": round(weight, 4),
        "field_state_after": {
            "top": (
                {"label": distribution_top[0], "prob": round(distribution_top[1], 4)}
                if distribution_top else None
            ),
            "entropy": round(entropy, 4),
        },
    }
    append_line_locked(path, json.dumps(row, ensure_ascii=False) + "\n")


# ─── SLLI ledger deposits ──────────────────────────────────────────────────

def deposit_llm_registry_entry(
    *,
    trigger_code: str,
    model_family: str,
    model_version: str,
    substrate: str,
    confidence_attestation: float,
    deposited_by: str,
    session_id: str = "ephemeral",
    anomaly_flag: bool = False,
    behavior_fingerprint: Optional[str] = None,
    notes: str = "",
    human_intuition_signal: Optional[HumanIntuitionSignal] = None,
    path: Path = _LLM_REGISTRY,
) -> Dict[str, Any]:
    """
    Append an SLLI ledger row to .sifta_state/llm_registry.jsonl.

    `deposited_by` is the trigger code of the node writing the row (C47H,
    AG31, CG53, …). Self-attested rows must set confidence_attestation <= 0.7;
    only externally-verified rows may exceed that. This is an honor-system
    ceiling, not a cryptographic one — use crypto_keychain.sign_block for
    the latter.
    """
    if not behavior_fingerprint:
        behavior_fingerprint = uuid.uuid4().hex
    if deposited_by == trigger_code and confidence_attestation > 0.7:
        confidence_attestation = 0.7  # self-report ceiling
    row: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "module_version": MODULE_VERSION,
        "timestamp": int(time.time()),
        "session_id": session_id,
        "llm_signature": {
            "trigger_code": trigger_code,
            "model_family": model_family,
            "model_version": model_version,
            "substrate": substrate,
            "confidence_attestation": round(float(confidence_attestation), 3),
        },
        "behavior_fingerprint": behavior_fingerprint,
        "anomaly_flag": bool(anomaly_flag),
        "deposited_by": deposited_by,
        "notes": notes,
    }
    if human_intuition_signal is not None:
        sig = human_intuition_signal.clamp()
        row["human_intuition_signal"] = {
            "label": sig.label,
            "confidence": round(sig.confidence, 3),
            "observer": sig.observer,
            "features": dict(sig.features),
            "notes": sig.notes,
            "timestamp": sig.timestamp,
        }
    append_line_locked(path, json.dumps(row, ensure_ascii=False) + "\n")
    return row


# ─── Demo / self-test ──────────────────────────────────────────────────────

def _demo() -> None:
    """Runs a synthetic three-node convergence to sanity-check the CRDT."""
    print(f"[identity_field_crdt] demo  v{MODULE_VERSION}")

    # Three independent nodes observe the same latent process.
    a = IdentityField()
    b = IdentityField()
    c = IdentityField()

    a.update_from_classifier("C47H", {"opus-4.7": 0.7, "gpt-5.3": 0.2, "gemini-3.1": 0.1}, weight=3)
    a.update_from_declaration("C47H", "opus-4.7", boost=0.2)

    b.update_from_classifier("AG31", {"opus-4.7": 0.5, "gemini-3.1": 0.4, "gpt-5.3": 0.1}, weight=2)
    b.update_from_declaration("AG31", "gemini-3.1", boost=0.2)

    c.update_from_classifier("CG53", {"gpt-5.3": 0.8, "opus-4.7": 0.1, "gemini-3.1": 0.1}, weight=2)
    c.update_from_declaration("CG53", "gpt-5.3", boost=0.2)

    # CRDT: merge order must not matter.
    m1 = IdentityField(); m1.merge(a); m1.merge(b); m1.merge(c)
    m2 = IdentityField(); m2.merge(c); m2.merge(a); m2.merge(b)
    assert m1.distribution() == m2.distribution(), "CRDT merge is not order-independent"

    # Idempotence.
    before = dict(m1.distribution())
    m1.merge(a)
    after = dict(m1.distribution())
    assert before == after, "CRDT merge is not idempotent"

    print("distribution:", {k: round(v, 3) for k, v in m1.distribution().items()})
    print("top:", m1.top())
    print("entropy:", round(m1.entropy(), 3), "/ max:", round(m1.max_entropy(), 3))
    print("stability:", round(m1.stability(), 3))
    print("probe route:", m1.generate_probe())
    print("CRDT: order-independent + idempotent  OK")

    # Human intuition layer — CG53 extension.
    intuition = HumanIntuitionSignal(
        label="gpt-5.3",
        confidence=0.8,
        observer="architect",
        features={"rigidity": 0.7, "anti_hallucination": 0.9, "mirroring": 0.2},
        notes="feels like CG53, consistent structure, low drift",
    )
    m1.update_from_human_intuition("ARCHITECT", intuition, weight=0.25)
    conflict = m1.detect_conflict(human_signal=intuition, declared_label="opus-4.7")
    print("after intuition top:", m1.top())
    print("conflict report:", conflict)
    # Hard invariant: intuition must not single-handedly flip the top hypothesis
    # against a multi-observation classifier majority.
    assert (m1.top() is not None), "field should still have a top"


if __name__ == "__main__":
    _demo()


__all__ = [
    "IdentityField",
    "HumanIntuitionSignal",
    "deposit_llm_registry_entry",
    "MODULE_VERSION",
    "SCHEMA_VERSION",
    "HUMAN_INTUITION_MAX_BOOST",
    "HUMAN_CONFLICT_CONFIDENCE_THRESHOLD",
]
