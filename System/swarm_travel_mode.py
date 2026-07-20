#!/usr/bin/env python3
"""Travel mode receipts and local-cortex pressure.

This organ does not infer GPS location. It reads what Alice can actually
prove on this Mac: clock timezone, network reachability, battery/power, and
the existing schedule ledger. When those receipts say the body is in travel
pressure, cloud-first cortex routing yields to a local model.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - direct script fallback
    append_line_locked = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "TRAVEL_MODE_V1"
LEDGER_NAME = "travel_mode.jsonl"
LATEST_NAME = "travel_mode_latest.json"
ROUTE_LEDGER_NAME = "travel_cortex_routes.jsonl"
FIRST_PERSON_NAME = "alice_first_person_journal.jsonl"
EPISODIC_NAME = "episodic_diary.jsonl"

ROMANIA_TIMEZONE_NEEDLES = (
    "eet",
    "eest",
    "bucharest",
    "romania",
    "europe/bucharest",
    "+02:00",
    "+03:00",
)

TRAVEL_PLAN_RE = re.compile(
    r"\b(?:flight|airport|turkish|airlines?|bucharest|romania|consulate|passport|visa|luggage|baggage)\b",
    re.IGNORECASE,
)
FLIGHT_RE = re.compile(r"\b(?:flight|airport|turkish|airlines?|baggage|luggage)\b", re.IGNORECASE)
CONSULATE_RE = re.compile(r"\b(?:consulate|passport|visa|embassy)\b", re.IGNORECASE)
LOCAL_MODEL_FALLBACK = "alice-m5-cortex-8b-6.3gb:latest"


def _state_dir(state_dir: Path | str | None = None) -> Path:
    if state_dir is None:
        return DEFAULT_STATE_DIR
    path = Path(state_dir)
    if path.name == ".sifta_state":
        return path
    if (path / "work_receipts.jsonl").exists() or (path / "travel_mode.jsonl").exists():
        return path
    return path / ".sifta_state"


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line)
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _write_json(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _iter_jsonl(path: Path, *, max_rows: int = 2000) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    for line in lines[-max_rows:]:
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _stable_id(payload: Mapping[str, Any]) -> str:
    stable = dict(payload)
    stable.pop("receipt_id", None)
    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "travel_" + hashlib.sha256(raw).hexdigest()[:16]


def _coerce_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _clock_reading(clock: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if clock is not None:
        return dict(clock)
    try:
        from System.swarm_hardware_time_oracle import current_time_for_alice

        return dict(current_time_for_alice() or {})
    except Exception as exc:
        return {"ok": False, "error": f"clock_unavailable:{type(exc).__name__}"}


def _network_reading(network: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if network is not None:
        return dict(network)
    try:
        from System import alice_hardware_body as hw

        return dict(hw.network() or {})
    except Exception as exc:
        return {"ok": False, "error": f"network_unavailable:{type(exc).__name__}"}


def _power_reading(power: Mapping[str, Any] | None = None, *, state_dir: Path) -> dict[str, Any]:
    if power is not None:
        return dict(power)
    try:
        from System.swarm_macbook_survival_swimmer import collect_power

        return dict(collect_power(state_dir=state_dir) or {})
    except Exception as exc:
        return {"ok": False, "error": f"power_unavailable:{type(exc).__name__}"}


def _timezone_text(clock: Mapping[str, Any]) -> str:
    return " ".join(
        str(clock.get(key) or "")
        for key in ("timezone", "tz", "local_iso", "local_human")
    ).strip()


def territory_from_clock(clock: Mapping[str, Any]) -> str:
    text = _timezone_text(clock).casefold()
    if any(needle in text for needle in ROMANIA_TIMEZONE_NEEDLES):
        return "romania"
    if text:
        return "current_os_timezone"
    return "unknown"


def _network_online(network: Mapping[str, Any]) -> bool:
    if not network:
        return False
    if network.get("online") is False or network.get("ok") is False:
        return False
    if network.get("active_interface") or network.get("interface") or network.get("ipv4") or network.get("ip"):
        return True
    if network.get("ok") is True:
        return True
    return False


def _power_source_kind(power: Mapping[str, Any]) -> str:
    text = str(power.get("source_kind") or power.get("source") or "").strip().casefold()
    if "battery" in text:
        return "battery"
    if "ac" in text or "wall" in text or "charger" in text:
        return "ac"
    return text or "unknown"


def _schedule_rows(state: Path) -> list[dict[str, Any]]:
    return list(_iter_jsonl(state / "stigmergic_schedule.jsonl", max_rows=1200))


def _travel_schedule_items(state: Path, *, now: float, horizon_s: float = 21 * 86400.0) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in _schedule_rows(state):
        text = str(row.get("text") or row.get("entry") or "").strip()
        if not text or not TRAVEL_PLAN_RE.search(text):
            continue
        due_ts = _coerce_float(row.get("due_ts"))
        created = _coerce_float(row.get("created") or row.get("ts"))
        near = False
        if due_ts is not None:
            near = -86400.0 <= due_ts - now <= horizon_s
        elif created is not None:
            near = now - created <= horizon_s
        else:
            near = True
        if not near:
            continue
        item = dict(row)
        item["text"] = text[:400]
        item["kind"] = (
            "consulate" if CONSULATE_RE.search(text)
            else "flight" if FLIGHT_RE.search(text)
            else "travel"
        )
        items.append(item)
    items.sort(key=lambda r: float(r.get("due_ts") or r.get("created") or r.get("ts") or now))
    return items[:8]


def _decide(
    *,
    clock: Mapping[str, Any],
    network: Mapping[str, Any],
    power: Mapping[str, Any],
    schedule_items: list[dict[str, Any]],
    latest: Mapping[str, Any],
) -> dict[str, Any]:
    territory = territory_from_clock(clock)
    prior_territory = str(latest.get("territory") or "")
    timezone = str(clock.get("timezone") or clock.get("tz") or "").strip()
    prior_timezone = str(latest.get("timezone") or "").strip()
    network_online = _network_online(network)
    pct = _coerce_int(power.get("percent"))
    source_kind = _power_source_kind(power)
    on_battery = source_kind == "battery"

    travel_planned = bool(schedule_items)
    territory_changed = bool(prior_territory and prior_territory != territory)
    timezone_changed = bool(prior_timezone and timezone and prior_timezone != timezone)
    in_transit_pressure = bool(travel_planned and (on_battery or not network_online))
    long_haul_battery_watch = bool(travel_planned and on_battery and pct is not None and pct <= 80)
    route_local_only = bool(not network_online or long_haul_battery_watch)
    cloud_blocked_reason = ""
    if not network_online:
        cloud_blocked_reason = "network_offline_or_unproven"
    elif long_haul_battery_watch:
        cloud_blocked_reason = f"travel_battery_watch_{pct}pct"

    if territory == "romania":
        status = "landed_romania_timezone"
    elif in_transit_pressure:
        status = "in_transit_pressure"
    elif travel_planned:
        status = "travel_planned"
    else:
        status = "home_or_unknown"

    return {
        "status": status,
        "territory": territory,
        "timezone": timezone,
        "territory_changed": territory_changed,
        "timezone_changed": timezone_changed,
        "travel_planned": travel_planned,
        "schedule_item_count": len(schedule_items),
        "network_online": network_online,
        "power_source_kind": source_kind,
        "battery_percent": pct,
        "in_transit_pressure": in_transit_pressure,
        "long_haul_battery_watch": long_haul_battery_watch,
        "route_local_only": route_local_only,
        "cloud_blocked_reason": cloud_blocked_reason,
    }


def sample_travel_mode(
    *,
    state_dir: Path | str | None = None,
    write: bool = True,
    force: bool = False,
    min_interval_s: float = 300.0,
    source: str = "body_prompt",
    now: float | None = None,
    clock: Mapping[str, Any] | None = None,
    network: Mapping[str, Any] | None = None,
    power: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one travel-mode reading and optionally write a throttled receipt."""
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    t = float(now if now is not None else time.time())
    latest = _read_json(state / LATEST_NAME)
    clock_row = _clock_reading(clock)
    network_row = _network_reading(network)
    power_row = _power_reading(power, state_dir=state)
    schedule_items = _travel_schedule_items(state, now=t)
    decision = _decide(
        clock=clock_row,
        network=network_row,
        power=power_row,
        schedule_items=schedule_items,
        latest=latest,
    )
    row: dict[str, Any] = {
        "ts": t,
        "truth_label": TRUTH_LABEL,
        "organ": "swarm_travel_mode",
        "source": source,
        "clock": {
            "ok": bool(clock_row.get("ok", True)),
            "timezone": clock_row.get("timezone") or clock_row.get("tz"),
            "local_iso": clock_row.get("local_iso"),
            "source": clock_row.get("source"),
            "signature": clock_row.get("signature"),
        },
        "network": {
            "ok": network_row.get("ok"),
            "online": _network_online(network_row),
            "active_interface": network_row.get("active_interface") or network_row.get("interface"),
            "ipv4": network_row.get("ipv4") or network_row.get("ip"),
        },
        "power": {
            "ok": power_row.get("ok"),
            "source_kind": decision["power_source_kind"],
            "percent": decision["battery_percent"],
            "status": power_row.get("status"),
        },
        "schedule_items": [
            {
                "schedule_id": item.get("schedule_id"),
                "kind": item.get("kind"),
                "text": str(item.get("text") or "")[:240],
                "due_ts": item.get("due_ts"),
                "due": item.get("due"),
            }
            for item in schedule_items
        ],
        **decision,
    }
    row["receipt_id"] = _stable_id(row)

    latest_ts = _coerce_float(latest.get("ts")) or 0.0
    changed = (
        row["territory"] != latest.get("territory")
        or row["timezone"] != latest.get("timezone")
        or row["network_online"] != latest.get("network_online")
        or row["route_local_only"] != latest.get("route_local_only")
    )
    wrote = False
    if write and (force or changed or t - latest_ts >= min_interval_s):
        _append_jsonl(state / LEDGER_NAME, row)
        _write_json(state / LATEST_NAME, row)
        wrote = True
        if row.get("territory_changed") or row.get("status") in {"landed_romania_timezone", "in_transit_pressure"}:
            summary = (
                f"Travel mode {row.get('status')}: territory={row.get('territory')} "
                f"timezone={row.get('timezone') or 'unknown'} route_local_only={row.get('route_local_only')} "
                f"receipt={row.get('receipt_id')}"
            )
            _append_jsonl(
                state / EPISODIC_NAME,
                {
                    "ts": t,
                    "kind": "TRAVEL_MODE",
                    "truth_label": TRUTH_LABEL,
                    "receipt_id": row.get("receipt_id"),
                    "summary": summary[:800],
                    "territory": row.get("territory"),
                },
            )
            try:
                from System.swarm_first_person_journal import append_first_person_journal_row

                append_first_person_journal_row(
                    {
                        "ts": t,
                        "truth_label": TRUTH_LABEL,
                        "receipt_id": row.get("receipt_id"),
                        "text": summary[:800],
                        "source": "swarm_travel_mode",
                    },
                    state_dir=state,
                    source_receipt_id=str(row.get("receipt_id") or ""),
                    pulse=True,
                )
            except Exception:
                _append_jsonl(
                    state / FIRST_PERSON_NAME,
                    {
                        "ts": t,
                        "truth_label": TRUTH_LABEL,
                        "receipt_id": row.get("receipt_id"),
                        "text": summary[:800],
                        "source": "swarm_travel_mode",
                    },
                )
    row["write_status"] = "written" if wrote else "not_written_throttled"
    if not wrote and latest.get("receipt_id"):
        row["last_written_receipt_id"] = latest.get("receipt_id")
    return row


