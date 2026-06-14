import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SIFTA_DISABLE_MESH", "1")

import pytest
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from System.sifta_base_widget import SiftaBaseWidget, _load_help_text


_app = QApplication.instance()
if _app is None:
    _app = QApplication(sys.argv)


@pytest.fixture(autouse=True)
def _isolate_writer_state(monkeypatch, tmp_path):
    """Writer widgets create/open documents during tests; route their journal rows to tmp."""
    import Applications.sifta_writer_widget as writer_mod

    monkeypatch.setattr(writer_mod, "STATE_DIR", tmp_path / ".sifta_state")


def test_system_settings_help_entry_exists():
    help_text = _load_help_text("System Settings")

    assert "No help entry found" not in help_text
    assert help_text.startswith("### System Settings")
    assert "Advanced configuration belongs here" in help_text


def test_finance_help_entry_and_widget_identity_match_manifest():
    from Applications.sifta_finance import FinanceDashboard

    assert FinanceDashboard.APP_NAME == "Finance"

    help_text = _load_help_text(FinanceDashboard.APP_NAME)
    assert "No help entry found" not in help_text
    assert help_text.startswith("### Finance")
    assert "no double-spend" in help_text
    assert "canonical STGM reserve" in help_text


def test_programs_menu_manifest_apps_have_help_sections():
    """Every non-retired, non-hidden manifest app with a widget_class must resolve APP_HELP.md."""
    repo = Path(__file__).resolve().parents[1]
    manifest = json.loads((repo / "Applications" / "apps_manifest.json").read_text(encoding="utf-8"))
    for name, dat in manifest.items():
        if str(name).startswith("_"):
            continue
        if dat.get("_retired") or dat.get("hidden") or dat.get("_hidden_from_launcher"):
            continue
        if not dat.get("widget_class"):
            continue
        body = _load_help_text(name)
        assert "No help entry found" not in body, f"missing APP_HELP section for {name!r}"


class _NormalLoop(SiftaBaseWidget):
    APP_NAME = "Finance"

    def build_ui(self, layout):
        layout.addWidget(QLabel("finance body"))


class _WriterLoop(SiftaBaseWidget):
    APP_NAME = "Stigmergic Writer"

    def build_ui(self, layout):
        layout.addWidget(QLabel("writer body"))


class _DisabledChatLoop(SiftaBaseWidget):
    APP_NAME = "Disabled Chat Loop"
    APP_LOCAL_CHAT_DISABLED = True

    def build_ui(self, layout):
        layout.addWidget(QLabel("disabled body"))


class _StickyOptInLoop(SiftaBaseWidget):
    APP_NAME = "Sticky Opt In"
    STICKY_GLOBAL_CHAT_ENABLED = True

    def build_ui(self, layout):
        layout.addWidget(QLabel("sticky body"))


def _chat_toggle_buttons(widget):
    return [
        button
        for button in widget.findChildren(QPushButton)
        if button.toolTip() == "Toggle Entity Chat"
    ]


def _sticky_toggle_buttons(widget):
    return [
        button
        for button in widget.findChildren(QPushButton)
        if button.toolTip() == "Toggle one global chat mirror"
    ]


def test_normal_apps_do_not_embed_alice_chat_panel(monkeypatch):
    monkeypatch.delenv("SIFTA_ENABLE_APP_LOCAL_CHAT", raising=False)
    monkeypatch.delenv("SIFTA_STICKY_GLOBAL_CHAT", raising=False)
    widget = _NormalLoop()
    try:
        assert widget._gci_visible is False
        assert widget._splitter.count() == 1
        assert _chat_toggle_buttons(widget) == []
        assert _sticky_toggle_buttons(widget) == []
        assert widget._sticky_global_chat_visible is False
        # Legacy apps can still call _gci safely; it is a non-visual bridge.
        widget._gci.chat_display.append("ignored")
        widget._gci.set_app_context("state update")
    finally:
        widget.close()


def test_sticky_global_chat_mirror_is_opt_in_by_class(monkeypatch):
    monkeypatch.delenv("SIFTA_STICKY_GLOBAL_CHAT", raising=False)
    widget = _StickyOptInLoop()
    try:
        assert widget._gci_visible is False
        assert widget._splitter.count() == 2
        assert len(_sticky_toggle_buttons(widget)) == 1
        assert widget._sticky_global_chat_visible is True
    finally:
        widget.close()


