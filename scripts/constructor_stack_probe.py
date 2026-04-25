#!/usr/bin/env python3
"""
Offscreen SiftaDesktop constructor probe: separate import time vs. __init__, and
dump Python stacks on demand while the process is hung.

Why this exists
  A probe that only prints *after* ``SiftaDesktop()`` can look like a hang
  before "the first print" if the process blocks during ``import sifta_os_desktop``
  or very early in ``__init__``.

Usage
  From repo root::

    QT_QPA_PLATFORM=offscreen \\
    SIFTA_DISABLE_MESH=1 \\
    SIFTA_DESKTOP_SKIP_WM_AUTOSTART=1 \\
    SIFTA_DESKTOP_INIT_TRACE=1 \\
    python3 scripts/constructor_stack_probe.py

  While it appears stuck, in another terminal::

    kill -USR1 <pid from stderr>

  Python writes all thread stacks to stderr (requires faulthandler + SIGUSR1).

  To force a wall-clock dump after N seconds without blocking the main thread::

    SIFTA_CONSTRUCTOR_DUMP_AFTER_S=5 python3 scripts/constructor_stack_probe.py

  If you pipe through ``| tee`` / ``| head``, set unbuffered I/O or the first
  log line can appear *after* a long block (looks like a hang before any print)::

    PYTHONUNBUFFERED=1 python3 -u scripts/constructor_stack_probe.py 2>&1 | tee /tmp/probe.log

  Interpreter-level faulthandler (belt-and-suspenders)::

    python3 -X faulthandler -u scripts/constructor_stack_probe.py
"""

from __future__ import annotations

import os

# Pipes use block-buffered stdio; set before other imports for pipeline visibility.
os.environ.setdefault("PYTHONUNBUFFERED", "1")

# One byte write to real fd=2: survives stdio block-buffering when stdout/stderr are pipes.
os.write(2, b"[probe] alive after import os (if no line, hang is before this)\n")

import faulthandler
import signal
import sys
import threading
import time
from pathlib import Path


def _raw_stderr_line(msg: str) -> None:
    """Unbuffered one line to fd 2 (visible even if Python's stderr is line-buffered to a pipe)."""
    try:
        os.write(2, (msg if msg.endswith("\n") else msg + "\n").encode("utf-8", errors="replace"))
    except Exception:
        pass

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# Defaults that reduce headless / CI hangs (align with scripts/smoke_test_desktop.py).
os.environ.setdefault("SIFTA_DISABLE_MESH", "1")
os.environ.setdefault("SIFTA_DESKTOP_SKIP_WM_AUTOSTART", "1")
os.environ.setdefault("SIFTA_DESKTOP_INIT_TRACE", "1")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

faulthandler.enable(all_threads=True)
if hasattr(signal, "SIGUSR1"):
    faulthandler.register(signal.SIGUSR1, all_threads=True)

_raw_stderr_line(f"[probe] module loaded pid={os.getpid()} (use kill -USR1 {os.getpid()} for Python stacks)")


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _maybe_timer_dump() -> None:
    s = os.environ.get("SIFTA_CONSTRUCTOR_DUMP_AFTER_S", "").strip()
    if not s:
        return
    try:
        delay = float(s)
    except ValueError:
        return
    if delay <= 0:
        return

    def _run() -> None:
        time.sleep(delay)
        _log(
            f"[probe] SIFTA_CONSTRUCTOR_DUMP_AFTER_S={delay!r} "
            f"— dumping all thread stacks"
        )
        faulthandler.dump_traceback(file=sys.stderr, all_threads=True)

    threading.Thread(target=_run, name="stack-dump-timer", daemon=True).start()


def main() -> int:
    # Timer first: if a later step blocks, the dump can still fire.
    _maybe_timer_dump()

    _raw_stderr_line(f"[probe] main() start python={sys.executable!s}")
    _log(f"[probe] python={sys.executable} pid={os.getpid()}")
    _log(
        "[probe] Send SIGUSR1 to this pid to dump all Python stacks; "
        "or set SIFTA_CONSTRUCTOR_DUMP_AFTER_S=5 for an automatic dump."
    )

    _log("[probe] step: PyQt6.QtWidgets QApplication import")
    from PyQt6.QtWidgets import QApplication  # noqa: WPS433

    _log("[probe] step: QApplication()")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    _log("[probe] step: import sifta_os_desktop (import-time cost only)")
    import sifta_os_desktop  # noqa: F401, WPS433  # type: ignore

    _log("[probe] step: SiftaDesktop() — watch [SiftaDesktop.__init__] lines on stderr")
    from sifta_os_desktop import SiftaDesktop  # noqa: WPS433

    w = SiftaDesktop()
    w.hide()
    w.close()
    app.quit()
    _log("[probe] done (clean)")
    return 0


if __name__ == "__main__":
    # Earliest line that runs in the process image after imports (stderr file object may still buffer in pipes).
    _raw_stderr_line(f"[probe] __main__ entry pid={os.getpid()}")
    raise SystemExit(main())
