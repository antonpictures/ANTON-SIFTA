import json
from pathlib import Path

from System import swarm_fireworks_qwen_config as cfg


class _FakeResponse:
    def __init__(self, payload: dict[str, object], status: int = 200):
        self.payload = payload
        self.status = status

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_fireworks_secret_reads_env_before_file(tmp_path):
    secret = tmp_path / "secrets" / "fireworks_api_key"
    secret.parent.mkdir()
    secret.write_text("fw_FILE\n", encoding="utf-8")

    assert cfg.read_fireworks_api_key(state_dir=tmp_path, env={"FIREWORKS_API_KEY": "fw_ENV"}) == "fw_ENV"
    assert cfg.read_fireworks_api_key(state_dir=tmp_path, env={}) == "fw_FILE"


def test_qwen_child_env_sets_openai_key_without_command_leak(tmp_path):
    secret = tmp_path / "secrets" / "fireworks_api_key"
    secret.parent.mkdir()
    secret.write_text("fw_LOCAL\n", encoding="utf-8")

    env = cfg.qwen_fireworks_child_env({}, state_dir=tmp_path)
    assert env["FIREWORKS_API_KEY"] == "fw_LOCAL"
    assert env["OPENAI_API_KEY"] == "fw_LOCAL"
    assert env["QWEN_CODE_SUPPRESS_YOLO_WARNING"] == "1"

    cmd = cfg.qwen_fireworks_command("hello")
    assert "fw_LOCAL" not in "\n".join(cmd)
    assert cfg.FIREWORKS_BASE_URL in cmd
    assert cfg.FIREWORKS_DEFAULT_MODEL in cmd
    assert cfg.FIREWORKS_DEEPSEEK_V4_FLASH_MODEL in cfg.qwen_fireworks_command(
        "hello",
        model=cfg.FIREWORKS_DEEPSEEK_V4_FLASH_MODEL,
    )


def test_install_qwen_settings_writes_local_secret_and_provider(tmp_path):
    qwen_home = tmp_path / "qwen_home"
    result = cfg.install_qwen_fireworks_settings(
        "fw_TEST",
        state_dir=tmp_path / "state",
        qwen_home=qwen_home,
    )

    assert Path(result["secret_path"]).read_text(encoding="utf-8").strip() == "fw_TEST"
    text = Path(result["settings_path"]).read_text(encoding="utf-8")
    assert cfg.FIREWORKS_DEFAULT_MODEL in text
    assert cfg.FIREWORKS_DEEPSEEK_V4_FLASH_MODEL in text
    assert cfg.FIREWORKS_KIMI_K2P6_MODEL not in text
    assert cfg.FIREWORKS_BASE_URL in text
    assert "FIREWORKS_API_KEY" in text
    assert "OPENAI_API_KEY" in text
    assert '"apiKey": "fw_TEST"' in text


def test_probe_missing_key_reports_missing(tmp_path):
    assert cfg.probe_fireworks_connectivity(state_dir=tmp_path, api_key="") == {
        "ok": False,
        "reason": "missing_api_key",
        "error": "No FIREWORKS_API_KEY available in env or .sifta_state/secrets/fireworks_api_key",
        "status": None,
    }


def test_probe_success_with_mock_transport(monkeypatch, tmp_path):
    payload = {
        "id": "abc",
        "object": "chat.completion",
        "model": cfg.FIREWORKS_DEFAULT_MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Working"},
            },
        ],
    }

    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = {k: request.headers[k] for k in request.headers}
        body = json.loads(request.data.decode("utf-8")) if request.data else None
        captured["body"] = body
        return _FakeResponse(payload, status=200)

    monkeypatch.setattr(cfg.urllib.request, "urlopen", fake_urlopen)
    cfg.install_qwen_fireworks_settings("fw_probe_token", state_dir=tmp_path)

    result = cfg.probe_fireworks_connectivity(state_dir=tmp_path, timeout_s=4)

    assert result["ok"] is True
    assert result["status"] == 200
    assert result["model_echo"] == cfg.FIREWORKS_DEFAULT_MODEL
    assert result["reply"] == "Working"
    assert captured["url"] == cfg.FIREWORKS_CHAT_COMPLETIONS_URL
    assert captured["timeout"] == 4
    assert captured["body"]["model"] == cfg.FIREWORKS_DEFAULT_MODEL
    assert captured["headers"]["Authorization"] == "Bearer fw_probe_token"
