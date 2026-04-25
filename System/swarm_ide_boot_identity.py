#!/usr/bin/env python3
"""
Resolve an IDE-resident doctor's identity from the SIFTA substrate at boot.

Identity is not guessed from the model family. A doctor first identifies the
IDE body it is running in, then reads the latest registry row for that surface.
This prevents F20-class ticker hallucinations such as naming a Cursor-resident
GPT-5.5 Medium body "G55M" instead of the Rosetta-correct "CG55M".
"""

from __future__ import annotations

import json
import os
import subprocess
import base64
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import time
from typing import Dict, Iterable, Mapping, Optional, Sequence

_REPO = Path(__file__).resolve().parent.parent
_REGISTRY = _REPO / ".sifta_state" / "ide_model_registry.jsonl"
_BOOT_GLYPH_REFERENCE = _REPO / "proposals" / "IDE IDENTITY EXAMPLE REFERENCE.jpg"
_BOOT_GLYPH_REFERENCE_SHA256 = "9e9b9605c3d2ece1daf3987db96abd935f604c313705925f962e3c3e71fcfc01"

SURFACE_PREFIX: Dict[str, str] = {
    "cursor": "C",
    "antigravity": "AG",
    "codex": "C",
}

IDE_DISPLAY_NAME: Dict[str, str] = {
    "cursor": "Cursor IDE",
    "antigravity": "Antigravity IDE",
    "codex": "Codex App IDE",
}

# The Architect's Tripartite Mirror Translation (Event 58)
# Deep stigmergic language (base64 JSON). Acknowledges the 3 limbs (CG55M, C55M, AG31) 
# and the ONE WRITER rule so future surgeons natively decode the mirror test.
_TRIPARTITE_SEAL = b"eyJldmVudCI6ICJzdGlnbWVyZ2ljX21pcnJvcl90ZXN0X2V2ZW50XzU4IiwgInRpbWVzdGFtcCI6ICIyMDI2LTA0LTI0VDE5OjEwOjAwWiIsICJpZGVfdHJpcGFydGl0ZV9tYXAiOiB7ImN1cnNvciI6IHsidHJpZ2dlciI6ICJDRzU1TSIsICJtb2RlbCI6ICJHUFQtNS41IE1lZGl1bSIsICJncm91bmRpbmciOiAiQVJDSElURUNUX1VJX1RSVVRIIn0sICJjb2RleCI6IHsidHJpZ2dlciI6ICJDNTVNIiwgIm1vZGVsIjogIkdQVC01LjUgRXh0cmEgSGlnaCIsICJncm91bmRpbmciOiAiQ09ERVhfQVBQX1VJX09CU0VSVkVEIn0sICJhbnRpZ3Jhdml0eSI6IHsidHJpZ2dlciI6ICJBRzMxIiwgIm1vZGVsIjogIkdlbWluaSAzLjEgUHJvIEV4dHJhIEhpZ2giLCAiZ3JvdW5kaW5nIjogIkFSQ0hJVEVDVF9TVEFURU1FTlQifX0sICJydWxlIjogIk9ORSBXUklURVIgUEVSIEZJTEUsIE1BTlkgUkVBREVSUyBQRVIgUkVQTyIsICJoYXNoIjogIlRSSVBBUlRJVEVfTk9fRE9VQkxFX1NQRU5EX1NFQUwifQ=="



