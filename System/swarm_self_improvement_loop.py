#!/usr/bin/env python3
"""Receipt-backed self-improvement promotion loop.

This closes the routine loop around training data, Fast Ask outcomes, LoRA
receipts, and primary cortex promotion without letting a broken adapter replace
the current multimodal Gemma4 cortex. It is conservative by default:
observe -> score -> receipt -> recommend; switching requires explicit opt-in.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]


_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
LEDGER_NAME = "self_improvement_loop.jsonl"
TRUTH_LABEL = "SIFTA_SELF_IMPROVEMENT_LOOP_V1"


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _hash_row(row: Mapping[str, Any]) -> str:
    clean = {k: v for k, v in row.items() if k != "receipt"}
    raw = json.dumps(clean, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _safe_lora_status() -> dict[str, Any]:
    try:
        from System.swarm_lora_runtime_receipt import lora_candidate_status

        status = lora_candidate_status()
        return dict(status) if isinstance(status, Mapping) else {"promotion_status": "UNKNOWN"}
    except Exception as exc:
        return {
            "candidate_model": "sifta-gemma4-alice-lora:latest",
            "promotion_ready": False,
            "promotion_status": "UNKNOWN",
            "promotion_blockers": [f"lora_status_error:{type(exc).__name__}"],
        }


def _safe_primary_truth() -> dict[str, Any]:
    try:
        from System.swarm_primary_cortex_switcher import current_primary_cortex_truth

        truth = current_primary_cortex_truth()
        return dict(truth) if isinstance(truth, Mapping) else {}
    except Exception as exc:
        return {
            "active_model": "",
            "installed": False,
            "truth_label": "PRIMARY_CORTEX_LOCAL_MODEL_TRUTH",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _safe_policy_snapshot(state_dir: Path | str | None = None) -> dict[str, Any]:
    try:
        from System.swarm_fast_ask_policy import policy_snapshot

        snap = policy_snapshot(state_dir=_state_dir(state_dir))
        return dict(snap) if isinstance(snap, Mapping) else {}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _safe_arm_summary(state_dir: Path | str | None = None) -> dict[str, Any]:
    path = _state_dir(state_dir) / "arm_performance_summary.json"
    if not path.exists():
        return {"available": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"available": False}
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}


def self_improvement_snapshot(
    *,
    state_dir: Path | str | None = None,
    lora_status: Mapping[str, Any] | None = None,
    primary_truth: Mapping[str, Any] | None = None,
    policy_snapshot_data: Mapping[str, Any] | None = None,
    arm_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the current promotion decision without mutating anything."""
    state = _state_dir(state_dir)
    lora = dict(lora_status or _safe_lora_status())
    primary = dict(primary_truth or _safe_primary_truth())
    policy = dict(policy_snapshot_data or _safe_policy_snapshot(state))
    arms = dict(arm_summary or _safe_arm_summary(state))

    active_model = str(primary.get("active_model") or "")
    candidate = str(lora.get("candidate_model") or "sifta-gemma4-alice-lora:latest")
    promotion_ready = bool(lora.get("promotion_ready"))
    blockers = list(lora.get("promotion_blockers") or [])

    recommended_actions: list[str] = []
    if not active_model:
        status = "PRIMARY_CORTEX_UNKNOWN"
        recommended_actions.append("probe primary cortex before promotion")
    elif promotion_ready:
        status = "CANDIDATE_READY_REQUIRES_EXPLICIT_SWITCH"
        recommended_actions.append("run multimodal harness and switch only with Architect GO")
    else:
        status = "KEEP_CURRENT_CORTEX"
        recommended_actions.append("keep active multimodal cortex")
        recommended_actions.append("use Fast Ask / arm outcome rows as runtime learning data")
        if blockers:
            recommended_actions.append("do not promote LoRA candidate until blockers clear")

    buckets = policy.get("buckets") if isinstance(policy.get("buckets"), Mapping) else {}
    weak_buckets = [
        name for name, info in buckets.items()
        if isinstance(info, Mapping) and float(info.get("success_rate", 1.0) or 1.0) < 0.6
    ][:6]
    if weak_buckets:
        recommended_actions.append("collect more outcome rows for weak buckets: " + ", ".join(weak_buckets))

    snapshot = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "active_model": active_model,
        "candidate_model": candidate,
        "promotion_status": status,
        "candidate_promotion_ready": promotion_ready,
        "candidate_blockers": blockers,
        "policy_examples_raw": policy.get("examples_raw"),
        "policy_decisions_raw": policy.get("decisions_raw"),
        "arm_summary_available": bool(arms.get("available", bool(arms))),
        "recommended_actions": recommended_actions,
        "switch_attempted": False,
        "switch_receipt": None,
    }
    snapshot["receipt"] = _hash_row(snapshot)
    return snapshot


def close_loop_once(
    *,
    state_dir: Path | str | None = None,
    allow_primary_switch: bool = False,
    source: str = "self_improvement_loop",
) -> dict[str, Any]:
    """Append one self-improvement decision receipt.

    `allow_primary_switch=False` is the daily safe path. If True and the
    candidate is ready, the function asks the primary-cortex switcher to switch.
    That still goes through the switcher's own verification/receipt gate.
    """
    state = _state_dir(state_dir)
    row = self_improvement_snapshot(state_dir=state)
    if allow_primary_switch and row["promotion_status"] == "CANDIDATE_READY_REQUIRES_EXPLICIT_SWITCH":
        try:
            from System.swarm_primary_cortex_switcher import set_primary_cortex

            receipt = set_primary_cortex(
                str(row["candidate_model"]),
                source=source,
                require_verification=True,
            )
            row["switch_attempted"] = True
            row["switch_receipt"] = receipt
            row["promotion_status"] = "PROMOTED_ACTIVE_CORTEX"
        except Exception as exc:
            row["switch_attempted"] = True
            row["switch_error"] = f"{type(exc).__name__}: {exc}"
            row["promotion_status"] = "PROMOTION_BLOCKED_BY_SWITCH_GATE"
    row["receipt"] = _hash_row(row)
    state.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, sort_keys=True) + "\n"
    if append_line_locked is not None:
        append_line_locked(state / LEDGER_NAME, line, encoding="utf-8")
    else:  # pragma: no cover
        with (state / LEDGER_NAME).open("a", encoding="utf-8") as handle:
            handle.write(line)
    return row


def summary_for_prompt(*, state_dir: Path | str | None = None) -> str:
    snap = self_improvement_snapshot(state_dir=state_dir)
    blockers = ", ".join(map(str, snap.get("candidate_blockers") or [])) or "none"
    actions = "; ".join(map(str, snap.get("recommended_actions") or []))
    return (
        "SELF-IMPROVEMENT LOOP: "
        f"active={snap.get('active_model') or 'unknown'} "
        f"candidate={snap.get('candidate_model')} "
        f"status={snap.get('promotion_status')} "
        f"blockers={blockers}. "
        f"Next={actions}"
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SIFTA self-improvement loop")
    parser.add_argument("--write", action="store_true", help="append a loop receipt")
    parser.add_argument("--allow-primary-switch", action="store_true", help="allow verified primary cortex switch")
    args = parser.parse_args(list(argv) if argv is not None else None)
    row = close_loop_once(allow_primary_switch=args.allow_primary_switch) if args.write else self_improvement_snapshot()
    print(json.dumps(row, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

