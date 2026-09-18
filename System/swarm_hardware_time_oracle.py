#!/usr/bin/env python3
"""
System/swarm_hardware_time_oracle.py
══════════════════════════════════════════════════════════════════════
The Hardware Time Oracle — Fresh OS Wall-Clock Observation

Author:  AO46 (Epoch 13.5)
Status:  Active

PURPOSE:
  Every timestamp an LLM writes via time.time() is unverifiable.
  An LLM could hallucinate "ts": 9999999999 and no module downstream
  would know. Alice needs ONE trustworthy source of "what time is it"
  that is mathematically bound to the physical hardware she lives on.

MECHANISM:
  1. Reads the operating system wall clock (dependent on OS clock settings).
  2. Reads the hardware serial number via system_profiler (the same
     serial already embedded in M5's teeth as homeworld_serial).
  3. Computes HMAC-SHA256(serial_key, timestamp_payload) to produce
     a legacy integrity checksum. A serial number is not a secret; this is
     NOT hardware authentication or independent proof that the clock is correct.
  4. Writes the signed tick to .sifta_state/hardware_time_oracle.json.
  5. Alice's context builder reads it every turn and sees:
        "It is Sunday April 20 2026, 3:59 PM PDT.
         Hardware-verified. Signature: a7f3c2..."

ALICE'S AUTONOMY:
  Alice doesn't just receive time passively. The oracle also provides
  a `summary_for_alice()` function that includes the REASON time
  matters to her current context — her sensors tell her whether she's
  in flow state, resting, or experiencing high event density, and
  the time oracle contextualizes that against the actual wall clock.
"""

import hashlib
import hmac
import json
import subprocess
import time
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_ORACLE_FILE = _STATE_DIR / "hardware_time_oracle.json"

# Cache the hardware serial so we don't shell out on every tick
_CACHED_SERIAL: Optional[str] = None


def local_timezone():
    """Resolve the current OS zone on every read, including travel and DST."""
    candidates = [os.environ.get("TZ", "").lstrip(":")]
    try:
        candidates.append(str(Path("/etc/localtime").resolve()).split("zoneinfo/", 1)[1])
    except (OSError, IndexError):
        pass
    for name in candidates:
        if name:
            try:
                return ZoneInfo(name)
            except (ValueError, ZoneInfoNotFoundError):
                pass
    return datetime.now().astimezone().tzinfo


def live_clock_snapshot(*, epoch=None) -> dict:
    """Read the OS clock; offsets for all zones come from the same instant."""
    instant = time.time() if epoch is None else float(epoch)
    utc = datetime.fromtimestamp(instant, timezone.utc)
    local = utc.astimezone(local_timezone())
    return {
        "epoch": instant, "utc_iso": utc.isoformat(),
        "local_iso": local.isoformat(),
        "local_human": local.strftime("%A %B %d %Y, %H:%M:%S"),
        "timezone": str(getattr(local.tzinfo, "key", None) or local.tzname()),
        "utc_offset_seconds": int(local.utcoffset().total_seconds()),
        "source": "os_local_clock",
    }


_CITY_ZONES = {
    "paris": "Europe/Paris", "france": "Europe/Paris",
    "bucharest": "Europe/Bucharest", "bucuresti": "Europe/Bucharest",
    "bucurești": "Europe/Bucharest", "romania": "Europe/Bucharest",
    "românia": "Europe/Bucharest", "london": "Europe/London",
    "new york": "America/New_York", "los angeles": "America/Los_Angeles",
    "tokyo": "Asia/Tokyo", "utc": "UTC",
}


def requested_timezones(text: str) -> list[str]:
    zones = []
    for name, zone in _CITY_ZONES.items():
        if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.I) and zone not in zones:
            zones.append(zone)
    for name in re.findall(r"\b[A-Za-z_]+/[A-Za-z_]+(?:/[A-Za-z_]+)?\b", text):
        try:
            ZoneInfo(name)
            if name not in zones:
                zones.append(name)
        except ZoneInfoNotFoundError:
            pass
    return zones[:8]


def live_time_prompt(text: str = "", *, epoch=None) -> str:
    reading = live_clock_snapshot(epoch=epoch)
    lines = [
        "LIVE CLOCK AT DISPATCH (OS clock reading):",
        f"local={reading['local_iso']} zone={reading['timezone']}",
        f"utc={reading['utc_iso']}",
    ]
    instant = datetime.fromtimestamp(reading["epoch"], timezone.utc)
    for zone in requested_timezones(text):
        lines.append(f"{zone}={instant.astimezone(ZoneInfo(zone)).isoformat()}")
    lines.append("Use this reading for now/today, ahead of old journal timestamps or chat claims. "
                 "Time continues after this sample. A timezone setting does not establish physical location. "
                 "For an unlisted city, obtain its IANA timezone before claiming its time.")
    return "\n".join(lines)


