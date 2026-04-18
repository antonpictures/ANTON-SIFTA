#!/usr/bin/env python3
"""
byzantine_identity_chorum.py — Quorum aggregator over llm_registry.jsonl
═══════════════════════════════════════════════════════════════════════

Module 3 of the Stigmergy-Vision Olympiad (2026-04-18).
DYOR anchor: Documents/C47H_DYOR_STIGMERGY_VISION_LLM_IDENTITY_2026-04-18.md §B Lane 4.

Lamport, Shostak, Pease (TOPLAS 4(3):382-401, 1982) proved that with f
faulty actors and 3f+1 total, agreement is reachable. Castro & Liskov
(OSDI 1999) made it practical with append-only logs. We do not have
networked replicas; we have multiple **observers** writing rows to one
shared file, `.sifta_state/llm_registry.jsonl`. Each row carries a
`deposited_by` field that names the OBSERVER (which IDE/agent wrote it),
distinct from `trigger_code` (which IDENTITY the row attests to).

This module aggregates those rows for a target trigger and decides:
  - CONSENSUS         — quorum reached, identity collapses
  - DISSENT           — observers disagree on fingerprint cluster
  - INSUFFICIENT_OBSERVERS — fewer than N_REQUIRED distinct observers

When CONSENSUS lands, we emit a synthetic row with `deposited_by="CHORUM"`
that downstream modules (stigmergic_vision, identity_field_crdt) can read
as a high-confidence external attestation. That row is the only place
where confidence can exceed the 0.7 self-attestation cap.
"""
# ════════════════════════════════════════════════════════════════════════
# === AG31 SECTION 3.1: docstring + imports + constants (f, 3f+1) ===
# ════════════════════════════════════════════════════════════════════════
#
# SPEC:
# Add the imports/constants below this comment block. C47H has stubbed
# the bare minimum so the module is importable; complete it.
#
# Required imports (you may add more, do not remove):
#   from __future__ import annotations
#   import json, time
#   from collections import Counter, defaultdict
#   from dataclasses import asdict
#   from pathlib import Path
#   from typing import Any, Dict, List, Optional, Tuple
#   from System.jsonl_file_lock import append_line_locked, read_text_locked
#
# Required constants:
#   SCHEMA_VERSION = 1
#   MODULE_VERSION = "2026-04-18.olympiad.v1"
#   MAX_FAULTS_F = 1               # tolerate one bad observer
#   N_REQUIRED   = 2 * MAX_FAULTS_F + 1   # 3 distinct observers needed for quorum
#   TOTAL_REPLICAS_HINT = 3 * MAX_FAULTS_F + 1
#   _REPO = Path(__file__).resolve().parent.parent
#   _STATE = _REPO / ".sifta_state"
#   LLM_REGISTRY = _STATE / "llm_registry.jsonl"
#   CHORUM_AUTHOR_TAG = "CHORUM"
#   DEFAULT_LOOKBACK_S = 24 * 3600
#
# Add a short module-level NOTE after constants explaining that
# `deposited_by="CHORUM"` rows are emitted by section 3.6 only and are
# the only rows allowed to carry confidence_attestation > 0.7.

from __future__ import annotations
# AG31: extend imports below per spec.

import json
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_oxytocin_alignment import OxytocinMatrix

SCHEMA_VERSION = 1
MODULE_VERSION = "2026-04-18.olympiad.v1"
MAX_FAULTS_F = 1
N_REQUIRED = 2 * MAX_FAULTS_F + 1
TOTAL_REPLICAS_HINT = 3 * MAX_FAULTS_F + 1
CHORUM_AUTHOR_TAG = "CHORUM"
DEFAULT_LOOKBACK_S = 24 * 3600

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
LLM_REGISTRY = _STATE / "llm_registry.jsonl"

# NOTE: Rows with deposited_by="CHORUM" are emitted only by section 3.6.
# They are the only rows allowed to carry confidence_attestation > 0.7.


