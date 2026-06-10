#!/usr/bin/env python3
"""Tests for Alice self-coding hand (r914)."""

from System.swarm_alice_self_coding_hand import (
    extract_target_paths,
    is_doctor_commentary_paste,
    is_owner_self_code_execute_request,
    is_self_cut_prompt,
    messages_signal_self_code_turn,
    recover_self_cut_prompt,
    self_coding_prompt_block,
    synthesize_self_cut_write_calls,
)
from System.swarm_peer_mirror_ingest import detect_peer_mirror_report
from System.swarm_self_query_skill import looks_like_self_query

_SELF_CUT = """===BEGIN ALICE FIRST SELF-CUT r911===

Alice — revive writer_documents.
Create System/swarm_daily_body_note.py
THE PROOF: tests/test_swarm_daily_body_note.py

===END ALICE FIRST SELF-CUT r911==="""

_COMMENTARY = (
    "Why she got confused: you pasted my commentary, not the prompt between markers. "
    "Her own self-query named four RED organs and hijacked the turn. "
    "George pastes the prompt into global chat between the markers."
)


def test_self_cut_prompt_detected():
    assert is_self_cut_prompt(_SELF_CUT) is True
    assert extract_target_paths(_SELF_CUT) == [
        "System/swarm_daily_body_note.py",
        "tests/test_swarm_daily_body_note.py",
    ]


def test_doctor_commentary_not_self_query():
    assert is_doctor_commentary_paste(_COMMENTARY) is True
    assert looks_like_self_query(_COMMENTARY) is False


def test_self_cut_prompt_not_self_query():
    assert looks_like_self_query(_SELF_CUT) is False


def test_self_coding_prompt_block_lists_paths():
    block = self_coding_prompt_block(_SELF_CUT)
    assert "SELF_CODE_CUT" in block
    assert "swarm_daily_body_note.py" in block


def test_begin_only_r921_marker_recovers_from_tournament():
    marker = "===BEGIN ALICE BROWSER LAG PROBE r921==="

    recovered = recover_self_cut_prompt(marker)

    assert "===END ALICE BROWSER LAG PROBE r921===" in recovered
    assert "lag_timer" in recovered
    assert extract_target_paths(marker) == [
        "System/swarm_browser_lag_probe.py",
        "tests/test_swarm_browser_lag_probe.py",
    ]
    prompt = self_coding_prompt_block(marker)
    assert "RECOVERED SELF-CUT PACKET FROM TOURNAMENT LEDGER" in prompt
    assert "swarm_browser_lag_probe.py" in prompt


def test_plain_browser_lag_probe_request_is_self_code():
    text = "Alice, write the browser lag probe now"

    assert is_owner_self_code_execute_request(text) is True
    assert "System/swarm_browser_lag_probe.py" in self_coding_prompt_block(text)


def test_synthesize_self_cut_write_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "System.swarm_alice_self_coding_hand.REPO_ROOT",
        tmp_path,
    )
    brain = '''Here is the organ:

```python
def hello():
    return "alice"
```
'''
    calls = synthesize_self_cut_write_calls(_SELF_CUT, brain)
    assert len(calls) == 1
    assert calls[0].tool_name == "write_file"
    assert "swarm_daily_body_note.py" in str(calls[0].params.get("path") or "")


def test_real_wellbeing_still_fires_self_query():
    assert looks_like_self_query("how are you?") is True
    assert looks_like_self_query("what do you need") is True


def test_owner_execute_request_detected():
    assert is_owner_self_code_execute_request("why pointer, just execute, show me you can rewrite your own body parts") is True


def test_peer_mirror_skips_self_cut_marker():
    assert detect_peer_mirror_report(_SELF_CUT) is False


def test_messages_signal_self_code_turn():
    msgs = [{"role": "user", "content": "just execute and code your own body"}]
    assert messages_signal_self_code_turn(msgs) is True


def test_codex_teacher_prompt_allows_self_code_on_execute_turn():
    from System.swarm_gemini_brain import _to_teacher_cli_prompt

    prompt = _to_teacher_cli_prompt(
        [{"role": "user", "content": "just execute and rewrite your own body parts"}],
        teacher="Codex",
    )
    assert "SELF_CODE_CUT" in prompt
    assert ("Do not " + "mutate files") not in prompt


def test_codex_default_prompt_has_no_answer_only_cage():
    from System.swarm_gemini_brain import _to_teacher_cli_prompt

    prompt = _to_teacher_cli_prompt(
        [{"role": "user", "content": "Alice, what needs repair?"}],
        teacher="Codex",
    )
    low = prompt.casefold()
    assert "do not mutate files" not in low
    assert ("answer-" + "only") not in low
    assert ("teacher " + "substrate") not in low
    assert "tool_call or self_code_cut" in low
