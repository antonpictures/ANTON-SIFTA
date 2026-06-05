#!/usr/bin/env python3
"""GC / stack hardening for the live SIFTA boot (r246).

George 2026-06-01: Alice's process took a SIGSEGV. The crash trace is unambiguous about WHERE:
main thread, inside the garbage collector —

    0  mark_stacks + 132
    1  _PyGC_Collect + 1488
    2  _Py_HandlePending + 76
    ...
    6  QtCore PyQtSlot::call            <- fired from inside a PyQt slot
    11 QtCore QTimer::timerEvent        <- driven by a QTimer
    --->  GAP below a Stack Guard page  <- faulting addr = C-stack exhaustion

`mark_stacks` is CPython 3.14's NEW incremental garbage collector walking thread frame stacks.
With the self-narration organ running a `while True` loop in a background thread, a routine
incremental collection triggered from a main-thread QTimer slot recursed through frame objects
and ran off the end of the C stack. This is a Python-3.14 + PyQt6 + threads instability, not an
Alice logic bug.

THE REAL FIX is environmental: run SIFTA on Python 3.12 (PyQt6's stable target), not 3.14.4.
This module is the in-repo MITIGATION while on 3.14: it shrinks what the incremental collector
has to mark each cycle (gc.freeze() moves the steady-state boot graph into the permanent set so
`mark_stacks` no longer walks it) and lowers collection frequency during timer storms. It cannot
guarantee the segfault is gone — only the Python downgrade does that — but it removes the marking
surface that overflowed. Pure stdlib; headless-testable (no Qt).
"""
from __future__ import annotations

import sys
from typing import Any, Callable, Optional


def python_version_tuple() -> tuple[int, int]:
    return (sys.version_info.major, sys.version_info.minor)


def should_harden(version: Optional[tuple[int, int]] = None) -> bool:
    """True on Python 3.14+ (the incremental-GC `mark_stacks` surface). On 3.12/3.13 we leave the
    runtime untouched so we never change behavior on the stable target we actually recommend."""
    v = version or python_version_tuple()
    return v >= (3, 14)


def harden_runtime_for_gc(
    *,
    force: bool = False,
    freeze: bool = True,
    threshold: tuple[int, int, int] = (50_000, 500, 500),
    log: Optional[Callable[[str], None]] = None,
) -> dict[str, Any]:
    """Reduce the incremental-GC marking surface that overflowed the C stack.

    - `gc.set_threshold(high)` — collect far less often during the 2-3s timer / self-narration storm.
    - `gc.collect(); gc.freeze()` — move the steady-state object graph into the permanent generation
      so subsequent incremental collections do NOT traverse it (smaller `mark_stacks` walks).
    Call this ONCE, AFTER boot has allocated its long-lived objects (so they get frozen)."""
    notes: list[str] = []
    result: dict[str, Any] = {"python": sys.version.split()[0], "applied": False, "notes": notes}
    if not (force or should_harden()):
        notes.append("skipped: python<3.14, runtime left untouched")
        return result
    import gc
    try:
        gc.set_threshold(*threshold)
        notes.append(f"gc_threshold={threshold}")
    except Exception as exc:
        notes.append(f"threshold_failed:{type(exc).__name__}:{exc}")
    if freeze:
        try:
            gc.collect()
            gc.freeze()
            frozen = gc.get_freeze_count() if hasattr(gc, "get_freeze_count") else -1
            notes.append(f"gc_frozen_objects={frozen}")
        except Exception as exc:
            notes.append(f"freeze_failed:{type(exc).__name__}:{exc}")
    result["applied"] = True
    msg = "[gc_hardening] " + "; ".join(notes)
    if log:
        try:
            log(msg)
        except Exception:
            pass
    return result


