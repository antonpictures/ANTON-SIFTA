"""tests/test_cortex_selection_mismatch.py — r988, the r985-carried mismatch organ.

The 13:53 incident: George ran /cortex 9 (the 4.4GB e2b), but the thinking
turns that followed are receipted on the 8B. r985 surfaced the per-turn model;
r988 proves the divergence itself — selected vs actual — so it is a receipted
body bug, not a story.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from System.swarm_alice_slash_commands import (  # noqa: E402
    cortex_selection_mismatches,
    handle_slash_command,
    _norm_cortex_tag,
)


def test_norm_collapses_provider_arms_and_local_weights():
    assert _norm_cortex_tag("claude:claude-code-cli-default") == "claude"
    assert _norm_cortex_tag("claude-fable-5") == "claude"
    assert _norm_cortex_tag("cline:cline-cli-default") == "cline"
    # local weight tag is its own identity (no provider prefix)
    assert _norm_cortex_tag("alice-m5-cortex-8b-6.3gb:latest") == "alice-m5-cortex-8b-6.3gb"


def _seed_incident(state: Path) -> None:
    state.mkdir(parents=True, exist_ok=True)
    # George selected the 4.4GB e2b at t=100
    with (state / "cortex_selection_receipts.jsonl").open("w") as f:
        f.write(json.dumps({
            "ts": 100.0, "truth_label": "CORTEX_SELECTION_RECEIPT_V1",
            "selected_model": "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
        }) + "\n")
    # but the thinking turns at t=120/130 ran on the 8B
    with (state / "alice_conversation.jsonl").open("w") as f:
        for ts, text in ((120.0, "You are astute, the truth is the 4.4 GB version"),
                         (130.0, "It is highly likely the 8B was before this session")):
            f.write(json.dumps({"payload": {
                "ts": ts, "role": "alice",
                "model": "alice-m5-cortex-8b-6.3gb:latest", "text": text,
            }}) + "\n")


def test_mismatch_detected_for_the_incident(tmp_path):
    state = tmp_path / "state"
    _seed_incident(state)
    mm = cortex_selection_mismatches(state, n=6)
    assert len(mm) == 2
    assert mm[0]["selected"] == "alice-gemma4-e2b-cortex-5.1b-4.4gb"
    assert mm[0]["actual_model"] == "alice-m5-cortex-8b-6.3gb:latest"


def test_no_mismatch_when_selection_matches(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    with (state / "cortex_selection_receipts.jsonl").open("w") as f:
        f.write(json.dumps({"ts": 100.0, "selected_model": "claude:claude-code-cli-default"}) + "\n")
    with (state / "alice_conversation.jsonl").open("w") as f:
        f.write(json.dumps({"payload": {"ts": 120.0, "role": "alice",
                                        "model": "claude-fable-5", "text": "hi"}}) + "\n")
    assert cortex_selection_mismatches(state, n=6) == []


def test_cortex_history_surfaces_the_mismatch(tmp_path):
    state = tmp_path / "state"
    _seed_incident(state)
    res = handle_slash_command("/cortex history", state_dir=state, current_cortex="")
    reply = res["reply"]
    assert "CORTEX_SELECTION_MISMATCH" in reply
    assert "alice-m5-cortex-8b-6.3gb:latest thought" in reply
    assert "body bug worth a receipt" in reply


def test_empty_state_no_crash(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    assert cortex_selection_mismatches(state) == []