def _is_cloudish_model(model: str) -> bool:
    low = str(model or "").casefold()
    if not low:
        return False
    if any(low.startswith(prefix) for prefix in ("grok:", "claude:", "codex:", "qwen:", "cline:", "gemini:", "mimo:", "antigravity:")):
        return True
    if "fireworks" in low or "openai" in low or "oauth" in low:
        return True
    try:
        from System.swarm_gemini_brain import is_cloud_model

        return bool(is_cloud_model(model))
    except Exception:
        return False


def _installed_local_models() -> list[str]:
    names: list[str] = []
    try:
        from System.swarm_primary_cortex_switcher import installed_ollama_models

        for row in installed_ollama_models() or []:
            name = str(row.get("name") or row.get("model") or "").strip()
            if name and not _is_cloudish_model(name):
                names.append(name)
    except Exception:
        pass
    if LOCAL_MODEL_FALLBACK not in names:
        names.append(LOCAL_MODEL_FALLBACK)
    return names


def local_only_cortex_route(
    current_model: str,
    *,
    state_dir: Path | str | None = None,
    query_text: str = "",
    now: float | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Return a local model override when travel/offline pressure blocks cloud."""
    state = _state_dir(state_dir)
    travel = sample_travel_mode(
        state_dir=state,
        write=write,
        source="cortex_route",
        now=now,
    )
    if not travel.get("route_local_only") or not _is_cloudish_model(current_model):
        return {
            "override": False,
            "model": current_model,
            "reason": "travel_mode_no_override",
            "travel_receipt_id": travel.get("receipt_id") or travel.get("last_written_receipt_id"),
        }
    candidates = _installed_local_models()
    chosen = candidates[0] if candidates else LOCAL_MODEL_FALLBACK
    row = {
        "ts": float(now if now is not None else time.time()),
        "truth_label": TRUTH_LABEL,
        "organ": "swarm_travel_mode",
        "action": "LOCAL_ONLY_CORTEX_ROUTE",
        "from_model": current_model,
        "chosen_model": chosen,
        "query_excerpt": str(query_text or "")[:180],
        "reason": travel.get("cloud_blocked_reason") or "travel_mode_local_only",
        "travel_receipt_id": travel.get("receipt_id") or travel.get("last_written_receipt_id"),
        "route_local_only": True,
        "model_name": "gpt-5-codex",
    }
    row["receipt_id"] = _stable_id(row)
    if write:
        _append_jsonl(state / ROUTE_LEDGER_NAME, row)
    return {
        "override": True,
        "model": chosen,
        "reason": row["reason"],
        "receipt_id": row["receipt_id"],
        "travel_receipt_id": row["travel_receipt_id"],
    }


def cloud_blocked_by_travel(*, state_dir: Path | str | None = None) -> tuple[bool, str]:
    travel = sample_travel_mode(state_dir=state_dir, write=True, source="cloud_gate")
    if travel.get("route_local_only"):
        return True, str(travel.get("cloud_blocked_reason") or "travel_mode_local_only")
    return False, ""


def boot_travel_greeting(
    *,
    state_dir: Path | str | None = None,
    now: float | None = None,
    horizon_s: float = 72 * 3600.0,
) -> str:
    state = _state_dir(state_dir)
    t = float(now if now is not None else time.time())
    items = _travel_schedule_items(state, now=t, horizon_s=horizon_s)
    due_now = [
        item for item in items
        if (_coerce_float(item.get("due_ts")) is None or -6 * 3600.0 <= (_coerce_float(item.get("due_ts")) or t) - t <= horizon_s)
    ]
    if not due_now:
        return ""
    kinds = {str(item.get("kind") or "travel") for item in due_now}
    named: list[str] = []
    for want in ("flight", "consulate", "travel"):
        for item in due_now:
            if item.get("kind") == want:
                text = str(item.get("text") or "").strip()
                if text and text not in named:
                    named.append(text[:120])
                break
    if not named:
        return ""
    label = " and ".join(k for k in ("flight", "consulate") if k in kinds) or "travel"
    return (
        f"Travel cue: {label} schedule rows are near. "
        f"Check: {'; '.join(named[:2])}. I will prefer local/offline cortex if network or battery receipts require it."
    )[:500]


def travel_prompt_block(*, state_dir: Path | str | None = None, max_chars: int = 900) -> str:
    row = sample_travel_mode(state_dir=state_dir, write=True, source="prompt_block")
    items = row.get("schedule_items") if isinstance(row.get("schedule_items"), list) else []
    item_bits = "; ".join(str(item.get("text") or "")[:80] for item in items[:2] if isinstance(item, dict))
    block = (
        "TRAVEL MODE BODY (receipt-grounded, no GPS inference):\n"
        f"- status={row.get('status')} territory={row.get('territory')} timezone={row.get('timezone') or 'unknown'} "
        f"territory_changed={str(row.get('territory_changed')).lower()}\n"
        f"- network_online={str(row.get('network_online')).lower()} power={row.get('battery_percent')}% "
        f"source={row.get('power_source_kind')} long_haul_battery_watch={str(row.get('long_haul_battery_watch')).lower()}\n"
        f"- route_local_only={str(row.get('route_local_only')).lower()} reason={row.get('cloud_blocked_reason') or 'none'}\n"
        f"- travel_schedule={item_bits or 'none'}\n"
        f"- receipt={row.get('receipt_id') if row.get('write_status') == 'written' else row.get('last_written_receipt_id') or 'pending'}"
    )
    return block[:max_chars]


__all__ = [
    "TRUTH_LABEL",
    "boot_travel_greeting",
    "cloud_blocked_by_travel",
    "local_only_cortex_route",
    "sample_travel_mode",
    "territory_from_clock",
    "travel_prompt_block",
]


if __name__ == "__main__":
    print(json.dumps(sample_travel_mode(write=True, force=True, source="module_main"), indent=2, ensure_ascii=False))
