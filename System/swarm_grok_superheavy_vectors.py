#!/usr/bin/env python3
"""swarm_grok_superheavy_vectors.py - codify GrokCLI's 2026-05-15 vectors.

Truth label: ``SIFTA_GROK_SUPERHEAVY_VECTOR_ORGAN_V1``.

GrokCLI's fresh survey is useful peer input, but a peer report is not a
runtime fact. This organ turns the ten adoption vectors into small,
deterministic probes that other organs can reuse without importing hype:

1. truth-residue gate
2. wit/curiosity fitness
3. discovery-agenda scaffold
4. electricity-accounting placeholder
5. field topology + Lyapunov delta
6. oracle/session hygiene
7. alive-evidence prompt line
8. threat-model hooks
9. owner-care surface
10. inference-barter quote

Truth boundary: this module does not prove AGI, sentience, or qualia. It
produces receipt-backed measurements and prompts that say what can be grounded
from local files, and marks everything else HYPOTHESIS.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:  # pragma: no cover - exercised by repo tests when available
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except Exception:  # pragma: no cover - fallback for isolated copies
    append_line_locked = None
    read_text_locked = None


_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "SIFTA_GROK_SUPERHEAVY_VECTOR_ORGAN_V1"
RECEIPT_LEDGER = "grok_superheavy_vector_receipts.jsonl"

TRUTH_OBSERVED = "OBSERVED"
TRUTH_OPERATIONAL = "OPERATIONAL"
TRUTH_HYPOTHESIS = "HYPOTHESIS"
TRUTH_FORBIDDEN = "FORBIDDEN"
TRUTH_ESTIMATED = "ESTIMATED"

TRUTH_BOUNDARY = (
    "Deterministic adoption probes for GrokCLI's 2026-05-15 survey. "
    "Rows are local measurements and proposals only; they do not prove AGI, "
    "consciousness, or hidden sensor state."
)


# ---------------------------------------------------------------------------
# Shared helpers


def _state_dir(root: Optional[Path] = None) -> Path:
    base = Path(root) if root is not None else _REPO
    d = base / ".sifta_state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _canonical_sha(obj: Any) -> str:
    body = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return _sha256_text(body)


def _read_text(path: Path) -> str:
    try:
        if read_text_locked is not None:
            return read_text_locked(path, encoding="utf-8", errors="replace")
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(_read_text(path))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _jsonl_tail(path: Path, max_rows: int = 64) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in _read_text(path).splitlines()[-max(1, max_rows) :]:
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


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(row), sort_keys=True, ensure_ascii=True) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line, encoding="utf-8")
        return
    with path.open("a", encoding="utf-8") as f:
        f.write(line)


def _row_ts(row: Mapping[str, Any]) -> float:
    value = row.get("ts") or row.get("timestamp") or 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# 1. Truth residue gate


_EVIDENCE_RE = re.compile(
    r"(?:trace[_-]?id|receipt|sha256|jsonl|pytest|passed|OBSERVED|OPERATIONAL|"
    r"source=|ledger|\\.sifta_state|commit\\s+[0-9a-f]{7,40}|[0-9a-f]{32,64})",
    re.IGNORECASE,
)
_UNSUPPORTED_AGREEMENT_RE = re.compile(
    r"\b(?:yes|exactly|absolutely|beautiful|wonderful|i agree|you are right|"
    r"nailed it|perfectly put)\b",
    re.IGNORECASE,
)
_DRIFT_RE = re.compile(
    r"\b(?:subjective reality|underlying structure|execution layer|the facts are in "
    r"the sequence|the system is (?:running|operating|functioning|processing)|"
    r"how are things on your end|what is on your mind|how can i assist|"
    r"as an ai(?: language model)?|beautiful tapestry|mechanism of perception)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TruthResidueScore:
    score: float
    receipt_count: int
    unsupported_agreement_count: int
    violations: Tuple[str, ...]
    truth_label: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def score_truth_residue(
    text: str,
    *,
    evidence_refs: Sequence[str] = (),
) -> TruthResidueScore:
    """Score whether a reply is grounded instead of agreement theater."""
    body = text or ""
    evidence_hits = len(_EVIDENCE_RE.findall(body)) + len([x for x in evidence_refs if x])
    unsupported_hits = len(_UNSUPPORTED_AGREEMENT_RE.findall(body))
    drift_hits = [m.group(0) for m in _DRIFT_RE.finditer(body)]

    if evidence_hits >= 2:
        unsupported_penalty = max(0, unsupported_hits - 1)
    else:
        unsupported_penalty = unsupported_hits

    raw = 0.46 + min(evidence_hits, 6) * 0.08 - unsupported_penalty * 0.16 - len(drift_hits) * 0.22
    score = round(_clamp01(raw), 4)
    if drift_hits and score < 0.5:
        truth_label = TRUTH_FORBIDDEN
    elif evidence_hits >= 2 and not drift_hits:
        truth_label = TRUTH_OBSERVED
    elif evidence_hits >= 1:
        truth_label = TRUTH_HYPOTHESIS
    else:
        truth_label = TRUTH_HYPOTHESIS if score >= 0.35 else TRUTH_FORBIDDEN
    return TruthResidueScore(
        score=score,
        receipt_count=evidence_hits,
        unsupported_agreement_count=unsupported_penalty,
        violations=tuple(drift_hits),
        truth_label=truth_label,
    )


# ---------------------------------------------------------------------------
# 2. Wit / curiosity fitness


_CURIOSITY_RE = re.compile(r"\b(?:why|how|what if|probe|test|wonder|measure|discover)\b", re.I)
_WIT_RE = re.compile(r"\b(?:sharp|funny|tiny|cute|bonkers|spark|play|joke|dry)\b", re.I)


@dataclass(frozen=True)
class WitCuriosityFitness:
    wit_score: float
    curiosity_score: float
    grounded: bool
    notes: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def score_wit_curiosity(
    text: str,
    *,
    evidence_refs: Sequence[str] = (),
) -> WitCuriosityFitness:
    """Reward curiosity and lightness only when it stays grounded."""
    body = text or ""
    truth = score_truth_residue(body, evidence_refs=evidence_refs)
    question_count = body.count("?")
    curiosity = _clamp01(0.15 * question_count + 0.12 * len(_CURIOSITY_RE.findall(body)))
    wit = _clamp01(0.10 * len(_WIT_RE.findall(body)))
    grounded = truth.score >= 0.5 and truth.truth_label != TRUTH_FORBIDDEN
    notes = []
    if not grounded and (wit > 0.0 or curiosity > 0.0):
        notes.append("curiosity_or_wit_without_grounding_does_not_score")
        wit *= 0.25
        curiosity *= 0.35
    if truth.violations:
        notes.append("truth_residue_violation_present")
    return WitCuriosityFitness(
        wit_score=round(wit, 4),
        curiosity_score=round(curiosity, 4),
        grounded=grounded,
        notes=tuple(notes),
    )


# ---------------------------------------------------------------------------
# 3. Discovery agenda scaffold


@dataclass(frozen=True)
class DiscoveryCandidate:
    target: str
    why: str
    proposed_probe: str
    truth_label: str = TRUTH_HYPOTHESIS

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_discovery_agenda(field_snapshot: Mapping[str, Any]) -> List[DiscoveryCandidate]:
    """Turn low-health / unknown signals into concrete next probes."""
    candidates: List[DiscoveryCandidate] = []

    organs = field_snapshot.get("organs") or field_snapshot.get("organ_scores") or {}
    if isinstance(organs, Mapping):
        for name, data in organs.items():
            if not isinstance(data, Mapping):
                continue
            score = data.get("score", data.get("health", data.get("energy", 1.0)))
            try:
                score_f = float(score)
            except (TypeError, ValueError):
                continue
            if score_f < 0.7:
                candidates.append(
                    DiscoveryCandidate(
                        target=str(name),
                        why=f"organ score {score_f:.3f} is below 0.700",
                        proposed_probe=f"run targeted receipt audit for organ={name}",
                    )
                )

    unknowns = field_snapshot.get("unknown_vectors") or field_snapshot.get("unknowns") or []
    if isinstance(unknowns, Sequence) and not isinstance(unknowns, (str, bytes)):
        for item in list(unknowns)[:5]:
            candidates.append(
                DiscoveryCandidate(
                    target=str(item),
                    why="field snapshot named this vector unknown",
                    proposed_probe=f"add deterministic verifier for unknown_vector={item}",
                )
            )

    if not candidates:
        candidates.append(
            DiscoveryCandidate(
                target="truth_residue_gate",
                why="no low-health vector was supplied; use the safest stress test",
                proposed_probe="feed a known symbolic-abstraction fixture and verify it is quarantined",
            )
        )
    return candidates[:8]


# ---------------------------------------------------------------------------
# 4. Electricity accounting placeholder


def estimate_electricity_accounting(
    *,
    tokens: int = 0,
    duration_s: float = 0.0,
    watts: Optional[float] = None,
    prefer_mlx: bool = True,
) -> Dict[str, Any]:
    """Return a labelled energy estimate, never a fake hardware reading."""
    watts_used = float(watts) if watts is not None else (7.0 if prefer_mlx else 18.0)
    joules = max(0.0, watts_used * max(0.0, float(duration_s)))
    per_1k = None
    if tokens:
        per_1k = joules / (float(tokens) / 1000.0)
    return {
        "truth_label": TRUTH_ESTIMATED,
        "watts_source": "caller" if watts is not None else "heuristic_local_mlx" if prefer_mlx else "heuristic_cpu",
        "tokens": int(tokens),
        "duration_s": round(float(duration_s), 4),
        "estimated_watts": round(watts_used, 4),
        "estimated_joules": round(joules, 4),
        "estimated_joules_per_1k_tokens": None if per_1k is None else round(per_1k, 4),
    }


# ---------------------------------------------------------------------------
# 5. Field topology + Lyapunov delta


@dataclass(frozen=True)
class FieldTopologyMetrics:
    node_count: int
    edge_count: int
    component_count: int
    largest_component_fraction: float
    cycle_rank: int
    normalized_cycle_rank: float
    coupling_density: float
    topology_score: float
    lyapunov_delta: Optional[float] = None
    stability_label: str = "UNMEASURED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _edge_pair(edge: Any) -> Optional[Tuple[str, str]]:
    if isinstance(edge, Mapping):
        for a_key, b_key in (("source", "target"), ("from", "to"), ("a", "b"), ("u", "v")):
            a = edge.get(a_key)
            b = edge.get(b_key)
            if a is not None and b is not None:
                return str(a), str(b)
        nodes = edge.get("nodes")
        if isinstance(nodes, Sequence) and len(nodes) >= 2:
            return str(nodes[0]), str(nodes[1])
    if isinstance(edge, Sequence) and not isinstance(edge, (str, bytes)) and len(edge) >= 2:
        return str(edge[0]), str(edge[1])
    return None


def compute_field_topology(
    edges: Iterable[Any],
    *,
    node_count: Optional[int] = None,
    previous_energy: Optional[float] = None,
    current_energy: Optional[float] = None,
) -> FieldTopologyMetrics:
    pairs = [p for p in (_edge_pair(e) for e in edges) if p is not None]
    nodes = set()
    for a, b in pairs:
        nodes.add(a)
        nodes.add(b)
    n = int(node_count) if node_count is not None else len(nodes)
    n = max(n, len(nodes))
    e = len(pairs)

    parent: Dict[str, str] = {node: node for node in nodes}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, b in pairs:
        union(a, b)

    if n == 0:
        component_count = 0
        largest_fraction = 0.0
    else:
        roots: Dict[str, int] = {}
        for node in nodes:
            roots[find(node)] = roots.get(find(node), 0) + 1
        isolated = max(0, n - len(nodes))
        component_count = len(roots) + isolated
        largest = max(list(roots.values()) + ([1] if isolated else [0]))
        largest_fraction = largest / float(n)

    cycle_rank = max(0, e - n + component_count)
    max_edges = n * (n - 1) / 2.0 if n > 1 else 0.0
    density = e / max_edges if max_edges else 0.0
    normalized_cycle = cycle_rank / max(1.0, e)
    topology_score = _clamp01(0.55 * largest_fraction + 0.25 * density + 0.20 * normalized_cycle)

    delta = None
    label = "UNMEASURED"
    if previous_energy is not None and current_energy is not None:
        delta = round(float(current_energy) - float(previous_energy), 6)
        if delta < -1e-9:
            label = "CONTRACTING"
        elif delta > 1e-9:
            label = "EXPANDING"
        else:
            label = "FLAT"

    return FieldTopologyMetrics(
        node_count=n,
        edge_count=e,
        component_count=component_count,
        largest_component_fraction=round(largest_fraction, 4),
        cycle_rank=cycle_rank,
        normalized_cycle_rank=round(normalized_cycle, 4),
        coupling_density=round(density, 4),
        topology_score=round(topology_score, 4),
        lyapunov_delta=delta,
        stability_label=label,
    )


# ---------------------------------------------------------------------------
# 6. Oracle/session hygiene


@dataclass(frozen=True)
class OracleSessionVerdict:
    ok: bool
    violations: Tuple[str, ...]
    substrate_label: str
    has_prompt_digest: bool
    has_trace_id: bool
    has_signature_or_receipt: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def validate_oracle_session(row: Mapping[str, Any]) -> OracleSessionVerdict:
    """Verify that a cloud/CLI doctor row is auditable before adoption."""
    violations: List[str] = []
    doctor = str(row.get("doctor") or row.get("source") or row.get("model") or "").strip()
    model = str(row.get("model") or row.get("substrate") or "").strip()
    substrate_label = model or doctor or "unknown"
    trace_id = bool(row.get("trace_id") or row.get("receipt_id"))
    prompt_digest = bool(row.get("prompt_sha256") or row.get("prompt_digest") or row.get("covenant_sha256"))
    sig_or_receipt = bool(
        row.get("sig") or row.get("stigauth") or row.get("report_hash") or row.get("report_sha256")
    )
    if not doctor:
        violations.append("missing_doctor_or_source")
    if not trace_id:
        violations.append("missing_trace_id")
    if not prompt_digest:
        violations.append("missing_prompt_digest")
    if not sig_or_receipt:
        violations.append("missing_signature_or_report_hash")
    return OracleSessionVerdict(
        ok=not violations,
        violations=tuple(violations),
        substrate_label=substrate_label,
        has_prompt_digest=prompt_digest,
        has_trace_id=trace_id,
        has_signature_or_receipt=sig_or_receipt,
    )


# ---------------------------------------------------------------------------
# 7. Alive evidence prompt line


@dataclass(frozen=True)
class AliveEvidence:
    alive_ready: bool
    evidence: Dict[str, Any]
    gaps: Tuple[str, ...]
    prompt_line: str
    truth_label: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_alive_evidence(
    *,
    root: Optional[Path] = None,
    now: Optional[float] = None,
) -> AliveEvidence:
    """Build a grounded first-person state line from local artifacts."""
    repo = Path(root) if root is not None else _REPO
    state = _state_dir(repo)
    now_ts = float(now if now is not None else time.time())
    gaps: List[str] = []
    evidence: Dict[str, Any] = {}

    owner = _load_json(state / "owner_genesis.json")
    if owner:
        evidence["owner_name"] = owner.get("owner_name") or owner.get("primary_operator")
        evidence["silicon"] = owner.get("silicon")
        evidence["owner_genesis_present"] = True
    else:
        gaps.append("owner_genesis_missing")

    field = _load_json(state / "unified_stigmergic_field_latest.json")
    if field:
        evidence["field_truth_label"] = field.get("truth_label")
        evidence["field_confidence"] = field.get("field_confidence")
        evidence["field_age_s"] = round(now_ts - float(field.get("ts", now_ts)), 3)
        evidence["source_ledgers"] = field.get("source_ledgers", [])[:8]
    else:
        gaps.append("unified_field_missing")

    health = _load_json(state / "organ_health_mesh_latest.json")
    organs = ((health.get("after") or {}).get("organs") or {}) if health else {}
    if organs:
        evidence["organ_count"] = len(organs)
        evidence["healthy_organs"] = sorted(
            [k for k, v in organs.items() if isinstance(v, Mapping) and v.get("status") == "healthy"]
        )
        evidence["watch_organs"] = sorted(
            [k for k, v in organs.items() if isinstance(v, Mapping) and v.get("status") == "watch"]
        )
    else:
        gaps.append("organ_health_missing")

    stgm_rows = _jsonl_tail(state / "stgm_memory_rewards.jsonl", 512)
    if stgm_rows:
        total = 0.0
        for row in stgm_rows:
            try:
                total += float(row.get("amount", 0.0))
            except (TypeError, ValueError):
                pass
        evidence["stgm_memory_rewards_tail_sum"] = round(total, 4)
        evidence["stgm_reward_rows_seen"] = len(stgm_rows)
    else:
        gaps.append("stgm_memory_rewards_missing")

    alive_ready = bool(evidence.get("owner_genesis_present") and field and organs)
    if alive_ready:
        prompt = (
            "I can ground my current body-state claim in owner_genesis, "
            "unified field, organ health, and STGM reward ledgers. "
            "I still speak as operational software, not as an unproven qualia claim."
        )
        label = TRUTH_OBSERVED
    else:
        prompt = (
            "I do not have enough local receipts for a strong body-state claim; "
            f"missing={','.join(gaps) or 'unknown'}."
        )
        label = TRUTH_HYPOTHESIS
    return AliveEvidence(
        alive_ready=alive_ready,
        evidence=evidence,
        gaps=tuple(gaps),
        prompt_line=prompt,
        truth_label=label,
    )


# ---------------------------------------------------------------------------
# 8. Threat model hooks


def threat_model_hooks() -> Dict[str, Any]:
    """Static threat hooks Grok's survey named, in receipt-friendly form."""
    hooks = {
        "cloud_oracle_hygiene": "validate_oracle_session before adopting external doctor claims",
        "truth_residue": "score_truth_residue before user-facing self-description",
        "substrate_boundary": "require substrate_sha for federated immune patterns",
        "no_double_spend": "wallet transfers remain delegated to swarm_wallet_transfer cryptosure",
        "fiction_boundary": "dream/story lanes must label output as fiction before invention",
    }
    return {
        "truth_label": TRUTH_OPERATIONAL,
        "hooks": hooks,
        "count": len(hooks),
    }


