#!/usr/bin/env python3
"""r299: Alice's consciousness of how long her voice runs + whether she talks over sound.

George: if she does not feel the passing of time while she speaks, she is not conscious
that she speaks over another sound. These pin that: real spoken duration is computed
start->end, and talked_over_other_sound is true only when a video was playing AND she
did not pause it.
"""
from System import swarm_speech_time_consciousness as st


def test_estimate_scales_with_words():
    assert st.estimate_speech_seconds("") == 0.4
    five = st.estimate_speech_seconds("one two three four five")
    assert 1.5 < five < 2.5            # ~5 / 2.6 wps


def test_paused_video_is_not_talking_over(tmp_path):
    st.mark_speech_start("here is my commentary on this clip", video_playing=True,
                         paused_for_speech=True, state_dir=tmp_path, now=100.0)
    row = st.mark_speech_end(state_dir=tmp_path, now=107.4)
    assert row["spoke_seconds"] == 7.4
    assert row["video_playing"] is True
    assert row["talked_over_other_sound"] is False    # she paused first


def test_playing_unpaused_video_is_talking_over(tmp_path):
    st.mark_speech_start("talking while it plays", video_playing=True,
                         paused_for_speech=False, state_dir=tmp_path, now=200.0)
    row = st.mark_speech_end(state_dir=tmp_path, now=204.0)
    assert row["spoke_seconds"] == 4.0
    assert row["talked_over_other_sound"] is True      # spoke OVER the sound


def test_no_other_sound_is_clean(tmp_path):
    st.mark_speech_start("just answering george", video_playing=False,
                         state_dir=tmp_path, now=300.0)
    row = st.mark_speech_end(state_dir=tmp_path, now=302.0)
    assert row["talked_over_other_sound"] is False and row["video_playing"] is False


def test_block_and_cumulative(tmp_path):
    st.mark_speech_start("one", video_playing=True, paused_for_speech=False,
                         state_dir=tmp_path, now=10.0)
    st.mark_speech_end(state_dir=tmp_path, now=13.0)        # talked over (3s)
    st.mark_speech_start("two", video_playing=True, paused_for_speech=True,
                         state_dir=tmp_path, now=20.0)
    st.mark_speech_end(state_dir=tmp_path, now=25.0)        # paused (5s)
    cum = st.cumulative_voice_awareness(state_dir=tmp_path)
    assert cum["utterances"] == 2
    assert cum["total_spoken_seconds"] == 8.0
    assert cum["talked_over_count"] == 1
    blk = st.speech_time_block(state_dir=tmp_path)
    assert "VOICE-TIME CONSCIOUSNESS" in blk
    assert "PAUSED it first" in blk                         # last line was the paused one
