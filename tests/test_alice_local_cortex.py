#!/usr/bin/env python3
"""Tests for System/alice_local_cortex.py — the llama.cpp fallback lane.

No server is started and no network is touched except one deliberate dead-port
probe. The real Ollama blob inventory is read (read-only) because the whole point
of the organ is that those blobs are servable.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System import alice_local_cortex as cortex


def test_is_gguf_reads_the_magic(tmp_path):
    good = tmp_path / "good.gguf"
    good.write_bytes(b"GGUF" + b"\x03\x00\x00\x00rest")
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"NOPErest")
    missing = tmp_path / "absent.gguf"

    assert cortex.is_gguf(good) is True
    assert cortex.is_gguf(bad) is False
    assert cortex.is_gguf(missing) is False


def test_real_blob_inventory_is_servable():
    """The claim 'Ollama's store is already GGUF' has to hold on this disk."""
    models = cortex.available_models()
    assert models, "no servable GGUF found — the fallback lane would have nothing to run"
    for name, row in models.items():
        assert row["gguf"] is True, f"{name} is listed but is not a GGUF"
        assert Path(row["path"]).exists()
        assert row["size_gb"] > 0.1


def test_start_prefers_the_smallest_coder_and_builds_a_real_command(monkeypatch, tmp_path):
    fake_models = {
        "library/sifta-ornith-coder": {"path": "/blobs/big", "size_gb": 16.76, "gguf": True},
        "LisyNeko/qwen3.8-9b-coder": {"path": "/blobs/small-coder", "size_gb": 5.78, "gguf": True},
        "some/plain-model": {"path": "/blobs/plain", "size_gb": 2.0, "gguf": True},
    }
    captured: dict = {}

    class FakeProcess:
        pid = 4242

        def poll(self):
            return None

    monkeypatch.setattr(cortex, "available_models", lambda: fake_models)
    monkeypatch.setattr(cortex, "_probe", lambda port, timeout=2.0: True)
    monkeypatch.setattr(cortex, "_running_pid", lambda: None)
    monkeypatch.setattr(cortex, "_STATE", tmp_path)
    monkeypatch.setattr(cortex, "_PID_FILE", tmp_path / "local_cortex.pid")
    monkeypatch.setattr(cortex, "_LOG_FILE", tmp_path / "local_cortex.log")
    monkeypatch.setattr(cortex, "_llama_binary", lambda: "/opt/homebrew/bin/llama-server")

    def fake_popen(command, **kwargs):
        captured["command"] = command
        return FakeProcess()

    monkeypatch.setattr(cortex.subprocess, "Popen", fake_popen)

    result = cortex.start(port=8081)

    assert result["ok"] is True
    assert result["model"] == "LisyNeko/qwen3.8-9b-coder", "a fallback must load the small coder, not the 16 GB one"
    command = captured["command"]
    assert "/blobs/small-coder" in command
    assert "--port" in command and "8081" in command
    assert "--alias" in command and "local-fallback" in command
    assert (tmp_path / "local_cortex.pid").read_text() == "4242"


def test_start_refuses_when_there_is_nothing_to_serve(monkeypatch, tmp_path):
    monkeypatch.setattr(cortex, "available_models", lambda: {})
    monkeypatch.setattr(cortex, "_running_pid", lambda: None)
    result = cortex.start()
    assert result["ok"] is False
    assert "no servable GGUF" in result["error"]


def test_start_refuses_a_non_gguf_blob(monkeypatch, tmp_path):
    monkeypatch.setattr(cortex, "available_models", lambda: {
        "x/not-gguf": {"path": "/blobs/x", "size_gb": 3.0, "gguf": False},
    })
    monkeypatch.setattr(cortex, "_running_pid", lambda: None)
    result = cortex.start("x/not-gguf")
    assert result["ok"] is False
    assert "not a GGUF" in result["error"]


def test_start_reuses_a_running_server(monkeypatch):
    monkeypatch.setattr(cortex, "_running_pid", lambda: 999)
    result = cortex.start()
    assert result["ok"] is True
    assert result["already_running"] is True


def test_stop_is_idempotent_when_nothing_runs(monkeypatch, tmp_path):
    monkeypatch.setattr(cortex, "_running_pid", lambda: None)
    monkeypatch.setattr(cortex, "_PID_FILE", tmp_path / "absent.pid")
    result = cortex.stop()
    assert result["ok"] is True
    assert result["stopped"] is False


def test_verify_reports_a_dead_port_as_failure_not_as_empty_content():
    result = cortex.verify(port=9, timeout=2.0)
    assert result["ok"] is False
    assert "error" in result
