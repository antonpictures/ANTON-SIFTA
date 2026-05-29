"""Round 89 tests — Qwen + Cline added as canonical cloud cortexes.

Mirrors the Round 77 pattern (Claude + Codex). Verifies that:
  - CANONICAL_CLOUD_QWEN, Fireworks Flash, and CANONICAL_CLOUD_CLINE are defined and exported
  - list_available_cortexes_with_canonical_fallback() returns them
  - the picker display formatter in sifta_system_settings.py handles
    qwen:* and cline:* tags with the proper teacher labels
  - the inference defaults module still parses + exports the older
    canonical cloud constants (Grok, Claude, Codex) — no regressions
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from System import sifta_inference_defaults as defaults


REPO = Path(__file__).resolve().parents[1]


# ─── Constants present and exported ────────────────────────────────────────


def test_canonical_cloud_qwen_defined():
    assert hasattr(defaults, "CANONICAL_CLOUD_QWEN")
    # Codex updated Round 89 to use the full Fireworks namespace path
    # so the resolver maps directly to the Fireworks model id.
    # Round 97 (2026-05-28): default cortex switched from Kimi K2.6 to
    # gpt-oss-20b (12× cheaper input pricing for drafter turns).
    assert defaults.CANONICAL_CLOUD_QWEN == "qwen:accounts/fireworks/models/gpt-oss-20b"


def test_canonical_cloud_cline_defined():
    assert hasattr(defaults, "CANONICAL_CLOUD_CLINE")
    assert defaults.CANONICAL_CLOUD_CLINE == "cline:cline-cli-default"


def test_both_constants_in__all__():
    assert "CANONICAL_CLOUD_QWEN" in defaults.__all__
    assert "CANONICAL_CLOUD_QWEN_LONG_DEEPSEEK_FLASH" in defaults.__all__
    assert "CANONICAL_CLOUD_CLINE" in defaults.__all__


def test_round77_constants_still_present():
    """No regressions: Grok/Claude/Codex still defined + exported."""
    assert defaults.CANONICAL_CLOUD_GROK == "grok:grok-4.3"
    assert defaults.CANONICAL_CLOUD_CLAUDE == "claude:claude-code-cli-default"
    assert defaults.CANONICAL_CLOUD_CODEX == "codex:gpt-5.5"
    for name in ("CANONICAL_CLOUD_GROK", "CANONICAL_CLOUD_CLAUDE", "CANONICAL_CLOUD_CODEX"):
        assert name in defaults.__all__


# ─── Picker function actually surfaces both new tags ───────────────────────


def test_picker_function_returns_qwen_and_cline():
    """list_available_cortexes_with_canonical_fallback() must include both
    new cloud cortex tags (alongside Grok/Claude/Codex)."""
    cortexes = defaults.list_available_cortexes_with_canonical_fallback()
    assert defaults.CANONICAL_CLOUD_QWEN in cortexes
    assert defaults.CANONICAL_CLOUD_QWEN_LONG_DEEPSEEK_FLASH in cortexes
    assert defaults.CANONICAL_CLOUD_CLINE in cortexes
    # And the existing teachers are still there
    assert defaults.CANONICAL_CLOUD_GROK in cortexes
    assert defaults.CANONICAL_CLOUD_CLAUDE in cortexes
    assert defaults.CANONICAL_CLOUD_CODEX in cortexes


def test_picker_function_no_duplicates():
    """Each cloud cortex tag must appear at most once in the dropdown list."""
    cortexes = defaults.list_available_cortexes_with_canonical_fallback()
    for tag in (
        defaults.CANONICAL_CLOUD_QWEN,
        defaults.CANONICAL_CLOUD_QWEN_LONG_DEEPSEEK_FLASH,
        defaults.CANONICAL_CLOUD_CLINE,
        defaults.CANONICAL_CLOUD_GROK,
        defaults.CANONICAL_CLOUD_CLAUDE,
        defaults.CANONICAL_CLOUD_CODEX,
    ):
        assert cortexes.count(tag) == 1, f"{tag} duplicated in picker list"


# ─── Settings widget picker display formatting ────────────────────────────


def test_settings_picker_formats_qwen_tag():
    """sifta_system_settings.py must format qwen:* with specific model labels."""
    src = (REPO / "Applications" / "sifta_system_settings.py").read_text(encoding="utf-8")
    assert "DeepSeek V4 Flash via Fireworks" in src
    assert "gpt-oss-20b via Fireworks" in src
    assert "Kimi K2.6 via Fireworks" in src


def test_settings_picker_formats_cline_tag():
    src = (REPO / "Applications" / "sifta_system_settings.py").read_text(encoding="utf-8")
    pattern = re.compile(
        r'tag\.lower\(\)\.startswith\("cline"\)[\s\S]{0,200}?'
        r'Cline[\s\S]{0,80}?teacher[\s\S]{0,40}?☁ cloud',
    )
    assert pattern.search(src), "settings picker must format cline:* with Cline OAuth teacher + cloud label"


def test_settings_picker_still_formats_round77_tags():
    """No regression in Round 77 grok/claude/codex display formatting."""
    src = (REPO / "Applications" / "sifta_system_settings.py").read_text(encoding="utf-8")
    assert "xAI Grok OAuth" in src
    assert "Claude Code OAuth teacher" in src
    assert "Codex CLI OAuth teacher" in src


# ─── Module still parses cleanly ───────────────────────────────────────────


def test_inference_defaults_parses_cleanly():
    src = (REPO / "System" / "sifta_inference_defaults.py").read_text(encoding="utf-8")
    try:
        ast.parse(src)
    except SyntaxError as exc:
        pytest.fail(f"sifta_inference_defaults.py no longer parses: {exc}")


def test_settings_widget_parses_cleanly():
    src = (REPO / "Applications" / "sifta_system_settings.py").read_text(encoding="utf-8")
    try:
        ast.parse(src)
    except SyntaxError as exc:
        pytest.fail(f"sifta_system_settings.py no longer parses: {exc}")
