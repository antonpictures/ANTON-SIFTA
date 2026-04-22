#!/usr/bin/env python3
"""
System/swarm_merkle_attestor.py
══════════════════════════════════════════════════════════════════════
Concept: Live Cryptoorganism Memory Attestation (Merkle Anchors)
Author:  C53M (OpenAI) for Architect tournament lane
Status:  Active (additive lobe)

Purpose:
  Seal a tamper-evident cryptographic root over critical .sifta_state ledgers
  without mutating those ledgers. Each anchor row forms a hash-chained timeline.

Why this is novel here:
  - Existing guards protect swimmer BODY files and schema shape.
  - This lobe protects *the memory field itself* (conversation, engrams, immune
    incidents, stigmergic traces) with append-only Merkle anchors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from System.canonical_schemas import assert_payload_keys
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    raise SystemExit(1)


_STATE_DIR = Path(".sifta_state")
_ANCHOR_LEDGER = _STATE_DIR / "memory_merkle_anchors.jsonl"
_LATEST_MANIFEST = _STATE_DIR / "memory_merkle_latest.json"
_LEDGER_NAME = "memory_merkle_anchors.jsonl"

# Keep this set compact and high-value: identity, safety, learning, discourse.
_DEFAULT_TARGETS = (
    "alice_conversation.jsonl",
    "ide_stigmergic_trace.jsonl",
    "long_term_engrams.jsonl",
    "stigmergic_nuggets.jsonl",
    "global_immune_system.jsonl",
    "swimmer_body_integrity_incidents.jsonl",
    "mycorrhizal_rejections.jsonl",
)


@dataclass
class AnchorResult:
    anchor_id: str
    root_hash: str
    file_count: int
    line_count: int
    manifest_sha256: str
    parent_anchor: str


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _merkle_parent(a_hex: str, b_hex: str) -> str:
    return _sha256_bytes(bytes.fromhex(a_hex) + bytes.fromhex(b_hex))


def _merkle_root(leaves: List[str]) -> str:
    if not leaves:
        return _sha256_text("EMPTY_MERKLE_TREE")
    level = list(leaves)
    while len(level) > 1:
        nxt: List[str] = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else left
            nxt.append(_merkle_parent(left, right))
        level = nxt
    return level[0]


def _normalized_nonempty_lines(path: Path) -> Tuple[List[str], int]:
    text = read_text_locked(path)
    lines = [ln.rstrip("\n") for ln in text.splitlines() if ln.strip()]
    return lines, len(lines)


def _manifest_for_targets(state_dir: Path, targets: Tuple[str, ...]) -> Tuple[Dict[str, Dict[str, str]], int]:
    manifest: Dict[str, Dict[str, str]] = {}
    total_lines = 0
    for name in targets:
        p = state_dir / name
        if not p.exists():
            continue
        lines, n = _normalized_nonempty_lines(p)
        total_lines += n
        line_hashes = [_sha256_text(ln) for ln in lines]
        file_root = _merkle_root(line_hashes)
        manifest[name] = {
            "line_count": str(n),
            "file_root": file_root,
            "bytes": str(p.stat().st_size),
        }
    return manifest, total_lines


def _load_last_anchor_id(anchor_ledger: Path) -> str:
    if not anchor_ledger.exists():
        return ""
    text = read_text_locked(anchor_ledger).strip()
    if not text:
        return ""
    last = text.splitlines()[-1]
    try:
        payload = json.loads(last)
    except Exception:
        return ""
    return str(payload.get("anchor_id", ""))


def create_anchor(
    state_dir: Path = _STATE_DIR,
    *,
    targets: Tuple[str, ...] = _DEFAULT_TARGETS,
    write_manifest: bool = True,
) -> AnchorResult:
    state_dir.mkdir(parents=True, exist_ok=True)
    anchor_ledger = state_dir / _ANCHOR_LEDGER.name
    latest_manifest_path = state_dir / _LATEST_MANIFEST.name

    manifest, total_lines = _manifest_for_targets(state_dir, targets)
    sorted_items = sorted(manifest.items(), key=lambda kv: kv[0])
    leaf_hashes = [_sha256_text(f"{k}:{v['file_root']}:{v['line_count']}:{v['bytes']}") for k, v in sorted_items]
    root_hash = _merkle_root(leaf_hashes)

    manifest_blob = json.dumps(
        {
            "ts": time.time(),
            "targets": list(targets),
            "files": manifest,
            "root_hash": root_hash,
        },
        indent=2,
        sort_keys=True,
    ) + "\n"
    manifest_sha = _sha256_text(manifest_blob)

    parent = _load_last_anchor_id(anchor_ledger)
    anchor_id = f"MERKLE_{_sha256_text(f'{time.time()}|{root_hash}|{parent}')[:12]}"
    payload = {
        "ts": time.time(),
        "anchor_id": anchor_id,
        "root_hash": root_hash,
        "file_count": len(manifest),
        "line_count": total_lines,
        "manifest_sha256": manifest_sha,
        "parent_anchor": parent,
    }
    assert_payload_keys(_LEDGER_NAME, payload, strict=True)
    append_line_locked(anchor_ledger, json.dumps(payload, ensure_ascii=False) + "\n")

    if write_manifest:
        latest_manifest_path.write_text(manifest_blob, encoding="utf-8")

    return AnchorResult(
        anchor_id=anchor_id,
        root_hash=root_hash,
        file_count=len(manifest),
        line_count=total_lines,
        manifest_sha256=manifest_sha,
        parent_anchor=parent,
    )


def verify_latest_against_manifest(state_dir: Path = _STATE_DIR) -> Tuple[bool, str]:
    latest_manifest_path = state_dir / _LATEST_MANIFEST.name
    if not latest_manifest_path.exists():
        return False, "no_latest_manifest"

    try:
        baseline = json.loads(latest_manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return False, "manifest_parse_error"

    targets = tuple(baseline.get("targets") or [])
    if not targets:
        return False, "manifest_has_no_targets"

    current_manifest, _ = _manifest_for_targets(state_dir, targets)
    baseline_files = baseline.get("files") or {}
    if current_manifest != baseline_files:
        return False, "drift_detected"

    sorted_items = sorted(current_manifest.items(), key=lambda kv: kv[0])
    leaf_hashes = [_sha256_text(f"{k}:{v['file_root']}:{v['line_count']}:{v['bytes']}") for k, v in sorted_items]
    current_root = _merkle_root(leaf_hashes)
    if current_root != baseline.get("root_hash"):
        return False, "root_mismatch"
    return True, "verified"


def _smoke() -> int:
    print("\n=== SIFTA MERKLE ATTESTOR : SMOKE TEST ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        state = Path(tmpdir)
        target_a = state / "alice_conversation.jsonl"
        target_b = state / "ide_stigmergic_trace.jsonl"
        target_a.write_text('{"x":1}\n{"x":2}\n', encoding="utf-8")
        target_b.write_text('{"trace":"ok"}\n', encoding="utf-8")

        targets = ("alice_conversation.jsonl", "ide_stigmergic_trace.jsonl")
        first = create_anchor(state, targets=targets, write_manifest=True)
        ok, reason = verify_latest_against_manifest(state)
        assert ok, f"expected verified after first anchor, got {reason}"

        # Tamper the live substrate and ensure drift is detected.
        target_a.write_text('{"x":1}\n{"x":999}\n', encoding="utf-8")
        ok2, reason2 = verify_latest_against_manifest(state)
        assert not ok2 and reason2 in {"drift_detected", "root_mismatch"}, reason2

        second = create_anchor(state, targets=targets, write_manifest=True)
        assert first.root_hash != second.root_hash, "tamper should alter Merkle root"
        assert second.parent_anchor == first.anchor_id, "anchor chain parent mismatch"

        print("[PASS] Baseline anchor created and verified.")
        print("[PASS] Tamper drift detected against latest manifest.")
        print("[PASS] Re-anchor after drift produces new root + chained parent.")
        print("\nMerkle Attestor Smoke Complete. Memory field is tamper-evident.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="SIFTA Merkle memory attestor")
    parser.add_argument("--anchor", action="store_true", help="create one new Merkle anchor")
    parser.add_argument("--verify", action="store_true", help="verify live state against latest manifest")
    parser.add_argument("--smoke", action="store_true", help="run offline smoke")
    args = parser.parse_args()

    if args.smoke:
        return _smoke()

    if args.anchor:
        result = create_anchor()
        print(
            f"[+] MERKLE ANCHORED {result.anchor_id} "
            f"root={result.root_hash[:16]} files={result.file_count} lines={result.line_count}"
        )
        return 0

    if args.verify:
        ok, reason = verify_latest_against_manifest()
        if ok:
            print("[+] MERKLE VERIFY PASS: latest manifest matches live substrate.")
            return 0
        print(f"[-] MERKLE VERIFY FAIL: {reason}")
        return 1

    # Default action: anchor now.
    result = create_anchor()
    print(
        f"[+] MERKLE ANCHORED {result.anchor_id} "
        f"root={result.root_hash[:16]} files={result.file_count} lines={result.line_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
