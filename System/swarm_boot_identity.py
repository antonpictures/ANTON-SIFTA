"""D1 — portable boot/topology identity, resource probes and capability loss ledger.

Job D1 of ``Documents/ALICE_ADAPTIVE_INTELLIGENCE_HANDOFF.md``: extend the hardware
census/capability registry surfaces so the organism knows *which* body it woke up in,
*how fresh* that knowledge is, *what it can actually measure*, and *what it has lost*.

Portability law: this module imports stdlib only. No Qt, no AppKit, no macOS-only module
is imported at import time; every platform probe is guarded and reports ``None`` (unknown)
rather than inventing a value. A headless Linux Dell must be able to import and run it.

Laws carried from C0 (``System/swarm_adaptive_contracts.py``):
  * unknown is null, never a guessed number;
  * a capability that was lost stays visible as unavailable with a reason code;
  * the emitted snapshot validates against the frozen ``capability_snapshot`` record.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import socket
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence

TOPOLOGY_SCHEMA_VERSION = "1.0.0"
BOOT_LEDGER_NAME = "boot_identity.jsonl"
CAPABILITY_HEALTH_NAME = "capability_health.jsonl"

# Reason codes (subset of the frozen C0 enum) used when something is not available.
REASON_UNSUPPORTED = "UNSUPPORTED"
REASON_SENSOR_STALE = "SENSOR_STALE"
REASON_BLOCKED = "BLOCKED"
REASON_TARGET_UNKNOWN = "TARGET_UNKNOWN"

_LOST = "lost"
_RECOVERED = "recovered"


# ── shared plumbing (same fallbacks the rest of the body uses) ─────────────────

def _state_dir(root: Optional[os.PathLike | str] = None) -> Path:
    if root is not None:
        return Path(root)
    try:
        from System.swarm_persistent_owner_history import state_dir as _sd  # type: ignore
        return Path(_sd())
    except Exception:
        return Path(os.environ.get("SIFTA_STATE_DIR", ".sifta_state"))


def _read_text(path: Path) -> str:
    try:
        from System.jsonl_file_lock import read_text_locked  # type: ignore
        return read_text_locked(path, encoding="utf-8")
    except Exception:
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""


def _append_line(path: Path, line: str) -> None:
    try:
        from System.jsonl_file_lock import append_line_locked  # type: ignore
        append_line_locked(path, line, encoding="utf-8")
    except Exception:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)


def _iter_rows(path: Path) -> Iterable[Dict[str, Any]]:
    for raw in _read_text(path).splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except Exception:
            continue
        if isinstance(row, dict):
            yield row


def utc_now(*, now: Optional[float] = None) -> str:
    ts = time.time() if now is None else now
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _parse_utc(text: Any) -> Optional[float]:
    if not isinstance(text, str):
        return None
    try:
        return time.mktime(time.strptime(text, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
    except Exception:
        return None


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _digest(prefix: str, payload: Any, *, length: int = 32) -> str:
    return prefix + hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:length]


# ── platform identification ────────────────────────────────────────────────────

def platform_id(*, os_release: Optional[Path] = None) -> str:
    """One of macos / linux_pi / linux_wsl / linux / unknown. Never guessed."""
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        model = ""
        try:
            model = (Path("/proc/device-tree/model").read_bytes().decode("utf-8", "replace")
                     if Path("/proc/device-tree/model").exists() else "")
        except Exception:
            model = ""
        if "raspberry pi" in model.lower():
            return "linux_pi"
        rel = ""
        try:
            rel = (os_release or Path("/proc/version")).read_text(encoding="utf-8", errors="replace")
        except Exception:
            rel = ""
        if "microsoft" in rel.lower() or "wsl" in rel.lower():
            return "linux_wsl"
        return "linux"
    if sys.platform.startswith("win"):
        return "windows"
    return "unknown"


def is_headless(*, env: Optional[Mapping[str, str]] = None,
                pid: Optional[str] = None) -> Optional[bool]:
    """True when no display is usable, so no Qt/App window may be assumed.

    ``None`` means undetermined — the caller must not then assume either way.
    """
    env_map = os.environ if env is None else env
    pid = platform_id() if pid is None else pid
    if pid == "macos":
        # macOS always runs a WindowServer, but a display may be absent over SSH.
        return False if env_map.get("SSH_CONNECTION") is None else not _macos_display_present()
    if pid.startswith("linux"):
        if env_map.get("DISPLAY") or env_map.get("WAYLAND_DISPLAY"):
            return False
        try:
            if any(Path("/tmp/.X11-unix").glob("X*")):
                return False
        except Exception:
            pass
        return True
    return None


def _macos_display_present() -> bool:
    try:
        import subprocess
        out = subprocess.run(["system_profiler", "SPDisplaysDataType"],
                             capture_output=True, text=True, timeout=5).stdout
        return "Resolution" in out or "Display Type" in out
    except Exception:
        return True  # a mac that cannot answer still has its built-in panel


# ── resource probes: measured, or explicitly unknown ──────────────────────────

def probe_storage(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    try:
        target = Path(path or _state_dir())
        while not target.exists() and target != target.parent:
            target = target.parent
        usage = shutil.disk_usage(target)
        return {"free_gb": round(usage.free / 1e9, 3), "total_gb": round(usage.total / 1e9, 3),
                "unit": "GB"}
    except Exception:
        return None


def probe_memory() -> Optional[Dict[str, Any]]:
    try:
        if hasattr(os, "sysconf") and "SC_AVPHYS_PAGES" in os.sysconf_names:
            pages = os.sysconf("SC_AVPHYS_PAGES")
            size = os.sysconf("SC_PAGE_SIZE")
            return {"available_gb": round(pages * size / 1e9, 3), "unit": "GB"}
    except Exception:
        pass
    try:
        import subprocess
        out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5).stdout
        free_pages = 0
        page = 4096
        for line in out.splitlines():
            if "page size of" in line:
                page = int(line.split("page size of")[1].split()[0])
            if line.startswith(("Pages free", "Pages inactive")):
                free_pages += int(line.split(":")[1].strip().rstrip("."))
        if free_pages:
            return {"available_gb": round(free_pages * page / 1e9, 3), "unit": "GB"}
    except Exception:
        pass
    return None


def probe_thermal() -> Optional[Dict[str, Any]]:
    """CPU temperature in Celsius where the platform exposes it; Linux-first."""
    try:
        zones = sorted(Path("/sys/class/thermal").glob("thermal_zone*"))
        for zone in zones:
            try:
                millis = int((zone / "temp").read_text(encoding="utf-8").strip())
            except Exception:
                continue
            if millis > 1000:
                return {"celsius": round(millis / 1000.0, 2), "unit": "C"}
    except Exception:
        pass
    return None


def probe_battery() -> Optional[Dict[str, Any]]:
    """Battery fraction + AC state. ``on_ac`` is None when the platform will not say."""
    try:
        bat = sorted(Path("/sys/class/power_supply").glob("BAT*"))
        ac = sorted(Path("/sys/class/power_supply").glob("A*"))
        if bat:
            cap = (bat[0] / "capacity").read_text(encoding="utf-8").strip()
            state = (bat[0] / "status").read_text(encoding="utf-8").strip().lower()
            on_ac = None
            if ac:
                try:
                    on_ac = bool(int((ac[0] / "online").read_text(encoding="utf-8").strip()))
                except Exception:
                    on_ac = None
            elif state in ("charging", "full", "not charging"):
                on_ac = state != "discharging"
            return {"fraction": round(float(cap) / 100.0, 4), "on_ac": on_ac, "unit": "fraction"}
    except Exception:
        pass
    try:
        import subprocess
        out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5).stdout
        if "%" not in out:
            return None
        pct = int(out.split("%")[0].split()[-1])
        on_ac = "AC Power" in out
        return {"fraction": round(pct / 100.0, 4), "on_ac": on_ac, "unit": "fraction"}
    except Exception:
        return None


def probe_network(*, timeout_s: float = 0.25, host: str = "1.1.1.1", port: int = 53) -> Optional[bool]:
    """True/False = actually probed. None = could not determine (never assume online)."""
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError as exc:
        # a refused connection still proves the network carried the packet
        if getattr(exc, "errno", None) in (111, 61):
            return True
        return False
    except Exception:
        return None


def probe_model_endpoint(env: Optional[Mapping[str, str]] = None) -> Optional[bool]:
    """Whether a configured local model endpoint answers. No endpoint configured = unknown."""
    env_map = os.environ if env is None else env
    url = env_map.get("SIFTA_MODEL_ENDPOINT") or env_map.get("OLLAMA_HOST")
    if not url:
        return None
    try:
        hostport = url.split("//")[-1].split("/")[0]
        host, _, port = hostport.partition(":")
        with socket.create_connection((host, int(port or 80)), timeout=0.25):
            return True
    except Exception:
        return False


DEFAULT_PROBERS: Dict[str, Callable[[], Any]] = {
    "storage": probe_storage,
    "memory": probe_memory,
    "thermal": probe_thermal,
    "battery": probe_battery,
    "network": probe_network,
    "model_endpoint": probe_model_endpoint,
}
# capability name → the reason code used when its probe reports nothing/negative
PROBE_CAPABILITY_REASONS: Dict[str, str] = {
    "storage": REASON_SENSOR_STALE,
    "memory": REASON_SENSOR_STALE,
    "thermal": REASON_UNSUPPORTED,
    "battery": REASON_UNSUPPORTED,
    "network": REASON_BLOCKED,
    "model_endpoint": REASON_UNSUPPORTED,
}


def run_probes(*, probes: Optional[Mapping[str, Callable[[], Any]]] = None,
               state_root: Optional[os.PathLike | str] = None) -> Dict[str, Any]:
    """Run every probe, never raising. Returns {name: value} with ``None`` for unknown.

    Probers are nullary by convention, so a test (or another body) can inject a fake
    reading for any subsystem without reaching into the real platform.
    """
    registry = dict(DEFAULT_PROBERS)
    if probes:
        registry.update(probes)
    out: Dict[str, Any] = {}
    for name, fn in sorted(registry.items()):
        try:
            out[name] = fn()
        except Exception:
            out[name] = None
    return out


# ── boot + topology identity ──────────────────────────────────────────────────

def _topology_roles(readings: Mapping[str, Any]) -> list[str]:
    """Body layout: which subsystem families actually answered. Sorted, explicit."""
    roles = []
    if readings.get("storage"):
        roles.append("storage")
    if readings.get("memory"):
        roles.append("memory")
    if readings.get("thermal"):
        roles.append("thermal")
    if readings.get("battery"):
        roles.append("battery")
    if readings.get("network") is True:
        roles.append("network")
    if readings.get("model_endpoint") is True:
        roles.append("model")
    if is_headless() is False:
        roles.append("display")
    return sorted(roles)


def topology_facts(*, readings: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Stable description of this physical body. Missing facts are explicit null."""
    readings = {} if readings is None else readings
    memory_gb: Optional[float] = None
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        size = os.sysconf("SC_PAGE_SIZE")
        memory_gb = round(pages * size / 1e9, 2)
    except Exception:
        memory_gb = None
    return {
        "platform_id": platform_id(),
        "machine": platform.machine() or None,
        "processor": platform.processor() or None,
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "physical_memory_gb": memory_gb,
        "headless": is_headless(),
        "roles": _topology_roles(readings),
    }