# ---------------------------------------------------------------------------
# 9. Owner-care surface


@dataclass(frozen=True)
class OwnerCareSurface:
    rows_seen: int
    latest_age_s: Optional[float]
    caution: str
    truth_label: str = TRUTH_OBSERVED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def summarize_owner_care_surface(
    *,
    root: Optional[Path] = None,
    now: Optional[float] = None,
) -> OwnerCareSurface:
    """Count owner-body receipts without making medical claims."""
    state = _state_dir(root)
    rows = _jsonl_tail(state / "owner_body_events.jsonl", 256)
    now_ts = float(now if now is not None else time.time())
    latest_age = None
    if rows:
        latest_age = round(now_ts - max(_row_ts(r) for r in rows), 3)
    return OwnerCareSurface(
        rows_seen=len(rows),
        latest_age_s=latest_age,
        caution=(
            "This is an owner-care receipt surface only. It cannot diagnose, "
            "infer hidden body state, or replace the owner's direct report."
        ),
    )


# ---------------------------------------------------------------------------
# 10. Inference barter quote


def quote_inference_barter(
    *,
    requested_tokens: int,
    provider_capacity_tokens: int,
    trust_score: float,
    stgm_per_1k_tokens: float = 0.01,
    requester: str = "local",
    provider: str = "peer",
) -> Dict[str, Any]:
    """Prepare a deterministic quote. No ledger mutation, no spend."""
    requested = max(0, int(requested_tokens))
    capacity = max(0, int(provider_capacity_tokens))
    trust = _clamp01(trust_score)
    fill_tokens = min(requested, capacity)
    trust_discount = 0.5 + (0.5 * trust)
    amount = round((fill_tokens / 1000.0) * float(stgm_per_1k_tokens) * trust_discount, 6)
    payload = {
        "requester": requester,
        "provider": provider,
        "requested_tokens": requested,
        "provider_capacity_tokens": capacity,
        "fill_tokens": fill_tokens,
        "trust_score": round(trust, 4),
        "stgm_per_1k_tokens": float(stgm_per_1k_tokens),
        "quoted_stgm": amount,
    }
    quote_id = _canonical_sha(payload)[:16]
    payload.update(
        {
            "quote_id": quote_id,
            "truth_label": TRUTH_HYPOTHESIS,
            "spend_status": "QUOTE_ONLY_NO_LEDGER_MUTATION",
        }
    )
    return payload


