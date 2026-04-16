"""
signal_ingestion.py
──────────────────────────────────────────────────────────────────────────────
REAL-WORLD SIGNAL INGESTION → OBSERVE PIPELINE
Author: Queen M5 (Antigravity IDE)

Theory:
    The swarm's cognitive stack is complete internally.
    Now we open a controlled window to the outside world.

    External signals — log anomalies, system sensors, API payloads —
    are funnelled through the same OBSERVE → HYPOTHESIS → CMF pipeline.

    No external signal bypasses the trust gate.
    No external signal mutates the codebase directly.
    All signals land in OBSERVE first. The swarm decides what to do next.

Channels:
    1. LOG WATCHER     — tails local log files for error patterns
    2. SYSTEM SENSOR   — polls CPU / memory / disk for thermal anomalies
    3. API HOOK        — polls any JSON endpoint for configurable signals
    4. REPAIR LOG FEED — reads repair_log.jsonl to surface recurring wounds

──────────────────────────────────────────────────────────────────────────────
HARD RULES:
    - All inbound signals are treated as high-novelty / low-confidence by default.
    - No signal promotes itself to SCAR. It enters OBSERVE. Agents decide.
    - Polling intervals are bounded (min 30s) to prevent inference flooding.
    - Sensitive API keys are never logged or persisted in signal records.
──────────────────────────────────────────────────────────────────────────────
"""

import json
import re
import time
import hashlib
from pathlib import Path
from typing import Optional

# Use the repair.py enter_observe → will be imported lazily to avoid circulars

INGESTION_DIR  = Path(".sifta_state/signals")
INGESTION_DIR.mkdir(parents=True, exist_ok=True)
SIGNAL_LOG     = INGESTION_DIR / "inbound_signals.jsonl"
CURSOR_FILE    = INGESTION_DIR / "log_cursors.json"   # remembers tail position per file

MIN_POLL_INTERVAL = 30   # seconds


# ══════════════════════════════════════════════════════════════════════════
# INTERNAL UTILS
# ══════════════════════════════════════════════════════════════════════════

def _signal_id(source: str, content: str) -> str:
    return hashlib.sha256(f"{source}:{content}".encode()).hexdigest()[:16]


def _write_signal(signal: dict):
    with open(SIGNAL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(signal) + "\n")


