from pathlib import Path

from Applications import sifta_talk_to_alice_widget as talk


def test_talk_worker_applies_live_prompt_budget_before_dispatch():
    source = Path(talk.__file__).read_text(encoding="utf-8")

    assert "clamp_live_turn_prompt" in source
    assert "[prompt live-budget] applied" in source
    assert "sysprompt_chars={len(sysprompt)}" in source


def test_grok_live_talk_timeout_is_shorter_than_general_cloud_default(monkeypatch, tmp_path):
    monkeypatch.delenv("SIFTA_GROK_CORTEX_TIMEOUT_S", raising=False)
    monkeypatch.delenv("SIFTA_CLOUD_BRAIN_TIMEOUT_S", raising=False)
    monkeypatch.delenv("SIFTA_MIMO_CORTEX_TIMEOUT_S", raising=False)
    monkeypatch.delenv("SIFTA_TEACHER_CLI_TIMEOUT_S", raising=False)

    assert talk._cloud_brain_timeout_s(model="grok:grok-4.3") == 60.0
    assert talk._cloud_brain_timeout_s(model="grok:grok-build") == 60.0
    assert talk._cloud_brain_timeout_s(model="claude:opus") == 120.0
    assert talk._cloud_brain_timeout_s(
        model="mimo:mimo-cli-default",
        state_dir=tmp_path,
    ) == 120.0


def test_mimo_timeout_is_stigmergic_from_failure_receipts(monkeypatch, tmp_path):
    from System.swarm_stigmergic_timeout_policy import record_timeout_outcome

    monkeypatch.delenv("SIFTA_MIMO_CORTEX_TIMEOUT_S", raising=False)
    monkeypatch.delenv("SIFTA_TEACHER_CLI_TIMEOUT_S", raising=False)
    record_timeout_outcome(
        "mimo:mimo-cli-default",
        outcome="timeout",
        timeout_s=120,
        elapsed_s=120,
        state_dir=tmp_path,
    )

    assert talk._cloud_brain_timeout_s(
        model="mimo:mimo-cli-default",
        state_dir=tmp_path,
    ) == 180.0


def test_mimo_live_talk_timeout_has_own_owner_override(monkeypatch):
    monkeypatch.delenv("SIFTA_TEACHER_CLI_TIMEOUT_S", raising=False)
    monkeypatch.setenv("SIFTA_MIMO_CORTEX_TIMEOUT_S", "275")

    assert talk._cloud_brain_timeout_s(model="mimo:mimo-cli-default") == 275.0
    assert talk._cloud_brain_timeout_s(model="claude:opus") == 120.0


def test_mimo_live_talk_timeout_hard_caps_owner_env(monkeypatch):
    monkeypatch.setenv("SIFTA_MIMO_CORTEX_TIMEOUT_S", "900")

    assert talk._cloud_brain_timeout_s(model="mimo:mimo-cli-default") == 300.0


def test_grok_self_screenshot_and_colistening_turns_get_full_live_cap(monkeypatch):
    monkeypatch.delenv("SIFTA_GROK_CORTEX_TIMEOUT_S", raising=False)
    monkeypatch.delenv("SIFTA_CLOUD_BRAIN_TIMEOUT_S", raising=False)

    assert talk._cloud_brain_timeout_s(
        model="grok:grok-4.3",
        user_text="are you listernig with me?? /sc Joe Rogan Experience #2513 - Dean Radin",
    ) == 120.0
    assert talk._cloud_brain_timeout_s(
        model="grok:grok-build",
        user_text="SELF-SCREENSHOT CORTEX TURN: Alice Browser is on YouTube",
    ) == 120.0
    assert talk._cloud_brain_timeout_s(
        model="xai:grok-build",
        user_text="podcast listening together",
    ) == 120.0


def test_grok_live_talk_timeout_hard_caps_owner_env(monkeypatch):
    monkeypatch.setenv("SIFTA_GROK_CORTEX_TIMEOUT_S", "900")

    assert talk._cloud_brain_timeout_s(model="grok:grok-4.3") == 120.0
