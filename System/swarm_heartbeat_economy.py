"""Settle observed body health through the canonical signed STGM wallet."""
from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import time
from pathlib import Path

from System.ledger_append import append_ledger_line

POLICY = "STGM_HEALTH_HEARTBEAT_V1"
REWARD = 0.00001
PENALTY = 0.0001
REWARD_CAP = 0.01
PENALTY_CAP = 0.05
STATE_NAME = "heartbeat_economy_state.json"


def signing_body(row: dict) -> str:
    return json.dumps({k: v for k, v in row.items() if k != "ed25519_sig"},
                      sort_keys=True, separators=(",", ":"), allow_nan=False)


def signature_valid(row: dict) -> bool:
    try:
        from System.crypto_keychain import verify_block
        return bool(verify_block(row["signing_node"], signing_body(row), row["ed25519_sig"]))
    except Exception:
        return False


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, row: dict) -> None:
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(row, stream, sort_keys=True, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def _latest(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as stream:
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(max(0, size - 131072))
        lines = stream.read().splitlines()
    for line in reversed(lines):
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                return row
        except (ValueError, UnicodeError):
            continue
    return {}


def classify(heart: dict, body: dict, now: float) -> tuple[str, list[str]]:
    """Missing/stale telemetry cannot assert success or charge a failure."""
    try:
        for row, ttl in ((heart, 180), (body, 600)):
            age = now - float(row["ts"])
            if not math.isfinite(age) or not 0 <= age <= ttl:
                return "UNKNOWN", ["stale_or_future_receipt"]
        if heart.get("schema") != "SIFTA_HARDWARE_HEART_V1" or not heart.get("receipt_id"):
            return "UNKNOWN", ["missing_hardware_receipt"]
        if body.get("truth_label") != "BODY_WRITER_TICK_V1":
            return "UNKNOWN", ["missing_body_receipt"]
        producers = body.get("producers") or []
        if not isinstance(producers, list) or any(not isinstance(p, dict) for p in producers):
            return "UNKNOWN", ["malformed_producer_evidence"]
        faults = [str(p.get("producer") or "unknown_organ") for p in producers
                  if p.get("status") in {"import_failed", "call_failed", "error", "failed"}]
        if body.get("degraded_mode"):
            faults.append("body_writer_supervisor_degraded")
        if faults:
            return "FAULT", faults
        if (heart.get("sensor_status") not in {"ok", "partial"} or not producers
                or any(p.get("status") != "ok" for p in producers)
                or body.get("overall_status") != "ok" or body.get("receipt_write_error")):
            return "UNKNOWN", ["incomplete_health_evidence"]
        return "HEALTHY", []
    except (KeyError, TypeError, ValueError):
        return "UNKNOWN", ["malformed_health_evidence"]


def settle_heartbeat(*, state_dir: Path, ledger: Path, now: float | None = None) -> dict:
    """One settlement per body receipt, durable retries and serialized writers.

    A prepared event is replayed after a crash; both canonical wallet readers
    deduplicate its signed event_id. Caps apply to this explicit health policy.
    """
    state_dir, ledger = Path(state_dir), Path(ledger)
    now = time.time() if now is None else float(now)
    if not math.isfinite(now):
        raise ValueError("Heartbeat time must be finite")
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "heartbeat_economy.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = state_dir / STATE_NAME
        state = _read(path)
        pending = state.get("pending")
        if pending:
            _commit_pending(state_dir, ledger, state, path)
            return {"status": "RECOVERED", "event_id": pending["event_id"]}
        heart = _latest(state_dir / "hardware_heart.jsonl")
        body = _latest(state_dir / "body_writer_tick.jsonl")
        status, faults = classify(heart, body, now)
        result = {"status": status, "faults": faults, "ts": now,
                  "policy": POLICY, "truth_label": "OBSERVED", "delta_stgm": 0.0}
        if status == "UNKNOWN":
            _save(state_dir / "heartbeat_economy_latest.json", result)
            return result
        source = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        seen = state.get("seen", [])
        if source in seen:
            return {**result, "status": "ALREADY_SETTLED"}
        if now - state.get("last_settlement_ts", 0) < 60:
            return {**result, "status": "THROTTLED"}
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        if state.get("day") != day:
            state.update(day=day, reward_total=0.0, penalty_total=0.0)
        healthy = status == "HEALTHY"
        amount, cap, total_key = (REWARD, REWARD_CAP, "reward_total") if healthy else (PENALTY, PENALTY_CAP, "penalty_total")
        if state.get(total_key, 0) + amount > cap + 1e-12:
            return {**result, "status": "DAILY_CAP"}
        from System.crypto_keychain import get_silicon_identity, sign_block
        from System.swarm_electricity_metabolism import CANONICAL_OS_BENEFICIARY
        event = {
            **result, "event_id": "health-" + source, "source_receipt_id": source,
            "heart_receipt_id": heart["receipt_id"], "body_receipt": body,
            "agent_id": CANONICAL_OS_BENEFICIARY, "miner_id": CANONICAL_OS_BENEFICIARY,
            "reason": "observed_body_health", "pulse_kind": "healthy_heartbeat" if healthy else "fault_heartbeat",
            "delta_stgm": amount if healthy else -amount,
            "signing_node": get_silicon_identity(),
        }
        if healthy:
            event.update(event_kind="UTILITY_MINT_POUW_PULSE", amount_stgm=amount)
        else:
            event.update(tx_type="STGM_SPEND", amount=amount, timestamp=now)
        event["ed25519_sig"] = sign_block(signing_body(event))
        if not signature_valid(event):
            result.update(status="SIGNATURE_UNAVAILABLE")
            _save(state_dir / "heartbeat_economy_latest.json", result)
            return result
        state.update(pending=event, seen=seen + [source], last_settlement_ts=now)
        state[total_key] = round(state.get(total_key, 0) + amount, 9)
        _save(path, state)
        _commit_pending(state_dir, ledger, state, path)
        return event


def _commit_pending(sd: Path, ledger: Path, state: dict, path: Path) -> None:
    event = state["pending"]
    if not signature_valid(event):
        raise ValueError("Invalid prepared heartbeat signature")
    append_ledger_line(ledger, event)
    if event["status"] == "FAULT":
        append_ledger_line(sd / "self_eval_swimmer_dispatch.jsonl", {
            "ts": event["ts"], "receipt_id": event["event_id"], "severity": "red",
            "summary": "Heartbeat detected: " + ", ".join(event["faults"]),
            "target_files": ["System/swarm_body_writer_tick.py"],
            "suggested_fix": "Inspect failing producer receipts, repair and rerun focused tests.",
            "truth_label": "OBSERVED",
        })
    append_ledger_line(sd / "heartbeat_economy.jsonl", event)
    _save(sd / "heartbeat_economy_latest.json", event)
    state.pop("pending")
    _save(path, state)
    # Let the existing desktop cache worker refresh the canonical topbar.
    (sd / "stgm_economy_cache.json").unlink(missing_ok=True)


def status_lines(state_dir: Path) -> list[str]:
    try:
        row = _read(Path(state_dir) / "heartbeat_economy_latest.json")
        if not row:
            return ["Heartbeat economy: awaiting a recorded settlement."]
        age = max(0, time.time() - float(row["ts"]))
        return [f"Heartbeat economy: {row['status']} | {float(row.get('delta_stgm', 0)):+.8f} STGM | age {age:.0f}s",
                "Observed faults: " + (", ".join(row.get("faults", [])) or "none in sampled producers"),
                "Policy: +0.00001 healthy / -0.0001 fault; one settlement per receipt; minimum 60s."]
    except Exception as exc:
        return [f"Heartbeat economy: telemetry unavailable ({type(exc).__name__})."]