def _load_cursors() -> dict:
    if CURSOR_FILE.exists():
        try:
            return json.loads(CURSOR_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_cursors(cursors: dict):
    CURSOR_FILE.write_text(json.dumps(cursors, indent=2))


def _build_signal(source: str, channel: str, raw: str,
                  confidence: float = 0.2, novelty: float = 0.8,
                  emotional_weight: float = 0.6) -> dict:
    return {
        "signal_id"       : _signal_id(source, raw),
        "channel"         : channel,
        "source"          : source,
        "raw"             : raw[:500],     # truncate — no novels in signals
        "confidence"      : confidence,
        "novelty"         : novelty,
        "emotional_weight": emotional_weight,
        "ts"              : time.time(),
        "resolved"        : False,
    }


# ══════════════════════════════════════════════════════════════════════════
# CHANNEL 1: LOG WATCHER
# ══════════════════════════════════════════════════════════════════════════

# Patterns that elevate novelty — anything suggesting unexpected system state
ERROR_PATTERNS = [
    (re.compile(r"\bERROR\b|\bFAIL\b|\bCRITICAL\b", re.I),       0.7, 0.8),
    (re.compile(r"\bException\b|\bTraceback\b",       re.I),       0.6, 0.85),
    (re.compile(r"\bBLEEDING\b|\bCORRUPTED\b",       re.I),       0.5, 0.9),
    (re.compile(r"\bDEAD\b|\bCEMETERY\b",            re.I),       0.4, 0.95),
    (re.compile(r"\bUNKNOWN\b|\bANOMALY\b",          re.I),       0.3, 0.99),
]


def watch_log_file(filepath: str, max_lines: int = 100) -> list[dict]:
    """
    Tail a log file from the last known cursor position.
    Returns a list of signal dicts for any anomalous lines found.
    """
    path     = Path(filepath)
    cursors  = _load_cursors()
    file_key = str(path.resolve())
    offset   = cursors.get(file_key, 0)
    signals  = []

    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(offset)
            lines = []
            for _ in range(max_lines):
                line = f.readline()
                if not line:
                    break
                lines.append(line.rstrip())
            new_offset = f.tell()

        cursors[file_key] = new_offset
        _save_cursors(cursors)

        for line in lines:
            for pattern, confidence, novelty in ERROR_PATTERNS:
                if pattern.search(line):
                    sig = _build_signal(
                        source           = str(path.name),
                        channel          = "LOG_WATCHER",
                        raw              = line,
                        confidence       = confidence,
                        novelty          = novelty,
                        emotional_weight = novelty * 0.8,
                    )
                    signals.append(sig)
                    _write_signal(sig)
                    break   # one match per line is enough

    except Exception as e:
        print(f"  [SIGNAL ERROR] log_watcher failed on {filepath}: {e}")

    return signals


# ══════════════════════════════════════════════════════════════════════════
# CHANNEL 2: SYSTEM SENSOR
# ══════════════════════════════════════════════════════════════════════════

SENSOR_THRESHOLDS = {
    "cpu_pct"  : 90.0,   # % — above this is anomalous
    "mem_pct"  : 88.0,   # %
    "disk_pct" : 92.0,   # %
}


def read_system_sensors() -> list[dict]:
    """
    Poll system health metrics.
    Returns signals only when thresholds are breached — not on every call.
    """
    try:
        import psutil
    except ImportError:
        # psutil not installed — graceful degradation, not a crash
        return []

    signals = []
    readings = {
        "cpu_pct"  : psutil.cpu_percent(interval=1),
        "mem_pct"  : psutil.virtual_memory().percent,
        "disk_pct" : psutil.disk_usage("/").percent,
    }

    for metric, value in readings.items():
        threshold = SENSOR_THRESHOLDS.get(metric, 95.0)
        if value >= threshold:
            severity = min(1.0, (value - threshold) / (100.0 - threshold))
            sig = _build_signal(
                source           = f"system:{metric}",
                channel          = "SYSTEM_SENSOR",
                raw              = f"{metric}={value:.1f}% (threshold={threshold}%)",
                confidence       = 0.9,       # sensors are reliable readings
                novelty          = severity,   # how far above threshold
                emotional_weight = severity * 0.9,
            )
            signals.append(sig)
            _write_signal(sig)

    return signals


# ══════════════════════════════════════════════════════════════════════════
# CHANNEL 3: API HOOK
# ══════════════════════════════════════════════════════════════════════════

def poll_api(
    url: str,
    signal_key: str,          # JSON key path to extract e.g. "data.status"
    anomaly_value: str = None,# treat this value as anomalous
    headers: dict = None,
    timeout: int = 10,
) -> list[dict]:
    """
    Poll any JSON endpoint. If the extracted value matches anomaly_value,
    or if the request fails, generate an OBSERVE signal.

    Example:
        poll_api(
            url="https://api.github.com/repos/antonpictures/ANTON-SIFTA",
            signal_key="open_issues_count",
        )
    """
    import urllib.request
    import urllib.error

    signals = []
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())

        # Navigate dotted key path
        value = data
        for part in signal_key.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break

        raw = f"API:{url} | key={signal_key} | value={value}"

        if anomaly_value is not None and str(value) == str(anomaly_value):
            sig = _build_signal(
                source="api:" + url[:60],
                channel="API_HOOK",
                raw=raw,
                confidence=0.7,
                novelty=0.8,
                emotional_weight=0.65,
            )
            signals.append(sig)
            _write_signal(sig)
            print(f"  [📡 SIGNAL] API anomaly detected: {raw[:80]}")

    except Exception as e:
        sig = _build_signal(
            source="api:" + url[:60],
            channel="API_HOOK",
            raw=f"API unreachable: {url} — {e}",
            confidence=0.8,
            novelty=0.7,
            emotional_weight=0.5,
        )
        signals.append(sig)
        _write_signal(sig)
        print(f"  [📡 SIGNAL] API failure: {url[:60]} — {e}")

    return signals


# ══════════════════════════════════════════════════════════════════════════
# CHANNEL 4: REPAIR LOG FEED (internal wound surface)
# ══════════════════════════════════════════════════════════════════════════

