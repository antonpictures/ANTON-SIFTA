#!/usr/bin/env python3
"""Regression guards for the SIFTA agent-arm registry and launcher."""

from pathlib import Path
from types import SimpleNamespace
import json
import sys

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_agent_arm_launcher import ask_agent_arm, ask_codex_evidence, ask_hermes, ask_hermes_evidence
from System.swarm_agent_arm_registry import get_agent_arm, registry_summary
from System.swarm_corvid_apprentice import CorvidResponse, CorvidTask, SwarmCorvidApprentice


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_hermes_registry_is_disabled_by_default() -> None:
    arm = get_agent_arm("hermes_agent")
    assert arm.enabled is False
    assert arm.live_env_var == "SIFTA_AGENT_ARMS_ENABLE"
    assert arm.model == "alice-m5-cortex-8b-6.3gb:latest"
    assert registry_summary()["hermes_agent"]["enabled"] is False
    assert registry_summary()["codex_agent"]["enabled"] is False
    assert registry_summary()["corvid_scout"]["enabled"] is False
    assert get_agent_arm("corvid_scout").model == "alice-m1-scout-2.3b-2.7gb:latest"


def test_launcher_blocks_live_call_without_env_gate(tmp_path: Path) -> None:
    result = ask_hermes("Reply exactly: HELLO", state_dir=tmp_path, env={})

    assert result.ok is False
    assert result.status == "DISABLED_ENV_GATE"
    rows = _read_jsonl(tmp_path / "agent_arm_receipts.jsonl")
    assert rows[0]["truth_label"] == "AGENT_ARM_LAUNCH_ATTEMPT"
    assert rows[1]["truth_label"] == "AGENT_ARM_LAUNCH_BLOCKED"
    assert rows[1]["status"] == "DISABLED_ENV_GATE"


def test_launcher_runs_fake_hermes_with_receipts(tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def fake_runner(command: list[str], timeout_s: int) -> SimpleNamespace:
        seen["command"] = command
        seen["timeout_s"] = timeout_s
        return SimpleNamespace(returncode=0, stdout="HERMES_OK\n", stderr="")

    result = ask_hermes(
        "Reply exactly: HERMES_OK",
        state_dir=tmp_path,
        env={"SIFTA_AGENT_ARMS_ENABLE": "1"},
        runner=fake_runner,
        timeout_s=7,
        require_exact="HERMES_OK",
    )

    assert result.ok is True
    assert result.status == "OK"
    assert seen["timeout_s"] == 7
    command = seen["command"]
    assert command[:3] == ["hermes", "chat", "-Q"]
    assert "--toolsets" in command
    assert "clarify" in command
    rows = _read_jsonl(tmp_path / "agent_arm_receipts.jsonl")
    assert rows[-1]["truth_label"] == "AGENT_ARM_LAUNCH_RESULT"
    assert rows[-1]["ok"] is True
    assert rows[-1]["output_tail"] == "HERMES_OK"


def test_launcher_rejects_wrapper_text_when_exact_required(tmp_path: Path) -> None:
    def fake_runner(command: list[str], timeout_s: int) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout="Sure: HERMES_OK\n", stderr="")

    result = ask_hermes(
        "Reply exactly: HERMES_OK",
        state_dir=tmp_path,
        env={"SIFTA_AGENT_ARMS_ENABLE": "1"},
        runner=fake_runner,
        require_exact="HERMES_OK",
    )

    assert result.ok is False
    assert result.status == "EXACTNESS_FAILED"
    rows = _read_jsonl(tmp_path / "agent_arm_receipts.jsonl")
    assert rows[-1]["status"] == "EXACTNESS_FAILED"


def test_evidence_mode_accepts_wrapper_text_without_env_gate(tmp_path: Path) -> None:
    def fake_runner(command: list[str], timeout_s: int) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout="Hermes says: useful evidence\nsession_id: test\n", stderr="")

    result = ask_hermes_evidence(
        "Research this and return evidence.",
        state_dir=tmp_path,
        env={},
        runner=fake_runner,
    )

    assert result.ok is True
    assert result.status == "EVIDENCE_CAPTURED"
    assert result.mode == "evidence"
    rows = _read_jsonl(tmp_path / "agent_arm_receipts.jsonl")
    assert rows[-1]["evidence_mode"] is True
    assert rows[-1]["status"] == "EVIDENCE_CAPTURED"


def test_codex_evidence_builds_read_only_ephemeral_command(tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def fake_runner(command: list[str], timeout_s: int) -> SimpleNamespace:
        seen["command"] = command
        seen["timeout_s"] = timeout_s
        return SimpleNamespace(returncode=0, stdout='{"msg":"CODEX_EVIDENCE"}\n', stderr="")

    result = ask_codex_evidence(
        "Return one evidence sentence.",
        state_dir=tmp_path,
        env={},
        runner=fake_runner,
        timeout_s=9,
    )

    assert result.ok is True
    assert result.status == "EVIDENCE_CAPTURED"
    assert result.arm_id == "codex_agent"
    command = seen["command"]
    assert command[:2] == ["codex", "exec"]
    assert "--oss" in command
    assert "--local-provider" in command
    assert "ollama" in command
    assert "--sandbox" in command
    assert "read-only" in command
    assert "--ephemeral" in command
    assert command[-1] == "Return one evidence sentence."
    rows = _read_jsonl(tmp_path / "agent_arm_receipts.jsonl")
    assert rows[-1]["arm_id"] == "codex_agent"
    assert rows[-1]["status"] == "EVIDENCE_CAPTURED"


def test_corvid_scout_evidence_runs_internal_organ_with_receipts(tmp_path: Path, monkeypatch) -> None:
    def fake_evidence(self, text: str) -> CorvidResponse:
        assert "summarize router risk" in text
        return CorvidResponse(
            task=CorvidTask.EVIDENCE,
            response="Corvid evidence: router risk is low.",
            latency_s=0.123,
            model=self.model,
            input_len=len(text),
            response_len=36,
            success=True,
        )

    monkeypatch.setattr(SwarmCorvidApprentice, "evidence", fake_evidence)
    result = ask_agent_arm(
        "corvid_scout",
        "summarize router risk",
        state_dir=tmp_path,
        env={},
        evidence_mode=True,
    )

    assert result.ok is True
    assert result.status == "EVIDENCE_CAPTURED"
    assert result.arm_id == "corvid_scout"
    assert "Corvid evidence" in result.output
    rows = _read_jsonl(tmp_path / "agent_arm_receipts.jsonl")
    assert rows[-1]["arm_id"] == "corvid_scout"
    assert rows[-1]["internal_arm"]["internal_runner"] == "SwarmCorvidApprentice.evidence"
    assert rows[-1]["internal_arm"]["corvid_ledger"] == "corvid_apprentice_trace.jsonl"


def test_exact_codex_call_is_still_env_gated(tmp_path: Path) -> None:
    result = ask_agent_arm("codex_agent", "Reply exactly: HELLO", state_dir=tmp_path, env={})

    assert result.ok is False
    assert result.status == "DISABLED_ENV_GATE"
