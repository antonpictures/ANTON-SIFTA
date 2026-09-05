"""Bounded HUD observations and off-GUI refresh of the canonical wallet cache."""
from __future__ import annotations

import math
import threading
import time
from pathlib import Path

from System.swarm_heartbeat_economy import _latest, _read, signature_valid

_lock = threading.Lock()
_busy = False
_last_attempt = 0.0


def hud_evidence(state_dir: Path, *, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    sd = Path(state_dir)
    try:
        heart = _latest(sd / "hardware_heart.jsonl")
        health = _read(sd / "heartbeat_economy_latest.json")
        cache = _read(sd / "stgm_economy_cache.json")
        if not all(isinstance(row, dict) for row in (heart, health, cache)):
            raise ValueError("Malformed HUD receipt")
    except (OSError, ValueError, TypeError):
        return {"state": "UNAVAILABLE", "detail": "Date indisponibile", "cache_stale": True}
    try:
        age = now - float(heart.get("ts", 0))
        fresh = math.isfinite(age) and 0 <= age <= 180 and bool(heart.get("receipt_id"))
        fresh = fresh and heart.get("schema") == "SIFTA_HARDWARE_HEART_V1"
        valid = bool(health.get("event_id")) and signature_valid(health)
        state = str(health.get("status", "AWAITING")) if valid else "AWAITING"
        if not fresh:
            state = "STALE"
        delta = float(health.get("delta_stgm", 0)) if valid else None
        health_age = now - float(health.get("ts", 0))
        # A current heart must not make an old settlement look like current health.
        if fresh and valid and (not math.isfinite(health_age) or not 0 <= health_age <= 180):
            state = "AWAITING"
        cache_ts = float(cache.get("cache_generated_at", 0))
        stale = (not math.isfinite(cache_ts) or not 0 <= now - cache_ts <= 90
                 or (valid and cache_ts < float(health["ts"])))
        detail = f"Ultima {delta:+.8f} STGM" if delta is not None else "Fara tranzactie verificata"
        detail += f" | {state}"
        return {"state": state, "detail": detail, "delta": delta,
                "heart_id": heart.get("receipt_id") if fresh else None,
                "heart_age": age if fresh else None,
                "event_id": health.get("event_id") if valid else None,
                "faults": health.get("faults", []) if valid else [],
                "cache_stale": stale, "cache_ts": cache_ts}
    except (ValueError, TypeError, KeyError):
        return {"state": "UNAVAILABLE", "detail": "Date invalide", "cache_stale": True}


def request_cache_refresh(state_dir: Path) -> bool:
    """At most one background replay per minute; never freeze the Qt timer."""
    global _busy, _last_attempt
    with _lock:
        now = time.monotonic()
        if _busy or (_last_attempt > 0 and now - _last_attempt < 60):
            return False
        _busy, _last_attempt = True, now

    def worker():
        global _busy
        try:
            from System.stgm_economy import refresh_stgm_economy_cache
            sd = Path(state_dir)
            refresh_stgm_economy_cache(repair_log=sd.parent / "repair_log.jsonl",
                                       state_dir=sd, cache_path=sd / "stgm_economy_cache.json")
        finally:
            with _lock:
                _busy = False

    try:
        threading.Thread(target=worker, daemon=True, name="StgmHudCache").start()
    except Exception:
        with _lock:
            _busy = False
        raise
    return True
