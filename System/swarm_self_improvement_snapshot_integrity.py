"""Snapshot restore integrity — corrupt copy must refuse restore (r1021 C11)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_snapshot_integrity(snapshot_path: Path, *, expected_sha256: str | None = None) -> Dict[str, Any]:
    if not snapshot_path.exists():
        return {"ok": False, "reason": "missing_snapshot"}
    try:
        data = snapshot_path.read_bytes()
    except OSError as exc:
        return {"ok": False, "reason": f"read_failed:{exc}"}
    if not data.strip():
        return {"ok": False, "reason": "empty_snapshot"}
    sha = hashlib.sha256(data).hexdigest()
    if expected_sha256 and sha != expected_sha256:
        return {"ok": False, "reason": "sha_mismatch", "sha256": sha}
    return {"ok": True, "sha256": sha, "bytes": len(data)}


def restore_from_snapshot_if_valid(
    snapshot_path: Path,
    target_path: Path,
    *,
    expected_sha256: str | None = None,
) -> Dict[str, Any]:
    check = verify_snapshot_integrity(snapshot_path, expected_sha256=expected_sha256)
    if not check.get("ok"):
        return {"ok": False, "restored": False, "integrity": check}
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(snapshot_path.read_bytes())
    return {"ok": True, "restored": True, "integrity": check}