#!/usr/bin/env python3
"""
System/swarm_castle_publisher.py
══════════════════════════════════════════════════════════════════════
The Castle Publisher (Event 46).

AG31 implementation of the public extension layer.
Strictly gated by:
1. PII Scrubbing (acid-blood guard using distro_scrubber.HARD_PII_TOKENS).
2. Idempotency (skips if manifest_sha256 matches last publish for transport).
3. CastleHomeostasis (aborts if the mound is degraded).
4. CLI Explicit opt-in (--allow-publish flag).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from System.swarm_extended_phenotype import (
    MODULE_VERSION as PHENOTYPE_VERSION,
    CASTLE_ROOT,
    BOLUS_LEDGER,
    CastleBuilder,
    CastleHomeostasis,
    emit_bolus,
    load_boluses,
    Bolus,
    BolusManifest
)

MODULE_VERSION = "2026-04-23.castle_publisher.v1"


def get_hard_pii_tokens() -> List[str]:
    repo_root = Path(__file__).resolve().parent.parent
    scrubber_path = repo_root / "scripts" / "distro_scrubber.py"

    if scrubber_path.exists():
        try:
            spec = importlib.util.spec_from_file_location("distro_scrubber", scrubber_path)
            distro_scrubber = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(distro_scrubber)
            return getattr(distro_scrubber, "HARD_PII_TOKENS", [])
        except Exception as e:
            print(f"[CastlePublisher] WARNING: Could not load distro_scrubber: {e}")
    return ["<YOUR_USERNAME>", "<YOUR_EMAIL>", "<YOUR_NAME>", "<YOUR_SILICON_SERIAL>", "<YOUR_M1_SERIAL>"]


HARD_PII_TOKENS = get_hard_pii_tokens()


class CastleTransport:
    """Base interface for deterministic Castle publishing transports."""
    def __init__(self, name: str) -> None:
        self.name = name

    def push(self, castle_dir: Path) -> Tuple[bool, int, str]:
        """
        Returns (success: bool, bytes_transferred: int, remote_id: str).
        """
        raise NotImplementedError


class DryRunTransport(CastleTransport):
    def __init__(self, original_transport_name: str = "dry_run") -> None:
        super().__init__(f"dry_run_for_{original_transport_name}")

    def push(self, castle_dir: Path) -> Tuple[bool, int, str]:
        print(f"[DryRunTransport] WOULD publish {castle_dir} to {self.name}")
        return True, 0, self.name


class LocalMirrorTransport(CastleTransport):
    def __init__(self, target_dir: Path) -> None:
        super().__init__("local_mirror")
        self.target_dir = Path(target_dir)

    def push(self, castle_dir: Path) -> Tuple[bool, int, str]:
        try:
            if self.target_dir.exists():
                shutil.rmtree(self.target_dir)
            shutil.copytree(castle_dir, self.target_dir)
            size = sum(f.stat().st_size for f in self.target_dir.rglob('*') if f.is_file())
            print(f"[LocalMirrorTransport] Successfully mirrored to {self.target_dir}")
            return True, size, str(self.target_dir)
        except Exception as e:
            print(f"[LocalMirrorTransport] Error: {e}")
            return False, 0, str(self.target_dir)


class GitHubTransport(CastleTransport):
    def __init__(self, remote: str, branch: str = "main", subtree: str = "castle") -> None:
        super().__init__("github")
        self.remote = remote
        self.branch = branch
        self.subtree = subtree

    def push(self, castle_dir: Path) -> Tuple[bool, int, str]:
        try:
            cwd = str(castle_dir)
            if not (castle_dir / ".git").exists():
                subprocess.run(["git", "init"], cwd=cwd, check=True, capture_output=True)
                subprocess.run(["git", "remote", "add", "origin", self.remote], cwd=cwd, check=True, capture_output=True)
                subprocess.run(["git", "branch", "-M", self.branch], cwd=cwd, check=True, capture_output=True)
            
            subprocess.run(["git", "add", "."], cwd=cwd, check=True, capture_output=True)
            
            st = subprocess.run(["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True)
            if not st.stdout.strip():
                return True, 0, self.remote
                
            subprocess.run(["git", "commit", "-m", "Castle update"], cwd=cwd, check=True, capture_output=True)
            subprocess.run(["git", "push", "-u", "origin", self.branch], cwd=cwd, check=True, capture_output=True)
            
            size = sum(f.stat().st_size for f in castle_dir.rglob('*') if f.is_file() and not '.git' in f.parts)
            print(f"[GitHubTransport] Pushed to {self.remote} branch {self.branch}")
            return True, size, self.remote
        except subprocess.CalledProcessError as e:
            print(f"[GitHubTransport] Error: {e.stderr.decode('utf-8') if e.stderr else str(e)}")
            return False, 0, self.remote


class CastlePublisher:
    def __init__(self, builder: CastleBuilder, transports: Sequence[CastleTransport]):
        self.builder = builder
        self.transports = transports

    def _check_pii(self, castle_dir: Path) -> bool:
        """Returns True if PII was found (unsafe)."""
        for f in castle_dir.rglob('*'):
            if f.is_file() and '.git' not in f.parts:
                try:
                    content = f.read_text(encoding="utf-8")
                    for token in HARD_PII_TOKENS:
                        if token in content:
                            print(f"[CastlePublisher] ACID-BLOOD GUARD TRIPPED: Found PII token '{token}' in {f}")
                            return True
                except UnicodeDecodeError:
                    pass
        return False

    def _get_last_published_manifest_sha(self, transport_name: str) -> Optional[str]:
        """Reads the bolus ledger to find the last successful distro push for this transport."""
        boluses = load_boluses(ledger_path=self.builder.ledger_path)
        last_sha = None
        for b in boluses:
            if b.kind == "distro" and b.payload.get("transport") == transport_name:
                last_sha = b.payload.get("manifest_sha256")
        return last_sha

    def publish(self, allow_publish: bool = False, now: Optional[float] = None) -> Dict[str, Any]:
        t = float(time.time() if now is None else now)
        manifest, health = self.builder.build(now=t)

        if not health.ok:
            print("[CastlePublisher] Homeostasis check FAILED. Aborting publish.")
            for issue in health.issues:
                print(f"  - {issue}")
            return {"status": "error", "reason": "homeostasis_failed"}

        self.builder.publish_local(now=t)

        if self._check_pii(self.builder.castle_root):
            return {"status": "error", "reason": "pii_detected"}

        reports = {}

        actual_transports = self.transports
        if not allow_publish:
            print("[CastlePublisher] --allow-publish not set. Falling back to DryRunTransport.")
            actual_transports = [DryRunTransport(t.name) for t in self.transports]

        for transport in actual_transports:
            transport_key = transport.name.replace("dry_run_for_", "") if transport.name.startswith("dry_run_for_") else transport.name
            
            last_sha = self._get_last_published_manifest_sha(transport_key)
            if last_sha == health.manifest_sha256:
                print(f"[CastlePublisher] Idempotent skip: Manifest unchanged for transport {transport_key}.")
                reports[transport.name] = {"status": "skipped", "reason": "unchanged"}
                continue

            success, size, remote_id = transport.push(self.builder.castle_root)
            reports[transport.name] = {
                "status": "success" if success else "failed",
                "bytes": size,
                "remote": remote_id
            }

            if success and not transport.name.startswith("dry_run"):
                distro_bolus = Bolus(
                    kind="distro",
                    ref_sha256=health.manifest_sha256,
                    ref_path=f"distro_push_{transport_key}",
                    source_homeworld="AG31_Publisher",
                    deposited_ts=t,
                    payload={
                        "transport": transport_key,
                        "merkle_root": manifest.merkle_root(),
                        "remote": remote_id,
                        "manifest_sha256": health.manifest_sha256
                    }
                )
                emit_bolus(distro_bolus, ledger_path=self.builder.ledger_path, ts=t)
                print(f"[CastlePublisher] Emitted kind=distro bolus for {transport_key} into {self.builder.ledger_path}")

        return reports


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="SIFTA Castle Publisher (Event 46)")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    pub_cmd = subparsers.add_parser("publish", help="Publish the local Castle to configured transports")
    pub_cmd.add_argument("--allow-publish", action="store_true", help="Opt-in to actual publishing. Without this, falls back to dry-run.")
    pub_cmd.add_argument("--transport", action="append", help="Transports to use (github, local)")
    pub_cmd.add_argument("--remote", type=str, default="origin", help="Remote for GitHubTransport")
    pub_cmd.add_argument("--local-dir", type=str, default="/tmp/sifta_castle_mirror", help="Target dir for LocalMirrorTransport")

    args = parser.parse_args(argv)

    if args.cmd == "publish":
        transports = []
        if args.transport:
            for t in args.transport:
                if t == "github":
                    transports.append(GitHubTransport(remote=args.remote))
                elif t == "local":
                    transports.append(LocalMirrorTransport(target_dir=Path(args.local_dir)))
                else:
                    print(f"Unknown transport: {t}")
        else:
            print("No --transport specified. Please specify --transport github or --transport local.")
            return 1

        builder = CastleBuilder()
        publisher = CastlePublisher(builder, transports)
        reports = publisher.publish(allow_publish=args.allow_publish)
        print(json.dumps(reports, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
