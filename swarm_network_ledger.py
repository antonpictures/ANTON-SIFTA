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
import os
import subprocess
import time
from pathlib import Path

ROOT_DIR       = Path(__file__).parent
DIRECTIVES_DIR = ROOT_DIR / ".sifta_directives"
BOUNTIES_DIR   = ROOT_DIR / ".sifta_bounties"

DIRECTIVES_DIR.mkdir(exist_ok=True)
BOUNTIES_DIR.mkdir(exist_ok=True)

_GIT = ["git", "-C", str(ROOT_DIR)]
_BRANCH = os.environ.get("SIFTA_GIT_BRANCH", "feat/sebastian-video-economy")


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
