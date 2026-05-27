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


def test_router_fires_on_six_greeter_punchthrough_fixtures(tmp_path, monkeypatch):
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
        assert routed is True

    assert len(widget.grok_calls) == 6
    assert len(widget.alice_lines) == 6
    assert len(widget._history) == 12
    for reply in widget.alice_lines:
        low = reply.lower()
        assert reply.startswith("[ARM SKILL skills/grok_pty_arm.md]")
        assert "hello" not in low
        assert "i feel" not in low
        assert "i sense" not in low
        assert "i am here" not in low
        assert "low-frequency vibration" not in low

    trace_path = tmp_path / "cortex_bypass_router_trace.jsonl"
    rows = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 6
    assert all(row.get("action_taken") == "dispatched_grok_pty_from_skill" for row in rows)
    assert all(row.get("arm_skill_path") == "skills/grok_pty_arm.md" for row in rows)


def test_start_brain_short_circuits_llm_when_router_consumes(monkeypatch):
    class _FakeStartBrainWidget:
        def __init__(self) -> None:
            self._busy = True
            self._pending_acoustic_fingerprint = {}
            self.router_called = False

        def _maybe_route_operational_prompt_before_cortex(self, *args, **kwargs) -> bool:
            self.router_called = True
            return True

    widget = _FakeStartBrainWidget()
    monkeypatch.setattr(talk, "_deterministic_prebrain_reflex", lambda *a, **k: ("", ""))

    class _FailIfConstructed:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ARG002
            raise AssertionError("LLM worker should not be constructed when router consumes turn")

    monkeypatch.setattr(talk, "_BrainWorker", _FailIfConstructed)

    talk.TalkToAliceWidget._start_brain(
        widget,
        "Alice, dispatch Grok and run pytest with work_receipt output.",
        conf=0.92,
        already_displayed=True,
    )

    assert widget.router_called is True
