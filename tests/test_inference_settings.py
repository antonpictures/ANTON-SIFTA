from __future__ import annotations

import os
from typing import Any
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SIFTA_DISABLE_MESH", "1")

REPO = Path(__file__).resolve().parent.parent


def test_ollama_weight_labels_require_exact_model_tags():
    from Applications.sifta_system_settings import _format_ollama_weight_label

    weights = {
        "alice-Q-m1-scout-2.3b-2.7gb:latest": 2_740_000_000,
        "sifta-classifier-c1-3.1b-6.2gb:latest": 6_180_000_000,
        "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest": 4_400_000_000,
        "alice-m5-cortex-8b-6.3gb:latest": 6_300_000_000,
        "alice-extra-cortex-25.8b-17gb:latest": 17_000_000_000,
    }

    assert _format_ollama_weight_label("alice-Q-m1-scout-2.3b-2.7gb:latest", weights) == "⚖ 2.74 GB"
    assert _format_ollama_weight_label("sifta-classifier-c1-3.1b-6.2gb:latest", weights) == "⚖ 6.18 GB"
    assert _format_ollama_weight_label("alice-gemma4-e2b-cortex-5.1b-4.4gb:latest", weights) == "⚖ 4.40 GB"
    assert _format_ollama_weight_label("alice-m5-cortex-8b-6.3gb:latest", weights) == "⚖ 6.30 GB"
    assert _format_ollama_weight_label("alice-extra-cortex-25.8b-17gb:latest", weights) == "⚖ 17.00 GB"
    assert _format_ollama_weight_label("qwen3.5:4b", weights) == "not installed"
    assert _format_ollama_weight_label("qwen3.5:9b", weights) == "not installed"


def test_inference_defaults_persist_global_and_app_models(tmp_path, monkeypatch):
    from System import sifta_inference_defaults as defaults

    monkeypatch.setattr(defaults, "_STATE", tmp_path)
    monkeypatch.setattr(defaults, "_ASSIGNMENTS", tmp_path / "swimmer_ollama_assignments.json")

    assert defaults.set_default_ollama_model("gemma4-phc:latest") == "gemma4-phc:latest"
    assert defaults.set_app_ollama_model("talk_to_alice", "alice-phc-cure") == "alice-phc-cure"

    assert defaults.get_default_ollama_model() == "gemma4-phc:latest"
    assert defaults.resolve_ollama_model(app_context="talk_to_alice") == "alice-phc-cure"


def test_talk_to_alice_demoted_small_gemma_pin_normalizes_to_m5(tmp_path, monkeypatch):
    from System import sifta_inference_defaults as defaults

    monkeypatch.setattr(defaults, "_STATE", tmp_path)
    monkeypatch.setattr(defaults, "_ASSIGNMENTS", tmp_path / "swimmer_ollama_assignments.json")

    defaults.set_default_ollama_model(defaults.CANONICAL_OLLAMA_GEMMA4_SMALL)
    defaults.set_app_ollama_model("talk_to_alice", defaults.CANONICAL_OLLAMA_GEMMA4_SMALL)

    assert (
        defaults.resolve_ollama_model(
            app_context="talk_to_alice",
            query_text="I am watching your Alice Browser organ now your body",
        )
        == defaults.CANONICAL_OLLAMA_DAILY
    )
    assert (
        defaults.normalize_talk_to_alice_model(defaults.CANONICAL_OLLAMA_GEMMA4_SMALL)
        == defaults.CANONICAL_OLLAMA_DAILY
    )


