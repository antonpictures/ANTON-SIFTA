"""
test_swarm_skill_ingest.py
==========================
Offline tests for swarm_skill_ingest. Mocks urllib and the local brain.
Hits the actual hash-chained jsonl in a temp .sifta_state.

Run from System/ (or with PYTHONPATH=System):
    python3 -m pytest -q tests/test_swarm_skill_ingest.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture
def chdir_tmp(tmp_path, monkeypatch):
    """Every test runs in a fresh tmp dir so .sifta_state/ is isolated."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".sifta_state").mkdir()
    (tmp_path / "skills").mkdir()
    yield tmp_path


@pytest.fixture
def fresh_ingest(chdir_tmp):
    """Reload module so its module-level _STATE path picks up the chdir."""
    for mod in list(sys.modules):
        if mod.startswith("swarm_skill_ingest"):
            del sys.modules[mod]
    import swarm_skill_ingest  # noqa
    return swarm_skill_ingest


# ----------------------------------------------------------------------
# Fetch
# ----------------------------------------------------------------------
def _fake_urlopen_response(body: bytes, content_type: str = "text/markdown"):
    class _R:
        def __init__(self):
            self.headers = {"Content-Type": content_type}
            self._buf = io.BytesIO(body)
        def read(self, n=-1):
            return self._buf.read(n)
        def __enter__(self): return self
        def __exit__(self, *a): pass
    return _R()


def test_fetch_refuses_non_http(fresh_ingest):
    with pytest.raises(fresh_ingest.IngestError):
        fresh_ingest.fetch_skill_from_url("file:///etc/passwd")


def test_fetch_success_logs_chain(fresh_ingest, monkeypatch):
    payload = b"---\nname: example\ndescription: x\n---\n# Hello\n"
    monkeypatch.setattr(
        fresh_ingest.urllib.request, "urlopen",
        lambda req, timeout=None: _fake_urlopen_response(payload, "text/markdown"),
    )
    out = fresh_ingest.fetch_skill_from_url("https://example.com/skill.md")
    assert out["url"] == "https://example.com/skill.md"
    assert "Hello" in out["content"]
    assert out["sha256"]
    # Chain: at least START (none in fetch), FETCH, FETCH_RESULT
    log = (Path(".sifta_state") / "skill_ingest.jsonl").read_text().splitlines()
    types_ = [json.loads(line)["type"] for line in log if line.strip()]
    assert "INGEST_FETCH" in types_
    assert "INGEST_FETCH_RESULT" in types_


# ----------------------------------------------------------------------
# Evaluate
# ----------------------------------------------------------------------
def _make_fake_brain(response_text: str):
    """Build a module-like object with .stream_chat that yields a fake stream."""
    def stream_chat(model, messages, request_tag=None, **kwargs):
        yield ("token", response_text[:20])
        yield ("done", response_text)
    fake = types.SimpleNamespace(
        stream_chat=stream_chat,
        available_models=lambda: ["ollama:fake-model"],
    )
    return fake


def test_evaluate_like_returns_converted_md(fresh_ingest):
    brain_text = (
        "VERDICT: LIKE\n"
        "REASON: Teaches Alice to list directory contents safely.\n"
        "CONVERTED_MD:\n"
        "---\n"
        "name: list-current-directory\n"
        "description: list files in cwd\n"
        "when_to_use: when asked what is in this folder\n"
        "---\n"
        "# List current directory\n\nUse list_dir with path='.'\n"
    )
    fake_brain = _make_fake_brain(brain_text)
    fetched = {"url": "https://x/y", "content": "raw skill text", "content_type": "text/markdown"}
    res = fresh_ingest.evaluate_skill_with_alice(fetched, brain=fake_brain)
    assert res["verdict"] == "LIKE"
    assert "list_dir" in res["converted_md"]
    assert "list-current-directory" in res["converted_md"]


def test_evaluate_skip_no_converted_md(fresh_ingest):
    brain_text = "VERDICT: SKIP\nREASON: References a paid SaaS API Alice cannot reach.\n"
    fake_brain = _make_fake_brain(brain_text)
    res = fresh_ingest.evaluate_skill_with_alice(
        {"url": "https://x/y", "content": "raw", "content_type": "text/markdown"},
        brain=fake_brain,
    )
    assert res["verdict"] == "SKIP"
    assert res["converted_md"] is None


def test_evaluate_like_without_body_falls_back_to_skip(fresh_ingest):
    brain_text = "VERDICT: LIKE\nREASON: looks fine\n"  # no CONVERTED_MD section
    fake_brain = _make_fake_brain(brain_text)
    res = fresh_ingest.evaluate_skill_with_alice(
        {"url": "https://x/y", "content": "raw", "content_type": "text/markdown"},
        brain=fake_brain,
    )
    assert res["verdict"] == "SKIP"


# ----------------------------------------------------------------------
# Install
# ----------------------------------------------------------------------
def test_install_writes_and_logs(fresh_ingest):
    md = ("---\nname: example-skill\ndescription: d\nwhen_to_use: w\n---\n"
          "# Example\n\nDo the thing.\n")
    res = fresh_ingest.install_skill(md, source_url="https://x/y")
    assert res["ok"]
    assert Path(res["path"]).exists()
    log = (Path(".sifta_state") / "skill_ingest.jsonl").read_text().splitlines()
    types_ = [json.loads(line)["type"] for line in log if line.strip()]
    assert "INGEST_INSTALL" in types_