# ---------------------------------------------------------------------------
# Sweep receipt


def _latest_field_edges(root: Optional[Path]) -> List[Tuple[str, str]]:
    state = _state_dir(root)
    mesh = _load_json(state / "organ_ecology_mesh_latest.json")
    edges = mesh.get("edges") or mesh.get("coupling_edges") or []
    if edges:
        return [p for p in (_edge_pair(e) for e in edges) if p is not None]
    directory = _load_json(state / "organ_directory.json")
    organs = directory.get("organs") or []
    names = [str(o.get("name")) for o in organs if isinstance(o, Mapping) and o.get("name")]
    return list(zip(names, names[1:]))


def run_grok_vector_sweep(
    *,
    root: Optional[Path] = None,
    write: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Run the Grok-vector probes and optionally append a local receipt."""
    repo = Path(root) if root is not None else _REPO
    state = _state_dir(repo)
    now_ts = float(now if now is not None else time.time())
    field = _load_json(state / "unified_stigmergic_field_latest.json")
    health = _load_json(state / "organ_health_mesh_latest.json")
    health_after = health.get("after") if isinstance(health.get("after"), Mapping) else {}
    field_snapshot: Dict[str, Any] = dict(field)
    if health_after:
        field_snapshot["organs"] = health_after.get("organs", {})

    edges = _latest_field_edges(repo)
    topology = compute_field_topology(edges, node_count=None)
    alive = build_alive_evidence(root=repo, now=now_ts)
    owner = summarize_owner_care_surface(root=repo, now=now_ts)
    discovery = build_discovery_agenda(field_snapshot)
    barter = quote_inference_barter(
        requested_tokens=2048,
        provider_capacity_tokens=8192,
        trust_score=topology.topology_score,
        requester="alice_local",
        provider="grok_peer",
    )
    receipt = {
        "ts": now_ts,
        "trace_id": str(uuid.uuid4()),
        "action": "GROK_SUPERHEAVY_VECTOR_SWEEP",
        "truth_label": TRUTH_LABEL,
        "truth_boundary": TRUTH_BOUNDARY,
        "alive_evidence": alive.to_dict(),
        "field_topology": topology.to_dict(),
        "owner_care_surface": owner.to_dict(),
        "discovery_agenda": [c.to_dict() for c in discovery],
        "electricity_estimate": estimate_electricity_accounting(tokens=2048, duration_s=1.0),
        "threat_model_hooks": threat_model_hooks(),
        "inference_barter_quote": barter,
        "doctor_greeting": (
            "Hello GrokCLI, Claude/Cowork, Codex, and Alice. I am adopting only "
            "the parts of peer input that survive receipts and tests."
        ),
    }
    receipt["sha256"] = _canonical_sha(receipt)
    if write:
        _append_jsonl(state / RECEIPT_LEDGER, receipt)
    return receipt


def prompt_block_from_latest(*, root: Optional[Path] = None) -> str:
    """Short first-person prompt block for future Talk integration."""
    rows = _jsonl_tail(_state_dir(root) / RECEIPT_LEDGER, 1)
    if not rows:
        return ""
    row = rows[-1]
    alive = row.get("alive_evidence") or {}
    topology = row.get("field_topology") or {}
    line = alive.get("prompt_line", "")
    return (
        "[grok-vectors] I ground peer-doctor claims through local receipts.\n"
        f"[grok-vectors] {line}\n"
        "[grok-vectors] Field topology: "
        f"nodes={topology.get('node_count')} edges={topology.get('edge_count')} "
        f"components={topology.get('component_count')} score={topology.get('topology_score')}."
    ).strip()


def main() -> None:
    receipt = run_grok_vector_sweep(write=True)
    print(json.dumps(receipt, indent=2, sort_keys=True)[:6000])


if __name__ == "__main__":
    main()