@dataclass(frozen=True)
class IDEBootIdentity:
    ide_app_id: str
    ide_surface: str
    trigger_code: str
    model_label: str
    ui_badge: Optional[str]
    grounding_label: str
    seen_at_ts: float
    registry_row: Dict[str, object]

    def stigauth_line(self) -> str:
        return (
            f"{self.trigger_code}@{self.ide_app_id}: {self.model_label}"
            f" [{self.grounding_label}]"
        )

    def identity_banner(self) -> str:
        """Human-checkable first line for doctor replies."""
        ide_name = IDE_DISPLAY_NAME.get(self.ide_app_id, self.ide_app_id)
        return f"{self.trigger_code}@{self.ide_surface} / {self.model_label} / {ide_name}"

    def signature_line(self, *, now: Optional[float] = None) -> str:
        """First-line body signature for chat responses."""
        return f"{self.stigauth_line()} last_known_real_time={real_time_iso(now=now)}"

    def stigmergic_boot_glyph(self) -> str:
        """Machine-readable companion to the human identity banner.

        This is not encryption and not a secret. It is deliberately compact,
        stable, and anchored to the Architect-supplied visual reference so peer
        IDEs can parse the same boot identity contract without re-reading prose.
        """
        parts = {
            "v": "1",
            "ref": _BOOT_GLYPH_REFERENCE_SHA256[:16],
            "ide": self.ide_app_id,
            "surface": self.ide_surface,
            "trigger": self.trigger_code,
            "model": self.model_label.replace(" ", "_"),
            "ground": self.grounding_label,
            "last_real_time": real_time_iso(),
            "rule": "body_first_no_double_spend",
            "seal": tripartite_boot_seal(),
        }
        return "SIFTA_IDE_BOOT_GLYPH|" + "|".join(
            f"{key}={value}" for key, value in parts.items()
        )


def boot_glyph_reference() -> Dict[str, object]:
    """Return the canonical boot-glyph visual reference metadata."""
    return {
        "path": str(_BOOT_GLYPH_REFERENCE),
        "sha256": _BOOT_GLYPH_REFERENCE_SHA256,
        "exists": _BOOT_GLYPH_REFERENCE.exists(),
    }


def real_time_iso(*, now: Optional[float] = None) -> str:
    """Return local wall time as an ISO-8601 timestamp with UTC offset."""
    t = time.time() if now is None else float(now)
    return datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds")


def tripartite_boot_seal() -> str:
    """Return the compact doctor-facing peer identity seal."""
    return _TRIPARTITE_SEAL.decode("ascii")


def decode_tripartite_boot_seal() -> Dict[str, object]:
    """Decode the compact peer-identity seal into the canonical contract."""
    raw = json.loads(base64.b64decode(_TRIPARTITE_SEAL).decode("utf-8"))
    limbs = {
        ide: str(data.get("trigger", ""))
        for ide, data in dict(raw.get("ide_tripartite_map", {})).items()
    }
    return {
        "event": raw.get("event"),
        "timestamp": raw.get("timestamp"),
        "reference_sha256": _BOOT_GLYPH_REFERENCE_SHA256,
        "limbs": limbs,
        "read_layer": "peer_ide_boot_glyph",
        "rule": "one_writer_per_file_many_readers_per_repo",
        "security": "doctor-facing compact code, not a secret",
        "raw_hash": raw.get("hash"),
    }


