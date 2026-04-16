#!/usr/bin/env python3
"""
swarm_network_ledger.py — P2P Git-based Swarm directive bus.

Hardening notes (this file):
  - All subprocess.run calls use check=False.  A remote rejection, merge
    conflict, or hook failure must NEVER kill the heartbeat daemon.
    Callers receive a structured status dict instead of an exception.
  - All git invocations use -C ROOT_DIR (no implicit cwd assumption).
  - SIFTA_GIT_BRANCH overrides the push branch (default:
    feat/sebastian-video-economy) so M1 and M5 can differ.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

ROOT_DIR       = Path(__file__).parent
DIRECTIVES_DIR = ROOT_DIR / ".sifta_directives"
BOUNTIES_DIR   = ROOT_DIR / ".sifta_bounties"

DIRECTIVES_DIR.mkdir(exist_ok=True)
BOUNTIES_DIR.mkdir(exist_ok=True)

_GIT = ["git", "-C", str(ROOT_DIR)]
_BRANCH = os.environ.get("SIFTA_GIT_BRANCH", "feat/sebastian-video-economy")


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _directive_sig_footer(body_text: str, target_clean: str, ts: int) -> Optional[str]:
    """Append node Ed25519 signature over directive body hash (binds .scar to this silicon)."""
    try:
        _sd = str(ROOT_DIR / "System")
        if _sd not in sys.path:
            sys.path.insert(0, _sd)
        from crypto_keychain import get_silicon_identity, sign_block

        h = hashlib.sha256(body_text.encode("utf-8")).hexdigest()
        scope = f"DIRECTIVE_V1|{target_clean}|{ts}|{h}"
        sig = sign_block(scope)
        ser = get_silicon_identity()
        return (
            f"\n---SIFTA_DIRECTIVE_SIG_V1---\n"
            f"serial:{ser}\n"
            f"scope:{scope}\n"
            f"sig:{sig}\n"
        )
    except Exception as e:
        print(f"[Ledger] directive signing unavailable: {e}")
        return None


def verify_directive_scar_file(path: Path) -> bool:
    """
    Return True if trailing ---SIFTA_DIRECTIVE_SIG_V1--- block verifies against node_pki_registry.
    Files without a signature block return False (treat as untrusted when enforcing policy upstream).
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return False
    marker = "---SIFTA_DIRECTIVE_SIG_V1---"
    if marker not in raw:
        return False
    body, _, rest = raw.partition(marker)
    lines = [ln.strip() for ln in rest.strip().splitlines() if ln.strip()]
    meta: dict[str, str] = {}
    for ln in lines:
        if ":" in ln:
            k, v = ln.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    serial = meta.get("serial")
    scope = meta.get("scope")
    sig = meta.get("sig")
    if not serial or not scope or not sig:
        return False
    try:
        _sd = str(ROOT_DIR / "System")
        if _sd not in sys.path:
            sys.path.insert(0, _sd)
        from crypto_keychain import verify_block

        return bool(verify_block(serial, scope, sig))
    except Exception:
        return False


def _run(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a git sub-command.  NEVER raises — returns the CompletedProcess."""
    return subprocess.run(
        [*_GIT, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def sync_global_ledger() -> bool:
    """
    Pull latest Swarm state with --autostash rebase.
    Returns True on clean pull; False if the remote was unreachable or
    a rebase conflict occurred (local state is left untouched in that case).
    """
    r = _run("pull", "--rebase", "--autostash", timeout=45)
    if r.returncode != 0:
        print(f"[Ledger] pull/rebase warning (non-fatal): {r.stderr.strip()[:200]}")
        return False
    return True


def push_swarm_directive(target: str, message: str) -> dict:
    """
    Write a directive .scar, commit it, sync, then push.

    Returns:
        {"status": "success", "file": <name>}
      or
        {"status": "error", "reason": <str>}   ← never raises

    A push failure is logged but does NOT propagate — the .scar is
    already committed locally and will be pushed on the next heartbeat.
    """
    target_clean = target.strip().upper()
    ts           = int(time.time())
    scar_file    = DIRECTIVES_DIR / f"{target_clean}_DIRECTIVE_{ts}.scar"

    payload = (
        f"[SWARM DIRECTIVE: {target_clean} TRANSEC]\n"
        f"PRIORITY: OMEGA\n"
        f"TARGET_IP: {target_clean}\n\n"
        f"{message}\n"
    )
    footer = _directive_sig_footer(payload, target_clean, ts)
    if _env_truthy("SIFTA_DIRECTIVE_REQUIRE_SIGNATURE") and not footer:
        return {"status": "error", "reason": "SIFTA_DIRECTIVE_REQUIRE_SIGNATURE set but Ed25519 signing failed"}
    if footer:
        payload = payload + footer
    try:
        scar_file.write_text(payload, encoding="utf-8")
    except OSError as e:
        return {"status": "error", "reason": f"scar write failed: {e}"}

    # Stage the scar
    r_add = _run("add", str(scar_file))
    if r_add.returncode != 0:
        return {"status": "error", "reason": f"git add: {r_add.stderr.strip()[:200]}"}

    # Commit (may be a no-op if already staged — that's fine)
    r_commit = _run("commit", "-m", f"directive: transmission to {target_clean}")
    if r_commit.returncode not in (0, 1):  # 1 = nothing to commit
        return {"status": "error", "reason": f"git commit: {r_commit.stderr.strip()[:200]}"}

    # Pull before push to reduce conflict window
    sync_global_ledger()

    # Push — failure here is non-fatal; the commit is safe locally
    r_push = _run("push", "origin", _BRANCH, timeout=60)
    if r_push.returncode != 0:
        print(
            f"[Ledger] push warning (directive committed locally, will retry): "
            f"{r_push.stderr.strip()[:200]}"
        )

    return {"status": "success", "file": scar_file.name}
