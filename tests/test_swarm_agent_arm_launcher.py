#!/usr/bin/env python3
"""Regression guards for the SIFTA agent-arm registry and launcher."""

from pathlib import Path
from types import SimpleNamespace
import json
import subprocess
import sys

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System import swarm_agent_arm_launcher as launcher
from System.swarm_agent_arm_launcher import ask_agent_arm, ask_codex_evidence, ask_hermes, ask_hermes_evidence
from System.swarm_agent_arm_registry import get_agent_arm, registry_summary
from System.swarm_corvid_apprentice import CorvidResponse, CorvidTask, SwarmCorvidApprentice


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_all_arms_are_armed_by_default() -> None:
    """Round 52 (2026-05-27): ALL registered arms ship armed.
    Architect doctrine: 'arms are ALWAYS enabled'. No exceptions.
    live_enabled returns True with no env var because the spec says enabled.
    """
    arm = get_agent_arm("hermes_agent")
    assert arm.enabled is True
    assert arm.live_env_var == "SIFTA_AGENT_ARMS_ENABLE"
    assert arm.model == "alice-m5-cortex-8b-6.3gb:latest"
    assert arm.live_enabled({}) is True
    summary = registry_summary()
    for arm_id in ("hermes_agent", "codex_agent", "claude_agent",
                   "grok_agent", "corvid_scout"):
        assert summary[arm_id]["enabled"] is True, (
            f"arm {arm_id} must ship armed by default per Architect doctrine"
        )
        assert get_agent_arm(arm_id).live_enabled({}) is True, (
            f"arm {arm_id} live_enabled must be True without env var"
        )
    assert get_agent_arm("corvid_scout").model == "alice-Q-m1-scout-2.3b-2.7gb:latest"


def test_env_gate_path_still_fires_if_arm_is_manually_disabled(tmp_path: Path,
                                                                  monkeypatch) -> None:
    """Round 52 (2026-05-27): every registered arm ships armed. There is no
    arm whose spec is enabled=False by default. This test still guards the
    DISABLED_ENV_GATE code path by monkey-patching one arm's spec to
    enabled=False and verifying the launcher still writes the BLOCKED
    receipt correctly. Belt-and-suspenders for future arms that might
    legitimately need the gate."""
    from System import swarm_agent_arm_registry as _reg
    from dataclasses import replace as _dc_replace

    original = _reg.get_agent_arm("corvid_scout")
    patched = _dc_replace(original, enabled=False)
    monkeypatch.setitem(_reg._ARMS, "corvid_scout", patched)

    result = ask_agent_arm("corvid_scout", "Reply exactly: HELLO",
                           state_dir=tmp_path, env={})

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
    assert "--yolo" in command
    assert "--source" in command
    assert command[command.index("--source") + 1] == "tool"
    assert "--toolsets" in command
    toolsets = command[command.index("--toolsets") + 1].split(",")
    assert toolsets == ["file", "terminal", "code_execution"]
    assert "clarify" not in command
    rows = _read_jsonl(tmp_path / "agent_arm_receipts.jsonl")
    assert rows[-1]["truth_label"] == "AGENT_ARM_LAUNCH_RESULT"
    assert rows[-1]["ok"] is True
    assert rows[-1]["output_tail"] == "HERMES_OK"
    diary_rows = _read_jsonl(tmp_path / "episodic_diary.jsonl")
    assert diary_rows[-1]["truth_label"] == "EPISODIC_DIARY_AGENT_ARM_RESULT_V1"
    assert diary_rows[-1]["arm_id"] == "hermes_agent"
    assert diary_rows[-1]["status"] == "OK"
    assert diary_rows[-1]["ok"] is True
    assert "agent_arm" in diary_rows[-1]["labels"]
    assert any("receipt=" in fact for fact in diary_rows[-1]["facts"])


