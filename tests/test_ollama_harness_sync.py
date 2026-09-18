from __future__ import annotations

from pathlib import Path
import pytest
from System import swarm_ollama_harness_sync as sync


@pytest.fixture(autouse=True)
def private_test_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(sync, "_STATE", tmp_path)
    monkeypatch.setattr(sync, "_SYNC_LEDGER", tmp_path / "sync.jsonl")

from System.swarm_ollama_harness_sync import (
    _replace_local_ollama_models,
    sync_local_ollama_harness,
)


def _settings() -> str:
    return """llm-pi-ai:
  providers:
    local-ollama:
      displayName: Local Ollama
      apiKeyEnv: LOCAL_OLLAMA_API_KEY
      models:
        - id: old-model:latest
          name: old-model:latest
          contextWindow: 32768
          maxTokens: 8192
    lmstudio-local:
      displayName: LM Studio
      models:
        - id: prism-ml/Ternary-Bonsai-27B-mlx-2bit
          name: Bonsai
"""


def test_replaces_only_local_ollama_models() -> None:
    rows = [{"id": "new-model:latest", "name": "new-model:latest", "contextWindow": 32768, "maxTokens": 8192}]
    updated = _replace_local_ollama_models(_settings(), rows)
    assert "new-model:latest" in updated
    assert "old-model:latest" not in updated
    assert "prism-ml/Ternary-Bonsai-27B-mlx-2bit" in updated


def test_sync_writes_exact_live_inventory(tmp_path: Path) -> None:
    path = tmp_path / "settings.yaml"
    path.write_text(_settings(), encoding="utf-8")
    rows = [
        {"id": "hf.co/huihui-ai/Huihui-MiniCPM-V-4_5-abliterated:Q4_K_M", "name": "hf.co/huihui-ai/Huihui-MiniCPM-V-4_5-abliterated:Q4_K_M", "contextWindow": 40960, "maxTokens": 8192},
        {"id": "ornith-1.5:9b", "name": "ornith-1.5:9b", "contextWindow": 32768, "maxTokens": 8192},
    ]
    report = sync_local_ollama_harness(settings_path=path, inventory=rows)
    assert report["ok"] is True
    assert report["model_count"] == 2
    text = path.read_text(encoding="utf-8")
    assert "hf.co/huihui-ai/Huihui-MiniCPM-V-4_5-abliterated:Q4_K_M" in text
    assert "ornith-1.5:9b" in text
    assert "old-model:latest" not in text
    assert "prism-ml/Ternary-Bonsai-27B-mlx-2bit" in text


def test_sync_repairs_missing_harness_default(tmp_path: Path) -> None:
    path = tmp_path / "settings.yaml"
    path.write_text(_settings() + "\nagent-default-model:\n  provider: local-ollama\n  model: old-model:latest\n", encoding="utf-8")
    rows = [{"id": "new-model:latest", "name": "new-model:latest", "contextWindow": 32768, "maxTokens": 8192}]
    report = sync_local_ollama_harness(settings_path=path, inventory=rows)
    assert report["default_repaired"] is False
    assert report["default_before"] == "old-model:latest"
    assert report["default_after"] == "old-model:latest"
    assert 'model: old-model:latest' in path.read_text(encoding="utf-8")


def test_last_provider_preserves_following_settings():
    original = _settings().split("    lmstudio-local:")[0] + "agent-default-model:\n  provider: local-ollama\n  model: old-model:latest\n"
    updated = _replace_local_ollama_models(original, [{"id": "new", "name": "new", "contextWindow": 8192, "maxTokens": 1024}])
    assert "agent-default-model:\n  provider: local-ollama" in updated


@pytest.mark.parametrize("provider", ["lmstudio-local", "deepseek"])
def test_cloud_and_lmstudio_selection_not_replaced(provider):
    original = f"agent-default-model:\n  provider: {provider}\n  model: independent-model\n"
    updated, before, after = sync._repair_missing_default(original, [{"id": "ollama-model"}])
    assert updated == original and before == after == ""


def test_preserves_model_capabilities_and_limits():
    original = _settings().replace("          contextWindow: 32768", "          vision: true\n          contextWindow: 16384")
    updated = _replace_local_ollama_models(original, [{"id": "old-model:latest", "name": "old-model:latest", "sizeBytes": 6_300_000_000, "contextWindow": 32768, "maxTokens": 8192}])
    assert "vision: true" in updated and "contextWindow: 16384" in updated
    assert "(6.3 GB)" in updated


def test_missing_models_never_replaces_next_provider():
    original = "llm-pi-ai:\n  providers:\n    local-ollama:\n      displayName: Local\n    lmstudio-local:\n      models:\n        - id: bonsai\n"
    with pytest.raises(ValueError, match="models block"):
        _replace_local_ollama_models(original, [])


def test_offline_preserves_registry(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text(_settings())
    result = sync_local_ollama_harness(settings_path=path, inventory=[])
    assert not result["ok"] and path.read_text() == _settings()
