#!/usr/bin/env python3
"""Early QtWebEngine bootstrap for the SIFTA Qt process.

QtWebEngine has a process-level rule: either import the WebEngine modules or
set AA_ShareOpenGLContexts before the first QCoreApplication/QApplication is
created. Alice Browser is usually loaded later from the MDI desktop, so the
desktop process must prime WebEngine at boot instead of letting the browser
widget discover it too late.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WebEngineBootstrapResult:
    available: bool
    error: str = ""


_BOOTSTRAP_RESULT: WebEngineBootstrapResult | None = None


def bootstrap_qt_webengine() -> WebEngineBootstrapResult:
    """Set WebEngine process attributes and import QtWebEngine once.

    The function is idempotent. Call it from `sifta_os_desktop.py` before
    `QApplication(...)`, and from browser widgets before they import
    QWebEngineView.
    """
    global _BOOTSTRAP_RESULT
    if _BOOTSTRAP_RESULT is not None:
        return _BOOTSTRAP_RESULT

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

        _BOOTSTRAP_RESULT = WebEngineBootstrapResult(True, "")
    except Exception as exc:
        _BOOTSTRAP_RESULT = WebEngineBootstrapResult(
            False,
            f"{type(exc).__name__}: {exc}",
        )
    return _BOOTSTRAP_RESULT


if __name__ == "__main__":
    result = bootstrap_qt_webengine()
    if result.available:
        print("QtWebEngine bootstrap: OK")
    else:
        print(f"QtWebEngine bootstrap: FAILED {result.error}")