def test_inference_stigmergic_router_selects_and_learns(tmp_path, monkeypatch):
    from System import sifta_inference_defaults as defaults
    import json as _json

    monkeypatch.setattr(defaults, "_STATE", tmp_path)
    monkeypatch.setattr(defaults, "_ASSIGNMENTS", tmp_path / "swimmer_ollama_assignments.json")
    monkeypatch.setattr(defaults, "_CORTEX_FIELD_PATH", tmp_path / "cortex_route_field.json")
    monkeypatch.setattr(defaults, "_CORTEX_ROUTING_LEDGER", tmp_path / "cortex_route_receipts.jsonl")

    # Architect 2026-05-15: resolve_ollama_model honors per_app pins BEFORE the
    # stigmergic router (so the cortex picker UI is not overridden). To exercise
    # the stigmergic router itself, clear the talk_to_alice pin from the
    # template assignments so the router has to decide.
    defaults.persist_default_assignments_template()
    raw = _json.loads(defaults._ASSIGNMENTS.read_text(encoding="utf-8"))
    raw.setdefault("per_app", {}).pop("talk_to_alice", None)
    defaults._ASSIGNMENTS.write_text(_json.dumps(raw), encoding="utf-8")

    # For code/debug queries the router now stays inside the two local Gemma4
    # student cortexes unless the owner explicitly selects a cloud teacher.
    # The retired 17GB cortex must not be auto-selected on a 24GB body.
    initial_pick = defaults.resolve_ollama_model(
        app_context="talk_to_alice",
        query_text="debug the kernel router and run pytest",
    )
    assert initial_pick == defaults.CANONICAL_OLLAMA_DAILY

    bucket = defaults.classify_inference_query_bucket(
        "debug the kernel router and run pytest",
        app_context="talk_to_alice",
    )
    defaults.deposit_cortex_route_trace(
        bucket,
        initial_pick,
        success=False,
        amount=20.0,
        reason="test_regression",
    )
    after_failure = defaults.resolve_ollama_model(
        app_context="talk_to_alice",
        query_text="debug the kernel router and run pytest",
    )

    assert after_failure == defaults.CANONICAL_OLLAMA_DAILY
    assert defaults._CORTEX_ROUTING_LEDGER.exists()


def test_inference_defaults_policy_matches_executable_default(monkeypatch):
    monkeypatch.delenv("SIFTA_DEFAULT_OLLAMA_MODEL", raising=False)

    from System import sifta_inference_defaults as defaults

    assert defaults.CANONICAL_OLLAMA_DAILY == "alice-m5-cortex-8b-6.3gb:latest"
    assert defaults.CANONICAL_OLLAMA_DEFAULT == "alice-m5-cortex-8b-6.3gb:latest"
    assert defaults.CANONICAL_OLLAMA_GEMMA4_SMALL == "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"
    assert defaults.CANONICAL_OLLAMA_M5_FALLBACK == "alice-m5-cortex-8b-6.3gb:latest"
    assert defaults.CANONICAL_OLLAMA_EXTRA == "alice-extra-cortex-25.8b-17gb:latest"
    assert defaults.CANONICAL_CLOUD_GROK == "grok:grok-4.3"
    assert defaults.CANONICAL_CLOUD_CLAUDE == "claude:claude-code-cli-default"
    assert defaults.CANONICAL_CLOUD_CODEX == "codex:gpt-5.5"
    assert defaults.CANONICAL_CLOUD_QWEN == "qwen:accounts/fireworks/models/gpt-oss-20b"
    assert (
        defaults.CANONICAL_CLOUD_QWEN_PREMIUM_KIMI
        == "qwen:accounts/fireworks/models/kimi-k2p6"
    )
    assert (
        defaults.CANONICAL_CLOUD_QWEN_LONG_DEEPSEEK_FLASH
        == "qwen:accounts/fireworks/models/deepseek-v4-flash"
    )
    assert defaults.CANONICAL_CLOUD_CLINE == "cline:cline-cli-default"
    assert (
        defaults.CANONICAL_OLLAMA_GEMMA4_UNCENSORED_TEST
        == "krishairnd/Gemma-4-Uncensored:latest"
    )
    assert (
        defaults.CANONICAL_OLLAMA_LOW_RAM
        == "alice-m1-cortex-4.5b-3.4gb:latest"
    )
    assert (
        defaults.CANONICAL_OLLAMA_LOW_RAM_SOURCE
        == "alice-m1-cortex-4.5b-3.4gb:latest"
    )
    assert defaults.DEFAULT_OLLAMA_MODEL == "alice-m5-cortex-8b-6.3gb:latest"
    assert defaults.CANONICAL_OLLAMA_REFLEX == "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"
    assert defaults.CANONICAL_OLLAMA_FALLBACK == "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"
    assert defaults.CANONICAL_OLLAMA_LORA_CANDIDATE == "sifta-gemma4-alice-lora:latest"
    assert "Default Alice cortex on M5:** `alice-m5-cortex-8b-6.3gb:latest`" in (defaults.__doc__ or "")
    assert "Experimental alias/test cortex:** `krishairnd/Gemma-4-Uncensored:latest`" in (defaults.__doc__ or "")
    assert "Retired heavy cortex:** `alice-extra-cortex-25.8b-17gb:latest`" in (defaults.__doc__ or "")
    assert "Cloud teacher cortexes:** Grok, Claude, Codex, Kimi K2.6/Fireworks, and Cline" in (defaults.__doc__ or "")


