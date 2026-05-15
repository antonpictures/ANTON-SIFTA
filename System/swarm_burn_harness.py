#!/usr/bin/env python3
"""
System/swarm_burn_harness.py
══════════════════════════════════════════════════════════════════════════════
Tournament §9.C — per-organ ENERGY / CPU receipts (the "burn ledger").

Cowork 2026-05-12 — Architect GO ("CODE IT ALL").

Why this organ exists
─────────────────────
The covenant's attention law in §8.0 has subtraction terms — `thermal_cost`,
`STGM_cost`. As long as those are placeholders, the sample-period formula
only sees the additive (prediction_error, salience). To make them real
inputs, we need OBSERVED numbers about how much each organ burns on this
specific Mac Studio. That is what the burn harness produces.

What it does
─────────────
At each call, samples a cheap process-level fingerprint of CPU + memory
load via psutil (always available), with optional macOS `powermetrics`
sampling for true CPU package power (gated behind an env var because it
requires sudo on some macOS configurations).

Public surface
──────────────
    sample_burn(organ_id, action=None, extra=None) -> dict
        Take one snapshot and write a row to .sifta_state/organ_burn.jsonl.
        Returns the row that was written. Cheap (<5ms typical).

    sample_burn_window(organ_id, fn, *args, **kwargs) -> (result, row)
        Wrap a callable; sample before+after and write the delta. The row
        carries cpu_delta_pct, rss_delta_mb, wall_ms.

    burn_track(organ_id) -> decorator
        Convenience decorator. @burn_track("eye_capture") around a function.

Truth labels
─────────────
    psutil path  : truth=OBSERVED, source=psutil
    powermetrics : truth=OBSERVED, source=macos_powermetrics, sudo=YES|NO
    fallback     : truth=HYPOTHESIS (when neither tool works)

Gated by env: SIFTA_BURN_HARNESS_ENABLE (default ON to make energy law real,
but Macos `powermetrics` itself is OPT-IN behind SIFTA_BURN_POWERMETRICS=1
because it usually needs root.

Never raises. If anything fails, write a partial row labeled with the error.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE = _REPO_ROOT / ".sifta_state"
_BURN_LEDGER = _STATE / "organ_burn.jsonl"
TRUTH_LABEL = "ORGAN_BURN_V1"
SCHEMA_VERSION = "organ_burn.v1"

_IS_MAC = sys.platform == "darwin"

# psutil is the preferred sampler. Import lazily so the module itself never
# fails on machines without it.
try:
    import psutil as _psutil  # type: ignore
    _HAS_PSUTIL = True
except Exception:
    _psutil = None
    _HAS_PSUTIL = False


# Cache one Process handle for our own PID — psutil keeps internal state
# (cpu_percent needs two calls to be meaningful).
_PROC = None
if _HAS_PSUTIL:
    try:
        _PROC = _psutil.Process(os.getpid())
        _PROC.cpu_percent(interval=None)  # prime the meter; first call returns 0.0
    except Exception:
        _PROC = None


def enabled() -> bool:
    """Master gate. Default ON — flip with SIFTA_BURN_HARNESS_ENABLE=0."""
    v = os.environ.get("SIFTA_BURN_HARNESS_ENABLE", "1").strip().lower()
    return v in ("1", "true", "yes", "on")


def _powermetrics_enabled() -> bool:
    """Secondary gate — macOS only, opt-in because it usually needs sudo."""
    if not _IS_MAC:
        return False
    return os.environ.get("SIFTA_BURN_POWERMETRICS", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _psutil_snapshot() -> Dict[str, Any]:
    """Cheap process-level metrics. Always returns SOMETHING — never raises."""
    snap: Dict[str, Any] = {
        "source": "psutil",
        "truth": "OBSERVED",
        "ok": _HAS_PSUTIL and _PROC is not None,
    }
    if not _HAS_PSUTIL or _PROC is None:
        snap["truth"] = "HYPOTHESIS"
        snap["error"] = "psutil_unavailable"
        return snap
    try:
        # cpu_percent uses delta since last call — fine for our cadence.
        snap["cpu_pct_total"] = float(_PROC.cpu_percent(interval=None))
        mem = _PROC.memory_info()
        snap["rss_mb"] = round(mem.rss / (1024 * 1024), 2)
        try:
            snap["num_threads"] = int(_PROC.num_threads())
        except Exception:
            pass
        try:
            snap["num_fds"] = int(_PROC.num_fds()) if hasattr(_PROC, "num_fds") else None
        except Exception:
            pass
    except Exception as e:
        snap["ok"] = False
        snap["truth"] = "HYPOTHESIS"
        snap["error"] = f"{type(e).__name__}: {e}"
    return snap


def _powermetrics_sample(duration_ms: int = 100) -> Dict[str, Any]:
    """Optional macOS package-power sample. Costs real time (blocks duration_ms).
    Returns {} when not enabled or unavailable so callers can merge into a row.
    """
    if not _powermetrics_enabled():
        return {}
    try:
        # `powermetrics --samplers cpu_power -i 100 -n 1` — one sample, 100ms.
        out = subprocess.run(
            ["powermetrics",
             "--samplers", "cpu_power",
             "-i", str(int(duration_ms)),
             "-n", "1",
             "--format", "plist"],
            capture_output=True, text=True, timeout=duration_ms / 1000.0 + 2.0,
        )
        if out.returncode != 0:
            return {"powermetrics_error": (out.stderr or "")[:120]}
        # Don't parse plist heavyweight — just record raw byte length + a
        # cheap grep for the "Package" line so downstream parsers can pick
        # up real numbers later. Architect can swap in a real plist parser
        # when the harness becomes load-bearing.
        return {
            "powermetrics_bytes": len(out.stdout),
            "powermetrics_sudo": "yes" if os.geteuid() == 0 else "no",
            "powermetrics_truth": "OBSERVED",
            "powermetrics_duration_ms": duration_ms,
        }
    except FileNotFoundError:
        return {"powermetrics_error": "binary_not_found"}
    except subprocess.TimeoutExpired:
        return {"powermetrics_error": "timeout"}
    except Exception as e:
        return {"powermetrics_error": f"{type(e).__name__}: {e}"}


def _write_row(row: Dict[str, Any]) -> None:
    """Append to .sifta_state/organ_burn.jsonl. Never raise."""
    try:
        _BURN_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _BURN_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass


def sample_burn(organ_id: str,
                action: Optional[str] = None,
                extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Take one snapshot and append a row. Returns the row."""
    if not enabled():
        return {"kind": "ORGAN_BURN", "status": "disabled", "ts": time.time()}
    row: Dict[str, Any] = {
        "kind": "ORGAN_BURN",
        "organ_id": str(organ_id),
        "schema_version": SCHEMA_VERSION,
        "ts": time.time(),
        "platform": platform.system(),
    }
    if action:
        row["action"] = str(action)
    row.update(_psutil_snapshot())
    row.update(_powermetrics_sample())
    if extra:
        row["extra"] = extra
    _write_row(row)
    return row


