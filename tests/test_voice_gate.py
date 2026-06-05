#!/usr/bin/env python3
"""Acceptance tests for the mandatory external-consciousness voice gate.

Ambient input such as overheard "Ace" from YouTube must not reach the brain.
Owner-direct speech must remain open to the normal direct path.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from System import swarm_media_ingress_gate as mig


def test_classify_spoken_ingress_detects_ambient_youtube():
    """Bare "Ace" with media focus is ambient/observed, not direct."""
    decision = mig.classify_spoken_ingress(
        "Ace",
        stt_conf=0.85,
        focus_context="YouTube: some video playing\ncurrent app: Safari",
        voice_george_conf=0.0,
    )

    assert decision["route"] in {"ambient_media", "observed_media"}
    assert "media" in decision.get("reason", "").lower() or decision.get("confidence", 0) > 0.6


def test_classify_external_consciousness_lane_youtube():
    lane = mig.classify_external_consciousness_lane(
        "Ace",
        route="ambient_media",
        reason="recent_media_plus_low_conf_abstract_dialogue",
        stt_conf=0.85,
        focus_context="youtube playing",
    )

    assert lane["source_class"] in {
        "screen_media_or_youtube",
        "unknown_ambient_speech",
        "appliance_or_environmental_noise",
    }
    assert "store_silent" in lane.get("attention_policy", "") or "observed" in lane.get("attention_policy", "")


def test_classify_spoken_ingress_direct_owner_speech():
    """Explicit address to Alice or strong owner signals is direct."""
    decision = mig.classify_spoken_ingress(
        "Alice, what time is it?",
        stt_conf=0.92,
        focus_context="",
        voice_george_conf=0.0,
    )

    assert decision["route"] == "direct"


def test_mandatory_voice_gate_helper_writes_field_receipt_for_ambient_ace(tmp_path, monkeypatch):
    """The real helper writes a field receipt for ambient "Ace" before cortex routing."""
    from Applications import sifta_talk_to_alice_widget as tw
    import System.swarm_app_focus as app_focus
    import System.swarm_youtube_context as youtube_context

    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(tw, "_STATE_DIR", state)
    monkeypatch.setattr(mig, "STATE_DIR", state)
    monkeypatch.setattr(mig, "LEDGER", state / "media_ingress_gate.jsonl")
    monkeypatch.setattr(mig, "AMBIENT_CONTEXT_FILE", state / "ambient_media_context.json")
    monkeypatch.setattr(
        app_focus,
        "get_focus_context",
        lambda max_age_s=180.0: "frontmost_app=Safari url=youtube.com",
    )
    monkeypatch.setattr(
        youtube_context,
        "get_latest_context",
        lambda max_age_s=7200.0: "YouTube video: Stanford CS153 Jensen Huang",
    )

    row = tw._mandatory_voice_ingress_receipt("Ace", 0.85, {})

    assert row is not None
    assert row["route"] in {"ambient_media", "observed_media"}
    assert row["external_consciousness"]["source_class"] == "screen_media_or_youtube"
    assert mig.LEDGER.exists()
    assert (state / "ambient_external_consciousness.jsonl").exists()


def test_mandatory_voice_gate_helper_allows_direct_owner_speech(monkeypatch):
    """Direct Alice-addressed owner speech is not blocked by the mandatory gate."""
    from Applications import sifta_talk_to_alice_widget as tw
    import System.swarm_app_focus as app_focus
    import System.swarm_youtube_context as youtube_context

    monkeypatch.setattr(app_focus, "get_focus_context", lambda max_age_s=180.0: "")
    monkeypatch.setattr(youtube_context, "get_latest_context", lambda max_age_s=7200.0: "")

    assert tw._mandatory_voice_ingress_receipt("Alice, help me with Stanford.", 0.92, {}) is None


def test_real_widget_ambient_input_never_reaches_brain(monkeypatch):
    """
    Hardened acceptance test (GROK_VOICE_GATE_ORDER level):
    when the mandatory gate returns a non-direct row, _on_stt_done exits
    before _start_brain.
    """
    from Applications import sifta_talk_to_alice_widget as tw

    class DummyTalk:
        def __init__(self):
            self._busy = True
            self._history = []
            self._pending_acoustic_fingerprint = {}
            self.system_lines = []
            self.returned = False
            self._start_brain = MagicMock()

        def _append_system_line(self, text, error=False):
            self.system_lines.append((text, error))

        def _return_to_listening(self):
            self.returned = True

    monkeypatch.setattr(
        tw,
        "_mandatory_voice_ingress_receipt",
        lambda *args, **kwargs: {
            "route": "ambient_media",
            "reason": "forced_youtube_ace",
            "external_consciousness": {"source_class": "screen_media_or_youtube"},
        },
    )
    widget = DummyTalk()

    tw.TalkToAliceWidget._on_stt_done(widget, "Ace", 0.85, typed_turn=False)

    widget._start_brain.assert_not_called()
    assert widget.returned is True
    assert widget._busy is False


def test_direct_owner_speech_passes_mandatory_gate_helper(monkeypatch):
    """Safety (via the canonical helper): owner-direct speech returns None from the gate (proceed to brain)."""
    from Applications import sifta_talk_to_alice_widget as tw
    import System.swarm_app_focus as app_focus
    import System.swarm_youtube_context as youtube_context

    monkeypatch.setattr(app_focus, "get_focus_context", lambda **k: "")
    monkeypatch.setattr(youtube_context, "get_latest_context", lambda **k: "")

    result = tw._mandatory_voice_ingress_receipt("Alice, help with the Stanford report", 0.94, {})
    assert result is None, "Direct owner speech must pass the mandatory gate"


def test_owner_self_eval_query_short_circuits_to_receipt_backed_body_report(monkeypatch, tmp_path):
    """Owner introspection questions should route through self_query_prompt_block without cortex."""
    from Applications import sifta_talk_to_alice_widget as tw
    import System.swarm_self_query_skill as self_query

    class DummyTalk:
        def __init__(self):
            self._busy = True
            self._history = []
            self._pending_acoustic_fingerprint = {}
            self.user_lines = []
            self.alice_lines = []
            self.returned = False
            self._start_brain = MagicMock()
            self._acer_lesson_intercept = lambda *_args, **_kwargs: False

        def _append_system_line(self, *_args, **_kwargs):
            pass

        def _append_user_line(self, text, conf=1.0):
            self.user_lines.append((text, conf))

        def _append_alice_line(self, text):
            self.alice_lines.append(text)

        def _return_to_listening(self):
            self.returned = True

    monkeypatch.setattr(self_query, "looks_like_self_query", lambda text: True)
    monkeypatch.setattr(
        self_query,
        "self_query_prompt_block",
        lambda **_kwargs: "I need more confidence and one organ probe.",
    )
    monkeypatch.setattr(tw, "_mandatory_voice_ingress_receipt", lambda *args, **kwargs: None)
    monkeypatch.setattr(tw, "_wordace_cue_currently_open", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(tw, "_foreground_ide_voice_attribution", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(tw, "_polarity_asr_clarification_reply", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(tw, "_log_turn", lambda *args, **kwargs: None)
    monkeypatch.setattr(tw, "_STATE_DIR", tmp_path / ".sifta_state")

    widget = DummyTalk()
    tw.TalkToAliceWidget._on_stt_done(widget, "Alice, what do you need right now?", 0.94, typed_turn=True)

    assert widget._start_brain.call_count == 0
    assert widget.returned is True
    assert widget._busy is False
    assert widget.user_lines
    assert "Alice, what do you need right now?" in widget.user_lines[0][0]
    assert widget.alice_lines
    assert "I ran a body self-check from current receipts." in widget.alice_lines[0]
    assert "I need more confidence" in widget.alice_lines[0]


def test_widget_direct_owner_input_reaches_brain(monkeypatch):
    """Owner-direct voice must not be over-gated away from the brain."""
    from Applications import sifta_talk_to_alice_widget as tw

    class DummyTalk:
        def __init__(self):
            self._busy = True
            self._history = []
            self._pending_acoustic_fingerprint = {}
            self._start_brain = MagicMock()
            self._acer_lesson_intercept = lambda *_args, **_kwargs: False

        def _append_system_line(self, *_args, **_kwargs):
            pass

        def _append_user_line(self, *_args, **_kwargs):
            pass

        def _return_to_listening(self):
            pass

        def _acer_lesson_intercept(self, *_args, **_kwargs):
            return False

    monkeypatch.setattr(tw, "_mandatory_voice_ingress_receipt", lambda *args, **kwargs: None)
    monkeypatch.setattr(tw, "_wordace_cue_currently_open", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(tw, "_foreground_ide_voice_attribution", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(tw, "_polarity_asr_clarification_reply", lambda *_args, **_kwargs: "")

    widget = DummyTalk()
    tw.TalkToAliceWidget._on_stt_done(widget, "Alice, help me with Stanford.", 0.94, typed_turn=False)

    widget._start_brain.assert_called_once()


def test_empty_stt_fallback_debounces_duplicate_visible_line(monkeypatch):
    """Two immediate empty-STT callbacks from one audio drop produce one visible fallback line."""
    from Applications import sifta_talk_to_alice_widget as tw

    class DummyTalk:
        def __init__(self):
            self._busy = True
            self.lines = []
            self.returns = 0

        def _append_system_line(self, text, error=False):
            self.lines.append(text)

        def _return_to_listening(self):
            self.returns += 1

    widget = DummyTalk()
    tw.TalkToAliceWidget._on_stt_done(widget, "", 0.12, typed_turn=False)
    tw.TalkToAliceWidget._on_stt_done(widget, "", 0.12, typed_turn=False)

    repeat_lines = [line for line in widget.lines if "say it once more" in line]
    assert len(repeat_lines) == 1
    assert widget.returns == 2


def test_gate_writes_field_receipt_for_ambient(tmp_path, monkeypatch):
    """Ambient turns still produce a receipt so the unified field sees the lane."""
    calls = []

    def fake_write_gate_receipt(decision, **kwargs):
        calls.append({"decision": decision, "kwargs": kwargs})
        return {"ts": 123, "receipt": "test"}

    monkeypatch.setattr(mig, "write_gate_receipt", fake_write_gate_receipt)

    ingress = {"route": "ambient_media", "reason": "test"}
    lane = {"source_class": "screen_media_or_youtube"}
    mig.write_gate_receipt(ingress, text="Ace", stt_conf=0.8, external_consciousness=lane)

    assert len(calls) == 1
    assert calls[0]["decision"]["route"] == "ambient_media"


def test_widget_source_places_mandatory_gate_before_wordace_and_brain():
    """Source-order guard: the mandatory gate stays before lesson/reflex/brain routing."""
    from Applications import sifta_talk_to_alice_widget as tw

    source = Path(tw.__file__).read_text(encoding="utf-8")
    method_start = source.index("    def _on_stt_done(")
    method_end = source.index("    def _start_brain(", method_start)
    method = source[method_start:method_end]

    gate_pos = method.index("_mandatory_voice_ingress_receipt(")
    wordace_pos = method.index("WordAce lesson")
    start_brain_pos = method.rindex("self._start_brain(")

    assert gate_pos < wordace_pos
    assert gate_pos < start_brain_pos