def test_legacy_fireworks_cortexes_normalize_to_kimi(tmp_path, monkeypatch):
    from System import sifta_inference_defaults as defaults

    monkeypatch.setattr(defaults, "_STATE", tmp_path)
    monkeypatch.setattr(defaults, "_ASSIGNMENTS", tmp_path / "swimmer_ollama_assignments.json")

    assert defaults.set_default_ollama_model(defaults.CANONICAL_CLOUD_QWEN) == defaults.CANONICAL_CLOUD_QWEN_PREMIUM_KIMI
    assert defaults.get_default_ollama_model() == defaults.CANONICAL_CLOUD_QWEN_PREMIUM_KIMI
    assert (
        defaults.set_app_ollama_model("talk_to_alice", defaults.CANONICAL_CLOUD_QWEN_LONG_DEEPSEEK_FLASH)
        == defaults.CANONICAL_CLOUD_QWEN_PREMIUM_KIMI
    )
    assert defaults.resolve_ollama_model(app_context="talk_to_alice") == defaults.CANONICAL_CLOUD_QWEN_PREMIUM_KIMI


def test_talk_resolver_mirror_stale_cloud_pin_uses_owner_default(tmp_path, monkeypatch):
    from System import sifta_inference_defaults as defaults

    monkeypatch.setattr(defaults, "_STATE", tmp_path)
    monkeypatch.setattr(defaults, "_ASSIGNMENTS", tmp_path / "swimmer_ollama_assignments.json")

    owner_selected = "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest"
    defaults.set_default_ollama_model(owner_selected)
    defaults.set_app_ollama_model("talk_to_alice", defaults.CANONICAL_CLOUD_CLINE)

    assert defaults.resolve_ollama_model(app_context="talk_to_alice") == owner_selected


def test_retired_17gb_cortex_hidden_from_installed_picker_by_default(monkeypatch):
    from System import sifta_inference_defaults as defaults
    import json as _json
    import urllib.request as _urlrequest

    payload = {
        "models": [
            {"name": defaults.CANONICAL_OLLAMA_DAILY},
            {"name": defaults.CANONICAL_OLLAMA_GEMMA4_SMALL},
            {"name": defaults.CANONICAL_OLLAMA_GEMMA4_UNCENSORED_TEST},
            {"name": "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest"},
            {"name": defaults.CANONICAL_OLLAMA_EXTRA},
            {"name": "llama3:latest"},
        ]
    }

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return _json.dumps(payload).encode("utf-8")

    monkeypatch.delenv("SIFTA_SHOW_RETIRED_CORTEXES", raising=False)
    monkeypatch.setattr(_urlrequest, "urlopen", lambda *_a, **_k: _Resp())

    models = defaults.list_installed_alice_cortexes()
    assert defaults.CANONICAL_OLLAMA_DAILY in models
    assert defaults.CANONICAL_OLLAMA_GEMMA4_SMALL in models
    assert defaults.CANONICAL_OLLAMA_GEMMA4_UNCENSORED_TEST in models
    assert "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest" in models
    assert defaults.CANONICAL_OLLAMA_EXTRA not in models
    assert "llama3:latest" not in models

    monkeypatch.setenv("SIFTA_SHOW_RETIRED_CORTEXES", "1")
    assert defaults.CANONICAL_OLLAMA_EXTRA in defaults.list_installed_alice_cortexes()
    assert "smaller Gemma4 4.4GB used to" in (defaults.__doc__ or "")
    assert "M1 Alice cortex:** `alice-m1-cortex-4.5b-3.4gb:latest`" in (defaults.__doc__ or "")
    assert "Reflex path:** fast deterministic checks first, then the shared Gemma path" in (defaults.__doc__ or "")
    assert "Generative fallback/probe:** `alice-gemma4-e2b-cortex-5.1b-4.4gb:latest`" in (defaults.__doc__ or "")
    assert "LoRA surgery candidate:** `sifta-gemma4-alice-lora:latest` is retired" in (defaults.__doc__ or "")


