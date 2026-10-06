#!/usr/bin/env python3
"""The mercury lane retries a transient bad body instead of reporting a dead turn.

Measured 2026-10-06 over eight identical calls to the lane: five answered and three came back
unparseable ("JSONDecodeError: Expecting value: line 1 column 1"), while a hand-made request to
the same endpoint returned HTTP 200 with valid JSON moments later. Nothing about the prompt or
the budget caused it: 256, 700, 1500 and 2000 max tokens all answered, and one 1024 call failed.
So roughly a third of the Architect's turns on a mercury cortex died as "could not complete this
turn". After the retry the same eight calls returned 8 answers, two of them rescued by the retry.

The lane is on the critical path of every mercury turn, so this is pinned rather than trusted.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

MODULE = REPO / "System" / "swarm_mercury_lane.py"


def _lane():
    spec = importlib.util.spec_from_file_location("mercury_lane_under_test", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Completed:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout


def _good_body(text: str = "OK") -> str:
    return json.dumps({"choices": [{"message": {"role": "assistant", "content": text}}],
                       "usage": {"completion_tokens_details": {"reasoning_tokens": 12}}})


@pytest.fixture(autouse=True)
def _no_sleep_and_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """No real pauses, and a stand-in key so the lane does not read the owner's."""
    lane = _lane()
    monkeypatch.setattr(lane, "api_key", lambda: "test-key")
    monkeypatch.setattr(lane.time, "sleep", lambda _s: None)


def test_a_bad_body_is_retried_and_the_answer_is_returned(monkeypatch) -> None:
    """The exact measured failure: an unparseable body, then a good one."""
    lane = _lane()
    bodies = ["", _good_body("recovered")]
    monkeypatch.setattr(lane.subprocess, "run",
                        lambda *_a, **_k: _Completed(bodies.pop(0)))
    out = lane.chat([{"role": "user", "content": "hi"}], write=False)
    assert out["ok"] is True
    assert out["text"] == "recovered"
    assert out["attempts"] == 2


def test_it_gives_up_after_the_configured_attempts_and_says_how_many(monkeypatch) -> None:
    """A permanently broken lane must fail loudly, and the receipt must show the count."""
    lane = _lane()
    monkeypatch.setattr(lane.subprocess, "run", lambda *_a, **_k: _Completed("not json"))
    out = lane.chat([{"role": "user", "content": "hi"}], write=False)
    assert out["ok"] is False
    assert out["attempts"] == lane.MERCURY_ATTEMPTS
    assert "JSONDecodeError" in out["error"]


def test_a_first_try_success_is_not_retried(monkeypatch) -> None:
    """The retry must not cost a second billed call when the first one worked."""
    lane = _lane()
    calls: list[int] = []

    def once(*_a, **_k):
        calls.append(1)
        return _Completed(_good_body())

    monkeypatch.setattr(lane.subprocess, "run", once)
    out = lane.chat([{"role": "user", "content": "hi"}], write=False)
    assert out["ok"] is True
    assert out["attempts"] == 1
    assert len(calls) == 1


def test_the_reasoning_only_answer_still_says_what_went_wrong(monkeypatch) -> None:
    """A valid body with empty content is a different failure and keeps its own message."""
    lane = _lane()
    body = json.dumps({"choices": [{"message": {"role": "assistant", "content": None}}],
                       "usage": {"completion_tokens_details": {"reasoning_tokens": 238}}})
    monkeypatch.setattr(lane.subprocess, "run", lambda *_a, **_k: _Completed(body))
    out = lane.chat([{"role": "user", "content": "hi"}], write=False)
    assert out["ok"] is False
    assert "spent reasoning" in out["error"]
    assert out["reasoning_tokens"] == 238


def test_the_web_node_routes_mercury_off_ollama() -> None:
    """The web node must not post a cloud model to Ollama, which answers 404 for it.

    `_cortex_turn` is the routing seam; a regression that sends the selected cortex straight to
    Ollama brings back "My selected cortex could not complete this turn" for every mercury turn.
    """
    worker_path = REPO / "System" / "swarm_web_global_chat_night_worker.py"
    source = worker_path.read_text(encoding="utf-8")
    assert "def _cortex_turn(" in source
    assert source.count("_cortex_turn(selected") == 2, "both turn paths must route through it"
    assert "_ollama_turn(selected" not in source, "no path may post the chosen cortex to Ollama"