def topology_id(*, facts: Optional[Mapping[str, Any]] = None,
                readings: Optional[Mapping[str, Any]] = None) -> str:
    facts = topology_facts(readings=readings) if facts is None else dict(facts)
    material = {k: facts.get(k) for k in
                ("platform_id", "machine", "cpu_count", "physical_memory_gb", "roles")}
    return _digest("topo:", material)


def _boot_ledger(state_root: Optional[os.PathLike | str] = None) -> Path:
    return _state_dir(state_root) / BOOT_LEDGER_NAME


def previous_boot(*, state_root: Optional[os.PathLike | str] = None) -> Optional[Dict[str, Any]]:
    """Last recorded boot row, or None if this body has never recorded one."""
    rows = list(_iter_rows(_boot_ledger(state_root)))
    return rows[-1] if rows else None


def start_boot(*, state_root: Optional[os.PathLike | str] = None,
               readings: Optional[Mapping[str, Any]] = None,
               now: Optional[float] = None, process_boot_id: Optional[str] = None) -> Dict[str, Any]:
    """Record this process boot and return its identity row.

    Idempotent inside one process: the same ``boot_id`` is returned on every call, so
    restarting SIFTA produces a new boot while re-entrant imports do not.
    """
    cached = globals().get("_BOOT_ROW")
    if isinstance(cached, dict) and state_root is None and process_boot_id is None:
        return dict(cached)
    prior = previous_boot(state_root=state_root)
    boot_id = process_boot_id or str(uuid.uuid4())
    row = {
        "schema": "sifta.body.boot/1",
        "schema_version": TOPOLOGY_SCHEMA_VERSION,
        "boot_id": boot_id,
        "sequence": int(prior.get("sequence", 0)) + 1 if prior else 1,
        "previous_boot_id": prior.get("boot_id") if prior else None,
        "started_at_utc": utc_now(now=now),
        "topology_id": topology_id(readings=readings),
        "topology_revision": TOPOLOGY_SCHEMA_VERSION,
        "hostname": socket.gethostname() or None,
        "pid": os.getpid(),
    }
    _append_line(_boot_ledger(state_root), json.dumps(row, sort_keys=True) + "\n")
    if state_root is None:
        globals()["_BOOT_ROW"] = row
    return dict(row)