def test_system_settings_imports_demoted_gemma4_alias():
    from Applications.sifta_system_settings import CANONICAL_OLLAMA_GEMMA4_SMALL

    assert CANONICAL_OLLAMA_GEMMA4_SMALL == "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"


def test_system_settings_treats_grok_as_remote_cortex():
    from Applications.sifta_system_settings import _looks_remote_model_name

    assert _looks_remote_model_name("gemini:gemini-2.5-flash")
    assert _looks_remote_model_name("grok:grok-4.3")
    assert _looks_remote_model_name("grok-4.3")
    assert _looks_remote_model_name("claude:claude-code-cli-default")
    assert _looks_remote_model_name("codex:gpt-5.5")
    assert _looks_remote_model_name("qwen:accounts/fireworks/models/gpt-oss-20b")
    assert _looks_remote_model_name("qwen:accounts/fireworks/models/deepseek-v4-flash")
    assert _looks_remote_model_name("cline:cline-cli-default")
    assert not _looks_remote_model_name("alice-m5-cortex-8b-6.3gb:latest")
    from System.sifta_inference_defaults import CANONICAL_MLX_GEMMA4_12B_ORIGINAL

    assert not _looks_remote_model_name(CANONICAL_MLX_GEMMA4_12B_ORIGINAL)


def test_cloud_backend_recognizes_grok_model_selector():
    from System.swarm_gemini_brain import is_cloud_model

    assert is_cloud_model("grok:grok-4.3")
    assert is_cloud_model("grok-4.3")
    assert is_cloud_model("claude:claude-code-cli-default")
    assert is_cloud_model("codex:gpt-5.5")
    assert is_cloud_model("qwen:accounts/fireworks/models/gpt-oss-20b")
    assert is_cloud_model("qwen:accounts/fireworks/models/deepseek-v4-flash")
    assert is_cloud_model("cline:cline-cli-default")
    assert is_cloud_model("gemini:gemini-2.5-flash")
    assert not is_cloud_model("alice-m5-cortex-8b-6.3gb:latest")


def test_gemma4_12b_mlx_vlm_routes_to_direct_vlm_not_omni_mlx():
    from System import swarm_gemini_brain as brain
    from System.sifta_inference_defaults import CANONICAL_MLX_GEMMA4_12B_ORIGINAL

    assert brain._is_direct_mlx_vlm_model(CANONICAL_MLX_GEMMA4_12B_ORIGINAL)
    assert not brain._is_mlx_model(CANONICAL_MLX_GEMMA4_12B_ORIGINAL)
    assert brain.strip_prefix(CANONICAL_MLX_GEMMA4_12B_ORIGINAL) == "SuperagenticAI/gemma-4-12b-it-8bit-mlx"


def test_inference_page_has_no_duplicate_dropdowns(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "1")

    from PyQt6.QtWidgets import QApplication, QComboBox, QLabel

    from Applications.sifta_system_settings import SystemSettingsWidget

    app = QApplication.instance() or QApplication([])
    settings = SystemSettingsWidget()
    try:
        chat_source = (REPO / "Applications" / "sifta_swarm_chat.py").read_text(encoding="utf-8")
        alice_source = (REPO / "Applications" / "sifta_talk_to_alice_widget.py").read_text(encoding="utf-8")
        assert "model_selector" not in chat_source
        assert "_brain_combo" not in alice_source
        assert settings.findChild(QComboBox, "DefaultInferenceModelCombo") is None
        assert settings.findChild(QComboBox, "AliceBrainModelCombo") is None
        picker = settings.findChild(QComboBox, "AliceCortexPicker")
        assert picker is not None
        inventory_picker = settings.findChild(QComboBox, "InstalledModelBodyPicker")
        assert inventory_picker is not None
        assert inventory_picker.isHidden()
        assert hasattr(settings, "inference_default_card")
        labels = "\n".join(label.text() for label in settings.findChildren(QLabel))
        assert "alice-Q-m1-scout-2.3b-2.7gb:latest" not in labels
        assert "sifta-classifier-c1-3.1b-6.2gb:latest" not in labels
        picker_items = "\n".join(picker.itemText(i) for i in range(picker.count()))
        assert "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest" in picker_items
        assert "alice-m5-cortex-8b-6.3gb:latest" in picker_items
        assert "krishairnd/Gemma-4-Uncensored:latest" in picker_items
        assert "grok:grok-4.3" in picker_items
        assert "claude:claude-code-cli-default" in picker_items
        assert "codex:gpt-5.5" in picker_items
        assert "qwen:accounts/fireworks/models/gpt-oss-20b" not in picker_items
        assert "qwen:accounts/fireworks/models/deepseek-v4-flash" not in picker_items
        assert "qwen:accounts/fireworks/models/kimi-k2p6" in picker_items
        assert settings.findChild(QComboBox, "HermesArmProviderPicker") is None
        assert "Hermes Arm Provider" not in labels
        assert "cline:cline-cli-default" in picker_items
        assert "heretic  ·" not in picker_items
        assert "grok-oauth" not in picker_items
    finally:
        settings.close()
        for _ in range(10):
            app.processEvents()