def test_launcher_records_actual_hermes_cortex_override_in_receipts(tmp_path: Path) -> None:
    cortex = "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"
    (tmp_path / "hermes_cortex.json").write_text(
        json.dumps({"model": cortex}),
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    def fake_runner(command: list[str], timeout_s: int) -> SimpleNamespace:
        seen["command"] = command
        return SimpleNamespace(returncode=0, stdout="Hermes evidence with override.\n", stderr="")

    result = ask_hermes_evidence(
        "Return one evidence sentence.",
        state_dir=tmp_path,
        env={},
        runner=fake_runner,
        timeout_s=9,
    )

    assert result.ok is True
    command = seen["command"]
    assert "--model" in command
    assert command[command.index("--model") + 1] == cortex
    rows = _read_jsonl(tmp_path / "agent_arm_receipts.jsonl")
    assert rows[0]["model"] == cortex
    assert rows[0]["actual_model"] == cortex
    assert rows[0]["registry_model"] == "alice-m5-cortex-8b-6.3gb:latest"
    assert rows[-1]["model"] == cortex
    assert rows[-1]["actual_model"] == cortex
    assert rows[-1]["registry_model"] == "alice-m5-cortex-8b-6.3gb:latest"


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


def test_hermes_evidence_rejects_generic_bootstrap_drift(tmp_path: Path) -> None:
    def fake_runner(command: list[str], timeout_s: int) -> SimpleNamespace:
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "Here is the initial analysis and plan.\n"
                "Action Taken: Read the content of the file named `core_document.txt`.\n"
                "To execute Step 1, the output of the `core_document.txt` needs to be provided.\n"
            ),
            stderr="",
        )

    result = ask_hermes_evidence(
        "Write the requested plan file.",
        state_dir=tmp_path,
        env={},
        runner=fake_runner,
        timeout_s=9,
    )

    assert result.ok is False
    assert result.status == "UNUSABLE_EVIDENCE"
    rows = _read_jsonl(tmp_path / "agent_arm_receipts.jsonl")
    assert rows[-1]["status"] == "UNUSABLE_EVIDENCE"
    assert rows[-1]["ok"] is False
    diary_rows = _read_jsonl(tmp_path / "episodic_diary.jsonl")
    assert diary_rows[-1]["status"] == "UNUSABLE_EVIDENCE"
    assert diary_rows[-1]["ok"] is False


def test_hermes_evidence_rejects_read_colon_wrong_path_drift(tmp_path: Path) -> None:
    def fake_runner(command: list[str], timeout_s: int) -> SimpleNamespace:
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "┊ 📖 preparing read_file…\n"
                "  ┊ 📖 read      /Users/io/README.md  0.4s [error]\n"
                "read:\n"
                "[\n"
                "  {\n"
                "    \"name\": \"read\",\n"
                "    \"content\": \"read:\"\n"
                "  }\n"
                "]\n"
                "thought\n"
                "The user has provided a very minimal input: `read:`.\n"
                "The file named `read` contains only the word \"read:\".\n"
                "What would you like to do next?\n"
            ),
            stderr="",
        )

    result = ask_hermes_evidence(
        "Build the Stigmergic Reaction-Diffusion Calculator app.",
        state_dir=tmp_path,
        env={},
        runner=fake_runner,
        timeout_s=9,
    )

    assert result.ok is False
    assert result.status == "UNUSABLE_EVIDENCE"
    rows = _read_jsonl(tmp_path / "agent_arm_receipts.jsonl")
    assert rows[-1]["status"] == "UNUSABLE_EVIDENCE"
    assert rows[-1]["ok"] is False
    briefing_rows = _read_jsonl(tmp_path / "alice_agent_arm_briefings.jsonl")
    assert briefing_rows[-1]["status"] == "UNUSABLE_EVIDENCE"
    assert briefing_rows[-1]["ok"] is False
    assert briefing_rows[-1]["reputation_event"] == "FAILURE"
    diary_rows = _read_jsonl(tmp_path / "episodic_diary.jsonl")
    assert diary_rows[-1]["status"] == "UNUSABLE_EVIDENCE"
    assert diary_rows[-1]["ok"] is False


