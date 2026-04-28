import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SIFTA_DISABLE_MESH", "1")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from System.sifta_base_widget import SiftaBaseWidget, _load_help_text


_app = QApplication.instance()
if _app is None:
    _app = QApplication(sys.argv)


def test_system_settings_help_entry_exists():
    help_text = _load_help_text("System Settings")

    assert "No help entry found" not in help_text
    assert help_text.startswith("### System Settings")
    assert "Advanced configuration belongs here" in help_text


class _NormalHarness(SiftaBaseWidget):
    APP_NAME = "Finance"

    def build_ui(self, layout):
        layout.addWidget(QLabel("finance body"))


class _WriterHarness(SiftaBaseWidget):
    APP_NAME = "Stigmergic Writer"

    def build_ui(self, layout):
        layout.addWidget(QLabel("writer body"))


def _chat_toggle_buttons(widget):
    return [
        button
        for button in widget.findChildren(QPushButton)
        if button.toolTip() == "Toggle Entity Chat"
    ]


def test_normal_apps_do_not_embed_alice_chat_panel(monkeypatch):
    monkeypatch.delenv("SIFTA_ENABLE_APP_LOCAL_CHAT", raising=False)
    widget = _NormalHarness()
    try:
        assert widget._gci_visible is False
        assert widget._splitter.count() == 1
        assert _chat_toggle_buttons(widget) == []
        # Legacy apps can still call _gci safely; it is a non-visual bridge.
        widget._gci.chat_display.append("ignored")
        widget._gci.set_app_context("state update")
    finally:
        widget.close()


def test_stigmergic_writer_keeps_shared_document_panel(monkeypatch):
    monkeypatch.delenv("SIFTA_ENABLE_APP_LOCAL_CHAT", raising=False)
    widget = _WriterHarness()
    try:
        assert widget._gci_visible is True
        assert widget._splitter.count() == 2
        assert len(_chat_toggle_buttons(widget)) == 1
    finally:
        widget.close()
