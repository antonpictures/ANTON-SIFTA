"""CUR-F1 — diffusion cortex route + honest not-installed guard."""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from System import swarm_diffusion_cortex as sdc


SAMPLE_OUTPUT = """diffusion step: 63/64 [=========================================         ] 98%
total time: 24885.29ms, time per step: 388.83ms, sampling time per step: 0.85ms

Alice is the protagonist of the M5.
ggml_metal_free: deallocating
"""


def test_parse_diffusion_cli_output_extracts_final_line():
    text = sdc.parse_diffusion_cli_output(SAMPLE_OUTPUT, "")
    assert text == "Alice is the protagonist of the M5."


def test_diffusiongemma_honest_not_installed():
    path, entry, err = sdc.resolve_model_spec("diffusion:diffusiongemma-26b")
    assert path is None
    assert entry.get("installed") is False
    assert "unmerged" in err.lower() or "arch" in err.lower()


def test_build_cli_command_llada_block_schedule(tmp_path):
    gguf = tmp_path / "llada-8b.gguf"
    gguf.write_bytes(b"x")
    entry = {"schedule": "block", "block_length": 32}
    with mock.patch.object(sdc, "_cli_path", return_value=Path("/bin/llama-diffusion-cli")):
        cmd = sdc.build_cli_command(gguf, "hello", entry, temperature=0.0)
    assert cmd[0] == "/bin/llama-diffusion-cli"
    assert "-m" in cmd and str(gguf) in cmd
    assert "--diffusion-block-length" in cmd
    assert "32" in cmd


def test_stream_chat_yields_tokens_on_mock_subprocess():
    fake_proc = mock.Mock(returncode=0, stdout=SAMPLE_OUTPUT, stderr="")
    with mock.patch.object(sdc, "is_cli_built", return_value=True):
        with mock.patch.object(sdc, "resolve_model_spec") as rs:
            rs.return_value = (Path("/tmp/llada-8b.gguf"), {"schedule": "block", "block_length": 32}, "")
            with mock.patch("subprocess.run", return_value=fake_proc):
                events = list(sdc.stream_chat("diffusion:llada-8b", [{"role": "user", "content": "hi"}]))
    kinds = [e[0] for e in events]
    assert "token" in kinds
    assert kinds[-1] == "done"
    assert "protagonist" in events[-1][1]


def test_stream_chat_error_when_cli_missing():
    with mock.patch.object(sdc, "is_cli_built", return_value=False):
        events = list(sdc.stream_chat("diffusion:llada-8b", [{"role": "user", "content": "hi"}]))
    assert events[0][0] == "error"
    assert "llama-diffusion-cli" in events[0][1]


def test_gemini_brain_routes_diffusion_prefix():
    from System import swarm_gemini_brain as sgb

    assert sgb._is_diffusion_model("diffusion:llada-8b")
    assert not sgb._is_diffusion_model("mlx:foo")
    from System.swarm_cortex_selection_receipt import decode_family_for_model

    assert decode_family_for_model("diffusion:llada-8b") == "usd"


def test_available_models_only_lists_cached_gguf(monkeypatch):
    monkeypatch.setattr(sdc, "is_cli_built", lambda: True)
    monkeypatch.setattr(
        sdc,
        "resolve_model_spec",
        lambda mid: (
            (Path("/tmp/x.gguf"), {}, "")
            if "llada" in mid
            else (None, {}, "blocked")
        ),
    )
    models = sdc.available_models()
    assert models == ["diffusion:llada-8b"]