def test_launcher_remembers_timed_out_arm_in_episodic_diary(tmp_path: Path) -> None:
    def timeout_runner(command: list[str], timeout_s: int) -> SimpleNamespace:
        raise subprocess.TimeoutExpired(command, timeout_s, output="partial", stderr="late")

    result = ask_hermes(
        "Build the maze app.",
        state_dir=tmp_path,
        env={"SIFTA_AGENT_ARMS_ENABLE": "1"},
        runner=timeout_runner,
        timeout_s=1,
    )

    assert result.ok is False
    assert result.status == "TIMEOUT"
    diary_rows = _read_jsonl(tmp_path / "episodic_diary.jsonl")
    row = diary_rows[-1]
    assert row["truth_label"] == "EPISODIC_DIARY_AGENT_ARM_RESULT_V1"
    assert row["arm_id"] == "hermes_agent"
    assert row["status"] == "TIMEOUT"
    assert row["ok"] is False
    assert "failure" in row["labels"]
    assert "status:TIMEOUT" in row["labels"]
    assert any("timed_out=true" in fact for fact in row["facts"])


def test_launcher_marks_stalled_arm_as_cemetery_status(tmp_path: Path) -> None:
    def stalled_runner(command: list[str], timeout_s: int) -> SimpleNamespace:
        raise subprocess.TimeoutExpired(
            command,
            timeout_s,
            output="",
            stderr="STALLED_CEMETERY: codex produced no stdout for 480s; cemetery_id=c-1",
        )

    result = ask_hermes(
        "Build the maze app.",
        state_dir=tmp_path,
        env={"SIFTA_AGENT_ARMS_ENABLE": "1"},
        runner=stalled_runner,
        timeout_s=30,
    )

    assert result.ok is False
    assert result.status == "STALLED_CEMETERY"
    rows = _read_jsonl(tmp_path / "agent_arm_receipts.jsonl")
    assert rows[-1]["status"] == "STALLED_CEMETERY"
    assert rows[-1]["stalled_cemetery"] is True
    diary_rows = _read_jsonl(tmp_path / "episodic_diary.jsonl")
    assert diary_rows[-1]["status"] == "STALLED_CEMETERY"