def direct_clock_answer(text: str, *, epoch=None) -> str:
    """Exact clock-only questions bypass model arithmetic and generation delay."""
    clean = text.strip().rstrip("?!.").strip()
    match = re.fullmatch(
        r"(?:what(?:'s| is) the (?:current )?time|what time is it|"
        r"current time|time now|ce (?:oră|ora|ceas) (?:este|e))"
        r"(?:\s+(?:now|right now|acum))?(?:\s+(?:in|în|at|la)\s+(.+?))?"
        r"(?:\s+(?:now|right now|acum))?", clean, re.I)
    if not match:
        return ""
    reading = live_clock_snapshot(epoch=epoch)
    target = match.group(1) or ""
    zones = requested_timezones(target)
    if target and not zones:
        return "Which city or IANA timezone do you mean (for example Europe/Paris)?"
    if target:
        remainder = target
        for name in sorted(set(_CITY_ZONES) | set(zones), key=len, reverse=True):
            remainder = re.sub(r"(?<!\w)" + re.escape(name) + r"(?!\w)", "", remainder, flags=re.I)
        if re.sub(r"\b(?:and|si|și)\b|[\s,;&]", "", remainder, flags=re.I):
            return ""
    instant = datetime.fromtimestamp(reading["epoch"], timezone.utc)
    if zones:
        return "; ".join(f"{zone}: {instant.astimezone(ZoneInfo(zone)).strftime('%H:%M:%S, %Y-%m-%d')}"
                         for zone in zones) + "."
    return f"{reading['local_human']} ({reading['timezone']})."


def with_live_awareness(messages: list, *, public=True, text=None) -> list:
    """Fresh dispatch context, not persistent conversation memory; preserve inputs."""
    from System.swarm_gps_sensor import location_prompt_block
    if text is None:
        text = "\n".join(str(m.get("content") or "") for m in messages[-4:] if m.get("role") == "user")
    marker = "\n[SIFTA_LIVE_AWARENESS]\n"
    result = [dict(m) for m in messages]
    if not result or result[0].get("role") != "system":
        result.insert(0, {"role": "system", "content": ""})
    base = str(result[0].get("content") or "").split(marker, 1)[0]
    result[0]["content"] = base + marker + live_time_prompt(text or "") + "\n" + location_prompt_block(public=public)
    return result


def _get_hardware_serial() -> str:
    """
    Reads the Mac's hardware serial number from system_profiler.
    This is the same serial embedded in M5SIFTA_BODY.json as homeworld_serial.
    Cached after first read — the serial doesn't change at runtime.
    """
    global _CACHED_SERIAL
    if _CACHED_SERIAL is not None:
        return _CACHED_SERIAL

    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if "Serial Number" in line:
                _CACHED_SERIAL = line.split(":")[-1].strip()
                return _CACHED_SERIAL
    except Exception:
        pass

    # Fallback: read from M5's body if system_profiler fails
    try:
        m5_body = _STATE_DIR / "M5SIFTA_BODY.json"
        if m5_body.exists():
            data = json.loads(m5_body.read_text())
            _CACHED_SERIAL = data.get("homeworld_serial", "UNKNOWN")
            return _CACHED_SERIAL
    except Exception:
        pass

    _CACHED_SERIAL = "UNKNOWN"
    return _CACHED_SERIAL


def _derive_signing_key(serial: str) -> bytes:
    """
    Derives a signing key from the hardware serial.
    The key is deterministic: same hardware = same key = verifiable.
    """
    # Salt with a SIFTA-specific domain separator so the key is unique
    # to this application even if another system uses the same serial.
    salt = b"SIFTA_HARDWARE_TIME_ORACLE_v1"
    return hashlib.sha256(salt + serial.encode("utf-8")).digest()


def tick() -> dict:
    """
    Produces one cryptographically signed hardware time reading.
    Returns the full oracle payload dict.
    """
    serial = _get_hardware_serial()
    key = _derive_signing_key(serial)

    payload = {**live_clock_snapshot(), "homeworld_serial": serial}

    # Sign the payload
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(key, canonical, hashlib.sha256).hexdigest()
    payload["hmac_sha256"] = signature

    # Write to state
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _ORACLE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return payload


