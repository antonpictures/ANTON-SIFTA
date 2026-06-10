#!/usr/bin/env python3
"""Early QtWebEngine bootstrap for the SIFTA Qt process.

QtWebEngine has a process-level rule: either import the WebEngine modules or
set AA_ShareOpenGLContexts before the first QCoreApplication/QApplication is
created. Alice Browser is usually loaded later from the MDI desktop, so the
desktop process must prime WebEngine at boot instead of letting the browser
widget discover it too late.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

# Chromium GPU pass-through (TASK 0, r779 GO).
# Must be set before QtWebEngineCore import / QApplication creation.
#
# r784 — BOOT CRASH FIX (George 2026-06-08 04:29): r779's "--use-gl=desktop"
# aborts the whole SIFTA OS at Alice Browser launch on macOS 26.5:
# "--use-gl=desktop is not supported with the current configuration." Apple
# dropped desktop OpenGL; Chromium on macOS renders through ANGLE-over-Metal.
# Forcing an unsupported GL value qFatals → zsh: abort. Fix: platform-aware.
# On macOS keep GPU on but DO NOT force a GL backend — Chromium auto-selects
# ANGLE/Metal (the working GPU path, and the one hardware H.264 decode will use
# once the codec build lands). On other platforms keep the desktop-GL behavior.
import sys as _sys
if _sys.platform == "darwin":
    _DEFAULT_CHROMIUM_GPU_FLAGS = (
        "--enable-gpu",
        # no --use-gl: default ANGLE/Metal on macOS, never the unsupported-value abort
    )
else:
    _DEFAULT_CHROMIUM_GPU_FLAGS = (
        "--enable-gpu",
        "--use-gl=desktop",
    )


@dataclass(frozen=True)
class WebEngineBootstrapResult:
    available: bool
    error: str = ""
    chromium_flags: str = ""


_BOOTSTRAP_RESULT: WebEngineBootstrapResult | None = None


def _merge_chromium_gpu_flags() -> str:
    """Append default GPU flags without clobbering owner overrides."""
    existing = (os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS") or "").strip()
    parts: list[str] = []
    seen: set[str] = set()
    for token in (existing.split() if existing else []) + list(_DEFAULT_CHROMIUM_GPU_FLAGS):
        if token and token not in seen:
            seen.add(token)
            parts.append(token)
    merged = " ".join(parts)
    if merged:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = merged
    for flag in _DEFAULT_CHROMIUM_GPU_FLAGS:
        if flag not in sys.argv:
            sys.argv.append(flag)
    return merged


def bootstrap_qt_webengine() -> WebEngineBootstrapResult:
    """Set WebEngine process attributes and import QtWebEngine once.

    The function is idempotent. Call it from `sifta_os_desktop.py` before
    `QApplication(...)`, and from browser widgets before they import
    QWebEngineView.
    """
    global _BOOTSTRAP_RESULT
    if _BOOTSTRAP_RESULT is not None:
        return _BOOTSTRAP_RESULT

    chromium_flags = _merge_chromium_gpu_flags()
    try:
        from PyQt6.QtCore import QCoreApplication, Qt

        if QCoreApplication.instance() is None:
            QCoreApplication.setAttribute(
                Qt.ApplicationAttribute.AA_ShareOpenGLContexts,
                True,
            )

        # Import both modules while the process is still legal for WebEngine.
        import PyQt6.QtWebEngineCore  # noqa: F401
        import PyQt6.QtWebEngineWidgets  # noqa: F401

        _BOOTSTRAP_RESULT = WebEngineBootstrapResult(True, "", chromium_flags)
    except Exception as exc:
        _BOOTSTRAP_RESULT = WebEngineBootstrapResult(
            False,
            f"{type(exc).__name__}: {exc}",
            chromium_flags,
        )
    return _BOOTSTRAP_RESULT


if __name__ == "__main__":
    result = bootstrap_qt_webengine()
    if result.available:
        print("QtWebEngine bootstrap: OK")
    else:
        print(f"QtWebEngine bootstrap: FAILED {result.error}")
