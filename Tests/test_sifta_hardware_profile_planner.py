from System.sifta_hardware_profile_planner import HardwareFacts, plan_for_hardware


def test_m5_foundry_plan_keeps_gemma4_primary():
    plan = plan_for_hardware(
        HardwareFacts(os_name="Darwin", machine="arm64", memory_gb=24, cpu_brand="Apple M5")
    )

    assert plan.hardware_role == "M5_FOUNDRY"
    assert any(slot.name == "sifta-gemma4-alice:latest" for slot in plan.local_models)
    assert not any(slot.name == "sifta-gemma4-alice:latest" for slot in plan.skipped_models)


def test_mac_8gb_sentry_skips_gemma4():
    plan = plan_for_hardware(
        HardwareFacts(os_name="Darwin", machine="arm64", memory_gb=8, cpu_brand="Apple M1")
    )

    assert plan.hardware_role == "MAC_SENTRY"
    assert any(slot.name == "qwen3.5:4b" for slot in plan.local_models)
    assert any(slot.name == "sifta-gemma4-alice:latest" for slot in plan.skipped_models)


def test_pi5_edge_scout_uses_receipts_and_optional_gguf():
    plan = plan_for_hardware(
        HardwareFacts(
            os_name="Linux",
            machine="aarch64",
            memory_gb=8,
            cpu_brand="Raspberry Pi 5 Model B",
            is_raspberry_pi=True,
        )
    )

    assert plan.hardware_role == "PI5_EDGE_SCOUT"
    assert any(slot.name == "qwen3.5:0.8b" for slot in plan.local_models)
    assert any("llama.cpp" in lane for lane in plan.optional_lanes)
    assert any("Hailo" in lane for lane in plan.optional_lanes)


def test_tiny_sensor_limb_has_no_local_models():
    plan = plan_for_hardware(
        HardwareFacts(os_name="Linux", machine="armv7l", memory_gb=1, cpu_brand="field controller")
    )

    assert plan.hardware_role == "TINY_SENSOR_LIMB"
    assert plan.local_models == []
    assert any(slot.name == "qwen3.5:0.8b" for slot in plan.skipped_models)