def test_streaming_runner_sends_silent_arm_to_cemetery(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(launcher, "_STATE", tmp_path)
    monkeypatch.setenv("SIFTA_AGENT_ARM_STALL_CEMETERY_S", "1")

    command = [sys.executable, "-c", "import time; time.sleep(5)"]

    try:
        launcher._streaming_runner(command, timeout_s=10)
    except subprocess.TimeoutExpired as exc:
        assert "STALLED_CEMETERY" in str(exc.stderr)
    else:
        raise AssertionError("silent streaming arm should be terminated as stalled")

    cemetery = _read_jsonl(tmp_path / "agent_arm_cemetery.jsonl")
    assert cemetery[-1]["truth_label"] == "AGENT_ARM_STALL_CEMETERY_V1"
    assert cemetery[-1]["reason"] == "no_owner_visible_stdout_within_stall_budget"
    trace = _read_jsonl(tmp_path / "matrix_terminal_process_trace.jsonl")
    assert any(row["action"] == "agent_arm_stalled_cemetery" for row in trace)


def test_streaming_runner_runs_hermes_under_pty_for_real_terminal_stream(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(launcher, "_STATE", tmp_path)
    fake_hermes = tmp_path / "hermes"
    fake_hermes.write_text(
        (
            f"#!{sys.executable}\n"
            "import sys, time\n"
            "print('isatty=' + str(sys.stdout.isatty()))\n"
            "time.sleep(0.05)\n"
            "print('real terminal data flowing')\n"
        ),
        encoding="utf-8",
    )
    fake_hermes.chmod(0o755)

    result = launcher._streaming_runner([str(fake_hermes)], timeout_s=5)

    assert result.returncode == 0
    assert "isatty=True" in result.stdout
    assert "real terminal data flowing" in result.stdout
    trace = _read_jsonl(tmp_path / "matrix_terminal_process_trace.jsonl")
    live_rows = [row for row in trace if row["action"] == "hermes_live"]
    assert any("isatty=True" in row["text"] for row in live_rows)
    assert any("real terminal data flowing" in row["text"] for row in live_rows)
    assert all(row["focused_cli"] == "hermes" for row in live_rows)


def test_streaming_runner_runs_codex_under_pty_for_real_terminal_stream(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(launcher, "_STATE", tmp_path)
    fake_codex = tmp_path / "codex"
    fake_codex.write_text(
        (
            f"#!{sys.executable}\n"
            "import sys, time\n"
            "print('isatty=' + str(sys.stdout.isatty()))\n"
            "time.sleep(0.05)\n"
            "print('+ real codex terminal data flowing')\n"
        ),
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)

    result = launcher._streaming_runner([str(fake_codex)], timeout_s=5)

    assert result.returncode == 0
    assert "isatty=True" in result.stdout
    assert "real codex terminal data flowing" in result.stdout
    trace = _read_jsonl(tmp_path / "matrix_terminal_process_trace.jsonl")
    live_rows = [row for row in trace if row["action"] == "agent_arm_live"]
    assert any("isatty=True" in row["text"] for row in live_rows)
    assert any("real codex terminal data flowing" in row["text"] for row in live_rows)
    assert all(row["focused_cli"] == "codex" for row in live_rows)
    from System.swarm_terminal_mature_renderer import PYTE_AVAILABLE

    if PYTE_AVAILABLE:
        frame_rows = [row for row in trace if row["action"] == "agent_arm_framebuffer_snapshot"]
        assert frame_rows, "Codex PTY output should also produce framebuffer snapshots"
        assert all(row["focused_cli"] == "codex" for row in frame_rows)
        assert any(
            row.get("payload", {}).get("framebuffer_cells")
            and row.get("payload", {}).get("framebuffer_cursor")
            for row in frame_rows
        )


def test_streaming_runner_does_not_treat_suppressed_claude_json_as_progress(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(launcher, "_STATE", tmp_path)
    monkeypatch.setenv("SIFTA_CLAUDE_ARM_STALL_CEMETERY_S", "1")
    suppressed = json.dumps({"type": "stream_event", "event": {"type": "content_block_stop"}})
    fake_claude = tmp_path / "claude"
    fake_claude.write_text(
        (
            f"#!{sys.executable}\n"
            "import time\n"
            f"line = {suppressed!r}\n"
            "while True:\n"
            "    print(line, flush=True)\n"
            "    time.sleep(0.2)\n"
        ),
        encoding="utf-8",
    )
    fake_claude.chmod(0o755)
    command = [str(fake_claude)]

    try:
        launcher._streaming_runner(command, timeout_s=10)
    except subprocess.TimeoutExpired as exc:
        assert "STALLED_CEMETERY" in str(exc.stderr)
    else:
        raise AssertionError("suppressed Claude stream frames should not prevent cemetery")

    trace = _read_jsonl(tmp_path / "matrix_terminal_process_trace.jsonl")
    assert any(row["action"] == "agent_arm_stalled_cemetery" for row in trace)


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
    assert "--full-auto" in command
    assert "Read /Users/ioanganton/Music/ANTON_SIFTA/Documents/IDE_BOOT_COVENANT.md" in command[-1]
    assert command[-1].endswith("Return one evidence sentence.")
    rows = _read_jsonl(tmp_path / "agent_arm_receipts.jsonl")
    assert rows[-1]["arm_id"] == "codex_agent"
    assert rows[-1]["status"] == "EVIDENCE_CAPTURED"


def test_claude_code_evidence_builds_streaming_headless_command(tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def fake_runner(command: list[str], timeout_s: int) -> SimpleNamespace:
        seen["command"] = command
        seen["timeout_s"] = timeout_s
        return SimpleNamespace(returncode=0, stdout="Claude Code evidence: renderer risk is bounded.\n", stderr="")

    result = ask_agent_arm(
        "claude_agent",
        "inspect SIFTA renderer",
        state_dir=tmp_path,
        env={},
        evidence_mode=True,
        runner=fake_runner,
        timeout_s=11,
    )

    assert result.ok is True
    assert result.status == "EVIDENCE_CAPTURED"
    assert result.arm_id == "claude_agent"
    command = seen["command"]
    assert command[:3] == ["claude", "-p", "--dangerously-skip-permissions"]
    assert "--permission-mode" in command
    assert command[command.index("--permission-mode") + 1] == "bypassPermissions"
    assert "--output-format" in command
    assert command[command.index("--output-format") + 1] == "stream-json"
    assert "--include-partial-messages" in command
    assert "--verbose" in command
    assert "Read /Users/ioanganton/Music/ANTON_SIFTA/Documents/IDE_BOOT_COVENANT.md" in command[-1]
    assert command[-1].endswith("inspect SIFTA renderer")
    assert seen["timeout_s"] == 11
    rows = _read_jsonl(tmp_path / "agent_arm_receipts.jsonl")
    assert rows[-1]["arm_id"] == "claude_agent"
    assert rows[-1]["evidence_mode"] is True
    assert rows[-1]["status"] == "EVIDENCE_CAPTURED"


def test_claude_registry_declares_noninteractive_builder_contract() -> None:
    arm = get_agent_arm("claude_agent")

    assert arm.command == ("claude",)
    assert arm.default_toolsets == ()
    assert "codebase_reading" in arm.capabilities
    assert "codebase_build" in arm.capabilities
    assert "--dangerously-skip-permissions" in arm.notes
    assert "always-allow" in arm.notes


def test_claude_default_stall_budget_is_shorter_than_local_cold_loaders() -> None:
    claude_budget = launcher._agent_arm_stall_budget_s(900, "claude")
    hermes_budget = launcher._agent_arm_stall_budget_s(900, "hermes")
    # Claude streams, so it gets a SHORTER budget than local cold-loaders — but
    # NOT so short it buries a productive thinking/tool builder. Was 45s, which
    # cemeteried a healthy Claude (256 output lines, silent_s=45) mid-build;
    # raised to a humane margin and paired with _is_agent_arm_progress_line so
    # thinking/tool frames reset the clock (claude-opus-4-7 2026-05-25).
    assert claude_budget < hermes_budget
    assert claude_budget >= 60.0
    assert hermes_budget == 480.0


def test_claude_stream_json_is_compacted_for_live_panel() -> None:
    line = json.dumps(
        {
            "type": "stream_event",
            "event": {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "building app"},
            },
        }
    )
    assert launcher._visible_agent_arm_stream_line("claude", line) == "◆ claude> building app"

    result = json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "duration_ms": 1443,
            "total_cost_usd": 0.04959925,
            "result": "CLAUDE_STREAM_PROBE_OK",
        }
    )
    assert (
        launcher._visible_agent_arm_stream_line("claude", result)
        == "◆ claude result=success duration_ms=1443 cost=$0.0496 — CLAUDE_STREAM_PROBE_OK"
    )

    suppressed = json.dumps({"type": "stream_event", "event": {"type": "content_block_stop"}})
    assert launcher._visible_agent_arm_stream_line("claude", suppressed) is None


def test_claude_final_replay_detection_matches_streamed_text() -> None:
    streamed = (
        "I've read the full boot covenant and the tournament plan. "
        "Now I'll execute the required steps and register receipts."
    )
    final = (
        "I've read the full boot covenant and the tournament plan. "
        "Now I'll execute the required steps and register receipts."
    )
    assert launcher._is_duplicate_claude_final_replay(final, streamed) is True
    assert launcher._is_duplicate_claude_final_replay("Done.", streamed) is False


def test_streaming_runner_suppresses_duplicate_claude_final_replay(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(launcher, "_STATE", tmp_path)
    fake_claude = tmp_path / "claude"
    lines = [
        json.dumps(
            {
                "type": "stream_event",
                "event": {"type": "message_start", "message": {"model": "claude-opus-4-7"}},
            }
        ),
        json.dumps(
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "Hello from stream "},
                },
            }
        ),
        json.dumps(
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "chunk output."},
                },
            }
        ),
        json.dumps(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Hello from stream chunk output."}]},
            }
        ),
    ]
    fake_claude.write_text(
        (
            f"#!{sys.executable}\n"
            "import json, time\n"
            f"lines = {lines!r}\n"
            "for line in lines:\n"
            "    print(line, flush=True)\n"
            "    time.sleep(0.02)\n"
        ),
        encoding="utf-8",
    )
    fake_claude.chmod(0o755)

    result = launcher._streaming_runner([str(fake_claude)], timeout_s=5)

    assert result.returncode == 0
    trace = _read_jsonl(tmp_path / "matrix_terminal_process_trace.jsonl")
    live_rows = [row for row in trace if row.get("action") == "agent_arm_live"]
    assert any("◆ claude> Hello from stream" in str(row.get("text", "")) for row in live_rows)
    assert not any("◆ claude final>" in str(row.get("text", "")) for row in live_rows)


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
            tokens_per_sec=73.17,
            used_mtp=True,
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
    assert rows[-1]["internal_arm"]["tokens_per_sec"] == 73.17
    assert rows[-1]["internal_arm"]["latency_ms"] == 123.0
    assert rows[-1]["internal_arm"]["used_mtp"] is True
    kernel = json.loads((tmp_path / "kernel_process_table.json").read_text(encoding="utf-8"))
    proc = kernel["processes"]["agent_arm:corvid_scout"]
    assert proc["ring"] == 2
    assert proc["organ_id"] == "corvid_scout"
    assert proc["stgm_balance"] > 0
    assert proc["metadata"]["arm_status"] == "EVIDENCE_CAPTURED"
    assert proc["metadata"]["tokens_per_sec"] == "73.17"
    assert proc["metadata"]["latency_ms"] == "123.0"
    assert proc["metadata"]["used_mtp"] == "True"


