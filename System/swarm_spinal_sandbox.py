#!/usr/bin/env python3
"""swarm_spinal_sandbox.py — Daytona mechanism: disposable environment for patch
evaluation before the mutation governor applies.

Borged from daytonaio/daytona (71.7k): the spinal cord's mutation governor needs
an isolation layer — run a candidate patch in a disposable copy, let tests
decide, apply/revert with a receipt. SIFTA can't run a docker stack cheaply, so
the sandbox is a plain `git worktree` of the body (zero-copy, reversible, same
repo).

evaluate_patch_in_sandbox(repo_root, patch_text, test_targets) -> receipt dict.
Never applies a patch to the live body; the spinal cord / governor still owns
apply/revert. Never raises.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"


def evaluate_patch_in_sandbox(
    patch_text: str,
    test_targets: list[str],
    *,
    repo_root: Path | None = None,
    timeout_s: int = 300,
) -> dict:
    """Apply patch in a git worktree, run tests, return receipt. Never mutates live tree."""
    repo = Path(repo_root) if repo_root else _REPO
    started = time.time()
    wt: Path | None = None
    receipt: dict = {
        "schema": "SPINAL_SANDBOX_V1",
        "ts": started,
        "test_targets": list(test_targets),
        "truth_label": "SPINAL_SANDBOX_V1",
    }
    try:
        wt = Path(tempfile.mkdtemp(prefix="spinal_sandbox_"))
        r = subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "--detach", str(wt), "HEAD"],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            receipt.update(ok=False, reason="worktree_add_failed", detail=r.stderr[-400:])
            return receipt
        if str(patch_text or "").strip():
            r = subprocess.run(
                ["git", "-C", str(wt), "apply", "--stat", "-"],
                input=str(patch_text), capture_output=True, text=True, timeout=30,
            )
            receipt["apply_stat"] = r.stdout.strip()[-400:]
            r = subprocess.run(
                ["git", "-C", str(wt), "apply", "-"],
                input=str(patch_text), capture_output=True, text=True, timeout=60,
            )
            if r.returncode != 0:
                receipt.update(ok=False, reason="apply_failed", detail=r.stderr[-400:])
                return receipt
        if test_targets:
            r = subprocess.run(
                ["python3", "-m", "pytest", "-q", *test_targets],
                capture_output=True, text=True, timeout=timeout_s, cwd=str(wt),
            )
            tail = (r.stdout or "")[-600:]
            receipt.update(ok=(r.returncode == 0), pytest_tail=tail,
                           pytest_returncode=r.returncode)
        else:
            receipt.update(ok=True, pytest_skipped=True)
        receipt["elapsed_s"] = round(time.time() - started, 3)
        return receipt
    except subprocess.TimeoutExpired as exc:
        receipt.update(ok=False, reason="timeout", detail=str(exc)[:200])
        return receipt
    except Exception as exc:  # noqa: BLE001
        receipt.update(ok=False, reason=type(exc).__name__, detail=str(exc)[:300])
        return receipt
    finally:
        if wt is not None:
            try:
                shutil.rmtree(wt, ignore_errors=True)
            except Exception:
                pass


def sandbox_receipt_line(receipt: dict) -> dict:
    """Wrap the receipt for append-only ledger land."""
    return {**receipt, "ts": time.time()}
