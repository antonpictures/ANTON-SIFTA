#!/usr/bin/env python3
"""
System/swarm_camera_target.py — Canonical "active eye" target
═══════════════════════════════════════════════════════════════════════════
Concept: One ledger, one schema, one truth for which physical camera Alice
is currently looking through.

Author:  C47H — surgery 2026-04-23, diagnosed by doctor codex IDE
Status:  Active organ (canonical contract)

WHY THIS EXISTS
───────────────
Before this surgery, three independent organs wrote `.sifta_state/
active_saccade_target.txt` in three different shapes (integer index,
camera name string, sometimes both), and three independent readers
parsed it three different ways:

  - `System/swarm_oculomotor_saccades.py`        wrote a NAME string
  - `System/swarm_multisensory_colliculus.py`    wrote an INTEGER index
  - `System/swarm_iris.py._get_saccade_target`   only accepted INTEGER
  - `Applications/sifta_what_alice_sees_widget`  did substring `findText`

The substring matcher hit "1" inside the Logitech entry
`USB Camera VID:1133 PID:2081`, which is why the Logitech LED stayed on
while iris thought Alice was on camera-index 1 (MacBook Pro Camera).

CANONICAL SCHEMA
────────────────
File:  `.sifta_state/active_saccade_target.json`

    {
        "name":       "MacBook Pro Camera",   # human / Qt description
        "index":      1,                      # AVFoundation / cv2 index
        "unique_id":  "0x1410000005ac8600",  # QCameraDevice.id() if known
        "ts":         1776921333.123,         # unix
        "writer":     "swarm_oculomotor_saccades",
        "priority":   20,                     # higher active lease wins
        "lease_until":1776921335.123          # optional unix expiry
    }

RESOLUTION ORDER (readers MUST follow)
──────────────────────────────────────
    1. unique_id  — exact match against live QMediaDevices ids
    2. name       — exact match (case-sensitive, never substring)
    3. index      — last-resort tiebreaker

BACK-COMPAT
───────────
On read, if `.json` is absent but the legacy `.txt` exists, this module
parses the .txt (bare integer OR bare name) and atomically rewrites it
as `.json`. The .txt is then kept as a one-line index mirror so any
stragglers we missed still see *something* valid.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_STATE = _REPO / ".sifta_state"
TARGET_JSON: Path = _STATE / "active_saccade_target.json"
TARGET_TXT_LEGACY: Path = _STATE / "active_saccade_target.txt"
TOPOLOGY_JSON: Path = _STATE / "camera_topology_latest.json"
DEVICE_EVENTS_JSONL: Path = _STATE / "device_events.jsonl"


# Current macOS/AVFoundation map observed on Alice's M5 rig during the
# 2026-04-23 camera split-brain surgery. These are fallbacks only; live Qt
# device ids/names still win when available.
_INDEX_TO_NAME = {
    2: "OBS Virtual Camera",
    3: "iPhone Camera",
    4: "Ioan's iPhone Camera",
    5: "MacBook Pro Desk View Camera",
    6: "iPhone Desk View Camera",
}

_NAME_TO_INDEX = {
    "obs virtual camera": 2,
    "iphone camera": 3,
    "iphone 15 camera": 3,
    "ioan's iphone camera": 4,
    "ioan’s iphone camera": 4,
    "macbook pro desk view camera": 5,
    "iphone desk view camera": 6,
}


# ── owner-eye safety (CUR-V4, 2026-06-13) ───────────────────────────────────
# George: "someone keeps accessing my iPhone camera — Cursor while coding."
# Root cause: macOS Continuity Camera renumbers AVFoundation indices when the
# iPhone is in range, so a bare index resolved against the frozen map above
# opens the iPhone instead of the built-in. These pure helpers let every
# capture path (a) prefer the built-in owner eye and refuse the iPhone /
# Continuity unless George explicitly selects it, and (b) refuse any LIVE
# camera open during tests / coding so an arm never wakes his phone. Runtime
# Talk is unaffected — the guard only bites under pytest / SIFTA_NO_LIVE_CAMERA.
import re as _re

_IPHONE_CONTINUITY_RE = _re.compile(r"(iphone|ipad|continuity|desk\s*view)", _re.IGNORECASE)
_BUILTIN_OWNER_RE = _re.compile(r"(macbook\s*pro\s*camera|facetime|built[\s-]*in)", _re.IGNORECASE)
_VIRTUAL_CAMERA_RE = _re.compile(r"(obs|virtual|screen\s*capture|passthrough)", _re.IGNORECASE)
_OWNER_IPHONE_ALLOWED_WRITERS = {
    "owner_camera_command",
    "what_alice_sees_widget",
    "sifta_what_alice_sees_widget",
}
_OWNER_LOCKED_CAMERA_WRITERS = _OWNER_IPHONE_ALLOWED_WRITERS | {
    "spinal_reflex_camera_switch",
    "swarm_sensor_attention_director",
}


def is_iphone_or_continuity(name: Optional[str]) -> bool:
    """True for iPhone / iPad / Continuity / Desk View cameras. These must never
    be auto-selected as the owner eye — Continuity index drift is what kept
    opening George's phone. 'Desk View' is a Continuity feature, so excluded."""
    if not name:
        return False
    return bool(_IPHONE_CONTINUITY_RE.search(str(name)))


