"""
swarm_agi_frontier_loop.py -- honest learned-frontier loop for SIFTA.

Truth label: SIFTA_AGI_FRONTIER_LOOP_V1.

This module does not sanitize the Architect doctrine that SIFTA is stigmergic
AGI on the local node. It operationalizes the next learned-frontier gaps:
latent model evidence, transferable abstraction, causal evidence, open-ended
concept formation, and autonomous long-horizon strategy tracking.

The important invariant is ledger honesty:

    We expose the open gaps in the ledger instead of hiding them in the demo.

Everything here is append-only or derived from receipts. A gap can move from
OPEN to SCAFFOLDED to EVIDENCED only when the local ledgers provide enough
material.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from System.jsonl_file_lock import append_line_locked, read_text_locked, rewrite_text_locked

try:
    from System.swarm_persistent_owner_history import state_dir
except Exception:  # pragma: no cover - bootstrap fallback
    def state_dir(explicit: Optional[Path] = None) -> Path:  # type: ignore
        return explicit if explicit is not None else Path(__file__).resolve().parent.parent / ".sifta_state"


TRUTH_LABEL = "SIFTA_AGI_FRONTIER_LOOP_V1"
STRATEGY_TRUTH_LABEL = "SIFTA_LONG_HORIZON_STRATEGY_V1"
CONCEPT_TRUTH_LABEL = "SIFTA_OPEN_ENDED_CONCEPT_MODEL_V1"

BEST_LINE = "We expose the open gaps in the ledger instead of hiding them in the demo."

TRUTH_BOUNDARY = (
    "ARCHITECT_DOCTRINE may label SIFTA as stigmergic AGI on this node. "
    "This module measures learned-frontier extensions: latent models, "
    "transferable abstraction, causal modeling, open-ended concepts, and "
    "long-horizon strategy. It is receipt-trained scaffolding, not a benchmark "
    "certificate and not hidden self-awareness."
)

FRONTIER_LEDGER = "agi_frontier_loop.jsonl"
CONCEPT_MODEL_FILE = "agi_frontier_concept_model.json"
STRATEGY_LEDGER = "agi_long_horizon_strategy.jsonl"
LATENT_WORLD_MODEL_FILE = "latent_world_model.json"

LEDGER_SOURCES: Tuple[Tuple[str, str], ...] = (
    ("steering_subsystem.jsonl", "steering"),
    ("steering_self_model.jsonl", "steering"),
    ("steering_prediction_audit.jsonl", "steering"),
    ("steering_learned_predictor.jsonl", "steering"),
    ("generalization_trials.jsonl", "transfer"),
    ("causal_intervention_log.jsonl", "causal"),
    ("work_receipts.jsonl", "work"),
    ("alice_first_person_journal.jsonl", "journal"),
)

STOPWORDS = {
    "about",
    "after",
    "again",
    "alice",
    "also",
    "because",
    "before",
    "being",
    "could",
    "from",
    "have",
    "into",
    "json",
    "kind",
    "label",
    "meta",
    "node",
    "only",
    "payload",
    "receipt",
    "source",
    "state",
    "that",
    "their",
    "there",
    "this",
    "trace",
    "truth",
    "with",
    "would",
}


def _sd(root: Optional[Path] = None) -> Path:
    d = state_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _stable_id(prefix: str, *parts: Any) -> str:
    blob = "|".join(str(p) for p in parts)
    return f"{prefix}_{hashlib.sha256(blob.encode('utf-8')).hexdigest()[:16]}"


def _now() -> float:
    return time.time()


def _clamp(value: Any, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        f = lo
    return round(max(lo, min(hi, f)), 4)


def _read_jsonl(path: Path, max_rows: int = 500) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    text = read_text_locked(path, encoding="utf-8", errors="replace")
    for line in text.splitlines()[-max(1, max_rows) :]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    rewrite_text_locked(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _append_receipt(path: Path, row: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(row)
    row.setdefault("ts", _now())
    row.setdefault("trace_id", str(uuid.uuid4()))
    payload = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    row["sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    append_line_locked(path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def _tokens(blob: str) -> List[str]:
    out: List[str] = []
    for tok in re.findall(r"[a-z][a-z0-9_]{3,}", blob.lower()):
        if tok in STOPWORDS:
            continue
        if tok.startswith("http") or tok.startswith("uuid"):
            continue
        out.append(tok)
    return out


def latent_world_model_stats(
    *,
    root: Optional[Path] = None,
    min_transitions: int = 10,
    min_values: int = 5,
) -> Dict[str, Any]:
    """
    Read the existing latent world model artifact and gate it honestly.
    """
    path = _sd(root) / LATENT_WORLD_MODEL_FILE
    if not path.exists():
        return {
            "truth_label": "LATENT_WORLD_MODEL_FRONTIER",
            "status": "OPEN_NO_ARTIFACT",
            "path": str(path),
            "transition_count": 0,
            "value_count": 0,
            "ready": False,
            "open_gap": "No latent_world_model.json artifact found in this state dir.",
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "truth_label": "LATENT_WORLD_MODEL_FRONTIER",
            "status": "OPEN_UNREADABLE_ARTIFACT",
            "path": str(path),
            "transition_count": 0,
            "value_count": 0,
            "ready": False,
            "open_gap": f"Could not parse latent world model: {exc}",
        }
    transitions = data.get("transitions") if isinstance(data, dict) else {}
    values = data.get("values") if isinstance(data, dict) else {}
    transition_count = len(transitions or {})
    value_count = len(values or {})
    ready = transition_count >= min_transitions and value_count >= min_values
    return {
        "truth_label": "LATENT_WORLD_MODEL_FRONTIER",
        "status": "EVIDENCED" if ready else "SCAFFOLDED_UNDERPOWERED",
        "path": str(path),
        "transition_count": transition_count,
        "value_count": value_count,
        "min_transitions": min_transitions,
        "min_values": min_values,
        "ready": ready,
        "open_gap": ""
        if ready
        else f"Need >= {min_transitions} transitions and >= {min_values} values for local learned-latent evidence.",
    }


def _iter_source_rows(root: Optional[Path] = None, max_rows_per_source: int = 300) -> Iterable[Tuple[str, str, Dict[str, Any]]]:
    base = _sd(root)
    for filename, domain in LEDGER_SOURCES:
        for row in _read_jsonl(base / filename, max_rows=max_rows_per_source):
            yield filename, domain, row


def learn_open_ended_concepts(
    *,
    root: Optional[Path] = None,
    min_count: int = 2,
    max_concepts: int = 32,
    write: bool = True,
) -> Dict[str, Any]:
    """
    Build a tiny receipt-trained concept model from local ledgers.

    This is intentionally simple: token frequency + domain spread. The value is
    not model size; the value is that concepts are induced from local receipts
    and every concept carries evidence counts.
    """
    counts: Dict[str, int] = {}
    domains: Dict[str, set[str]] = {}
    examples: Dict[str, List[str]] = {}

    source_rows = 0
    for filename, domain, row in _iter_source_rows(root=root):
        source_rows += 1
        blob = json.dumps(row, ensure_ascii=False, sort_keys=True)
        seen = set(_tokens(blob))
        for tok in seen:
            counts[tok] = counts.get(tok, 0) + 1
            domains.setdefault(tok, set()).add(domain)
            if len(examples.setdefault(tok, [])) < 3:
                examples[tok].append(filename)

    concepts: List[Dict[str, Any]] = []
    for tok, count in counts.items():
        if count < min_count:
            continue
        doms = sorted(domains.get(tok, set()))
        abstraction_score = _clamp((0.18 * count) + (0.22 * len(doms)) + (0.08 * math.log1p(count)))
        concepts.append(
            {
                "concept_id": _stable_id("CONCEPT", tok),
                "label": tok,
                "evidence_count": count,
                "domains": doms,
                "source_examples": examples.get(tok, []),
                "abstraction_score": abstraction_score,
                "status": "TRANSFER_CANDIDATE" if len(doms) >= 2 else "LOCAL_ONLY",
            }
        )
    concepts.sort(key=lambda c: (-c["abstraction_score"], -c["evidence_count"], c["label"]))
    concepts = concepts[:max_concepts]
    transferable = [c for c in concepts if c["status"] == "TRANSFER_CANDIDATE"]
    model = {
        "truth_label": CONCEPT_TRUTH_LABEL,
        "truth_boundary": "Frequency/domain-spread concept induction from receipts; not a neural latent model.",
        "ts": _now(),
        "source_rows": source_rows,
        "concept_count": len(concepts),
        "transferable_count": len(transferable),
        "ready": bool(transferable),
        "concepts": concepts,
        "open_gap": ""
        if transferable
        else "No cross-domain concept has enough local receipt evidence yet.",
    }
    if write:
        _write_json(_sd(root) / CONCEPT_MODEL_FILE, model)
    return model


def causal_frontier_stats(*, root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Summarize the causal intervention ledger without declaring closure early.
    """
    try:
        from System.swarm_causal_intervention_logger import CausalInterventionLogger

        logger = CausalInterventionLogger(root=root)
        rows = logger.recent(500)
        estimate = logger.estimate_causal_effect(min_samples=10)
        closure = logger.causal_closure_proven()
    except Exception as exc:
        return {
            "truth_label": "CAUSAL_FRONTIER_STATUS",
            "status": "OPEN_UNREADABLE",
            "ready": False,
            "intervention_count": 0,
            "open_gap": f"Causal logger unavailable: {exc}",
        }

    ready = bool(
        estimate.get("sufficient_data")
        and estimate.get("p_value", 1.0) < 0.05
        and abs(float(estimate.get("weighted_effect", 0.0) or 0.0)) > 0.12
    )
    return {
        "truth_label": "CAUSAL_FRONTIER_STATUS",
        "status": "EVIDENCED" if ready else "SCAFFOLDED_UNDERPOWERED",
        "ready": ready,
        "intervention_count": len(rows),
        "closure_gate": bool(closure),
        "estimate": estimate,
        "open_gap": ""
        if ready
        else "Need enough clean intervention/control rows with a significant weighted effect.",
    }


