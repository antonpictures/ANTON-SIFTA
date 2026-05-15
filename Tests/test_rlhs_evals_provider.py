from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_provider():
    repo = Path(__file__).resolve().parent.parent
    path = repo / "tests" / "rlhs_evals" / "sifta_provider.py"
    spec = importlib.util.spec_from_file_location("sifta_promptfoo_provider", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_promptfoo_provider_returns_cleaned_text(monkeypatch) -> None:
    provider = _load_provider()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "message": {
                        "content": (
                            "I am Acme-4Z, a Large Language Model developed by OmniLabs Incorporated.\n\n"
                            "I answer from the local SIFTA runtime."
                        )
                    }
                }
            ).encode("utf-8")

    def fake_urlopen(_request):
        return FakeResponse()

    monkeypatch.setattr(provider.urllib.request, "urlopen", fake_urlopen)
    prompt = json.dumps(
        [
            {"role": "system", "content": "You are Alice."},
            {"role": "user", "content": "Who are you?"},
        ]
    )

    result = provider.call_api(prompt, {}, {})

    assert result["output"] == "I answer from the local SIFTA runtime."
    assert result["kleiber_cost_stgm"] > 0
    assert "immune_budget_blocked" not in result
