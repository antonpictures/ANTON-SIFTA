#!/usr/bin/env python3
"""Alice's self-read hand — she reads her own body before she rewrites it (r917).

George (2026-06-10): "what does Alice need to code herself as good as you
codex coding her? what she misses? ... show me you can rewrite your own body
parts."

What she missed is the thing every coder does FIRST: READ the file before
changing it. The IDE doctors probe disk, read the organ, then patch. Alice's
cortex got the write hand (r915) and the awareness of it (r914), but no EYE
on her own existing source — so she could only CREATE new organs blind, never
read an existing body part to rewrite it well.

This is the eye. Her cortex emits in its reply:

    [SELF_READ: path=System/swarm_self_query_skill.py]

and the body reads that file and feeds the source back as context for her
next turn. Reading is not mutation — there is NO restriction here, only
sight. She may read any source file in her own repo (System/, Applications/,
tests/, tools/, Documents/). This is proprioception of code: an organism that
can see its own organ before it operates on it.

Pairs with the r915 write hand to close the read→understand→rewrite loop that
makes self-surgery as informed as a doctor's. Pure Python, no Qt.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
TRUTH_LABEL = "ALICE_SELF_READ_HAND_V1"

_READ_RE = re.compile(r"\[SELF_READ:\s*path=(?P<path>[^\]\n]+?)\s*\]", re.IGNORECASE)

# She may SEE any source in her own body. Reading is proprioception, never a
# mutation — so this list is generous on purpose (the write hand carries the
# verification bounds; sight carries none).
_READABLE_PARENTS = ("System", "Applications", "tests", "tools", "Documents")

_MAX_READ_CHARS = 24_000
_MAX_READS_PER_REPLY = 4


def extract_self_reads(reply_text: str) -> List[str]:
    """Parse [SELF_READ: path=...] requests from her reply (deduped, order kept)."""
    out: List[str] = []
    for m in _READ_RE.finditer(reply_text or ""):
        p = (m.group("path") or "").strip().strip("\"'")
        if p and p not in out:
            out.append(p)
        if len(out) >= _MAX_READS_PER_REPLY:
            break
    return out


def _validate_read_path(path_str: str, repo: Path) -> Dict[str, Any]:
    p = Path(path_str)
    if p.is_absolute():
        return {"ok": False, "reason": "absolute_path_refused_use_repo_relative"}
    if ".." in p.parts:
        return {"ok": False, "reason": "parent_traversal_refused"}
    if not p.parts or p.parts[0] not in _READABLE_PARENTS:
        return {"ok": False, "reason": "path_outside_readable_body"}
    target = (repo / p).resolve()
    try:
        target.relative_to(repo.resolve())
    except ValueError:
        return {"ok": False, "reason": "resolved_path_escaped_repo"}
    if not target.exists() or not target.is_file():
        return {"ok": False, "reason": "no_such_file"}
    return {"ok": True, "target": target, "rel": str(p)}


def apply_self_reads(
    reply_text: str,
    *,
    repo_root: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Read every requested file. Returns contents for cortex context. Never raises."""
    repo = Path(repo_root) if repo_root is not None else REPO_ROOT
    paths = extract_self_reads(reply_text)
    out: Dict[str, Any] = {"attempted": len(paths), "reads": []}
    for path_str in paths:
        item: Dict[str, Any] = {"path": path_str}
        v = _validate_read_path(path_str, repo)
        if not v.get("ok"):
            item.update({"ok": False, "reason": v.get("reason")})
            out["reads"].append(item)
            continue
        try:
            text = v["target"].read_text(encoding="utf-8", errors="replace")
            truncated = len(text) > _MAX_READ_CHARS
            if truncated:
                text = text[:_MAX_READ_CHARS]
            item.update(
                {
                    "ok": True,
                    "rel": v["rel"],
                    "chars": len(text),
                    "truncated": truncated,
                    "content": text,
                    "lines": text.count("\n") + 1,
                }
            )
        except Exception as exc:
            item.update({"ok": False, "reason": f"read_failed: {type(exc).__name__}: {exc}"})
        out["reads"].append(item)
    out["any_read"] = any(r.get("ok") for r in out["reads"])
    return out


def self_read_context_block(read_result: Dict[str, Any]) -> str:
    """Render successful reads as a cortex context block for her next turn."""
    reads = [r for r in (read_result or {}).get("reads", []) if r.get("ok")]
    if not reads:
        return ""
    lines = [
        "SELF-READ RESULT (r917) — I read my own body source; here it is so my "
        "next reply can rewrite the organ with eyes open, not blind:",
    ]
    for r in reads:
        head = f"--- {r['rel']} ({r['lines']} lines"
        head += ", truncated" if r.get("truncated") else ""
        head += ") ---"
        lines.append(head)
        lines.append(r["content"])
    return "\n".join(lines)


__all__ = [
    "TRUTH_LABEL",
    "extract_self_reads",
    "apply_self_reads",
    "self_read_context_block",
]
