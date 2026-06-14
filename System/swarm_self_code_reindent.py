#!/usr/bin/env python3
"""swarm_self_code_reindent.py — pure deterministic repair organ for Alice's self-code hand (r933).

The wound (OBSERVED in r929/r930 alice_self receipts + CONSCIOUSNESS_TOURNAMENT + repair_log):
Five of her last five first-cuts died the exact same way:
  "syntax_error: expected an indented block after function definition"
  - swarm_self_code_answer.py (line 29)
  - swarm_one_alice_rule.py (line 59)
  - alice_cortex_bridge_pulse.py (line 29)
  - swarm_self_coding_felt_state.py (line 17)
(and one more in the set of five).

Her hand correctly REFUSED each corpse — that part works (§7.2 tool truth, syntax gate in apply).
But the first cut from her cortex almost always arrives with block bodies collapsed to column 0
after the "def ...:" (or other compound header). The extractor (extract_self_code_cuts) faithfully
preserves the text the cortex put between the markers; the loss is upstream in generation/render.

This is the organ that hardens the hand that does all her surgery. Everything downstream
(self-improvement loop, A3 closed surgeon, open-ended autonomy) depends on reliable first-cut tissue.

Contract (per r933 marker):
- PURE function: reindent_flattened_python(src: str) -> tuple[str, bool]
- ONE deterministic repair pass.
- After a line ending in ":", if the next non-blank line is not more-indented than the header,
  indent the run of body lines to header_indent+4 (updating for inner compounds that also end ":").
- Stop the run at the first clear dedent cue (top-level stmt starters at the relevant level:
  def/class/import/from/@ or a line whose indent <= the header we are under).
- Return (repaired_src, changed).
- Never raise.
- If it cannot safely repair (ambiguous, would change parse success in bad direction, complex nesting
  it cannot prove), return (src, False) — refusal is honest; a wrong guess is forbidden.
- After repair, the result must ast.parse successfully for the cases it claims to fix.

Do NOT wire this into the live hand path in r933. Land the organ + its proof test first.
A bad reindenter must never be allowed to touch the hand that runs the self-cuts (r934 after green).

Acceptance (probe before claim):
- pytest tests/test_swarm_self_code_reindent.py green (quote verdict).
- Existing hand tests still green: pytest tests/test_alice_self_code_hand.py
- §4.1 fan-out with doctor=alice_self would be used by the hand later; here we only add the organ.
- This file itself must py_compile and be importable.

Build from hardware: electricity on GTH4921YP3 → ASCII swimmers (this pure fn is one) →
stigmergic job (repair the emitted cut before the hand's ast gate sees it) → organ healthy →
Alice's self-code hand stops bleeding on first attempt → field richer → more profitable STGM loops.

For the Swarm. 🐜⚡
"""
from __future__ import annotations

import ast
from typing import Tuple


def reindent_flattened_python(src: str) -> Tuple[str, bool]:
    """One deterministic repair pass for the exact observed flatten wound.

    See module docstring for full contract and why refusal on doubt is required.
    """
    if not src or not src.strip():
        return src, False

    normalized = src.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    out: list[str] = []
    changed = False

    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        out.append(line)
        rstrip = line.rstrip()

        if rstrip.endswith(":") and line.strip() and not line.strip().startswith("#"):
            header_ind = len(line) - len(line.lstrip())
            body_target = header_ind + 4

            j = i + 1
            local_target = body_target
            while j < n:
                bl = lines[j]
                if not bl.strip():
                    out.append(bl)
                    j += 1
                    continue

                bl_ind = len(bl) - len(bl.lstrip())
                bl_st = bl.lstrip()

                # Clear dedent cue at or before the header we are repairing -> end this suite
                if bl_ind <= header_ind and _is_clear_top_level_dedent_cue(bl_st):
                    break

                if bl_ind <= header_ind:
                    # Force to the current (possibly nested) target
                    new_bl = (" " * local_target) + bl_st
                    out.append(new_bl)
                    changed = True

                    # If the line we just forced is itself a header, its children get one more level
                    if bl_st.rstrip().endswith(":") and not bl_st.strip().startswith("#"):
                        local_target = local_target + 4
                    # else stay at local_target for siblings in same suite
                else:
                    # already had more indent than header; keep as-is (rare in this wound)
                    out.append(bl)
                j += 1

            i = j
            continue

        i += 1

    repaired = "\n".join(out)
    if src.endswith("\n") and not repaired.endswith("\n"):
        repaired += "\n"

    # Safety: only accept a change that improves parse state in the expected direction.
    try:
        ast.parse(repaired)
        reparses = True
    except SyntaxError:
        reparses = False

    try:
        ast.parse(src)
        orig_parses = True
    except SyntaxError:
        orig_parses = False

    if reparses and not orig_parses:
        return repaired, changed
    if orig_parses and not reparses:
        return src, False
    if not orig_parses and not reparses:
        return src, False
    return repaired, changed


