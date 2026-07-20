#!/usr/bin/env python3
"""macOS privacy/cache surface scanner for Alice's local body.

The scanner is intentionally metadata-only. It records cache/service names,
top-level stat data, known Apple service meaning, and owner-control locations.
It does not read private cache payload contents.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import time
import uuid
from pathlib import Path
from typing import Any

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - standalone fallback
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(line)


_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE_DIR = _REPO / ".sifta_state"
LEDGER_NAME = "macos_privacy_cache_scan.jsonl"


APPLE_CACHE_SURFACES: dict[str, dict[str, Any]] = {
    "cloudkit": {
        "service": "CloudKit / iCloud sync",
        "plain_meaning": "Local cache/stub for Apple's iCloud app-data sync framework.",
        "possible_data": ["iCloud account metadata", "app sync metadata", "local sync cache pointers"],
        "owner_controls": ["System Settings > Apple Account > iCloud"],
    },
    "familycircle": {
        "service": "Family Sharing",
        "plain_meaning": "Local cache/stub for Apple family group services.",
        "possible_data": ["Family Sharing account metadata", "family-member service state"],
        "owner_controls": ["System Settings > Family", "System Settings > Apple Account > Family Sharing"],
    },
    "familycircled": {
        "service": "Family Sharing daemon",
        "plain_meaning": "Daemon cache/stub for Apple family group services.",
        "possible_data": ["Family Sharing account metadata", "family-member service state"],
        "owner_controls": ["System Settings > Family", "System Settings > Apple Account > Family Sharing"],
    },
    "com.apple.homekit": {
        "service": "HomeKit",
        "plain_meaning": "Local cache/stub for Apple Home/HomeKit accessory state.",
        "possible_data": ["home/accessory metadata", "automation state", "home membership metadata"],
        "owner_controls": ["Home app", "System Settings > Privacy & Security > HomeKit"],
    },
    "com.apple.homed": {
        "service": "HomeKit daemon",
        "plain_meaning": "Daemon cache/stub for Apple Home/HomeKit accessory state.",
        "possible_data": ["home/accessory metadata", "automation state", "home membership metadata"],
        "owner_controls": ["Home app", "System Settings > Privacy & Security > HomeKit"],
    },
    "com.apple.safari": {
        "service": "Safari",
        "plain_meaning": "Safari browser cache/stub.",
        "possible_data": ["browser cache metadata", "site resources", "Safari local service state"],
        "owner_controls": ["Safari > Settings > Privacy", "Safari > Clear History"],
    },
    "com.apple.safari.safebrowsing": {
        "service": "Safari Safe Browsing",
        "plain_meaning": "Local Safe Browsing threat-list/service cache used by Safari.",
        "possible_data": ["safe-browsing threat-list cache", "security service state"],
        "owner_controls": ["Safari > Settings > Security", "Safari > Settings > Privacy"],
    },
    "com.apple.findmy.imagecache": {
        "service": "Find My",
        "plain_meaning": "Local image/cache stub for Apple's Find My service.",
        "possible_data": ["Find My image/cache metadata", "device/person presentation cache"],
        "owner_controls": ["System Settings > Apple Account > Find My", "Find My app"],
    },
    "com.apple.findmy.fmfcore": {
        "service": "Find My Friends core",
        "plain_meaning": "Local cache/stub for Find My people/location-sharing services.",
        "possible_data": ["location-sharing service metadata", "Find My people state"],
        "owner_controls": ["System Settings > Apple Account > Find My", "Find My app"],
    },
    "com.apple.findmy.fmipcore": {
        "service": "Find My iPhone/Mac core",
        "plain_meaning": "Local cache/stub for Find My device services.",
        "possible_data": ["device-location service metadata", "Find My device state"],
        "owner_controls": ["System Settings > Apple Account > Find My", "Find My app"],
    },
    "com.apple.containermanagerd": {
        "service": "App sandbox container manager",
        "plain_meaning": "macOS service cache/stub for application containers.",
        "possible_data": ["container metadata", "sandbox bookkeeping"],
        "owner_controls": ["System Settings > Privacy & Security", "Finder app container storage"],
    },
    "com.apple.ap.adprivacyd": {
        "service": "Apple advertising privacy daemon",
        "plain_meaning": "Local cache/stub for Apple's ad privacy/attribution service.",
        "possible_data": ["ad privacy service metadata", "attribution/privacy daemon state"],
        "owner_controls": ["System Settings > Privacy & Security > Apple Advertising"],
    },
    "geoservices": {
        "service": "Apple GeoServices",
        "plain_meaning": "Local cache/stub for Apple's maps/location/geography service.",
        "possible_data": ["maps/geography service metadata", "location-service cache state"],
        "owner_controls": ["System Settings > Privacy & Security > Location Services"],
    },
    "ssu": {
        "service": "Apple system software update/service cache",
        "plain_meaning": "Small Apple system-service cache/stub; exact daemon ownership is macOS-managed.",
        "possible_data": ["system service metadata"],
        "owner_controls": ["System Settings > General > Software Update"],
    },
}

APPLE_GENERIC_PREFIXES = ("com.apple.",)


def _generic_apple_surface(name: str) -> dict[str, Any] | None:
    key = name.casefold()
    if not key.startswith(APPLE_GENERIC_PREFIXES):
        return None
    if "siri" in key or "assistant" in key:
        service = "Apple Siri/Assistant service"
        controls = ["System Settings > Apple Intelligence & Siri", "System Settings > Privacy & Security > Microphone"]
        possible = ["Siri/Assistant service metadata", "local assistant cache state"]
    elif "nsurlsessiond" in key:
        service = "Apple URLSession network daemon"
        controls = ["System Settings > Privacy & Security", "Network settings"]
        possible = ["Apple network transfer daemon cache", "download/session metadata"]
    elif "parsecd" in key:
        service = "Apple search/suggestions daemon"
        controls = ["System Settings > Spotlight", "System Settings > Privacy & Security"]
        possible = ["search/suggestions service metadata", "local suggestion cache state"]
    elif "duet" in key:
        service = "Apple intelligence/activity prediction daemon"
        controls = ["System Settings > Privacy & Security"]
        possible = ["local activity prediction metadata", "device intelligence cache state"]
    elif "e5rt" in key:
        service = "Apple on-device ML/runtime cache"
        controls = ["System Settings > Apple Intelligence & Siri", "System Settings > Privacy & Security"]
        possible = ["on-device ML runtime cache", "model/runtime bundle metadata"]
    else:
        service = "Apple macOS service cache"
        controls = ["System Settings > Privacy & Security"]
        possible = ["macOS service metadata", "local cache state"]
    return {
        "service": service,
        "plain_meaning": "Built-in Apple service cache/stub inferred from the com.apple bundle prefix.",
        "possible_data": possible,
        "owner_controls": controls,
    }


def _now() -> float:
    return time.time()


def _mode_string(mode: int | None) -> str | None:
    if mode is None:
        return None
    return stat.filemode(mode)


def _iso_from_epoch(ts: float | None) -> str | None:
    if ts is None:
        return None
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(float(ts)))
    except Exception:
        return None


def _stat_entry(path: Path) -> dict[str, Any]:
    try:
        st = path.stat()
        return {
            "exists": True,
            "mode": _mode_string(st.st_mode),
            "uid": st.st_uid,
            "gid": st.st_gid,
            "mtime": st.st_mtime,
            "mtime_local": _iso_from_epoch(st.st_mtime),
            "top_level_size_bytes": st.st_size,
        }
    except PermissionError as exc:
        return {"exists": True, "stat_error": f"PermissionError:{exc}"}
    except FileNotFoundError:
        return {"exists": False}
    except OSError as exc:
        return {"exists": path.exists(), "stat_error": f"{type(exc).__name__}:{exc}"}


def _bounded_metadata_size(path: Path, *, max_entries: int = 20000) -> tuple[int | None, str | None, int]:
    """Return recursive byte total from metadata only.

    The function reads directory entries and file stat data, not file contents.
    It stops after max_entries to avoid turning a cache audit into a heavy crawl.
    """
    total = 0
    visited = 0
    errors: list[str] = []

    if not path.exists():
        return None, "missing", visited
    if path.is_file():
        try:
            return path.stat().st_size, None, 1
        except OSError as exc:
            return None, f"{type(exc).__name__}:{exc}", visited

    for root, dirs, files in os.walk(path, topdown=True, onerror=lambda e: errors.append(f"{type(e).__name__}:{e}")):
        visited += 1
        if visited > max_entries:
            return total, "truncated:max_entries", visited
        for name in list(files):
            visited += 1
            if visited > max_entries:
                return total, "truncated:max_entries", visited
            fp = Path(root) / name
            try:
                total += fp.stat().st_size
            except OSError as exc:
                errors.append(f"{type(exc).__name__}:{fp.name}:{exc}")
        # Keep the crawl bounded even for huge caches.
        if visited + len(dirs) > max_entries:
            del dirs[:]
    return total, ";".join(errors[:3]) if errors else None, visited


def _classify_cache_entry(path: Path, *, cache_root: Path) -> dict[str, Any]:
    name = path.name
    key = name.casefold()
    stat_info = _stat_entry(path)
    known = APPLE_CACHE_SURFACES.get(key) or _generic_apple_surface(name)

    if name == "SIFTA OS":
        relation = "SIFTA_CACHE"
        recommendation = "KEEP"
        helps_sifta = True
        service_info = {
            "service": "SIFTA OS",
            "plain_meaning": "Alice/SIFTA local cache bucket.",
            "possible_data": ["SIFTA runtime cache"],
            "owner_controls": ["SIFTA OS"],
        }
        size_bytes, size_error, visited = _bounded_metadata_size(path)
    elif known:
        relation = "APPLE_OS_SERVICE_CACHE"
        recommendation = "OS_MANAGED_CHECK_SETTINGS"
        helps_sifta = False
        service_info = known
        # Privacy posture: do not descend into Apple service caches by default.
        size_bytes = stat_info.get("top_level_size_bytes")
        size_error = None
        visited = 1
    else:
        relation = "NON_SIFTA_CACHE"
        recommendation = "DELETE_CANDIDATE_IF_OWNER_DOES_NOT_USE_APP"
        helps_sifta = False
        service_info = {
            "service": "Unknown/non-SIFTA cache",
            "plain_meaning": "Not recognized as SIFTA or a known protected Apple service cache.",
            "possible_data": ["app cache/state"],
            "owner_controls": ["Remove the app or delete cache after app is closed"],
        }
        size_bytes, size_error, visited = _bounded_metadata_size(path)

    protected_hint = bool(known) and str(stat_info.get("mode") or "").startswith("d")
    return {
        "path": str(path),
        "name": name,
        "cache_root": str(cache_root),
        "relation_to_sifta": relation,
        "helps_sifta_now": helps_sifta,
        "recommendation": recommendation,
        "service": service_info["service"],
        "plain_meaning": service_info["plain_meaning"],
        "possible_data_categories": service_info["possible_data"],
        "owner_control_surfaces": service_info["owner_controls"],
        "evidence_level": "OBSERVED_NAME_STAT_METADATA_ONLY",
        "content_read": False,
        "size_bytes": size_bytes,
        "size_error": size_error,
        "metadata_entries_seen": visited,
        "macos_protected_likely": protected_hint,
        "stat": stat_info,
    }


def scan_macos_privacy_cache_surfaces(
    *,
    cache_root: str | Path | None = None,
    state_dir: str | Path | None = None,
    write_receipt: bool = True,
) -> dict[str, Any]:
    """Scan local macOS cache surfaces and optionally append a JSONL receipt."""
    root = Path(cache_root).expanduser() if cache_root is not None else Path.home() / "Library" / "Caches"
    state = Path(state_dir).expanduser() if state_dir is not None else _DEFAULT_STATE_DIR
    entries: list[dict[str, Any]] = []
    errors: list[str] = []

    try:
        children = sorted(root.iterdir(), key=lambda p: p.name.casefold())
    except PermissionError as exc:
        children = []
        errors.append(f"cache_root_permission_error:{exc}")
    except FileNotFoundError:
        children = []
        errors.append("cache_root_missing")

    for child in children:
        entries.append(_classify_cache_entry(child, cache_root=root))

    readable_total = sum(int(e.get("size_bytes") or 0) for e in entries)
    receipt = {
        "trace_id": f"MACOS_PRIVACY_CACHE_{uuid.uuid4().hex[:12]}",
        "ts": _now(),
        "truth_label": "OBSERVED",
        "scanner": "System.swarm_macos_privacy_cache_scanner",
        "cache_root": str(root),
        "privacy_mode": "metadata_only_no_payload_contents",
        "entry_count": len(entries),
        "readable_total_bytes": readable_total,
        "sifta_entries": sum(1 for e in entries if e["relation_to_sifta"] == "SIFTA_CACHE"),
        "apple_service_entries": sum(1 for e in entries if e["relation_to_sifta"] == "APPLE_OS_SERVICE_CACHE"),
        "delete_candidate_entries": sum(1 for e in entries if e["relation_to_sifta"] == "NON_SIFTA_CACHE"),
        "errors": errors,
        "entries": entries,
    }

    if write_receipt:
        ledger = state / LEDGER_NAME
        append_line_locked(ledger, json.dumps(receipt, sort_keys=True) + "\n")
        receipt["ledger_path"] = str(ledger)
    return receipt


def summarize_for_owner(scan: dict[str, Any]) -> str:
    """Return a compact grounded summary for the Talk surface or CLI."""
    entries = scan.get("entries") or []
    apple = [e for e in entries if e.get("relation_to_sifta") == "APPLE_OS_SERVICE_CACHE"]
    sifta = [e for e in entries if e.get("relation_to_sifta") == "SIFTA_CACHE"]
    candidates = [e for e in entries if e.get("relation_to_sifta") == "NON_SIFTA_CACHE"]
    lines = [
        f"Scan: {scan.get('entry_count', 0)} cache surfaces; mode={scan.get('privacy_mode')}.",
        f"SIFTA cache: {len(sifta)}. Apple service stubs: {len(apple)}. Non-SIFTA delete candidates: {len(candidates)}.",
    ]
    if sifta:
        lines.append("Keep: " + ", ".join(e["name"] for e in sifta))
    if apple:
        names = ", ".join(e["name"] for e in apple[:12])
        suffix = "" if len(apple) <= 12 else f" +{len(apple) - 12} more"
        lines.append(f"Apple protected/service surfaces: {names}{suffix}.")
    if candidates:
        lines.append("Delete candidates: " + ", ".join(e["name"] for e in candidates[:12]))
    ledger = scan.get("ledger_path")
    if ledger:
        lines.append(f"Receipt: {ledger}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", default=None, help="cache root to scan; default ~/Library/Caches")
    parser.add_argument("--state-dir", default=None, help="state dir for JSONL receipt")
    parser.add_argument("--no-receipt", action="store_true", help="scan only; do not append JSONL")
    parser.add_argument("--summary", action="store_true", help="print compact owner summary instead of JSON")
    args = parser.parse_args(argv)

    scan = scan_macos_privacy_cache_surfaces(
        cache_root=args.cache_root,
        state_dir=args.state_dir,
        write_receipt=not args.no_receipt,
    )
    if args.summary:
        print(summarize_for_owner(scan))
    else:
        print(json.dumps(scan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