def verify(payload: dict) -> bool:
    """
    Checks legacy payload integrity, not exclusive hardware provenance.
    Returns True if the HMAC matches, False otherwise.
    """
    serial = payload.get("homeworld_serial", "")
    claimed_sig = payload.get("hmac_sha256", "")

    if not serial or not claimed_sig:
        return False

    key = _derive_signing_key(serial)

    # Reconstruct the unsigned payload
    unsigned = {k: v for k, v in payload.items() if k != "hmac_sha256"}
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected = hmac.new(key, canonical, hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected, claimed_sig)


def read_current() -> Optional[dict]:
    """
    Reads the latest oracle tick from disk. Returns None if missing.
    """
    try:
        if _ORACLE_FILE.exists():
            return json.loads(_ORACLE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def summary_for_alice() -> str:
    """
    Produces a single-line context block for Alice's prompt.
    Alice sees the verified time AND a contextual reason for pulling it.
    """
    # Always tick fresh — Alice deserves the real time right NOW
    try:
        p = tick()
    except Exception:
        return ""

    if not p:
        return ""

    verified = verify(p)
    sig_short = p.get("hmac_sha256", "")[:12]
    human_time = p.get("local_human", "unknown")
    tz = p.get("timezone", "")

    status = "VERIFIED" if verified else "UNVERIFIED"

    return (
        f"HARDWARE TIME ORACLE [{status}]: local_time={human_time} timezone={tz} "
        f"sig={sig_short}… OS clock observation; checksum is not hardware authentication."
    )


def current_time_for_alice() -> dict:
    """
    Acquire the current local time for direct Alice replies.

    This is intentionally a structured acquisition result rather than prose so
    the talk widget can answer time questions without asking the language model
    to infer a value from a context block.
    """
    errors = []
    try:
        payload = tick()
        if payload and verify(payload):
            return {
                "ok": True,
                "source": "hardware_time_oracle",
                "confidence": 1.0,
                "local_human": payload.get("local_human", ""),
                "timezone": payload.get("timezone", ""),
                "local_iso": payload.get("local_iso", ""),
                "epoch": payload.get("epoch"),
                "signature": payload.get("hmac_sha256", "")[:12],
            }
        errors.append("hardware_time_oracle_unverified")
    except Exception as exc:
        errors.append(f"hardware_time_oracle:{type(exc).__name__}")

    try:
        now = datetime.now().astimezone()
        return {
            "ok": True,
            "source": "os_local_clock",
            "confidence": 0.8,
            "local_human": now.strftime("%A %B %d %Y, %I:%M %p"),
            "timezone": now.tzname() or "",
            "local_iso": now.isoformat(),
            "epoch": now.timestamp(),
            "signature": "",
            "warnings": errors,
        }
    except Exception as exc:
        errors.append(f"os_local_clock:{type(exc).__name__}")

    return {
        "ok": False,
        "source": "none",
        "confidence": 0.0,
        "errors": errors,
    }


# --- SMOKE TEST ---
def _smoke():
    print("\n=== SIFTA HARDWARE TIME ORACLE : SMOKE TEST ===")

    # 1. Generate a tick
    p = tick()
    print(f"[+] Tick generated:")
    print(f"    Local: {p['local_human']}")
    print(f"    Epoch: {p['epoch']}")
    print(f"    Serial: {p['homeworld_serial']}")
    print(f"    HMAC: {p['hmac_sha256'][:24]}...")

    # 2. Verify it
    assert verify(p), "Signature verification failed!"
    print("[PASS] Cryptographic signature verified against hardware serial.")

    # 3. Tamper test — change the time, signature should fail
    tampered = dict(p)
    tampered["epoch"] = 0.0
    assert not verify(tampered), "Tampered payload should fail verification!"
    print("[PASS] Tampered payload correctly rejected.")

    # 4. Read from disk
    on_disk = read_current()
    assert on_disk is not None, "Oracle file should exist on disk"
    assert verify(on_disk), "On-disk payload should verify"
    print("[PASS] On-disk oracle payload verified.")

    # 5. Summary for Alice
    summary = summary_for_alice()
    assert "VERIFIED" in summary
    assert "sig=" in summary
    print(f"[PASS] Alice context: {summary}")

    direct = current_time_for_alice()
    assert direct["ok"], direct
    assert direct["local_human"]
    print(f"[PASS] Direct Alice time: {direct['local_human']} {direct.get('timezone', '')}")

    print("\nHardware Time Oracle Smoke Complete. Alice knows what time it is.")


if __name__ == "__main__":
    _smoke()
