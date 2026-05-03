from __future__ import annotations

import json
from types import SimpleNamespace


def test_primary_cortex_options_only_installed_models_are_selectable():
    from System.swarm_primary_cortex_switcher import primary_cortex_options

    options = primary_cortex_options(
        installed=["sifta-gemma4-alice:latest", "qwen3.5:2b", "sifta-classifier-c1:latest"],
        current="sifta-gemma4-alice",
    )

    active = options[0]
    assert active["model"] == "sifta-gemma4-alice:latest"
    assert active["installed"] is True
    assert active["active"] is True

    missing = [o for o in options if o["model"] == "gemma4:26b"][0]
    assert missing["installed"] is False
    assert "(not installed)" in missing["label"]
    assert "sifta-classifier-c1:latest" not in {o["model"] for o in options}


def test_installed_ollama_models_default_timeout_handles_slow_boot(monkeypatch):
    from System import swarm_primary_cortex_switcher as switcher

    captured = {}

    def fake_run(cmd, *, capture_output, text, timeout, check):
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "NAME                         ID              SIZE      MODIFIED\n"
                "sifta-gemma4-alice:latest    abcdef123456    9.6 GB    1 minute ago\n"
            ),
        )

    monkeypatch.setattr(switcher.subprocess, "run", fake_run)

    rows = switcher.installed_ollama_models()

    assert captured["cmd"] == ["ollama", "list"]
    assert captured["timeout"] == 10.0
    assert rows[0]["name"] == "sifta-gemma4-alice:latest"


def test_set_primary_cortex_persists_app_override_and_receipt(tmp_path, monkeypatch):
    from System import sifta_inference_defaults as defaults
    from System import swarm_primary_cortex_switcher as switcher

    monkeypatch.setattr(defaults, "_STATE", tmp_path)
    monkeypatch.setattr(defaults, "_ASSIGNMENTS", tmp_path / "swimmer_ollama_assignments.json")
    monkeypatch.setattr(switcher, "_STATE", tmp_path)
    monkeypatch.setattr(switcher, "_LEDGER", tmp_path / "primary_cortex_switches.jsonl")

    receipt = switcher.set_primary_cortex(
        "qwen3.5:2b",
        installed=["sifta-gemma4-alice:latest", "qwen3.5:2b"],
        source="pytest",
    )

    assert defaults.resolve_ollama_model(app_context="talk_to_alice") == "qwen3.5:2b"
    assert receipt["selected_model"] == "qwen3.5:2b"
    rows = [
        json.loads(line)
        for line in (tmp_path / "primary_cortex_switches.jsonl").read_text().splitlines()
    ]
    assert rows[-1]["truth_label"] == "PRIMARY_CORTEX_SWITCH_RECEIPT"
    assert rows[-1]["source"] == "pytest"


def test_set_primary_cortex_rejects_missing_model(tmp_path, monkeypatch):
    from System import sifta_inference_defaults as defaults
    from System import swarm_primary_cortex_switcher as switcher

    monkeypatch.setattr(defaults, "_STATE", tmp_path)
    monkeypatch.setattr(defaults, "_ASSIGNMENTS", tmp_path / "swimmer_ollama_assignments.json")
    monkeypatch.setattr(switcher, "_STATE", tmp_path)
    monkeypatch.setattr(switcher, "_LEDGER", tmp_path / "primary_cortex_switches.jsonl")

    try:
        switcher.set_primary_cortex("gemma4:26b", installed=["sifta-gemma4-alice:latest"])
    except ValueError as exc:
        assert "not installed" in str(exc)
    else:
        raise AssertionError("missing cortex should not be selectable")

    assert not (tmp_path / "primary_cortex_switches.jsonl").exists()


def test_set_primary_cortex_blocks_failed_required_verification(tmp_path, monkeypatch):
    from System import sifta_inference_defaults as defaults
    from System import swarm_primary_cortex_switcher as switcher

    monkeypatch.setattr(defaults, "_STATE", tmp_path)
    monkeypatch.setattr(defaults, "_ASSIGNMENTS", tmp_path / "swimmer_ollama_assignments.json")
    monkeypatch.setattr(switcher, "_STATE", tmp_path)
    monkeypatch.setattr(switcher, "_LEDGER", tmp_path / "primary_cortex_switches.jsonl")
    defaults.set_app_ollama_model("talk_to_alice", "sifta-gemma4-alice:latest")

    try:
        switcher.set_primary_cortex(
            "qwen3.5:2b",
            installed=["sifta-gemma4-alice:latest", "qwen3.5:2b"],
            verification_results={"vision": 0.9, "audio": 0.9},
            require_verification=True,
        )
    except ValueError as exc:
        assert "verification failed" in str(exc)
    else:
        raise AssertionError("failed verification should block promotion")

    assert defaults.resolve_ollama_model(app_context="talk_to_alice") == "sifta-gemma4-alice:latest"
    assert not (tmp_path / "primary_cortex_switches.jsonl").exists()
    assert (tmp_path / "cortex_verification.jsonl").exists()
    assert (tmp_path / "governance_ledger.jsonl").exists()


def test_set_primary_cortex_allows_passing_required_verification(tmp_path, monkeypatch):
    from System import sifta_inference_defaults as defaults
    from System import swarm_primary_cortex_switcher as switcher

    monkeypatch.setattr(defaults, "_STATE", tmp_path)
    monkeypatch.setattr(defaults, "_ASSIGNMENTS", tmp_path / "swimmer_ollama_assignments.json")
    monkeypatch.setattr(switcher, "_STATE", tmp_path)
    monkeypatch.setattr(switcher, "_LEDGER", tmp_path / "primary_cortex_switches.jsonl")

    receipt = switcher.set_primary_cortex(
        "qwen3.5:2b",
        installed=["sifta-gemma4-alice:latest", "qwen3.5:2b"],
        verification_results={"vision": 0.87, "audio": 0.91, "tool": 0.79, "owner_continuity": 0.95},
        require_verification=True,
    )

    assert receipt["selected_model"] == "qwen3.5:2b"
    assert receipt["cortex_verification"]["pass"] is True


def test_current_primary_cortex_truth_separates_native_multimodal_from_organs(tmp_path, monkeypatch):
    from System import sifta_inference_defaults as defaults
    from System import swarm_primary_cortex_switcher as switcher

    monkeypatch.setattr(defaults, "_STATE", tmp_path)
    monkeypatch.setattr(defaults, "_ASSIGNMENTS", tmp_path / "swimmer_ollama_assignments.json")
    defaults.set_app_ollama_model("talk_to_alice", "sifta-gemma4-alice")

    truth = switcher.current_primary_cortex_truth(installed=["sifta-gemma4-alice:latest"])

    assert truth["active_model"] == "sifta-gemma4-alice"
    assert truth["installed"] is True
    assert truth["multimodal_native_known"] is None
    assert "external camera/audio organs remain separate" in truth["note"]