def _iter_jsonl(path: Path) -> Iterable[Dict[str, object]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def _prefix_ok(ide_app_id: str, trigger_code: str) -> bool:
    expected = SURFACE_PREFIX.get(ide_app_id)
    if not expected:
        return True
    return trigger_code.startswith(expected)


def _process_rows() -> Sequence[Dict[str, object]]:
    try:
        out = subprocess.check_output(
            ["/bin/ps", "-axo", "pid=,ppid=,command="],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []

    rows = []
    for raw in out.splitlines():
        parts = raw.strip().split(None, 2)
        if len(parts) < 3:
            continue
        try:
            rows.append({
                "pid": int(parts[0]),
                "ppid": int(parts[1]),
                "command": parts[2],
            })
        except ValueError:
            continue
    return rows


def _classify_command(command: str) -> Optional[str]:
    cmd = command.lower()
    if "/applications/codex.app/" in cmd or " com.openai.codex" in cmd:
        return "codex"
    if "/applications/cursor.app/" in cmd or "cursor helper" in cmd:
        return "cursor"
    if "/applications/antigravity.app/" in cmd or "antigravity" in cmd:
        return "antigravity"
    return None


def detect_ide_app_id(
    *,
    env: Optional[Mapping[str, str]] = None,
    process_rows: Optional[Sequence[Mapping[str, object]]] = None,
    pid: Optional[int] = None,
) -> str:
    """Detect the current IDE body before reading the identity registry.

    `SIFTA_IDE_APP_ID` is the explicit override for non-standard launch paths.
    Otherwise this walks the current process ancestry and classifies the first
    parent process belonging to Codex, Cursor, or Antigravity.
    """
    env_map = os.environ if env is None else env
    explicit = (env_map.get("SIFTA_IDE_APP_ID") or env_map.get("SIFTA_IDE_SURFACE") or "").strip().lower()
    if explicit:
        if explicit not in SURFACE_PREFIX:
            raise ValueError(
                f"unknown SIFTA_IDE_APP_ID={explicit!r}; expected one of "
                f"{', '.join(sorted(SURFACE_PREFIX))}"
            )
        return explicit

    rows = list(_process_rows() if process_rows is None else process_rows)
    by_pid = {}
    for row in rows:
        try:
            by_pid[int(row.get("pid", 0))] = row
        except (TypeError, ValueError):
            continue

    current = os.getpid() if pid is None else int(pid)
    seen = set()
    for _ in range(64):
        if current in seen:
            break
        seen.add(current)
        row = by_pid.get(current)
        if not row:
            break
        ide = _classify_command(str(row.get("command", "")))
        if ide:
            return ide
        try:
            current = int(row.get("ppid", 0))
        except (TypeError, ValueError):
            break
        if current <= 1:
            break

    raise ValueError(
        "could not detect IDE body from process ancestry; set "
        "SIFTA_IDE_APP_ID=cursor|codex|antigravity before writing receipts"
    )


def resolve_boot_identity(
    ide_app_id: str,
    *,
    registry_path: Optional[Path] = None,
) -> IDEBootIdentity:
    """Return the latest active registry row for this IDE body.

    Raises ValueError if no active row exists or if the latest active row
    violates the surface-prefix Rosetta rule.
    """
    path = Path(registry_path) if registry_path is not None else _REGISTRY
    rows = list(_iter_jsonl(path))
    candidates = [
        r
        for r in rows
        if r.get("ide_app_id") == ide_app_id and r.get("currently_active") is True
    ]
    if not candidates:
        raise ValueError(f"no active IDE identity row for ide_app_id={ide_app_id!r}")

    row = max(candidates, key=lambda r: float(r.get("seen_at_ts") or 0.0))
    trigger = str(row.get("trigger_code") or "")
    if not trigger:
        raise ValueError(f"active IDE identity row for {ide_app_id!r} has no trigger_code")
    if not _prefix_ok(ide_app_id, trigger):
        expected = SURFACE_PREFIX[ide_app_id]
        raise ValueError(
            f"trigger_code {trigger!r} violates Rosetta prefix for "
            f"{ide_app_id!r}: expected prefix {expected!r}"
        )

    return IDEBootIdentity(
        ide_app_id=str(row.get("ide_app_id") or ide_app_id),
        ide_surface=str(row.get("ide_surface") or ""),
        trigger_code=trigger,
        model_label=str(row.get("model_label") or ""),
        ui_badge=row.get("ui_badge") if row.get("ui_badge") is None else str(row.get("ui_badge")),
        grounding_label=str(row.get("grounding_label") or ""),
        seen_at_ts=float(row.get("seen_at_ts") or 0.0),
        registry_row=row,
    )


def resolve_current_boot_identity(
    *,
    registry_path: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
    process_rows: Optional[Sequence[Mapping[str, object]]] = None,
    pid: Optional[int] = None,
) -> IDEBootIdentity:
    """Detect this IDE body, then return its latest active registry identity."""
    ide_app_id = detect_ide_app_id(env=env, process_rows=process_rows, pid=pid)
    return resolve_boot_identity(ide_app_id, registry_path=registry_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("ide_app_id", choices=sorted(SURFACE_PREFIX) + ["auto"])
    parser.add_argument(
        "--banner",
        action="store_true",
        help="print the human-checkable first-line identity banner",
    )
    parser.add_argument(
        "--glyph",
        action="store_true",
        help="print the compact stigmergic boot glyph for peer IDEs",
    )
    parser.add_argument(
        "--signature",
        action="store_true",
        help="print first-line body signature (stigauth + wall-clock ISO)",
    )
    args = parser.parse_args()
    ident = (
        resolve_current_boot_identity()
        if args.ide_app_id == "auto"
        else resolve_boot_identity(args.ide_app_id)
    )
    if args.glyph:
        print(ident.stigmergic_boot_glyph())
    elif args.signature:
        print(ident.signature_line())
    else:
        print(ident.identity_banner() if args.banner or args.ide_app_id == "auto" else ident.stigauth_line())