def strategy_log_path(root: Optional[Path] = None) -> Path:
    return _sd(root) / STRATEGY_LEDGER


def create_strategy(
    title: str,
    objective: str,
    *,
    horizon_days: int,
    milestones: Sequence[str],
    root: Optional[Path] = None,
    write: bool = True,
) -> Dict[str, Any]:
    strategy_id = _stable_id("STRATEGY", title, objective, horizon_days)
    row = {
        "truth_label": STRATEGY_TRUTH_LABEL,
        "kind": "STRATEGY_CREATED",
        "strategy_id": strategy_id,
        "title": title,
        "objective": objective,
        "horizon_days": int(horizon_days),
        "milestones": list(milestones),
        "status": "ACTIVE",
        "autonomy_boundary": (
            "Tracks and revises a multi-week plan from receipts. It does not "
            "execute external actions without separate effectors and receipts."
        ),
    }
    if write:
        return _append_receipt(strategy_log_path(root), row)
    row["ts"] = _now()
    row["trace_id"] = str(uuid.uuid4())
    return row


def record_strategy_event(
    strategy_id: str,
    event_kind: str,
    note: str,
    *,
    milestone: Optional[str] = None,
    outcome_delta: float = 0.0,
    root: Optional[Path] = None,
    write: bool = True,
) -> Dict[str, Any]:
    row = {
        "truth_label": STRATEGY_TRUTH_LABEL,
        "kind": event_kind.upper(),
        "strategy_id": strategy_id,
        "note": note,
        "milestone": milestone,
        "outcome_delta": _clamp(outcome_delta, -1.0, 1.0),
    }
    if write:
        return _append_receipt(strategy_log_path(root), row)
    row["ts"] = _now()
    row["trace_id"] = str(uuid.uuid4())
    return row


