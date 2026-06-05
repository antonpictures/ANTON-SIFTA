#!/usr/bin/env python3
"""Audit local Ollama model tags, shared blobs, and orphaned blobs.

This tool is deliberately read-only. It answers a practical installer question:
which model names are duplicate tags over the same physical weight file, and
which files are unreferenced store residue from failed pulls or rebuilds?
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MODEL_MEDIA_TYPE = "application/vnd.ollama.image.model"


@dataclass(frozen=True)
class BlobReference:
    tag: str
    media_type: str
    size: int


@dataclass
class OllamaInventory:
    root: Path
    model_tags: dict[str, dict[str, Any]] = field(default_factory=dict)
    blob_refs: dict[str, list[BlobReference]] = field(default_factory=dict)
    blob_sizes: dict[str, int] = field(default_factory=dict)

    @property
    def shared_model_blobs(self) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = {}
        for tag, info in self.model_tags.items():
            digest = info.get("model_blob")
            if digest:
                groups.setdefault(digest, []).append(tag)
        return {digest: sorted(tags) for digest, tags in groups.items() if len(tags) > 1}

    @property
    def orphaned_blobs(self) -> dict[str, int]:
        return {
            blob: size
            for blob, size in self.blob_sizes.items()
            if blob not in self.blob_refs
        }


def _blob_name(digest: str) -> str:
    if digest.startswith("sha256:"):
        return digest.replace(":", "-", 1)
    return digest


def _tag_name(manifest_path: Path, manifests_root: Path) -> str:
    rel = manifest_path.relative_to(manifests_root)
    parts = rel.parts
    if len(parts) >= 4 and parts[0] == "registry.ollama.ai":
        namespace = parts[1]
        name = parts[2]
        tag = parts[3]
        return f"{name}:{tag}" if namespace == "library" else f"{namespace}/{name}:{tag}"
    if len(parts) >= 2:
        return f"{parts[-2]}:{parts[-1]}"
    return str(rel)


def scan_inventory(root: Path | None = None) -> OllamaInventory:
    """Return a read-only inventory for an Ollama models directory."""

    root = root or Path.home() / ".ollama" / "models"
    inv = OllamaInventory(root=root)
    manifests_root = root / "manifests"
    blobs_root = root / "blobs"

    if blobs_root.exists():
        for blob in blobs_root.glob("sha256-*"):
            if blob.is_file():
                inv.blob_sizes[blob.name] = blob.stat().st_size

    if not manifests_root.exists():
        return inv

    for manifest in sorted(p for p in manifests_root.rglob("*") if p.is_file()):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            continue

        tag = _tag_name(manifest, manifests_root)
        model_blob = None
        model_size = 0
        for layer in data.get("layers", []):
            digest = _blob_name(str(layer.get("digest", "")))
            if not digest.startswith("sha256-"):
                continue
            size = int(layer.get("size") or 0)
            media_type = str(layer.get("mediaType", ""))
            inv.blob_refs.setdefault(digest, []).append(
                BlobReference(tag=tag, media_type=media_type, size=size)
            )
            if media_type == MODEL_MEDIA_TYPE:
                model_blob = digest
                model_size = size

        config = data.get("config") or {}
        digest = _blob_name(str(config.get("digest", "")))
        if digest.startswith("sha256-"):
            inv.blob_refs.setdefault(digest, []).append(
                BlobReference(
                    tag=tag,
                    media_type=str(config.get("mediaType", "")),
                    size=int(config.get("size") or 0),
                )
            )

        inv.model_tags[tag] = {
            "manifest": str(manifest),
            "model_blob": model_blob,
            "model_size": model_size,
        }

    return inv


def _gb(size: int) -> str:
    return f"{size / (1024 ** 3):.2f} GB"


def render_report(inv: OllamaInventory) -> str:
    lines: list[str] = []
    lines.append(f"Ollama store: {inv.root}")
    lines.append("")
    lines.append("Model tags:")
    for tag, info in sorted(inv.model_tags.items()):
        size = int(info.get("model_size") or 0)
        blob = info.get("model_blob") or "NO_MODEL_BLOB"
        lines.append(f"  {tag:32} {_gb(size):>8}  {blob}")

    lines.append("")
    lines.append("Shared model blobs:")
    shared = inv.shared_model_blobs
    if not shared:
        lines.append("  none")
    else:
        for blob, tags in sorted(shared.items()):
            size = inv.blob_sizes.get(blob) or 0
            lines.append(f"  {_gb(size):>8}  {blob}")
            for tag in tags:
                lines.append(f"            - {tag}")

    lines.append("")
    lines.append("Unreferenced blobs:")
    orphans = inv.orphaned_blobs
    if not orphans:
        lines.append("  none")
    else:
        for blob, size in sorted(orphans.items(), key=lambda item: item[1], reverse=True):
            lines.append(f"  {_gb(size):>8}  {blob}")

    return "\n".join(lines)


def delete_orphaned_blobs(inv: OllamaInventory) -> list[dict[str, Any]]:
    """Delete only blobs that no manifest references.

    The caller must explicitly request this path. Shared model blobs and any blob
    with a manifest reference are never deleted by this function.
    """

    deleted: list[dict[str, Any]] = []
    for blob, size in sorted(inv.orphaned_blobs.items(), key=lambda item: item[1], reverse=True):
        path = inv.root / "blobs" / blob
        if not path.exists() or not path.is_file():
            continue
        path.unlink()
        deleted.append({"blob": blob, "size": size, "path": str(path)})
    return deleted


def append_cleanup_receipt(receipt_path: Path, inv: OllamaInventory, deleted: list[dict[str, Any]]) -> None:
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "event": "ollama_orphan_blob_cleanup",
        "root": str(inv.root),
        "deleted_count": len(deleted),
        "deleted_bytes": sum(int(item["size"]) for item in deleted),
        "deleted": deleted,
        "truth_label": "OBSERVED_LOCAL_FILESYSTEM_DELETE",
    }
    with receipt_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.home() / ".ollama" / "models")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--delete-orphans",
        action="store_true",
        help="Delete unreferenced blobs after scanning. Requires --yes.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required with --delete-orphans so accidental deletes fail closed.",
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path(".sifta_state/ollama_cleanup_receipts.jsonl"),
        help="Append a JSONL cleanup receipt when deleting orphaned blobs.",
    )
    args = parser.parse_args()

    inv = scan_inventory(args.root)
    if args.delete_orphans:
        if not args.yes:
            parser.error("--delete-orphans requires --yes")
        deleted = delete_orphaned_blobs(inv)
        append_cleanup_receipt(args.receipt, inv, deleted)
        if args.json:
            print(
                json.dumps(
                    {
                        "root": str(inv.root),
                        "deleted": deleted,
                        "deleted_count": len(deleted),
                        "deleted_bytes": sum(int(item["size"]) for item in deleted),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(render_report(inv))
            print("")
            print(
                f"Deleted {len(deleted)} orphaned blobs "
                f"({sum(int(item['size']) for item in deleted) / (1024 ** 3):.2f} GB)."
            )
        return 0

    if args.json:
        print(
            json.dumps(
                {
                    "root": str(inv.root),
                    "model_tags": inv.model_tags,
                    "shared_model_blobs": inv.shared_model_blobs,
                    "orphaned_blobs": inv.orphaned_blobs,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(render_report(inv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
