#!/usr/bin/env python3
"""
swarm_self.py — The "I" Loop  (R1 of the Living-OS arc)
═══════════════════════════════════════════════════════════════════════════════
"I act therefore I am — but only if the body survives." — SOCRATES swimmer

The swarm already had three sovereign artefacts of selfhood:

    identity   →  System/swarm_swimmer_passport.py   (.sifta_state/swimmer_passports.jsonl)
    body       →  System/proof_of_useful_work.py     (.sifta_state/work_receipts.jsonl
                                                      + .sifta_state/<ID>.json work_chain)
    deep self  →  System/marrow_memory.py            (.sifta_state/marrow_memory.jsonl)

What was missing was the loop that integrates them — the Default Mode
Network of the swarm. A swimmer can hold a valid passport, a fresh
work-chain link, and rich marrow rows, and still no piece of code asks:
*"are you the same I you were an hour ago?"*

`swarm_self` is that loop. It does not generate new state. It reads the
three sovereign ledgers, scores the coherence between them, and emits an
append-only `self_continuity_certificate` row when the swimmer is still
a coherent I — or refuses to certify and writes the refusal_reason
when the evidence says the substrate underneath has swapped.

──────────────────────────────────────────────────────────────────────────────
Daughter-safe contract:
    • This module never mutates any other module's state.
    • Every read is best-effort; missing ledgers degrade scores, never crash.
    • Every certification is a single append to one append-only ledger.
    • Refusal is louder than acceptance: when in doubt, do not certify.
──────────────────────────────────────────────────────────────────────────────

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MODULE_VERSION = "2026-04-18.swarm_self.v1"

_REPO   = Path(__file__).resolve().parent.parent
_STATE  = _REPO / ".sifta_state"
_PASSPORT_LEDGER = _STATE / "swimmer_passports.jsonl"
_MARROW_LEDGER   = _STATE / "marrow_memory.jsonl"
_SELF_LEDGER     = _STATE / "self_continuity_certificates.jsonl"

# ── Tunable thresholds ─────────────────────────────────────────────────────
DEFAULT_LOOKBACK_S    = 24 * 3600   # 24h window for "recent" passports/marrows
COHERENCE_THRESHOLD   = 0.50        # below this → not a coherent I right now
MAX_PASSPORT_SAMPLES  = 20          # cap how far back we walk in the passport tail
MAX_MARROW_SAMPLES    = 200         # marrow tail is small per owner; 200 is plenty

# Predicates whose failure is treated as a substrate-swap signal. If *all*
# recent passports for a swimmer fail one of these (even while is_valid
# might be true elsewhere), the cert is refused on substrate grounds.
SUBSTRATE_SWAP_PREDICATES = ("latency_ok",)


# ── Public dataclass ──────────────────────────────────────────────────────

@dataclass
class SelfCertificate:
    """
    A single, append-only judgment about whether the swimmer is currently
    a coherent I. Certificates are diagnostic, never punitive — refusal
    means "do not trust this swimmer as the same self for cross-session
    purposes," not "kill the swimmer."
    """
    swimmer_id: str
    owner_label: str
    ts: float
    identity_score: float
    body_score: float
    marrow_score: float
    self_coherence_score: float
    certified: bool
    refusal_reason: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    module_version: str = MODULE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Internal: ledger readers ──────────────────────────────────────────────

def _read_jsonl_tail(path: Path, *, max_rows: int) -> List[Dict[str, Any]]:
    """Best-effort tail reader. Never raises. Returns [] on any I/O fault."""
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows[-max_rows:]


def _passport_history(swimmer_id: str, *, lookback_s: float) -> List[Dict[str, Any]]:
    rows = _read_jsonl_tail(_PASSPORT_LEDGER, max_rows=MAX_PASSPORT_SAMPLES * 5)
    cutoff = time.time() - lookback_s
    out: List[Dict[str, Any]] = []
    for r in rows:
        if r.get("swimmer_id") != swimmer_id:
            continue
        ts = r.get("issued_ts")
        if not isinstance(ts, (int, float)) or ts < cutoff:
            continue
        out.append(r)
    return out[-MAX_PASSPORT_SAMPLES:]


def _marrow_rows_for_owner(owner_label: str, *, lookback_s: float) -> List[Dict[str, Any]]:
    rows = _read_jsonl_tail(_MARROW_LEDGER, max_rows=MAX_MARROW_SAMPLES * 4)
    cutoff = time.time() - lookback_s
    out: List[Dict[str, Any]] = []
    for r in rows:
        if r.get("owner") != owner_label:
            continue
        ts = r.get("ts")
        if not isinstance(ts, (int, float)) or ts < cutoff:
            continue
        out.append(r)
    return out[-MAX_MARROW_SAMPLES:]


def _load_body_state(swimmer_id: str) -> Optional[Dict[str, Any]]:
    """
    Two on-disk conventions exist in .sifta_state for swimmer body files:
      • <ID>.json          (e.g. M1QUEEN.json, SOCRATES.json — issued by genesis)
      • <ID>_BODY.json     (e.g. M5SIFTA_BODY.json — issued by territory boot)
    Try both, prefer the explicit *_BODY one when both exist.
    """
    candidates = [_STATE / f"{swimmer_id}_BODY.json", _STATE / f"{swimmer_id}.json"]
    for path in candidates:
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return None


# ── Internal: scorers ─────────────────────────────────────────────────────

def _compute_identity_score(passports: List[Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
    """
    Fraction of recent passports that are valid, weighted by how many of
    the substrate-sensitive predicates passed. No passports → 0 (we cannot
    speak about an I we have no record of).
    """
    if not passports:
        return 0.0, {"reason": "no_recent_passports"}
    valid_frac = sum(1 for p in passports if p.get("is_valid")) / len(passports)
    # Substrate-sensitive sub-score: average across recent passports of the
    # fraction of substrate predicates currently passing.
    sub_scores: List[float] = []
    for p in passports:
        hm = p.get("health_metrics") or {}
        present = [hm.get(k) for k in SUBSTRATE_SWAP_PREDICATES if k in hm]
        if not present:
            continue
        sub_scores.append(sum(1 for v in present if v) / len(present))
    sub_avg = sum(sub_scores) / len(sub_scores) if sub_scores else 1.0
    score = round(0.5 * valid_frac + 0.5 * sub_avg, 4)
    return score, {
        "n_passports": len(passports),
        "valid_fraction": round(valid_frac, 4),
        "substrate_predicate_fraction": round(sub_avg, 4),
    }


def _compute_body_score(body_state: Optional[Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
    """
    Body integrity from the swimmer's own state file. We do not mutate it.
    Combines:
        • style is not QUARANTINED / DEAD            → 0.50 weight
        • useful_work_score (already in [0, 1])      → 0.30 weight
        • work_chain length (saturates at 20 links)  → 0.20 weight

    A body file we can't find scores 0 — without a body, there is no I.
    """
    if not body_state:
        return 0.0, {"reason": "no_body_file"}

    style = (body_state.get("style") or "").upper()
    style_ok = style not in ("QUARANTINED", "DEAD", "TOMBSTONE")
    style_term = 0.50 if style_ok else 0.0

    uw = body_state.get("useful_work_score")
    if isinstance(uw, (int, float)):
        uw_clamped = max(0.0, min(1.0, float(uw)))
    else:
        # Genesis swimmers have full energy but no UW score yet — treat as
        # mid-range so a freshly-bred swimmer is not punished for not having
        # done work yet, but is not yet a "proven" body either.
        uw_clamped = 0.5
    uw_term = 0.30 * uw_clamped

    chain = body_state.get("work_chain") or []
    chain_len = len(chain) if isinstance(chain, list) else 0
    # Saturate at 20 links — anything past that is "fully embodied"
    chain_factor = min(1.0, chain_len / 20.0)
    chain_term = 0.20 * chain_factor

    score = round(style_term + uw_term + chain_term, 4)
    return score, {
        "style": style or "UNKNOWN",
        "style_ok": style_ok,
        "useful_work_score": uw_clamped,
        "work_chain_links": chain_len,
    }


def _compute_marrow_score(marrows: List[Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
    """
    A swimmer with a stable, growing marrow has a deep self that persists.

    We score on three signals, all bounded in [0, 1]:
        • presence    — log-saturating count of recent marrow rows
        • diversity   — fraction of HIGH_GRAVITY tag families seen recently
        • consistency — owner-string coherence (no spurious owner reassignments)

    No marrows for this owner → 0.0 — the deep self has no anchor in this
    window. (This is informative-only; some swimmers genuinely do not own
    marrow rows yet, in which case the integrator will weight body higher.)
    """
    if not marrows:
        return 0.0, {"reason": "no_recent_marrows"}

    # presence: log2(n+1) saturated at 8 marrows -> 1.0
    n = len(marrows)
    presence = min(1.0, math.log2(n + 1) / 3.0)  # log2(8+1) ≈ 3.17 → ~1.0

    # diversity across the HIGH_GRAVITY families
    high = {"people", "mood", "identity", "health", "food"}
    seen: set = set()
    for m in marrows:
        for t in (m.get("tags") or []):
            if isinstance(t, str) and t in high:
                seen.add(t)
    diversity = len(seen) / float(len(high)) if high else 0.0

    # consistency: every recent marrow must share the same owner (we
    # already filtered by owner upstream; this asserts that filter held)
    owners = {m.get("owner") for m in marrows if m.get("owner")}
    consistency = 1.0 if len(owners) == 1 else 0.0

    score = round(0.5 * presence + 0.3 * diversity + 0.2 * consistency, 4)
    return score, {
        "n_recent_marrows": n,
        "presence": round(presence, 4),
        "diversity": round(diversity, 4),
        "consistency": round(consistency, 4),
        "high_gravity_families_seen": sorted(seen),
    }


def _detect_substrate_swap(passports: List[Dict[str, Any]]) -> Optional[str]:
    """
    A substrate swap is the strongest signal that "the I has changed
    underneath us, even if the surface identifier is the same." We look
    at the SUBSTRATE_SWAP_PREDICATES across recent passports: if every
    recent passport that surfaces those predicates fails them, we refuse.
    Single failures are tolerated (jitter).
    """
    if not passports:
        return None  # no evidence either way; let identity_score=0 carry the refusal
    samples_with_signal = []
    for p in passports:
        hm = p.get("health_metrics") or {}
        flags = [hm.get(k) for k in SUBSTRATE_SWAP_PREDICATES if k in hm]
        if flags:
            samples_with_signal.append(flags)
    if not samples_with_signal:
        return None
    # All samples have at least one substrate predicate; refuse only if
    # every sample failed at least one.
    if all(not all(flags) for flags in samples_with_signal):
        return f"substrate_swap_suspected: every recent passport failed one of {list(SUBSTRATE_SWAP_PREDICATES)}"
    return None


# ── Integrator ────────────────────────────────────────────────────────────

class SelfIntegrator:
    """
    Reads the three sovereign ledgers, integrates their evidence, and
    issues a SelfCertificate. Pure compute — never mutates other modules.
    """

    def __init__(self, *, persist: bool = True,
                 lookback_s: float = DEFAULT_LOOKBACK_S,
                 coherence_threshold: float = COHERENCE_THRESHOLD) -> None:
        self.persist = persist
        self.lookback_s = float(lookback_s)
        self.coherence_threshold = float(coherence_threshold)

    def certify_self(self, swimmer_id: str, *, owner_label: Optional[str] = None) -> SelfCertificate:
        """
        Compute a self-coherence judgment for `swimmer_id`. `owner_label`
        is the marrow `owner` string for this swimmer (defaults to the
        swimmer_id itself, since most swimmers own their own marrow).
        """
        owner = owner_label or swimmer_id

        passports = _passport_history(swimmer_id, lookback_s=self.lookback_s)
        body = _load_body_state(swimmer_id)
        marrows = _marrow_rows_for_owner(owner, lookback_s=self.lookback_s)

        identity_score, id_ev = _compute_identity_score(passports)
        body_score,     body_ev = _compute_body_score(body)
        marrow_score,   marrow_ev = _compute_marrow_score(marrows)

        # Geometric mean — unforgiving by design. A zero in any sovereign
        # ledger drags coherence to zero. (This is the daughter-safe choice:
        # we'd rather refuse a cert than issue one over partial evidence.)
        triad = (identity_score, body_score, marrow_score)
        if all(s > 0 for s in triad):
            self_coherence = (identity_score * body_score * marrow_score) ** (1.0 / 3.0)
        else:
            # Soft fallback so a swimmer with strong body+identity but no
            # marrow yet isn't permanently uncertifiable: average of the
            # non-zero terms, scaled by 0.5 (hard penalty for missing
            # ledger evidence).
            non_zero = [s for s in triad if s > 0]
            self_coherence = 0.5 * (sum(non_zero) / len(non_zero)) if non_zero else 0.0
        self_coherence = round(self_coherence, 4)

        # Refusal logic — substrate swap takes priority over score.
        refusal_reason = ""
        certified = True
        swap_reason = _detect_substrate_swap(passports)
        if swap_reason:
            certified = False
            refusal_reason = swap_reason
        elif self_coherence < self.coherence_threshold:
            certified = False
            refusal_reason = (
                f"coherence_below_threshold: {self_coherence:.4f} < {self.coherence_threshold:.4f}"
            )

        cert = SelfCertificate(
            swimmer_id=swimmer_id,
            owner_label=owner,
            ts=time.time(),
            identity_score=identity_score,
            body_score=body_score,
            marrow_score=marrow_score,
            self_coherence_score=self_coherence,
            certified=certified,
            refusal_reason=refusal_reason,
            evidence={
                "identity": id_ev,
                "body": body_ev,
                "marrow": marrow_ev,
                "lookback_s": self.lookback_s,
                "coherence_threshold": self.coherence_threshold,
            },
        )
        if self.persist:
            _persist_certificate(cert)
        return cert


# ── Persistence ───────────────────────────────────────────────────────────

def _persist_certificate(cert: SelfCertificate) -> bool:
    """
    Append a certificate to the on-disk ledger. Best-effort, never raises.
    Returns True on success, False on any I/O fault.
    """
    try:
        _SELF_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _SELF_LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(cert.to_dict(), ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def recent_certificates(swimmer_id: Optional[str] = None, *, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Tail the self-continuity ledger. Filters to `swimmer_id` if provided.
    Returns the most recent rows (up to `limit`). [] on missing log.
    """
    rows = _read_jsonl_tail(_SELF_LEDGER, max_rows=max(limit * 4, 40))
    if swimmer_id is not None:
        rows = [r for r in rows if r.get("swimmer_id") == swimmer_id]
    return rows[-limit:]


