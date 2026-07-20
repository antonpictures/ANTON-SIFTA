from __future__ import annotations

import json


def test_timeout_policy_starts_at_base_without_receipts(tmp_path):
    from System.swarm_stigmergic_timeout_policy import timeout_for_model

    decision = timeout_for_model("mimo:mimo-cli-default", state_dir=tmp_path)

    assert decision["timeout_s"] == 120
    assert decision["truth_label"] == "DEFAULT_NO_PRIOR"


def test_timeout_policy_raises_after_timeout_receipts(tmp_path):
    from System.swarm_stigmergic_timeout_policy import (
        record_timeout_outcome,
        timeout_for_model,
    )

    record_timeout_outcome(
        "mimo:mimo-cli-default",
        outcome="timeout",
        timeout_s=120,
        elapsed_s=120,
        state_dir=tmp_path,
    )

    decision = timeout_for_model("mimo:mimo-cli-default", state_dir=tmp_path)

    assert decision["timeout_s"] == 180
    assert decision["recent_failures"] == 1
    assert decision["last_outcome"] == "timeout"


def test_timeout_policy_lowers_after_fast_successes(tmp_path):
    from System.swarm_stigmergic_timeout_policy import (
        record_timeout_outcome,
        timeout_for_model,
    )

    for _ in range(3):
        record_timeout_outcome(
            "mimo:mimo-cli-default",
            outcome="success",
            timeout_s=120,
            elapsed_s=12,
            state_dir=tmp_path,
        )

    decision = timeout_for_model("mimo:mimo-cli-default", state_dir=tmp_path)

    assert decision["timeout_s"] == 75
    assert decision["recent_fast_successes"] == 3


def test_timeout_policy_reads_existing_recovery_receipts(tmp_path):
    from System.swarm_stigmergic_timeout_policy import timeout_for_model

    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "cortex_timeout_recovery.jsonl").write_text(
        json.dumps({
            "model": "mimo:mimo-cli-default",
            "timeout_s": 120,
            "trace_id": "t1",
            "ts": 1.0,
        }) + "\n",
        encoding="utf-8",
    )

    decision = timeout_for_model("mimo:mimo-cli-default", state_dir=state)

    assert decision["timeout_s"] == 180
    assert decision["truth_label"] == "OBSERVED"


def test_first_token_patience_learns_model_latency_percentile(tmp_path):
    from System.swarm_stigmergic_timeout_policy import (
        first_token_patience_for_model,
        record_timeout_outcome,
    )

    for latency in (18.0, 20.0, 22.0):
        record_timeout_outcome(
            "mimo:mimo-cli-default",
            outcome="first_token",
            timeout_s=45,
            elapsed_s=latency,
            first_token_latency_s=latency,
            state_dir=tmp_path,
        )

    decision = first_token_patience_for_model(
        "mimo:mimo-cli-default",
        state_dir=tmp_path,
        floor_s=12,
        default_s=12,
        max_s=90,
    )

    assert decision["truth_label"] == "OBSERVED"
    assert decision["sample_count"] == 3
    assert decision["patience_s"] > 22.0


def test_first_token_patience_uses_no_token_censored_receipts(tmp_path):
    from System.swarm_stigmergic_timeout_policy import first_token_patience_for_model

    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "cortex_timeout_recovery.jsonl").write_text(
        json.dumps({
            "model": "grok:grok-4.3",
            "timeout_s": 20,
            "trace_id": "no-token-1",
            "cause": "no_token_watchdog",
            "ts": 1.0,
        }) + "\n",
        encoding="utf-8",
    )

    decision = first_token_patience_for_model(
        "grok:grok-4.3",
        state_dir=state,
        floor_s=12,
        default_s=12,
        max_s=90,
    )

    assert decision["censored_sample_count"] == 1
    assert decision["patience_s"] > 20.0


def test_local_fallback_for_mimo_is_observed_gemma4_tag(monkeypatch):
    from System import sifta_inference_defaults
    from System.swarm_stigmergic_timeout_policy import local_fallback_for_model

    monkeypatch.setattr(sifta_inference_defaults, "resolve_live_local_ollama_default", lambda: "")

    assert local_fallback_for_model("mimo:mimo-cli-default") == (
        "krishairnd/Gemma-4-Uncensored:latest"
    )
    assert local_fallback_for_model("claude:opus") == ""


def test_fast_fallback_after_recent_timeout(tmp_path, monkeypatch):
    import time

    from System import sifta_inference_defaults
    from System.swarm_stigmergic_timeout_policy import (
        record_timeout_outcome,
        should_fast_fallback_cloud,
    )

    monkeypatch.setattr(sifta_inference_defaults, "resolve_live_local_ollama_default", lambda: "")

    record_timeout_outcome(
        "mimo:mimo-cli-default",
        outcome="timeout",
        timeout_s=240,
        elapsed_s=240,
        state_dir=tmp_path,
    )

    row = should_fast_fallback_cloud("mimo:mimo-cli-default", state_dir=tmp_path)

    assert row["fast_fallback"] is True
    assert row["local_fallback"] == "krishairnd/Gemma-4-Uncensored:latest"
    assert row["last_outcome"] == "timeout"


def test_fast_fallback_evaporates_after_cooldown(tmp_path):
    import time

    from System.swarm_stigmergic_timeout_policy import (
        record_timeout_outcome,
        should_fast_fallback_cloud,
    )

    state = tmp_path / ".sifta_state"
    state.mkdir()
    path = state / "stigmergic_timeout_policy.jsonl"
    path.write_text(
        json.dumps({
            "model_key": "mimo",
            "model": "mimo:mimo-cli-default",
            "outcome": "timeout",
            "timeout_s": 240,
            "elapsed_s": 240,
            "ts": time.time() - 1200,
        }) + "\n",
        encoding="utf-8",
    )

    row = should_fast_fallback_cloud("mimo:mimo-cli-default", state_dir=state, cooldown_s=900)

    assert row["fast_fallback"] is False