def test_inference_page_reflects_talk_app_override_not_global_default(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "1")

    from PyQt6.QtWidgets import QApplication, QComboBox

    from Applications import sifta_system_settings as settings_mod

    default_model = "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest"
    talk_model = "cline:cline-cli-default"
    monkeypatch.setattr(
        settings_mod,
        "list_available_cortexes_with_canonical_fallback",
        lambda: [default_model, talk_model],
    )
    monkeypatch.setattr(settings_mod, "get_default_ollama_model", lambda: default_model)
    monkeypatch.setattr(
        settings_mod,
        "resolve_ollama_model",
        lambda **_kw: talk_model,
    )
    monkeypatch.setattr(settings_mod, "list_inference_model_inventory", lambda: [])
    monkeypatch.setattr(settings_mod, "inference_runtime_nuggets", lambda: [])

    app = QApplication.instance() or QApplication([])
    settings = settings_mod.SystemSettingsWidget()
    try:
        picker = settings.findChild(QComboBox, "AliceCortexPicker")
        assert picker is not None
        assert picker.currentData() == talk_model
    finally:
        settings.close()
        for _ in range(10):
            app.processEvents()


def test_qwen_key_mask_and_provider_tag_helpers(tmp_path, monkeypatch):
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from Applications.sifta_system_settings import (
        _is_cline_cortex_tag,
        _is_qwen_cortex_tag,
        _qwen_api_key_masked,
    )
    from System import swarm_fireworks_qwen_config as qcfg

    key_path = tmp_path / "secrets" / "fireworks_api_key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("sk_live_verysecret_key_1234\n", encoding="utf-8")

    assert _is_qwen_cortex_tag("qwen:accounts/fireworks/models/gpt-oss-20b")
    assert _is_qwen_cortex_tag("qwen:accounts/fireworks/models/deepseek-v4-flash")
    assert not _is_qwen_cortex_tag("grok:grok-4.3")
    assert _is_cline_cortex_tag("cline:cline-cli-default")
    assert not _is_cline_cortex_tag("codex:gpt-5.5")

    monkeypatch.setattr(qcfg, "FIREWORKS_SECRET_RELATIVE", key_path.relative_to(tmp_path))
    masked = _qwen_api_key_masked(state_dir=tmp_path)
    assert masked.startswith("sk_l") and masked.endswith("1234")


