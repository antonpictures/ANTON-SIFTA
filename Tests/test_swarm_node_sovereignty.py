import json

from System.swarm_node_sovereignty import (
    build_hardware_profile,
    node_policy_summary,
    parse_ollama_tags,
    parse_system_profiler_hardware,
    resolve_node_model,
    scan_sovereignty_paths,
    scan_text_for_node_leaks,
    serial_hash,
)


M1_PROFILER = """
Hardware:

    Hardware Overview:

      Model Name: Mac mini
      Chip: Apple M1
      Memory: 8 GB
      Serial Number (system): C07FL0JAQ6NV
"""


M5_PROFILER = """
Hardware:

    Hardware Overview:

      Model Name: Mac Studio
      Chip: Apple M5 Max
      Memory: 24 GB
      Serial Number (system): GTH4921YP3
"""


def test_system_profiler_parser_hashes_serial_and_reads_ram():
    facts = parse_system_profiler_hardware(M1_PROFILER)

    assert facts["chip"] == "Apple M1"
    assert facts["ram_gb"] == 8.0
    assert facts["serial"] == "C07FL0JAQ6NV"
    assert facts["serial_hash"] == serial_hash("C07FL0JAQ6NV")
    assert facts["serial_hash"] != "C07FL0JAQ6NV"


def test_ollama_list_parser_keeps_tags_only():
    output = """
NAME                                ID              SIZE      MODIFIED
qwen3.5:0.8b                        abc123          800 MB    1 hour ago
qwen3.5:2b                          def456          2.7 GB    1 hour ago
huihui_ai/gemma-4-abliterated:latest 999999         9.6 GB    yesterday
"""

    assert parse_ollama_tags(output) == (
        "qwen3.5:0.8b",
        "qwen3.5:2b",
        "huihui_ai/gemma-4-abliterated:latest",
    )


def test_m1_web_host_selects_tiny_model_and_blocks_gemma_override():
    profile = build_hardware_profile(
        system_profiler_output=M1_PROFILER,
        installed_models=("huihui_ai/gemma-4-abliterated:latest", "qwen3.5:0.8b", "qwen3.5:2b"),
        node_role={"role": "web_host", "public_services": 5},
    )

    decision = resolve_node_model(profile, app_context="web_chat")

    assert profile.safe_model_tier == "tiny_local"
    assert decision.selected_model == "qwen3.5:0.8b"
    assert not decision.allowed_to_autopull
    assert "huihui_ai/gemma-4-abliterated:latest" in decision.forbidden_models

    rejected = resolve_node_model(
        profile,
        app_context="web_chat",
        owner_override="huihui_ai/gemma-4-abliterated:latest",
    )
    assert rejected.selected_model == ""
    assert rejected.reason.startswith("owner_override_rejected_for_tiny_local")


def test_m5_heavy_node_can_choose_deeper_installed_model_for_tournament():
    profile = build_hardware_profile(
        system_profiler_output=M5_PROFILER,
        installed_models=("qwen3.5:2b", "huihui_ai/gemma-4-abliterated:latest"),
        node_role={"role": "m5_heavy_inference", "public_services": 0},
    )

    decision = resolve_node_model(profile, app_context="tournament")

    assert profile.safe_model_tier == "heavy_local"
    assert decision.selected_model == "huihui_ai/gemma-4-abliterated:latest"
    assert decision.forbidden_models == ()


def test_private_organism_paths_are_blocked_before_public_commit():
    findings = scan_sovereignty_paths(
        [
            ".sifta_state/owner_genesis.json",
            ".sifta_state/work_receipts.jsonl",
            "System/swarm_node_sovereignty.py",
            "secrets/node.pem",
        ]
    )

    reasons = {f.reason for f in findings}
    assert "local organism state" in reasons
    assert "cryptographic secret" in reasons
    assert all(f.severity == "block" for f in findings)


def test_text_scanner_flags_phone_and_private_ip_without_blocking_docs():
    findings = scan_text_for_node_leaks("Call +1 760-555-1212 or hit http://192.168.1.42:8090")

    assert {f.reason for f in findings} == {"possible phone number", "local/private IP address"}
    assert all(f.severity == "review" for f in findings)


def test_policy_summary_is_json_serializable_and_public_safe():
    profile = build_hardware_profile(
        system_profiler_output=M1_PROFILER,
        installed_models=("qwen3.5:0.8b",),
        node_role={"role": "web_host", "public_services": 3},
    )

    summary = node_policy_summary(profile, app_context="web_chat")
    encoded = json.dumps(summary, sort_keys=True)

    assert "C07FL0JAQ6NV" not in encoded
    assert summary["schema"] == "SIFTA_NODE_SOVEREIGNTY_V1"
    assert summary["model_decision"]["selected_model"] == "qwen3.5:0.8b"
    assert summary["federation_rule"] == "exchange_receipts_hashes_summaries_never_raw_sifta_state"