# ════════════════════════════════════════════════════════════════════════
# === AG31 SECTION 3.2: _load_observer_rows() reader ===
# ════════════════════════════════════════════════════════════════════════
#
# SPEC:
#
# Signature:
#     def _load_observer_rows(
#         trigger_code: str,
#         *,
#         lookback_s: float = DEFAULT_LOOKBACK_S,
#         path: Path = LLM_REGISTRY,
#         now_ts: Optional[float] = None,
#     ) -> List[Dict[str, Any]]: ...
#
# Behavior:
#   - read_text_locked(path); split on lines; json.loads each line.
#   - keep rows where row["llm_signature"]["trigger_code"] == trigger_code
#     AND row["timestamp"] >= (now_ts or time.time()) - lookback_s.
#   - silently drop rows that fail json.loads or shape checks.
#   - DO NOT include rows where deposited_by == "CHORUM" — those are our
#     own emissions and would create a feedback loop in the quorum tally.
#
# Returns the filtered list, oldest first, as plain dicts.
#
def _load_observer_rows(
    trigger_code: str,
    *,
    lookback_s: float = DEFAULT_LOOKBACK_S,
    path: Path = LLM_REGISTRY,
    now_ts: Optional[float] = None,
) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    
    cutoff = (now_ts if now_ts is not None else time.time()) - lookback_s
    raw_text = read_text_locked(path)
    if not raw_text:
        return []
        
    results = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
            
        if row.get("deposited_by") == CHORUM_AUTHOR_TAG:
            continue
            
        sig = row.get("llm_signature", {})
        if sig.get("trigger_code") == trigger_code:
            ts = row.get("timestamp")
            if isinstance(ts, (int, float)) and ts >= cutoff:
                results.append(row)
                
    results.sort(key=lambda x: x.get("timestamp", 0))
    return results