def is_builtin_owner_camera(name: Optional[str]) -> bool:
    """True for the built-in MacBook / FaceTime camera — the default owner eye."""
    if not name:
        return False
    return bool(_BUILTIN_OWNER_RE.search(str(name))) and not is_iphone_or_continuity(name)


def is_virtual_or_loopback_camera(name: Optional[str]) -> bool:
    """True for OBS/virtual/loopback camera endpoints.

    These can be useful as deliberate tooling, but they are not physical body
    eyes. By default they stay out of Alice's body topology so stale/virtual
    feeds cannot be treated like owner-visible camera hardware.
    """
    if not name:
        return False
    return bool(_VIRTUAL_CAMERA_RE.search(str(name)))


_USB_LOGITECH_BODY_RE = _re.compile(r"usb\s*camera\s*vid:1133\s*pid:2081", _re.IGNORECASE)
_NOISE_CAMERA_NAME_RE = _re.compile(
    r"^(camera|model\s*id:|uvc\s*camera\s*vendorid_\d+\s*productid_\d+)\s*:?\s*",
    _re.IGNORECASE,
)


def _is_noise_camera_name(name: Optional[str]) -> bool:
    """Drop generic Qt/system_profiler aliases that duplicate real body eyes."""
    if not name:
        return True
    norm = _norm_name(str(name))
    if not norm or norm == "camera":
        return True
    if norm.startswith("model id:"):
        return True
    if "uvc camera vendorid_" in norm and "productid_" in norm:
        return True
    return bool(_NOISE_CAMERA_NAME_RE.match(norm))


def is_allowed_owner_body_camera(name: Optional[str]) -> bool:
    """Strict allowlist: only George's two physical body eyes.

    Owner eye: built-in MacBook / FaceTime camera.
    World eye: ``USB Camera VID:1133 PID:2081`` (Logitech on this node).
    Everything else — OBS, iPhone/Continuity, generic ``Camera:``, duplicate
    ``Model ID:`` rows — stays out of topology and UI combos.
    """
    if not name or _is_noise_camera_name(name):
        return False
    text = str(name).strip()
    if is_builtin_owner_camera(text):
        return True
    return bool(_USB_LOGITECH_BODY_RE.search(_norm_name(text)))


