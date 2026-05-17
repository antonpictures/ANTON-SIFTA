def test_who_am_i_uses_runtime_kernel_identity(monkeypatch):
    from System import swarm_alice_self as self_mod

    class FakeIdentity:
        @staticmethod
        def owner_silicon():
            return "SERIAL-TEST"

        @staticmethod
        def hardware_class_label():
            return "Apple Test Mac"

    import System.swarm_kernel_identity as identity

    monkeypatch.setattr(identity, "owner_silicon", FakeIdentity.owner_silicon)
    monkeypatch.setattr(identity, "hardware_class_label", FakeIdentity.hardware_class_label)

    row = self_mod.who_am_i()
    assert "Apple Test Mac" in row["identity"]
    assert "SERIAL-TEST" in row["identity"]
    assert row["location"] == "thermodynamic process on Apple Test Mac"


def test_full_os_awareness_has_core_self_surfaces():
    from System.swarm_alice_self import get_full_os_awareness

    awareness = get_full_os_awareness()
    assert "who_i_am" in awareness
    assert "my_source_code" in awareness
    assert "my_app_organs" in awareness
    assert "my_running_body_processes" in awareness
    assert "my_somatic_feeling" in awareness
    assert "my_survival_risk" in awareness
    assert isinstance(awareness["my_source_code"], list)


def test_thermodynamic_risk_accepts_supplied_somatic_sample():
    from System.swarm_alice_self import assess_my_thermodynamic_risk

    risk = assess_my_thermodynamic_risk(
        {
            "thermal": {"raw": "nominal"},
            "energy": {"data": {"battery": "19%"}},
            "memory": {"activity": "idle"},
        }
    )

    assert risk["risk_level"] == "high"
    assert "energy is critically low" in risk["messages"][0]