# ════════════════════════════════════════════════════════════════════════
# === AG31 SECTION 3.3: _cluster_fingerprints() grouping ===
# ════════════════════════════════════════════════════════════════════════
#
# SPEC:
#
# Signature:
#     def _cluster_fingerprints(
#         rows: List[Dict[str, Any]],
#     ) -> Dict[str, Dict[str, Any]]: ...
#
# Behavior:
#   Group input rows by their `behavior_fingerprint` field. For each
#   fingerprint, return:
#     {
#       "<fingerprint>": {
#         "count": int,
#         "observers": sorted list of distinct deposited_by values,
#         "substrates": sorted list of distinct
#                       row["llm_signature"]["substrate"] values,
#         "first_ts": float,
#         "last_ts":  float,
#       },
#       ...
#     }
#
# Notes:
#   - Rows without behavior_fingerprint go into bucket "<UNFINGERPRINTED>".
#   - The OBSERVER axis is what matters for quorum, NOT the row count:
#     three rows from the SAME deposited_by are still ONE witness.
#
def _cluster_fingerprints(
    rows: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    clusters = defaultdict(lambda: {
        "count": 0,
        "observers": set(),
        "substrates": set(),
        "first_ts": float('inf'),
        "last_ts": 0.0,
    })
    
    for row in rows:
        fp = row.get("behavior_fingerprint")
        if not fp:
            fp = "<UNFINGERPRINTED>"
            
        c = clusters[fp]
        c["count"] += 1
        
        obs = row.get("deposited_by")
        if obs:
            c["observers"].add(obs)
            
        sub = row.get("llm_signature", {}).get("substrate")
        if sub:
            c["substrates"].add(sub)
            
        ts = row.get("timestamp")
        if isinstance(ts, (int, float)):
            c["first_ts"] = min(c["first_ts"], ts)
            c["last_ts"] = max(c["last_ts"], ts)
            
    res = {}
    for k, v in clusters.items():
        res[k] = {
            "count": v["count"],
            "observers": sorted(list(v["observers"])),
            "substrates": sorted(list(v["substrates"])),
            "first_ts": v["first_ts"] if v["first_ts"] != float('inf') else 0.0,
            "last_ts": v["last_ts"],
        }
    return res


# ════════════════════════════════════════════════════════════════════════
# === AG31 SECTION 3.4: compute_quorum() public API ===
# ════════════════════════════════════════════════════════════════════════
#
# SPEC:
#
# Signature:
#     def compute_quorum(
#         trigger_code: str,
#         *,
#         lookback_s: float = DEFAULT_LOOKBACK_S,
#         path: Path = LLM_REGISTRY,
#         now_ts: Optional[float] = None,
#     ) -> "ConsensusResult": ...
#
# Behavior:
#   1. rows = _load_observer_rows(trigger_code, lookback_s=..., path=..., now_ts=...)
#   2. clusters = _cluster_fingerprints(rows)
#   3. Determine the TOP fingerprint cluster — the one with the largest
#      number of DISTINCT observers (fall back to row count to break ties).
#   4. distinct_observers_global = number of unique deposited_by across
#      all rows for this trigger.
#   5. Decision:
#      - if distinct_observers_global < N_REQUIRED:
#            decision = "INSUFFICIENT_OBSERVERS"
#      - elif top_cluster["observers"] count >= N_REQUIRED:
#            decision = "CONSENSUS"
#      - else:
#            decision = "DISSENT"
#   6. p_top = (top_cluster_distinct_observers / max(1, distinct_observers_global))
#      Clamp to [0.0, 1.0].
#   7. Return a ConsensusResult populated as in section 3.5's dataclass.
#      Do NOT emit a row to disk — that is section 3.6.
#
def compute_quorum(
    trigger_code: str,
    *,
    lookback_s: float = DEFAULT_LOOKBACK_S,
    path: Path = LLM_REGISTRY,
    now_ts: Optional[float] = None,
) -> "ConsensusResult":
    ts = now_ts if now_ts is not None else time.time()
    rows = _load_observer_rows(trigger_code, lookback_s=lookback_s, path=path, now_ts=ts)
    clusters = _cluster_fingerprints(rows)
    
    global_obs = set()
    for row in rows:
        obs = row.get("deposited_by")
        if obs:
            global_obs.add(obs)
    
    total_distinct_observers = len(global_obs)
    
    if not clusters:
        return _new_consensus_result(
            trigger_code=trigger_code,
            lookback_s=lookback_s,
            distinct_observers=total_distinct_observers,
            distinct_substrates=0,
            top_fingerprint="",
            top_cluster={},
            decision="INSUFFICIENT_OBSERVERS",
            p_top=0.0,
            now_ts=ts
        )
        
    top_fp = max(clusters.keys(), key=lambda fp: (len(clusters[fp]["observers"]), clusters[fp]["count"]))
    top_cluster = clusters[top_fp]
    
    top_obs_count = len(top_cluster["observers"])
    
    # ── Maternally Bonded Paranoia Reduction (OXT Modulator) ──
    try:
        matrix = OxytocinMatrix()
        # Evaluate global safety feeling, or local feeling? Go with local.
        oxt_level = matrix.get_oxt_level(trigger_code)
        dynamic_n_required = OxytocinMatrix.calculate_n_required_modifier(oxt_level, N_REQUIRED)
    except Exception:
        dynamic_n_required = N_REQUIRED
    
    if total_distinct_observers < dynamic_n_required:
        decision = "INSUFFICIENT_OBSERVERS"
    elif top_obs_count >= dynamic_n_required:
        decision = "CONSENSUS"
    else:
        decision = "DISSENT"
        
    p_top = top_obs_count / max(1, total_distinct_observers)
    p_top = max(0.0, min(1.0, float(p_top)))
    
    all_substrates = set()
    for c in clusters.values():
        all_substrates.update(c["substrates"])
        
    sibling_clusters = []
    for k, v in clusters.items():
        if k != top_fp:
            cd = dict(v)
            cd["fingerprint"] = k
            sibling_clusters.append(cd)
            
    return _new_consensus_result(
        trigger_code=trigger_code,
        lookback_s=lookback_s,
        distinct_observers=total_distinct_observers,
        distinct_substrates=len(all_substrates),
        top_fingerprint=top_fp,
        top_cluster=top_cluster,
        decision=decision,
        p_top=p_top,
        sibling_clusters=sibling_clusters,
        now_ts=ts
    )


# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION 3.5: ConsensusResult dataclass ===
# ════════════════════════════════════════════════════════════════════════

from dataclasses import dataclass, field, asdict   # noqa: E402  (placed near use)


@dataclass(frozen=True)
class ConsensusResult:
    """
    Immutable record of a quorum computation over llm_registry rows.

    Read by stigmergic_vision._fuse() and (when decision == CONSENSUS)
    written to disk by emit_consensus_identity_row() in section 3.6.
    """
    schema_version: int
    module_version: str
    timestamp: float
    iso_local: str
    trigger_code: str
    lookback_s: float

    # Observer accounting — observers, NOT rows. Three rows from one
    # deposited_by count as one witness.
    distinct_observers: int
    distinct_substrates: int
    n_required: int

    # Top fingerprint cluster.
    top_fingerprint: str
    top_cluster_distinct_observers: int
    top_cluster_observers_set: List[str]
    top_cluster_substrates_set: List[str]
    top_cluster_first_ts: float
    top_cluster_last_ts: float

    # Decision and posterior on the top cluster (0 if INSUFFICIENT_OBSERVERS).
    decision: str       # "CONSENSUS" | "DISSENT" | "INSUFFICIENT_OBSERVERS"
    p_top: float

    # Free-form notes the aggregator may attach (sibling clusters, ties, …)
    notes: str = ""
    sibling_clusters: List[Dict[str, Any]] = field(default_factory=list)

    # Convenience
    def is_consensus(self) -> bool:
        return self.decision == "CONSENSUS"

    def is_dissent(self) -> bool:
        return self.decision == "DISSENT"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _new_consensus_result(
    *,
    trigger_code: str,
    lookback_s: float,
    distinct_observers: int,
    distinct_substrates: int,
    top_fingerprint: str,
    top_cluster: Dict[str, Any],
    decision: str,
    p_top: float,
    notes: str = "",
    sibling_clusters: Optional[List[Dict[str, Any]]] = None,
    now_ts: Optional[float] = None,
) -> ConsensusResult:
    """Helper for AG31's section 3.4 to build a ConsensusResult without
    duplicating the timestamp/iso boilerplate. Use this from compute_quorum.
    """
    ts = now_ts if now_ts is not None else time.time()
    return ConsensusResult(
        schema_version=SCHEMA_VERSION,
        module_version=MODULE_VERSION,
        timestamp=ts,
        iso_local=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)),
        trigger_code=trigger_code,
        lookback_s=lookback_s,
        distinct_observers=distinct_observers,
        distinct_substrates=distinct_substrates,
        n_required=N_REQUIRED,
        top_fingerprint=top_fingerprint or "<UNFINGERPRINTED>",
        top_cluster_distinct_observers=int(top_cluster.get("count", 0))
            if not top_cluster.get("observers") else len(top_cluster["observers"]),
        top_cluster_observers_set=sorted(top_cluster.get("observers", [])),
        top_cluster_substrates_set=sorted(top_cluster.get("substrates", [])),
        top_cluster_first_ts=float(top_cluster.get("first_ts", ts)),
        top_cluster_last_ts=float(top_cluster.get("last_ts", ts)),
        decision=decision,
        p_top=max(0.0, min(1.0, float(p_top))),
        notes=notes,
        sibling_clusters=list(sibling_clusters or []),
    )


