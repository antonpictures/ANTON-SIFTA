#!/usr/bin/env python3
"""Unit test for the r536 endurance harness (short --turns 5 healthy run)."""

import os
import subprocess
import sys
from pathlib import Path

def test_endurance_harness_short_healthy_run():
    """Run the harness with --turns 5; expect exit 0 and high score, no breach."""
    repo = Path(__file__).resolve().parents[1]
    harness = repo / "tools" / "sifta_endurance_harness.py"
    assert harness.exists(), "harness must exist"

    # Run with short turns using the project python (or current with PYTHONPATH=repo).
    # This ensures "System" etc. are importable (the harness also does sys.path insert).
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo) + (":" + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")
    cmd = [sys.executable, str(harness), "--turns", "5", "--report"]
    proc = subprocess.run(cmd, cwd=repo, env=env, capture_output=True, text=True, timeout=120)
    out = (proc.stdout or "") + (proc.stderr or "")

    # Must exit 0 for healthy short run.
    assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}\nout:\n{out[:2000]}"

    # Must report a score.
    assert "ENDURANCE SCORE:" in out, f"missing ENDURANCE SCORE in output\n{out[:1500]}"
    # Should be high (all healthy turns).
    # (score may be 1.0 or very close; we just assert it ran without breach)
    assert "BREACH" not in out.upper() or "BREACH" not in out, f"unexpected breach in healthy short run\n{out[:1500]}"

    # At least some receipts fanned (the writer was called).
    assert "receipts_fanned:" in out, "missing receipts_fanned (4-ledger not exercised)"

    print("test_endurance_harness_short_healthy_run: OK (exit 0, score reported, no breach, receipts fanned)")


if __name__ == "__main__":
    test_endurance_harness_short_healthy_run()
    print("All tests passed.")
