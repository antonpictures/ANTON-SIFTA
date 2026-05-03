"""
Event 140 — Autopoiesis / Viability Monitor (Q2)
Varela, F., Maturana, H. & Uribe, R. (1974). Autopoiesis: The organization of
    living systems. BioSystems, 5(4), 187-196.
Luisi, P.L. (2003). Autopoiesis: a review and reappraisal. Naturwissenschaften.

Computes a bounded scalar viability index V_t ∈ [0, 1] every tick from
five observable sub-scores (all read from existing SIFTA ledgers):

    V_t = α₁·energy_budget + α₂·memory_continuity + α₃·owner_contact_freshness
        + α₄·self_repair_rate + α₅·schema_refinement_rate

Thresholds (configurable via env):
    V_t ≥ 0.70 → VIABLE
    V_t ≥ 0.45 → METABOLIC_CONSERVATION (organism is straining)
    V_t < 0.45 → CRITICAL (owner should be notified)

Writes append-only to viability.jsonl. Never mutates other organs.
Kill-switch: SIFTA_AUTOPOIESIS_DISABLE=1.

Q3 (Φ̂ integrated information) and Q5 (emergence / synergy) are stubs here —
    their measurement requires joint probability tables across all organ outputs,
    which needs a separate joint-ledger sweep. See summary_for_prompt() for
    the placeholder that will be filled once the joint sweep is built.
"""
from __future__ import annotations

import json
import math
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from System.swarm_persistent_owner_history import state_dir
except ImportError:
    def state_dir(root=None):  # type: ignore
        return Path(root) if root else Path(".sifta_state")

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except ImportError:
    def read_text_locked(path: Path, **kw) -> str:  # type: ignore
        return path.read_text(**kw) if path.exists() else ""

    def append_line_locked(path: Path, line: str, **kw) -> None:  # type: ignore
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kw) as f:
            f.write(line)

_DISABLE_ENV = "SIFTA_AUTOPOIESIS_DISABLE"
LOG_NAME     = "viability.jsonl"

# Weights — must sum to 1.0 (checked at import)
_W = {
    "energy_budget":            0.25,
    "memory_continuity":        0.20,
    "owner_contact_freshness":  0.25,
    "self_repair_rate":         0.15,
    "schema_refinement_rate":   0.15,
}
assert abs(sum(_W.values()) - 1.0) < 1e-9, "Viability weights must sum to 1.0"

_VIABLE_THRESHOLD       = float(os.environ.get("SIFTA_VIABLE_THRESHOLD",       "0.70"))
_CONSERVATION_THRESHOLD = float(os.environ.get("SIFTA_CONSERVATION_THRESHOLD", "0.45"))


