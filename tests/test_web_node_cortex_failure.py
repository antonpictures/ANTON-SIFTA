#!/usr/bin/env python3
"""A transient Ollama failure must cost a retry, not an answer.

The Architect, 2026-10-06, on the SIFTA web node: "My selected cortex could not complete this
turn. The failure was recorded, and you can try again shortly." — twice, on consecutive turns.

Measured: the web node answered a turn normally, then two turns died, and the same call to the
same model returned HTTP 200 minutes later. The ledger held eleven failures across 25 MB, every
one of them reading `"error": "HTTPError"` — no status code, no model, no body. So the fallback's
claim that "the failure was recorded" was not true in any useful sense.

Two repairs are pinned here: one retry after a short pause when a local server answers 5xx, and
an error record that carries the status code so the next occurrence explains itself. And one
boundary is pinned too: the recovery path must not read a name it cannot see, because a NameError
inside the handler turns a graceful failure into a crash.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
import urllib.error
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

MODULE = REPO / "System" / "swarm_web_global_chat_night_worker.py"


def _load():
    """Load the night worker without starting its loop."""
    spec = importlib.util.spec_from_file_location("night_worker_under_test", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


def _http_error(code: int, reason: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://127.0.0.1:11434/api/chat", code, reason, {}, None)


def test_a_5xx_is_retried_once_and_the_second_answer_is_returned(monkeypatch) -> None:
    """One momentary 500 from localhost must not lose the turn."""
    worker = _load()
    calls: list[int] = []

    def fake_urlopen(_request, timeout=None):  # noqa: ANN001, ARG001
        calls.append(1)
        if len(calls) == 1:
            raise _http_error(500, "Internal Server Error")
        return _FakeResponse(b'{"message": {"content": "recovered"}}')

    monkeypatch.setattr(worker.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(worker.time, "sleep", lambda _s: None)
    out = worker._ollama_turn("AliceG4U:latest", [{"role": "user", "content": "hi"}], timeout_s=5)
    assert len(calls) == 2, "the transient failure must be retried exactly once"
    assert out["message"]["content"] == "recovered"


def test_a_400_still_drops_the_think_field_rather_than_retrying_blindly(monkeypatch) -> None:
    """The original 400 recovery keeps its meaning: rebuild the request without `think`."""
    worker = _load()
    sent: list[bytes] = []

    def fake_urlopen(request, timeout=None):  # noqa: ANN001, ARG001
        sent.append(request.data)
        if len(sent) == 1:
            raise _http_error(400, "Bad Request")
        return _FakeResponse(b'{"message": {"content": "ok"}}')

    monkeypatch.setattr(worker.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(worker.time, "sleep", lambda _s: None)
    out = worker._ollama_turn("some-model", [{"role": "user", "content": "hi"}], timeout_s=5)
    assert b'"think"' in sent[0]
    assert b'"think"' not in sent[1], "the retry must drop the field that was rejected"
    assert out["message"]["content"] == "ok"


def test_a_4xx_that_is_not_400_is_not_retried(monkeypatch) -> None:
    """A real client error is not a momentary one; retrying it would only repeat the failure."""
    worker = _load()
    calls: list[int] = []

    def fake_urlopen(_request, timeout=None):  # noqa: ANN001, ARG001
        calls.append(1)
        raise _http_error(404, "Not Found")

    monkeypatch.setattr(worker.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(worker.time, "sleep", lambda _s: None)
    with pytest.raises(urllib.error.HTTPError):
        worker._ollama_turn("missing-model", [{"role": "user", "content": "hi"}], timeout_s=5)
    assert len(calls) == 1, "a 404 must fail immediately, not be retried"


def test_the_failure_record_carries_the_status_code() -> None:
    """`str(exc)` is what survives into the ledger; the type alone told us nothing."""
    source = MODULE.read_text(encoding="utf-8")
    assert 'error=f"{type(exc).__name__}: {str(exc)[:300]}"' in source
    assert 'error=type(exc).__name__' not in source, "the bare type record must be gone"


def test_the_recovery_path_reads_no_name_it_cannot_see() -> None:
    """A NameError inside the handler turns a graceful failure into a crash.

    `selected` is bound INSIDE the try, so if the failing call is the very one that assigns it,
    it is unbound by the time the handler runs. Naming it in the recovery path was written once
    during this repair and removed before it shipped; this test keeps it out. Only the handlers
    are checked, because `selected` is legitimately read on the success path that precedes them.
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    function = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == "process_claimed_turn")
    handlers = [handler for node in ast.walk(function)
                if isinstance(node, ast.Try) for handler in node.handlers]
    assert handlers, "the recovery handler must exist"
    for handler in handlers:
        read_names = {n.id for n in ast.walk(handler)
                      if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        assert "selected" not in read_names, (
            "the handler reads `selected`, which is unbound when the failing call is the one "
            "that assigns it: that NameError would replace a graceful failure with a crash"
        )
