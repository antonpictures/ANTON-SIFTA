"""Inference UI checks without booting sensors, network services or repair jobs."""
import io
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from Applications import sifta_system_settings as settings
from System import swarm_spinal_cord as spinal


@pytest.fixture
def surface(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(settings, "STATE", tmp_path)
    monkeypatch.setattr(settings, "resolve_ollama_model", lambda **kw: "test/local:latest")
    monkeypatch.setattr(settings, "list_available_cortexes_with_canonical_fallback",
                        lambda: ["test/local:latest", "missing:latest", "mimo:mimo-cli-default"])
    monkeypatch.setattr(settings.SystemSettingsWidget, "_refresh_cortex_auth_indicator", lambda self: None)
    monkeypatch.setattr(settings.SystemSettingsWidget, "closeEvent", lambda self, event: event.accept())
    monkeypatch.setattr(settings.SystemSettingsWidget, "_refresh_attached_llm_picker", lambda self: None)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: io.BytesIO(json.dumps({
        "models": [{"name": "test/local:latest", "size": 6_600_000_000}]
    }).encode()))
    monkeypatch.setattr(spinal, "spinal_cord_status", lambda **kw: {
        "last_cycle": {"status": "NO_PATCH", "ts": 1787648774}
    })
    # Bypass base-widget boot: this fixture tests only the actual Inference page.
    widget = settings.SystemSettingsWidget.__new__(settings.SystemSettingsWidget)
    QWidget.__init__(widget)
    layout = QVBoxLayout(widget)
    scroll = widget._inference_page()
    layout.addWidget(scroll)
    widget.resize(780, 580)
    widget.show()
    app.processEvents()
    yield widget, scroll, app
    widget._cortex_auth_timer.stop()
    widget.close()
    app.processEvents()


def test_verified_inventory_and_configured_routes_are_distinct(surface):
    widget, scroll, app = surface
    labels = "\n".join(label.text() for label in scroll.findChildren(QLabel))
    assert "1 installed model tags" in labels
    assert "NO_PATCH" in labels
    assert "No inference test performed" in labels
    assert "Training Corpus" not in labels
    assert not hasattr(widget, "_brain_diagram")
    combo = widget._cortex_combo
    assert "6.6 GB | test/local:latest" == combo.itemText(0)
    assert "not installed in Ollama" in combo.itemText(1)
    assert "cloud route / availability not tested" in combo.itemText(2)
    assert widget._inference_provider_details.isHidden()


@pytest.mark.parametrize("payload", [None, {"models": "bad"}, {}])
def test_failed_probe_never_claims_ollama_live(surface, monkeypatch, payload):
    widget, _, _ = surface
    def fetch(*args, **kwargs):
        if payload is None:
            raise OSError("offline")
        return io.BytesIO(json.dumps(payload).encode())
    monkeypatch.setattr("urllib.request.urlopen", fetch)
    widget._refresh_inference_facts()
    assert "unavailable" in widget._inference_runtime_status.text()
    assert "availability unknown" in widget._cortex_combo.itemText(0)


def test_refresh_does_not_switch_model_but_user_selection_does(surface, monkeypatch):
    widget, _, _ = surface
    calls = []
    monkeypatch.setattr(widget, "_persist_primary_cortex_selection",
                        lambda tag, **kw: calls.append(tag) or {"ok": True})
    widget._refresh_inference_facts()
    assert calls == []
    widget._cortex_combo.setCurrentIndex(2)
    assert calls == ["mimo:mimo-cli-default"]
    assert "new requests" in widget.inference_default_card.detail.text()


def test_all_five_owner_models_include_gb_even_when_discovery_only_lists_mimo(surface, monkeypatch):
    widget, scroll, app = surface
    models = {
        "dlasher/Muse-Glimmer-30B-GGUF:IQ4_NL": 16044054038,
        "satgeze/qwenpaw-9b-heretic-1m:latest": 10707765240,
        "ornith-1.5:9b": 6550813657,
        "baytout3/ultragemma4-12b-heretic-uncensored:Q8_0": 12828634760,
        "krishairnd/Gemma-4-Uncensored:latest": 6325657891,
    }
    longest = "baytout3/ultragemma4-12b-heretic-uncensored:Q8_0"
    monkeypatch.setattr(settings, "resolve_ollama_model", lambda **kw: longest)
    monkeypatch.setattr(settings, "list_available_cortexes_with_canonical_fallback",
                        lambda: ["mimo:mimo-cli-default"])
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: io.BytesIO(json.dumps({
        "models": [{"name": name, "size": size} for name, size in models.items()]
    }).encode()))
    widget._refresh_inference_facts()
    for tag, size in models.items():
        index = widget._cortex_combo.findData(tag)
        assert index >= 0
        assert widget._cortex_combo.itemText(index) == f"{size / 1e9:.1f} GB | {tag}"
    assert "12.8 GB on disk" in widget.inference_default_card.detail.text()
    widget.resize(520, 400)
    app.processEvents()
    assert scroll.horizontalScrollBar().maximum() == 0


@pytest.mark.parametrize("width,height", [(780, 580), (520, 400)])
def test_small_screen_scroll_and_no_horizontal_overflow(surface, width, height):
    widget, scroll, app = surface
    widget._inference_provider_details.show()
    widget.resize(width, height)
    app.processEvents()
    assert scroll.horizontalScrollBar().maximum() == 0
    assert scroll.widget().width() <= scroll.viewport().width()
    if height == 400:
        assert scroll.verticalScrollBar().maximum() > 0
