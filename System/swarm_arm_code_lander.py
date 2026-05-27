#!/usr/bin/env python3
"""Deterministic code lander for SIFTA agent-arm builds.

Problem (George 2026-05-25): the ``agent_arm_research`` tool dispatches arms in
EVIDENCE mode (``swarm_tool_router`` calls ``ask_agent_arm(..., evidence_mode=
True)``), which captures the arm's stdout as evidence *text* and writes a
receipt — it never writes the app file. So when an arm (e.g. hermes on the
25.8B ``alice-extra-cortex`` cortex) streams a fenced ```python block instead of
calling its own write-file tool, nothing lands on disk.

This module closes that gap WITHOUT the external doctor authoring the app: it
takes the arm's captured output plus the owner's build request, extracts the
fenced code the ARM produced, and writes it to the requested path under the
repo, then ``py_compile``s it and returns an honest receipt. The code is Alice's
arm's; the lander is only the hand that commits it (covenant §7.6 — fix the
hand, do not become the organism).

Pure stdlib. No Qt, no network. Unit-testable in isolation. Never raises — on
any failure it returns ``ok=False`` with a reason so the caller can record a
truthful failure receipt instead of a fake success (covenant §6/§7.2).
"""

from __future__ import annotations

import ast
import py_compile
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

# Largest fenced ```python ... ``` block in the arm's output is the file body.
_FENCE_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)

# Owner-requested repo-relative target path, e.g. Applications/sifta_foo.py.
_PATH_RE = re.compile(
    r"\b((?:Applications|Simulations|System|tests|Utilities)/[\w./-]+\.py)\b"
)


def extract_target_path(prompt: str) -> str | None:
    """Return the repo-relative ``.py`` path the owner asked the arm to write."""
    match = _PATH_RE.search(prompt or "")
    return match.group(1) if match else None


def extract_code(output: str) -> str | None:
    """Return the largest fenced python block in the arm's output.

    A fence is REQUIRED. We no longer fall back to ``ast.parse(output)`` on
    fence-less captures: Claude-style stream JSON is, line-for-line, a sequence
    of valid Python dict-literal expressions (``{"type": "stream_event", …}``
    parses as a dict), so ``ast.parse`` happily accepts a whole stream-JSON
    dump and the lander would then overwrite the target ``.py`` path with
    junk. Observed catastrophe (George 2026-05-26 ~01:06): the talk widget
    file was replaced wholesale with Claude's own stream-event JSON via this
    exact path. Restore from ``git show HEAD:…`` succeeded; the fix is to
    refuse fence-less captures here so the file never gets touched again."""
    if not output:
        return None
    blocks = [b.rstrip() for b in _FENCE_RE.findall(output)]
    blocks = [b for b in blocks if b.strip()]
    if not blocks:
        return None
    return max(blocks, key=len)


def _safe_repo_path(rel_path: str) -> Path | None:
    """Resolve ``rel_path`` under ``_REPO``; refuse anything that escapes it."""
    try:
        target = (_REPO / rel_path).resolve()
        target.relative_to(_REPO.resolve())  # raises ValueError if outside repo
        return target
    except (ValueError, OSError):
        return None


def land_arm_code(
    *, prompt: str, output: str, arm: str, receipt_id: str = ""
) -> dict:
    """Extract the arm's fenced code and write it to the owner-requested path.

    Returns an honest receipt dict. The app content is the arm's; this only
    commits it. Never raises."""
    rel = extract_target_path(prompt)
    if not rel:
        return {"ok": False, "reason": "no_target_path_in_prompt", "arm": arm}

    target = _safe_repo_path(rel)
    if target is None:
        return {"ok": False, "reason": "path_escapes_repo", "rel_path": rel, "arm": arm}

    code = extract_code(output)
    if not code:
        return {"ok": False, "reason": "no_code_block_in_output", "rel_path": rel, "arm": arm}

    # Validate it parses BEFORE writing, so we never land syntactic garbage.
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return {
            "ok": False,
            "reason": f"arm_code_syntax_error: {exc}",
            "rel_path": rel,
            "arm": arm,
        }

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code + "\n", encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "reason": f"write_failed: {exc}", "rel_path": rel, "arm": arm}

    compiled_ok = True
    compile_error = ""
    try:
        py_compile.compile(str(target), doraise=True)
    except py_compile.PyCompileError as exc:  # pragma: no cover - defensive
        compiled_ok = False
        compile_error = str(exc)

    return {
        "ok": True,
        "rel_path": rel,
        "abs_path": str(target),
        "bytes": len(code) + 1,
        "compiled": compiled_ok,
        "compile_error": compile_error,
        "arm": arm,
        "source_receipt": receipt_id,
        "truth_label": "ARM_CODE_LANDED_V1",
    }
