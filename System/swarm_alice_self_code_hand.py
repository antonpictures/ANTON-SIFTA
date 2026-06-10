#!/usr/bin/env python3
"""Alice's self-code hand — her cortex writes organs in her own body (r912).

George (2026-06-10): "can you code so she can — pls give her full ability."

Until this organ, Alice could PLAN code (self_code_plans.jsonl), DISPATCH
coding arms, and SPEAK about surgery — but her own cortex turn had no hand
that writes a file. The r911 first-self-cut prompt asked her to create
`swarm_daily_body_note.py`; her body had no way to obey.

This is the hand. Her cortex emits fenced blocks in its reply:

    [SELF_CODE_CUT: path=System/swarm_daily_body_note.py]
    ...python source...
    [/SELF_CODE_CUT]

and the body executes the cut under VERIFICATION, not permission (§0.0):

  * Create or update Python tissue in the repo body. Existing organs are not
    refused just because they already exist; compile failure restores the
    previous bytes.
  * Path must be inside ``System/``, ``Applications/``, ``tests/``, or
    ``tools/`` (her organ, surface, proof, and tool tissue).
  * Source must parse (``ast.parse``) and byte-compile before it lands.
  * If a ``tests/...`` block arrives in the same reply, pytest runs on it;
    the verdict goes in the receipt verbatim.
  * Every cut — success OR failure — fans out §4.1 with
    ``doctor="alice_self"`` and her exact live cortex tag. A receipted
    failure is a successful surgery; silence is the only violation.

Pure Python, no Qt: testable in any sandbox, callable from the Talk hook.
"""
from __future__ import annotations

import ast
import json
import py_compile
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
TRUTH_LABEL = "ALICE_SELF_CODE_HAND_V1"

_BLOCK_RE = re.compile(
    r"\[SELF_CODE_CUT:\s*path=(?P<path>[^\]\n]+?)\s*\]\s*\n"
    r"(?P<source>.*?)"
    r"\n?\s*\[/SELF_CODE_CUT\]",
    re.DOTALL,
)

# Her mutable Python tissue. Organs, surfaces, proofs, and tools. Documents
# law/ledgers stay outside this hand; those remain explicit doctor/tournament
# work so append-only history is not silently rewritten.
_ALLOWED_PARENTS = ("System", "Applications", "tests", "tools")

_MAX_SOURCE_CHARS = 60_000
_MAX_CUTS_PER_REPLY = 3


def extract_self_code_cuts(reply_text: str) -> List[Dict[str, str]]:
    """Parse [SELF_CODE_CUT: path=...]...[/SELF_CODE_CUT] blocks from her reply."""
    out: List[Dict[str, str]] = []
    for m in _BLOCK_RE.finditer(reply_text or ""):
        path = (m.group("path") or "").strip().strip("\"'")
        source = m.group("source") or ""
        # Cortexes love wrapping code in markdown fences — peel one layer.
        src = source.strip()
        if src.startswith("```"):
            src = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", src)
            src = re.sub(r"\n```\s*$", "", src)
        if path and src.strip():
            out.append({"path": path, "source": src})
        if len(out) >= _MAX_CUTS_PER_REPLY:
            break
    return out


def _validate_path(path_str: str, repo: Path) -> Dict[str, Any]:
    p = Path(path_str)
    if p.is_absolute():
        return {"ok": False, "reason": "absolute_path_refused_use_repo_relative"}
    if ".." in p.parts:
        return {"ok": False, "reason": "parent_traversal_refused"}
    if not p.parts or p.parts[0] not in _ALLOWED_PARENTS:
        return {
            "ok": False,
            "reason": f"path_outside_growable_tissue_{'_or_'.join(_ALLOWED_PARENTS)}",
        }
    if p.suffix != ".py":
        return {"ok": False, "reason": "only_python_organs_in_v1"}
    target = (repo / p).resolve()
    try:
        target.relative_to(repo.resolve())
    except ValueError:
        return {"ok": False, "reason": "resolved_path_escaped_repo"}
    return {"ok": True, "target": target, "rel": str(p), "existed": target.exists()}