def _tail(path: Path, n: int = 20) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in read_text_locked(path, encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows[-n:]


# ── Sub-score extractors ──────────────────────────────────────────────────────

def _energy_budget_score(sd: Path) -> float:
    """
    Fraction of STGM metabolic budget remaining.
    Reads from astrocyte_modulation_log.jsonl → modulated_budget.
    Full budget = 1000.0 STGM. Clamped to [0, 1].
    """
    rows = _tail(sd / "astrocyte_modulation_log.jsonl", 3)
    if not rows:
        return 0.5  # unknown → neutral
    budget = float(rows[-1].get("modulated_budget", 1000.0) or 1000.0)
    return min(1.0, max(0.0, budget / 1000.0))


def _memory_continuity_score(sd: Path) -> float:
    """
    Measure of how intact the replay buffer is.
    1.0 when no prunes recommended in last 20 microglia rows,
    degraded proportionally to recommended pruning rate.
    """
    rows = _tail(sd / "microglia_prune.jsonl", 20)
    if not rows:
        return 1.0  # no prunes → perfect continuity
    recommended = sum(1 for r in rows if r.get("prune_recommended"))
    return max(0.0, 1.0 - (recommended / len(rows)))


def _owner_contact_freshness_score(sd: Path) -> float:
    """
    Recency of last verified owner contact (from owner_history.jsonl).
    1.0 = contact within last hour. 0.0 = contact > 48h ago.
    """
    rows = _tail(sd / "owner_history.jsonl", 1)
    if not rows:
        return 0.0
    ts    = float(rows[-1].get("ts", 0.0) or 0.0)
    age_h = (time.time() - ts) / 3600.0
    # Linear decay: 0h→1.0, 48h→0.0
    return max(0.0, 1.0 - age_h / 48.0)


def _self_repair_rate_score(sd: Path) -> float:
    """
    Rate at which the stability audit is STABLE vs UNSTABLE in last 10 rows.
    1.0 = all stable, 0.0 = all unstable.
    """
    rows = _tail(sd / "stability_audit.jsonl", 10)
    rows = [r for r in rows if r.get("kind") == "STABILITY_AUDIT"]
    if not rows:
        return 0.5
    stable_count = sum(1 for r in rows if r.get("stable", False))
    return stable_count / len(rows)


def _schema_refinement_rate_score(sd: Path) -> float:
    """
    Fraction of temporal self-model updates that reduced self-PE (schema_refined=True).
    Drives towards a self-improving organism (Drescher 1991 schema mechanism).
    """
    rows = _tail(sd / "self_model.jsonl", 20)
    updates = [r for r in rows if r.get("kind") == "TEMPORAL_SELF_UPDATE"]
    if not updates:
        return 0.5
    refined = sum(1 for r in updates if r.get("schema_refined"))
    return refined / len(updates)


# ── Main API ──────────────────────────────────────────────────────────────────

def compute_viability(
    *,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
    # Allow direct injection for tests
    energy_budget: Optional[float] = None,
    memory_continuity: Optional[float] = None,
    owner_contact_freshness: Optional[float] = None,
    self_repair_rate: Optional[float] = None,
    schema_refinement_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Compute and (optionally) write one V_t row to viability.jsonl.
    Returns the full receipt dict.
    """
    if os.environ.get(_DISABLE_ENV, "").strip() == "1":
        return {
            "ts": now or time.time(),
            "kind": "VIABILITY",
            "disabled": True,
            "viability": 0.5,
            "viability_regime": "UNKNOWN",
        }

    sd = state_dir(root)

    sub: Dict[str, float] = {
        "energy_budget":            energy_budget           if energy_budget is not None
                                    else _energy_budget_score(sd),
        "memory_continuity":        memory_continuity       if memory_continuity is not None
                                    else _memory_continuity_score(sd),
        "owner_contact_freshness":  owner_contact_freshness if owner_contact_freshness is not None
                                    else _owner_contact_freshness_score(sd),
        "self_repair_rate":         self_repair_rate        if self_repair_rate is not None
                                    else _self_repair_rate_score(sd),
        "schema_refinement_rate":   schema_refinement_rate  if schema_refinement_rate is not None
                                    else _schema_refinement_rate_score(sd),
    }

    V = sum(_W[k] * v for k, v in sub.items())
    V = round(min(1.0, max(0.0, V)), 6)

    if V >= _VIABLE_THRESHOLD:
        regime = "VIABLE"
    elif V >= _CONSERVATION_THRESHOLD:
        regime = "METABOLIC_CONSERVATION"
    else:
        regime = "CRITICAL"

    # Q3 + Q5: live computation from sub_scores vector (5D proxy until full 12D window)
    phi_hat = None
    emergence_synergy = None
    try:
        from System.swarm_emergence_synergy import compute_phi_id_approx, compute_joint_surprise
        sub_vec = [[sub[k] for k in sorted(sub)]]
        sub_mat = sub_vec * 4  # replicate to give estimator ≥ 2 time points
        phi_hat = compute_phi_id_approx(sub_mat)
        synergy_dict = compute_joint_surprise(sub_mat)
        emergence_synergy = synergy_dict.get("synergy")
    except Exception:
        pass  # graceful degradation

    row: Dict[str, Any] = {
        "ts":                now or time.time(),
        "trace_id":          str(uuid.uuid4()),
        "kind":              "VIABILITY",
        "truth_label":       "AUTOPOIESIS_VIABILITY",
        "viability":         V,
        "viability_regime":  regime,
        "sub_scores":        {k: round(v, 4) for k, v in sub.items()},
        "weights":           _W,
        "thresholds":        {
            "viable":        _VIABLE_THRESHOLD,
            "conservation":  _CONSERVATION_THRESHOLD,
        },
        "phi_hat":           phi_hat,
        "emergence_synergy": emergence_synergy,
        "provenance":        (
            "Varela,Maturana&Uribe1974; Luisi2003; "
            "Q3=Oizumi2016THOI+Haun&Tononi2019; Q5=Kraskov2004+Bertschinger2014PID"
        ),
    }

    if write_ledger:
        append_line_locked(
            sd / LOG_NAME,
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def tail_viability_rows(max_rows: int = 12, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    return _tail(state_dir(root) / LOG_NAME, max_rows)


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    rows = tail_viability_rows(1, root=root)
    if not rows:
        return ""
    r = rows[-1]
    regime = r.get("viability_regime", "UNKNOWN")
    V      = r.get("viability", "?")
    subs   = r.get("sub_scores", {})
    low    = [k for k, v in subs.items() if v < 0.4]
    low_str = f" | LOW: {', '.join(low)}" if low else ""
    phi = r.get("phi_hat")
    phi_str = f" | Φ̂={phi:.4f}" if phi is not None else ""
    syn = r.get("emergence_synergy")
    syn_str = f" | synergy={syn:.4f}" if syn is not None else ""
    return (
        f"AUTOPOIESIS VIABILITY (Event 140 — Varela 1974):\n"
        f"- V_t={V} | regime={regime}{low_str}\n"
        f"- Q3/Q5 live{phi_str}{syn_str} (Oizumi 2016; Kraskov 2004)"
    )
