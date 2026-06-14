"""Hardware-grounded Alice heart pulse.

r1010: Fable/George specified the portable heart contract:
monotonic timer for rhythm, power or thermal telemetry for metabolism.
This organ receipts what the host can actually observe. It never invents
watts or temperature when the OS refuses sensor access.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Tuple

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - import fallback for direct script use
    append_line_locked = None  # type: ignore[assignment]


RunCmd = Callable[[Iterable[str], float], Tuple[int, str, str]]
LEDGER_NAME = "hardware_heart.jsonl"
ALIAS_LEDGER_NAME = "alice_body_heart.jsonl"
SNAPSHOT_NAME = "hardware_heart.json"
ALIAS_SNAPSHOT_NAME = "alice_body_heart.json"


def _default_state_dir() -> Path:
    return Path(__file__).resolve().parents[1] / ".sifta_state"


def _default_run_cmd(cmd: Iterable[str], timeout: float) -> Tuple[int, str, str]:
    proc = subprocess.run(
        list(cmd),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _sensor_probe_enabled() -> bool:
    raw = os.environ.get("SIFTA_HEART_SENSOR_PROBE", "1").strip().lower()
    return raw not in {"0", "false", "off", "no", "skip"}


def _first_float(patterns: Iterable[str], text: str) -> float | None:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue
        try:
            return float(m.group(1))
        except Exception:
            continue
    return None


def _first_power_watts(patterns: Iterable[str], text: str) -> float | None:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue
        try:
            value = float(m.group(1))
        except Exception:
            continue
        unit = (m.group(2) if len(m.groups()) > 1 else "W").lower()
        if unit == "mw":
            return value / 1000.0
        return value
    return None


def _parse_powermetrics_smc(text: str) -> Dict[str, Any]:
    """Extract best-effort power and temperature from powermetrics SMC text."""
    power_w = _first_power_watts(
        (
            r"(?:package|processor|cpu|gpu|ane|soc)[^\n]{0,80}?power[^\n]{0,40}?([0-9]+(?:\.[0-9]+)?)\s*(mW|W)",
            r"([0-9]+(?:\.[0-9]+)?)\s*(mW|W)[^\n]{0,80}?(?:package|processor|cpu|gpu|ane|soc)",
        ),
        text,
    )
    temp_c = _first_float(
        (
            r"(?:die|cpu|gpu|ane|soc|package)[^\n]{0,80}?(?:temperature|temp)[^\n]{0,40}?([0-9]+(?:\.[0-9]+)?)\s*C",
            r"([0-9]+(?:\.[0-9]+)?)\s*C[^\n]{0,80}?(?:die|cpu|gpu|ane|soc|package)",
        ),
        text,
    )
    return {"power_watts": power_w, "temperature_c": temp_c}


def _probe_thermal_helper_ledger(state_dir: Path | None = None) -> Dict[str, Any]:
    """Read latest privileged thermal helper row if the LaunchDaemon is running."""
    sd = state_dir or _default_state_dir()
    path = sd / "thermal_state.jsonl"
    if not path.exists():
        return {
            "sensor_source": "thermal_state.jsonl",
            "sensor_tier": "privileged_helper_cache",
            "sensor_status": "unavailable",
            "sensor_reason": "thermal_state.jsonl missing",
            "power_watts": None,
            "temperature_c": None,
        }
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
        for line in reversed(lines[-20:]):
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            ane_mw = row.get("ane_power_mw")
            temp_c = row.get("die_temp_c")
            power_w = (float(ane_mw) / 1000.0) if ane_mw is not None else None
            if power_w is not None or temp_c is not None:
                return {
                    "sensor_source": "thermal_state.jsonl",
                    "sensor_tier": "privileged_helper_cache",
                    "sensor_status": "ok",
                    "sensor_reason": "",
                    "power_watts": power_w,
                    "temperature_c": float(temp_c) if temp_c is not None else None,
                    "thermal_helper_age_s": max(0.0, time.time() - float(row.get("ts") or 0.0)),
                }
    except Exception as exc:
        return {
            "sensor_source": "thermal_state.jsonl",
            "sensor_tier": "privileged_helper_cache",
            "sensor_status": "error",
            "sensor_reason": f"{type(exc).__name__}: {exc}",
            "power_watts": None,
            "temperature_c": None,
        }
    return {
        "sensor_source": "thermal_state.jsonl",
        "sensor_tier": "privileged_helper_cache",
        "sensor_status": "unparsed",
        "sensor_reason": "thermal_state.jsonl has no usable rows",
        "power_watts": None,
        "temperature_c": None,
    }


def _probe_unprivileged_body() -> Dict[str, Any]:
    """Read always-available body tiers before any privileged power probe."""
    body: Dict[str, Any] = {
        "sensor_source": "alice_hardware_body",
        "sensor_tier": "unprivileged_body",
        "sensor_status": "unavailable",
        "sensor_reason": "no unprivileged body probe succeeded",
        "power_watts": None,
        "temperature_c": None,
    }
    reasons: list[str] = []
    try:
        from System import alice_hardware_body as hw

        power = hw.power()
        thermal = hw.thermal()
        if isinstance(power, dict):
            body["hardware_power"] = power
            body["battery_percent"] = power.get("percent")
            body["power_source"] = power.get("source")
        if isinstance(thermal, dict):
            body["hardware_thermal"] = thermal
            body["thermal_pressure_pct"] = thermal.get("cpu_scheduler_limit_pct")
        if bool((power or {}).get("ok")) or bool((thermal or {}).get("ok")):
            body["sensor_status"] = "partial"
            body["sensor_reason"] = "battery/source/thermal-pressure observed; watts/temp still require sensor tier"
        else:
            reasons.append("alice_hardware_body returned no ok rows")
    except Exception as exc:
        reasons.append(f"alice_hardware_body:{type(exc).__name__}:{exc}")
    try:
        from System import swarm_battery_metabolism_organ as battery

        brow = battery.sample(write=False)
        body["battery_metabolism"] = brow
        metabolic = brow.get("metabolic") if isinstance(brow, dict) else None
        if isinstance(metabolic, dict):
            body["metabolic_band"] = metabolic.get("band")
            body["activity_multiplier"] = metabolic.get("activity_multiplier")
            body["conserve"] = metabolic.get("conserve")
            if body["sensor_status"] == "unavailable":
                body["sensor_status"] = "partial"
                body["sensor_reason"] = "battery metabolism observed; watts/temp still require sensor tier"
    except Exception as exc:
        reasons.append(f"battery_metabolism:{type(exc).__name__}:{exc}")
    if reasons and body["sensor_status"] == "unavailable":
        body["sensor_reason"] = "; ".join(reasons)[:220]
    return body


def _probe_macos_smc(run_cmd: RunCmd, *, timeout: float = 3.0) -> Dict[str, Any]:
    if not _sensor_probe_enabled():
        return {
            "sensor_source": "powermetrics_power_thermal",
            "sensor_tier": "privileged_power_thermal",
            "sensor_status": "skipped",
            "sensor_reason": "SIFTA_HEART_SENSOR_PROBE disabled",
            "power_watts": None,
            "temperature_c": None,
        }
    exe = shutil.which("powermetrics")
    if not exe:
        return {
            "sensor_source": "powermetrics_power_thermal",
            "sensor_tier": "privileged_power_thermal",
            "sensor_status": "unavailable",
            "sensor_reason": "powermetrics not found",
            "power_watts": None,
            "temperature_c": None,
        }
    try:
        code, stdout, stderr = run_cmd(
            [exe, "--samplers", "cpu_power,thermal,gpu_power,ane_power", "-n", "1", "-i", "250"],
            timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "sensor_source": "powermetrics_power_thermal",
            "sensor_tier": "privileged_power_thermal",
            "sensor_status": "timeout",
            "sensor_reason": f"powermetrics exceeded {timeout:.1f}s",
            "power_watts": None,
            "temperature_c": None,
        }
    except Exception as exc:
        return {
            "sensor_source": "powermetrics_power_thermal",
            "sensor_tier": "privileged_power_thermal",
            "sensor_status": "error",
            "sensor_reason": f"{type(exc).__name__}: {exc}",
            "power_watts": None,
            "temperature_c": None,
        }
    text = (stdout or "") + "\n" + (stderr or "")
    parsed = _parse_powermetrics_smc(text)
    if parsed["power_watts"] is not None or parsed["temperature_c"] is not None:
        return {
            "sensor_source": "powermetrics_power_thermal",
            "sensor_tier": "privileged_power_thermal",
            "sensor_status": "ok",
            "sensor_reason": "",
            **parsed,
        }
    reason = (stderr or stdout or "no SMC fields parsed").strip().splitlines()
    return {
        "sensor_source": "powermetrics_power_thermal",
        "sensor_tier": "privileged_power_thermal",
        "sensor_status": "unavailable" if code else "unparsed",
        "sensor_reason": (reason[0][:220] if reason else "no SMC fields parsed"),
        "power_watts": None,
        "temperature_c": None,
    }


def _probe_sensor(
    run_cmd: RunCmd,
    *,
    privileged_probe: bool = True,
    state_dir: Path | None = None,
) -> Dict[str, Any]:
    base = _probe_unprivileged_body()
    system = platform.system().lower()
    helper = _probe_thermal_helper_ledger(state_dir)
    if helper.get("power_watts") is not None or helper.get("temperature_c") is not None:
        return {**base, **helper, "unprivileged_sensor": base, "helper_sensor": helper}
    base["helper_sensor"] = helper
    if system == "darwin" and privileged_probe:
        priv = _probe_macos_smc(run_cmd)
        if priv.get("power_watts") is not None or priv.get("temperature_c") is not None:
            return {**base, **priv, "unprivileged_sensor": base, "helper_sensor": helper}
        base["privileged_sensor"] = priv
        if base.get("sensor_status") == "unavailable":
            return {**priv, "unprivileged_sensor": base, "helper_sensor": helper}
        base["sensor_reason"] = (
            f"{base.get('sensor_reason')}; privileged tier {priv.get('sensor_status')}: "
            f"{priv.get('sensor_reason')}"
        )[:260]
        return base
    if system == "darwin":
        base["privileged_sensor"] = {
            "sensor_source": "powermetrics_power_thermal",
            "sensor_tier": "privileged_power_thermal",
            "sensor_status": "skipped",
            "sensor_reason": "desktop heartbeat uses unprivileged tier only",
        }
        return base
    if base.get("sensor_status") != "unavailable":
        return base
    return {
        "sensor_source": "host_power_thermal",
        "sensor_tier": "platform_power_thermal",
        "sensor_status": "unimplemented",
        "sensor_reason": f"no probe implemented for {platform.system() or 'unknown OS'}",
        "power_watts": None,
        "temperature_c": None,
    }


def _ledger_paths(state_dir: Path) -> tuple[Path, Path]:
    return state_dir / LEDGER_NAME, state_dir / ALIAS_LEDGER_NAME


def _snapshot_paths(state_dir: Path) -> tuple[Path, Path]:
    return state_dir / SNAPSHOT_NAME, state_dir / ALIAS_SNAPSHOT_NAME


def _read_last_jsonl(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
        for line in reversed(lines[-20:]):
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                return row
    except Exception:
        return None
    return None


def latest_hardware_heart(*, state_dir: Path | str | None = None) -> Dict[str, Any] | None:
    sd = Path(state_dir) if state_dir is not None else _default_state_dir()
    primary, alias = _ledger_paths(sd)
    return _read_last_jsonl(primary) or _read_last_jsonl(alias)


def _derive_rhythm(previous: Dict[str, Any] | None, monotonic_ns: int) -> Dict[str, Any]:
    if not previous:
        return {"last_interval_s": None, "bpm_derived": None}
    try:
        prev_ns = int(previous.get("monotonic_ns") or 0)
    except Exception:
        prev_ns = 0
    delta_ns = monotonic_ns - prev_ns
    if delta_ns <= 0:
        return {"last_interval_s": None, "bpm_derived": None}
    interval_s = delta_ns / 1_000_000_000.0
    if interval_s <= 0 or interval_s > 3600:
        return {"last_interval_s": round(interval_s, 6), "bpm_derived": None}
    return {
        "last_interval_s": round(interval_s, 6),
        "bpm_derived": round(60.0 / interval_s, 3),
    }


def _write_heart_row(state_dir: Path, row: Dict[str, Any]) -> None:
    line = json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
    for ledger in _ledger_paths(state_dir):
        if append_line_locked is not None:
            append_line_locked(ledger, line)
        else:  # pragma: no cover
            ledger.parent.mkdir(parents=True, exist_ok=True)
            with ledger.open("a", encoding="utf-8") as f:
                f.write(line)
    snap = json.dumps(row, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    for snapshot in _snapshot_paths(state_dir):
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(snap, encoding="utf-8")


def pulse_hardware_heart(
    *,
    state_dir: Path | str | None = None,
    write: bool = True,
    run_cmd: RunCmd | None = None,
    monotonic_ns_fn: Callable[[], int] | None = None,
    now_fn: Callable[[], float] | None = None,
    privileged_probe: bool = True,
    source: str = "slash_heart",
) -> Dict[str, Any]:
    """Return and optionally receipt one hardware heart pulse."""
    sd = Path(state_dir) if state_dir is not None else _default_state_dir()
    mono_fn = monotonic_ns_fn or time.monotonic_ns
    now = now_fn or time.time
    runner = run_cmd or _default_run_cmd
    current_ns = int(mono_fn())
    previous = latest_hardware_heart(state_dir=sd)
    sensor = _probe_sensor(runner, privileged_probe=privileged_probe, state_dir=sd)
    row: Dict[str, Any] = {
        "schema": "SIFTA_HARDWARE_HEART_V1",
        "truth_label": "HARDWARE_HEART_PULSE_V1",
        "receipt_id": str(uuid.uuid4()),
        "ts": float(now()),
        "monotonic_ns": current_ns,
        "monotonic_source": "time.monotonic_ns (mach-backed on macOS)",
        "host_os": platform.platform(),
        "source": source,
        "pacemaker": "monotonic_timer",
        "metabolism": "power_or_thermal_sensor",
        "compatibility_contract": {
            "requires": ["monotonic_timer", "power_or_thermal_sensor"],
            "mac": "monotonic clock plus SMC/powermetrics when permitted",
            "linux": "monotonic clock plus hwmon/powercap probe when implemented",
            "raspberry_pi": "monotonic clock plus vcgencmd or hwmon probe when implemented",
        },
        **_derive_rhythm(previous, current_ns),
        **sensor,
    }
    if write:
        _write_heart_row(sd, row)
        # r1027-fable-two-eyes-one-field (P0 reconciled): one canonical bridge (saccadic).
        # owner_eye on every beat (grounding the person). world_eye on beat only during co-watch
        # (media playback field), decimated otherwise. Metabolism gates power. eye_id in rows.
        try:
            from System.swarm_saccadic_blink_vision import pulse_saccadic_blink

            # owner_eye always (the person, you, George)
            pulse_saccadic_blink(
                state_dir=sd,
                heart_row=row,
                reason=source or "heartbeat",
                now_fn=lambda: float(row.get("ts") or time.time()),
                eye_id="owner_eye",
                eye_role="owner_eye",
            )
            # world_eye (TV / shared reality) only if co-watch declared (decimate otherwise to protect power)
            try:
                # Simple co-watch detection: recent media / youtube context or flag (extend with real playback field).
                co_watch = False
                for ctx_name in ("youtube_context_latest.json", "ambient_media_context.json", "media_shazam_latest.json"):
                    try:
                        ctx = json.loads((sd / ctx_name).read_text(encoding="utf-8"))
                        age = float(row.get("ts") or time.time()) - float(ctx.get("ts") or 0.0)
                        if 0 <= age <= 300:
                            co_watch = True
                    except Exception:
                        pass
                yt = sd / "youtube_watch_memory.jsonl"
                if yt.exists():
                    lines = [l for l in yt.read_text(errors="ignore").splitlines()[-5:] if l.strip()]
                    if lines and ("co_watch" in lines[-1].lower() or "media" in lines[-1].lower() or "youtube" in lines[-1].lower()):
                        co_watch = True
                if (sd / "co_watch_active.flag").exists():
                    co_watch = True
                if co_watch:
                    pulse_saccadic_blink(
                        state_dir=sd,
                        heart_row=row,
                        reason=source or "heartbeat",
                        now_fn=lambda: float(row.get("ts") or time.time()),
                        eye_id="world_eye",
                        eye_role="world_eye",
                    )
            except Exception:
                pass
        except Exception:
            pass
        try:
            from System.swarm_bio_world_model import tick_prediction
            from System.swarm_canonical_organ_registry import publish_organ_vital

            tick_prediction(state_dir=sd, source=source or "heartbeat")
            publish_organ_vital(
                organ="heart",
                health=1.0 if row.get("sensor_status") in {"ok", "partial"} else 0.4,
                load=0.2,
                top_signal=str(row.get("sensor_tier") or row.get("sensor_status") or ""),
                state_dir=sd,
            )
        except Exception:
            pass
    return row


def format_heart_reply(row: Dict[str, Any]) -> str:
    power = row.get("power_watts")
    temp = row.get("temperature_c")
    metabolism_bits = []
    if power is not None:
        metabolism_bits.append(f"power={power:.3g} W")
    if temp is not None:
        metabolism_bits.append(f"temp={temp:.3g} C")
    if not metabolism_bits:
        reason = str(row.get("sensor_reason") or row.get("sensor_status") or "not observed")
        metabolism_bits.append(f"sensor {row.get('sensor_status')}: {reason}")
    rhythm = "first beat"
    if row.get("bpm_derived") is not None:
        rhythm = f"{row.get('bpm_derived')} bpm from {row.get('last_interval_s')}s interval"
    battery = ""
    if row.get("battery_percent") is not None or row.get("power_source"):
        battery = f"  battery: {row.get('battery_percent', '?')}% source={row.get('power_source') or '?'}"
    budget = ""
    if row.get("metabolic_band"):
        budget = (
            f"  budget: {row.get('metabolic_band')} "
            f"x{row.get('activity_multiplier', '?')} conserve={row.get('conserve')}"
        )
    return "\n".join(
        [ln for ln in [
            "HEART:",
            f"  pacemaker: monotonic_ns={row.get('monotonic_ns')} ({row.get('monotonic_source')})",
            f"  rhythm: {rhythm}",
            f"  metabolism: {', '.join(metabolism_bits)} via {row.get('sensor_tier') or row.get('sensor_source')}",
            battery,
            budget,
            f"  compatibility: {', '.join(row.get('compatibility_contract', {}).get('requires', []))}",
            f"  receipt: {row.get('receipt_id')}",
        ] if ln]
    )


if __name__ == "__main__":  # pragma: no cover
    print(format_heart_reply(pulse_hardware_heart()))
