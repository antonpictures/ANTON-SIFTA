#!/usr/bin/env python3
"""Duplicate-organ audit gate for SIFTA.

The canonical organ registry tells Alice where organs live. This audit catches
the failure mode that created a second owner-recognition organ before checking
the existing AG46 face-recognition organ first.

The audit is intentionally conservative:
  - exact duplicate manifest entry points are blockers for active apps;
  - duplicate truth-label definitions are reported as warnings;
  - owner face identity has a hard canonical lane and any second organ must
    delegate to ``System.swarm_architect_face_recognition`` instead of defining
    a new face embedding pipeline.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


TRUTH_LABEL = "DUPLICATE_ORGAN_AUDIT_V1"

_SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".distro_build",
    ".sifta_state",
    ".venv",
    "Archive",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}

_TRUTH_LABEL_RE = re.compile(
    r"""
    (?:
        (?:^|\n)\s*(?:TRUTH_LABEL|_TRUTH_LABEL)\s*=\s*["'](?P<const>[^"']+)["']
      | truth_label["']?\s*[:=]\s*["'](?P<kv>[^"']+)["']
      | Truth\s+label:\s*``(?P<doc>[^`]+)``
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_OWNER_FACE_CANONICAL = Path("System/swarm_architect_face_recognition.py")
_OWNER_FACE_ALLOWED_WRAPPERS = {
    Path("System/swarm_sovereign_recognition_organ.py"),
}
_OWNER_FACE_DELEGATION_NEEDLES = (
    "swarm_architect_face_recognition",
    "_EMBEDDING",
    "_extract_face_patch",
)
_OWNER_FACE_PIPELINE_NEEDLES = (
    "architect_face_embedding.npy",
    "haarcascade_frontalface",
    "cosine similarity",
    "_extract_face_patch",
    "_load_owner_embedding",
)


@dataclass(frozen=True)
class Finding:
    severity: str
    kind: str
    message: str
    paths: tuple[str, ...]
    lane: str = ""


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _iter_files(root: Path, suffixes: tuple[str, ...]) -> Iterable[Path]:
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in _SKIP_DIRS]
        base = Path(dirpath)
        for filename in filenames:
            path = base / filename
            if path.suffix in suffixes:
                yield path


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _load_manifest(root: Path) -> dict[str, Any]:
    path = root / "Applications" / "apps_manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _active_manifest_items(manifest: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    for name, meta in manifest.items():
        if not isinstance(meta, dict):
            continue
        if meta.get("_retired") is True or meta.get("enabled") is False:
            continue
        yield str(name), meta


def _audit_manifest(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    manifest = _load_manifest(root)
    by_entry: dict[str, list[str]] = defaultdict(list)
    by_widget: dict[tuple[str, str], list[str]] = defaultdict(list)

    for app_name, meta in _active_manifest_items(manifest):
        entry = str(meta.get("entry_point") or "").strip()
        widget = str(meta.get("widget_class") or "").strip()
        if entry:
            by_entry[entry].append(app_name)
        if entry and widget:
            by_widget[(entry, widget)].append(app_name)

    for entry, names in sorted(by_entry.items()):
        if len(names) > 1:
            findings.append(
                Finding(
                    severity="error",
                    kind="duplicate_manifest_entry_point",
                    message=(
                        "Active apps share one entry_point. If this is one organ, "
                        "merge the manifest names; if it is multiple organs, split "
                        "the implementation and receipts."
                    ),
                    paths=(f"Applications/apps_manifest.json:{entry}",),
                    lane=", ".join(names),
                )
            )

    for (entry, widget), names in sorted(by_widget.items()):
        if len(names) > 1:
            findings.append(
                Finding(
                    severity="warning",
                    kind="duplicate_manifest_widget",
                    message="Active apps share the same entry_point + widget_class.",
                    paths=(f"Applications/apps_manifest.json:{entry}::{widget}",),
                    lane=", ".join(names),
                )
            )
    return findings


def _truth_labels_in(text: str) -> set[str]:
    labels: set[str] = set()
    for match in _TRUTH_LABEL_RE.finditer(text):
        for key in ("const", "kv", "doc"):
            value = match.groupdict().get(key)
            if value:
                labels.add(value.strip())
    return labels


def _audit_truth_labels(root: Path) -> list[Finding]:
    by_label: dict[str, set[str]] = defaultdict(set)
    for source_dir in ("System", "Applications", "Kernel"):
        base = root / source_dir
        if not base.exists():
            continue
        for path in _iter_files(base, (".py",)):
            rel = _rel(root, path)
            for label in _truth_labels_in(_read_text(path)):
                by_label[label].add(rel)

    findings: list[Finding] = []
    for label, paths in sorted(by_label.items()):
        if len(paths) > 1:
            findings.append(
                Finding(
                    severity="warning",
                    kind="duplicate_truth_label",
                    message=(
                        "One truth label appears in multiple source files. This may be "
                        "shared schema code, but organ-specific labels should usually "
                        "have a single owner."
                    ),
                    paths=tuple(sorted(paths)),
                    lane=label,
                )
            )
    return findings


def _delegates_to_owner_face_canonical(text: str) -> bool:
    return all(needle in text for needle in _OWNER_FACE_DELEGATION_NEEDLES)


def _looks_like_owner_face_pipeline(text: str) -> bool:
    hits = sum(1 for needle in _OWNER_FACE_PIPELINE_NEEDLES if needle in text)
    return hits >= 2


def _audit_owner_face_identity(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    canonical = root / _OWNER_FACE_CANONICAL
    if not canonical.exists():
        findings.append(
            Finding(
                severity="error",
                kind="missing_canonical_owner_face_organ",
                message="Canonical owner face identity organ is missing.",
                paths=(_OWNER_FACE_CANONICAL.as_posix(),),
                lane="owner_face_identity",
            )
        )
        return findings

    for path in _iter_files(root / "System", (".py",)) if (root / "System").exists() else ():
        rel_path = Path(_rel(root, path))
        if rel_path == _OWNER_FACE_CANONICAL:
            continue
        if rel_path == Path("System/swarm_duplicate_organ_audit.py"):
            continue
        text = _read_text(path)
        name = rel_path.name.lower()
        in_identity_name = ("face" in name and "recognition" in name) or "sovereign_recognition" in name
        if not in_identity_name and not _looks_like_owner_face_pipeline(text):
            continue

        if rel_path in _OWNER_FACE_ALLOWED_WRAPPERS and _delegates_to_owner_face_canonical(text):
            continue

        if _delegates_to_owner_face_canonical(text):
            findings.append(
                Finding(
                    severity="warning",
                    kind="owner_face_wrapper_not_allowlisted",
                    message=(
                        "Owner-face code delegates to the canonical organ but is not "
                        "listed as an allowed wrapper. Add it deliberately or merge it."
                    ),
                    paths=(rel_path.as_posix(), _OWNER_FACE_CANONICAL.as_posix()),
                    lane="owner_face_identity",
                )
            )
        else:
            findings.append(
                Finding(
                    severity="error",
                    kind="owner_face_identity_duplicate",
                    message=(
                        "Owner-face identity has exactly one canonical organ. New code "
                        "must call System.swarm_architect_face_recognition instead of "
                        "training/loading a second owner embedding."
                    ),
                    paths=(rel_path.as_posix(), _OWNER_FACE_CANONICAL.as_posix()),
                    lane="owner_face_identity",
                )
            )
    return findings


def audit_repo(root: Path | str | None = None) -> dict[str, Any]:
    root_path = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    root_path = root_path.resolve()
    findings = [
        *_audit_manifest(root_path),
        *_audit_truth_labels(root_path),
        *_audit_owner_face_identity(root_path),
    ]
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    return {
        "ok": not errors,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "audit_id": f"duporgan-{uuid.uuid4().hex[:12]}",
        "root": str(root_path),
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "findings": len(findings),
        },
        "canonical_owner_face_identity": _OWNER_FACE_CANONICAL.as_posix(),
        "observer_term": (
            "reflexive self-model loop / second-order observer; ganglia names "
            "the organ cluster, not the observer-observed relation itself"
        ),
        "findings": [asdict(f) for f in findings],
    }


def write_audit_receipt(result: dict[str, Any], state_dir: Path | str | None = None) -> Path:
    root = Path(result.get("root") or Path(__file__).resolve().parents[1])
    state = Path(state_dir) if state_dir is not None else root / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    path = state / "duplicate_organ_audit.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit duplicate SIFTA organs")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--write", action="store_true", help="append receipt to .sifta_state/duplicate_organ_audit.jsonl")
    parser.add_argument("--strict-warnings", action="store_true", help="treat warnings as non-zero")
    args = parser.parse_args(argv)

    result = audit_repo(args.root)
    if args.write:
        result["receipt_path"] = str(write_audit_receipt(result))
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    if not result["ok"]:
        return 2
    if args.strict_warnings and result["summary"]["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
