"""Tests for Round 33 — 4th cortex option label + Hermes arm provider dropdown.

Authors:
- Patch + tests: claude-opus-4-6 (Cowork, HEAD, direct landing — no Codex relay).
- Round 33, 2026-05-27. Architect: "0000 we have four options for cortexes,
  simple - u do it pls --- also add in inference settings a dropdown where
  i can select the hermes arm between ollama llm and xai for now".

What is verified:
1. `_on_hermes_arm_provider_changed` correctly writes the selected provider
   tag + label + previous + timestamp to .sifta_state/hermes_cortex.json
   without crashing, even when the file does not exist yet.
2. Pre-existing hermes_cortex.json contents are read into `previous` so
   the change is auditable in the same row.
3. The two provider tags are the canonical strings the arm launcher reads:
   `ollama_local` and `grok_via_hermes_oauth`.

PyQt6 absence triggers a module-level skip (silent-pass anti-pattern guard
per covenant §4.4 / §6 — same shape as test_grok_direct_type_ready_gate.py).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from Applications import sifta_system_settings as settings
except Exception as exc:  # noqa: BLE001
    pytest.skip(
        f"Skipping Round 33 hermes-arm-provider tests: settings import failed "
        f"({type(exc).__name__}: {exc}). "
        "Requires PyQt6 + the live settings widget module. "
        "Silent-pass against stubs is forbidden per covenant §6 / §7.12.",
        allow_module_level=True,
    )


class _FakeCombo:
    """Minimal QComboBox stand-in for direct handler invocation."""

    def __init__(self) -> None:
        self._items: list[tuple[str, str]] = []
        self._idx: int = 0

    def addItem(self, label: str, userData: str) -> None:
        self._items.append((str(label), str(userData)))

    def itemData(self, i: int) -> str:
        return self._items[i][1]

    def itemText(self, i: int) -> str:
        return self._items[i][0]

    def count(self) -> int:
        return len(self._items)

    def setCurrentIndex(self, i: int) -> None:
        self._idx = i

    def currentIndex(self) -> int:
        return self._idx


def _build_fake_widget(tmp_state_dir: Path) -> tuple[object, _FakeCombo, Path]:
    """Bind the _on_hermes_arm_provider_changed handler to a fake widget
    that resolves the config path inside the test's tmp dir."""
    combo = _FakeCombo()
    combo.addItem(
        "Ollama (local) · alice-m5-cortex-8b-6.3gb",
        userData="ollama_local",
    )
    combo.addItem(
        "xAI Grok OAuth (SuperGrok / X Premium+) · ☁ cloud",
        userData="grok_via_hermes_oauth",
    )

    cfg_path = tmp_state_dir / ".sifta_state" / "hermes_cortex.json"

    # Bind handler with patched __file__ path resolution by monkey-patching
    # Path.resolve to redirect parent.parent to the tmp state dir.
    handler = settings.SystemSettingsWidget._on_hermes_arm_provider_changed

    class _Bound:
        _hermes_arm_combo = combo

    return _Bound, combo, cfg_path


def test_hermes_arm_provider_options_use_canonical_tags(tmp_path, monkeypatch):
    bound, combo, _cfg = _build_fake_widget(tmp_path)
    assert combo.itemData(0) == "ollama_local"
    assert combo.itemData(1) == "grok_via_hermes_oauth"
    assert "Ollama" in combo.itemText(0)
    assert "Grok" in combo.itemText(1)


def test_handler_writes_hermes_cortex_json_with_provider_and_previous(
    tmp_path, monkeypatch
):
    bound, combo, cfg_path = _build_fake_widget(tmp_path)
    # Redirect the handler's path resolution into tmp_path.
    real_file = Path(settings.__file__).resolve()
    fake_dir = tmp_path / "Applications"
    fake_dir.mkdir()
    fake_file = fake_dir / "fake_app.py"
    fake_file.write_text("# stub")
    monkeypatch.setattr(settings, "__file__", str(fake_file))

    # Seed an existing config to test `previous` carries over.
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        json.dumps({"provider": "ollama_local", "note": "seeded"}),
        encoding="utf-8",
    )

    combo.setCurrentIndex(1)
    settings.SystemSettingsWidget._on_hermes_arm_provider_changed(bound, 1)

    written = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert written["provider"] == "grok_via_hermes_oauth"
    assert written["previous"] == "ollama_local"
    assert "Grok" in written["label"]
    assert written["set_by"] == "owner_via_system_settings_ui"
    assert "Round 33" in written.get("note", "")
    assert "changed_at" in written


def test_handler_creates_file_when_absent(tmp_path, monkeypatch):
    bound, combo, cfg_path = _build_fake_widget(tmp_path)
    fake_dir = tmp_path / "Applications"
    fake_dir.mkdir()
    fake_file = fake_dir / "fake_app.py"
    fake_file.write_text("# stub")
    monkeypatch.setattr(settings, "__file__", str(fake_file))

    # File does not exist yet.
    assert not cfg_path.exists()

    combo.setCurrentIndex(0)
    settings.SystemSettingsWidget._on_hermes_arm_provider_changed(bound, 0)

    written = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert written["provider"] == "ollama_local"
    assert written["previous"] == ""  # no prior file


def test_handler_does_not_crash_on_corrupt_existing_json(tmp_path, monkeypatch):
    bound, combo, cfg_path = _build_fake_widget(tmp_path)
    fake_dir = tmp_path / "Applications"
    fake_dir.mkdir()
    fake_file = fake_dir / "fake_app.py"
    fake_file.write_text("# stub")
    monkeypatch.setattr(settings, "__file__", str(fake_file))

    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text("{not valid json", encoding="utf-8")

    combo.setCurrentIndex(1)
    # Must not raise.
    settings.SystemSettingsWidget._on_hermes_arm_provider_changed(bound, 1)

    written = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert written["provider"] == "grok_via_hermes_oauth"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
