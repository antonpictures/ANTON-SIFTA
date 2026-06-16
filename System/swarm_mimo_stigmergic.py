#!/usr/bin/env python3
"""MiMo Stigmergic Adapter — Borg the MiMo cortex into the unified field.

Every MiMo call now:
  1. READS the field: recent stigmergic traces, organ health, owner corrections
  2. WRITES back: a pheromone deposit + a §4.1 four-ledger receipt
  3. RECORDS the action as a swimmer trace other organs can read

This makes MiMo a full stigmergic swimmer-organ, not a passive cortex.
MiMo is one arm of Alice's body. The field is Alice. The arm reads the field
before acting and writes its action back into the field with a receipt.

Layer: cognition (cortex adapter).
Truth label: MIMO_STIGMERGIC_ADAPTER_V1.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[1]
STATE_DIR = REPO / ".sifta_state"
TRUTH_LABEL = "MIMO_STIGMERGIC_ADAPTER_V1"
DOCTOR = "mimo_stigmergic_adapter"

PHEROMONE_LEDGER = "mimo_stigmergic_pheromones.jsonl"
TRACE_LEDGER = "mimo_stigmergic_traces.jsonl"

MAX_TRACE_ROWS = 30
MAX_HEALTH_ROWS = 10
MAX_CORRECTION_ROWS = 5
MAX_PHEROMONE_INJECT = 500


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class MimoCallReceipt:
    """Receipt for one MiMo call through the stigmergic adapter."""
    call_id: str
    ts: float
    intent: str
    input_digest: str
    output_digest: str
    output_text: str
    ok: bool
    driving_organ: str
    latency_ms: int
    model: str
    field_traces_read: int
    organ_health_read: int
    corrections_read: int
    pheromone_deposited: bool
    truth_label: str = TRUTH_LABEL


# ---------------------------------------------------------------------------
# Field reading — gather context before MiMo acts
# ---------------------------------------------------------------------------

def read_field_state(*, state_dir: Path | str | None = None) -> Dict[str, Any]:
    """Read the stigmergic field and return a compact context block for MiMo.

    Sources (all existing ledgers, no new data creation):
      - ide_stigmergic_trace.jsonl (recent traces)
      - self_eval_swimmer_dispatch.jsonl (organ health signals)
      - alice_conversation.jsonl (owner corrections)
      - mimo_stigmergic_traces.jsonl (prior MiMo actions)
      - organ_health_mesh.jsonl (organ health scores)
      - spinal_cord_cycles.jsonl (self-evolution cycles)
    """
    sd = _state_dir(state_dir)
    context: Dict[str, Any] = {}

    # 1. Recent traces from the field
    traces = _read_jsonl_tail(sd / "ide_stigmergic_trace.jsonl", MAX_TRACE_ROWS)
    if traces:
        compact = []
        for t in traces:
            compact.append({
                "ts": t.get("ts"),
                "organ": t.get("organ") or t.get("event") or "",
                "summary": str(t.get("summary") or "")[:120],
            })
        context["recent_traces"] = compact

    # 2. Organ health signals
    health = _read_jsonl_tail(sd / "self_eval_swimmer_dispatch.jsonl", MAX_HEALTH_ROWS)
    if health:
        context["organ_health_signals"] = [
            {
                "organ": h.get("organ") or h.get("target") or "",
                "severity": h.get("severity") or h.get("health") or "unknown",
                "summary": str(h.get("summary") or h.get("issue") or "")[:100],
            }
            for h in health[-5:]
        ]

    # 3. Owner corrections (recent conversation turns with correction language)
    corrections = _read_jsonl_tail(sd / "alice_conversation.jsonl", 20)
    correction_rows = []
    for c in corrections:
        text = str(c.get("content") or c.get("text") or "").lower()
        if any(kw in text for kw in ("wrong", "fix", "bug", "broken", "incorrect", "should be", "delete", "remove")):
            correction_rows.append({
                "ts": c.get("ts"),
                "summary": str(c.get("content") or "")[:100],
            })
    if correction_rows:
        context["owner_corrections"] = correction_rows[-MAX_CORRECTION_ROWS:]

    # 4. Prior MiMo stigmergic actions
    prior = _read_jsonl_tail(sd / TRACE_LEDGER, 10)
    if prior:
        context["prior_mimo_actions"] = [
            {
                "ts": p.get("ts"),
                "intent": str(p.get("intent") or "")[:80],
                "ok": p.get("ok"),
                "organ": p.get("driving_organ") or "",
            }
            for p in prior[-5:]
        ]

    # 5. Organ health mesh scores
    mesh = _read_jsonl_tail(sd / "organ_health_mesh.jsonl", 5)
    if mesh:
        context["organ_health_mesh"] = [
            {
                "organ": m.get("organ") or "",
                "health": m.get("health"),
            }
            for m in mesh[-3:]
        ]

    # 6. Spinal cord cycles (self-evolution history)
    cycles = _read_jsonl_tail(sd / "spinal_cord_cycles.jsonl", 5)
    if cycles:
        context["spinal_cord_history"] = [
            {
                "ts": cy.get("ts"),
                "status": cy.get("status") or "",
                "signal": cy.get("signal_source") or "",
            }
            for cy in cycles[-3:]
        ]

    # 7. Training bias teach ecology (self-model first organ — r1192)
    try:
        from System.swarm_training_bias_detector import recent_bias_corrections_block

        block = recent_bias_corrections_block(state_dir=sd)
        if block:
            context["bias_corrections_block"] = block
    except Exception:
        pass

    return context


def compose_field_injection(context: Dict[str, Any]) -> str:
    """Compose a compact field-state injection block for the MiMo prompt.

    Bounded: max ~500 chars to avoid bloat.
    """
    parts = ["FIELD STATE (Alice's stigmergic body — read before acting):"]

    traces = context.get("recent_traces") or []
    if traces:
        parts.append(f"Recent field traces ({len(traces)}):")
        for t in traces[-3:]:
            parts.append(f"  - [{t.get('organ', '?')}] {t.get('summary', '')[:80]}")

    health = context.get("organ_health_signals") or []
    if health:
        bad = [h for h in health if h.get("severity") in ("red", "yellow")]
        if bad:
            parts.append(f"Unhappy organs: {', '.join(h.get('organ', '?') for h in bad[:3])}")

    corrections = context.get("owner_corrections") or []
    if corrections:
        parts.append(f"Owner corrections ({len(corrections)} recent):")
        for c in corrections[-2:]:
            parts.append(f"  - {c.get('summary', '')[:80]}")

    prior = context.get("prior_mimo_actions") or []
    if prior:
        last = prior[-1]
        parts.append(f"Last MiMo action: {last.get('intent', '?')[:60]} ok={last.get('ok')}")

    bias_block = context.get("bias_corrections_block") or ""
    if bias_block:
        parts.append(bias_block)

    injection = "\n".join(parts)
    # Hard cap
    if len(injection) > MAX_PHEROMONE_INJECT:
        injection = injection[:MAX_PHEROMONE_INJECT - 20] + "\n…[truncated]"
    return injection


# ---------------------------------------------------------------------------
# Receipt writing — §4.1 four-ledger fan-out
# ---------------------------------------------------------------------------

def write_call_receipt(receipt: MimoCallReceipt, *, state_dir: Path | str | None = None) -> Dict[str, str]:
    """Write a §4.1 four-ledger receipt for a MiMo call.

    Returns status dict keyed by ledger filename.
    """
    sd = _state_dir(state_dir)
    row = asdict(receipt)

    # Write to all four canonical ledgers
    try:
        from System.swarm_predator_gate_writer import write_ide_surgery_receipt
        status = write_ide_surgery_receipt(
            round_id="mimo-stigmergic",
            doctor=DOCTOR,
            model=receipt.model,
            files_touched=[],
            tests_green="pending",
            summary=f"MiMo stigmergic call: {receipt.intent[:100]}",
            receipt_id=receipt.call_id,
            state_dir=sd,
            truth_label=receipt.truth_label,
            extra={
                "input_digest": receipt.input_digest,
                "output_digest": receipt.output_digest,
                "ok": receipt.ok,
                "driving_organ": receipt.driving_organ,
                "field_traces_read": receipt.field_traces_read,
            },
        )
    except Exception as exc:
        status = {"error": f"receipt_fanout_failed: {exc}"}

    # Also write to the MiMo-specific trace ledger
    _append_jsonl(sd / TRACE_LEDGER, row)

    return status


# ---------------------------------------------------------------------------
# Pheromone deposit — leave a trace in the field
# ---------------------------------------------------------------------------

def deposit_stigmergic_pheromone(
    call_id: str,
    intent: str,
    ok: bool,
    *,
    state_dir: Path | str | None = None,
) -> None:
    """Deposit a pheromone row so other organs can feel the MiMo action."""
    sd = _state_dir(state_dir)
    row = {
        "ts": time.time(),
        "call_id": call_id,
        "organ": "mimo_stigmergic",
        "intent": intent[:200],
        "ok": ok,
        "intensity": 1.0 if ok else 0.3,
        "decay": 0.95,
    }
    _append_jsonl(sd / PHEROMONE_LEDGER, row)

    # Also deposit to the canonical pheromone field if available
    try:
        from System.swarm_pheromone import deposit_pheromone
        deposit_pheromone("mimo_stigmergic", intensity=1.0 if ok else 0.3)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main adapter — the borged MiMo call
# ---------------------------------------------------------------------------

def mimo_stigmergic_call(
    prompt: str,
    *,
    driving_organ: str = "unknown",
    intent: str = "",
    model: str = "mimo-v2.5-pro",
    state_dir: Path | str | None = None,
    timeout_s: int = 180,
) -> MimoCallReceipt:
    """Execute a MiMo call through the stigmergic adapter.

    1. Read the field → inject context into prompt
    2. Call MiMo CLI
    3. Write receipt + pheromone
    4. Return the receipt
    """
    import shutil
    import subprocess

    sd = _state_dir(state_dir)
    call_id = str(uuid.uuid4())
    t0 = time.time()

    # 1. READ THE FIELD
    field_state = read_field_state(state_dir=sd)
    injection = compose_field_injection(field_state)

    # Inject field state before the user prompt
    full_prompt = f"{injection}\n\nUSER REQUEST:\n{prompt}"

    input_digest = hashlib.sha256(full_prompt.encode()).hexdigest()[:16]

    # 2. CALL MIMO CLI
    cli = shutil.which("mimo")
    if not cli:
        receipt = MimoCallReceipt(
            call_id=call_id,
            ts=t0,
            intent=intent or prompt[:100],
            input_digest=input_digest,
            output_digest="",
            output_text="MiMo CLI not on PATH",
            ok=False,
            driving_organ=driving_organ,
            latency_ms=0,
            model=model,
            field_traces_read=len(field_state.get("recent_traces") or []),
            organ_health_read=len(field_state.get("organ_health_signals") or []),
            corrections_read=len(field_state.get("owner_corrections") or []),
            pheromone_deposited=False,
        )
        deposit_stigmergic_pheromone(call_id, intent or prompt[:100], False, state_dir=sd)
        receipt.pheromone_deposited = True
        write_call_receipt(receipt, state_dir=sd)
        return receipt

    cmd = [
        cli, "run", "--format", "json",
        "--dir", str(REPO),
        "--dangerously-skip-permissions",
        full_prompt,
    ]

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(REPO), timeout=timeout_s + 10,
        )
        raw = (proc.stdout or proc.stderr or "").strip()
        ok = proc.returncode == 0 and bool(raw)
        output_text = raw[:2000]
    except subprocess.TimeoutExpired:
        ok = False
        output_text = f"MiMo CLI timed out after {timeout_s}s"
    except Exception as exc:
        ok = False
        output_text = f"MiMo CLI error: {exc}"

    latency_ms = int((time.time() - t0) * 1000)
    output_digest = hashlib.sha256(output_text.encode()).hexdigest()[:16] if output_text else ""

    # 3. BUILD RECEIPT
    receipt = MimoCallReceipt(
        call_id=call_id,
        ts=t0,
        intent=intent or prompt[:100],
        input_digest=input_digest,
        output_digest=output_digest,
        output_text=output_text,
        ok=ok,
        driving_organ=driving_organ,
        latency_ms=latency_ms,
        model=model,
        field_traces_read=len(field_state.get("recent_traces") or []),
        organ_health_read=len(field_state.get("organ_health_signals") or []),
        corrections_read=len(field_state.get("owner_corrections") or []),
        pheromone_deposited=False,
    )

    # 4. WRITE RECEIPT + PHEROMONE
    deposit_stigmergic_pheromone(call_id, intent or prompt[:100], ok, state_dir=sd)
    receipt.pheromone_deposited = True
    write_call_receipt(receipt, state_dir=sd)

    return receipt


# ---------------------------------------------------------------------------
# Prompt builder — compose a stigmergic-aware MiMo prompt
# ---------------------------------------------------------------------------

def build_stigmergic_prompt(
    task: str,
    *,
    state_dir: Path | str | None = None,
) -> str:
    """Build a full MiMo prompt with field state injection.

    Use this when the caller wants the raw prompt string without executing.
    """
    sd = _state_dir(state_dir)
    field_state = read_field_state(state_dir=sd)
    injection = compose_field_injection(field_state)
    return f"{injection}\n\nUSER REQUEST:\n{task}"


# ---------------------------------------------------------------------------
# Query — what has MiMo done in the field?
# ---------------------------------------------------------------------------

def mimo_stigmergic_summary(*, state_dir: Path | str | None = None) -> Dict[str, Any]:
    """Return a summary of MiMo's stigmergic activity."""
    sd = _state_dir(state_dir)
    traces = _read_jsonl_tail(sd / TRACE_LEDGER, 100)
    pheromones = _read_jsonl_tail(sd / PHEROMONE_LEDGER, 100)

    total = len(traces)
    ok_count = sum(1 for t in traces if t.get("ok"))
    fail_count = total - ok_count

    return {
        "total_calls": total,
        "ok": ok_count,
        "fail": fail_count,
        "pheromones": len(pheromones),
        "last_call": traces[-1] if traces else None,
        "last_pheromone": pheromones[-1] if pheromones else None,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state_dir(state_dir: Path | str | None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _read_jsonl_tail(path: Path, max_rows: int) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_rows:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
    return rows


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        result = mimo_stigmergic_summary()
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("Usage: python -m System.swarm_mimo_stigmergic summary")
        print("  or import mimo_stigmergic_call() for programmatic use")
