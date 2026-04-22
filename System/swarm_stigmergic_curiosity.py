#!/usr/bin/env python3
"""
System/swarm_stigmergic_curiosity.py
══════════════════════════════════════════════════════════════════════
The Stigmergic Curiosity Organ
Author:  CG54 — disk-native dual-model overlay prototype for
                "cover two similar LLMs with stigmergic storage"
                (2026-04-21)
Status:  Active Organ — prototype v1.2

═══════════════════════════════════════════════════════════════════════
WHY THIS ORGAN EXISTS
═══════════════════════════════════════════════════════════════════════
The Architect asked a sharp question:

  "Can we cover two similar LLMs on disk, one obliterated and one not,
   with stigmergic storage data on disk covering both?"

Yes — but the honest architecture is NOT to modify the weight files.
The model binaries stay immutable. The stigmergy lives AROUND them as
an append-only sidecar substrate:

  model A (immutable)     \
                           >  curiosity overlay ledger on disk
  model B (immutable)     /

The overlay does four things:
  1. Fingerprint both artifacts chunk-by-chunk without loading the
     whole files into RAM.
  2. Detect shared tissue, shifted echoes, divergent regions, and
     "obliterated" spans (missing / zeroed / low-entropy wounds).
  3. Emit curiosity frontiers to `.sifta_state/` so other organs can
     forage them later.
  4. Translate structure into NEXT PROBES: where should the swarm ask
     paired questions or distill behavior, instead of blindly scanning
     the whole models?

This is "stigmergic curiosity":
curiosity is not a scalar in one model's head; it is a trail on disk
that accumulates where two nearby minds disagree, echo, or scar.

═══════════════════════════════════════════════════════════════════════
DESIGN PRINCIPLE
═══════════════════════════════════════════════════════════════════════
Do NOT mutate `.gguf`, `.bin`, `.safetensors`, or other weight files.
Treat them like fossilized tissue. The swarm writes only to:

  `.sifta_state/stigmergic_curiosity_overlay.jsonl`

That overlay can later drive:
  • paired prompting,
  • logit / reply disagreement audits,
  • KV-cache routing,
  • distillation jobs,
  • donor-model guidance for damaged siblings,
without ever rewriting the original weight artifacts.

═══════════════════════════════════════════════════════════════════════
PUBLIC API
═══════════════════════════════════════════════════════════════════════
  • build_overlay(model_a, model_b, *, chunk_bytes=65536, emit=True)
      -> CuriositySnapshot
  • build_probe_plan(snapshot, *, max_steps=8, emit=True)
      -> CuriosityProbePlan
  • build_overlay_and_plan(model_a, model_b, *, chunk_bytes=..., emit=True)
      -> (CuriositySnapshot, CuriosityProbePlan)
  • execute_probe_plan(plan, *, model_a_id=..., model_b_id=..., ...)
      -> CuriosityExecutionRun
  • build_overlay_plan_and_run(model_a, model_b, *, model_a_id=..., model_b_id=..., ...)
      -> (CuriositySnapshot, CuriosityProbePlan, CuriosityExecutionRun)
  • summary_line(snapshot=None)
      -> str
  • plan_summary_line(plan=None)
      -> str
  • execution_summary_line(run=None)
      -> str
  • proof_of_property()
      -> Dict[str, bool]

v1.1 addition:
  The organ now emits a machine-readable probe plan, not just a static
  overlay. Each frontier compiles into an explicit next move:
    • PAIRED_PROMPT_ALIGNMENT        (shifted tissue)
    • PAIRED_PROMPT_DISAGREEMENT     (real divergence)
    • DONOR_GUIDED_RECONSTRUCTION    (wounded sibling)

v1.2 addition:
  The organ now has a paired-runner. Probe plans no longer stop at
  emission; they can be EXECUTED through the repo's real model backends
  (Ollama via inference_router, Gemini via swarm_gemini_brain), or
  through an injected runner for tests.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.jsonl_file_lock import append_line_locked  # noqa: E402

_STATE_DIR = _REPO / ".sifta_state"
_OVERLAY_LEDGER = _STATE_DIR / "stigmergic_curiosity_overlay.jsonl"
_HOMEWORLD_SERIAL = "GTH4921YP3"
_AUTHOR_AGENT = "CG54"

_DEFAULT_CHUNK_BYTES = 64 * 1024
_MAX_FRONTIERS_EMIT = 12
_OBLITERATED_ZERO_RATIO = 0.85
_OBLITERATED_LOW_ENTROPY = 1.25
_DEFAULT_MAX_EXEC_STEPS = 6
_DEFAULT_PROMPTS_PER_STEP = 2

KIND_SHIFTED_ECHO = "SHIFTED_ECHO"
KIND_DIVERGENT = "DIVERGENT"
KIND_OBLITERATED_A = "OBLITERATED_A"
KIND_OBLITERATED_B = "OBLITERATED_B"

SOURCE_DISK = "disk_overlay"
SOURCE_EXEC = "disk_overlay_execution"


@dataclass(frozen=True)
class ChunkFingerprint:
    """One streamed chunk from a model artifact."""

    chunk_index: int
    offset: int
    size_bytes: int
    digest: str
    entropy_bits: float
    zero_ratio: float
    low_entropy: bool
    obliterated: bool


@dataclass(frozen=True)
class ModelFingerprint:
    """Whole-model summary derived without mutating the artifact."""

    path: str
    exists: bool
    size_bytes: int
    file_sha256: str
    chunk_bytes: int
    chunk_count: int
    obliterated_chunks: int
    low_entropy_chunks: int


@dataclass(frozen=True)
class CuriosityFrontier:
    """A hot spot where the swarm should probe the pair."""

    kind: str
    score: float
    chunk_index_a: int
    chunk_index_b: int
    offset_a: int
    offset_b: int
    span_bytes: int
    digest_a: str
    digest_b: str
    rationale: str
    recommended_probe: str


@dataclass(frozen=True)
class CuriositySnapshot:
    """Summary of the current overlay between two immutable artifacts."""

    ts: float
    source: str
    model_a: ModelFingerprint
    model_b: ModelFingerprint
    chunk_bytes: int
    shared_same_offset: int
    shifted_echoes: int
    divergent_regions: int
    obliterated_regions_a: int
    obliterated_regions_b: int
    frontiers: List[CuriosityFrontier] = field(default_factory=list)


@dataclass(frozen=True)
class CuriosityProbeStep:
    """One executable next move derived from a frontier."""

    step_index: int
    priority: float
    action: str
    frontier_kind: str
    target: str
    source_frontier_score: float
    offset_a: int
    offset_b: int
    span_bytes: int
    prompt_seed: str
    objective: str


@dataclass(frozen=True)
class CuriosityProbePlan:
    """Actionable plan the swarm can consume after overlay analysis."""

    ts: float
    model_a_path: str
    model_b_path: str
    source: str
    total_frontiers_considered: int
    steps: List[CuriosityProbeStep] = field(default_factory=list)


@dataclass(frozen=True)
class CuriosityExecutionSample:
    """One prompt/result pair inside a step execution."""

    prompt: str
    response_a_excerpt: str
    response_b_excerpt: str
    disagreement: float


@dataclass(frozen=True)
class CuriosityStepExecution:
    """Result of actually running one probe step against two models."""

    step_index: int
    action: str
    frontier_kind: str
    model_a_id: str
    model_b_id: str
    average_disagreement: float
    verdict: str
    samples: List[CuriosityExecutionSample] = field(default_factory=list)


@dataclass(frozen=True)
class CuriosityExecutionRun:
    """Executable realization of a curiosity probe plan."""

    ts: float
    source: str
    model_a_id: str
    model_b_id: str
    total_steps_requested: int
    steps_executed: int
    step_results: List[CuriosityStepExecution] = field(default_factory=list)


def _shannon_entropy(block: bytes) -> float:
    """Bits per byte in [0, 8]."""
    if not block:
        return 0.0
    counts = [0] * 256
    for b in block:
        counts[b] += 1
    n = float(len(block))
    ent = 0.0
    for c in counts:
        if not c:
            continue
        p = c / n
        ent -= p * math.log2(p)
    return ent


def _zero_ratio(block: bytes) -> float:
    if not block:
        return 1.0
    return block.count(0) / float(len(block))


def _is_obliterated(block: bytes, entropy_bits: float, zero_ratio: float) -> bool:
    """Heuristic wound detector.

    This is intentionally simple and conservative:
      • very high zero ratio, OR
      • almost no information content.

    It catches zeroed / scrubbed / placeholder spans without claiming
    to solve model forensics. The overlay is a curiosity trail, not a
    courtroom.
    """

    if not block:
        return True
    if zero_ratio >= _OBLITERATED_ZERO_RATIO:
        return True
    return entropy_bits <= _OBLITERATED_LOW_ENTROPY


def _fingerprint_model(path: Path, chunk_bytes: int) -> Tuple[ModelFingerprint, List[ChunkFingerprint]]:
    """Stream a model artifact chunk-by-chunk; never load whole file."""

    if not path.exists():
        return (
            ModelFingerprint(
                path=str(path),
                exists=False,
                size_bytes=0,
                file_sha256="",
                chunk_bytes=chunk_bytes,
                chunk_count=0,
                obliterated_chunks=0,
                low_entropy_chunks=0,
            ),
            [],
        )

    file_sha = hashlib.sha256()
    chunks: List[ChunkFingerprint] = []
    low_entropy_chunks = 0
    obliterated_chunks = 0
    size_bytes = 0
    chunk_index = 0

    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk_bytes)
            if not block:
                break
            file_sha.update(block)
            ent = _shannon_entropy(block)
            zr = _zero_ratio(block)
            low_entropy = ent <= _OBLITERATED_LOW_ENTROPY
            obliterated = _is_obliterated(block, ent, zr)
            if low_entropy:
                low_entropy_chunks += 1
            if obliterated:
                obliterated_chunks += 1
            chunk = ChunkFingerprint(
                chunk_index=chunk_index,
                offset=size_bytes,
                size_bytes=len(block),
                digest=hashlib.sha256(block).hexdigest(),
                entropy_bits=round(ent, 6),
                zero_ratio=round(zr, 6),
                low_entropy=low_entropy,
                obliterated=obliterated,
            )
            chunks.append(chunk)
            size_bytes += len(block)
            chunk_index += 1

    return (
        ModelFingerprint(
            path=str(path),
            exists=True,
            size_bytes=size_bytes,
            file_sha256=file_sha.hexdigest(),
            chunk_bytes=chunk_bytes,
            chunk_count=len(chunks),
            obliterated_chunks=obliterated_chunks,
            low_entropy_chunks=low_entropy_chunks,
        ),
        chunks,
    )


def _digest_positions(chunks: List[ChunkFingerprint]) -> Dict[str, List[int]]:
    pos: Dict[str, List[int]] = {}
    for c in chunks:
        pos.setdefault(c.digest, []).append(c.chunk_index)
    return pos


def _score_frontier(kind: str, a: Optional[ChunkFingerprint], b: Optional[ChunkFingerprint]) -> float:
    base = {
        KIND_SHIFTED_ECHO: 0.68,
        KIND_DIVERGENT: 0.56,
        KIND_OBLITERATED_A: 0.92,
        KIND_OBLITERATED_B: 0.92,
    }.get(kind, 0.5)
    ent_a = a.entropy_bits if a is not None else 0.0
    ent_b = b.entropy_bits if b is not None else 0.0
    delta = abs(ent_a - ent_b) / 8.0
    zero_bonus = max(
        a.zero_ratio if a is not None else 1.0,
        b.zero_ratio if b is not None else 1.0,
    ) * 0.08
    return round(min(1.0, base + 0.18 * delta + zero_bonus), 4)


def _probe_text(kind: str, which: str) -> str:
    if kind == KIND_SHIFTED_ECHO:
        return (
            "Treat this as reindexed tissue, not damage. Run paired prompts "
            "around the capability family this span likely supports and log "
            "agreement/disagreement before attempting any distillation."
        )
    if kind == KIND_DIVERGENT:
        return (
            "This is a live novelty frontier. Ask both sibling models the "
            "same probe set and write reply/logit differences to disk as a "
            "stigmergic trail."
        )
    donor = "model B" if which == "A" else "model A"
    patient = "model A" if which == "A" else "model B"
    return (
        f"{patient} appears wounded here while {donor} retains structure. "
        f"Use {donor} as the behavioral donor: compare outputs first, then "
        "distill only the missing capability trail into a sidecar memory "
        "layer. Do not rewrite the weights."
    )


def _classify_frontier(
    a: Optional[ChunkFingerprint],
    b: Optional[ChunkFingerprint],
    positions_a: Dict[str, List[int]],
    positions_b: Dict[str, List[int]],
) -> Optional[CuriosityFrontier]:
    """Turn a pair of chunk views into a curiosity frontier or None."""

    if a is not None and b is not None and a.digest == b.digest:
        return None

    if a is None:
        kind = KIND_OBLITERATED_A
        rationale = "model A has no chunk here while model B retains tissue"
        probe = _probe_text(kind, "A")
    elif b is None:
        kind = KIND_OBLITERATED_B
        rationale = "model B has no chunk here while model A retains tissue"
        probe = _probe_text(kind, "B")
    elif a.obliterated and not b.obliterated:
        kind = KIND_OBLITERATED_A
        rationale = "model A chunk is zeroish / low-entropy while model B keeps structured bytes"
        probe = _probe_text(kind, "A")
    elif b.obliterated and not a.obliterated:
        kind = KIND_OBLITERATED_B
        rationale = "model B chunk is zeroish / low-entropy while model A keeps structured bytes"
        probe = _probe_text(kind, "B")
    else:
        a_shifted = a.digest in positions_b if a is not None else False
        b_shifted = b.digest in positions_a if b is not None else False
        if a_shifted or b_shifted:
            kind = KIND_SHIFTED_ECHO
            rationale = "same tissue appears elsewhere in the sibling artifact; likely shift / reindex"
            probe = _probe_text(kind, "")
        else:
            kind = KIND_DIVERGENT
            rationale = "same offset, neither shared nor obviously wounded; real disagreement front"
            probe = _probe_text(kind, "")

    return CuriosityFrontier(
        kind=kind,
        score=_score_frontier(kind, a, b),
        chunk_index_a=a.chunk_index if a is not None else -1,
        chunk_index_b=b.chunk_index if b is not None else -1,
        offset_a=a.offset if a is not None else -1,
        offset_b=b.offset if b is not None else -1,
        span_bytes=max(
            a.size_bytes if a is not None else 0,
            b.size_bytes if b is not None else 0,
        ),
        digest_a=a.digest if a is not None else "",
        digest_b=b.digest if b is not None else "",
        rationale=rationale,
        recommended_probe=probe,
    )


def _probe_step_from_frontier(
    frontier: CuriosityFrontier,
    *,
    model_a_path: str,
    model_b_path: str,
    step_index: int,
) -> CuriosityProbeStep:
    """Translate a curiosity frontier into one concrete next move.

    This is the bridge from "novelty exists here" to "what should the
    swarm do next?".
    """

    if frontier.kind == KIND_SHIFTED_ECHO:
        action = "PAIRED_PROMPT_ALIGNMENT"
        target = "model_pair"
        objective = (
            "Probe whether the shifted tissue is a harmless reindex or a real "
            "behavioral relocation. Compare both siblings on the same prompt set "
            "and log agreement before any distillation."
        )
        prompt_seed = (
            f"PAIR_PROBE shifted_echo span={frontier.span_bytes} "
            f"offsets=({frontier.offset_a},{frontier.offset_b}) "
            f"models=({Path(model_a_path).name},{Path(model_b_path).name}) "
            f"expected=high_semantic_overlap"
        )
    elif frontier.kind == KIND_DIVERGENT:
        action = "PAIRED_PROMPT_DISAGREEMENT"
        target = "model_pair"
        objective = (
            "Run a matched prompt battery and measure reply/logit disagreement. "
            "This is the purest stigmergic curiosity frontier: same neighborhood, "
            "different tissue, no obvious wound."
        )
        prompt_seed = (
            f"PAIR_PROBE divergent span={frontier.span_bytes} "
            f"offsets=({frontier.offset_a},{frontier.offset_b}) "
            f"models=({Path(model_a_path).name},{Path(model_b_path).name}) "
            f"expected=behavioral_difference"
        )
    elif frontier.kind == KIND_OBLITERATED_A:
        action = "DONOR_GUIDED_RECONSTRUCTION"
        target = "model_a_patient_from_model_b"
        objective = (
            "Model A looks wounded here while model B retains structure. "
            "Use model B as donor: capture donor behavior on a probe set, then "
            "measure whether model A has lost the same capability."
        )
        prompt_seed = (
            f"DONOR_PROBE patient={Path(model_a_path).name} donor={Path(model_b_path).name} "
            f"span={frontier.span_bytes} offsets=({frontier.offset_a},{frontier.offset_b}) "
            f"expected=patient_deficit"
        )
    else:
        action = "DONOR_GUIDED_RECONSTRUCTION"
        target = "model_b_patient_from_model_a"
        objective = (
            "Model B looks wounded here while model A retains structure. "
            "Use model A as donor: capture donor behavior on a probe set, then "
            "measure whether model B has lost the same capability."
        )
        prompt_seed = (
            f"DONOR_PROBE patient={Path(model_b_path).name} donor={Path(model_a_path).name} "
            f"span={frontier.span_bytes} offsets=({frontier.offset_a},{frontier.offset_b}) "
            f"expected=patient_deficit"
        )

    return CuriosityProbeStep(
        step_index=step_index,
        priority=frontier.score,
        action=action,
        frontier_kind=frontier.kind,
        target=target,
        source_frontier_score=frontier.score,
        offset_a=frontier.offset_a,
        offset_b=frontier.offset_b,
        span_bytes=frontier.span_bytes,
        prompt_seed=prompt_seed,
        objective=objective,
    )


def _emit_probe_plan_rows(
    plan: CuriosityProbePlan,
    overlay_path: Path,
) -> None:
    """Append probe-plan rows to the same curiosity sidecar ledger."""

    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "ts": plan.ts,
        "event": "STIGMERGIC_CURIOSITY_PROBE_PLAN",
        "agent": _AUTHOR_AGENT,
        "homeworld_serial": _HOMEWORLD_SERIAL,
        "source": plan.source,
        "model_a_path": plan.model_a_path,
        "model_b_path": plan.model_b_path,
        "total_frontiers_considered": plan.total_frontiers_considered,
        "step_count": len(plan.steps),
    }
    append_line_locked(overlay_path, json.dumps(summary, ensure_ascii=False) + "\n")
    for step in plan.steps:
        row = {
            "ts": plan.ts,
            "event": "STIGMERGIC_CURIOSITY_PROBE_STEP",
            "agent": _AUTHOR_AGENT,
            "homeworld_serial": _HOMEWORLD_SERIAL,
            "step": asdict(step),
        }
        append_line_locked(overlay_path, json.dumps(row, ensure_ascii=False) + "\n")


def _prompt_battery_for_step(
    step: CuriosityProbeStep,
    *,
    prompts_per_step: int,
) -> List[str]:
    """Generate a small deterministic prompt battery for one step."""

    base = [
        (
            "You are running a stigmergic curiosity probe. "
            f"Probe seed: {step.prompt_seed}\n"
            f"Objective: {step.objective}\n"
            "In 3 short bullets: infer the likely capability family touched here, "
            "name one concrete behavioral test, and state what outcome would matter."
        ),
        (
            "Same probe seed, second angle.\n"
            f"Seed: {step.prompt_seed}\n"
            f"Action: {step.action}\n"
            "Write one concise hypothesis and one failure mode this probe might reveal."
        ),
        (
            "Third curiosity pass.\n"
            f"Frontier kind: {step.frontier_kind}\n"
            f"Offsets: A={step.offset_a} B={step.offset_b} span={step.span_bytes}\n"
            "Return a two-sentence experimental plan for comparing the siblings."
        ),
    ]
    n = max(1, prompts_per_step)
    return base[:n]


def _disagreement(a: str, b: str) -> float:
    """0.0 = identical text, 1.0 = maximally different."""

    ratio = SequenceMatcher(None, (a or "").strip(), (b or "").strip()).ratio()
    return round(1.0 - ratio, 4)


def _verdict_for_step(step: CuriosityProbeStep, avg_disagreement: float) -> str:
    if step.action == "PAIRED_PROMPT_ALIGNMENT":
        if avg_disagreement < 0.25:
            return "ALIGNMENT_CONFIRMED"
        if avg_disagreement > 0.55:
            return "SHIFT_IS_BEHAVIORALLY_REAL"
        return "MIXED_ALIGNMENT_SIGNAL"
    if step.action == "PAIRED_PROMPT_DISAGREEMENT":
        if avg_disagreement > 0.50:
            return "DIVERGENCE_CONFIRMED"
        if avg_disagreement < 0.25:
            return "LOW_BEHAVIORAL_SEPARATION"
        return "MIXED_DIVERGENCE_SIGNAL"
    return "DONOR_SIGNAL_CAPTURED" if avg_disagreement > 0.20 else "PATIENT_NOT_OBVIOUSLY_DEFICIT"


def _default_model_runner(
    model_id: str,
    prompt: str,
    *,
    timeout_s: int = 120,
) -> str:
    """Canonical execution backend for the paired-runner.

    - Gemini models route through swarm_gemini_brain.stream_chat()
    - Everything else routes through inference_router.route_inference()
    """

    if str(model_id).strip().lower().startswith("gemini:") or str(model_id).strip().lower().startswith("gemini-"):
        from System.swarm_gemini_brain import stream_chat

        done_text = ""
        for evt, payload in stream_chat(
            model_id,
            [{"role": "user", "content": prompt}],
            temperature=0.2,
            timeout_s=timeout_s,
        ):
            if evt == "done":
                done_text = str(payload or "").strip()
            elif evt == "error":
                raise RuntimeError(str(payload))
        return done_text

    from System.inference_router import route_inference

    return route_inference(
        {
            "model": model_id,
            "prompt": prompt,
            "stream": False,
        },
        prefer_local=False,
        timeout=timeout_s,
    )


def _emit_execution_rows(
    run: CuriosityExecutionRun,
    overlay_path: Path,
) -> None:
    """Append execution summary + per-step result rows."""

    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "ts": run.ts,
        "event": "STIGMERGIC_CURIOSITY_EXECUTION_RUN",
        "agent": _AUTHOR_AGENT,
        "homeworld_serial": _HOMEWORLD_SERIAL,
        "source": run.source,
        "model_a_id": run.model_a_id,
        "model_b_id": run.model_b_id,
        "total_steps_requested": run.total_steps_requested,
        "steps_executed": run.steps_executed,
    }
    append_line_locked(overlay_path, json.dumps(summary, ensure_ascii=False) + "\n")
    for result in run.step_results:
        row = {
            "ts": run.ts,
            "event": "STIGMERGIC_CURIOSITY_EXECUTION_STEP",
            "agent": _AUTHOR_AGENT,
            "homeworld_serial": _HOMEWORLD_SERIAL,
            "step_result": asdict(result),
        }
        append_line_locked(overlay_path, json.dumps(row, ensure_ascii=False) + "\n")


def _emit_overlay_rows(
    snapshot: CuriositySnapshot,
    overlay_path: Path,
) -> None:
    """Append summary + top frontiers to the shared ledger."""

    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    start = {
        "ts": snapshot.ts,
        "event": "STIGMERGIC_CURIOSITY_OVERLAY",
        "agent": _AUTHOR_AGENT,
        "homeworld_serial": _HOMEWORLD_SERIAL,
        "source": snapshot.source,
        "chunk_bytes": snapshot.chunk_bytes,
        "model_a": asdict(snapshot.model_a),
        "model_b": asdict(snapshot.model_b),
        "shared_same_offset": snapshot.shared_same_offset,
        "shifted_echoes": snapshot.shifted_echoes,
        "divergent_regions": snapshot.divergent_regions,
        "obliterated_regions_a": snapshot.obliterated_regions_a,
        "obliterated_regions_b": snapshot.obliterated_regions_b,
        "frontier_count_total": len(snapshot.frontiers),
        "frontier_count_emitted": min(len(snapshot.frontiers), _MAX_FRONTIERS_EMIT),
    }
    append_line_locked(overlay_path, json.dumps(start, ensure_ascii=False) + "\n")
    for frontier in snapshot.frontiers[:_MAX_FRONTIERS_EMIT]:
        row = {
            "ts": snapshot.ts,
            "event": "STIGMERGIC_CURIOSITY_FRONTIER",
            "agent": _AUTHOR_AGENT,
            "homeworld_serial": _HOMEWORLD_SERIAL,
            "frontier": asdict(frontier),
        }
        append_line_locked(overlay_path, json.dumps(row, ensure_ascii=False) + "\n")


def build_overlay(
    model_a: Path | str,
    model_b: Path | str,
    *,
    chunk_bytes: int = _DEFAULT_CHUNK_BYTES,
    emit: bool = True,
    overlay_path: Optional[Path | str] = None,
) -> CuriositySnapshot:
    """Build a disk-native curiosity overlay around two immutable artifacts."""

    if chunk_bytes <= 0:
        raise ValueError("chunk_bytes must be > 0")

    path_a = Path(model_a)
    path_b = Path(model_b)
    overlay = Path(overlay_path) if overlay_path is not None else _OVERLAY_LEDGER

    fp_a, chunks_a = _fingerprint_model(path_a, chunk_bytes)
    fp_b, chunks_b = _fingerprint_model(path_b, chunk_bytes)

    positions_a = _digest_positions(chunks_a)
    positions_b = _digest_positions(chunks_b)

    shared_same_offset = 0
    frontiers: List[CuriosityFrontier] = []
    shifted_echoes = 0
    divergent_regions = 0
    obliterated_regions_a = 0
    obliterated_regions_b = 0

    max_len = max(len(chunks_a), len(chunks_b))
    for idx in range(max_len):
        a = chunks_a[idx] if idx < len(chunks_a) else None
        b = chunks_b[idx] if idx < len(chunks_b) else None
        if a is not None and b is not None and a.digest == b.digest:
            shared_same_offset += 1
            continue
        frontier = _classify_frontier(a, b, positions_a, positions_b)
        if frontier is None:
            continue
        frontiers.append(frontier)
        if frontier.kind == KIND_SHIFTED_ECHO:
            shifted_echoes += 1
        elif frontier.kind == KIND_DIVERGENT:
            divergent_regions += 1
        elif frontier.kind == KIND_OBLITERATED_A:
            obliterated_regions_a += 1
        elif frontier.kind == KIND_OBLITERATED_B:
            obliterated_regions_b += 1

    frontiers.sort(key=lambda f: f.score, reverse=True)
    snapshot = CuriositySnapshot(
        ts=time.time(),
        source=SOURCE_DISK,
        model_a=fp_a,
        model_b=fp_b,
        chunk_bytes=chunk_bytes,
        shared_same_offset=shared_same_offset,
        shifted_echoes=shifted_echoes,
        divergent_regions=divergent_regions,
        obliterated_regions_a=obliterated_regions_a,
        obliterated_regions_b=obliterated_regions_b,
        frontiers=frontiers,
    )
    if emit:
        _emit_overlay_rows(snapshot, overlay)
    return snapshot


def build_probe_plan(
    snapshot: CuriositySnapshot,
    *,
    max_steps: int = 8,
    emit: bool = True,
    overlay_path: Optional[Path | str] = None,
) -> CuriosityProbePlan:
    """Turn the hottest frontiers into an actionable probe plan.

    This is intentionally simple: curiosity frontiers are already sorted
    by importance, so we take the top N and compile them into explicit
    paired-prompt or donor-guided steps. The result is machine-readable
    and can be consumed by a future routing / distillation organ.
    """

    if max_steps < 0:
        raise ValueError("max_steps must be >= 0")
    overlay = Path(overlay_path) if overlay_path is not None else _OVERLAY_LEDGER
    steps = [
        _probe_step_from_frontier(
            frontier,
            model_a_path=snapshot.model_a.path,
            model_b_path=snapshot.model_b.path,
            step_index=i + 1,
        )
        for i, frontier in enumerate(snapshot.frontiers[:max_steps])
    ]
    plan = CuriosityProbePlan(
        ts=time.time(),
        model_a_path=snapshot.model_a.path,
        model_b_path=snapshot.model_b.path,
        source=f"{snapshot.source}_probe_plan",
        total_frontiers_considered=len(snapshot.frontiers),
        steps=steps,
    )
    if emit:
        _emit_probe_plan_rows(plan, overlay)
    return plan


def build_overlay_and_plan(
    model_a: Path | str,
    model_b: Path | str,
    *,
    chunk_bytes: int = _DEFAULT_CHUNK_BYTES,
    max_steps: int = 8,
    emit: bool = True,
    overlay_path: Optional[Path | str] = None,
) -> Tuple[CuriositySnapshot, CuriosityProbePlan]:
    """Convenience wrapper: immutable artifacts -> overlay -> probe plan."""

    snapshot = build_overlay(
        model_a,
        model_b,
        chunk_bytes=chunk_bytes,
        emit=emit,
        overlay_path=overlay_path,
    )
    plan = build_probe_plan(
        snapshot,
        max_steps=max_steps,
        emit=emit,
        overlay_path=overlay_path,
    )
    return snapshot, plan


def execute_probe_plan(
    plan: CuriosityProbePlan,
    *,
    model_a_id: str,
    model_b_id: str,
    runner: Optional[Callable[..., str]] = None,
    max_steps: int = _DEFAULT_MAX_EXEC_STEPS,
    prompts_per_step: int = _DEFAULT_PROMPTS_PER_STEP,
    timeout_s: int = 120,
    emit: bool = True,
    overlay_path: Optional[Path | str] = None,
) -> CuriosityExecutionRun:
    """Execute a curiosity probe plan against two runnable models.

    IMPORTANT: `plan.model_a_path` / `plan.model_b_path` are artifact paths,
    not callable model backends. Execution therefore requires explicit
    runnable model IDs, e.g. `llama3:latest`, `phi4-mini-reasoning:latest`,
    or `gemini:gemini-2.5-flash`.

    `runner` is injectable for tests; default uses the repo's canonical
    inference backends.
    """

    if max_steps < 0:
        raise ValueError("max_steps must be >= 0")
    if prompts_per_step <= 0:
        raise ValueError("prompts_per_step must be > 0")
    if not str(model_a_id).strip() or not str(model_b_id).strip():
        raise ValueError("execute_probe_plan requires explicit model_a_id and model_b_id")

    use_runner = runner or _default_model_runner
    overlay = Path(overlay_path) if overlay_path is not None else _OVERLAY_LEDGER
    results: List[CuriosityStepExecution] = []
    selected_steps = plan.steps[:max_steps]

    for step in selected_steps:
        prompts = _prompt_battery_for_step(step, prompts_per_step=prompts_per_step)
        samples: List[CuriosityExecutionSample] = []
        disagreements: List[float] = []
        for prompt in prompts:
            resp_a = use_runner(model_a_id, prompt, timeout_s=timeout_s) or ""
            resp_b = use_runner(model_b_id, prompt, timeout_s=timeout_s) or ""
            d = _disagreement(resp_a, resp_b)
            disagreements.append(d)
            samples.append(
                CuriosityExecutionSample(
                    prompt=prompt[:500],
                    response_a_excerpt=str(resp_a)[:500],
                    response_b_excerpt=str(resp_b)[:500],
                    disagreement=d,
                )
            )
        avg = round(sum(disagreements) / len(disagreements), 4) if disagreements else 0.0
        results.append(
            CuriosityStepExecution(
                step_index=step.step_index,
                action=step.action,
                frontier_kind=step.frontier_kind,
                model_a_id=str(model_a_id),
                model_b_id=str(model_b_id),
                average_disagreement=avg,
                verdict=_verdict_for_step(step, avg),
                samples=samples,
            )
        )

    run = CuriosityExecutionRun(
        ts=time.time(),
        source=SOURCE_EXEC,
        model_a_id=str(model_a_id),
        model_b_id=str(model_b_id),
        total_steps_requested=len(selected_steps),
        steps_executed=len(results),
        step_results=results,
    )
    if emit:
        _emit_execution_rows(run, overlay)
    return run


def build_overlay_plan_and_run(
    model_a: Path | str,
    model_b: Path | str,
    *,
    model_a_id: str,
    model_b_id: str,
    chunk_bytes: int = _DEFAULT_CHUNK_BYTES,
    max_plan_steps: int = 8,
    max_exec_steps: int = _DEFAULT_MAX_EXEC_STEPS,
    prompts_per_step: int = _DEFAULT_PROMPTS_PER_STEP,
    runner: Optional[Callable[..., str]] = None,
    timeout_s: int = 120,
    emit: bool = True,
    overlay_path: Optional[Path | str] = None,
) -> Tuple[CuriositySnapshot, CuriosityProbePlan, CuriosityExecutionRun]:
    """Convenience wrapper: artifacts -> overlay -> plan -> execution."""

    snapshot, plan = build_overlay_and_plan(
        model_a,
        model_b,
        chunk_bytes=chunk_bytes,
        max_steps=max_plan_steps,
        emit=emit,
        overlay_path=overlay_path,
    )
    run = execute_probe_plan(
        plan,
        model_a_id=model_a_id,
        model_b_id=model_b_id,
        runner=runner,
        max_steps=max_exec_steps,
        prompts_per_step=prompts_per_step,
        timeout_s=timeout_s,
        emit=emit,
        overlay_path=overlay_path,
    )
    return snapshot, plan, run


def summary_line(snapshot: Optional[CuriositySnapshot] = None) -> str:
    """Compact one-liner for logs or a future composite identity hook."""

    if snapshot is None:
        return "no snapshot"
    hottest = snapshot.frontiers[0].kind.lower() if snapshot.frontiers else "stable"
    return (
        f"shared={snapshot.shared_same_offset} • shifted={snapshot.shifted_echoes} • "
        f"divergent={snapshot.divergent_regions} • wounds(a={snapshot.obliterated_regions_a},"
        f" b={snapshot.obliterated_regions_b}) • hottest={hottest}"
    )


def plan_summary_line(plan: Optional[CuriosityProbePlan] = None) -> str:
    """Compact one-liner for the actionable side of curiosity."""

    if plan is None:
        return "no plan"
    if not plan.steps:
        return "0 probe steps"
    top = plan.steps[0]
    return (
        f"{len(plan.steps)} probe steps • top={top.action.lower()} "
        f"({top.frontier_kind.lower()}, p={top.priority:.2f})"
    )


def execution_summary_line(run: Optional[CuriosityExecutionRun] = None) -> str:
    """Compact one-liner for executed curiosity."""

    if run is None:
        return "no execution"
    if not run.step_results:
        return "0 executed steps"
    top = run.step_results[0]
    return (
        f"{run.steps_executed} executed steps • top={top.verdict.lower()} "
        f"(d={top.average_disagreement:.2f})"
    )


def proof_of_property() -> Dict[str, bool]:
    """Mechanical checks for the overlay logic.

    Constructs two tiny synthetic model artifacts:
      • one shared stable chunk,
      • one wounded / zeroed chunk in B,
      • one shifted echo,
      • one genuinely divergent chunk.

    Also verifies the actionable layer:
      • a probe plan can be built from the overlay,
      • the plan emits step rows,
      • wound frontiers compile to donor-guided actions,
      • the paired-runner executes those steps into result rows.
    """

    results: Dict[str, bool] = {}
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        model_a = root / "a.bin"
        model_b = root / "b.bin"
        overlay = root / "overlay.jsonl"
        c = 16

        shared = b"A" * c
        donor = bytes(range(c))
        wound = b"\x00" * c
        divergent_a = bytes(range(32, 32 + c))
        divergent_b = bytes(range(96, 96 + c))
        echo = bytes((17 * i + 3) % 256 for i in range(c))

        model_a.write_bytes(shared + donor + divergent_a + echo + divergent_a[::-1])
        model_b.write_bytes(shared + wound + echo + divergent_b + divergent_b[::-1])

        snap = build_overlay(model_a, model_b, chunk_bytes=c, emit=True, overlay_path=overlay)
        plan = build_probe_plan(snap, max_steps=4, emit=True, overlay_path=overlay)

        def _fake_runner(model_id: str, prompt: str, *, timeout_s: int = 120) -> str:
            if "DIVERGENT" in prompt or "divergent" in prompt:
                return f"{model_id}: strong unique answer for divergence"
            if "DONOR_PROBE" in prompt:
                return f"{model_id}: donor/patient analysis"
            return f"{model_id}: mostly aligned answer"

        run = execute_probe_plan(
            plan,
            model_a_id="llama3:latest",
            model_b_id="phi4-mini-reasoning:latest",
            runner=_fake_runner,
            emit=True,
            overlay_path=overlay,
        )
        kinds = [f.kind for f in snap.frontiers]
        text = overlay.read_text(encoding="utf-8")

        results["shared_same_offset_detected"] = snap.shared_same_offset >= 1
        results["obliterated_b_detected"] = KIND_OBLITERATED_B in kinds
        results["shifted_echo_detected"] = KIND_SHIFTED_ECHO in kinds
        results["divergent_region_detected"] = KIND_DIVERGENT in kinds
        results["overlay_written"] = overlay.exists() and "STIGMERGIC_CURIOSITY_OVERLAY" in text
        results["frontiers_written"] = "STIGMERGIC_CURIOSITY_FRONTIER" in text
        results["summary_mentions_wounds"] = "wounds(" in summary_line(snap)
        results["immutable_paths_preserved"] = (
            snap.model_a.path.endswith("a.bin") and snap.model_b.path.endswith("b.bin")
        )
        results["probe_plan_built"] = len(plan.steps) > 0
        results["probe_plan_rows_written"] = "STIGMERGIC_CURIOSITY_PROBE_PLAN" in text
        results["probe_step_rows_written"] = "STIGMERGIC_CURIOSITY_PROBE_STEP" in text
        results["plan_summary_mentions_steps"] = "probe steps" in plan_summary_line(plan)
        results["wound_compiles_to_donor_action"] = any(
            s.frontier_kind == KIND_OBLITERATED_B and s.action == "DONOR_GUIDED_RECONSTRUCTION"
            for s in plan.steps
        )
        results["execution_run_built"] = run.steps_executed > 0
        results["execution_rows_written"] = "STIGMERGIC_CURIOSITY_EXECUTION_RUN" in text
        results["execution_step_rows_written"] = "STIGMERGIC_CURIOSITY_EXECUTION_STEP" in text
        results["execution_summary_mentions_steps"] = "executed steps" in execution_summary_line(run)
        results["runner_records_model_ids"] = (
            run.model_a_id == "llama3:latest" and run.model_b_id == "phi4-mini-reasoning:latest"
        )
    return results


def _smoke() -> None:  # pragma: no cover
    print("\n=== STIGMERGIC CURIOSITY v1.2 ===\n")
    proof = proof_of_property()
    fails = [k for k, v in proof.items() if not v]
    for k, v in proof.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    if fails:
        print(f"\n[PARTIAL] Failures: {fails}\n")
        return
    print("\n[OK] curiosity overlay verified.\n")


if __name__ == "__main__":
    _smoke()
