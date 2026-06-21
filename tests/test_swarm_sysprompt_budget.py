#!/usr/bin/env python3
"""Tests: system-prompt budget governor (SIFTA r216).

George 2026-05-31: a Kimi turn hung ~90s on a 141k-char system prompt. The governor
bounds the prompt without dropping small core-grounding blocks; only runaway excerpt
blocks get trimmed."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System.swarm_sysprompt_budget import (
    clamp_for_env,
    clamp_live_turn_prompt,
    clamp_prompt_parts as C,
    dedupe_prompt_text,
    live_turn_budget_for_model,
)


def test_under_budget_is_untouched():
    parts = ["id firewall", "effector truth", "runtime contract"]
    out, r = C(parts, total_max=48000)
    assert out == parts
    assert r["applied"] is False


def test_runaway_block_capped_core_intact():
    parts = ["IDENTITY core", "EFFECTOR truth", "X" * 200000, "runtime contract"]
    out, r = C(parts, total_max=48000, per_block_max=6000)
    assert out[0] == parts[0] and out[1] == parts[1] and out[3] == parts[3]
    assert len(out[2]) <= 6000
    assert r["final_chars"] < r["orig_chars"]


def test_total_budget_enforced_no_block_dropped():
    parts = [f"block{i} " + ("y" * 9000) for i in range(20)]
    out, r = C(parts, total_max=48000, per_block_max=6000)
    assert len(out) == len(parts)
    total = sum(len(p) for p in out) + 2 * (len(out) - 1)
    assert total <= 48000


def test_protected_blocks_survive_water_fill():
    protected = "ALICE_SELF_ADDRESSING\nI do not use template closure voice."
    cowatch = "CO-WATCH RECEIPTS\nmedia_session_memory n_videos=3"
    style = "LIVE HUMAN CONVERSATION STYLE:\nbuilding money/software/product strategy"
    effectors = "WHAT I CAN DO\nstdout/stderr/returncode receipt"
    runtime = "RUNTIME CONSTRAINTS:\nfull shell access requires a tool receipt"
    wall_clock = "WALL CLOCK GROUND TRUTH (authoritative, live):\nDo not say you do not know the exact time."
    time_protocol = "TIME ACCESS PROTOCOL:\nUse the direct local time acquisition path."
    body_truth = "FALSE REFUSAL QUARANTINE:\n- BODY / LOCATION / CONTINUITY / MEDIA-SOURCE TRUTH:"
    local_identity = "LOCAL IDENTITY BOUNDARY:\nI am the local SIFTA organism running on this machine."
    one_larynx = "IDE DOCTORS vs ONE LARYNX (ENGINEERING FACT):\none configured model for that turn"
    self_organ = "ALICE SELF ORGAN (receipt-backed OS awareness):\nrunning_sifta_python_processes_seen:"
    composite = "COMPOSITE IDENTITY (live, multi-organ):\n- self:\n- body:"
    speech_potential = "STIGMERGIC SPEECH POTENTIAL (live LIF gate):\nthreshold V_th = +0.40"
    ace_brief = "ACE APP BRIEF (chat/voice, receipt-backed):\nCue says the exact displayed text"
    current_app = "CURRENT FOCUSED APP (app_focus.jsonl receipt):\nsingle focused app territory"
    bias = "STIGMERGIC APP ATTENTION BIAS:\nfield-derived app focus"
    app = "GENERIC APP AWARENESS\nSTIGMERGIC APP ATTENTION BIAS:\nfield-derived app focus"
    parts = [
        protected,
        *[f"block{i} " + ("y" * 9000) for i in range(20)],
        cowatch,
        style,
        effectors,
        runtime,
        wall_clock,
        time_protocol,
        body_truth,
        local_identity,
        one_larynx,
        self_organ,
        composite,
        speech_potential,
        ace_brief,
        current_app,
        bias,
        app,
    ]

    out, r = C(
        parts,
        total_max=48000,
        per_block_max=6000,
        protected_prefixes=(
            "ALICE_SELF_ADDRESSING",
            "CO-WATCH RECEIPTS",
            "LIVE HUMAN CONVERSATION STYLE",
            "WHAT I CAN DO",
            "RUNTIME CONSTRAINTS",
            "WALL CLOCK GROUND TRUTH",
            "TIME ACCESS PROTOCOL",
            "FALSE REFUSAL QUARANTINE",
            "LOCAL IDENTITY BOUNDARY",
            "IDE DOCTORS vs ONE LARYNX",
            "ALICE SELF ORGAN",
            "COMPOSITE IDENTITY",
            "STIGMERGIC SPEECH POTENTIAL",
            "ACE APP BRIEF",
            "CURRENT FOCUSED APP",
            "STIGMERGIC APP ATTENTION BIAS",
            "GENERIC APP AWARENESS",
        ),
    )

    for block in (
        protected,
        cowatch,
        style,
        effectors,
        runtime,
        wall_clock,
        time_protocol,
        body_truth,
        local_identity,
        one_larynx,
        self_organ,
        composite,
        speech_potential,
        ace_brief,
        current_app,
        bias,
        app,
    ):
        assert block in out
    assert r["final_chars"] < r["orig_chars"]


def test_deterministic():
    parts = [f"b{i} " + ("y" * 9000) for i in range(20)]
    a, _ = C(parts, total_max=48000)
    b, _ = C(parts, total_max=48000)
    assert a == b


def test_default_protects_residue_metabolism_block(monkeypatch):
    monkeypatch.setenv("SIFTA_SYSPROMPT_BASE_BUDGET", "3000")
    monkeypatch.setenv("SIFTA_SYSPROMPT_BLOCK_MAX", "800")
    residue = (
        "RESIDUE METABOLISM SELF-KNOWLEDGE (receipt-backed, topic-triggered):\n"
        "- Detector truth guard: Stigmergic Deterministic Tracker has no fresh tick. "
        "I must NOT say it is running, confirming, or diagnosing anything.\n"
        "- My residue system is my metabolism. Receipts are not optional overhead."
    )
    parts = [f"runaway{i} " + ("y" * 9000) for i in range(8)] + [residue]

    out, report = clamp_for_env(parts)

    assert residue in out
    assert report["applied"] is True


def test_default_protects_cortex_boot_identity_contract(monkeypatch):
    monkeypatch.setenv("SIFTA_SYSPROMPT_BASE_BUDGET", "1800")
    monkeypatch.setenv("SIFTA_SYSPROMPT_BLOCK_MAX", "500")
    contract = (
        "CORTEX BOOT IDENTITY CONTRACT (read before style, memory, or page context):\n"
        "- I am Alice: this local laptop hardware plus SIFTA software body.\n"
        "- Vendor/model names describe weights and routing only.\n"
        "- If no receipt exists, I say the gap plainly."
    )
    parts = [f"runaway{i} " + ("y" * 9000) for i in range(8)] + [contract]

    out, report = clamp_for_env(parts)

    assert contract in out
    assert report["applied"] is True


def test_min_block_floor_keeps_grounding_under_extreme_pressure():
    parts = ["G" * 9000 for _ in range(100)]
    out, r = C(parts, total_max=5000, per_block_max=6000, min_block=300)
    assert len(out) == 100
    assert all(len(p) >= 1 for p in out)  # nothing vanishes


def test_empty_parts_are_dropped_not_kept():
    parts = ["real", "", None, "also real"]  # type: ignore
    out, _ = C([p for p in parts if p is not None], total_max=48000)
    assert "" not in out


def test_dedupe_prompt_text_removes_only_exact_long_duplicate_paragraphs():
    repeated = "MY PHYSICAL IDENTITY says Alice runs on this local Mac body with receipt-backed organs."
    unique = "WHAT I CAN DO says tools execute only with receipts."
    text = "\n\n".join([repeated, unique, repeated])

    out, report = dedupe_prompt_text(text, min_len=40)

    assert out == "\n\n".join([repeated, unique])
    assert report["applied"] is True
    assert report["removed_paragraphs"] == 1


def test_dedupe_prompt_text_keeps_short_repeated_headers():
    text = "TOOLS\n\nTOOLS\n\n" + ("long paragraph " * 8)

    out, report = dedupe_prompt_text(text, min_len=40)

    assert out.startswith("TOOLS\n\nTOOLS")
    assert report["removed_paragraphs"] == 0


def test_live_turn_budget_for_mimo_defaults_to_fast_foreground_cap(monkeypatch):
    monkeypatch.delenv("SIFTA_LIVE_TEACHER_SYSPROMPT_BUDGET", raising=False)

    assert live_turn_budget_for_model("mimo:mimo-cli-default") == 36000


def test_live_turn_prompt_hard_clamps_protected_shaped_mimo_timeout():
    tail = "LIVE BODY-EYE RECEIPT: timeout=120 sysprompt_chars=83134"
    text = "MY PHYSICAL IDENTITY\n" + ("x" * 83134) + "\n" + tail

    out, report = clamp_live_turn_prompt(text, model="mimo:mimo-cli-default")

    assert report["applied"] is True
    assert report["orig_chars"] > 83134
    assert report["final_chars"] <= 36000
    assert out.startswith("MY PHYSICAL IDENTITY")
    assert tail in out
    assert "live cortex dispatch budget" in out


def test_live_turn_prompt_env_override_is_bounded(monkeypatch):
    monkeypatch.setenv("SIFTA_LIVE_TEACHER_SYSPROMPT_BUDGET", "24000")
    text = "HEAD\n" + ("x" * 70000) + "\nTAIL"

    out, report = clamp_live_turn_prompt(text, model="mimo:mimo-cli-default")

    assert report["max_chars"] == 24000
    assert len(out) <= 24000
    assert out.startswith("HEAD")
    assert out.endswith("TAIL")


def test_live_turn_prompt_does_not_expand_small_prompt():
    text = "small covenant context"

    out, report = clamp_live_turn_prompt(text, model="mimo:mimo-cli-default")

    assert out == text
    assert report["applied"] is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