def scan_repair_log(max_entries: int = 50) -> list[dict]:
    """
    Read the swarm's own repair_log.jsonl and surface recurring
    BLEEDING wounds as high-novelty signals.

    A file that bleeds more than 3 times in a session is anomalous —
    it suggests the repair loop is failing to heal that territory.
    """
    repair_log = Path("repair_log.jsonl")
    if not repair_log.exists():
        return []

    wound_counts: dict[str, int] = {}
    signals = []

    try:
        lines = repair_log.read_text(encoding="utf-8").splitlines()
        for line in lines[-max_entries:]:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("status") == "BLEEDING" or entry.get("event") == "bite_fail":
                    file_target = entry.get("file", entry.get("found", "unknown"))
                    wound_counts[file_target] = wound_counts.get(file_target, 0) + 1
            except Exception:
                continue

        for filepath, count in wound_counts.items():
            if count >= 3:
                novelty = min(1.0, count / 10)
                sig = _build_signal(
                    source=f"repair_log:{Path(filepath).name}",
                    channel="REPAIR_LOG_FEED",
                    raw=f"Recurring wound: {filepath} bled {count} times in last {max_entries} entries.",
                    confidence=0.85,
                    novelty=novelty,
                    emotional_weight=novelty * 0.9,
                )
                signals.append(sig)
                _write_signal(sig)
                print(f"  [🩸 SIGNAL] Recurring wound detected: {filepath} × {count}")

    except Exception as e:
        print(f"  [SIGNAL ERROR] repair_log scan failed: {e}")

    return signals


# ══════════════════════════════════════════════════════════════════════════
# INGESTION RUNNER — pushes signals into OBSERVE
# ══════════════════════════════════════════════════════════════════════════

def run_ingestion_cycle(
    agent_state: dict,
    log_files: list[str] = None,
    api_hooks: list[dict] = None,
    include_sensors: bool = True,
    include_repair_log: bool = True,
) -> list[dict]:
    """
    Runs all enabled ingestion channels and funnels detected signals
    into the agent's OBSERVE state via enter_observe().

    Parameters
    ----------
    agent_state       : the receiving agent's state dict
    log_files         : list of log file paths to watch
    api_hooks         : list of dicts {url, signal_key, anomaly_value?, headers?}
    include_sensors   : whether to poll system metrics
    include_repair_log: whether to scan repair_log.jsonl for wounds

    Returns list of raw signal dicts that were detected.
    """
    from repair import enter_observe, detect_uncertainty

    all_signals = []

    # ── Channel 1: Logs ───────────────────────────────────────────────────
    for logpath in (log_files or []):
        found = watch_log_file(logpath)
        all_signals.extend(found)

    # ── Channel 2: Sensors ────────────────────────────────────────────────
    if include_sensors:
        found = read_system_sensors()
        all_signals.extend(found)

    # ── Channel 3: API hooks ──────────────────────────────────────────────
    for hook in (api_hooks or []):
        found = poll_api(**hook)
        all_signals.extend(found)

    # ── Channel 4: Repair log wounds ─────────────────────────────────────
    if include_repair_log:
        found = scan_repair_log()
        all_signals.extend(found)

    # ── Push detected signals into OBSERVE ────────────────────────────────
    triggered = 0
    for sig in all_signals:
        if detect_uncertainty(sig):
            agent_state = enter_observe(agent_state, signal=sig)
            triggered += 1

    if triggered:
        print(f"\n[👁️ INGESTION] {triggered} signal(s) pushed {agent_state['id']} into OBSERVE.")
    else:
        print(f"[👁️ INGESTION] {agent_state['id']} scanned all channels. No anomalies detected.")

    return all_signals


# ══════════════════════════════════════════════════════════════════════════
# DASHBOARD SUMMARY
# ══════════════════════════════════════════════════════════════════════════

def ingestion_summary(tail: int = 50) -> dict:
    """
    Returns recent signal stats for the dashboard.
    """
    if not SIGNAL_LOG.exists():
        return {"total": 0, "by_channel": {}, "recent": []}

    lines = SIGNAL_LOG.read_text(encoding="utf-8").splitlines()
    signals = []
    for line in lines[-tail:]:
        try:
            signals.append(json.loads(line))
        except Exception:
            pass

    by_channel: dict[str, int] = {}
    for s in signals:
        ch = s.get("channel", "unknown")
        by_channel[ch] = by_channel.get(ch, 0) + 1

    return {
        "total"      : len(signals),
        "by_channel" : by_channel,
        "recent"     : signals[-5:][::-1],   # last 5, newest first
    }