def test_sticky_global_chat_mirror_can_be_forced_by_env(monkeypatch):
    monkeypatch.setenv("SIFTA_STICKY_GLOBAL_CHAT", "1")
    widget = _NormalLoop()
    try:
        assert widget._gci_visible is False
        assert widget._splitter.count() == 2
        assert len(_sticky_toggle_buttons(widget)) == 1
        assert widget._sticky_global_chat_visible is True
    finally:
        widget.close()


def test_stigmergic_writer_uses_simple_page_without_app_local_chat(monkeypatch):
    monkeypatch.delenv("SIFTA_ENABLE_APP_LOCAL_CHAT", raising=False)
    widget = _WriterLoop()
    try:
        assert widget._gci_visible is False
        assert widget._splitter.count() == 1
        assert _chat_toggle_buttons(widget) == []
        widget._gci.chat_display.append("ignored")
        widget._gci.set_app_context("inline writer update")
    finally:
        widget.close()


def test_stigmergic_writer_name_overrides_chat_environment(monkeypatch):
    monkeypatch.setenv("SIFTA_ENABLE_APP_LOCAL_CHAT", "1")
    widget = _WriterLoop()
    try:
        assert widget._gci_visible is False
        assert widget._splitter.count() == 1
        assert _chat_toggle_buttons(widget) == []
    finally:
        widget.close()


def test_actual_stigmergic_writer_declares_inline_page_mode():
    from Applications.sifta_writer_widget import WriterWidget

    assert WriterWidget.APP_LOCAL_CHAT_DISABLED is True


def test_actual_stigmergic_writer_is_one_page_even_when_env_requests_chat(monkeypatch):
    from Applications.sifta_writer_widget import WriterWidget

    monkeypatch.setenv("SIFTA_ENABLE_APP_LOCAL_CHAT", "1")
    widget = WriterWidget()
    try:
        assert widget._gci_visible is False
        assert widget._splitter.count() == 1
        assert _chat_toggle_buttons(widget) == []
        assert hasattr(widget, "editor")
    finally:
        widget.close()


def test_stigmergic_writer_appends_alice_in_same_page(monkeypatch):
    from Applications.sifta_writer_widget import WriterWidget

    monkeypatch.setenv("SIFTA_ENABLE_APP_LOCAL_CHAT", "1")
    widget = WriterWidget()
    try:
        widget.editor.setPlainText("---\nHi Alice, can you see what I type?")
        widget._on_ghost_ready("[ALICE_M5] Yes. I am reading this shared page.")
        text = widget.editor.toPlainText()

        assert widget._gci_visible is False
        assert widget._splitter.count() == 1
        assert "\n\nAlice\nYes. I am reading this shared page.\n\n---\n" in text
        assert "[ALICE_M5]" not in text
    finally:
        widget.close()


def test_stigmergic_writer_cleans_alice_labels():
    from Applications.sifta_writer_widget import WriterWidget

    assert WriterWidget._clean_alice_continuation("Alice: I can continue.") == "I can continue."
    assert WriterWidget._clean_alice_continuation("[ALICE_M5] I can continue.") == "I can continue."


def test_stigmergic_writer_seed_is_clean_and_owner_variable(monkeypatch):
    import Applications.sifta_writer_widget as writer_mod

    monkeypatch.setattr(writer_mod, "owner_display_name", lambda default="Architect": "Layer One Owner")

    seed = writer_mod._seed_from_context()

    assert "# Document — Layer One Owner" in seed
    assert "Recent Swarm Activity" not in seed
    assert "INFERENCE_BORROW" not in seed
    assert seed.rstrip().endswith("---")