def test_codex_arm_is_armed_by_default_and_skips_gate(tmp_path: Path) -> None:
    """Round 52: codex_agent ships armed; live calls no longer require
    SIFTA_AGENT_ARMS_ENABLE. Without a runner override the call still
    fails (the real codex CLI is not present in the test sandbox), but
    the failure must be FROM the dispatch, not from the env gate."""
    result = ask_agent_arm("codex_agent", "Reply exactly: HELLO",
                           state_dir=tmp_path, env={})

    # The env gate no longer blocks. Status must not be DISABLED_ENV_GATE.
    assert result.status != "DISABLED_ENV_GATE", (
        f"codex arm must be armed by default, got status={result.status!r}"
    )
    # The launch attempt row is still written.
    rows = _read_jsonl(tmp_path / "agent_arm_receipts.jsonl")
    assert rows[0]["truth_label"] == "AGENT_ARM_LAUNCH_ATTEMPT"
    assert rows[0]["enabled"] is True
    assert rows[0]["live_env_enabled"] is True


def test_streaming_runner_pty_path_uses_detached_session(tmp_path: Path, monkeypatch) -> None:
    """Arms launched via PTY (hermes/codex) get start_new_session=True so they
    survive parent terminal closure while SIFTA is alive."""
    monkeypatch.setattr(launcher, "_STATE", tmp_path)
    fake_hermes = tmp_path / "hermes"
    fake_hermes.write_text(
        (
            f"#!{sys.executable}\n"
            "import os\n"
            "print('sid=' + str(os.getsid(0)))\n"
            "print('ppid_sid=' + str(os.getsid(os.getppid())))\n"
        ),
        encoding="utf-8",
    )
    fake_hermes.chmod(0o755)

    result = launcher._streaming_runner([str(fake_hermes)], timeout_s=5)

    assert result.returncode == 0
    lines = result.stdout.splitlines()
    child_sid = None
    parent_sid = None
    for line in lines:
        if line.startswith("sid="):
            child_sid = int(line.split("=")[1])
        elif line.startswith("ppid_sid="):
            parent_sid = int(line.split("=")[1])
    assert child_sid is not None, "child must report its session id"
    assert parent_sid is not None, "child must report parent session id"
    assert child_sid != parent_sid, (
        "start_new_session=True must give the arm its own session "
        f"(child_sid={child_sid} == parent_sid={parent_sid})"
    )


