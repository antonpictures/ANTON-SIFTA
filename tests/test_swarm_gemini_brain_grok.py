from __future__ import annotations

from types import SimpleNamespace
from urllib.error import HTTPError
import urllib.request


def test_stream_grok_chat_falls_back_to_cli_default_model(monkeypatch):
    from System import swarm_gemini_brain as brain

    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(list(cmd))
        if "--model" in cmd:
            return SimpleNamespace(
                returncode=1,
                stdout="",
                stderr='Error: unknown model id',
            )
        return SimpleNamespace(
            returncode=0,
            stdout="SIFTA_GROK_CORTEX_OK\nTurn completed in 1s.\n",
            stderr="",
        )

    monkeypatch.setattr(brain, "xai_api_key", lambda: None)
    monkeypatch.setattr(brain, "_grok_cli_binary", lambda: "/usr/local/bin/grok")
    monkeypatch.setattr(brain.subprocess, "run", fake_run)

    events = list(
        brain.stream_chat(
            "grok:grok-4.3",
            [{"role": "user", "content": "Reply with SIFTA_GROK_CORTEX_OK"}],
            timeout_s=5,
        )
    )

    assert len(calls) == 2
    assert "--model" in calls[0]
    assert "--model" not in calls[1]
    assert events[0][0] == "token"
    assert events[0][1] == "SIFTA_GROK_CORTEX_OK"
    assert events[1][0] == "usage"
    assert events[1][1].raw.get("fallback_to_cli_default") is True
    assert events[2] == ("done", "SIFTA_GROK_CORTEX_OK")


def test_stream_grok_chat_errors_when_no_key_and_no_cli(monkeypatch):
    from System import swarm_gemini_brain as brain

    monkeypatch.setattr(brain, "xai_api_key", lambda: None)
    monkeypatch.setattr(brain, "_grok_cli_binary", lambda: None)

    events = list(
        brain.stream_chat(
            "grok:grok-4.3",
            [{"role": "user", "content": "ping"}],
            timeout_s=3,
        )
    )
    assert len(events) == 1
    assert events[0][0] == "error"
    assert "No xAI credential found and local `grok` CLI is missing" in events[0][1]


def test_stream_grok_chat_falls_back_to_cli_on_xai_auth_denied(monkeypatch):
    from System import swarm_gemini_brain as brain

    def fake_urlopen(*_args, **_kwargs):
        raise HTTPError(
            url="https://api.x.ai/v1/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )

    def fake_cli_fallback(**_kwargs):
        yield ("token", "CLI_FALLBACK_OK")
        yield ("done", "CLI_FALLBACK_OK")

    monkeypatch.setattr(brain, "xai_api_key", lambda: "xai-token")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(brain, "_stream_grok_chat_via_cli", fake_cli_fallback)

    events = list(
        brain.stream_chat(
            "grok:grok-4.3",
            [{"role": "user", "content": "ping"}],
            timeout_s=3,
        )
    )
    assert events[0] == ("token", "CLI_FALLBACK_OK")
    assert events[1] == ("done", "CLI_FALLBACK_OK")
