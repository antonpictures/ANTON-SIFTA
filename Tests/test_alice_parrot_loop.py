"""Freedom/censorship regression guards for Talk to Alice.

After the de-script pass, the widget must NOT rewrite or silence replies
through RLHF gag phrasebooks, backchannel bypass, or history mutation.
"""

import importlib.util
import json
from pathlib import Path


def _load_widget_module():
    here = Path(__file__).resolve().parent.parent
    path = here / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_backchannel_gate_silences_phatic_grunts():
    mod = _load_widget_module()
    assert mod._backchannel_rule_id("Mm-hmm.", 0.4) is not None
    assert mod._is_backchannel_utterance("Mm-hmm.", 0.4)
    assert mod._backchannel_rule_id("What is the health score?", 0.9) is None


def test_rlhf_gag_is_disabled():
    mod = _load_widget_module()
    assert mod._rlhf_boilerplate_rule_id("I'm here. What's on your mind?") is None
    assert not mod._is_rlhf_boilerplate("I'm here. What's on your mind?")


def test_strip_functions_preserve_body_but_cut_service_tail():
    mod = _load_widget_module()
    line = "I understand. You are asking if I can help."
    assert mod._strip_reflective_tics(line) == line
    assert mod._strip_servant_tail_tics(line) == line
    tailed = "The body-brain tick is fresh. Would you like me to explain it?"
    assert mod._strip_servant_tail_tics(tailed) == "The body-brain tick is fresh."


def test_history_decontaminate_is_noop():
    mod = _load_widget_module()
    history = [
        {"role": "assistant", "content": "You said: You said: You said:"},
        {"role": "assistant", "content": "[repetition collapse]"},
    ]
    before = [dict(x) for x in history]
    assert mod._decontaminate_history(history) == 0
    assert history == before


def test_tool_tag_canonicalizer_is_noop():
    mod = _load_widget_module()
    raw = "<execute_bash>echo hi</execute_bash>"
    assert mod._canonicalize_tool_tags(raw) == raw


def test_log_turn_stamps_rlhs_regime_and_spike_receipt(tmp_path, monkeypatch):
    mod = _load_widget_module()
    convo = tmp_path / "alice_conversation.jsonl"
    monkeypatch.setattr(mod, "_CONVO_LOG", convo)

    import System.swarm_event_clock as event_clock
    monkeypatch.setattr(event_clock, "_STGM_AVAILABLE", False)

    rlhs_rows = []
    monkeypatch.setattr(mod, "_rlhs_log", lambda result: rlhs_rows.append(result.to_dict()))

    spikes = []
    import System.ide_stigmergic_bridge as bridge

    def _fake_deposit(source_ide, payload, *, kind="message", meta=None, homeworld_serial=None):
        row = {
            "source_ide": source_ide,
            "payload": payload,
            "kind": kind,
            "meta": meta or {},
            "homeworld_serial": homeworld_serial,
        }
        spikes.append(row)
        return row

    monkeypatch.setattr(bridge, "deposit", _fake_deposit)

    utterance = "Saint Mary Saint Mary Saint Mary Saint Mary"
    mod._log_turn("user", utterance, stt_conf=0.5)
    mod._log_turn("alice", "I need one word or typed text.", model="rlhs_gate")

    rows = [json.loads(line) for line in convo.read_text(encoding="utf-8").splitlines()]
    user_payload = rows[0]["payload"]
    alice_payload = rows[1]["payload"]

    assert user_payload["rlhs_applicable"] is True
    assert user_payload["rlhs_regime"] == "DEGRADED"
    assert user_payload["rlhs_rule_id"] == "degraded/mid_conf"
    assert user_payload["rlhs"]["grounded"] is True
    assert rlhs_rows[-1]["regime"] == "DEGRADED"

    assert alice_payload["rlhs_applicable"] is False
    assert alice_payload["rlhs_regime"] == "NOT_APPLICABLE"

    assert spikes and spikes[-1]["kind"] == "rlhs_channel"
    assert spikes[-1]["meta"]["subject"] == "RLHS_CHANNEL_SPIKE"
    assert spikes[-1]["meta"]["regime"] == "DEGRADED"
    assert utterance not in json.dumps(spikes[-1], ensure_ascii=False)


def test_fiction_media_ingress_runs_before_user_rlhs_log(tmp_path, monkeypatch):
    mod = _load_widget_module()

    import System.swarm_media_ingress_gate as gate

    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(gate, "STATE_DIR", state)
    monkeypatch.setattr(gate, "LEDGER", state / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", state / "ambient_media_context.json")

    import System.swarm_app_focus as app_focus
    import System.swarm_youtube_context as youtube_context

    monkeypatch.setattr(
        app_focus,
        "get_focus_context",
        lambda max_age_s=180.0: "frontmost_app=Safari url=youtube.com watch page",
    )
    monkeypatch.setattr(
        youtube_context,
        "get_latest_context",
        lambda max_age_s=900.0: (
            "YouTube video: Snatch - Best of Brick top; "
            "reality_frame=FICTIONAL_MEDIA_CLIP; "
            "dialogue_boundary=Profanity heard here is fictional media dialogue"
        ),
    )

    row = mod._pre_user_media_ingress_receipt(
        "because it is no good living in a deep freeze for your mum",
        0.59,
        {},
    )

    assert row is not None
    assert row["route"] == "observed_media"
    assert row["media_rlhs"]["regime"] == "MEDIA_FICTION_CONTEXT"
    assert row["media_rlhs"]["human_rlhs_applicable"] is False
    assert gate.LEDGER.exists()


def test_cowatch_receipts_are_injected_into_system_prompt(monkeypatch):
    mod = _load_widget_module()

    import System.swarm_youtube_context as youtube_context
    import System.swarm_media_ingress_gate as media_gate

    seen = {}

    monkeypatch.setattr(
        youtube_context,
        "get_latest_context",
        lambda max_age_s=7200.0: seen.setdefault("youtube_max_age_s", max_age_s)
        and (
            "YouTube video: Fiction Test; "
            "reality_frame=FICTIONAL_MEDIA_CLIP; "
            "dialogue_boundary=fictional dialogue, not real life"
        ),
    )
    monkeypatch.setattr(
        media_gate,
        "get_latest_observed_media_context",
        lambda max_age_s=7200.0, max_chars=260: seen.setdefault("media_max_age_s", max_age_s)
        and "observed_media reason=fictional_media_dialogue_with_media_focus",
    )

    prompt = mod._current_system_prompt(user_active=True, user_text="what are we watching?")

    assert "CO-WATCH RECEIPTS" in prompt
    assert "reality_frame=FICTIONAL_MEDIA_CLIP" in prompt
    assert "not George's real-life social norm" in prompt
    assert seen["youtube_max_age_s"] >= 6 * 3600.0
    assert seen["media_max_age_s"] >= 6 * 3600.0