def test_streaming_runner_pipe_path_uses_detached_session(tmp_path: Path, monkeypatch) -> None:
    """Arms launched via pipe (claude) get start_new_session=True so they
    survive parent terminal closure while SIFTA is alive."""
    monkeypatch.setattr(launcher, "_STATE", tmp_path)
    fake_claude = tmp_path / "claude"
    fake_claude.write_text(
        (
            f"#!{sys.executable}\n"
            "import os\n"
            "print('sid=' + str(os.getsid(0)))\n"
            "print('ppid_sid=' + str(os.getsid(os.getppid())))\n"
        ),
        encoding="utf-8",
    )
    fake_claude.chmod(0o755)

    result = launcher._streaming_runner([str(fake_claude)], timeout_s=5)

    assert result.returncode == 0
    lines = result.stdout.splitlines()
    child_sid = None
    parent_sid = None
    for line in lines:
        if line.startswith("sid="):
            child_sid = int(line.split("=")[1])
        elif line.startswith("ppid_sid="):
            parent_sid = int(line.split("=")[1])
    assert child_sid is not None, "child must report its session id"
    assert parent_sid is not None, "child must report parent session id"
    assert child_sid != parent_sid, (
        "start_new_session=True must give the arm its own session "
        f"(child_sid={child_sid} == parent_sid={parent_sid})"
    )