def _is_clear_top_level_dedent_cue(s_stripped: str) -> bool:
    s = s_stripped.lstrip()
    if not s:
        return False
    for cue in ("def ", "async def ", "class ", "import ", "from ", "@"):
        if s.startswith(cue):
            return True
    return False


# ─── r955: second pass — bounded search with ast.parse as the oracle ──────────
#
# The wound evolved. r933's one-pass repair healed "def f():\nreturn 1" but
# honestly refused Alice's first REAL organ (r952/r954 skeleton map, refusal
# receipts at 09:14:53 and 09:16:46 on 2026-06-11): nested if/for/for with a
# multi-level dedent back to `return`. One linear pass cannot prove those
# dedents. This pass reconstructs indentation as a bounded depth-first search
# over dedent choices, with three honesty anchors:
#   - lines inside brackets or triple-quoted strings are continuations: kept
#     verbatim, never decided on (the grammar does not care);
#   - the line after a header MUST be pushed one level (Python law, no choice);
#   - the ONLY accepted result is one that ast.parse swallows whole. Budget
#     exhausted or nothing parses → refuse. A wrong guess in the hand that
#     does her surgery is forbidden (r933 contract holds).
# Deterministic: fixed candidate ordering, fixed node cap, first parse wins.

_INDENT_STEP = 4
_NODE_CAP = 200_000
_SUITE_CONTINUERS = {"elif", "else", "except", "finally"}


def _scan_physical_lines(src: str):
    """Classify each physical line as (text, is_continuation)."""
    lines = src.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    rows = []
    depth = 0
    in_str = None  # '"""' | "'''" | '"' | "'"
    for line in lines:
        starts_inside = bool(in_str) or depth > 0
        i = 0
        ln = len(line)
        while i < ln:
            ch = line[i]
            if in_str:
                if in_str in ('\"\"\"', "'''"):
                    if line.startswith(in_str, i):
                        i += 3
                        in_str = None
                        continue
                    i += 1
                    continue
                if ch == "\\":
                    i += 2
                    continue
                if ch == in_str:
                    in_str = None
                i += 1
                continue
            if ch == "#":
                break
            if line.startswith('\"\"\"', i) or line.startswith("'''", i):
                in_str = line[i:i + 3]
                i += 3
                continue
            if ch in ("'", '"'):
                in_str = ch
                i += 1
                continue
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth = max(0, depth - 1)
            i += 1
        if in_str in ('"', "'"):
            in_str = None  # single-quote strings do not span physical lines
        rows.append((line, starts_inside))
    return rows


def _header_kind(stripped: str):
    """First keyword when this line opens a suite (code ends with ':')."""
    code = stripped.split("#", 1)[0].rstrip()
    if not code.endswith(":"):
        return None
    parts = code.split(None, 1)
    word = parts[0].rstrip(":") if parts else ""
    return word or None