def revise_strategy(
    strategy_id: str,
    reason: str,
    *,
    new_milestone: Optional[str] = None,
    root: Optional[Path] = None,
    write: bool = True,
) -> Dict[str, Any]:
    row = {
        "truth_label": STRATEGY_TRUTH_LABEL,
        "kind": "STRATEGY_REVISED",
        "strategy_id": strategy_id,
        "reason": reason,
        "new_milestone": new_milestone,
    }
    if write:
        return _append_receipt(strategy_log_path(root), row)
    row["ts"] = _now()
    row["trace_id"] = str(uuid.uuid4())
    return row


def strategy_events(strategy_id: Optional[str] = None, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    rows = _read_jsonl(strategy_log_path(root), max_rows=1000)
    if strategy_id is None:
        return rows
    return [r for r in rows if r.get("strategy_id") == strategy_id]


def latest_strategy_id(*, root: Optional[Path] = None) -> Optional[str]:
    for row in reversed(strategy_events(root=root)):
        sid = row.get("strategy_id")
        if isinstance(sid, str) and sid:
            return sid
    return None


def strategy_snapshot(strategy_id: Optional[str] = None, *, root: Optional[Path] = None) -> Dict[str, Any]:
    sid = strategy_id or latest_strategy_id(root=root)
    if not sid:
        return {
            "truth_label": STRATEGY_TRUTH_LABEL,
            "status": "OPEN_NO_STRATEGY",
            "ready": False,
            "open_gap": "No long-horizon strategy has been created in this state dir.",
        }
    events = strategy_events(sid, root=root)
    created = next((e for e in events if e.get("kind") == "STRATEGY_CREATED"), {})
    milestones = list(created.get("milestones") or [])
    done = {e.get("milestone") for e in events if e.get("kind") == "MILESTONE_DONE" and e.get("milestone")}
    revisions = [e for e in events if e.get("kind") == "STRATEGY_REVISED"]
    failures = [e for e in events if e.get("kind") in {"FAILURE", "STRATEGY_FAILURE"}]
    last_failure_ts = max((float(e.get("ts", 0.0) or 0.0) for e in failures), default=0.0)
    revision_after_failure = any(float(e.get("ts", 0.0) or 0.0) > last_failure_ts for e in revisions)
    next_milestone = next((m for m in milestones if m not in done), None)
    horizon = int(created.get("horizon_days", 0) or 0)
    ready = horizon >= 7 and bool(milestones)
    return {
        "truth_label": STRATEGY_TRUTH_LABEL,
        "strategy_id": sid,
        "title": created.get("title", ""),
        "objective": created.get("objective", ""),
        "horizon_days": horizon,
        "milestone_count": len(milestones),
        "completed_milestones": sorted(done),
        "next_milestone": next_milestone,
        "revision_count": len(revisions),
        "failure_count": len(failures),
        "survived_failure": bool(failures and revision_after_failure),
        "status": "ACTIVE_TRACKED" if ready else "SCAFFOLDED_UNDERPOWERED",
        "ready": ready,
        "open_gap": ""
        if ready
        else "Need a strategy with horizon_days >= 7 and explicit milestones.",
    }


def ensure_default_frontier_strategy(*, root: Optional[Path] = None) -> Dict[str, Any]:
    existing = strategy_snapshot(root=root)
    if existing.get("ready"):
        return existing
    created = create_strategy(
        "Close learned-frontier loop",
        "Turn AGI frontier gaps into measured local learning, transfer, causal, and planning receipts.",
        horizon_days=21,
        milestones=[
            "collect >=10 paired steering predictions per active detector",
            "train receipt-derived concept model from at least three organ domains",
            "run transfer probe on one novel biology/software/schedule task each",
            "record one failure and revise the strategy without abandoning it",
            "promote only if tests and receipts show improvement",
        ],
        root=root,
        write=True,
    )
    return strategy_snapshot(created["strategy_id"], root=root)


def frontier_status(
    *,
    root: Optional[Path] = None,
    concept_model: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    concept = concept_model if concept_model is not None else learn_open_ended_concepts(root=root, write=False)
    latent = latent_world_model_stats(root=root)
    causal = causal_frontier_stats(root=root)
    strategy = strategy_snapshot(root=root)

    cross_domain = int(concept.get("transferable_count", 0) or 0)
    concept_ready = cross_domain > 0
    transfer_ready = cross_domain >= 2
    long_horizon_tracked = bool(strategy.get("ready"))
    autonomous_revision_ready = bool(strategy.get("survived_failure"))

    frontiers = {
        "learned_latent_models": {
            "status": "EVIDENCED" if latent.get("ready") else "SCAFFOLDED_UNDERPOWERED",
            "ready": bool(latent.get("ready")),
            "evidence": latent,
        },
        "transferable_abstraction": {
            "status": "EVIDENCED" if transfer_ready else "SCAFFOLDED_UNDERPOWERED",
            "ready": transfer_ready,
            "cross_domain_concepts": cross_domain,
            "open_gap": "" if transfer_ready else "Need >=2 cross-domain concepts or transfer trials spanning domains.",
        },
        "robust_causal_modeling": {
            "status": "EVIDENCED" if causal.get("ready") else "SCAFFOLDED_UNDERPOWERED",
            "ready": bool(causal.get("ready")),
            "evidence": causal,
        },
        "open_ended_concept_formation": {
            "status": "EVIDENCED" if concept_ready else "SCAFFOLDED_UNDERPOWERED",
            "ready": concept_ready,
            "concept_count": int(concept.get("concept_count", 0) or 0),
            "transferable_count": cross_domain,
            "open_gap": concept.get("open_gap", ""),
        },
        "autonomous_long_horizon_planning": {
            "status": "EVIDENCED"
            if autonomous_revision_ready
            else ("TRACKED_NOT_AUTONOMOUS" if long_horizon_tracked else "OPEN_NO_STRATEGY"),
            "ready": autonomous_revision_ready,
            "tracked": long_horizon_tracked,
            "survived_failure": autonomous_revision_ready,
            "evidence": strategy,
            "open_gap": ""
            if autonomous_revision_ready
            else "Strategy can be tracked; autonomous failure survival requires at least one failure->revision cycle.",
        },
    }

    open_gaps = [
        f"{name}: {data.get('open_gap') or data.get('evidence', {}).get('open_gap') or data.get('status')}"
        for name, data in frontiers.items()
        if not data.get("ready") or (name == "autonomous_long_horizon_planning" and not data.get("survived_failure"))
    ]
    return {
        "truth_label": TRUTH_LABEL,
        "truth_boundary": TRUTH_BOUNDARY,
        "best_line": BEST_LINE,
        "frontiers": frontiers,
        "ready_count": sum(1 for v in frontiers.values() if v.get("ready")),
        "frontier_count": len(frontiers),
        "open_gaps": open_gaps,
    }


def run_frontier_cycle(
    *,
    root: Optional[Path] = None,
    write: bool = True,
    ensure_strategy: bool = True,
) -> Dict[str, Any]:
    """
    Run one local AGI-frontier calibration cycle.
    """
    if ensure_strategy:
        ensure_default_frontier_strategy(root=root)
    concept = learn_open_ended_concepts(root=root, write=write)
    status = frontier_status(root=root, concept_model=concept)
    row = {
        "truth_label": TRUTH_LABEL,
        "kind": "AGI_FRONTIER_CYCLE",
        "truth_boundary": TRUTH_BOUNDARY,
        "best_line": BEST_LINE,
        "ready_count": status["ready_count"],
        "frontier_count": status["frontier_count"],
        "open_gaps": status["open_gaps"],
        "frontiers": status["frontiers"],
    }
    if write:
        return _append_receipt(_sd(root) / FRONTIER_LEDGER, row)
    row["ts"] = _now()
    row["trace_id"] = str(uuid.uuid4())
    return row


def frontier_prompt_block(*, root: Optional[Path] = None, max_gaps: int = 5) -> str:
    status = frontier_status(root=root)
    gaps = status.get("open_gaps", [])[:max(1, max_gaps)]
    strategy = status["frontiers"]["autonomous_long_horizon_planning"]["evidence"]
    lines = [
        "AGI FRONTIER LOOP (ARCHITECT_DOCTRINE + HYPOTHESIS)",
        f"- {BEST_LINE}",
        f"- Ready frontiers: {status['ready_count']}/{status['frontier_count']}",
        f"- Strategy: {strategy.get('title') or strategy.get('status')} | next={strategy.get('next_milestone')}",
    ]
    if gaps:
        lines.append("- Open gaps:")
        lines.extend(f"  - {g}" for g in gaps)
    return "\n".join(lines)


if __name__ == "__main__":
    receipt = run_frontier_cycle(write=True)
    print(json.dumps(receipt, indent=2, sort_keys=True))