def test_install_dedupes_slug(fresh_ingest):
    md = "---\nname: dup\ndescription: d\nwhen_to_use: w\n---\nA\n"
    r1 = fresh_ingest.install_skill(md, source_url="https://x/1")
    r2 = fresh_ingest.install_skill(md, source_url="https://x/2")
    assert r1["ok"] and r2["ok"]
    assert r1["path"] != r2["path"]
    assert "dup-1" in r2["slug"] or "dup-1" in r2["path"]


# ----------------------------------------------------------------------
# Top-level wrapper — Hermes-format end-to-end (Lane 2 receipt)
# ----------------------------------------------------------------------
HERMES_FORMAT_SKILL = b"""{
  "name": "summarize_file",
  "description": "Read a file and emit a 3-sentence summary.",
  "category": "filesystem",
  "instructions": "Use read_file then produce a summary in markdown.",
  "input_schema": {"path": "string"},
  "version": "1.0.0"
}
"""

AGENTSKILLS_FORMAT_SKILL = b"""---
name: search-recent-news
description: Search the web for recent news about a topic
trigger: user asks about current events
---
# Search recent news

Use search_web with the user's topic, then fetch_url on the top result.
"""


def test_ingest_skill_hermes_format_end_to_end(fresh_ingest, monkeypatch):
    """Lane 2 receipt — Hermes-format JSON skill goes through full pipeline."""
    monkeypatch.setattr(
        fresh_ingest.urllib.request, "urlopen",
        lambda req, timeout=None: _fake_urlopen_response(HERMES_FORMAT_SKILL, "application/json"),
    )
    fake_brain = _make_fake_brain(
        "VERDICT: LIKE\n"
        "REASON: Useful summarization wrapper around read_file.\n"
        "CONVERTED_MD:\n"
        "---\n"
        "name: summarize-file\n"
        "description: Read a file and emit a 3-sentence summary.\n"
        "when_to_use: when the user asks for a quick summary of a file\n"
        "---\n"
        "# Summarize file\n\n1. Call read_file with the provided path.\n"
        "2. Emit a 3-sentence summary in markdown.\n"
    )
    # Patch _resolve_brain so the function picks up our fake even though
    # swarm_local_brain isn't on disk in the test env.
    monkeypatch.setattr(fresh_ingest, "_resolve_brain", lambda b: b or fake_brain)
    res = fresh_ingest.ingest_skill(
        "https://example.com/hermes-skill.json",
        cost_justification="user asked Alice to borg a Hermes skill",
        brain=fake_brain,
    )
    assert res["verdict"] == "LIKE"
    assert res["install"] is not None
    assert res["install"]["ok"]
    assert Path(res["install"]["path"]).exists()
    body = Path(res["install"]["path"]).read_text()
    assert "summarize-file" in body
    assert "read_file" in body


def test_ingest_skill_agentskills_format(fresh_ingest, monkeypatch):
    monkeypatch.setattr(
        fresh_ingest.urllib.request, "urlopen",
        lambda req, timeout=None: _fake_urlopen_response(AGENTSKILLS_FORMAT_SKILL, "text/markdown"),
    )
    fake_brain = _make_fake_brain(
        "VERDICT: LIKE\nREASON: Useful current-events workflow.\n"
        "CONVERTED_MD:\n---\nname: search-recent-news\n"
        "description: Search the web for recent news\n"
        "when_to_use: user asks about current events\n---\n"
        "# Search recent news\n\nCall search_web with the topic.\n"
    )
    monkeypatch.setattr(fresh_ingest, "_resolve_brain", lambda b: b or fake_brain)
    res = fresh_ingest.ingest_skill(
        "https://example.com/skill.md",
        cost_justification="testing agentskills-style ingest",
        brain=fake_brain,
    )
    assert res["verdict"] == "LIKE"
    assert res["install"]["ok"]


def test_ingest_chain_is_continuous(fresh_ingest, monkeypatch):
    """Every row's prev == previous row's hash."""
    monkeypatch.setattr(
        fresh_ingest.urllib.request, "urlopen",
        lambda req, timeout=None: _fake_urlopen_response(AGENTSKILLS_FORMAT_SKILL, "text/markdown"),
    )
    fake_brain = _make_fake_brain(
        "VERDICT: LIKE\nREASON: x\nCONVERTED_MD:\n---\nname: chain-test\n"
        "description: d\nwhen_to_use: w\n---\n# t\n"
    )
    monkeypatch.setattr(fresh_ingest, "_resolve_brain", lambda b: b or fake_brain)
    fresh_ingest.ingest_skill("https://x/y", "test", brain=fake_brain)

    log = Path(".sifta_state/skill_ingest.jsonl").read_text().splitlines()
    rows = [json.loads(line) for line in log if line.strip()]
    assert len(rows) >= 3
    for i in range(1, len(rows)):
        assert rows[i]["prev"] == rows[i - 1]["hash"], (
            f"chain break at row {i}: prev={rows[i]['prev']!r} expected={rows[i - 1]['hash']!r}"
        )
