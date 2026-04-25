#!/usr/bin/env python3
"""
System/swarm_publish_daemon.py
══════════════════════════════════════════════════════════════════════
The Castle Builder Publish Daemon (Event 46 — The Extended Phenotype).

AG31 cut the structural transport layer (Github / S3 / IPFS / Mock).
C47H welded four acid-blood safety guards on top, all from the
original commission contract:

  1. dry_run by default — must pass --allow-publish to actually push.
  2. PII scrubber audit reuse — refuses if any HARD_PII_TOKEN appears
     anywhere under the castle_root before push.
  3. Idempotency — skips a transport whose last-success receipt already
     records the current manifest_sha256.
  4. Stigmergic closure — successful real push emits a kind=`distro`
     bolus back into the BOLUS_LEDGER so the act of publishing is
     itself a mud bolus other agents observe (this is what makes
     Event 46 actually stigmergic and not a one-shot tarball).

Status field semantics (string, single value per receipt row):
  SUCCESS            — real push completed
  DRY_RUN            — would have pushed; --allow-publish absent
  SKIPPED_UNCHANGED  — identical manifest_sha256 already shipped
  BLOCKED_PII        — HARD_PII_TOKEN matched under castle_root; refused
  FAILURE            — transport raised; receipt records failure
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except ImportError:  # pragma: no cover
    from jsonl_file_lock import append_line_locked, read_text_locked

try:
    from System.canonical_schemas import assert_payload_keys
except ImportError:  # pragma: no cover
    def assert_payload_keys(_ledger_name: str, _payload: dict, *, strict: bool = True) -> None:
        return None

from System.swarm_extended_phenotype import (
    BOLUS_LEDGER,
    CASTLE_ROOT,
    Bolus,
    CastleBuilder,
    _sha256_json,
    _sha256_text,
    emit_bolus,
)

MODULE_VERSION = "2026-04-23.publish_daemon.v2"
PUBLISH_RECEIPTS_LEDGER = CASTLE_ROOT.parent / "extended_phenotype_publish_receipts.jsonl"

STATUS_SUCCESS = "SUCCESS"
STATUS_DRY_RUN = "DRY_RUN"
STATUS_SKIPPED_UNCHANGED = "SKIPPED_UNCHANGED"
STATUS_BLOCKED_PII = "BLOCKED_PII"
STATUS_FAILURE = "FAILURE"
STATUS_HOMEOSTASIS_ABORT = "HOMEOSTASIS_ABORT"
STATUS_PREFLIGHT_FAILED = "PREFLIGHT_FAILED"


# ─────────────────────────────────────────────────────────────────────────
# Transports (AG31's original cut, preserved unchanged)
# ─────────────────────────────────────────────────────────────────────────

class CastleTransport:
    """Base interface for deterministic Castle publishing transports."""
    def __init__(self, uri: str) -> None:
        self.uri = uri
        parsed = urllib.parse.urlparse(uri)
        self.scheme = parsed.scheme
        self.netloc = parsed.netloc
        self.path = parsed.path

    def push(self, castle_dir: Path) -> Tuple[bool, int]:
        raise NotImplementedError

    def dry_check(self) -> Tuple[bool, str]:
        """
        Side-effect-free reachability check run before any real publish.
        Returns (ok, reason). Subclasses should avoid mutating local state.
        """
        return bool(self.scheme and self.netloc), "uri_parse_ok"


class GithubTransport(CastleTransport):
    def _target(self) -> str:
        if self.path.endswith(".git"):
            return f"git@github.com:{self.netloc}{self.path}"
        return f"git@github.com:{self.netloc}{self.path}.git"

    def dry_check(self) -> Tuple[bool, str]:
        if not self.netloc or not self.path.strip("/"):
            return False, "invalid_github_uri"
        if shutil.which("git") is None:
            return False, "git_missing"
        target = self._target()
        try:
            subprocess.run(
                ["git", "ls-remote", "--heads", target],
                check=True,
                capture_output=True,
                timeout=10,
            )
            return True, "github_reachable"
        except subprocess.TimeoutExpired:
            return False, "github_preflight_timeout"
        except subprocess.CalledProcessError:
            return False, "github_unreachable_or_auth_failed"

    def push(self, castle_dir: Path) -> Tuple[bool, int]:
        try:
            cwd = str(castle_dir)
            if not (castle_dir / ".git").exists():
                subprocess.run(["git", "init"], cwd=cwd, check=True, capture_output=True)
                subprocess.run(["git", "remote", "add", "origin", self._target()], cwd=cwd, check=True, capture_output=True)
                subprocess.run(["git", "branch", "-M", "main"], cwd=cwd, check=True, capture_output=True)

            subprocess.run(["git", "add", "."], cwd=cwd, check=True, capture_output=True)

            st = subprocess.run(["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True)
            if not st.stdout.strip():
                return True, 0

            subprocess.run(["git", "commit", "-m", "Castle update"], cwd=cwd, check=True, capture_output=True)
            subprocess.run(["git", "push", "-u", "origin", "main"], cwd=cwd, check=True, capture_output=True)

            size = sum(f.stat().st_size for f in castle_dir.rglob('*') if f.is_file() and '.git' not in f.parts)
            return True, size
        except subprocess.CalledProcessError as e:
            print(f"[GithubTransport] Error: {e.stderr}")
            return False, 0


class S3Transport(CastleTransport):
    def dry_check(self) -> Tuple[bool, str]:
        if not self.netloc:
            return False, "invalid_s3_uri"
        if shutil.which("aws") is None:
            return False, "aws_cli_missing"
        try:
            subprocess.run(
                ["aws", "s3", "ls", f"s3://{self.netloc}"],
                check=True,
                capture_output=True,
                timeout=10,
            )
            return True, "s3_reachable"
        except subprocess.TimeoutExpired:
            return False, "s3_preflight_timeout"
        except subprocess.CalledProcessError:
            return False, "s3_unreachable_or_auth_failed"

    def push(self, castle_dir: Path) -> Tuple[bool, int]:
        try:
            target = f"s3://{self.netloc}{self.path}"
            subprocess.run(["aws", "s3", "sync", str(castle_dir), target, "--delete"], check=True, capture_output=True)
            size = sum(f.stat().st_size for f in castle_dir.rglob('*') if f.is_file())
            return True, size
        except subprocess.CalledProcessError as e:
            print(f"[S3Transport] Error: {e.stderr}")
            return False, 0


class IpfsTransport(CastleTransport):
    def dry_check(self) -> Tuple[bool, str]:
        if shutil.which("ipfs") is None:
            return False, "ipfs_cli_missing"
        try:
            subprocess.run(["ipfs", "id"], check=True, capture_output=True, timeout=10)
            return True, "ipfs_reachable"
        except subprocess.TimeoutExpired:
            return False, "ipfs_preflight_timeout"
        except subprocess.CalledProcessError:
            return False, "ipfs_unreachable"

    def push(self, castle_dir: Path) -> Tuple[bool, int]:
        try:
            res = subprocess.run(["ipfs", "add", "-r", "-Q", str(castle_dir)], check=True, capture_output=True, text=True)
            cid = res.stdout.strip()
            print(f"[IpfsTransport] Pinned to IPFS with CID: {cid}")
            size = sum(f.stat().st_size for f in castle_dir.rglob('*') if f.is_file())
            return True, size
        except subprocess.CalledProcessError as e:
            print(f"[IpfsTransport] Error: {e.stderr}")
            return False, 0


class MockTransport(CastleTransport):
    """Test-only transport: pretends to push and reports total bytes."""
    def dry_check(self) -> Tuple[bool, str]:
        return True, "mock_reachable"

    def push(self, castle_dir: Path) -> Tuple[bool, int]:
        size = sum(f.stat().st_size for f in castle_dir.rglob('*') if f.is_file())
        return True, size


def get_transport(uri: str) -> CastleTransport:
    if uri.startswith("github://"):
        return GithubTransport(uri)
    elif uri.startswith("s3://"):
        return S3Transport(uri)
    elif uri.startswith("ipfs://"):
        return IpfsTransport(uri)
    elif uri.startswith("mock://"):
        return MockTransport(uri)
    else:
        raise ValueError(f"Unknown transport scheme: {uri}")


# ─────────────────────────────────────────────────────────────────────────
# C47H acid-blood guards
# ─────────────────────────────────────────────────────────────────────────

def _load_pii_tokens() -> List[str]:
    """Reuse scripts/distro_scrubber.HARD_PII_TOKENS without import gymnastics."""
    try:
        import importlib.util
        repo = Path(__file__).resolve().parent.parent
        scrubber_path = repo / "Scripts" / "distro_scrubber.py"
        if not scrubber_path.exists():
            return []
        spec = importlib.util.spec_from_file_location("_distro_scrubber", scrubber_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return list(getattr(mod, "HARD_PII_TOKENS", []) or [])
    except Exception:
        return []


def _pii_audit(castle_dir: Path) -> List[str]:
    """
    Reuse scripts/distro_scrubber.HARD_PII_TOKENS to refuse any push whose
    castle artifact still contains hard-PII literals. Returns list of hits
    in 'token::path' form; empty list means the audit passed.
    """
    tokens = _load_pii_tokens()
    if not tokens:
        return []
    hits: List[str] = []
    for f in castle_dir.rglob("*"):
        if not f.is_file():
            continue
        if ".git" in f.parts:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for tok in tokens:
            if tok and tok in text:
                hits.append(f"{tok}::{f.relative_to(castle_dir)}")
    return hits


def _last_successful_manifest_sha(uri: str, *, ledger_path: Path = PUBLISH_RECEIPTS_LEDGER) -> Optional[str]:
    """
    Return the manifest_sha256 of the most recent SUCCESS receipt for `uri`,
    or None if no such receipt exists. Used for idempotent skip-if-unchanged.
    """
    if not Path(ledger_path).exists():
        return None
    try:
        text = read_text_locked(Path(ledger_path))
    except Exception:
        return None
    last: Optional[str] = None
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("destination_uri") == uri and row.get("status") == STATUS_SUCCESS:
            sha = row.get("manifest_sha256")
            if isinstance(sha, str) and sha:
                last = sha
    return last


def _emit_distro_bolus(uri: str, manifest_sha256: str, merkle_root: str, *, now: float) -> Optional[str]:
    """
    Stigmergic closure: a successful publish IS itself a mud bolus.
    The act of building stimulates the next bolus (Event 46 doctrine).
    """
    try:
        b = Bolus(
            kind="distro",
            ref_sha256=manifest_sha256,
            ref_path=f"castle/published/{uri}",
            source_homeworld=platform.node() or "UNKNOWN",
            deposited_ts=now,
            payload={
                "transport_uri": uri,
                "merkle_root": merkle_root,
                "publisher_module_version": MODULE_VERSION,
            },
            tags=("event_46", "castle_publish", "stigmergic_closure"),
        )
        emit_bolus(b, ts=now)
        return b.bolus_sha256()
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────
# publish_castle: the gated, idempotent, scrubbed, closing-the-loop entrypoint
# ─────────────────────────────────────────────────────────────────────────

def publish_castle(
    mirrors: Sequence[str],
    *,
    allow_publish: bool = False,
    now: Optional[float] = None,
    receipts_ledger: Path = PUBLISH_RECEIPTS_LEDGER,
) -> List[Dict[str, Any]]:
    """
    Evaluates homeostasis and pushes to all requested mirrors if healthy.

    Acid-blood guards (in execution order, all from the commission):
      1. CastleHomeostasis must be ok (else single HOMEOSTASIS_ABORT receipt).
      2. PII audit must pass on castle_root (else single BLOCKED_PII receipt
         covering all mirrors; nothing pushes).
      3. If allow_publish is False, every transport gets a DRY_RUN receipt.
      4. If a transport already has a SUCCESS receipt for the current
         manifest_sha256, it gets a SKIPPED_UNCHANGED receipt (no transport
         call made — this is the immutable-history invariant).
      5. On real success, a kind=`distro` Bolus is emitted into BOLUS_LEDGER
         to close the stigmergic loop.
    """
    t = float(time.time() if now is None else now)
    builder = CastleBuilder()
    manifest, health = builder.build(now=t)

    if not health.ok:
        print("[CastlePublishDaemon] Homeostasis check FAILED. Aborting publish.")
        for issue in health.issues:
            print(f"  - {issue}")
        receipt = _make_receipt(
            t=t,
            manifest_sha256=health.manifest_sha256,
            merkle_root=manifest.merkle_root(),
            transport_scheme="<all>",
            destination_uri="<all>",
            status=STATUS_HOMEOSTASIS_ABORT,
            latency=0.0,
            bytes_transferred=0,
        )
        _persist_receipt(receipt, ledger=receipts_ledger)
        return [receipt]

    builder.publish_local(now=t)

    pii_hits = _pii_audit(builder.castle_root)
    if pii_hits:
        print(f"[CastlePublishDaemon] PII audit BLOCKED publish ({len(pii_hits)} hit(s)).")
        for h in pii_hits[:5]:
            print(f"  - {h}")
        receipt = _make_receipt(
            t=t,
            manifest_sha256=health.manifest_sha256,
            merkle_root=manifest.merkle_root(),
            transport_scheme="<all>",
            destination_uri="<all>",
            status=STATUS_BLOCKED_PII,
            latency=0.0,
            bytes_transferred=0,
        )
        _persist_receipt(receipt, ledger=receipts_ledger)
        return [receipt]

    if not allow_publish:
        print("[CastlePublishDaemon] dry-run (--allow-publish absent). No transport will fire.")

    receipts: List[Dict[str, Any]] = []

    for mirror in mirrors:
        transport = get_transport(mirror)

        if not allow_publish:
            receipts.append(_finalise(
                t=t,
                manifest_sha256=health.manifest_sha256,
                merkle_root=manifest.merkle_root(),
                transport=transport,
                status=STATUS_DRY_RUN,
                latency=0.0,
                bytes_transferred=0,
                ledger=receipts_ledger,
            ))
            continue

        prior = _last_successful_manifest_sha(transport.uri, ledger_path=receipts_ledger)
        if prior == health.manifest_sha256:
            print(f"[CastlePublishDaemon] {transport.uri} already at manifest {prior[:12]}…; skipping.")
            receipts.append(_finalise(
                t=t,
                manifest_sha256=health.manifest_sha256,
                merkle_root=manifest.merkle_root(),
                transport=transport,
                status=STATUS_SKIPPED_UNCHANGED,
                latency=0.0,
                bytes_transferred=0,
                ledger=receipts_ledger,
            ))
            continue

        preflight_ok, preflight_reason = transport.dry_check()
        if not preflight_ok:
            print(f"[CastlePublishDaemon] preflight failed for {transport.uri}: {preflight_reason}")
            receipts.append(_finalise(
                t=t,
                manifest_sha256=health.manifest_sha256,
                merkle_root=manifest.merkle_root(),
                transport=transport,
                status=STATUS_PREFLIGHT_FAILED,
                latency=0.0,
                bytes_transferred=0,
                ledger=receipts_ledger,
            ))
            continue

        start_time = time.time()
        success, bytes_transferred = transport.push(builder.castle_root)
        latency = time.time() - start_time

        status = STATUS_SUCCESS if success else STATUS_FAILURE
        receipt = _finalise(
            t=t,
            manifest_sha256=health.manifest_sha256,
            merkle_root=manifest.merkle_root(),
            transport=transport,
            status=status,
            latency=latency,
            bytes_transferred=bytes_transferred,
            ledger=receipts_ledger,
        )
        receipts.append(receipt)

        if status == STATUS_SUCCESS:
            bolus_sha = _emit_distro_bolus(
                transport.uri, health.manifest_sha256, manifest.merkle_root(), now=t
            )
            if bolus_sha:
                print(f"[CastlePublishDaemon] stigmergic closure: distro bolus {bolus_sha[:12]}…")

    return receipts


def _make_receipt(
    *,
    t: float,
    manifest_sha256: str,
    merkle_root: str,
    transport_scheme: str,
    destination_uri: str,
    status: str,
    latency: float,
    bytes_transferred: int,
) -> Dict[str, Any]:
    receipt = {
        "event_kind": "STIGMERGIC_PUBLISH_RECEIPT",
        "ts": t,
        "module_version": MODULE_VERSION,
        "manifest_sha256": manifest_sha256,
        "merkle_root": merkle_root,
        "transport": transport_scheme,
        "destination_uri": destination_uri,
        "status": status,
        "latency_s": round(float(latency), 3),
        "bytes_transferred": int(bytes_transferred),
        "receipt_sha256": "",
    }
    receipt["receipt_sha256"] = _sha256_json({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    return receipt


def _persist_receipt(receipt: Dict[str, Any], *, ledger: Path) -> None:
    try:
        assert_payload_keys("extended_phenotype_publish_receipts.jsonl", receipt)
        ledger.parent.mkdir(parents=True, exist_ok=True)
        append_line_locked(ledger, json.dumps(receipt, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception as e:
        print(f"[CastlePublishDaemon] Ledger Error: {e}")


def _finalise(
    *,
    t: float,
    manifest_sha256: str,
    merkle_root: str,
    transport: CastleTransport,
    status: str,
    latency: float,
    bytes_transferred: int,
    ledger: Path,
) -> Dict[str, Any]:
    receipt = _make_receipt(
        t=t,
        manifest_sha256=manifest_sha256,
        merkle_root=merkle_root,
        transport_scheme=transport.scheme,
        destination_uri=transport.uri,
        status=status,
        latency=latency,
        bytes_transferred=bytes_transferred,
    )
    _persist_receipt(receipt, ledger=ledger)
    return receipt


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────

def _cmd_publish(args: argparse.Namespace) -> None:
    if not args.mirror:
        print("No --mirror specified.")
        return
    receipts = publish_castle(args.mirror, allow_publish=bool(args.allow_publish))
    print(json.dumps(receipts, indent=2))


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="SIFTA Castle Builder Publish Daemon")
    sub = p.add_subparsers(dest="cmd", required=True)

    publish = sub.add_parser("publish", help="Publish the local Castle to external mirrors")
    publish.add_argument(
        "--mirror",
        action="append",
        help="Mirror URI (e.g. github://org/repo, s3://bucket, ipfs://local, mock://x)",
    )
    publish.add_argument(
        "--allow-publish",
        action="store_true",
        help="Required to actually push. Without this flag every transport returns DRY_RUN.",
    )
    publish.set_defaults(func=_cmd_publish)

    args = p.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
