from __future__ import annotations


def test_mimo_batch_cli_emits_liveness_before_blocking(tmp_path, monkeypatch):
    from System import swarm_gemini_brain as brain
    from System.swarm_cortex_capabilities import record_attached_models

    state = tmp_path / ".sifta_state"
    record_attached_models(
        "mimo:mimo-cli-default",
        ["mimo-auto"],
        default_attached="mimo-auto",
        state_dir=state,
    )
    monkeypatch.setattr(brain, "_STATE", state)
    monkeypatch.setattr(brain, "_mimo_cli_binary", lambda: "/tmp/mimo")

    events: list[tuple[str, object]] = []
    gen = brain._stream_mimo_chat_via_cli(
        model="mimo:mimo-cli-default",
        messages=[{"role": "user", "content": "ping"}],
        timeout_s=1,
    )
    try:
        first = next(gen)
        events.append(first)
    except StopIteration:
        pass

    assert events
    assert events[0][0] == "token"
    assert events[0][1] == brain._BATCH_CLI_LIVENESS_TOKEN


def test_talk_on_token_treats_liveness_as_watchdog_pulse():
    from Applications import sifta_talk_to_alice_widget as talk

    class Dummy:
        pass

    dummy = Dummy()
    dummy._streaming_response = []
    talk.TalkToAliceWidget._on_token(dummy, "\u200b")

    assert dummy._brain_first_token_ts is not None
    assert dummy._streaming_response == []