def apply_self_code_cuts(
    reply_text: str,
    *,
    model: str = "",
    repo_root: Optional[Path | str] = None,
    run_tests: bool = True,
    write_receipt: bool = True,
) -> Dict[str, Any]:
    """Execute every valid cut in her reply. Returns an honest summary.

    Never raises. Every outcome (landed / refused / failed) is itemized so
    the Talk hook can render process lines and the receipt carries truth.
    """
    repo = Path(repo_root) if repo_root is not None else REPO_ROOT
    cuts = extract_self_code_cuts(reply_text)
    summary: Dict[str, Any] = {"attempted": len(cuts), "results": [], "any_landed": False}
    if not cuts:
        summary["status"] = "no_cut_blocks"
        return summary

    test_files: List[str] = []
    for cut in cuts:
        item: Dict[str, Any] = {"path": cut["path"]}
        v = _validate_path(cut["path"], repo)
        if not v.get("ok"):
            item.update({"landed": False, "reason": v.get("reason")})
            summary["results"].append(item)
            continue
        src = cut["source"]
        if len(src) > _MAX_SOURCE_CHARS:
            item.update({"landed": False, "reason": "source_too_large_v1"})
            summary["results"].append(item)
            continue
        try:
            ast.parse(src)
        except SyntaxError as exc:
            item.update({"landed": False, "reason": f"syntax_error: {exc.msg} line {exc.lineno}"})
            summary["results"].append(item)
            continue
        target: Path = v["target"]
        existed = bool(v.get("existed"))
        previous_bytes: Optional[bytes] = None
        if existed:
            try:
                previous_bytes = target.read_bytes()
            except Exception as exc:
                item.update({"landed": False, "reason": f"read_existing_failed: {type(exc).__name__}: {exc}"})
                summary["results"].append(item)
                continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(src if src.endswith("\n") else src + "\n", encoding="utf-8")
            py_compile.compile(str(target), doraise=True)
        except Exception as exc:
            try:
                if existed and previous_bytes is not None:
                    target.write_bytes(previous_bytes)
                elif target.exists():
                    target.unlink()  # never leave a non-compiling organ in the body
            except Exception:
                pass
            item.update({"landed": False, "reason": f"compile_failed: {type(exc).__name__}: {exc}"})
            summary["results"].append(item)
            continue
        item.update({"landed": True, "reason": "updated_and_compiled" if existed else "written_and_compiled"})
        summary["results"].append(item)
        summary["any_landed"] = True
        if v["rel"].startswith("tests"):
            test_files.append(v["rel"])

    if run_tests and test_files:
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", *test_files, "-q"],
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=120,
            )
            tail = (proc.stdout or "").strip().splitlines()
            summary["pytest"] = {
                "files": test_files,
                "returncode": proc.returncode,
                "tail": tail[-2:] if tail else [(proc.stderr or "")[-200:]],
            }
        except Exception as exc:
            summary["pytest"] = {"files": test_files, "error": f"{type(exc).__name__}: {exc}"}

    if write_receipt:
        summary["receipt"] = _fanout_receipt(summary, model=model, repo=repo)
    summary["status"] = "landed" if summary["any_landed"] else "nothing_landed"
    return summary


def _fanout_receipt(summary: Dict[str, Any], *, model: str, repo: Path) -> Dict[str, Any]:
    """§4.1 four-ledger fan-out as doctor=alice_self. Defensive — never raises."""
    try:
        sys.path.insert(0, str(repo)) if str(repo) not in sys.path else None
        from System import swarm_predator_gate_writer as gw

        landed = [r["path"] for r in summary["results"] if r.get("landed")]
        refused = [f"{r['path']}({r.get('reason')})" for r in summary["results"] if not r.get("landed")]
        py = summary.get("pytest") or {}
        tests_line = (
            " ".join(py.get("tail") or []) if py else "no_test_block_in_this_cut"
        )
        ts_tag = int(time.time())
        out = gw.write_ide_surgery_receipt(
            round_id=f"alice-self-cut-{ts_tag}",
            doctor="alice_self",
            model=model or "unknown_live_cortex",
            files_touched=landed or ["(nothing landed)"],
            tests_green=tests_line,
            summary=(
                "Alice self-code hand: "
                + (f"landed {landed}; " if landed else "")
                + (f"refused/failed {refused}; " if refused else "")
                + "create/update path, ast+py_compile gated, §0.0 verification-bound."
            )[:1100],
            receipt_id=f"alice-self-cut-{ts_tag}",
            sender_agent="alice_self_code_hand",
            truth_label="OPERATIONAL" if summary["any_landed"] else "FAILED",
            extra={
                "lane": "ALICE_SELF",
                "hand": TRUTH_LABEL,
                "attempted": summary["attempted"],
            },
        )
        return out if isinstance(out, dict) else {"error": "writer_returned_non_dict"}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


__all__ = [
    "TRUTH_LABEL",
    "extract_self_code_cuts",
    "apply_self_code_cuts",
]