def live_camera_allowed() -> bool:
    """False under pytest or SIFTA_NO_LIVE_CAMERA=1 so automated tests / coding
    arms never open a live camera (never wake the owner's iPhone via Continuity).
    Returns True in normal Talk runtime. Mirrors the PYTEST_CURRENT_TEST guard
    pattern already used in swarm_prompt_contract.py."""
    flag = os.environ.get("SIFTA_NO_LIVE_CAMERA", "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return True


def prefer_builtin_owner_eye(
    device_names: "List[str] | Tuple[str, ...]",
    *,
    allow_iphone: bool = False,
) -> Optional[str]:
    """Pick the safest OWNER eye from live device names.

    Built-in (MacBook/FaceTime) first; then any non-iPhone / non-Continuity
    device; iPhone/Continuity cams only when ``allow_iphone=True`` (George
    explicitly selected one). None if nothing safe is available.
    """
    names = [str(n) for n in (device_names or []) if str(n).strip()]
    if not names:
        return None
    for n in names:
        if is_builtin_owner_camera(n):
            return n
    for n in names:
        if not is_iphone_or_continuity(n):
            return n
    return names[0] if allow_iphone else None


def _target_allows_iphone_or_continuity(target: Dict[str, Any]) -> bool:
    """Only owner-facing selectors may deliberately target Continuity/iPhone.

    Legacy bare-index rows are normalized to names by this module, so the
    writer is the difference between "George selected iPhone" and "an old
    integer happened to map to iPhone after AVFoundation renumbered devices."
    """
    if not is_iphone_or_continuity(target.get("name")):
        return False
    return str(target.get("writer") or "") in _OWNER_IPHONE_ALLOWED_WRITERS


def _norm_name(text: str) -> str:
    return " ".join(str(text).replace("’", "'").strip().lower().split())


def normalize_unique_id(value: Any) -> str:
    """Normalize Qt/AVFoundation camera IDs across bytes and bytes-repr strings."""
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        try:
            return bytes(value).decode("utf-8", errors="replace").strip()
        except Exception:
            return str(value).strip()
    text = str(value).strip()
    if len(text) >= 3 and text[:2] in {"b'", 'b"'} and text[-1:] in {"'", '"'}:
        return text[2:-1].strip()
    return text


def name_for_index(index: Optional[int]) -> Optional[str]:
    if index is None:
        return None
    try:
        idx = int(index)
    except Exception:
        return None
    live = _live_devices()
    if live and 0 <= idx < len(live):
        return live[idx][1]
    frozen = _INDEX_TO_NAME.get(idx)
    if frozen:
        return frozen
    # Legacy bare-integer heal when enumeration is unavailable in headless tests.
    if idx == 1:
        return "MacBook Pro Camera"
    return None


def _legacy_name_for_index(index: int) -> Optional[str]:
    """Interpret old bare-index target rows without live enumeration drift."""
    if index == 1:
        return "MacBook Pro Camera"
    return _INDEX_TO_NAME.get(index)


def index_for_name(name: Optional[str]) -> Optional[int]:
    if not name:
        return None
    live = _live_devices()
    norm = _norm_name(name)
    for i, (_uid, desc) in enumerate(live):
        if desc == name or _norm_name(desc) == norm:
            return i
    if norm in _NAME_TO_INDEX:
        return _NAME_TO_INDEX[norm]
    for key, idx in _NAME_TO_INDEX.items():
        if key in norm or norm in key:
            return idx
    for token in ("usb", "logitech", "external", "webcam", "macbook", "facetime", "built-in"):
        if token in norm:
            for i, (_uid, desc) in enumerate(live):
                desc_norm = _norm_name(desc)
                if token in desc_norm or desc_norm in norm:
                    return i
            if token in ("macbook", "facetime", "built-in") and not live:
                return 1
    return None


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        text = str(value).strip()
        if text.lstrip("-").isdigit():
            return int(text)
    except Exception:
        return None
    return None


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        out = float(value)
        return out if out == out and out not in (float("inf"), float("-inf")) else None
    except Exception:
        return None


def _coerce_priority(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def parse_legacy_text(raw: str, *, writer: str = "legacy_txt") -> Optional[Dict[str, Any]]:
    """Parse old target-file shapes: bare int, bare name, JSON, or key=value."""
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return _normalize(
                    name=data.get("name"),
                    index=data.get("index"),
                    unique_id=data.get("unique_id"),
                    writer=data.get("writer", writer),
                    ts=data.get("ts"),
                    priority=data.get("priority", 0),
                    lease_until=data.get("lease_until"),
                )
        except Exception:
            pass
    if "=" in text:
        key, value = text.split("=", 1)
        if key.strip().lower() in {"active_saccade_target", "camera", "camera_index", "index"}:
            text = value.strip()
    idx = _coerce_int(text)
    if idx is not None:
        legacy_name = _legacy_name_for_index(idx)
        if legacy_name:
            return _normalize(name=legacy_name, index=idx, writer=f"{writer}_int")
        return _normalize(index=idx, writer=f"{writer}_int")
    return _normalize(name=text, writer=f"{writer}_name")


# ── atomic write helper ─────────────────────────────────────────────────
def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def _normalize(
    *,
    name: Optional[str] = None,
    index: Optional[int] = None,
    unique_id: Optional[str] = None,
    writer: str = "unknown",
    ts: Optional[float] = None,
    priority: Any = 0,
    lease_until: Any = None,
) -> Dict[str, Any]:
    idx = _coerce_int(index)
    clean_name = (name or "").strip() or None
    clean_uid = normalize_unique_id(unique_id)

    # Name/unique-id are the stable identity. If a UI writes its combobox
    # position as "index", correct it from the camera name whenever we can.
    mapped_from_name = index_for_name(clean_name)
    if mapped_from_name is not None and not clean_uid:
        idx = mapped_from_name
    elif clean_name is None:
        clean_name = name_for_index(idx)

    return {
        "name": clean_name,
        "index": idx,
        "unique_id": clean_uid or None,
        "ts": float(ts) if ts is not None else time.time(),
        "writer": writer or "unknown",
        "priority": _coerce_priority(priority),
        "lease_until": _coerce_float(lease_until),
    }


def _active_lease_blocks(
    current: Optional[Dict[str, Any]],
    *,
    writer: str,
    priority: int,
    now: float,
) -> bool:
    """Return True when an active higher-priority owner should keep the eye."""
    if not current:
        return False
    lease_until = _coerce_float(current.get("lease_until"))
    if lease_until is None or lease_until <= now:
        return False
    if str(current.get("writer") or "") == str(writer or ""):
        return False
    current_priority = _coerce_priority(current.get("priority"))
    return current_priority > int(priority)


# ── write API ───────────────────────────────────────────────────────────
def write_target(
    *,
    name: Optional[str] = None,
    index: Optional[int] = None,
    unique_id: Optional[str] = None,
    writer: str = "unknown",
    priority: int = 0,
    lease_s: Optional[float] = None,
    respect_lease: bool = True,
) -> Dict[str, Any]:
    """Write the canonical eye target. At least one of name/index/unique_id
    must be provided. Returns the normalized record actually written."""
    if not (name or index is not None or unique_id):
        raise ValueError(
            "write_target requires at least one of name, index, unique_id"
        )
    now = time.time()
    priority_i = _coerce_priority(priority)
    if respect_lease:
        current = read_target()
        if _active_lease_blocks(current, writer=writer, priority=priority_i, now=now):
            return current  # type: ignore[return-value]
    unique_id = normalize_unique_id(unique_id)
    live = _live_devices()
    if unique_id:
        live_idx = _index_for_unique_id(unique_id, live)
        if live_idx >= 0:
            live_uid, live_name = live[live_idx]
            name = live_name or name
            index = live_idx
            unique_id = normalize_unique_id(live_uid) or unique_id
    if name:
        match = _live_device_for_name(str(name), live)
        if match:
            live_idx, live_uid, live_name = match
            name = live_name
            index = live_idx
            unique_id = normalize_unique_id(live_uid) or unique_id
    lease_until = None
    if lease_s is not None:
        try:
            lease_until = now + max(0.0, float(lease_s))
        except Exception:
            lease_until = None
    rec = _normalize(
        name=name,
        index=index,
        unique_id=unique_id,
        writer=writer,
        ts=now,
        priority=priority_i,
        lease_until=lease_until,
    )
    # Order matters: write the legacy .txt mirror FIRST, then the JSON last,
    # so the JSON's mtime is always ≥ the .txt's mtime. Otherwise the
    # "reverse-heal when .txt newer than .json" path in read_target would
    # immediately discard our richer JSON record (unique_id, writer) and
    # replace it with a thinner heal-from-.txt record. (C47H 2026-04-23.)
    if rec["index"] is not None:
        try:
            _atomic_write_text(TARGET_TXT_LEGACY, f"{rec['index']}\n")
        except Exception:
            pass
    _atomic_write_text(TARGET_JSON, json.dumps(rec) + "\n")
    # Belt-and-suspenders: if filesystem timestamp granularity (or a clock
    # quirk) leaves them equal, bump JSON forward by 1ms so reverse-heal
    # cannot accidentally win on a tie.
    try:
        st_json = TARGET_JSON.stat()
        if TARGET_TXT_LEGACY.exists():
            st_txt = TARGET_TXT_LEGACY.stat()
            if st_json.st_mtime <= st_txt.st_mtime:
                os.utime(TARGET_JSON, (st_json.st_atime, st_txt.st_mtime + 0.001))
    except Exception:
        pass
    return rec


# ── read API ────────────────────────────────────────────────────────────
def _heal_legacy_into_json() -> Optional[Dict[str, Any]]:
    """If only the legacy .txt exists, parse it once and rewrite as .json."""
    if not TARGET_TXT_LEGACY.exists():
        return None
    try:
        raw = TARGET_TXT_LEGACY.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    if not raw:
        return None
    rec = parse_legacy_text(raw, writer="legacy_txt")
    if not rec:
        return None
    try:
        _atomic_write_text(TARGET_JSON, json.dumps(rec) + "\n")
    except Exception:
        pass
    return rec


def read_target() -> Optional[Dict[str, Any]]:
    """Return the canonical eye target as a dict, or None if no target set."""
    # During migration, older organs can still write only the .txt mirror. If
    # that happens after JSON exists, trust the newer mtime and heal forward.
    try:
        if TARGET_TXT_LEGACY.exists() and (
            not TARGET_JSON.exists()
            or TARGET_TXT_LEGACY.stat().st_mtime > TARGET_JSON.stat().st_mtime
        ):
            rec = _heal_legacy_into_json()
            if rec:
                return rec
    except Exception:
        pass
    if TARGET_JSON.exists():
        try:
            data = json.loads(TARGET_JSON.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return _normalize(
                    name=data.get("name"),
                    index=data.get("index"),
                    unique_id=data.get("unique_id"),
                    writer=data.get("writer", "unknown"),
                    ts=data.get("ts"),
                    priority=data.get("priority", 0),
                    lease_until=data.get("lease_until"),
                )
        except Exception:
            pass
    return _heal_legacy_into_json()


def _read_target_from_paths(json_path: Path, txt_path: Path) -> Optional[Dict[str, Any]]:
    """Read a target from explicit paths without touching module globals."""
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return _normalize(
                    name=data.get("name"),
                    index=data.get("index"),
                    unique_id=data.get("unique_id"),
                    writer=data.get("writer", "unknown"),
                    ts=data.get("ts"),
                    priority=data.get("priority", 0),
                    lease_until=data.get("lease_until"),
                )
        except Exception:
            pass
    if txt_path.exists():
        try:
            raw = txt_path.read_text(encoding="utf-8").strip()
        except Exception:
            raw = ""
        if raw:
            return parse_legacy_text(raw, writer="legacy_txt")
    return None


# ── resolution helpers ──────────────────────────────────────────────────
def resolve_index(target: Optional[Dict[str, Any]] = None) -> int:
    """Return the integer camera index implied by the current target,
    or -1 if no target is set / nothing in the target maps to an index.

    Use this from organs that index by integer (cv2 VideoCapture, iris).
    Resolution order: unique_id → name → index.
    """
    rec = target if target is not None else read_target()
    if not rec:
        return -1
    live = _live_devices()
    iphone_allowed = _target_allows_iphone_or_continuity(rec)

    # 1) unique_id against live devices (best-effort; never required)
    uid = rec.get("unique_id")
    if uid:
        idx = _index_for_unique_id(uid, live)
        if idx >= 0:
            return idx

    # 2) name against live devices
    nm = rec.get("name")
    if nm:
        if is_iphone_or_continuity(nm) and not iphone_allowed:
            if live:
                return _preferred_live_index(live)
            return -1
        idx = _index_for_name(nm, live)
        if idx >= 0:
            return idx
        # The named device is NOT in the live list.
        if live:
            if _target_requires_exact_live_device(rec):
                return -1
            # We CAN enumerate devices and the named one simply isn't here
            # (e.g. the Logitech was unplugged). Fall back to the built-in
            # instead of pointing at whatever renumbered into its old slot.
            # This is the hot-plug fix: never resolve an absent device to the
            # integer it used to occupy. §7.1 Sensory Lock-On.
            if uid or _looks_like_hardware_camera_name(nm):
                return _preferred_live_index(live)
        # else: no live device info in this context (AVFoundation/Qt missing in
        # a background thread). We cannot tell present from absent, so we fall
        # through to the target's OWN recorded index below rather than guessing
        # from the frozen name→index map. Callers (the capture daemon) re-probe
        # on read failure, which is the backstop for a dead index here.

    if uid and live:
        if _target_requires_exact_live_device(rec):
            return -1
        return _preferred_live_index(live)

    # 3) raw index as last resort — only meaningful when we still have no
    #    name/unique_id signal at all (legacy bare-index targets).
    if rec.get("index") is not None:
        idx = int(rec["index"])
        frozen_name = name_for_index(idx)
        if frozen_name and is_iphone_or_continuity(frozen_name) and not iphone_allowed:
            if live:
                return _preferred_live_index(live)
            return -1
        return idx
    return -1


def _qt_live_devices() -> List[Tuple[str, str]]:
    """Return Qt camera devices when a Qt context is already usable."""
    try:
        from PyQt6.QtCore import QCoreApplication  # type: ignore
        if QCoreApplication.instance() is None:
            return []
        from PyQt6.QtMultimedia import QMediaDevices  # type: ignore
    except Exception:
        return []
    try:
        out: List[Tuple[str, str]] = []
        for d in QMediaDevices.videoInputs():
            did = d.id()
            try:
                did_s = bytes(did).decode() if not isinstance(did, str) else did
            except Exception:
                did_s = did.decode() if isinstance(did, bytes) else str(did)
            out.append((did_s, d.description()))
        return out
    except Exception:
        return []


def _avfoundation_live_devices() -> List[Tuple[str, str]]:
    """Return macOS AVFoundation camera devices without requiring Qt."""
    try:
        import AVFoundation  # type: ignore
    except Exception:
        return []
    try:
        devs = AVFoundation.AVCaptureDevice.devicesWithMediaType_(AVFoundation.AVMediaTypeVideo)
        return [(str(d.uniqueID()), str(d.localizedName())) for d in devs]
    except Exception:
        return []


def _system_profiler_live_devices() -> List[Tuple[str, str]]:
    """Return macOS camera devices from system_profiler without opening cameras.

    Background doctor shells do not always have PyObjC/AVFoundation available.
    `system_profiler SPCameraDataType -json` still reports the hardware
    topology, including stable unique IDs, and does not activate camera LEDs.
    """
    try:
        proc = subprocess.run(
            ["system_profiler", "SPCameraDataType", "-json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    try:
        payload = json.loads(proc.stdout or "{}")
    except Exception:
        return []
    rows = payload.get("SPCameraDataType") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    out: List[Tuple[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("_name") or "").strip()
        if not name:
            continue
        uid = normalize_unique_id(row.get("spcamera_unique-id") or name)
        if is_allowed_owner_body_camera(name):
            out.append((uid, name))
    return out


def _iphone_camera_excluded() -> bool:
    """Architect 2026-06-16: iPhone/Continuity out of body topology until re-enabled."""
    flag = os.environ.get("SIFTA_ALLOW_IPHONE_CAMERA", "").strip().lower()
    return flag not in ("1", "true", "yes", "on")


def _virtual_camera_excluded() -> bool:
    """Virtual/OBS cameras are not body eyes unless explicitly re-enabled."""
    flag = os.environ.get("SIFTA_ALLOW_VIRTUAL_CAMERA", "").strip().lower()
    return flag not in ("1", "true", "yes", "on")


def _filter_body_cameras(devices: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Keep only the two allowed owner body cameras (allowlist, not blocklist)."""
    out: List[Tuple[str, str]] = []
    seen_names: set[str] = set()
    for uid, desc in devices:
        if not is_allowed_owner_body_camera(desc):
            continue
        name_key = _norm_name(desc)
        if name_key in seen_names:
            continue
        seen_names.add(name_key)
        out.append((uid, desc))
    return out


def _live_devices() -> List[Tuple[str, str]]:
    """Return [(unique_id, description), ...] in current live device order.

    Qt wins when it is already available because the visible eye widget uses
    that order. Background cv2 organs fall back to AVFoundation, whose
    uniqueID is stable across USB hot-plug.
    """
    qt = _qt_live_devices()
    raw = qt if qt else (_avfoundation_live_devices() or _system_profiler_live_devices())
    return _filter_body_cameras(raw)


def _index_for_unique_id(uid: str, devices: Optional[List[Tuple[str, str]]] = None) -> int:
    wanted = normalize_unique_id(uid)
    if not wanted:
        return -1
    for i, (did, _desc) in enumerate(devices if devices is not None else _live_devices()):
        if normalize_unique_id(did) == wanted:
            return i
    return -1


def _index_for_name(name: str, devices: Optional[List[Tuple[str, str]]] = None) -> int:
    wanted_alias = index_for_name(name)
    for i, (_did, desc) in enumerate(devices if devices is not None else _live_devices()):
        if desc == name:
            return i
        if wanted_alias is not None and index_for_name(desc) == wanted_alias:
            return i
    return -1


def _live_device_for_name(
    name: Optional[str],
    devices: Optional[List[Tuple[str, str]]] = None,
) -> Optional[Tuple[int, str, str]]:
    """Return the live ``(index, unique_id, description)`` for a target name."""
    if not name:
        return None
    wanted_alias = index_for_name(name)
    for i, (uid, desc) in enumerate(devices if devices is not None else _live_devices()):
        if desc == name:
            return i, normalize_unique_id(uid), desc
        if wanted_alias is not None and index_for_name(desc) == wanted_alias:
            return i, normalize_unique_id(uid), desc
    return None


def _looks_like_hardware_camera_name(name: str) -> bool:
    norm = _norm_name(name)
    markers = (
        "camera", "logitech", "usb", "vid:", "pid:", "macbook", "facetime",
        "iphone", "obs", "desk view",
    )
    return any(m in norm for m in markers)


def _target_requires_exact_live_device(target: Dict[str, Any]) -> bool:
    """True when an owner-facing selector chose a concrete camera.

    Those targets must fail closed if the named/unique hardware is absent.
    Otherwise a stale USB target can silently open the MacBook camera after
    AVFoundation renumbers index 0.
    """
    writer = str(target.get("writer") or "")
    if writer not in _OWNER_LOCKED_CAMERA_WRITERS:
        return False
    name = str(target.get("name") or "")
    return bool(target.get("unique_id") or (name and _looks_like_hardware_camera_name(name)))


def _preferred_live_index(devices: Optional[List[Tuple[str, str]]] = None) -> int:
    """Pick the safest live fallback camera per §7.1: built-in first.

    iPhone / Continuity / Desk View are never automatic fallbacks. They require
    an explicit owner-facing selector; otherwise a hot-plug index drift can wake
    George's phone while doctors are coding.
    """
    live = devices if devices is not None else _live_devices()
    if not live:
        return -1
    built_in = ("macbook pro camera", "facetime", "built-in", "built in")
    avoid = ("obs", "virtual", "desk view")
    for i, (_uid, desc) in enumerate(live):
        norm = _norm_name(desc)
        if any(k in norm for k in built_in) and not is_iphone_or_continuity(desc):
            return i
    for i, (_uid, desc) in enumerate(live):
        norm = _norm_name(desc)
        if not any(k in norm for k in avoid) and not is_iphone_or_continuity(desc):
            return i
    return -1


# ── public identity helpers (stable-uniqueID surface for other organs) ───
def live_devices() -> List[Tuple[str, str]]:
    """Public: [(unique_id, description), ...] in current live device order."""
    return _live_devices()


def preferred_live_index() -> int:
    """Public: safest live fallback index (built-in first), or -1 if none."""
    return _preferred_live_index()


def unique_id_for_name(name: Optional[str]) -> Optional[str]:
    """Return the AVFoundation/Qt uniqueID of the live device matching `name`.

    uniqueID is stable across USB hot-plug, so callers should stamp it onto a
    saccade target to make resolution survive renumbering. Returns None when
    the named device is not currently present (the caller should then treat
    the target as stale rather than re-pinning a dead integer)."""
    if not name:
        return None
    match = _live_device_for_name(name)
    return normalize_unique_id(match[1]) or None if match else None


def refresh_active_target_from_live(
    *,
    state_dir: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Stamp the active target with live uniqueID/current index if available.

    This does not switch cameras. It only heals stale observation fields such
    as ``index`` after USB hotplug. The active target's writer/priority/lease
    are preserved; the live device identity is added so future resolution is
    uniqueID-first.
    """
    if state_dir is None:
        target_json = TARGET_JSON
        target_txt = TARGET_TXT_LEGACY
        rec = read_target()
    else:
        state = Path(state_dir)
        target_json = state / TARGET_JSON.name
        target_txt = state / TARGET_TXT_LEGACY.name
        rec = _read_target_from_paths(target_json, target_txt)
    if not rec or not rec.get("name"):
        return {"changed": False, "reason": "no_active_named_target"}
    live = _live_devices()
    match = _live_device_for_name(str(rec.get("name") or ""), live)
    if not match:
        return {"changed": False, "reason": "active_target_not_live", "target": rec}
    idx, uid, desc = match
    changed = rec.get("index") != idx or (uid and rec.get("unique_id") != uid) or rec.get("name") != desc
    if not changed:
        return {"changed": False, "reason": "target_already_fresh", "target": rec}
    healed = dict(rec)
    healed["name"] = desc
    healed["index"] = idx
    healed["unique_id"] = uid or healed.get("unique_id")
    healed["ts"] = float(now if now is not None else time.time())
    healed["refreshed_by"] = "swarm_camera_target.refresh_active_target_from_live"
    if healed.get("index") is not None:
        try:
            _atomic_write_text(target_txt, f"{int(healed['index'])}\n")
        except Exception:
            pass
    try:
        _atomic_write_text(target_json, json.dumps(healed) + "\n")
    except Exception:
        pass
    return {"changed": True, "target": healed}


def is_device_present(*, name: Optional[str] = None, unique_id: Optional[str] = None) -> bool:
    """True if a device matching `name` or `unique_id` is in the live list.

    When no live device info is available in this context (background thread
    without AVFoundation/Qt), returns True to avoid false negatives — liveness
    gating must never blind an organ that simply cannot enumerate."""
    live = _live_devices()
    if not live:
        return True
    if unique_id:
        wanted_uid = normalize_unique_id(unique_id)
        for uid, _desc in live:
            if normalize_unique_id(uid) == wanted_uid:
                return True
    if name:
        wanted_alias = index_for_name(name)
        for _uid, desc in live:
            if desc == name:
                return True
            if wanted_alias is not None and index_for_name(desc) == wanted_alias:
                return True
    return False


def _device_key(uid: str, desc: str) -> str:
    return normalize_unique_id(uid) or f"name:{_norm_name(desc)}"


def _topology_snapshot(now: Optional[float] = None) -> Dict[str, Any]:
    ts = time.time() if now is None else float(now)
    devices = [
        {"index": i, "unique_id": normalize_unique_id(uid), "name": desc}
        for i, (uid, desc) in enumerate(_live_devices())
    ]
    return {
        "truth_label": "CAMERA_TOPOLOGY_V1",
        "ts": ts,
        "devices": devices,
        "device_count": len(devices),
        "preferred_index": _preferred_live_index([(d["unique_id"], d["name"]) for d in devices]),
    }


def probe_camera_topology(
    *,
    state_dir: Optional[Path] = None,
    now: Optional[float] = None,
    write_receipt: bool = False,
) -> Dict[str, Any]:
    """Return live camera topology and optionally write attach/detach receipts.

    This makes plug/unplug a body event Alice can read, even outside the Qt
    eye widget. Rows use the same `device_events.jsonl` lane the eye widget
    already publishes.
    """
    sd = Path(state_dir) if state_dir is not None else _STATE
    latest_path = sd / TOPOLOGY_JSON.name
    device_log = sd / DEVICE_EVENTS_JSONL.name
    snapshot = _topology_snapshot(now=now)

    previous: Dict[str, Any] = {}
    try:
        previous = json.loads(latest_path.read_text(encoding="utf-8"))
        if not isinstance(previous, dict):
            previous = {}
    except Exception:
        previous = {}

    prev_devices = previous.get("devices") if isinstance(previous.get("devices"), list) else []
    prev_by_key = {
        _device_key(str(d.get("unique_id") or ""), str(d.get("name") or "")): d
        for d in prev_devices
        if isinstance(d, dict)
    }
    new_by_key = {
        _device_key(str(d.get("unique_id") or ""), str(d.get("name") or "")): d
        for d in snapshot["devices"]
        if isinstance(d, dict)
    }
    appeared = [new_by_key[k] for k in sorted(set(new_by_key) - set(prev_by_key))]
    vanished = [prev_by_key[k] for k in sorted(set(prev_by_key) - set(new_by_key))]

    snapshot["appeared"] = appeared
    snapshot["vanished"] = vanished
    snapshot["changed"] = bool(appeared or vanished)

    if write_receipt:
        sd.mkdir(parents=True, exist_ok=True)
        try:
            snapshot["active_target_refresh"] = refresh_active_target_from_live(
                state_dir=sd,
                now=snapshot["ts"],
            )
        except Exception as exc:
            snapshot["active_target_refresh"] = {"changed": False, "error": type(exc).__name__}
        try:
            _atomic_write_text(latest_path, json.dumps(snapshot, sort_keys=True) + "\n")
        except Exception:
            pass
        if appeared or vanished:
            try:
                with device_log.open("a", encoding="utf-8") as handle:
                    for kind, rows in (("attached", appeared), ("detached", vanished)):
                        for dev in rows:
                            name = str(dev.get("name") or "unknown camera")
                            handle.write(json.dumps({
                                "ts": snapshot["ts"],
                                "kind": kind,
                                "camera_name": name,
                                "camera_index": dev.get("index"),
                                "unique_id": dev.get("unique_id"),
                                "is_logitech": "logitech" in name.casefold() or "1133" in name,
                                "summary": f"{name} camera {kind}",
                                "source": "swarm_camera_target.probe_camera_topology",
                                "truth_label": "CAMERA_TOPOLOGY_V1",
                            }, sort_keys=True) + "\n")
            except Exception:
                pass
        try:
            from System.swarm_eye_registry import refresh_eye_registry

            refresh_eye_registry(
                state_dir=sd,
                devices=snapshot.get("devices") if isinstance(snapshot.get("devices"), list) else [],
                now=snapshot["ts"],
                write_receipt=True,
            )
        except Exception:
            pass

    return snapshot


# ── prompt-line helper for Alice ────────────────────────────────────────
def prompt_line() -> str:
    """One-line summary for `alice_body_autopilot.read_prompt_line()`.

    Example:
      "current eye: MacBook Pro Camera (idx 1, writer=swarm_oculomotor_saccades)"
    """
    rec = read_target()
    if not rec:
        return "current eye: (no saccade target set; iris uses auto-discovery)"
    name = rec.get("name") or "(unnamed)"
    idx = rec.get("index")
    writer = rec.get("writer") or "unknown"
    idx_str = f"idx {idx}" if idx is not None else "idx ?"
    resolved = resolve_index(rec)
    if resolved < 0 and name != "(unnamed)":
        return (
            f"current eye target: {name} (not live/unresolved, recorded {idx_str}, "
            f"writer={writer})"
        )
    if resolved >= 0 and idx is not None and int(idx) != int(resolved):
        return (
            f"current eye: {name} (resolved idx {resolved}, recorded {idx}, "
            f"writer={writer})"
        )
    return f"current eye: {name} ({idx_str}, writer={writer})"


# ── module self-test ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("[swarm_camera_target] live devices:")
    for i, (uid, desc) in enumerate(_live_devices()):
        print(f"  {i}  {desc}  [uid={uid}]")
    print()
    print("[swarm_camera_target] current target:")
    rec = read_target()
    print(f"  {rec}")
    print(f"  resolved index = {resolve_index(rec)}")
    print(f"  prompt_line    = {prompt_line()!r}")
