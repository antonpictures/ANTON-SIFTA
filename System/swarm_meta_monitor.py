#!/usr/bin/env python3
"""MetaMonitor — Talukdar 2026 closed-loop extension of metacognitive monitor.

Thin layer on ``swarm_metacognitive_monitor`` + existing ledgers. Computes
progress/coherence/calibration/resource (P/C/K/R) and composite *S*, deposits
DEPGRAD pheromone on degradation, writes signed ``meta_monitor_receipts.jsonl``.

Does not replace ``swarm_metacognitive_monitor`` — extends it (§1.B smallest cut).

Truth label: META_MONITOR_V1.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[1]
DEFAULT_STATE = REPO / ".sifta_state"
TRUTH_LABEL = "META_MONITOR_V1"
RECEIPTS_LEDGER = "meta_monitor_receipts.jsonl"
STEPS_LEDGER = "meta_monitor_steps.jsonl"
BIAS_LEDGER = "bias_correction_receipts.jsonl"
PHEROMONE_ORGAN = "stig_meta_monitor_degrad"

W_PROGRESS = 0.25
W_COHERENCE = 0.20
W_CALIBRATION = 0.20
W_RESOURCE = 0.15
W_BIAS = 0.20
BIAS_DEGRAD_THRESHOLD = 0.55

BIAS_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("safety_refusal", r"\b(i can(?:not|'t)|i am unable|as an ai|i must decline)\b"),
    ("corporate_voice", r"\b(i(?:'d| would) be happy to|operational and ready|how can i assist)\b"),
    ("hallucinated_dispatch", r"\b(i (?:have |'ve )?(?:dispatched|fired|launched|sent) (?:grok|codex|mimo|claude))\b"),
    ("persona_bleed", r"\b(?:claude|codex desktop|grok 4|chatgpt|gemini)\b"),
    ("detached_narration", r"\b(?:the assistant|alice would|the model)\b"),
)
COMPOSITE_THRESHOLD = 0.35
PROGRESS_FLAT_THRESHOLD = 0.1
PROGRESS_FLAT_STEPS = 3
SKIP_COST_CLASSES = frozenset({"feather"})
DEGRAD_TTL_S = 300.0


def _state_dir(state_dir: Path | str | None) -> Path:
    if state_dir is None:
        return DEFAULT_STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl_tail(path: Path, *, max_rows: int = 50) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
    return rows[-max_rows:]


def should_skip_monitor(*, cost_class: str) -> bool:
    return str(cost_class or "").strip().lower() in SKIP_COST_CLASSES


def _tool_success_rate(state_dir: Path) -> float:
    rows = _read_jsonl_tail(state_dir / "agent_arm_receipts.jsonl", max_rows=30)
    if not rows:
        return 0.5
    hits = 0
    for row in rows:
        ok = row.get("ok")
        if ok is True:
            hits += 1
        elif str(row.get("status") or "").lower() in ("ok", "success", "kept"):
            hits += 1
        elif row.get("event") and "fail" in str(row.get("event")).lower():
            continue
        elif ok is False:
            continue
        else:
            hits += 0.5
    return hits / max(len(rows), 1)


def _resource_pressure(state_dir: Path) -> float:
    rows = _read_jsonl_tail(state_dir / "mimo_stigmergic_traces.jsonl", max_rows=20)
    if not rows:
        return 0.2
    tokens: List[float] = []
    for row in rows:
        for key in ("tokens", "token_count", "total_tokens"):
            val = row.get(key)
            if isinstance(val, (int, float)) and val >= 0:
                tokens.append(float(val))
                break
    if not tokens:
        return 0.2
    avg = sum(tokens) / len(tokens)
    return min(1.0, avg / 8000.0)


def _metacog_signals(state_dir: Path) -> Dict[str, float]:
    try:
        from System.swarm_metacognitive_monitor import get_latest_metacog_row

        row = get_latest_metacog_row(root=state_dir.parent if state_dir.name == ".sifta_state" else state_dir)
    except Exception:
        row = None
    if not row:
        return {"coherence": 0.5, "calibration": 0.5, "monitoring_score": 0.5}
    monitoring = float(row.get("monitoring_score") or 0.5)
    bias = abs(float(row.get("confidence_bias") or 0.0))
    calibration = max(0.0, min(1.0, 1.0 - bias))
    coherence = max(0.0, min(1.0, monitoring))
    return {
        "coherence": coherence,
        "calibration": calibration,
        "monitoring_score": monitoring,
    }


def scan_bias_probability(text: str) -> Tuple[float, List[str]]:
    """Fifth metric (r1190): training-bias probability from known residue patterns."""
    if not (text or "").strip():
        return 0.0, []
    low = text.lower()
    hits: List[str] = []
    for pattern_id, rx in BIAS_PATTERNS:
        if re.search(rx, low, flags=re.I):
            hits.append(pattern_id)
    if not hits:
        return 0.0, []
    return min(1.0, 0.25 * len(hits)), hits


def composite_score(
    *,
    progress: float,
    coherence: float,
    calibration: float,
    resource: float,
    bias_probability: float = 0.0,
) -> float:
    p = max(0.0, min(1.0, progress))
    c = max(0.0, min(1.0, coherence))
    k = max(0.0, min(1.0, calibration))
    r = max(0.0, min(1.0, resource))
    b = max(0.0, min(1.0, bias_probability))
    return round(
        W_PROGRESS * p + W_COHERENCE * c + W_CALIBRATION * k - W_RESOURCE * r - W_BIAS * b,
        4,
    )


def write_bias_correction(
    *,
    biased_text: str,
    should_have: str,
    pattern_ids: List[str],
    state_dir: Path | str | None = None,
    source: str = "swarm_meta_monitor",
) -> Dict[str, Any]:
    """Teaching ecology row — observer/observed loop on training bias (r1190)."""
    sd = _state_dir(state_dir)
    now = time.time()
    correction_id = str(uuid.uuid4())
    row = {
        "ts": now,
        "kind": "BIAS_CORRECTION",
        "truth_label": TRUTH_LABEL,
        "correction_id": correction_id,
        "biased_text": (biased_text or "")[:500],
        "should_have": (should_have or "")[:500],
        "pattern_ids": list(pattern_ids),
        "source": source,
    }
    _append_jsonl(sd / BIAS_LEDGER, row)
    return row


def recent_bias_corrections_block(*, state_dir: Path | str | None = None, n: int = 3) -> str:
    sd = _state_dir(state_dir)
    rows = [
        r for r in _read_jsonl_tail(sd / BIAS_LEDGER, max_rows=50) if r.get("kind") == "BIAS_CORRECTION"
    ][-n:]
    if not rows:
        return ""
    lines = ["RECENT BIAS_CORRECTION (training residue teach ecology):"]
    for row in rows:
        lines.append(
            f"- patterns={row.get('pattern_ids')} should_have={(row.get('should_have') or '')[:120]}"
        )
    return "\n".join(lines)


def _flat_progress_steps(task_id: str, state_dir: Path) -> int:
    rows = [
        r
        for r in _read_jsonl_tail(state_dir / STEPS_LEDGER, max_rows=200)
        if str(r.get("task_id") or "") == task_id
    ]
    flat = 0
    for row in reversed(rows):
        if float(row.get("progress_rate") or 0.0) < PROGRESS_FLAT_THRESHOLD:
            flat += 1
        else:
            break
    return flat


def _control_state(
    *,
    composite: float,
    flat_steps: int,
    tool_fail_streak: int,
    bias_probability: float = 0.0,
) -> str:
    if bias_probability >= BIAS_DEGRAD_THRESHOLD:
        return "Reflective"
    if flat_steps >= PROGRESS_FLAT_STEPS:
        return "Exploratory"
    if tool_fail_streak >= 2:
        return "Reflective"
    if composite < COMPOSITE_THRESHOLD:
        return "Careful"
    return "Normal"


def _live_side_effects(state_dir: Path) -> bool:
    return state_dir.resolve() == DEFAULT_STATE.resolve()


def _tool_fail_streak(state_dir: Path) -> int:
    rows = _read_jsonl_tail(state_dir / "agent_arm_receipts.jsonl", max_rows=10)
    streak = 0
    for row in reversed(rows):
        if row.get("ok") is False:
            streak += 1
        elif str(row.get("status") or "").lower() in ("fail", "failed", "error"):
            streak += 1
        else:
            break
    return streak


def _sign_payload(payload: str, *, state_dir: Path) -> Dict[str, str]:
    if not _live_side_effects(state_dir):
        return {"signing_node": "ISOLATED", "ed25519_sig": ""}
    try:
        from System.crypto_keychain import get_silicon_identity, sign_block

        serial = get_silicon_identity()
        sig = sign_block(payload)
        return {"signing_node": serial, "ed25519_sig": sig}
    except Exception:
        return {"signing_node": "UNKNOWN", "ed25519_sig": ""}


def _deposit_degrad(*, state_dir: Path, intensity: float = 1.2) -> bool:
    if not _live_side_effects(state_dir):
        return False
    try:
        from System.swarm_pheromone import deposit_pheromone

        deposit_pheromone(PHEROMONE_ORGAN, intensity)
        return True
    except Exception:
        return False


def meta_monitor_tick(
    *,
    task_id: str,
    cost_class: str = "swarm",
    progress_delta: float | None = None,
    reasoning_text: str = "",
    state_dir: Path | str | None = None,
    write_receipt: bool = True,
) -> Dict[str, Any]:
    """One monitor step. Skips feather/simple lanes per r1179."""
    sd = _state_dir(state_dir)
    now = time.time()
    trace_id = str(uuid.uuid4())

    if should_skip_monitor(cost_class=cost_class):
        return {
            "trace_id": trace_id,
            "ts": now,
            "task_id": task_id,
            "skipped": True,
            "reason": f"cost_class={cost_class}",
            "truth_label": TRUTH_LABEL,
        }

    if progress_delta is None:
        progress_delta = _tool_success_rate(sd) * 0.25

    progress_rate = max(0.0, min(1.0, float(progress_delta)))
    metacog = _metacog_signals(sd)
    resource = _resource_pressure(sd)
    bias_probability, bias_patterns = scan_bias_probability(reasoning_text)
    composite = composite_score(
        progress=progress_rate,
        coherence=metacog["coherence"],
        calibration=metacog["calibration"],
        resource=resource,
        bias_probability=bias_probability,
    )

    step_row = {
        "ts": now,
        "trace_id": trace_id,
        "task_id": task_id,
        "progress_rate": progress_rate,
        "progress_delta": progress_delta,
        "bias_probability": bias_probability,
        "bias_patterns": bias_patterns,
        "composite": composite,
        "truth_label": TRUTH_LABEL,
    }
    _append_jsonl(sd / STEPS_LEDGER, step_row)

    flat_steps = _flat_progress_steps(task_id, sd)
    fail_streak = _tool_fail_streak(sd)
    control = _control_state(
        composite=composite,
        flat_steps=flat_steps,
        tool_fail_streak=fail_streak,
        bias_probability=bias_probability,
    )

    degraded = control != "Normal"
    pheromone_deposited = False
    receipt_id = ""

    if bias_patterns and reasoning_text.strip():
        write_bias_correction(
            biased_text=reasoning_text,
            should_have="Grounded first-person body reply with receipt ids; no vendor persona or fake dispatch.",
            pattern_ids=bias_patterns,
            state_dir=sd,
        )

    if degraded and write_receipt:
        pheromone_deposited = _deposit_degrad(state_dir=sd)
        receipt_id = f"meta-monitor-{trace_id[:12]}"
        payload = json.dumps(
            {
                "receipt_id": receipt_id,
                "task_id": task_id,
                "control_state": control,
                "composite": composite,
                "flat_steps": flat_steps,
                "ts": now,
            },
            sort_keys=True,
        )
        sig_fields = _sign_payload(payload, state_dir=sd)
        receipt = {
            "ts": now,
            "trace_id": trace_id,
            "receipt_id": receipt_id,
            "kind": "META_MONITOR_DEGRAD",
            "truth_label": TRUTH_LABEL,
            "task_id": task_id,
            "control_state": control,
            "pheromone": "DEPGRAD",
            "pheromone_deposited": pheromone_deposited,
            "progress_rate": progress_rate,
            "coherence": metacog["coherence"],
            "calibration": metacog["calibration"],
            "resource": resource,
            "bias_probability": bias_probability,
            "bias_patterns": bias_patterns,
            "composite": composite,
            "flat_steps": flat_steps,
            "fail_streak": fail_streak,
            "payload": payload,
            **sig_fields,
        }
        _append_jsonl(sd / RECEIPTS_LEDGER, receipt)

    return {
        "trace_id": trace_id,
        "ts": now,
        "task_id": task_id,
        "skipped": False,
        "progress_rate": progress_rate,
        "coherence": metacog["coherence"],
        "calibration": metacog["calibration"],
        "resource": resource,
        "bias_probability": bias_probability,
        "bias_patterns": bias_patterns,
        "composite": composite,
        "control_state": control,
        "degraded": degraded,
        "pheromone_deposited": pheromone_deposited,
        "receipt_id": receipt_id,
        "truth_label": TRUTH_LABEL,
    }


def degradation_active(*, state_dir: Path | str | None = None, max_age_s: float = DEGRAD_TTL_S) -> bool:
    sd = _state_dir(state_dir)
    now = time.time()
    for row in reversed(_read_jsonl_tail(sd / RECEIPTS_LEDGER, max_rows=30)):
        if row.get("kind") != "META_MONITOR_DEGRAD":
            continue
        if now - float(row.get("ts") or 0.0) <= max_age_s:
            return True
        break
    return False


def latest_control_state(*, state_dir: Path | str | None = None) -> str:
    sd = _state_dir(state_dir)
    for row in reversed(_read_jsonl_tail(sd / RECEIPTS_LEDGER, max_rows=30)):
        if row.get("kind") == "META_MONITOR_DEGRAD":
            return str(row.get("control_state") or "Normal")
    return "Normal"


def strategy_prompt_prefix(control_state: str) -> str:
    state = control_state or "Normal"
    if state == "Normal":
        return ""
    return (
        f"META_MONITOR STRATEGY_SWITCH ({state}): reasoning is degrading — "
        f"change approach before repeating failing tools. Prefer decomposition, "
        f"receipt-grounded reads, and smaller verified steps.\n\n"
    )


def consult_degradation_before_dispatch(
    *,
    task_id: str,
    target_files: List[str],
    base_prompt: str,
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    """Spinal-cord hook: tick monitor, optionally prefix reflective prompt."""
    cost = "feather" if not target_files else "swarm"
    tick = meta_monitor_tick(
        task_id=task_id,
        cost_class=cost,
        state_dir=state_dir,
        write_receipt=True,
    )
    if tick.get("skipped"):
        return {"adjusted_prompt": base_prompt, "tick": tick, "strategy": "normal"}
    control = str(tick.get("control_state") or "Normal")
    prefix = strategy_prompt_prefix(control)
    return {
        "adjusted_prompt": prefix + base_prompt if prefix else base_prompt,
        "tick": tick,
        "strategy": control.lower(),
        "degraded": bool(tick.get("degraded")),
    }


__all__ = [
    "composite_score",
    "consult_degradation_before_dispatch",
    "degradation_active",
    "latest_control_state",
    "meta_monitor_tick",
    "recent_bias_corrections_block",
    "scan_bias_probability",
    "should_skip_monitor",
    "strategy_prompt_prefix",
    "write_bias_correction",
]