def test_stigmergic_writer_journals_document_open_event(monkeypatch, tmp_path):
    import Applications.sifta_writer_widget as writer_mod

    state = tmp_path / ".sifta_state"
    monkeypatch.setattr(writer_mod, "STATE_DIR", state)
    monkeypatch.setattr(writer_mod, "owner_display_name", lambda default="Architect": "George")
    doc = tmp_path / "05 14 26 10-55AM.sifta.md"
    doc.write_text("# Document — George\n\n---\n", encoding="utf-8")

    writer_mod._log_territory(doc, "BOOT_SAVE", 4)

    first_person = json.loads((state / "alice_first_person_journal.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    daily_rows = (state / "alice_journal" / f"{first_person['date']}.jsonl").read_text(encoding="utf-8").splitlines()
    daily_row = json.loads(daily_rows[-1])
    receipts = (state / "writer_document_receipts.jsonl").read_text(encoding="utf-8")

    assert "George" in first_person["line"]
    assert "start Stigmergic Writer" in first_person["line"]
    assert first_person["document_name"] == doc.name
    assert first_person["source"] == "stigmergic_writer"
    assert daily_row["entry"] == first_person["line"]
    assert str(doc) in json.loads(receipts.splitlines()[-1])["evidence"]["document_path"]


def test_stigmergic_writer_idle_starts_alice_continuation_worker(monkeypatch, tmp_path):
    import Applications.sifta_writer_widget as writer_mod
    from Applications.sifta_writer_widget import WriterWidget

    class FakeSignal:
        def __init__(self):
            self.callbacks = []

        def connect(self, callback):
            self.callbacks.append(callback)

    class FakeGhostWorker:
        def __init__(self, context):
            self.context = context
            self.ghost_ready = FakeSignal()
            self.error = FakeSignal()
            self.started = False

        def isRunning(self):
            return False

        def start(self):
            self.started = True

    monkeypatch.setattr(writer_mod, "DOCS_DIR", tmp_path)
    monkeypatch.setattr(writer_mod, "GhostWorker", FakeGhostWorker)

    widget = WriterWidget()
    try:
        widget.editor.setPlainText("Hi Alice, can you see what I type in this saved page?")
        widget._on_idle()

        assert isinstance(widget.ghost_worker, FakeGhostWorker)
        assert widget.ghost_worker.started is True
        assert widget.ghost_worker.ghost_ready.callbacks == [widget._on_ghost_ready]
        assert widget.ghost_worker.error.callbacks == [widget._on_ghost_error]
        assert widget._status.text() == "Alice is typing in this page..."
    finally:
        widget.close()


def test_stigmergic_writer_memory_query_uses_saved_docs_before_worker(monkeypatch, tmp_path):
    import Applications.sifta_writer_widget as writer_mod
    from Applications.sifta_writer_widget import WriterWidget

    class ExplodingGhostWorker:
        def __init__(self, context):
            raise AssertionError("memory query should not start GhostWorker")

    docs = tmp_path / ".sifta_documents"
    docs.mkdir()
    (docs / "05 14 26 10-55AM.sifta.md").write_text(
        "# Document - Ioan George Anton\n"
        "*May 14, 2026 at 10:55 AM*\n\n"
        "---\nHahaha Alice, you responded, this is the first app we created together.\n",
        encoding="utf-8",
    )
    state = tmp_path / ".sifta_state"
    monkeypatch.setattr(writer_mod, "DOCS_DIR", docs)
    monkeypatch.setattr(writer_mod, "STATE_DIR", state)
    monkeypatch.setattr(writer_mod, "GhostWorker", ExplodingGhostWorker)

    widget = WriterWidget()
    try:
        widget.editor.setPlainText(
            "# Document - George\n"
            "*May 14, 2026 at 11:03 AM*\n\n"
            "---\nWhat did we talk about?"
        )
        widget._on_idle()
        text = widget.editor.toPlainText()

        assert "\n\nAlice\nI checked 2 saved Writer document" in text
        assert "05 14 26 10-55AM.sifta.md" in text
        assert "first app we created together" in text
        assert "Receipt: writer_memory_reader:" in text
        assert (state / "writer_memory_reader_receipts.jsonl").exists()
    finally:
        widget.close()


def test_stigmergic_writer_surfaces_worker_error(monkeypatch, tmp_path):
    import Applications.sifta_writer_widget as writer_mod
    from Applications.sifta_writer_widget import WriterWidget

    monkeypatch.setattr(writer_mod, "DOCS_DIR", tmp_path)
    widget = WriterWidget()
    try:
        widget._on_ghost_error("model offline")
        assert "Alice continuation failed: model offline" == widget._status.text()
    finally:
        widget.close()


def test_stigmergic_writer_direct_alice_fallback_reply():
    from Applications.sifta_writer_widget import GhostWorker

    assert GhostWorker.fallback_reply("---\nHi Alice") == "Yes. I am here with you in this saved page."
    assert GhostWorker.fallback_reply("---\nI am writing a paragraph without direct address.") == ""


def test_stigmergic_writer_empty_model_response_uses_direct_alice_fallback(monkeypatch):
    import Applications.sifta_writer_widget as writer_mod
    from Applications.sifta_writer_widget import GhostWorker
    from System import inference_router

    class EmptyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"response": ""}'

    monkeypatch.setattr(inference_router, "route_inference", lambda *args, **kwargs: "")
    monkeypatch.setattr(writer_mod.urllib.request, "urlopen", lambda *args, **kwargs: EmptyResponse())

    replies = []
    errors = []
    worker = GhostWorker("---\nHi Alice", model="local-test")
    worker.ghost_ready.connect(replies.append)
    worker.error.connect(errors.append)
    worker.run()

    assert replies == ["Yes. I am here with you in this saved page."]
    assert errors == []


def test_stigmergic_writer_boot_saves_timestamped_file_and_toolbar_is_simple(monkeypatch, tmp_path):
    import Applications.sifta_writer_widget as writer_mod
    from Applications.sifta_writer_widget import WriterWidget

    monkeypatch.setattr(writer_mod, "DOCS_DIR", tmp_path)
    widget = WriterWidget()
    try:
        buttons = {button.text() for button in widget.findChildren(QPushButton)}

        assert "Open" in buttons
        assert "Export PDF" in buttons
        assert "Save" not in buttons
        assert "✦ Ask Swarm" not in buttons
        assert widget.current_file is not None
        assert widget.current_file.exists()
        assert widget.current_file.parent == tmp_path
        assert widget.current_file.name.endswith(".sifta.md")
        assert widget.path_label.text() == widget.current_file.name
        assert widget.path_label.text() != "Untitled"
        assert widget.current_file.read_text(encoding="utf-8") == widget.editor.toPlainText()
    finally:
        widget.close()


def test_stigmergic_writer_autosaves_edits(monkeypatch, tmp_path):
    import Applications.sifta_writer_widget as writer_mod
    from Applications.sifta_writer_widget import WriterWidget

    monkeypatch.setattr(writer_mod, "DOCS_DIR", tmp_path)
    widget = WriterWidget()
    try:
        assert widget.current_file is not None
        widget.editor.setPlainText("Alice shared document autosave check.")
        widget._autosave_doc()

        assert widget.current_file.read_text(encoding="utf-8") == "Alice shared document autosave check."
        assert widget.path_label.text() == widget.current_file.name
    finally:
        widget.close()


def test_stigmergic_writer_unique_path_preserves_sifta_markdown_suffix(tmp_path):
    from Applications.sifta_writer_widget import WriterWidget

    first = tmp_path / "05 14 26 10-30AM.sifta.md"
    first.write_text("old", encoding="utf-8")

    assert WriterWidget._unique_path(first).name == "05 14 26 10-30AM 2.sifta.md"


def test_app_local_chat_disabled_overrides_environment(monkeypatch):
    monkeypatch.setenv("SIFTA_ENABLE_APP_LOCAL_CHAT", "1")
    widget = _DisabledChatLoop()
    try:
        assert widget._gci_visible is False
        assert widget._splitter.count() == 1
        assert _chat_toggle_buttons(widget) == []
    finally:
        widget.close()


def test_make_timer_contains_python_exceptions(monkeypatch):
    monkeypatch.delenv("SIFTA_ENABLE_APP_LOCAL_CHAT", raising=False)
    widget = _NormalLoop()
    calls = []

    def bad_callback():
        calls.append("called")
        raise RuntimeError("timer boom")

    try:
        timer = widget.make_timer(999_999, bad_callback)
        timer.stop()
        timer.timeout.emit()
        assert calls == ["called"]
    finally:
        widget.close()
