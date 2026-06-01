from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from System import xai_grok_oauth_organ as organ


def _registration(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "ts": time.time(),
            "kind": "LLM_REGISTRATION",
            "model": "codex",
            "lane": "xai_oauth_test",
        }) + "\n",
        encoding="utf-8",
    )


def test_refuses_without_recent_registration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "xai_calls.jsonl"
    monkeypatch.setenv("XAI_API_KEY", "xai-test-secret")

    with pytest.raises(PermissionError):
        organ.call_xai_responses(
            "hello",
            trace_path=tmp_path / "missing_trace.jsonl",
            ledger_path=ledger,
            dry_run=True,
        )

    row = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert row["ok"] is False
    assert row["reason"] == "missing_recent_sifta_registration"
    assert row["credential_redacted"] == "xai-t...cret"


def test_dry_run_with_registration_writes_redacted_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trace = tmp_path / "ide_stigmergic_trace.jsonl"
    ledger = tmp_path / "xai_calls.jsonl"
    _registration(trace)
    monkeypatch.setenv("XAI_OAUTH_ACCESS_TOKEN", "oauth-token-123456")

    row = organ.call_xai_responses(
        "hello",
        trace_path=trace,
        ledger_path=ledger,
        dry_run=True,
    )
    saved = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])

    assert row["ok"] is True
    assert saved["reason"] == "dry_run_auth_resolved"
    assert saved["credential_kind"] == "oauth_access_token"
    assert saved["credential_redacted"] == "oauth...3456"
    assert saved["model"] == "grok-4"


def test_grok_product_labels_normalize_to_api_model_id() -> None:
    assert organ.normalize_grok_model_id("grok:grok-4.3") == "grok-4.3"
    assert organ.normalize_grok_model_id("xai:grok-4.20-reasoning") == "grok-4.20-reasoning"
    assert organ.normalize_grok_model_id("grok-2-vision-1212") == "grok-2-vision-1212"


def test_grok_oauth_bad_credentials_get_stable_status() -> None:
    body = (
        '{"code":"The caller does not have permission to execute the specified operation",'
        '"error":"The OAuth2 access token could not be validated. '
        '[WKE=unauthenticated:bad-credentials]"}'
    )

    assert organ._classify_grok_http_failure(403, body) == "oauth_bad_credentials"
    assert organ._classify_grok_http_failure(500, "server down") == "http_error:500"


