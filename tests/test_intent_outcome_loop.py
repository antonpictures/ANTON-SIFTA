"""Tests for the Intent Before Action closed-loop organ.

Architect 2026-05-17 verbatim:
  "A mature agent should: explain why it is acting, predict expected
  outcome, perform action, compare outcome vs prediction, update
  self-vector."

This file pins steps 2 + 4 of that loop:
  * predict_app_open_outcome returns concrete signals with deadlines
  * declare_intent writes a complete declaration row
  * observe_intent identifies met vs unmet against a real focus log
  * write_intent_outcome_delta fires IFF at least one signal failed
  * Ace-specific signals include the cw47-0517-0007 display/voice
    invariant

StigAuth: SIFTA_INTENT_OUTCOME_LOOP_V0
Cowork CW47 / Claude surgery cw47-0517-0512, 2026-05-17.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_intent_outcome_loop import (  # noqa: E402
    ExpectedSignal,
    IntentDeclaration,
    Observation,
    TRUTH_LABEL_DECLARATION,
    TRUTH_LABEL_DELTA,
    TRUTH_LABEL_OBSERVATION,
    _row_matches_signal,
    declare_intent,
    observe_intent,
    predict_app_open_outcome,
    write_intent_outcome_delta,
)


# ── prediction catalog ────────────────────────────────────────────────────


def test_predict_generic_app_returns_launcher_and_widget_signals():
    sigs = predict_app_open_outcome("SomeApp")
    names = [s.name for s in sigs]
    assert "launcher_fired" in names
    assert "widget_mounted" in names


def test_predict_ace_adds_lesson_and_first_cue_signals():
    sigs = predict_app_open_outcome("Ace")
    names = [s.name for s in sigs]
    assert "launcher_fired" in names
    assert "widget_mounted" in names
    assert "lesson_auto_started" in names
    assert "first_cue_published" in names


# ── cw47-0517-0640: per-organ manifest-driven signals ─────────────────────


def test_ace_extra_signals_come_from_manifest_not_hardcode():
    """The lesson_auto_started + first_cue_published signals must be
    declared in apps_manifest.json — not hardcoded in Python.

    This pins the cw47-0517-0640 generalization: any app that adds
    expected_open_signals to its manifest entry gets the same loop
    coverage Ace gets, with no code change.
    """
    import json as _json
    manifest = _json.loads(
        (_REPO / "Applications" / "apps_manifest.json").read_text(encoding="utf-8")
    )
    ace = manifest.get("Ace") or {}
    raw_signals = ace.get("expected_open_signals") or []
    names = {s.get("name") for s in raw_signals if isinstance(s, dict)}
    assert "lesson_auto_started" in names, (
        "Ace must declare lesson_auto_started in its manifest entry, "
        "not rely on a Python hardcode."
    )
    assert "first_cue_published" in names


def test_unknown_app_only_gets_generic_signals():
    sigs = predict_app_open_outcome("NonexistentAppXYZ")
    names = [s.name for s in sigs]
    # Floor only — no manifest entry, no extra signals.
    assert names == ["launcher_fired", "widget_mounted"], (
        f"unknown app should get only the OS-dispatch floor; got {names!r}"
    )


def test_app_with_only_description_no_open_signals_gets_only_floor():
    """An app that has a manifest entry but no expected_open_signals
    field must still get the two floor signals."""
    import json as _json
    manifest = _json.loads(
        (_REPO / "Applications" / "apps_manifest.json").read_text(encoding="utf-8")
    )
    # Find some app that is NOT Ace and has no expected_open_signals.
    target = None
    for name, entry in manifest.items():
        if not isinstance(entry, dict):
            continue
        if name == "Ace" or entry.get("_retired"):
            continue
        if not entry.get("expected_open_signals"):
            target = name
            break
    if target is None:
        pytest.skip("every manifest app already declares expected_open_signals")
    sigs = predict_app_open_outcome(target)
    names = [s.name for s in sigs]
    assert names == ["launcher_fired", "widget_mounted"], (
        f"{target} (no expected_open_signals) should get only the floor; got {names!r}"
    )


def test_ace_first_cue_signal_carries_show_say_invariant():
    sigs = predict_app_open_outcome("Ace")
    cue = next(s for s in sigs if s.name == "first_cue_published")
    assert cue.matcher.get("metadata_invariant") == "current_cue_show_equals_current_cue_say"


def test_deadlines_are_monotonically_increasing_for_ace():
    sigs = predict_app_open_outcome("Ace")
    deadlines = [s.deadline_s for s in sigs]
    assert deadlines == sorted(deadlines), (
        f"signals should be ordered earliest-first: {deadlines}"
    )


# ── matcher evaluation ────────────────────────────────────────────────────


def test_matcher_accepts_app_and_source():
    sig = ExpectedSignal(
        name="x", deadline_s=1.0, description="",
        matcher={"app": "Ace", "metadata_eq": {"source": "ace_widget"}},
    )
    row = {"app": "Ace", "metadata": {"source": "ace_widget"}, "ts": 1.0}
    assert _row_matches_signal(row, sig)


def test_matcher_rejects_wrong_app():
    sig = ExpectedSignal(
        name="x", deadline_s=1.0, description="",
        matcher={"app": "Ace"},
    )
    row = {"app": "Browser", "metadata": {}, "ts": 1.0}
    assert not _row_matches_signal(row, sig)


def test_matcher_metadata_present_requires_nonempty():
    sig = ExpectedSignal(
        name="x", deadline_s=1.0, description="",
        matcher={"metadata_present": ["cue_id"]},
    )
    assert _row_matches_signal({"metadata": {"cue_id": "abc123"}}, sig)
    assert not _row_matches_signal({"metadata": {"cue_id": ""}}, sig)
    assert not _row_matches_signal({"metadata": {}}, sig)


def test_matcher_source_suffix_supports_any_widget():
    sig = ExpectedSignal(
        name="x", deadline_s=1.0, description="",
        matcher={"app": "Ace", "metadata_source_suffix": "_widget"},
    )
    assert _row_matches_signal(
        {"app": "Ace", "metadata": {"source": "ace_widget"}, "ts": 1.0}, sig
    )
    assert not _row_matches_signal(
        {"app": "Ace", "metadata": {"source": "sifta_os_desktop"}, "ts": 1.0}, sig
    )


def test_matcher_show_say_invariant_requires_equality():
    sig = ExpectedSignal(
        name="x", deadline_s=1.0, description="",
        matcher={
            "metadata_present": ["current_cue_show", "current_cue_say"],
            "metadata_invariant": "current_cue_show_equals_current_cue_say",
        },
    )
    assert _row_matches_signal(
        {"metadata": {"current_cue_show": "cat", "current_cue_say": "cat"}}, sig
    )
    assert not _row_matches_signal(
        {"metadata": {"current_cue_show": "cat", "current_cue_say": "mat"}}, sig
    )


def test_matcher_rejects_unknown_invariant_conservatively():
    sig = ExpectedSignal(
        name="x", deadline_s=1.0, description="",
        matcher={"metadata_invariant": "no_such_invariant"},
    )
    assert not _row_matches_signal({"metadata": {}}, sig)


# ── declare + observe round trip ──────────────────────────────────────────


def test_declare_intent_writes_a_row(tmp_path: Path):
    ledger = tmp_path / "decls.jsonl"
    decl = declare_intent(
        actor="Alice",
        intent_kind="open_app",
        target="Ace",
        narration="I'm opening the reading game.",
        expected_signals=predict_app_open_outcome("Ace"),
        now=1000.0,
        declarations_path=ledger,
    )
    assert decl.intent_id
    assert decl.declared_ts == 1000.0
    assert ledger.exists()
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["target"] == "Ace"
    assert rows[0]["truth_label"] == TRUTH_LABEL_DECLARATION


def _write_focus_log(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_observe_intent_marks_all_met_for_complete_ace_open(tmp_path: Path):
    decl = declare_intent(
        actor="Alice", intent_kind="open_app", target="Ace",
        narration="I'm opening the reading game.",
        expected_signals=predict_app_open_outcome("Ace"),
        now=1000.0, write=False,
    )
    # Build a synthetic focus log that satisfies every expected signal.
    focus_log = tmp_path / "app_focus.jsonl"
    rows = [
        {"ts": 1001.0, "app": "Ace", "detail": "launcher", "metadata": {"source": "sifta_os_desktop"}},
        {"ts": 1002.0, "app": "Ace", "detail": "widget mount", "metadata": {"source": "ace_widget"}},
        {"ts": 1005.0, "app": "Ace", "detail": "greeting",
         "metadata": {"source": "ace_widget", "lesson_started": True}},
        {"ts": 1020.0, "app": "Ace", "detail": "first cue",
         "metadata": {
             "source": "ace_widget", "cue_id": "abc123def",
             "current_cue_show": "cat", "current_cue_say": "cat",
         }},
    ]
    _write_focus_log(focus_log, rows)
    obs = observe_intent(decl, now=1031.0, focus_path=focus_log)
    by_name = {o.signal_name: o for o in obs}
    assert by_name["launcher_fired"].met
    assert by_name["widget_mounted"].met
    assert by_name["lesson_auto_started"].met
    assert by_name["first_cue_published"].met


def test_observe_intent_flags_lesson_start_missing(tmp_path: Path):
    decl = declare_intent(
        actor="Alice", intent_kind="open_app", target="Ace",
        narration="I'm opening the reading game.",
        expected_signals=predict_app_open_outcome("Ace"),
        now=1000.0, write=False,
    )
    focus_log = tmp_path / "app_focus.jsonl"
    rows = [
        {"ts": 1001.0, "app": "Ace", "detail": "launcher", "metadata": {"source": "sifta_os_desktop"}},
        {"ts": 1002.0, "app": "Ace", "detail": "widget mount", "metadata": {"source": "ace_widget"}},
        # NO lesson_started row, NO cue_id row
    ]
    _write_focus_log(focus_log, rows)
    obs = observe_intent(decl, now=1031.0, focus_path=focus_log)
    by_name = {o.signal_name: o for o in obs}
    assert by_name["launcher_fired"].met
    assert by_name["widget_mounted"].met
    assert not by_name["lesson_auto_started"].met
    assert not by_name["first_cue_published"].met


def test_observe_intent_flags_cue_display_voice_drift(tmp_path: Path):
    """Architect bug from 2026-05-17: card shows 'cat' but Alice cues 'mat'.
    The first_cue_published signal must catch that and mark NOT MET."""
    decl = declare_intent(
        actor="Alice", intent_kind="open_app", target="Ace",
        narration="open Ace",
        expected_signals=predict_app_open_outcome("Ace"),
        now=1000.0, write=False,
    )
    focus_log = tmp_path / "app_focus.jsonl"
    rows = [
        {"ts": 1001.0, "app": "Ace", "detail": "launcher", "metadata": {"source": "sifta_os_desktop"}},
        {"ts": 1002.0, "app": "Ace", "detail": "widget", "metadata": {"source": "ace_widget"}},
        {"ts": 1005.0, "app": "Ace", "detail": "greeting",
         "metadata": {"source": "ace_widget", "lesson_started": True}},
        # show='cat' but say='mat' — the bug.
        {"ts": 1020.0, "app": "Ace", "detail": "first cue",
         "metadata": {
             "source": "ace_widget", "cue_id": "abc123def",
             "current_cue_show": "cat", "current_cue_say": "mat",
         }},
    ]
    _write_focus_log(focus_log, rows)
    obs = observe_intent(decl, now=1031.0, focus_path=focus_log)
    by_name = {o.signal_name: o for o in obs}
    assert not by_name["first_cue_published"].met, (
        "show/say drift must trip the first_cue_published invariant"
    )


def test_observe_intent_marks_pending_when_called_before_deadline(tmp_path: Path):
    decl = declare_intent(
        actor="Alice", intent_kind="open_app", target="Ace",
        narration="open Ace",
        expected_signals=predict_app_open_outcome("Ace"),
        now=1000.0, write=False,
    )
    focus_log = tmp_path / "app_focus.jsonl"
    _write_focus_log(focus_log, [])  # nothing landed yet
    # Now = 1002 → launcher deadline (1003) not yet passed
    obs = observe_intent(decl, now=1002.0, focus_path=focus_log)
    by_name = {o.signal_name: o for o in obs}
    assert not by_name["launcher_fired"].met
    assert "pending" in by_name["launcher_fired"].note


# ── delta writer ──────────────────────────────────────────────────────────


def test_write_delta_returns_none_when_all_met(tmp_path: Path):
    decl = declare_intent(
        actor="Alice", intent_kind="open_app", target="Ace",
        narration="open Ace",
        expected_signals=[ExpectedSignal(name="x", deadline_s=1.0, description="", matcher={})],
        now=1000.0, write=False,
    )
    obs = [Observation(intent_id=decl.intent_id, signal_name="x", met=True, observed_ts=1001.0, note="matched")]
    deltas_path = tmp_path / "deltas.jsonl"
    out = write_intent_outcome_delta(decl, obs, deltas_path=deltas_path)
    assert out is None
    assert not deltas_path.exists()


def test_write_delta_skips_pending_signals(tmp_path: Path):
    decl = declare_intent(
        actor="Alice", intent_kind="open_app", target="Ace",
        narration="open Ace",
        expected_signals=[ExpectedSignal(name="x", deadline_s=10.0, description="", matcher={})],
        now=1000.0, write=False,
    )
    obs = [Observation(intent_id=decl.intent_id, signal_name="x", met=False, observed_ts=1005.0, note="still pending")]
    deltas_path = tmp_path / "deltas.jsonl"
    out = write_intent_outcome_delta(decl, obs, deltas_path=deltas_path)
    assert out is None, "pending signals must NOT trigger a delta"
    assert not deltas_path.exists()


def test_write_delta_fires_on_real_failure(tmp_path: Path):
    decl = declare_intent(
        actor="Alice", intent_kind="open_app", target="Ace",
        narration="open Ace",
        expected_signals=[
            ExpectedSignal(name="ok", deadline_s=1.0, description="", matcher={}),
            ExpectedSignal(name="miss", deadline_s=1.0, description="", matcher={}),
        ],
        now=1000.0, write=False,
    )
    obs = [
        Observation(intent_id=decl.intent_id, signal_name="ok", met=True, observed_ts=1002.0, note="matched"),
        Observation(intent_id=decl.intent_id, signal_name="miss", met=False, observed_ts=1002.0,
                    note="no matching focus row within deadline"),
    ]
    deltas_path = tmp_path / "deltas.jsonl"
    out = write_intent_outcome_delta(decl, obs, deltas_path=deltas_path)
    assert out is not None
    assert out["truth_label"] == TRUTH_LABEL_DELTA
    assert any(u["name"] == "miss" for u in out["unmet_signals"])
    assert "ok" in out["met_signals"]
    assert deltas_path.exists()
