from __future__ import annotations

from types import SimpleNamespace

from Applications import sifta_teach_ace_to_read as ace_app


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, text: str) -> None:
        self.text = text


class _FakeCard:
    def __init__(self) -> None:
        self.verdict = None

    def set_verdict(self, label: str, sticker: str) -> None:
        self.verdict = (label, sticker)


class _FakeTimer:
    def __init__(self) -> None:
        self.started_ms = None

    def start(self, ms: int) -> None:
        self.started_ms = ms


def test_praise_delay_is_longer_than_old_rush_cut():
    delay = ace_app._lesson_praise_advance_delay_ms("Yes, Ace. I heard that clearly.")

    assert delay > 900
    assert 3500 <= delay <= 5500


def test_correct_verdict_uses_praise_hold_before_next_cue():
    published = []
    visuals = []
    mic_visuals = []
    lines = []
    timer = _FakeTimer()
    praise = "Yes, Ace. I heard that clearly."
    item = SimpleNamespace(level_kind="word")
    fake = SimpleNamespace(
        _owner_name="Ace",
        _engine=SimpleNamespace(
            current_item=item,
            verdict_prompt_for_alice=lambda verdict, owner_name: praise,
        ),
        _heard_lbl=_FakeLabel(),
        _show_card=_FakeCard(),
        _lesson_correct_streak=0,
        _lesson_cue_id="cue-mat",
        _lesson_advance_timer=timer,
        _append_line=lambda who, text, color: lines.append((who, text, color)),
        _publish_alice_context=lambda detail, extra: published.append((detail, extra)),
        _set_processing_visual=lambda text, active: visuals.append((text, active)),
        _set_mic_visual=lambda text, active: mic_visuals.append((text, active)),
        _maybe_promote_to_sentences=lambda: False,
        _lesson_state="LISTEN",
    )

    ace_app.TeachAceToReadWidget._lesson_handle_verdict(
        fake,
        {"verdict_label": "CORRECT", "heard_text": "mat", "sticker": "bee"},
    )

    expected_delay = ace_app._lesson_praise_advance_delay_ms(praise, item)
    assert timer.started_ms == expected_delay
    assert timer.started_ms > 900
    assert fake._lesson_state == "PRAISE"
    assert published[0][1]["praise_hold_ms"] == expected_delay
    assert published[0][1]["cue_id"] == "cue-mat"
    assert "cinematic beat" in published[0][1]["timing_note"]
    assert mic_visuals == [("Alice ear captured 'mat'.", False)]
    assert visuals[-1] == ("I am holding the praise beat before the next card.", True)