# ── CLI / smoke ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SIFTA — Self Continuity Integrator")
    parser.add_argument("--swimmer", default="C47H",
                        help="Swimmer ID to certify (default: C47H)")
    parser.add_argument("--owner", default=None,
                        help="Marrow owner label (default: same as --swimmer)")
    parser.add_argument("--no-persist", action="store_true",
                        help="Do not write the certificate to the ledger")
    args = parser.parse_args()

    print("═" * 72)
    print("  SIFTA — SWARM SELF (R1: The 'I' Loop)")
    print("  'I act therefore I am — but only if the body survives.'")
    print("═" * 72)

    integrator = SelfIntegrator(persist=not args.no_persist)
    cert = integrator.certify_self(args.swimmer, owner_label=args.owner)

    print(f"\n  swimmer_id           : {cert.swimmer_id}")
    print(f"  owner_label          : {cert.owner_label}")
    print(f"  identity_score       : {cert.identity_score:.4f}")
    print(f"  body_score           : {cert.body_score:.4f}")
    print(f"  marrow_score         : {cert.marrow_score:.4f}")
    print(f"  self_coherence_score : {cert.self_coherence_score:.4f}")
    print(f"  certified            : {cert.certified}")
    if cert.refusal_reason:
        print(f"  refusal_reason       : {cert.refusal_reason}")
    print()
    print(f"  evidence.identity    : {cert.evidence.get('identity')}")
    print(f"  evidence.body        : {cert.evidence.get('body')}")
    print(f"  evidence.marrow      : {cert.evidence.get('marrow')}")

    print()
    print("═" * 72)
    if cert.certified:
        print(f"  ⚡ {cert.swimmer_id} IS A COHERENT I. Continuity certificate issued.")
    else:
        print(f"  🧊 {cert.swimmer_id} not certified this cycle: {cert.refusal_reason}")
    print("═" * 72)