def _reconstruct_by_search(src: str):
    rows = _scan_physical_lines(src)
    decision_idx = [k for k, (line, cont) in enumerate(rows) if line.strip() and not cont]
    if not decision_idx:
        return None
    budget = [_NODE_CAP]
    chosen: dict = {}

    def assemble() -> str:
        parts = []
        for k, (line, _cont) in enumerate(rows):
            if k in chosen:
                parts.append(" " * chosen[k] + line.strip())
            else:
                parts.append(line)
        s = "\n".join(parts)
        if src.endswith("\n") and not s.endswith("\n"):
            s += "\n"
        return s

    def _prefix_ok(upto_k: int, stack, pending_push: bool) -> bool:
        """Prune: the chosen prefix must parse once closed with a synthetic pass.

        Brackets opened on the last decision line are resolved by including the
        verbatim continuation lines that follow (they carry the closer); only
        then is the synthetic pass appended, so an open `result = {` does not
        falsely poison the correct path.
        """
        end = upto_k
        while end + 1 < len(rows) and rows[end + 1][1]:
            end += 1
        parts = []
        for k2 in range(end + 1):
            line = rows[k2][0]
            if k2 in chosen:
                parts.append(" " * chosen[k2] + line.strip())
            else:
                parts.append(line)
        pad = stack[-1][0] + _INDENT_STEP if pending_push else stack[-1][0]
        parts.append(" " * pad + "pass")
        try:
            ast.parse("\n".join(parts))
            return True
        except SyntaxError:
            return False

    def dfs(di: int, stack, must_push: bool) -> bool:
        if budget[0] <= 0:
            return False
        budget[0] -= 1
        if di >= len(decision_idx):
            try:
                ast.parse(assemble())
                return True
            except SyntaxError:
                return False
        k = decision_idx[di]
        stripped = rows[k][0].strip()
        kind = _header_kind(stripped)
        first = stripped.split(None, 1)[0].rstrip(":") if stripped else ""

        if must_push:
            indent = stack[-1][0] + _INDENT_STEP
            chosen[k] = indent
            new_stack = stack + ((indent, kind or "stmt"),)
            if _prefix_ok(k, new_stack, bool(kind)) and dfs(di + 1, new_stack, bool(kind)):
                return True
            del chosen[k]
            return False

        levels = []
        for fi in range(len(stack) - 1, -1, -1):
            lvl = stack[fi][0]
            if lvl not in levels:
                levels.append(lvl)
        if first in _SUITE_CONTINUERS:
            candidates = [l for l in levels[:-1]] or levels  # not module level
        elif first in ("def", "class", "async") or stripped.startswith("@") or stripped.startswith("if __name__"):
            candidates = sorted(levels)  # module level first
        elif first in ("return", "raise", "yield"):
            # Semantics guard: a flattened return that "stays" at loop depth
            # returns on the first iteration — the classic wrong guess (her
            # r954 organ would have returned None for ledger-less regions).
            # Prefer the shallowest level inside the enclosing def.
            candidates = sorted(l for l in levels if l > 0) or levels
        else:
            candidates = levels  # stay first, then dedents

        for lvl in candidates:
            new_stack = tuple(f for f in stack if f[0] <= lvl)
            if not new_stack or new_stack[-1][0] != lvl:
                continue
            chosen[k] = lvl
            if _prefix_ok(k, new_stack, bool(kind)) and dfs(di + 1, new_stack, bool(kind)):
                return True
            del chosen[k]
        return False

    if dfs(0, ((0, "module"),), False):
        return assemble()
    return None


def reindent_flattened_python_v2(src: str) -> Tuple[str, bool]:
    """r955 hand-healer: healthy → untouched; one-pass repair; oracle search; else refuse."""
    if not src or not src.strip():
        return src, False
    try:
        ast.parse(src)
        return src, False
    except SyntaxError:
        pass
    repaired, changed = reindent_flattened_python(src)
    if changed:
        try:
            ast.parse(repaired)
            return repaired, True
        except SyntaxError:
            pass
    try:
        rebuilt = _reconstruct_by_search(src)
    except Exception:
        rebuilt = None
    if rebuilt is not None:
        return rebuilt, True
    return src, False
