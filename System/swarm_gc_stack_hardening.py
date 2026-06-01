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


__all__ = ["python_version_tuple", "should_harden", "harden_runtime_for_gc"]
