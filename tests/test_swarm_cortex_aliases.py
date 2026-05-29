"""Round 99 tests — cortex alias resolver.

Alice (or George) can say ``cheap`` / ``long`` / ``kimi`` / ``premium`` etc.
and the resolver maps it to the canonical cortex tag. Pure stdlib tests;
no live cortex switch.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from System import swarm_cortex_aliases as ca
from System import sifta_inference_defaults as defaults


# ─── Pure resolver ────────────────────────────────────────────────────────


def test_cheap_resolves_to_gpt_oss_20b():
    assert ca.resolve_cortex_alias("cheap") == defaults.CANONICAL_CLOUD_QWEN
    assert defaults.CANONICAL_CLOUD_QWEN.endswith("gpt-oss-20b")


def test_premium_resolves_to_kimi():
    assert ca.resolve_cortex_alias("kimi") == defaults.CANONICAL_CLOUD_QWEN_PREMIUM_KIMI
    assert ca.resolve_cortex_alias("premium") == defaults.CANONICAL_CLOUD_QWEN_PREMIUM_KIMI
    assert ca.resolve_cortex_alias("vision") == defaults.CANONICAL_CLOUD_QWEN_PREMIUM_KIMI


def test_long_resolves_to_deepseek_flash():
    assert ca.resolve_cortex_alias("long") == defaults.CANONICAL_CLOUD_QWEN_LONG_DEEPSEEK_FLASH
    assert ca.resolve_cortex_alias("deepseek") == defaults.CANONICAL_CLOUD_QWEN_LONG_DEEPSEEK_FLASH


def test_local_resolves_to_m5_8b():
    assert ca.resolve_cortex_alias("local") == defaults.CANONICAL_OLLAMA_DAILY
    assert ca.resolve_cortex_alias("smart") == defaults.CANONICAL_OLLAMA_DAILY
    assert ca.resolve_cortex_alias("8b") == defaults.CANONICAL_OLLAMA_DAILY


def test_tiny_resolves_to_gemma_small():
    assert ca.resolve_cortex_alias("tiny") == defaults.CANONICAL_OLLAMA_GEMMA4_SMALL
    assert ca.resolve_cortex_alias("gemma") == defaults.CANONICAL_OLLAMA_GEMMA4_SMALL


def test_grok_claude_codex_cline():
    assert ca.resolve_cortex_alias("grok") == defaults.CANONICAL_CLOUD_GROK
    assert ca.resolve_cortex_alias("claude") == defaults.CANONICAL_CLOUD_CLAUDE
    assert ca.resolve_cortex_alias("codex") == defaults.CANONICAL_CLOUD_CODEX
    assert ca.resolve_cortex_alias("cline") == defaults.CANONICAL_CLOUD_CLINE


# ─── Edge cases ───────────────────────────────────────────────────────────


def test_case_insensitive():
    assert ca.resolve_cortex_alias("CHEAP") == ca.resolve_cortex_alias("cheap")
    assert ca.resolve_cortex_alias("Kimi") == ca.resolve_cortex_alias("kimi")
    assert ca.resolve_cortex_alias("GroK") == ca.resolve_cortex_alias("grok")


def test_whitespace_stripped():
    assert ca.resolve_cortex_alias("  cheap  ") == defaults.CANONICAL_CLOUD_QWEN


def test_unknown_alias_returns_empty():
    assert ca.resolve_cortex_alias("doesnotexist") == ""
    assert ca.resolve_cortex_alias("") == ""
    assert ca.resolve_cortex_alias(None) == ""


def test_canonical_tag_passes_through():
    """If you already have a canonical tag, resolver returns it unchanged."""
    assert ca.resolve_cortex_alias("qwen:accounts/fireworks/models/gpt-oss-20b") == \
        "qwen:accounts/fireworks/models/gpt-oss-20b"
    assert ca.resolve_cortex_alias("alice-m5-cortex-8b-6.3gb:latest") == \
        "alice-m5-cortex-8b-6.3gb:latest"


# ─── list_aliases / groups ────────────────────────────────────────────────


def test_list_aliases_has_expected_groups():
    aliases = ca.list_aliases()
    # All the mood-tagged short names that George should be able to use
    for required in ("cheap", "fast", "long", "kimi", "premium", "local",
                     "tiny", "grok", "claude", "codex", "cline"):
        assert required in aliases, f"missing alias: {required}"


def test_list_canonical_groups_returns_lists():
    groups = ca.list_canonical_groups()
    assert isinstance(groups, dict)
    assert "cheap_cloud_drafter" in groups
    assert "premium_cloud_vision" in groups
    assert "local_smart_8b" in groups
    # Values must be lists (JSON-friendly), not tuples
    for v in groups.values():
        assert isinstance(v, list)


def test_prompt_block_mentions_groups_and_canonical_tags():
    text = ca.cortex_alias_prompt_block()
    assert "CORTEX ALIASES" in text
    assert "cheap" in text and "drafter" in text
    assert "kimi" in text and "vision" in text
    assert "long" in text and "book" in text
    # Has the canonical tag for at least one group so Alice can verify
    assert "gpt-oss-20b" in text or "accounts/fireworks" in text


# ─── set_cortex_by_alias ──────────────────────────────────────────────────


def test_set_by_unknown_alias_returns_not_ok():
    out = ca.set_cortex_by_alias("doesnotexist")
    assert out["ok"] is False
    assert "unknown alias" in out["reason"]
    assert out["alias"] == "doesnotexist"
    assert out["resolved_tag"] == ""


def test_set_by_alias_calls_set_default_ollama_model(monkeypatch):
    """When the alias resolves, we delegate to the existing assignment
    writer instead of touching the JSON file directly."""
    calls = []

    def fake_setter(model: str) -> dict:
        calls.append(model)
        return {"ok": True, "model": model}

    monkeypatch.setattr(ca, "set_default_ollama_model", fake_setter)
    out = ca.set_cortex_by_alias("cheap")
    assert out["ok"] is True
    assert out["resolved_tag"] == defaults.CANONICAL_CLOUD_QWEN
    assert len(calls) == 1
    assert calls[0] == defaults.CANONICAL_CLOUD_QWEN


def test_set_by_alias_surfaces_setter_failure(monkeypatch):
    def fake_setter(model: str) -> dict:
        return {"ok": False, "error": "assignment_locked"}

    monkeypatch.setattr(ca, "set_default_ollama_model", fake_setter)
    out = ca.set_cortex_by_alias("cheap")
    assert out["ok"] is False
    assert "declined" in out["reason"]
    assert "assignment_locked" in out["reason"]


def test_set_by_alias_handles_setter_raising(monkeypatch):
    def fake_setter(model: str) -> dict:
        raise RuntimeError("disk full")

    monkeypatch.setattr(ca, "set_default_ollama_model", fake_setter)
    out = ca.set_cortex_by_alias("cheap")
    assert out["ok"] is False
    assert "RuntimeError" in out["reason"]
    assert "disk full" in out["reason"]


# ─── No real ledger mutation ───────────────────────────────────────────────


def test_resolver_does_not_touch_state(tmp_path):
    """Pure read — must not write anything when only resolving."""
    real_assignments = (
        defaults._ASSIGNMENTS if hasattr(defaults, "_ASSIGNMENTS") else None
    )
    size_before = (
        real_assignments.stat().st_size
        if real_assignments and real_assignments.exists()
        else 0
    )
    # Resolve a dozen aliases — none of these should write anything
    for alias in ("cheap", "kimi", "long", "local", "grok", "claude", "codex"):
        ca.resolve_cortex_alias(alias)
    ca.list_aliases()
    ca.list_canonical_groups()
    ca.cortex_alias_prompt_block()
    size_after = (
        real_assignments.stat().st_size
        if real_assignments and real_assignments.exists()
        else 0
    )
    assert size_before == size_after, "resolver mutated swimmer_ollama_assignments"
