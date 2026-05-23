"""Tests for the Impress Me / Explain Why translator.

Architect 2026-05-13 spec: stop showing raw JSON, start telling the
story. These tests pin the translation function to the architect's
exact copy and verify it doesn't crash on missing fields.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_mammal_impress_summary import (
    explain_why_this_matters,
    render_panel_text,
    summary_what_happened,
)


# ── Architect's canonical example ──────────────────────────────────

CODEX_BACKEND_PAYLOAD = {
    "n_tokens": 1537,
    "n_pheromones": 1412,
    "n_scalar_projections": 276,
    "pheromones_by_type": {
        "MEMORY_WELL": 1117,
        "BINDING_TRAIL": 253,
        "CONTRADICTION_STORM": 10,
        "INFLAMMATION_SIGNAL": 13,
        "TOXICITY_CLUSTER": 12,
    },
    "metabolism": {"stabilized_tokens": 1208},
}


def test_what_happened_renders_architect_template():
    out = summary_what_happened(CODEX_BACKEND_PAYLOAD)
    # The architect's exact framing — these strings must be present.
    assert "WHAT HAPPENED" in out
    assert "1,537 typed organ tokens entered the field." in out
    assert "1,412 pheromone trails were laid by swimmers." in out
    assert "1,208 tokens stabilized instead of evaporating." in out
    assert "276 scalar values were bound to nearby context." in out
    assert "10 contradiction storms were detected." in out
    assert "13 inflammation signals were detected." in out
    assert "12 toxicity clusters were detected." in out
    # The "Meaning" footer
    assert "It turned it into a living evidence field." in out


def test_what_happened_has_no_duplicate_scalar_line():
    """Bug guard: BINDING_TRAIL and n_scalar_projections used to share
    the same display text, producing duplicate '276 scalar values...'
    and '253 scalar values...' lines. They now have distinct prose."""
    out = summary_what_happened(CODEX_BACKEND_PAYLOAD)
    # "276 scalar values" appears exactly once
    assert out.count("scalar values were bound to nearby context") == 1
    # BINDING_TRAIL has its own line
    assert "binding trails were laid" in out


def test_explain_why_ends_with_architect_punchline():
    out = explain_why_this_matters(CODEX_BACKEND_PAYLOAD)
    # The closing line — the architect's exact phrasing.
    assert out.endswith("This is the start of cross-organ attention with memory.")


def test_explain_why_names_the_strongest_signal():
    out = explain_why_this_matters(CODEX_BACKEND_PAYLOAD)
    # MEMORY_WELL is the strongest at 1,117
    assert "MEMORY_WELL" in out
    assert "1,117" in out


def test_explain_why_includes_no_silent_fake_count():
    """When there ARE tokens, the count must come from the payload, not
    a made-up number."""
    out = explain_why_this_matters(CODEX_BACKEND_PAYLOAD)
    assert "1,537 typed tokens" in out
    assert "1,412 persistent swimmer trails" in out


# ── Edge cases — empty / missing / wrong shape ─────────────────────

def test_what_happened_handles_empty_payload():
    out = summary_what_happened({})
    assert "WHAT HAPPENED" in out
    assert "press Run" in out.lower() or "no signals" in out.lower()


def test_explain_why_handles_empty_payload():
    out = explain_why_this_matters({})
    # Even on empty, the closing punchline appears (as forward-looking)
    assert "cross-organ attention with memory" in out


def test_what_happened_handles_non_dict_input():
    """Defensive: non-mapping input must not crash."""
    out = summary_what_happened("not a dict")  # type: ignore[arg-type]
    assert "WHAT HAPPENED" in out


def test_explain_why_handles_none():
    out = explain_why_this_matters(None)  # type: ignore[arg-type]
    assert "cross-organ attention with memory" in out


def test_our_backend_payload_also_works():
    """The translator must also handle our backend's payload shape
    (receipts_by_kind instead of pheromones_by_type)."""
    payload = {
        "n_tokens": 4,
        "n_tokens_spawned_total": 38,
        "n_tokens_died_total": 34,
        "receipts_by_kind": {
            "HYPOTHESIS": 593,
            "REPLAY_REINFORCED": 267,
            "CONTRADICTION": 8,  # different name from CONTRADICTION_STORM
            "TOXICITY_CLUSTER": 2,
        },
    }
    out = summary_what_happened(payload)
    assert "4 typed organ tokens" in out
    # Stabilized = spawned - died = 4
    assert "4 tokens stabilized instead of evaporating" in out
    # Counts of receipts get summed
    assert "870 pheromone trails were laid" in out  # 593+267+8+2


def test_render_panel_text_includes_both_blocks_and_divider():
    out = render_panel_text(CODEX_BACKEND_PAYLOAD)
    assert "WHAT HAPPENED" in out
    assert "─" * 10 in out  # divider line
    assert out.endswith("This is the start of cross-organ attention with memory.")


# ── Number formatting ──────────────────────────────────────────────

def test_counts_use_thousands_separator():
    """A million tokens → '1,000,000', not '1000000'."""
    payload = {
        "n_tokens": 1_234_567,
        "n_pheromones": 999_888,
        "pheromones_by_type": {"MEMORY_WELL": 555_444},
        "metabolism": {"stabilized_tokens": 800_000},
    }
    out = summary_what_happened(payload)
    assert "1,234,567" in out
    assert "999,888" in out
    assert "555,444" in out


def test_zero_pheromones_of_type_does_not_render():
    """A type with count=0 should NOT produce a '0 contradiction storms' line."""
    payload = {
        "n_tokens": 100,
        "n_pheromones": 50,
        "pheromones_by_type": {
            "MEMORY_WELL": 50,
            "CONTRADICTION_STORM": 0,
            "TOXICITY_CLUSTER": 0,
        },
    }
    out = summary_what_happened(payload)
    assert "0 contradiction storms" not in out
    assert "0 toxicity clusters" not in out
    assert "50 tokens stabilized as memory wells" in out
