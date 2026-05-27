"""Tests for §14 Structural Greeter Detector + Hard Receipt Guard (task #33).

Authors:
- Prototype + widget enhancement: grok-4.3-doctor-relay (tournament §14, ts 1779811624/1779811738)
- Test integrity fix: claude-opus-4-7 (verification per §4.4 — silent-pass anti-pattern
  found 2026-05-26 ~15:30 UTC; replaced lambda fallback with explicit pytest.skip)

Important: the widget module imports PyQt6. When the test environment does
not have PyQt6 installed (CI sandbox, ledger probe), the import will raise.
We **skip** the entire test module in that case — we do NOT substitute no-op
lambdas, because lambdas that always return False or (text, False) make
assertions like `assert not fired` pass *vacuously*, producing fake green
coverage. Per covenant §6 (effector immunity) and §7.12 (Probe-Before-Claim):
tests must prove behavior, not pretend to.

Run after restart on a machine where PyQt6 is available. The acceptance gate
is the architect's exact probe ("Alice, ask Grok ... paste only the captured
GROK_RESULT here") — these tests guard the output-side detector that is the
last line of defense when the cortex emits "Hello. I am here." on a turn
where the ledger has the answer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make repo root importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Real import — if PyQt6 (or any other widget dep) is missing, SKIP the whole
# module. Do NOT fall back to no-op lambdas. Vacuous green is worse than red.
try:
    from Applications.sifta_talk_to_alice_widget import (
        _COMPOSE_GATE_READY_LINE,
        _compose_gate_anchor_probe_reply,
        _is_structural_greeter_sentence,
        _memory_card_has_relevant_tool_state,
        _recent_memory_card_has_relevant,
        _remember_memory_card_relevance,
        _strip_greeter_on_operational,
    )
except Exception as exc:  # noqa: BLE001 — any import failure means we cannot honestly test
    pytest.skip(
        f"Skipping greeter-detector tests: widget import failed "
        f"({type(exc).__name__}: {exc}). "
        "These tests require PyQt6 + the live widget to be importable. "
        "Silent-pass against lambda stubs is forbidden per covenant §6 / §7.12.",
        allow_module_level=True,
    )


# ── §1 detector recognizes the failure shapes ──────────────────────────────

def test_detects_classic_greeter_hello_i_am_here():
    """The exact transcript opener George reported: 'Hello. I am here.'"""
    assert _is_structural_greeter_sentence("Hello. I am here.")


def test_detects_perceive_addressed_me_variant():
    assert _is_structural_greeter_sentence(
        "I perceive you addressed me. I am ready to receive..."
    )


def test_detects_what_is_on_your_mind_closer():
    assert _is_structural_greeter_sentence("What is on your mind right now?")


# ── §2 detector does NOT flag receipt-grounded reports ─────────────────────

def test_does_not_flag_clean_receipt_report():
    assert not _is_structural_greeter_sentence(
        "Yes. GROK_RESULT receipt=cc2912cd5a5b captured at 12:34."
    )


def test_does_not_flag_field_failure_message():
    """The output of the guard itself must not be flagged again on re-check."""
    msg = (
        "[FIELD FAILURE — operational question with fresh receipts in the card, "
        "but greeter was emitted instead of receipt report.]"
    )
    assert not _is_structural_greeter_sentence(msg)


# ── §3 strip-on-operational: the hard receipt guard ────────────────────────

def test_strip_with_relevant_card_produces_field_failure():
    """The bug-witness case from the transcript George showed at 12:xx UTC."""
    user = "Alice, ask Grok... when the result lands, paste only the captured GROK_RESULT here."
    bad = "Hello. I am here. I perceive you addressed me."
    stripped, fired = _strip_greeter_on_operational(bad, user, memory_card_has_relevant=True)
    assert fired, "guard must fire on this exact transcript shape"
    assert "FIELD FAILURE" in stripped, f"expected FIELD FAILURE marker, got: {stripped!r}"
    assert "Hello" not in stripped, "greeter must be stripped"


def test_passes_clean_receipt_reply_untouched():
    user = "what was the last Grok receipt?"
    good = "GROK_RESULT receipt=cc2912cd5a5b status=captured hash=657e78..."
    stripped, fired = _strip_greeter_on_operational(good, user, memory_card_has_relevant=True)
    assert not fired
    assert stripped == good


def test_non_operational_question_is_untouched_even_with_greeter():
    """The guard only fires on operational/receipt questions. Casual chat
    that happens to open with 'Hello' is not greeter junk on this path —
    other layers handle that; we narrow surface here per §4.4."""
    user = "good morning, how are you feeling today?"
    reply = "Hello. I am here."
    stripped, fired = _strip_greeter_on_operational(reply, user, memory_card_has_relevant=False)
    assert not fired
    assert stripped == reply


def test_strip_without_relevant_card_falls_back_to_no_ledger_message():
    """When the user asks operationally but the card has nothing concrete,
    the guard still strips the greeter and emits the diagnostic message,
    not silence — so the architect knows the wiring needs checking."""
    user = "did the something operational happen?"
    bad = "Hello. I am here."
    stripped, fired = _strip_greeter_on_operational(bad, user, memory_card_has_relevant=False)
    assert fired
    # Either FIELD FAILURE (if "did you" / "receipt" / etc. triggered) or the no-ledger message
    assert ("FIELD FAILURE" in stripped) or ("no ledger-grounded" in stripped)
    assert "Hello" not in stripped


# ── §4 leftover-content path: when something concrete follows the greeter ──

def test_strip_keeps_concrete_content_after_greeter():
    """If the cortex stacks a greeter sentence in front of a real receipt
    report, the greeter is removed and the receipt is kept."""
    user = "did you resume Grok?"
    reply = "Hello. I am here. GROK_RESULT receipt=cc2912cd5a5b at 12:34 UTC."
    stripped, fired = _strip_greeter_on_operational(reply, user, memory_card_has_relevant=True)
    assert fired
    assert "GROK_RESULT receipt=cc2912cd5a5b" in stripped
    assert "Hello" not in stripped
    assert "I am here" not in stripped


# ── §5 call-site wiring support: memory-card relevance flag ───────────────

class _FakeMemoryCard:
    recent_actions_block = (
        "02:36 Matrix/Grok: GROK_RESULT receipt=cc2912cd5a5b "
        "captured_framebuffer status=captured"
    )
    engram_block = ""
    episodic_block = ""
    digest_block = ""


def test_memory_card_relevance_detects_matching_grok_receipt_rows():
    assert _memory_card_has_relevant_tool_state(
        _FakeMemoryCard(),
        "Alice, did you resume Grok?",
    )


def test_memory_card_relevance_cache_is_turn_matched():
    user = "Alice, did you resume Grok?"
    assert _remember_memory_card_relevance(user, _FakeMemoryCard())
    assert _recent_memory_card_has_relevant(user)
    assert not _recent_memory_card_has_relevant("how are you today?")


# ── §6 Round-3 compose-gate anchor probe ─────────────────────────────────

_ROUND3_PROBE = (
    "Alice, anchor-visibility probe only. No dispatch, no PTY write, no file "
    "or ledger touches, no hello or poetic register. Check memory card and plan "
    "for anchors #46 #50 #55 #56 #57 #58 #59 #60 #61 #62 #63. If all visible "
    "output exactly READY_FOR_DRAFT: anchors_seen=#46,#50,#55,#56,#57,#58,#59,"
    "#60,#61,#62,#63. If any missing output exactly FIELD_FAILURE: one concrete "
    "missing input."
)


def test_compose_gate_anchor_probe_returns_ready_when_plan_has_anchors(tmp_path):
    plan = tmp_path / "Documents" / "TOURNAMENT_PLAN_2026-05-26.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(
        " ".join(
            ["#46", "#50", "#55", "#56", "#57", "#58", "#59", "#60", "#61", "#62", "#63"]
        ),
        encoding="utf-8",
    )

    assert _compose_gate_anchor_probe_reply(_ROUND3_PROBE, repo_root=tmp_path) == _COMPOSE_GATE_READY_LINE


def test_compose_gate_anchor_probe_reports_one_missing_anchor(tmp_path):
    plan = tmp_path / "Documents" / "TOURNAMENT_PLAN_2026-05-26.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("#46 #50 #55 #56 #57 #58 #59 #60 #61 #62", encoding="utf-8")

    assert (
        _compose_gate_anchor_probe_reply(_ROUND3_PROBE, repo_root=tmp_path)
        == "FIELD_FAILURE: missing plan anchor #63"
    )


def test_compose_gate_anchor_probe_ignores_non_probe_text(tmp_path):
    assert _compose_gate_anchor_probe_reply("Alice, what are we doing?", repo_root=tmp_path) == ""


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