# ── r315 (cowork_claude) ────────────────────────────────────────────────────
# George re-booted on 3.14.4 after r246 and Alice STILL took the SIGSEGV: thread 11
# was `self_narration` (its while-True loop), thread 0 (main) crashed in `mark_stacks`
# at a C-stack-guard gap — an automatic collection fired INSIDE a QTimer slot via
# `_Py_HandlePending` and recursed off the end of the C stack. r246 shrank the marking
# surface (freeze) but never stopped auto-GC from firing mid-slot. These two functions
# add the missing lever George approved: turn OFF automatic collection so it can never
# fire inside a slot, and collect manually ONLY when no thread holds a dangerously deep
# Python frame chain (the exact surface `mark_stacks` walks). Still pure stdlib, no Qt —
# the desktop owns the timer that drives `safe_manual_collect`. The real fix is still
# Python 3.12; this keeps her alive on 3.14 until George downgrades.


def disable_auto_collection(*, force: bool = False, log: Optional[Callable[[str], None]] = None) -> dict[str, Any]:
    """Disable CPython's automatic garbage collection so a collection can NEVER be
    triggered from inside a QTimer slot via `_Py_HandlePending` (the crash path).

    No-op on Python <3.14 (the stable target has no `mark_stacks` overflow, so we leave
    its GC alone). After this, something MUST drive `safe_manual_collect` on a cadence or
    memory grows unbounded — the desktop wires a recurring shallow-stack timer for that."""
    result: dict[str, Any] = {"disabled": False, "python": sys.version.split()[0]}
    if not (force or should_harden()):
        result["reason"] = "skipped: python<3.14, automatic GC left enabled"
        return result
    import gc
    try:
        result["was_enabled"] = gc.isenabled()
        gc.disable()
        result["disabled"] = True
        if log:
            try:
                log("[gc_hardening] automatic GC disabled; manual shallow-stack collection only")
            except Exception:
                pass
    except Exception as exc:
        result["reason"] = f"disable_failed:{type(exc).__name__}:{exc}"
    return result


def max_thread_frame_depth() -> int:
    """Deepest Python frame chain across ALL live threads.

    `gc.mark_stacks` recurses over every thread's frame stack on the collecting thread's
    C stack, so the deepest chain anywhere — not the caller's depth — is what overflows.
    We gate manual collection on this number."""
    import sys as _sys
    deepest = 0
    try:
        frames = _sys._current_frames()
    except Exception:
        return 0
    for _tid, top in list(frames.items()):
        depth = 0
        f = top
        # Cap the walk so a runaway chain can't make THIS function expensive.
        while f is not None and depth < 100_000:
            depth += 1
            f = f.f_back
        if depth > deepest:
            deepest = depth
    return deepest


def safe_manual_collect(
    *,
    max_frame_depth: int = 150,
    force: bool = False,
    log: Optional[Callable[[str], None]] = None,
) -> dict[str, Any]:
    """Run `gc.collect()` ONLY when no thread holds a Python frame chain deeper than
    `max_frame_depth`. If something is mid-deep-call (e.g. a timer storm, a deep render),
    defer — collecting then is what overflowed the C stack inside `mark_stacks`.

    Returns {collected, skipped, frame_depth, reason}. No-op on Python <3.14."""
    result: dict[str, Any] = {"collected": None, "skipped": False, "frame_depth": 0}
    if not (force or should_harden()):
        result["skipped"] = True
        result["reason"] = "python<3.14"
        return result
    import gc
    depth = max_thread_frame_depth()
    result["frame_depth"] = depth
    if depth > max_frame_depth:
        result["skipped"] = True
        result["reason"] = f"stack_too_deep:{depth}>{max_frame_depth}"
        if log:
            try:
                log(f"[gc_hardening] manual collect deferred — deepest frame chain {depth} > {max_frame_depth}")
            except Exception:
                pass
        return result
    try:
        result["collected"] = gc.collect()
        if log:
            try:
                log(f"[gc_hardening] manual collect ok — freed {result['collected']} (deepest chain {depth})")
            except Exception:
                pass
    except Exception as exc:
        result["reason"] = f"collect_failed:{type(exc).__name__}:{exc}"
    return result


__all__ = [
    "python_version_tuple",
    "should_harden",
    "harden_runtime_for_gc",
    "disable_auto_collection",
    "max_thread_frame_depth",
    "safe_manual_collect",
]