def test_grok_image_request_preserves_selected_model_and_payload_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0" + b"x" * 64)
    monkeypatch.setenv("XAI_OAUTH_ACCESS_TOKEN", "oauth-test-token")
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({
                "choices": [{
                    "message": {"role": "assistant", "content": "A visible photo."}
                }]
            }).encode("utf-8")

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(organ.request, "urlopen", fake_urlopen)

    result = organ.describe_image_via_oauth(
        str(img),
        "Describe this.",
        model="grok:grok-4.3",
        timeout_s=12,
    )

    assert result.ok is True
    assert result.model == "grok-4.3"
    assert captured["url"] == organ._CHAT_API_URL
    assert captured["body"]["model"] == "grok-4.3"
    assert captured["body"]["stream"] is False
    content = captured["body"]["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "Describe this."}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert captured["timeout"] == 12


def test_grok_cli_image_call_uses_logged_in_cli_content_blocks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    img = tmp_path / "photo.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 128)
    captured: dict[str, object] = {}

    class FakeProc:
        returncode = 0
        stdout = "A visible red square."
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr(organ, "discover_official_grok_cli", lambda: "/usr/local/bin/grok")
    monkeypatch.setattr(organ.subprocess, "run", fake_run)

    result = organ.describe_image_via_grok_cli(
        str(img),
        "Describe this.",
        model="grok:grok-4.3",
        timeout_s=9,
    )

    assert result.ok is True
    assert result.model == "grok-build"
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert cmd[0] == "/usr/local/bin/grok"
    assert "--prompt-json" in cmd
    payload = json.loads(cmd[cmd.index("--prompt-json") + 1])
    assert payload[0] == {"type": "text", "text": "Describe this."}
    assert payload[1]["type"] == "image"
    assert payload[1]["mimeType"] == "image/png"
    assert payload[1]["data"]
    assert "--model" in cmd
    assert cmd[cmd.index("--model") + 1] == "grok-build"
    assert "--max-turns" in cmd
    assert cmd[cmd.index("--max-turns") + 1] == "5"
    assert captured["kwargs"]["timeout"] == 9


def test_grok_cli_no_image_message_is_not_accepted_as_description(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    img = tmp_path / "tiny.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 128)

    class FakeProc:
        returncode = 0
        stdout = "No image received — image 1 normalization failed."
        stderr = ""

    monkeypatch.setattr(organ, "discover_official_grok_cli", lambda: "/usr/local/bin/grok")
    monkeypatch.setattr(organ.subprocess, "run", lambda *args, **kwargs: FakeProc())

    result = organ.describe_image_via_grok_cli(str(img), "Describe this.")

    assert result.ok is False
    assert result.status == "grok_cli_image_not_accepted"
    assert result.output == ""


def test_grok_wrapper_tries_cli_before_direct_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    img = tmp_path / "photo.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 128)
    calls: list[str] = []

    def fake_cli(*args, **kwargs):
        calls.append("cli")
        return organ.GrokVisionResult(ok=True, output="Grok CLI saw the image.", status="ok", model="grok-build")

    def fake_api(*args, **kwargs):
        calls.append("api")
        return organ.GrokVisionResult(ok=True, output="API saw the image.", status="ok", model="grok-4.3")

    monkeypatch.setattr(organ, "describe_image_via_grok_cli", fake_cli)
    monkeypatch.setattr(organ, "describe_image_via_oauth", fake_api)

    result = organ.describe_image_with_grok(str(img), "Describe this.", model="grok:grok-4.3")

    assert result.ok is True
    assert result.output == "Grok CLI saw the image."
    assert calls == ["cli"]


def test_grok_wrapper_falls_back_to_api_when_cli_rejects_image_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    img = tmp_path / "photo.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 128)
    calls: list[str] = []

    def fake_cli(*args, **kwargs):
        calls.append("cli")
        return organ.GrokVisionResult(
            ok=False,
            output="",
            stderr="No image received — image 1 normalization failed.",
            status="grok_cli_image_not_accepted",
            model="grok-build",
        )

    def fake_api(*args, **kwargs):
        calls.append("api")
        return organ.GrokVisionResult(
            ok=True,
            output="API saw the image.",
            status="ok",
            model="grok-4.3",
        )

    monkeypatch.setattr(organ, "describe_image_via_grok_cli", fake_cli)
    monkeypatch.setattr(organ, "describe_image_via_oauth", fake_api)

    result = organ.describe_image_with_grok(str(img), "Describe this.", model="grok:grok-4.3")

    assert result.ok is True
    assert result.output == "API saw the image."
    assert calls == ["cli", "api"]


def test_missing_credential_is_receipted_not_faked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trace = tmp_path / "ide_stigmergic_trace.jsonl"
    ledger = tmp_path / "xai_calls.jsonl"
    _registration(trace)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_OAUTH_ACCESS_TOKEN", raising=False)

    row = organ.call_xai_responses(
        "hello",
        trace_path=trace,
        ledger_path=ledger,
        token_file=tmp_path / "missing_token.json",
        hermes_auth_file=tmp_path / "missing_hermes_auth.json",
        dry_run=True,
    )

    assert row["ok"] is False
    assert row["reason"] == "missing_xai_credential"


def test_token_file_is_local_and_chmod_600(tmp_path: Path) -> None:
    token_file = tmp_path / "secrets" / "xai.json"
    organ.write_token_file({"access_token": "oauth-token-abcdef"}, token_file=token_file)
    cred = organ.load_credential(token_file=token_file, env={})

    assert cred is not None
    assert cred.kind == "oauth_access_token"
    assert oct(token_file.stat().st_mode & 0o777) == "0o600"


def test_hermes_auth_provider_token_is_accepted(tmp_path: Path) -> None:
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(
        json.dumps(
            {
                "providers": {
                    "xai-oauth": {
                        "tokens": {
                            "access_token": "oauth-hermes-provider-abcdef",
                            "refresh_token": "refresh-xyz",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    cred = organ.load_credential(
        token_file=tmp_path / "missing_token.json",
        hermes_auth_file=auth_file,
        env={},
    )
    assert cred is not None
    assert cred.kind == "oauth_access_token"
    assert cred.value == "oauth-hermes-provider-abcdef"
    assert "providers.tokens.access_token" in cred.source


def test_hermes_auth_credential_pool_token_is_accepted(tmp_path: Path) -> None:
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(
        json.dumps(
            {
                "credential_pool": {
                    "xai-oauth": [
                        {"access_token": "oauth-hermes-pool-123456", "label": "default"}
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    cred = organ.load_credential(
        token_file=tmp_path / "missing_token.json",
        hermes_auth_file=auth_file,
        env={},
    )
    assert cred is not None
    assert cred.kind == "oauth_access_token"
    assert cred.value == "oauth-hermes-pool-123456"
    assert "credential_pool" in cred.source
