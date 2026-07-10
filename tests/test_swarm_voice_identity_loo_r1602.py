#!/usr/bin/env python3
"""r1602 VA1 — leave-one-out ≥85% with owner margin ≥0.15."""
from __future__ import annotations

from pathlib import Path

from System.swarm_voice_identity_organ import (
    PRIMARY_OPERATOR_VOICE_LABEL,
    leave_one_out_eval,
    seed_discriminative_bank,
    extract_features,
    classify,
    synthesize_class_audio,
    is_learn_my_voice_command,
    start_voice_enrollment,
    enroll_audio_clip,
    voice_verdict_snapshot,
)


def test_leave_one_out_passes_accuracy_and_margin(tmp_path: Path) -> None:
    ledger = tmp_path / "voice_identity_ledger.jsonl"
    seed_discriminative_bank(per_class=6, ledger_path=ledger)
    result = leave_one_out_eval(ledger_path=ledger, write_receipt=False)
    assert result["n"] >= 20
    assert result["accuracy"] >= 0.85, result
    assert result["min_primary_margin"] >= 0.15, result
    assert result["passes"] is True
    assert result["per_label"][PRIMARY_OPERATOR_VOICE_LABEL]["accuracy"] >= 0.85


def test_feature_version_is_v2() -> None:
    audio = synthesize_class_audio(PRIMARY_OPERATOR_VOICE_LABEL, seed=1)
    feat = extract_features(audio)
    assert feat.get("feature_version") == 2
    assert len(feat.get("mfcc") or []) >= 20
    assert "mfcc_delta" in feat and "mfcc_delta2" in feat
    assert "f0_mean" in feat


def test_youtube_does_not_outscore_owner_on_owner_audio(tmp_path: Path) -> None:
    ledger = tmp_path / "voice_identity_ledger.jsonl"
    seed_discriminative_bank(per_class=5, ledger_path=ledger)
    from System.swarm_voice_identity_organ import load_exemplars

    exs = load_exemplars(ledger_path=ledger)
    audio = synthesize_class_audio(PRIMARY_OPERATOR_VOICE_LABEL, seed=42)
    pred = classify(extract_features(audio), exs)
    assert pred["label"] == PRIMARY_OPERATOR_VOICE_LABEL
    assert float(pred.get("owner_margin") or 0.0) >= 0.15


def test_learn_my_voice_command_phrases() -> None:
    assert is_learn_my_voice_command("Alice, learn my voice")
    assert is_learn_my_voice_command("please enroll my voice now")
    assert not is_learn_my_voice_command("what is my voiceprint score")


def test_enrollment_session_captures_and_scores(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    ledger = state / "voice_identity_ledger.jsonl"
    # seed competitors so LOO is multi-class
    seed_discriminative_bank(
        per_class=3,
        ledger_path=ledger,
        classes=["youtube", "keyboard", "environment"],
    )
    sess = start_voice_enrollment(n_clips=3, state_dir=state)
    assert sess["status"] == "active"
    for i in range(3):
        audio = synthesize_class_audio(PRIMARY_OPERATOR_VOICE_LABEL, seed=200 + i)
        r = enroll_audio_clip(audio, state_dir=state, ledger_path=ledger)
        assert r["ok"] is True
    assert r.get("complete") is True
    assert "loo" in r
    assert float(r["loo"]["accuracy"]) >= 0.0  # multi-class with owner now present
    assert (state / "voice_identity_loo_receipts.jsonl").exists()
    snap = voice_verdict_snapshot(state_dir=state, ledger_path=ledger)
    assert snap["loo_accuracy"] == r["loo"]["accuracy"]


def test_voice_verdict_snapshot(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    ledger = state / "voice_identity_ledger.jsonl"
    seed_discriminative_bank(per_class=2, ledger_path=ledger)
    snap = voice_verdict_snapshot(
        last_confidence=0.72,
        media_active=True,
        state_dir=state,
        ledger_path=ledger,
    )
    assert snap["media_context_active"] is True
    assert snap["owner_match_confidence"] == 0.72
    assert snap["primary_operator_n"] >= 2
