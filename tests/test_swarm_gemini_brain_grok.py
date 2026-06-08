from __future__ import annotations

from types import SimpleNamespace
from urllib.error import HTTPError
import json
import urllib.request


def test_grok_cli_model_for_maps_canonical_sifta_key_to_live_cli_model():
    from System import swarm_gemini_brain as brain

    assert brain.grok_cli_model_for("grok:grok-4.3") == "grok-build"
    assert brain.grok_cli_model_for("grok-4.3") == "grok-build"
    assert brain.grok_cli_model_for("grok:unknown-future") == "unknown-future"
    assert brain.is_cloud_model("claude:claude-code-cli-default")
    assert brain.is_cloud_model("codex:gpt-5.5")
    assert brain.strip_prefix("claude:claude-code-cli-default") == "claude-code-cli-default"
    assert brain.strip_prefix("codex:gpt-5.5") == "gpt-5.5"
    assert brain.display_label("claude-code-cli-default") == "claude:claude-code-cli-default"
    assert brain.display_label("gpt-5.5") == "codex:gpt-5.5"


def test_stream_grok_chat_uses_live_cli_model_for_canonical_key(monkeypatch):
    from System import swarm_gemini_brain as brain

    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(list(cmd))
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

    assert len(calls) == 1
    assert "--model" in calls[0]
    assert calls[0][calls[0].index("--model") + 1] == "grok-build"
    assert events[0][0] == "token"
    assert events[0][1] == "SIFTA_GROK_CORTEX_OK"
    assert events[1][0] == "usage"
    assert events[1][1].model == "grok-build"
    assert events[1][1].raw.get("requested_model") == "grok-4.3"
    assert events[1][1].raw.get("cli_model") == "grok-build"
    assert events[1][1].raw.get("fallback_to_cli_default") is False
    assert events[2] == ("done", "SIFTA_GROK_CORTEX_OK")


def test_stream_grok_chat_falls_back_to_cli_default_for_unknown_model(monkeypatch):
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
            stdout="UNKNOWN_MODEL_FALLBACK_OK\nTurn completed in 1s.\n",
            stderr="",
        )

    monkeypatch.setattr(brain, "xai_api_key", lambda: None)
    monkeypatch.setattr(brain, "_grok_cli_binary", lambda: "/usr/local/bin/grok")
    monkeypatch.setattr(brain.subprocess, "run", fake_run)

    events = list(
        brain.stream_chat(
            "grok:unknown-future",
            [{"role": "user", "content": "Reply with UNKNOWN_MODEL_FALLBACK_OK"}],
            timeout_s=5,
        )
    )

    assert len(calls) == 2
    assert "--model" in calls[0]
    assert calls[0][calls[0].index("--model") + 1] == "unknown-future"
    assert "--model" not in calls[1]
    assert events[0] == ("token", "UNKNOWN_MODEL_FALLBACK_OK")
    assert events[1][0] == "usage"
    assert events[1][1].raw.get("fallback_to_cli_default") is True
    assert events[2] == ("done", "UNKNOWN_MODEL_FALLBACK_OK")


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
    assert "No Grok OAuth credential found and local `grok` CLI is missing" in events[0][1]
    assert "Hermes: `hermes auth add xai-oauth`" in events[0][1]


def test_xai_sse_content_delta_parser():
    from System import swarm_gemini_brain as brain

    assert brain._xai_sse_content_delta(
        'data: {"choices":[{"delta":{"content":"Hello"}}]}'
    ) == "Hello"
    assert brain._xai_sse_content_delta(
        'data: {"choices":[{"delta":{"role":"assistant"}}]}'
    ) == ""
    assert brain._xai_sse_content_delta("data: [DONE]") == ""
    assert brain._xai_sse_content_delta("not json") == ""


def test_stream_grok_chat_streams_xai_sse_without_duplicate_final_token(monkeypatch):
    from System import swarm_gemini_brain as brain

    captured: dict[str, object] = {}

    class FakeStreamingResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def __iter__(self):
            return iter(
                [
                    b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n',
                    b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n',
                    b'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n',
                    b'data: {"choices":[],"usage":{"prompt_tokens":3,"completion_tokens":2,"total_tokens":5}}\n\n',
                    b"data: [DONE]\n\n",
                ]
            )

    def fake_urlopen(req, **_kwargs):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeStreamingResponse()

    usage_rows = []
    monkeypatch.setattr(brain, "xai_api_key", lambda: "xai-token")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(brain, "record_usage", lambda usage, backend: usage_rows.append((backend, usage)))

    events = list(
        brain.stream_chat(
            "grok:grok-4.3",
            [{"role": "user", "content": "Say Hello"}],
            timeout_s=5,
        )
    )

    assert captured["body"]["stream"] is True
    assert captured["body"]["stream_options"] == {"include_usage": True}
    assert events[0] == ("token", "Hel")
    assert events[1] == ("token", "lo")
    assert events[2][0] == "usage"
    assert events[2][1].prompt_tokens == 3
    assert events[2][1].completion_tokens == 2
    assert events[3] == ("done", "Hello")
    assert [event for event in events if event == ("token", "Hello")] == []
    assert usage_rows and usage_rows[0][0] == "xai_grok"


