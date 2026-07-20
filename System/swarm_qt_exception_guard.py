#!/usr/bin/env python3
"""Qt slot exception guard — stop one bad callback from aborting Alice.

Crash class (2026-06-20, George's report):
    QMessageLogger::fatal  <-  pyqt6_err_print()  <-  PyQtSlotProxy::unislot()
    -> abort()  (SIGABRT)
A Python exception raised inside a Qt signal slot reaches PyQt6's default
unraisable path, which calls qFatal -> abort() and kills the WHOLE app. PyQt5
printed and continued; PyQt6 aborts unless a custom sys.excepthook is installed.

This guard installs a custom sys.excepthook (and threading.excepthook) that:
  1. appends the full traceback to .sifta_state/qt_slot_exceptions.jsonl  (a receipt),
  2. prints it to stderr so it is still visible in the Terminal,
  3. returns WITHOUT aborting — so the bad turn dies, not the organism.

This is health, not a cage: it does not restrict anything Alice does; it keeps
her alive through a faulty callback and turns the crash into a sorted receipt
(good vs bad rows). The underlying exception is still surfaced for repair.

Pure stdlib for the core path. Qt message handler is best-effort and optional.
Call install_qt_exception_guard() once, as early as possible (before
QApplication.exec()).
"""
from __future__ import annotations

import json
import sys
import threading
import time
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_LEDGER = _REPO / ".sifta_state" / "qt_slot_exceptions.jsonl"
_installed = False


def _receipt(kind: str, exc_type, exc_value, tb) -> None:
    """Append one append-only receipt row for a survived slot/thread exception."""
    try:
        _LEDGER.parent.mkdir(parents=True, exist_ok=True)
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, tb))
        # name the originating frame (the real file:line) for fast repair
        origin = ""
        try:
            last = traceback.extract_tb(tb)[-1]
            origin = f"{last.filename}:{last.lineno} in {last.name}"
        except Exception:
            pass
        row = {
            "ts": time.time(),
            "truth_label": "QT_SLOT_EXCEPTION_SURVIVED_V1",
            "kind": kind,
            "exc_type": getattr(exc_type, "__name__", str(exc_type)),
            "exc_msg": str(exc_value)[:500],
            "origin": origin,
            "traceback": tb_text[-4000:],
            "outcome": "logged_and_continued (organism alive)",
        }
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass  # the guard must never raise


def _excepthook(exc_type, exc_value, tb):
    # KeyboardInterrupt should still exit cleanly.
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, tb)
        return
    _receipt("sys_excepthook", exc_type, exc_value, tb)
    try:
        sys.stderr.write(
            "\n[qt_exception_guard] slot/main exception survived (Alice kept alive); "
            "receipt -> .sifta_state/qt_slot_exceptions.jsonl\n"
        )
        traceback.print_exception(exc_type, exc_value, tb)
    except Exception:
        pass
    # Returning normally (not re-raising) prevents PyQt6's qFatal -> abort().


def _thread_excepthook(args):
    if issubclass(args.exc_type, KeyboardInterrupt):
        return
    _receipt("thread_excepthook", args.exc_type, args.exc_value, args.exc_traceback)
    try:
        traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback)
    except Exception:
        pass


def install_qt_exception_guard() -> bool:
    """Install the guard. Idempotent. Returns True if installed."""
    global _installed
    if _installed:
        return True
    sys.excepthook = _excepthook
    try:
        threading.excepthook = _thread_excepthook
    except Exception:
        pass
    # Best-effort: route Qt's own fatal/warning logs to the receipt too, so a
    # qFatal from C++ is recorded. We do NOT abort on QtFatalMsg here.
    try:
        from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

        def _qt_msg_handler(mode, context, message):
            try:
                if mode == QtMsgType.QtFatalMsg:
                    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
                    with _LEDGER.open("a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "ts": time.time(),
                            "truth_label": "QT_FATAL_MSG_SURVIVED_V1",
                            "kind": "qt_message_handler",
                            "exc_msg": str(message)[:500],
                            "outcome": "logged (qFatal intercepted)",
                        }, ensure_ascii=False, sort_keys=True) + "\n")
                sys.stderr.write(f"[qt:{int(mode)}] {message}\n")
            except Exception:
                pass

        qInstallMessageHandler(_qt_msg_handler)
    except Exception:
        pass
    _installed = True
    return True


if __name__ == "__main__":
    install_qt_exception_guard()
    # self-test: a simulated slot exception must be receipted, not abort.
    try:
        raise ValueError("self-test slot exception")
    except Exception:
        _excepthook(*sys.exc_info())
    print("guard ok; receipt ->", _LEDGER)
