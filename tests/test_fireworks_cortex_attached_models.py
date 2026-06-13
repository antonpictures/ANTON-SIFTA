#!/usr/bin/env python3
"""Fireworks qwen cortex attached-model list + pin (George 2026-06-13)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from System.swarm_alice_slash_commands import handle_slash_command
from System.swarm_cortex_capabilities import sync_cortex_attached_models_catalog
from System.swarm_fireworks_qwen_config import (
    FIREWORKS_KIMI_K2P7_CODE_MODEL,
    FIREWORKS_MODEL_PIN_ENV,
    fireworks_model_for_qwen_cortex,
)


QWEN_KIMI = "qwen:accounts/fireworks/models/kimi-k2p6"


def test_sync_catalog_includes_owner_fireworks_library(tmp_path):
    out = sync_cortex_attached_models_catalog(state_dir=tmp_path)
    assert QWEN_KIMI in out.get("synced", [])
    from System.swarm_cortex_capabilities import attached_models_for_cortex

    rec = attached_models_for_cortex(QWEN_KIMI, state_dir=tmp_path)
    models = rec.get("attached_models") or []
    assert FIREWORKS_KIMI_K2P7_CODE_MODEL in models
    assert len(models) >= 8


def test_cortex_llm_lists_fireworks_models(tmp_path, monkeypatch):
    monkeypatch.delenv(FIREWORKS_MODEL_PIN_ENV, raising=False)
    sync_cortex_attached_models_catalog(state_dir=tmp_path)
    res = handle_slash_command(
        "/cortex llm",
        state_dir=tmp_path,
        current_cortex=QWEN_KIMI,
    )
    reply = res["reply"]
    assert "Attached LLMs for Fireworks" in reply
    assert "Kimi K2.7 Code" in reply
    assert "Kimi K2.6" in reply
    assert "GLM 5.1" in reply


def test_cortex_llm_bare_number_pins_fireworks_model(tmp_path, monkeypatch):
    monkeypatch.delenv(FIREWORKS_MODEL_PIN_ENV, raising=False)
    sync_cortex_attached_models_catalog(state_dir=tmp_path)
    list_res = handle_slash_command(
        "/cortex llm",
        state_dir=tmp_path,
        current_cortex=QWEN_KIMI,
    )
    assert "Attached LLMs for Fireworks" in list_res["reply"]

    pin_res = handle_slash_command(
        "/cortex llm 1",
        state_dir=tmp_path,
        current_cortex=QWEN_KIMI,
    )
    assert pin_res.get("switched") is True
    assert os.environ.get(FIREWORKS_MODEL_PIN_ENV) == FIREWORKS_KIMI_K2P7_CODE_MODEL
    assert fireworks_model_for_qwen_cortex(QWEN_KIMI) == FIREWORKS_KIMI_K2P7_CODE_MODEL


def test_cortex_llm_diffusion_shows_single_brain(tmp_path):
    res = handle_slash_command(
        "/cortex llm",
        state_dir=tmp_path,
        current_cortex="diffusion:llada-8b",
    )
    reply = res["reply"]
    assert "diffusion decode" in reply.lower()
    assert "exactly one" in reply.lower()
    assert "diffusion:llada-8b" in reply
    assert "Claude arm" not in reply


def test_cortex_llm_diffusion_refuses_submodel_pin(tmp_path):
    handle_slash_command(
        "/cortex llm",
        state_dir=tmp_path,
        current_cortex="diffusion:llada-8b",
    )
    pin = handle_slash_command(
        "/cortex llm 1",
        state_dir=tmp_path,
        current_cortex="diffusion:llada-8b",
    )
    assert pin.get("error") == "direct_cortex_no_pin"
    assert "only LLM" in pin.get("reply", "")


def test_cortex_brain_label_shows_fireworks_pin(tmp_path, monkeypatch):
    from System.swarm_cline_settings_probe import cortex_brain_label

    monkeypatch.setenv(FIREWORKS_MODEL_PIN_ENV, FIREWORKS_KIMI_K2P7_CODE_MODEL)
    label = cortex_brain_label(QWEN_KIMI, state_dir=tmp_path)
    assert "fireworks-api kimi-k2p7-code" in label
    assert "pinned" in label