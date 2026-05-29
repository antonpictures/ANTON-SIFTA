"""Round 93 tests — body writer tick runs off the main thread.

After Round 91 added the heavy SwarmPhysiology body_brain_tick producer
(~5s per cycle), the Round 85 QTimer was running tick_writer_organs
synchronously on the Qt main thread, beachballing the UI for ~7s every
tick. Round 93 moves the tick onto a daemon thread and reschedules the
next tick from the main thread immediately.

PyQt6 is not in the Linux sandbox; tests verify the wiring by static
source inspection.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


WIDGET = Path(__file__).resolve().parents[1] / "Applications" / "sifta_talk_to_alice_widget.py"


def _src() -> str:
    return WIDGET.read_text(encoding="utf-8")


def test_widget_still_parses_after_threading_fix():
    """A multi-line replacement on a 22k-line file must not break syntax."""
    try:
        ast.parse(_src())
    except SyntaxError as exc:
        pytest.fail(f"widget no longer parses: {exc}")


def test_body_writer_tick_uses_threading():
    """The fix must spawn a daemon Thread named 'body_writer_tick'."""
    src = _src()
    # Isolate the _body_writer_tick method block (Python doesn't use braces,
    # so split between method defs instead of regex over the whole file).
    block_match = re.search(
        r"def _body_writer_tick\(self\) -> None:(.*?)def _start_listener",
        src, re.DOTALL,
    )
    assert block_match is not None, "could not locate _body_writer_tick block"
    block = block_match.group(1)
    # Both signals of the fix must be inside the method block.
    assert "threading.Thread(" in block, "thread spawn missing from _body_writer_tick"
    assert "daemon=True" in block, "daemon flag missing"
    assert 'name="body_writer_tick"' in block, "thread name missing"


def test_body_writer_tick_calls_tick_writer_organs_inside_worker():
    """tick_writer_organs must be called from the worker, NOT from the
    main thread directly."""
    src = _src()
    # Locate the _body_writer_tick block
    block_match = re.search(
        r"def _body_writer_tick\(self\) -> None:(.*?)def _start_listener",
        src, re.DOTALL,
    )
    assert block_match, "could not locate _body_writer_tick block"
    block = block_match.group(1)
    # tick_writer_organs must appear AFTER a `def _worker()` declaration
    worker_pos = block.find("def _worker")
    call_pos = block.find("tick_writer_organs(")
    assert worker_pos != -1, "expected nested _worker() function"
    assert call_pos != -1, "expected tick_writer_organs call"
    assert call_pos > worker_pos, (
        "tick_writer_organs must be inside the _worker, not on the main thread"
    )


def test_in_flight_guard_present():
    """Without an in-flight guard, slow ticks would queue up workers
    indefinitely if the schedule fires faster than the body_brain_loop."""
    src = _src()
    assert "_body_writer_tick_in_flight" in src, (
        "in-flight guard attribute missing — workers could stack up"
    )


def test_reschedule_happens_outside_worker_too():
    """The next tick MUST be scheduled from the main thread regardless of
    how long the worker takes — otherwise the cadence breaks if a worker
    crashes or hangs."""
    src = _src()
    block_match = re.search(
        r"def _body_writer_tick\(self\) -> None:(.*?)def _start_listener",
        src, re.DOTALL,
    )
    assert block_match
    block = block_match.group(1)
    # Main-thread reschedule must be after the thread.start() line, not
    # buried in the worker function.
    start_pos = block.find(".start()")
    assert start_pos != -1, "thread must be started"
    after_start = block[start_pos:]
    assert "_schedule_body_writer_tick" in after_start, (
        "next tick must be scheduled from the main thread after thread.start()"
    )


def test_no_synchronous_tick_writer_organs_in_main_path():
    """The old synchronous call shape MUST be gone — that's the beachball
    root cause."""
    src = _src()
    # Find the _body_writer_tick block
    block_match = re.search(
        r"def _body_writer_tick\(self\) -> None:(.*?)def _start_listener",
        src, re.DOTALL,
    )
    assert block_match
    block = block_match.group(1)
    # tick_writer_organs must not appear OUTSIDE the worker (i.e. directly
    # inside the method body before _worker is defined).
    pre_worker = block.split("def _worker", 1)[0]
    assert "tick_writer_organs(" not in pre_worker, (
        "synchronous tick_writer_organs call still on main thread — beachball "
        "regression"
    )