def current_boot(*, state_root: Optional[os.PathLike | str] = None) -> Optional[Dict[str, Any]]:
    """The boot this process is running under, recording one if none exists yet."""
    cached = globals().get("_BOOT_ROW")
    if isinstance(cached, dict) and state_root is None:
        return dict(cached)
    prior = previous_boot(state_root=state_root)
    if prior and prior.get("pid") == os.getpid():
        return prior
    return start_boot(state_root=state_root)


def boot_is_stale(expected_boot_id: str, *,
                  state_root: Optional[os.PathLike | str] = None) -> bool:
    """True when a command addressed to ``expected_boot_id`` no longer matches this body."""
    here = current_boot(state_root=state_root)
    if not here:
        return True
    return here.get("boot_id") != expected_boot_id


# ── capability loss / recovery ledger ─────────────────────────────────────────

def _health_path(state_root: Optional[os.PathLike | str] = None) -> Path:
    return _state_dir(state_root) / CAPABILITY_HEALTH_NAME


def record_capability_event(kind: str, capability: str, *, reason_code: Optional[str] = None,
                            detail: Optional[str] = None,
                            state_root: Optional[os.PathLike | str] = None,
                            now: Optional[float] = None) -> Dict[str, Any]:
    """Append one loss/recovery transition. ``kind`` is 'lost' or 'recovered'."""
    if kind not in (_LOST, _RECOVERED):
        raise ValueError(f"unknown capability event kind: {kind!r}")
    if not capability:
        raise ValueError("capability name is required")
    row = {
        "schema": "sifta.body.capability_health/1",
        "capability": capability,
        "kind": kind,
        "reason_code": reason_code if kind == _LOST else None,
        "detail": detail,
        "at_utc": utc_now(now=now),
        "boot_id": (current_boot(state_root=state_root) or {}).get("boot_id"),
    }
    _append_line(_health_path(state_root), json.dumps(row, sort_keys=True) + "\n")
    return row


