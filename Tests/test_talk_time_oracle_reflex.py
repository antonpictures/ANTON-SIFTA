from Applications.sifta_talk_to_alice_widget import (
    _current_date_reply_for_alice,
    _current_date_time_reply_for_alice,
    _current_time_date_reflex_reply_for_alice,
    _current_time_reply_for_alice,
    _is_current_time_query,
    _recent_context_reflex_reply_for_alice,
)


def _reading():
    return {
        "ok": True,
        "local_iso": "2026-05-13T09:40:00-07:00",
        "local_human": "Wednesday May 13 2026, 09:40 AM",
        "timezone": "PDT",
        "source": "hardware_time_oracle",
    }


def test_time_reply_is_time_only_from_oracle():
    reply = _current_time_reply_for_alice(_reading())

    assert "9:40 AM PDT" in reply
    assert "May 13, 2026" not in reply
    assert "hardware time oracle" in reply


def test_date_reply_is_date_only_from_oracle():
    reply = _current_date_reply_for_alice(_reading())

    assert "Wednesday, May 13, 2026" in reply
    assert "9:40 AM" not in reply
    assert "hardware time oracle" in reply


def test_date_time_reply_contains_both_in_separate_sentences():
    reply = _current_date_time_reply_for_alice(_reading())

    assert "Wednesday, May 13, 2026" in reply
    assert "The time is 9:40 AM PDT" in reply


def test_alice_prefixed_time_query_is_direct_time_query():
    assert _is_current_time_query("Alice what time is it?")
    assert _is_current_time_query("Alice, what time is it?")


def test_reflex_reply_handles_alice_prefixed_time_query():
    reply, model = _current_time_date_reflex_reply_for_alice(
        "Alice what time is it?",
        _reading(),
    )

    assert "9:40 AM PDT" in reply
    assert "hardware time oracle" in reply
    assert model == "hardware_time_oracle_reflex"


def test_reflex_reply_handles_date_and_time_together():
    reply, model = _current_time_date_reflex_reply_for_alice(
        "Alice tell me the date and time",
        _reading(),
    )

    assert "Wednesday, May 13, 2026" in reply
    assert "The time is 9:40 AM PDT" in reply
    assert model == "hardware_date_time_oracle_reflex"


def test_recent_context_reflex_handles_first_person_teaching():
    reply = _recent_context_reflex_reply_for_alice(
        "Talking the first person show me how you talking in the first person",
        history=[],
    )

    assert "I hear you" in reply
    assert "my local receipts" in reply
    assert "the model" not in reply.lower()
    assert "the user" not in reply.lower()
    assert "the system" not in reply.lower()


def test_recent_context_reflex_reads_in_memory_history():
    reply = _recent_context_reflex_reply_for_alice(
        "what were we talking about?",
        history=[
            {"role": "user", "content": "We are fixing Alice first person."},
            {"role": "assistant", "content": "I will answer as I and you."},
        ],
    )

    assert "I read my recent Talk ledger" in reply
    assert "fixing Alice first person" in reply