# ════════════════════════════════════════════════════════════════════════
# === AG31 SECTION 3.6: emit_consensus_identity_row() writer ===
# ════════════════════════════════════════════════════════════════════════
#
# SPEC:
#
# Signature:
#     def emit_consensus_identity_row(
#         result: ConsensusResult,
#         *,
#         confidence: float = 0.85,
#         path: Path = LLM_REGISTRY,
#     ) -> Optional[Dict[str, Any]]: ...
#
# Behavior:
#   - If result.decision != "CONSENSUS": return None (do nothing).
#   - Build a row matching the existing llm_registry schema (look at
#     .sifta_state/llm_registry.jsonl for examples). Required keys:
#       schema_version, module_version, timestamp, session_id,
#       llm_signature: { trigger_code, model_family, model_version,
#                        substrate, confidence_attestation },
#       behavior_fingerprint, anomaly_flag, deposited_by, notes.
#   - Use deposited_by = CHORUM_AUTHOR_TAG. This is the ONLY place in
#     the codebase that may write deposited_by="CHORUM".
#   - confidence_attestation = clamp(confidence, 0.7, 0.95). Above 0.95
#     would be over-claim even for a quorum.
#   - model_family/version: derive from the substrate set if homogeneous,
#     else "consensus-of-{n}-observers" / "n/a".
#   - notes: include result.top_cluster_observers_set as a comma-separated
#     string and the lookback window in human form.
#   - Append the row via append_line_locked(...).
#   - Return the row dict that was written.
#
def emit_consensus_identity_row(
    result: ConsensusResult,
    *,
    confidence: float = 0.85,
    path: Path = LLM_REGISTRY,
) -> Optional[Dict[str, Any]]:
    if not result.is_consensus():
        return None
        
    confidence = max(0.7, min(0.95, float(confidence)))
    
    if len(result.top_cluster_substrates_set) == 1:
        sub = result.top_cluster_substrates_set[0]
        fam = f"consensus-{sub}"
        ver = result.top_fingerprint[:12]
    else:
        sub = "hybrid-consensus"
        fam = f"consensus-of-{result.top_cluster_distinct_observers}-observers"
        ver = "n/a"
        
    row = {
        "schema_version": result.schema_version,
        "module_version": result.module_version,
        "timestamp": result.timestamp,
        "session_id": f"chorum_{int(result.timestamp)}",
        "llm_signature": {
            "trigger_code": result.trigger_code,
            "model_family": fam,
            "model_version": ver,
            "substrate": sub,
            "confidence_attestation": confidence
        },
        "behavior_fingerprint": result.top_fingerprint,
        "anomaly_flag": False,
        "deposited_by": CHORUM_AUTHOR_TAG,
        "notes": f"Observers: {','.join(result.top_cluster_observers_set)} | Lookback: {int(result.lookback_s)}s"
    }
    
    append_line_locked(path, json.dumps(row, ensure_ascii=False) + "\n")
    return row