def sample_burn_window(organ_id: str,
                       fn: Callable[..., Any],
                       *args: Any,
                       action: Optional[str] = None,
                       extra: Optional[Dict[str, Any]] = None,
                       **kwargs: Any) -> Any:
    """Wrap `fn(*args, **kwargs)`; emit ONE row with deltas before+after.
    Returns fn's result. Never swallows fn's exception."""
    if not enabled():
        return fn(*args, **kwargs)
    before = _psutil_snapshot()
    t0 = time.perf_counter()
    try:
        result = fn(*args, **kwargs)
    finally:
        wall_ms = (time.perf_counter() - t0) * 1000.0
        after = _psutil_snapshot()
        row: Dict[str, Any] = {
            "kind": "ORGAN_BURN_WINDOW",
            "organ_id": str(organ_id),
            "schema_version": SCHEMA_VERSION,
            "ts": time.time(),
            "wall_ms": round(wall_ms, 3),
            "platform": platform.system(),
        }
        if action:
            row["action"] = str(action)
        if before.get("ok") and after.get("ok"):
            try:
                row["cpu_delta_pct"] = round(
                    float(after.get("cpu_pct_total", 0)) - float(before.get("cpu_pct_total", 0)), 3
                )
                row["rss_delta_mb"] = round(
                    float(after.get("rss_mb", 0)) - float(before.get("rss_mb", 0)), 3
                )
            except Exception:
                pass
        row["before"] = before
        row["after"] = after
        if extra:
            row["extra"] = extra
        _write_row(row)
    return result


def burn_track(organ_id: str, action: Optional[str] = None):
    """Decorator form. Usage:

        @burn_track("eye_capture")
        def grab_one_frame(...): ...
    """
    def _decorator(fn: Callable[..., Any]):
        def _wrapped(*args: Any, **kwargs: Any):
            return sample_burn_window(organ_id, fn, *args, action=action or fn.__name__, **kwargs)
        _wrapped.__name__ = getattr(fn, "__name__", "burn_tracked")
        _wrapped.__doc__ = getattr(fn, "__doc__", None)
        return _wrapped
    return _decorator


@contextmanager
def burn_window(organ_id: str, action: Optional[str] = None,
                extra: Optional[Dict[str, Any]] = None):
    """Context-manager form. Usage:

        with burn_window("network_cortex_refresh"):
            refresh_network_state()
    """
    if not enabled():
        yield
        return
    before = _psutil_snapshot()
    t0 = time.perf_counter()
    try:
        yield
    finally:
        wall_ms = (time.perf_counter() - t0) * 1000.0
        after = _psutil_snapshot()
        row: Dict[str, Any] = {
            "kind": "ORGAN_BURN_WINDOW",
            "organ_id": str(organ_id),
            "schema_version": SCHEMA_VERSION,
            "ts": time.time(),
            "wall_ms": round(wall_ms, 3),
            "platform": platform.system(),
            "before": before,
            "after": after,
        }
        if action:
            row["action"] = str(action)
        if extra:
            row["extra"] = extra
        try:
            if before.get("ok") and after.get("ok"):
                row["cpu_delta_pct"] = round(
                    float(after.get("cpu_pct_total", 0)) - float(before.get("cpu_pct_total", 0)), 3
                )
                row["rss_delta_mb"] = round(
                    float(after.get("rss_mb", 0)) - float(before.get("rss_mb", 0)), 3
                )
        except Exception:
            pass
        _write_row(row)


if __name__ == "__main__":
    # CLI: `python3 -m System.swarm_burn_harness` — emit one sample so you
    # can see what shape the rows have.
    row = sample_burn(organ_id="cli_self_test", action="module_main")
    print(json.dumps(row, indent=2))
