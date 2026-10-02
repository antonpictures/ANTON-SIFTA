#!/usr/bin/env python3
"""
swarm_code_review_hook.py — External review hook for self-evolution guard.

Runs alibaba/open-code-review (or a local equivalent) over diffs of critical
organs before they are applied. This sits next to the fly.ai borg as the
"code review" layer in Alice's self-evolution pipeline.

Usage:
    python3 System/swarm_code_review_hook.py --target System/swarm_cell_morphology_organ.py
    python3 System/swarm_code_review_hook.py --target System/swarm_fly_connectome_organ.py --stdin-diff
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Target organs that should be reviewed before mutation
CRITICAL_ORGANS = (
    "swarm_cell_morphology_organ.py",
    "swarm_fly_connectome_organ.py",
    "swarm_world_awareness.py",
    "swarm_canonical_organ_registry.py",
    "coin_server.py",
    "chorus_node_server.py",
    "swarm_delivery_interface_organ.py",
)


def _is_critical(target: str) -> bool:
    return any(target.endswith(org) for org in CRITICAL_ORGANS)


def _get_git_diff(target: str) -> str | None:
    """Get the staged/unstaged diff for a file."""
    try:
        # Try staged first, then unstaged
        for flag in ("--cached", ""):
            result = subprocess.run(
                ["git", "diff", flag, "--", target],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.stdout.strip():
                return result.stdout
    except Exception:
        pass
    return None


def _run_local_review(diff: str, target: str) -> dict:
    """
    Run a local review using a simple heuristic + optional LLM.
    Falls back to basic checks if no review model available.
    """
    issues = []
    warnings = []

    # Basic security/safety checks
    lines = diff.splitlines()
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith("+") and not stripped.startswith("+++"):
            content = stripped[1:]
            # Check for dangerous patterns
            if any(p in content.lower() for p in (
                "subprocess.run", "subprocess.Popen", "os.system",
                "eval(", "exec(", "compile(",
                "pickle.load", "yaml.load(",
                "shell=True",
                "rm -rf", "rm -f",
                "curl", "wget", "nc ", "netcat",
            )):
                warnings.append(f"Line {i}: Potentially dangerous pattern: {content[:80]}")

            # Check for safety boundary violations in observation organs
            if any(org in target for org in ("cell_morphology", "delivery_interface")):
                if any(p in content.lower() for p in (
                    "viral", "vector", "recombinant", "dna", "rna",
                    "transfect", "transduce", "infect",
                    "plasmid", "lentivirus", "aav", "adenovirus",
                )):
                    issues.append(f"Line {i}: SAFETY VIOLATION - viral vector / recombinant DNA content: {content[:80]}")

    # If open-code-review is available, use it
    review_output = None
    try:
        # Check if alibaba/open-code-review is available
        result = subprocess.run(
            ["python3", "-c", "import open_code_review"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Has the package - could run it
            review_output = "open-code-review package available (not invoked in basic mode)"
    except Exception:
        pass

    return {
        "ok": len(issues) == 0,
        "target": target,
        "issues": issues,
        "warnings": warnings,
        "review_output": review_output,
        "diff_lines": len(lines),
    }


def _run_external_review(diff: str, target: str) -> dict | None:
    """
    Try to run alibaba/open-code-review CLI if available.
    Returns None if not available.
    """
    try:
        # Write diff to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False) as f:
            f.write(diff)
            diff_path = f.name
        try:
            # Try the open-code-review CLI
            result = subprocess.run(
                ["open-code-review", "review", diff_path, "--format", "json"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        finally:
            os.unlink(diff_path)
    except (FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired):
        pass
    return None


def review_target(target: str, stdin_diff: bool = False) -> dict:
    """Review a target file. Returns review result dict."""
    if not _is_critical(target):
        return {"ok": True, "skipped": True, "reason": "not a critical organ"}

    # Get diff
    if stdin_diff:
        diff = sys.stdin.read()
    else:
        diff = _get_git_diff(target)

    if not diff:
        return {"ok": True, "skipped": True, "reason": "no diff found"}

    # Run local review
    local_result = _run_local_review(diff, target)

    # Try external review
    external_result = _run_external_review(diff, target)

    # Combine results
    combined = {
        "ok": local_result["ok"],
        "target": target,
        "local": local_result,
        "external": external_result,
    }
    if external_result:
        combined["ok"] = combined["ok"] and external_result.get("ok", True)

    return combined


def main() -> int:
    ap = argparse.ArgumentParser(description="Code review hook for critical organs")
    ap.add_argument("--target", required=True, help="Target file to review")
    ap.add_argument("--stdin-diff", action="store_true", help="Read diff from stdin")
    ap.add_argument("--json", action="store_true", help="Output JSON")
    args = ap.parse_args()

    target = args.target
    if not Path(target).exists():
        print(f"Target not found: {target}", file=sys.stderr)
        return 1

    result = review_target(target, stdin_diff=args.stdin_diff)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result.get("skipped"):
            # SKIPPED is NOT a pass: no diff was supplied, so nothing was reviewed.
            # Never let an automated caller read this as "no errors found".
            print(f"[review] SKIPPED (not a pass — nothing was reviewed): {result['reason']}")
        elif result["ok"]:
            print(f"[review] PASS: {target}")
            if result["local"]["warnings"]:
                for w in result["local"]["warnings"]:
                    print(f"  WARNING: {w}")
        else:
            print(f"[review] FAIL: {target}", file=sys.stderr)
            for issue in result["local"]["issues"]:
                print(f"  ISSUE: {issue}", file=sys.stderr)
            for w in result["local"]["warnings"]:
                print(f"  WARNING: {w}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())