def test_stream_claude_teacher_uses_signed_in_cli(monkeypatch):
    from System import swarm_gemini_brain as brain

    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0, stdout="CLAUDE_TEACHER_OK", stderr="")

    monkeypatch.setattr(brain.shutil, "which", lambda name: "/usr/local/bin/claude" if name == "claude" else None)
    monkeypatch.setattr(brain.subprocess, "run", fake_run)

    events = list(
        brain.stream_chat(
            "claude:claude-code-cli-default",
            [{"role": "user", "content": "Reply CLAUDE_TEACHER_OK"}],
            timeout_s=5,
        )
    )

    assert calls
    assert calls[0][0].endswith("claude")
    assert "--permission-mode" in calls[0]
    assert "CLAUDE_TEACHER_OK" in events[0][1]
    assert events[-1] == ("done", "CLAUDE_TEACHER_OK")


def test_stream_codex_teacher_uses_signed_in_cli_read_only(monkeypatch, tmp_path):
    from System import swarm_gemini_brain as brain

    calls: list[list[str]] = []
    monkeypatch.setattr(brain, "_STATE", tmp_path)

    def fake_run(cmd, **_kwargs):
        calls.append(list(cmd))
        out_path = cmd[cmd.index("--output-last-message") + 1]
        from pathlib import Path

        Path(out_path).write_text("CODEX_TEACHER_OK", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(brain.shutil, "which", lambda name: "/opt/homebrew/bin/codex" if name == "codex" else None)
    monkeypatch.setattr(brain.subprocess, "run", fake_run)

    events = list(
        brain.stream_chat(
            "codex:gpt-5.5",
            [{"role": "user", "content": "Reply CODEX_TEACHER_OK"}],
            timeout_s=5,
        )
    )

    assert calls
    assert calls[0][:2] == ["/opt/homebrew/bin/codex", "exec"]
    assert "--sandbox" in calls[0]
    assert "read-only" in calls[0]
    assert events[-1] == ("done", "CODEX_TEACHER_OK")


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


def test_stream_grok_chat_falls_back_to_cli_on_xai_unknown_model(monkeypatch):
    from System import swarm_gemini_brain as brain

    class FakeBody:
        def read(self):
            return b'{"error":"Invalid params: unknown model id"}'

        def close(self):
            pass

    def fake_urlopen(*_args, **_kwargs):
        raise HTTPError(
            url="https://api.x.ai/v1/chat/completions",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=FakeBody(),
        )

    def fake_cli_fallback(**_kwargs):
        yield ("token", "CLI_UNKNOWN_MODEL_FALLBACK_OK")
        yield ("done", "CLI_UNKNOWN_MODEL_FALLBACK_OK")

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
    assert events[0] == ("token", "CLI_UNKNOWN_MODEL_FALLBACK_OK")
    assert events[1] == ("done", "CLI_UNKNOWN_MODEL_FALLBACK_OK")


def test_r708_xai_sse_content_delta_parses_stream_lines():
    """r708: grok cloud streams like George's terminal CLI. The SSE delta
    parser is the unit-testable core of that path."""
    from System.swarm_gemini_brain import _xai_sse_content_delta as d

    assert d('data: {"choices":[{"delta":{"content":"Hello"}}]}') == "Hello"
    assert d('data: {"choices":[{"delta":{"role":"assistant"}}]}') == ""
    assert d("data: [DONE]") == ""
    assert d("") == ""
    assert d('data: {"choices":[],"usage":{"prompt_tokens":5}}') == ""
    # full reconstruction matches a non-streamed answer
    lines = [
        'data: {"choices":[{"delta":{"content":"Open"}}]}',
        'data: {"choices":[{"delta":{"content":"ing "}}]}',
        'data: {"choices":[{"delta":{"content":"YouTube."}}]}',
        "data: [DONE]",
    ]
    assert "".join(d(l) for l in lines) == "Opening YouTube."