def test_qwen_cortex_indicator_click_installs_key(monkeypatch, tmp_path):
    from Applications.sifta_system_settings import SystemSettingsWidget
    from PyQt6.QtWidgets import QApplication, QComboBox
    from System import sifta_inference_defaults as defaults

    # Keep UI startup deterministic and avoid any live persistence.
    monkeypatch.setattr(
        "Applications.sifta_system_settings.list_available_cortexes_with_canonical_fallback",
        lambda: [
            defaults.CANONICAL_OLLAMA_DAILY,
            defaults.CANONICAL_CLOUD_GROK,
            defaults.CANONICAL_CLOUD_CLAUDE,
            defaults.CANONICAL_CLOUD_CODEX,
            defaults.CANONICAL_CLOUD_QWEN_PREMIUM_KIMI,
            defaults.CANONICAL_CLOUD_CLINE,
        ],
    )
    monkeypatch.setattr(
        "Applications.sifta_system_settings.set_default_ollama_model",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "Applications.sifta_system_settings.set_app_ollama_model",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        SystemSettingsWidget,
        "_persist_primary_cortex_selection",
        lambda _self, tag, *, source: {
            "ok": True,
            "selected_model": str(tag),
            "source": source,
            "trace_id": "pytest-no-live-write",
        },
    )
    monkeypatch.setattr("Applications.sifta_system_settings.STATE", tmp_path)
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    installed: dict[str, Any] = {}

    def fake_install(api_key: str, *, state_dir: str | Path | None = None, qwen_home: str | Path | None = None) -> dict[str, str]:
        installed["api_key"] = api_key
        installed["state_dir"] = str(state_dir)
        installed["qwen_home"] = str(qwen_home)
        secret_path = Path(state_dir or tmp_path) / "secrets" / "fireworks_api_key"
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        secret_path.write_text(f"{api_key}\n", encoding="utf-8")
        return {
            "secret_path": str((Path(state_dir or tmp_path) / "secrets" / "fireworks_api_key")),
            "settings_path": str((Path(qwen_home or tmp_path) / "qwen" / "settings.json")),
        }

    monkeypatch.setattr("Applications.sifta_system_settings.install_qwen_fireworks_settings", fake_install)
    monkeypatch.setattr(
        "Applications.sifta_system_settings.QInputDialog.getText",
        staticmethod(lambda *_a, **_k: ("sk_test_1234", True)),
    )

    app = QApplication.instance() or QApplication([])
    status_rows: list[str] = []

    settings = SystemSettingsWidget()
    try:
        settings.set_status = lambda msg: status_rows.append(str(msg))
        picker = settings.findChild(QComboBox, "AliceCortexPicker")
        assert picker is not None
        qidx = None
        for i in range(picker.count()):
            if picker.itemData(i) == defaults.CANONICAL_CLOUD_QWEN_PREMIUM_KIMI:
                qidx = i
                break
        assert qidx is not None
        picker.setCurrentIndex(qidx)

        settings._on_cortex_auth_indicator_clicked()
        assert installed["api_key"] == "sk_test_1234"
        assert installed["state_dir"] == str(tmp_path)
        assert settings._cortex_auth_indicator.toolTip().startswith("Qwen/Fireworks key present")
        assert any("saved" in row.lower() for row in status_rows)
    finally:
        settings.close()
        for _ in range(10):
            app.processEvents()


def test_cline_cortex_indicator_refresh_message(monkeypatch, tmp_path):
    from Applications.sifta_system_settings import SystemSettingsWidget
    from PyQt6.QtWidgets import QApplication, QComboBox
    from System import sifta_inference_defaults as defaults

    monkeypatch.setattr(
        "Applications.sifta_system_settings.list_available_cortexes_with_canonical_fallback",
        lambda: [defaults.CANONICAL_CLOUD_CLINE],
    )
    monkeypatch.setattr(
        "Applications.sifta_system_settings.set_default_ollama_model",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "Applications.sifta_system_settings.set_app_ollama_model",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        SystemSettingsWidget,
        "_persist_primary_cortex_selection",
        lambda _self, tag, *, source: {
            "ok": True,
            "selected_model": str(tag),
            "source": source,
            "trace_id": "pytest-no-live-write",
        },
    )
    monkeypatch.setattr(
        "Applications.sifta_system_settings._cline_cli_available",
        lambda: None,
    )

    app = QApplication.instance() or QApplication([])
    settings = SystemSettingsWidget()
    try:
        picker = settings.findChild(QComboBox, "AliceCortexPicker")
        assert picker is not None
        assert picker.count() >= 1
        picker.setCurrentIndex(0)
        settings._refresh_cortex_auth_indicator()
        assert "alice-hand" in settings._cortex_auth_indicator.toolTip()
        settings._on_cortex_auth_indicator_clicked()
        assert "alice-hand" in settings._cortex_auth_indicator.toolTip()
    finally:
        settings.close()
        for _ in range(10):
            app.processEvents()