def mark_lost(capability: str, *, reason_code: str = REASON_BLOCKED,
              detail: Optional[str] = None, state_root: Optional[os.PathLike | str] = None,
              now: Optional[float] = None) -> Dict[str, Any]:
    return record_capability_event(_LOST, capability, reason_code=reason_code, detail=detail,
                                   state_root=state_root, now=now)


def mark_recovered(capability: str, *, detail: Optional[str] = None,
                   state_root: Optional[os.PathLike | str] = None,
                   now: Optional[float] = None) -> Dict[str, Any]:
    return record_capability_event(_RECOVERED, capability, detail=detail,
                                   state_root=state_root, now=now)


def capability_health(*, state_root: Optional[os.PathLike | str] = None,
                      now: Optional[float] = None,
                      readings: Optional[Mapping[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    """Replay the ledger into current state. Probe-derived loss is merged in.

    A capability the probes cannot measure is reported ``lost`` with a reason — never
    silently dropped, and never assumed present.
    """
    state: Dict[str, Dict[str, Any]] = {}
    for row in _iter_rows(_health_path(state_root)):
        name = row.get("capability")
        if not name:
            continue
        if row.get("kind") == _RECOVERED:
            state[name] = {"state": "present", "reason_code": None,
                           "detail": row.get("detail"), "at_utc": row.get("at_utc")}
        else:
            state[name] = {"state": _LOST, "reason_code": row.get("reason_code") or REASON_BLOCKED,
                           "detail": row.get("detail"), "at_utc": row.get("at_utc")}

    measured = run_probes(state_root=state_root) if readings is None else dict(readings)
    for name, value in sorted(measured.items()):
        if value is None or value is False:
            # only claim loss when the ledger does not already describe it more precisely
            state.setdefault(name, {
                "state": _LOST,
                "reason_code": PROBE_CAPABILITY_REASONS.get(name, REASON_UNSUPPORTED),
                "detail": "probe reported no usable reading" if value is None else "probe reported unavailable",
                "at_utc": utc_now(now=now),
            })
        else:
            # a measured reading is positive evidence of presence, unless the ledger
            # records a loss that the probe cannot see (e.g. a tool, not a sensor)
            state.setdefault(name, {
                "state": "present", "reason_code": None, "detail": None,
                "at_utc": utc_now(now=now),
            })
    stamp = time.time() if now is None else now
    for entry in state.values():
        parsed = _parse_utc(entry.get("at_utc"))
        entry["age_ms"] = None if parsed is None else max(0, int((stamp - parsed) * 1000))
    return state


def unavailable_capabilities(*, state_root: Optional[os.PathLike | str] = None,
                             now: Optional[float] = None,
                             readings: Optional[Mapping[str, Any]] = None) -> list[Dict[str, Any]]:
    health = capability_health(state_root=state_root, now=now, readings=readings)
    return [{"name": name, "reason_code": entry["reason_code"], "detail": entry.get("detail")}
            for name, entry in sorted(health.items()) if entry["state"] == _LOST]


def planning_view(actions: Sequence[Mapping[str, Any]], *,
                  state_root: Optional[os.PathLike | str] = None,
                  now: Optional[float] = None,
                  readings: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """The next relevant planning step: drop actions whose preconditions are lost.

    An action is any mapping with ``name`` and optional ``preconditions`` (the same
    shape the frozen ``capability_snapshot`` record uses). A lost precondition makes the
    action unavailable *with the reason the capability was lost*, so the planner can
    replan rather than retry a body that no longer has the organ.
    """
    health = capability_health(state_root=state_root, now=now, readings=readings)
    available: list[Dict[str, Any]] = []
    blocked: list[Dict[str, Any]] = []
    for action in actions:
        name = str(action.get("name") or "")
        missing = []
        for requirement in action.get("preconditions") or ():
            entry = health.get(str(requirement))
            if entry is None:
                # never reported by this body: on an unfamiliar body the planner must
                # not assume the organ exists.
                missing.append((str(requirement), REASON_UNSUPPORTED))
            elif entry.get("state") == _LOST:
                missing.append((str(requirement), entry.get("reason_code") or REASON_BLOCKED))
        if missing:
            requirement, reason = missing[0]
            blocked.append({
                "name": name,
                "reason_code": reason,
                "detail": f"unmet precondition: {requirement}",
                "blocked_by": [r for r, _ in missing],
            })
        else:
            available.append(dict(action))
    return {"available": available, "unavailable": blocked,
            "topology_id": topology_id(readings=readings),
            "checked_at_utc": utc_now(now=now)}


# ── frozen capability_snapshot record ─────────────────────────────────────────

def _resource_estimates(readings: Mapping[str, Any]) -> list[Dict[str, Any]]:
    """Only measured resources appear here: the record's ``value`` cannot be null."""
    out: list[Dict[str, Any]] = []
    storage = readings.get("storage")
    if isinstance(storage, dict) and storage.get("free_gb") is not None:
        out.append({"resource": "disk_free", "value": float(storage["free_gb"]),
                    "unit": "GB", "uncertainty": None, "evidence_ref": None})
        if storage.get("total_gb") is not None:
            out.append({"resource": "disk_total", "value": float(storage["total_gb"]),
                        "unit": "GB", "uncertainty": None, "evidence_ref": None})
    memory = readings.get("memory")
    if isinstance(memory, dict) and memory.get("available_gb") is not None:
        out.append({"resource": "memory_available", "value": float(memory["available_gb"]),
                    "unit": "GB", "uncertainty": None, "evidence_ref": None})
    thermal = readings.get("thermal")
    if isinstance(thermal, dict) and thermal.get("celsius") is not None:
        out.append({"resource": "cpu_temperature", "value": float(thermal["celsius"]),
                    "unit": "C", "uncertainty": None, "evidence_ref": None})
    battery = readings.get("battery")
    if isinstance(battery, dict) and battery.get("fraction") is not None:
        out.append({"resource": "battery", "value": float(battery["fraction"]),
                    "unit": "fraction", "uncertainty": None, "evidence_ref": None})
    return sorted(out, key=lambda r: r["resource"])


def capability_snapshot(*, body_id: str, node_id: str,
                        actions: Sequence[Mapping[str, Any]] = (),
                        sensors: Sequence[Mapping[str, Any]] = (),
                        state_root: Optional[os.PathLike | str] = None,
                        probes: Optional[Mapping[str, Callable[[], Any]]] = None,
                        readings: Optional[Mapping[str, Any]] = None,
                        now: Optional[float] = None) -> Any:
    """Build and validate the frozen ``capability_snapshot`` record (C0 contract)."""
    from System import swarm_adaptive_contracts as C

    measured = dict(readings) if readings is not None else run_probes(probes=probes,
                                                                      state_root=state_root)
    health = capability_health(state_root=state_root, now=now, readings=measured)
    facts = topology_facts(readings=measured)
    boot = current_boot(state_root=state_root)
    view = planning_view(actions, state_root=state_root, now=now, readings=measured)

    sensor_rows = []
    for sensor in sensors:
        sensor_id = str(sensor.get("sensor_id") or "")
        entry = health.get(sensor_id)
        lost = entry is not None and entry.get("state") == _LOST
        sensor_rows.append({
            "sensor_id": sensor_id,
            "modality": str(sensor.get("modality") or "unknown"),
            "coverage": None if lost else sensor.get("coverage"),
            "freshness_ms": None if lost else sensor.get("freshness_ms"),
            "source_id": str(sensor.get("source_id") or "unprobed"),
        })

    # the frozen record allows only name/reason_code/detail here; planner-internal
    # fields such as blocked_by stay in planning_view, out of the wire record.
    unavailable = [{"name": str(u["name"]), "reason_code": str(u["reason_code"]),
                    "detail": u.get("detail")} for u in view["unavailable"]]
    for name, entry in sorted(health.items()):
        if entry["state"] == _LOST and not any(u["name"] == name for u in unavailable):
            unavailable.append({"name": name, "reason_code": entry["reason_code"],
                                "detail": entry.get("detail")})

    record = {
        "schema_version": C.RECORDS_SCHEMA_VERSION,
        "snapshot_id": str(uuid.uuid4()),
        "body_id": body_id,
        "node_id": node_id,
        "boot_id": (boot or {}).get("boot_id") or str(uuid.uuid4()),
        "topology_revision": TOPOLOGY_SCHEMA_VERSION,
        "captured_at_utc": utc_now(now=now),
        "hardware": {
            "topology_id": topology_id(facts=facts),
            "platform_id": facts["platform_id"],
            "machine": facts["machine"],
            "processor": facts["processor"],
            "cpu_count": facts["cpu_count"],
            "physical_memory_gb": facts["physical_memory_gb"],
            "headless": facts["headless"],
            "roles": facts["roles"],
            "boot_sequence": (boot or {}).get("sequence"),
        },
        "os_facts": {
            "python": facts["python"] or "unknown",
            "hostname": str((boot or {}).get("hostname") or "unknown"),
            "headless": "yes" if facts["headless"] else ("no" if facts["headless"] is False else "unknown"),
            "network": {True: "reachable", False: "unreachable", None: "unknown"}[measured.get("network")],
        },
        "available_actions": [
            {"name": str(a.get("name") or ""),
             "input_schema": dict(a.get("input_schema") or {}),
             "output_schema": dict(a.get("output_schema") or {}),
             "preconditions": [str(p) for p in (a.get("preconditions") or ())],
             "adapter_id": str(a.get("adapter_id") or "unbound")}
            for a in view["available"]
        ],
        "sensor_coverage": sensor_rows,
        "resource_estimates": _resource_estimates(measured),
        "unavailable_capabilities": unavailable,
        "observation_evidence_refs": [],
    }
    return C.CapabilitySnapshot.from_dict(record)


def summary_lines(snapshot: Any) -> list[str]:
    """Short human-readable census for boot banners and receipts."""
    data = snapshot.to_dict() if hasattr(snapshot, "to_dict") else dict(snapshot)
    hw = data.get("hardware", {})
    lines = [
        f"body      : {data.get('body_id')} node {data.get('node_id')}",
        f"boot      : {data.get('boot_id')} (#{hw.get('boot_sequence')})",
        f"topology  : {hw.get('topology_id')} platform {hw.get('platform_id')} "
        f"roles {','.join(hw.get('roles') or []) or 'none'}",
        f"headless  : {hw.get('headless')}",
        f"resources : {len(data.get('resource_estimates') or [])} measured",
        f"actions   : {len(data.get('available_actions') or [])} available, "
        f"{len(data.get('unavailable_capabilities') or [])} unavailable",
    ]
    for entry in data.get("unavailable_capabilities") or []:
        lines.append(f"  lost    : {entry['name']} [{entry['reason_code']}] {entry.get('detail') or ''}".rstrip())
    return lines


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="SIFTA boot/topology identity + capability census")
    parser.add_argument("--state-root", default=None)
    parser.add_argument("--body-id", default=os.environ.get("SIFTA_BODY_ID", "body_local"))
    parser.add_argument("--node-id", default=os.environ.get("SIFTA_NODE_ID", "node_local"))
    parser.add_argument("--actions", default="[]", help="JSON list of action names/preconditions")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    actions = json.loads(args.actions)
    if actions and isinstance(actions[0], str):
        actions = [{"name": a} for a in actions]
    snap = capability_snapshot(body_id=args.body_id, node_id=args.node_id,
                               actions=actions, state_root=args.state_root)
    print(snap.to_json() if args.json else "\n".join(summary_lines(snap)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