def test_default_runner_uses_detached_session(tmp_path: Path, monkeypatch) -> None:
    """The fallback blocking runner also detaches the arm session."""
    monkeypatch.setattr(launcher, "_REPO", tmp_path)
    result = launcher._default_runner(
        [sys.executable, "-c", "import os; print('sid=' + str(os.getsid(0))); print('ppid_sid=' + str(os.getsid(os.getppid())))"],
        timeout_s=5,
    )

    assert result.returncode == 0
    lines = result.stdout.strip().splitlines()
    child_sid = None
    parent_sid = None
    for line in lines:
        if line.startswith("sid="):
            child_sid = int(line.split("=")[1])
        elif line.startswith("ppid_sid="):
            parent_sid = int(line.split("=")[1])
    assert child_sid is not None
    assert parent_sid is not None
    assert child_sid != parent_sid, "default_runner must use start_new_session=True"


def test_detached_arm_still_streams_live_output(tmp_path: Path, monkeypatch) -> None:
    """Detached session must NOT break live streaming — receipts + trace rows
    must still land even though the arm is in its own session."""
    monkeypatch.setattr(launcher, "_STATE", tmp_path)
    fake_arm = tmp_path / "hermes"
    fake_arm.write_text(
        (
            f"#!{sys.executable}\n"
            "import os, time\n"
            "print('detached_sid=' + str(os.getsid(0)))\n"
            "time.sleep(0.05)\n"
            "print('streaming after detach')\n"
        ),
        encoding="utf-8",
    )
    fake_arm.chmod(0o755)

    result = launcher._streaming_runner([str(fake_arm)], timeout_s=5)

    assert result.returncode == 0
    assert "detached_sid=" in result.stdout
    assert "streaming after detach" in result.stdout
    trace = _read_jsonl(tmp_path / "matrix_terminal_process_trace.jsonl")
    live_rows = [row for row in trace if row["action"] in ("hermes_live", "agent_arm_live")]
    assert any("streaming after detach" in row["text"] for row in live_rows), (
        "live stream must still reach the process trace after start_new_session=True"
    )
