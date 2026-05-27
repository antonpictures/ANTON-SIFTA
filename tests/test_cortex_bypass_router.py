from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from Applications import sifta_talk_to_alice_widget as talk
except Exception as exc:  # noqa: BLE001
    pytest.skip(
        f"Skipping cortex-bypass router tests: widget import failed ({type(exc).__name__}: {exc})",
        allow_module_level=True,
    )


class _FakeRouterWidget:
    def __init__(self) -> None:
        self._history: list[dict[str, str]] = []
        self._busy = True
        self.user_lines: list[tuple[str, float]] = []
        self.alice_lines: list[str] = []
        self.grok_calls: list[str] = []
        self.return_to_listening_calls = 0

    def _append_user_line(self, text: str, conf: float) -> None:
        self.user_lines.append((text, conf))

    def _append_alice_line(self, text: str) -> None:
        self.alice_lines.append(text)

    def _return_to_listening(self) -> None:
        self.return_to_listening_calls += 1

    def _bring_up_grok_in_global_chat(self, text: str, delegate: bool = True) -> str:
        self.grok_calls.append(text)
        return "Grok dispatched. receipt=delegation_intent_test."

    def _maybe_start_observable_direct_tool_request(self, *args, **kwargs) -> bool:
        return False


def test_router_stands_down_on_six_greeter_punchthrough_fixtures(tmp_path, monkeypatch):
    monkeypatch.setattr(talk, "_state_root", lambda: tmp_path)
    widget = _FakeRouterWidget()
    prompts = [
        "Alice, ask Grok to code Round 20 inside the SIFTA matrix-terminal PTY and write work_receipt.",
        "Alice, dispatch Grok now and run py_compile then pytest with receipt output.",
        "Alice, paste this to Grok arm and code Round 21 with FIELD_FAILURE contract.",
        "Alice, ask Grok to run tournament milestone and print tests_run + receipt_id.",
        "Alice, dispatch Grok headless mode and record episodic_diary milestone.",
        "Alice, ask Grok to code round patch, run pytest, and append work_receipt.",
    ]

    for prompt in prompts:
        routed = talk.TalkToAliceWidget._maybe_route_operational_prompt_before_cortex(
            widget,
            prompt,
            1.0,
            already_displayed=False,
            already_logged=False,
        )
        assert routed is False

    assert widget.grok_calls == []
    assert widget.alice_lines == []
    assert widget._history == []

    trace_path = tmp_path / "cortex_bypass_router_trace.jsonl"
    rows = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 6
    assert all(row.get("action_taken") == "router_disabled_round35_fallthrough" for row in rows)
    assert all(row.get("arm_skill_path") == "" for row in rows)


def test_natural_arm_dispatch_is_not_direct_tool_routed():
    text = talk._owner_direct_read_tool_request(
        "Alice, dispatch Grok and run pytest with work_receipt output."
    )

    assert text == ""


@pytest.mark.parametrize(
    "owner_text",
    [
        "Alice, dispatch your codex arm now to read the tournament file and code the next item.",
        "Alice, dispatch your Codex arm to read Documents/TOURNAMENT_PLAN_2026-05-26.md and code the next teaching gate.",
        "Alice, ask grok to read Documents/TOURNAMENT_PLAN_2026-05-26.md and code the lost-Alice fix.",
        "Alice, ask your Grok arm to read Documents/TOURNAMENT_PLAN_2026-05-26.md and code the next teaching gate.",
        "Alice, use your Hermes arm to read file:///Users/ioanganton/Music/ANTON_SIFTA/.sifta_state/eval/ORGAN_EVAL_MATRIX_V2.html",
        "Alice, tell Claude Code to inspect the repo and patch the cortex-first gate.",
        "Alice, have Codex build the Round 47 restart loader and print receipt_id.",
    ],
)
def test_natural_language_arm_delegation_reaches_cortex_first(owner_text):
    """Round 47B: dispatch/ask arm to read/code wording reaches cortex first."""
    text = talk._owner_direct_read_tool_request(owner_text)

    assert text == ""


def test_explicit_tool_call_syntax_still_routes_after_cortex_composes():
    from System.swarm_tool_router import parse_tool_calls

    explicit = (
        "[TOOL_CALL: read_file | path=Documents/IDE_BOOT_COVENANT.md | "
        "cost_justification=cortex explicitly requested a receipt-backed read]"
    )

    text = talk._owner_direct_read_tool_request(explicit)
    calls = parse_tool_calls(text)

    assert text == explicit
    assert len(calls) == 1
    assert calls[0].tool_name == "read_file"
