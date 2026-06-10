from Applications import sifta_talk_to_alice_widget as talk


def test_grok_live_talk_timeout_is_shorter_than_general_cloud_default(monkeypatch):
    monkeypatch.delenv("SIFTA_GROK_CORTEX_TIMEOUT_S", raising=False)
    monkeypatch.delenv("SIFTA_CLOUD_BRAIN_TIMEOUT_S", raising=False)

    assert talk._cloud_brain_timeout_s(model="grok:grok-4.3") == 60.0
    assert talk._cloud_brain_timeout_s(model="grok:grok-build") == 60.0
    assert talk._cloud_brain_timeout_s(model="claude:opus") == 120.0


def test_grok_live_talk_timeout_hard_caps_owner_env(monkeypatch):
    monkeypatch.setenv("SIFTA_GROK_CORTEX_TIMEOUT_S", "900")

    assert talk._cloud_brain_timeout_s(model="grok:grok-4.3") == 120.0
