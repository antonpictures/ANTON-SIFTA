"""r1614 — robot grounding triad + history-swimmer epoch pins."""
from __future__ import annotations

import time

from System.swarm_concept_human_anchor import (
    resolve_concept_anchor,
    resolve_concept_anchors,
)
from System.swarm_robot_grounding_triad import (
    TRIAD_QUESTIONS,
    TRUTH_LABEL,
    build_grounding_triad,
    concept_orientation_prompt_block,
    orient_concept_turn,
    pin_owner_place,
    triad_prompt_block,
)


def test_triad_answers_three_human_ground_questions(tmp_path):
    reading = {
        "ok": True,
        "source": "test",
        "local_human": "Friday July 10 2026, 07:40 AM",
        "timezone": "PDT",
        "local_iso": "2026-07-10T07:40:00",
        "epoch": 1783694400.0,
    }
    row = build_grounding_triad(state_dir=tmp_path, reading=reading)
    assert row["truth_label"] == TRUTH_LABEL
    assert list(row["questions"]) == list(TRIAD_QUESTIONS)
    assert "07:40" in row["what_time_is_it"]["answer"] or "7:40" in row["what_time_is_it"]["answer"]
    assert row["what_day_is_it"]["weekday"] == "Friday"
    assert row["what_day_is_it"]["calendar_date"] == "2026-07-10"
    assert row["where_am_i"]["place_truth"] in {"TIMEZONE_HINT_NOT_GPS", "RECEIPT_BACKED"}


def test_place_pin_is_receipt_backed(tmp_path):
    pin_owner_place("Brawley region, California (owner home area)", state_dir=tmp_path, source="test")
    reading = {
        "ok": True,
        "local_human": "Friday July 10 2026, 08:00 AM",
        "timezone": "PDT",
        "local_iso": "2026-07-10T08:00:00",
        "epoch": 1783695600.0,
        "source": "test",
    }
    row = build_grounding_triad(state_dir=tmp_path, reading=reading)
    assert row["where_am_i"]["place_truth"] == "RECEIPT_BACKED"
    assert "Brawley" in row["where_am_i"]["place_label"]


def test_triad_prompt_block_names_all_three():
    reading = {
        "ok": True,
        "local_human": "Friday July 10 2026, 07:40 AM",
        "timezone": "PDT",
        "local_iso": "2026-07-10T07:40:00",
        "epoch": 1783694400.0,
        "source": "test",
    }
    block = triad_prompt_block(reading=reading)
    assert "what_time_is_it" in block
    assert "what_day_is_it" in block
    assert "where_am_i" in block
    assert "ROBOT GROUNDING TRIAD" in block


def test_trojan_war_has_epoch_pin():
    row = resolve_concept_anchor("Trojan War")
    assert row is not None
    era = (row.get("temporal_epoch_pin") or {}).get("era_label", "")
    assert "Bronze" in era or "BCE" in era or "Aegean" in era


def test_einstein_unique_history_swimmer():
    row = resolve_concept_anchor("Einstein")
    assert row is not None
    assert row["primary_birth_anchor"]["human_name"] == "Albert Einstein"
    assert "20th" in (row.get("temporal_epoch_pin") or {}).get("era_label", "")


def test_multiple_concepts_keep_conversation_order():
    rows = resolve_concept_anchors(
        "Start with the Trojan War, compare Einstein, then discuss Donald Trump."
    )
    assert [row["concept_id"] for row in rows] == [
        "trojan_war_myth_history",
        "albert_einstein_physics",
        "donald_trump_political_figure",
    ]


def test_orientation_receipts_previous_to_current_subject_shift(tmp_path):
    first = orient_concept_turn("The Trojan War belongs in history.", state_dir=tmp_path)
    second = orient_concept_turn(
        "Now switch to Einstein and relativity.",
        stt_confidence=0.58,
        state_dir=tmp_path,
    )
    assert first["current_subject"] == "trojan_war_myth_history"
    assert second["previous_subject"] == "trojan_war_myth_history"
    assert second["current_subject"] == "albert_einstein_physics"
    assert second["subject_shift"]["detected"] is True
    assert second["stt"]["uncertain"] is True
    assert second["stt"]["raw_preserved"] is True


def test_orientation_prompt_keeps_observation_and_historical_time_distinct(tmp_path):
    block = concept_orientation_prompt_block(
        "We are talking about the Trojan War and then Einstein.",
        stt_confidence=0.7,
        state_dir=tmp_path,
    )
    assert "subject_sequence=trojan_war_myth_history -> albert_einstein_physics" in block
    assert "historical_epoch=" in block
    assert "observation time/place separate" in block


def test_transient_place_pin_expires(tmp_path):
    pin_owner_place(
        "owner kitchen with Alice computer body",
        source="owner_stream",
        ttl_s=1.0,
        now=time.time() - 10.0,
        state_dir=tmp_path,
    )
    row = build_grounding_triad(state_dir=tmp_path)
    assert row["where_am_i"]["place_source"] == "timezone_hint_only"


def test_kitchen_source_defaults_four_hour_ttl(tmp_path):
    now = time.time()
    pin = pin_owner_place(
        "kitchen temporary situating",
        source="owner_kitchen_photo",
        now=now,
        state_dir=tmp_path,
    )
    assert pin["expires_ts"] > now
    # ~4 hours default for kitchen/photo observations
    assert abs((pin["expires_ts"] - now) - 4 * 3600) < 2.0


def test_spoken_grounding_answers_time_day_place_and_troy_dual_clock(tmp_path):
    from System.swarm_robot_grounding_triad import spoken_grounding_answer

    reading = {
        "ok": True,
        "local_human": "Friday July 10 2026, 08:41 AM",
        "timezone": "PDT",
        "local_iso": "2026-07-10T08:41:00",
        "epoch": 1783694460.0,
        "source": "test",
    }
    pin_owner_place(
        "Brawley region kitchen",
        source="owner_declared",
        state_dir=tmp_path,
    )
    ans = spoken_grounding_answer(
        "Alice — what time is it, what day is it, where are you? "
        "And when did the Trojan War happen versus when did we talk about it?",
        state_dir=tmp_path,
        reading=reading,
    )
    low = ans.lower()
    assert "friday" in low
    assert "08:41" in ans or "8:41" in ans
    assert "brawley" in low
    assert "bronze" in low or "bce" in low or "aegean" in low
    assert "observation" in low or "conversation" in low


def test_orientation_separates_observation_and_historical_clocks(tmp_path):
    reading = {
        "ok": True,
        "local_human": "Friday July 10 2026, 07:51 AM",
        "timezone": "PDT",
        "local_iso": "2026-07-10T07:51:00",
        "epoch": 1783695060.0,
        "source": "test",
    }
    row = orient_concept_turn(
        "When did the Trojan War happen versus when did we talk about it?",
        stt_confidence=0.72,
        state_dir=tmp_path,
        reading=reading,
    )
    assert row["observation_clock"]["kind"] == "conversation_now"
    assert row["historical_clock"]["kind"] == "concept_human_history"
    assert "Bronze" in (row["historical_clock"].get("epoch") or "") or "BCE" in (
        row["historical_clock"].get("epoch") or ""
    )
    assert "07:51" in str(row["observation_clock"]["time"].get("answer") or "")
    assert row["stt"]["raw_preserved"] is True