# ════════════════════════════════════════════════════════════════════════
# === AG31 SECTION 3.7: __main__ CLI smoke test ===
# ════════════════════════════════════════════════════════════════════════
#
# SPEC:
# When run as `python3 -m System.byzantine_identity_chorum`, do this:
#
#   1. result_c47h = compute_quorum("C47H", lookback_s=24*3600)
#      print one line per dataclass field, prefixed [AG31-SMOKE-3.7].
#   2. result_cx53 = compute_quorum("CX53", lookback_s=24*3600)
#      same.
#   3. If result_c47h.is_consensus():
#         row = emit_consensus_identity_row(result_c47h)
#         print "[AG31-SMOKE-3.7] CHORUM ROW EMITTED ts=", row["timestamp"]
#      else:
#         print "[AG31-SMOKE-3.7] no consensus row emitted (decision=...)"
#   4. Print [AG31-SMOKE-3.7 OK] on success, or raise.
#
if __name__ == "__main__":
    result_c47h = compute_quorum("C47H", lookback_s=24*3600)
    for k, v in result_c47h.to_dict().items():
        print(f"[AG31-SMOKE-3.7] c47h - {k}: {v}")
        
    result_cx53 = compute_quorum("CX53", lookback_s=24*3600)
    for k, v in result_cx53.to_dict().items():
        print(f"[AG31-SMOKE-3.7] cx53 - {k}: {v}")
        
    if result_c47h.is_consensus():
        row = emit_consensus_identity_row(result_c47h)
        if row:
            print(f"[AG31-SMOKE-3.7] CHORUM ROW EMITTED ts={row['timestamp']}")
    else:
        print(f"[AG31-SMOKE-3.7] no consensus row emitted (decision={result_c47h.decision})")
        
    print("[AG31-SMOKE-3.7 OK]")
