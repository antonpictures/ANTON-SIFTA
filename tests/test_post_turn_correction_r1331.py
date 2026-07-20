"""Post-turn self-correction — r1331."""
from __future__ import annotations

import json
import time

from System.swarm_post_turn_correction import (
    check_action_prediction_mistake,
    check_owner_correction,
    check_provider_mismatch,
    run_post_turn_correction,
)


def test_provider_mismatch_writes_signal(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    ledger = sd / "search_provider_reality.jsonl"
    ledger.write_text(
        json.dumps({
            "schema": "SEARCH_PROVIDER_REALITY_ROW_V1",
            "ts": time.time(),
            "owner_phrase": "SEARCH ON GOOGLE PLS",
            "execution_provider": "duckduckgo",
            "execution_url": "https://duckduckgo.com/?q=test",
            "provider_mismatch": True,
            "requested_brand_or_verb": "google",
        }) + "\n",
        encoding="utf-8",
    )
    signal = check_provider_mismatch(state_dir=tmp_path)
    assert signal is not None
    assert signal["source"] == "post_turn_provider_mismatch"
    assert signal["severity"] == "yellow"
    assert "duckduckgo" in signal["summary"].lower()


def test_no_mismatch_returns_none(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    ledger = sd / "search_provider_reality.jsonl"
    ledger.write_text(
        json.dumps({
            "schema": "SEARCH_PROVIDER_REALITY_ROW_V1",
            "ts": time.time(),
            "provider_mismatch": False,
        }) + "\n",
        encoding="utf-8",
    )
    assert check_provider_mismatch(state_dir=tmp_path) is None


def test_action_mistake_writes_signal(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    ledger = sd / "action_prediction.jsonl"
    ledger.write_text(
        json.dumps({
            "ts": time.time(),
            "outcome": "MISTAKE",
            "expected": "browser opens search results",
            "actual": "error: timeout",
        }) + "\n",
        encoding="utf-8",
    )
    signal = check_action_prediction_mistake(state_dir=tmp_path)
    assert signal is not None
    assert signal["source"] == "post_turn_action_mistake"
    assert "MISTAKE" in signal["summary"]


def test_owner_correction_detects_keywords(tmp_path):
    signal = check_owner_correction(state_dir=tmp_path, owner_text="that's wrong, fix this bug")
    assert signal is not None
    assert signal["source"] == "post_turn_owner_correction"


def test_owner_correction_ignores_non_correction(tmp_path):
    signal = check_owner_correction(state_dir=tmp_path, owner_text="search google for cats")
    assert signal is None


def test_run_post_turn_correction_empty(tmp_path):
    result = run_post_turn_correction(state_dir=tmp_path)
    assert result["body_execution_written"] is True
    assert result["signals_written"] == 0


def test_run_post_turn_correction_with_mismatch(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    ledger = sd / "search_provider_reality.jsonl"
    ledger.write_text(
        json.dumps({
            "schema": "SEARCH_PROVIDER_REALITY_ROW_V1",
            "ts": time.time(),
            "provider_mismatch": True,
            "requested_brand_or_verb": "google",
            "execution_provider": "duckduckgo",
            "execution_url": "https://duckduckgo.com/?q=test",
        }) + "\n",
        encoding="utf-8",
    )
    result = run_post_turn_correction(state_dir=tmp_path)
    assert result["body_execution_written"] is True
    assert result["signals_written"] >= 1
    dispatch = sd / "self_eval_swimmer_dispatch.jsonl"
    assert dispatch.exists()
    rows = [json.loads(l) for l in dispatch.read_text().splitlines() if l.strip()]
    assert any(r["source"] == "post_turn_provider_mismatch" for r in rows)
