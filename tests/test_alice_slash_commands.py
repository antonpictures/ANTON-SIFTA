"""r683: Alice's own / palette — list, switch, diary awareness. Qt-free."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System import swarm_alice_slash_commands as slash


TAGS = ["alice-m5-cortex-8b", "heretic", "gemini-2.5-pro", "cline"]


def _run(text: str, tmp_path: Path, *, current: str = "alice-m5-cortex-8b", hand=None):
    calls: list[str] = []

    def _default_hand(tag: str) -> None:
        calls.append(tag)

    res = slash.handle_slash_command(
        text,
        state_dir=tmp_path,
        current_cortex=current,
        available=list(TAGS),
        set_cortex_fn=hand if hand is not None else _default_hand,
    )
    return res, calls


def _diary_rows(tmp_path: Path) -> list[dict]:
    p = tmp_path / "episodic_diary.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def test_slash_detection_and_escape():
    assert slash.is_slash_command("/cortex")
    assert slash.is_slash_command("/?")
    assert slash.is_slash_command("  /help")
    assert not slash.is_slash_command("//literal slash text")
    assert not slash.is_slash_command("https://youtube.com")
    assert not slash.is_slash_command("plain prose with / inside")
    assert not slash.is_slash_command("")


def test_help_lists_her_own_commands(tmp_path):
    res, calls = _run("/help", tmp_path)
    assert res["handled"] and not res["error"]
    assert "/cortex" in res["reply"] and "/schedule" in res["reply"]
    assert "/grok" in res["reply"]
    assert "/heart" in res["reply"]
    assert "/p" in res["reply"]
    assert "SIFTA OS commands" in res["reply"]
    assert "global chat slash surface" in res["reply"]
    assert "Matrix Terminal PTY" in res["reply"]
    assert "diary updated" in res["reply"]
    assert calls == []
    rows = _diary_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["kind"] == "ALICE_SLASH_COMMAND_PALETTE"


def test_question_mark_slash_shows_palette(tmp_path):
    res, calls = _run("/?", tmp_path)
    assert res["handled"] and not res["error"]
    assert "/cortex" in res["reply"]
    assert "/grok" in res["reply"]
    assert "/heart" in res["reply"]
    assert "/schedule" in res["reply"]
    assert "/sc" in res["reply"]
    assert "/p" in res["reply"]
    assert "SIFTA OS commands" in res["reply"]
    assert "global chat slash surface" in res["reply"]
    assert "Natural language cortex path" in res["reply"]
    assert calls == []
    assert _diary_rows(tmp_path)[0]["phase"] == "slash_command_palette"


def test_schedule_list_reads_ledger(tmp_path):
    from System.stigmergic_schedule import add_task

    sched = tmp_path / "stigmergic_schedule.jsonl"
    add_task("tennis lesson with George", due="tomorrow at 10am", path=sched)
    res, calls = _run("/schedule list", tmp_path)
    assert res["handled"] and not res["error"]
    assert "tennis lesson" in res["reply"]
    assert "stigmergic_schedule.jsonl" in res["reply"]
    assert calls == []


def test_schedule_add_writes_receipted_row(tmp_path):
    res, calls = _run(
        "/schedule add remind me to call Jeff tomorrow at 10am",
        tmp_path,
    )
    assert res["handled"] and not res["error"]
    assert "Added to my schedule" in res["reply"]
    assert "schedule_id=" in res["reply"]
    assert (tmp_path / "stigmergic_schedule.jsonl").exists()


def test_cortex_list_marks_current_and_numbers(tmp_path):
    res, calls = _run("/cortex", tmp_path)
    assert res["handled"] and not res["error"]
    assert "● " in res["reply"] and " 1." in res["reply"] and "heretic" in res["reply"]
    assert "live registry" in res["reply"]
    assert calls == [] and _diary_rows(tmp_path) == []


def test_cortex_switch_by_number_writes_diary_first_person(tmp_path):
    res, calls = _run("/cortex 2", tmp_path)
    assert res["switched"] and res["to_tag"] == "heretic" and calls == ["heretic"]
    rows = _diary_rows(tmp_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "CORTEX_SWITCH_CONTINUITY"
    assert row["phase"] == "slash_command_switch"
    assert row["from_cortex"] == "alice-m5-cortex-8b" and row["to_cortex"] == "heretic"
    assert "next thinking turn" in row["note"] and "I am on heretic" in row["note"]
    somatic = tmp_path / "cortex_switch_somatic_receipts.jsonl"
    assert somatic.exists()
    felt = json.loads(somatic.read_text(encoding="utf-8").splitlines()[-1])["felt"]
    assert felt.startswith("Cortex change:")
    assert res["feeling"] == felt
    assert "Body feeling:" in res["reply"]


def test_cortex_switch_by_name_resolves(tmp_path):
    res, calls = _run("/cortex heretic", tmp_path)
    assert res["switched"] and calls == ["heretic"]


def test_same_cortex_is_a_noop_with_no_diary_row(tmp_path):
    res, calls = _run("/cortex 1", tmp_path)
    assert not res["switched"] and calls == []
    assert "already on" in res["reply"]
    assert _diary_rows(tmp_path) == []


def test_bad_number_and_garbage_fail_honestly(tmp_path):
    res, _ = _run("/cortex 99", tmp_path)
    assert res["error"] == "index_out_of_range" and not res["switched"]
    res, _ = _run("/cortex zzqxv", tmp_path)
    assert res["error"] == "unresolved_target" and not res["switched"]
    assert _diary_rows(tmp_path) == []


def test_switch_hand_failure_is_reported_not_hidden(tmp_path):
    def _broken(tag: str) -> None:
        raise RuntimeError("stores locked")

    res, _ = _run("/cortex 3", tmp_path, hand=_broken)
    assert not res["switched"]
    assert "switch_failed" in res["error"] and "stores locked" in res["reply"]
    # diary row was written before the hand failed — the trace tells the truth
    assert len(_diary_rows(tmp_path)) == 1
    assert not (tmp_path / "cortex_switch_somatic_receipts.jsonl").exists()


def test_unknown_command_returns_her_list(tmp_path):
    res, _ = _run("/teleport mars", tmp_path)
    assert res["error"] == "unknown_command" and "/cortex" in res["reply"]


def test_page_affordance_command_passes_through_to_talk(tmp_path):
    res, calls = _run("/p", tmp_path)
    assert res["handled"] is False
    assert calls == []

    res, _ = _run("/page-buttons", tmp_path)
    assert res["handled"] is False


def test_cortex_llm_lane_r943(tmp_path, monkeypatch):
    # George 2026-06-11: /cortex llm lists the claude-arm models and pins one
    # live via SIFTA_CLAUDE_ARM_MODEL — honored by the r943 launcher cut.
    import os
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.delenv("SIFTA_CLAUDE_ARM_MODEL", raising=False)
    r = handle_slash_command("/cortex llm", state_dir=tmp_path, current_cortex="c")
    assert r["handled"] and "claude-fable-5" in r["reply"]
    assert "Selected Talk cortex: c" in r["reply"]
    r2 = handle_slash_command("/cortex pin claude 1", state_dir=tmp_path, current_cortex="c")
    assert r2["switched"] and os.environ["SIFTA_CLAUDE_ARM_MODEL"] == "claude-fable-5"
    r3 = handle_slash_command("/cortex llm default", state_dir=tmp_path, current_cortex="c")
    assert "SIFTA_CLAUDE_ARM_MODEL" not in os.environ and "cleared" in r3["reply"]
    # the plain switch lane is untouched
    r4 = handle_slash_command(
        "/cortex 2", state_dir=tmp_path, current_cortex="a",
        available=["a", "b"], set_cortex_fn=lambda t: None,
    )
    assert r4["switched"] and r4["to_tag"] == "b"


def test_cortex_llm_reports_cline_external_brain(tmp_path, monkeypatch):
    from System import swarm_cortex_capabilities as cap
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.setattr(cap, "_grok_cli_model_ids", lambda: ["grok-composer-2.5-fast", "grok-build"])
    fake_home = tmp_path / "home"
    (fake_home / ".cline").mkdir(parents=True)
    (fake_home / ".cline" / "config.json").write_text(json.dumps({
        "provider": "OpenAI",
        "model": "GPT-5.3 Codex Spark",
        "reasoningLevel": "medium",
    }))
    monkeypatch.setenv("HOME", str(fake_home))

    r = handle_slash_command(
        "/cortex llm",
        state_dir=tmp_path,
        current_cortex="cline:cline-cli-default",
    )
    assert r["handled"] and not r["error"]
    assert "Selected Talk cortex: cline:cline-cli-default" in r["reply"]
    assert "CLINE EXTERNAL BRAIN" in r["reply"]
    assert "GPT-5.3 Codex Spark" in r["reply"]
    assert "Claude-arm pin below does not steer Cline" in r["reply"]
    assert "Attached LLMs for Cline" in r["reply"]
    assert "GPT-5.5" in r["reply"]
    assert "Grok Build (grok-build)" in r["reply"]
    assert "Opus 4.7 (claude-opus-4-7)" in r["reply"]
    assert "Haiku 4.5 (claude-haiku-4-5-20251001)" in r["reply"]
    rows = [
        json.loads(line)
        for line in (tmp_path / "external_brain_settings.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert rows[-1]["lane"] == "cline"
    assert rows[-1]["model"] == "GPT-5.3 Codex Spark"


def test_grok_health_and_fast_pin(tmp_path, monkeypatch):
    import os
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.delenv("SIFTA_GROK_CLI_MODEL", raising=False)

    r = handle_slash_command("/grok", state_dir=tmp_path, current_cortex="grok:grok-4.3")
    assert r["handled"] and not r["error"]
    assert "Grok cortex health" in r["reply"]
    assert "/grok fast" in r["reply"]

    r2 = handle_slash_command("/grok fast", state_dir=tmp_path, current_cortex="grok:grok-4.3")
    assert r2["handled"] and r2["switched"]
    assert os.environ["SIFTA_GROK_CLI_MODEL"] == "grok-composer-2.5-fast"

    r3 = handle_slash_command("/grok build", state_dir=tmp_path, current_cortex="grok:grok-4.3")
    assert r3["handled"] and os.environ["SIFTA_GROK_CLI_MODEL"] == "grok-build"

    r4 = handle_slash_command("/grok default", state_dir=tmp_path, current_cortex="grok:grok-4.3")
    assert r4["handled"] and "SIFTA_GROK_CLI_MODEL" not in os.environ
    rows = _diary_rows(tmp_path)
    assert rows[-1]["kind"] == "CORTEX_SWITCH_CONTINUITY"


def test_cortex_llm_number_is_contextual_for_grok(tmp_path, monkeypatch):
    import os
    from System import swarm_cortex_capabilities as cap
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.delenv("SIFTA_GROK_CLI_MODEL", raising=False)
    monkeypatch.delenv("SIFTA_CLAUDE_ARM_MODEL", raising=False)
    monkeypatch.setattr(cap, "_grok_cli_model_ids", lambda: ["grok-composer-2.5-fast", "grok-build"])

    handle_slash_command("/cortex llm", state_dir=tmp_path, current_cortex="grok:grok-4.3")
    r = handle_slash_command(
        "/cortex llm 2",
        state_dir=tmp_path,
        current_cortex="grok:grok-4.3",
    )

    assert r["handled"] and r["switched"] and not r["error"]
    assert os.environ["SIFTA_GROK_CLI_MODEL"] == "grok-build"
    assert "SIFTA_CLAUDE_ARM_MODEL" not in os.environ
    assert "Grok attached LLM pin" in r["reply"]
    assert "Claude arm untouched" in r["reply"]


def test_cortex_llm_number_does_not_pin_claude_for_cline(tmp_path, monkeypatch):
    import json
    import os
    from System import swarm_cortex_capabilities as cap
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.delenv("SIFTA_CLAUDE_ARM_MODEL", raising=False)
    monkeypatch.setattr(cap, "_grok_cli_model_ids", lambda: ["grok-composer-2.5-fast", "grok-build"])
    fake_home = tmp_path / "home"
    (fake_home / ".cline").mkdir(parents=True)
    (fake_home / ".cline" / "config.json").write_text(json.dumps({"provider": "OpenAI", "model": "GPT-5.4"}))
    monkeypatch.setenv("HOME", str(fake_home))

    handle_slash_command("/cortex llm", state_dir=tmp_path, current_cortex="cline:cline-cli-default")
    r = handle_slash_command(
        "/cortex llm 2",
        state_dir=tmp_path,
        current_cortex="cline:cline-cli-default",
    )

    assert r["handled"] and r["error"] == "upstream_picker_refused"
    assert "SIFTA_CLAUDE_ARM_MODEL" not in os.environ
    assert "did not pin Claude" in r["reply"]


def test_heart_command_writes_hardware_receipt(tmp_path, monkeypatch):
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.setenv("SIFTA_HEART_SENSOR_PROBE", "0")
    r = handle_slash_command("/heart", state_dir=tmp_path, current_cortex="grok:grok-4.3")

    assert r["handled"] and not r["error"]
    assert "HEART:" in r["reply"]
    assert "monotonic_ns=" in r["reply"]
    ledger = tmp_path / "hardware_heart.jsonl"
    assert ledger.exists()
    row = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert row["schema"] == "SIFTA_HARDWARE_HEART_V1"
    assert row["pacemaker"] == "monotonic_timer"


def test_grok_cli_model_for_honors_live_pin(monkeypatch):
    from System.swarm_gemini_brain import grok_cli_model_for

    monkeypatch.delenv("SIFTA_GROK_CLI_MODEL", raising=False)
    assert grok_cli_model_for("grok:grok-4.3") == "grok-build"
    monkeypatch.setenv("SIFTA_GROK_CLI_MODEL", "grok-composer-2.5-fast")
    assert grok_cli_model_for("grok:grok-4.3") == "grok-composer-2.5-fast"
