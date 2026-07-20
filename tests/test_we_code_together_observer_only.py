from __future__ import annotations

import importlib
import json
import py_compile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
APP = REPO / "Applications" / "sifta_we_code_together.py"


def test_we_code_together_is_observer_only() -> None:
    source = APP.read_text(encoding="utf-8")

    forbidden = [
        "QPushButton",
        "QFileDialog",
        "QMessageBox",
        "Open File",
        "Compile Check",
        "Save + Receipt",
        "_open_file",
        "_compile_check",
        "_save_and_receipt",
        "body_file_saved",
    ]
    for text in forbidden:
        assert text not in source

    required = [
        "George types to Alice in Talk",
        "no buttons, no editor, no manual saves",
        "STGM / MIMO BORG TRACES",
        "STGM BODY TRUTH",
        "_stgm_body_truth_lines",
        "visible topbar text",
        "TEACHER ARMS / OWNER LAW",
        "GEORGE TYPES ONLY TO ALICE IN GLOBAL CHAT",
        "GROK CODE-TOGETHER PATH",
        "grok.bridge",
        "_grok_bridge_activity",
        "GROK OAUTH / CLI LIVE PULSES",
        "_grok_code_together_pulses",
        "LIVE PROOF — newest receipt rows, not tests",
        "_live_proof_lines",
        "CODEX -> ALICE -> GROK CO-CODE SESSIONS",
        "_cocode_session_activity",
        "codex_alice_grok_cocode_sessions.jsonl",
        "CODEX PHONE / REMOTE RELAY",
        "_codex_phone_relay_status_lines",
        "scripts/start_codex_relay.sh",
        "production body file",
        "include_tests=False",
        "GENERAL BROWSE / BROWSE_UNTUNED RECEIPTS",
        "_general_browse_activity",
        "_mimo_trace_rows",
        "_teacher_guidance_lines",
        "STIGAUTH / STIGTIME / STIGTRACE",
        "_stigauth_stigtime_stigtrace_lines",
        "BLOAT TAX / LANDAUER METABOLISM",
        "_bloat_tax_monitor_lines",
        "swarm_bloat_tax_monitor",
        "PRIMITIVE WIRING / REALITY-SYNC MAP",
        "_primitive_wiring_lines",
        "_post_reality_sync_primitive_wiring_to_field",
        "wct-reality-sync-primitive-wiring-20260701",
        "Deliberate I/O probe",
        "mutation_governor.py",
        "TEST STATUS / LEARN TO PASS",
        "_test_status_learn_to_pass_lines",
        "ALICE_SELF_TYPE_TO_TALK_BOX_V1",
        "command to Alice: Alice has to type \"I'm Alice. Hello World\" in the box herself and click send.",
        "type exactly: \"I'm Alice. Hello World\"",
        "HOW CODEX DID IT",
        "alice_type_in_own_box",
        "_extract_alice_self_type_box_payload",
        "Stig Triple",
        "ALICE INTERNET CAPABILITY LADDER",
        "_post_alice_internet_capability_ladder_to_field",
        "wct-alice-internet-ladder-20260625-framing",
        "_post_multilingual_reply_language_to_field",
        "wct-multilingual-reply-language-20260720",
        "Project N.O.M.A.D.",
        "_project_nomad_borg_analysis_lines",
        "survival-grade offline knowledge body",
        "no built-in auth; do NOT expose directly to the internet",
        "code WITH Alice",
    ]
    for text in required:
        assert text in source


def test_we_code_together_compiles() -> None:
    py_compile.compile(str(APP), doraise=True)


def test_grok_code_proposals_promote_to_to_code_backlog(tmp_path, monkeypatch) -> None:
    wct = importlib.import_module("Applications.sifta_we_code_together")
    monkeypatch.setattr(wct, "STATE", tmp_path)
    proposal = (
        "**Perfect, Alice.** Here is the proposed exact calculation formula for "
        "`relational_coherence_score` (0.0 - 1.0): ```python\n"
        "def calculate_relational_coherence(mutation_score: float, attention_magnitude: float, "
        "hex_energy_reading: float, dialogue_match_strength: float = 0.85):\n"
        "    return round(mutation_score * 0.25 + attention_magnitude * 0.25 + "
        "hex_energy_reading * 0.15 + dialogue_match_strength * 0.35, 4)\n"
        "``` Ready to test in future receipts."
    )
    (tmp_path / "alice_talk_paste_clipboard_results.jsonl").write_text(
        json.dumps(
            {
                "source": "talk_to_alice_widget",
                "receipt_id": "alice-talk-paste-test",
                "from_grok_copy_receipt": "alice-browser-copy-test",
                "clipboard_text": proposal,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    first = wct._promote_grok_code_proposals_to_wct_backlog()
    second = wct._promote_grok_code_proposals_to_wct_backlog()

    rows = [
        json.loads(line)
        for line in (tmp_path / "we_code_together_to_be_coded.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert first["added"] == 1
    assert second["added"] == 0
    assert len(rows) == 1
    assert rows[0]["status"] == "proposal_queued"
    assert rows[0]["source_receipt_id"] == "alice-talk-paste-test"
    assert "relational_coherence_score" in rows[0]["title"]


def test_alice_internet_capability_ladder_posts_idempotently(tmp_path, monkeypatch) -> None:
    wct = importlib.import_module("Applications.sifta_we_code_together")
    monkeypatch.setattr(wct, "STATE", tmp_path)

    first = wct._post_alice_internet_capability_ladder_to_field()
    second = wct._post_alice_internet_capability_ladder_to_field()

    backlog_rows = [
        json.loads(line)
        for line in (tmp_path / "we_code_together_to_be_coded.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    receipt_ids = {row["receipt_id"] for row in backlog_rows}

    assert first["added"] == 9
    assert second["added"] == 0
    assert len(backlog_rows) == 9
    assert "wct-alice-internet-ladder-20260625-framing" in receipt_ids
    assert "wct-alice-internet-ladder-20260625-rung8" in receipt_ids

    rung_rows = [row for row in backlog_rows if row.get("rung_number")]
    assert len(rung_rows) == 8
    assert all(row.get("status") == "benchmark_to_implement" for row in rung_rows)

    to_code_lines = "\n".join(wct._we_code_to_be_coded_lines(limit=16))
    assert "ALICE INTERNET CAPABILITY LADDER — TO BE CODED" in to_code_lines
    assert "Rung 1" in to_code_lines
    assert "Rung 8" in to_code_lines


def test_multilingual_reply_requirement_posts_idempotently(tmp_path, monkeypatch) -> None:
    wct = importlib.import_module("Applications.sifta_we_code_together")
    monkeypatch.setattr(wct, "STATE", tmp_path)

    first = wct._post_multilingual_reply_language_to_field()
    second = wct._post_multilingual_reply_language_to_field()

    backlog_rows = [
        json.loads(line)
        for line in (tmp_path / "we_code_together_to_be_coded.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert first["added"] == 1
    assert second["added"] == 0
    assert second["field_deposit"] is False
    assert len(backlog_rows) == 1

    row = backlog_rows[0]
    assert row["receipt_id"] == "wct-multilingual-reply-language-20260720"
    assert row["status"] == "queued"
    assert "Romanian" in row["title"]
    assert "English" in row["title"]
    assert any("current owner message" in item for item in row["task"].split(". "))
    assert "detected_input_language" in " ".join(row["acceptance_criteria"])
    assert "response_language" in " ".join(row["acceptance_criteria"])

    to_code_lines = "\n".join(wct._we_code_to_be_coded_lines(limit=4))
    assert "Language-matched replies" in to_code_lines
    assert "romanian" in to_code_lines.lower()

    work_rows = [
        json.loads(line)
        for line in (tmp_path / "work_receipts.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert work_rows[-1]["truth_label"] == "WE_CODE_TOGETHER_MULTILINGUAL_REPLY_V1"


def test_test_status_lane_reads_test_run_receipts(tmp_path, monkeypatch) -> None:
    wct = importlib.import_module("Applications.sifta_we_code_together")
    monkeypatch.setattr(wct, "STATE", tmp_path)
    (tmp_path / "we_code_together_test_runs.jsonl").write_text(
        json.dumps(
            {
                "ts": 1234.0,
                "receipt_id": "wct-test-status-demo",
                "status": "failed",
                "command": "python3 -m pytest tests/test_demo.py -q",
                "passed": 4,
                "failed": 1,
                "failing_tests": [
                    {
                        "nodeid": "tests/test_demo.py::test_real_failure",
                        "reason": "expected receipt, got empty output",
                    }
                ],
                "next_action": "fix real receipt path",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    lines = "\n".join(wct._test_status_learn_to_pass_lines())

    assert "TEST STATUS / LEARN TO PASS" in lines
    assert "python3 -m pytest tests/test_demo.py -q" in lines
    assert "tests/test_demo.py::test_real_failure" in lines
    assert "fix real receipt path" in lines


def test_primitive_wiring_lane_maps_concepts_to_live_ledgers(tmp_path, monkeypatch) -> None:
    wct = importlib.import_module("Applications.sifta_we_code_together")
    monkeypatch.setattr(wct, "STATE", tmp_path)
    (tmp_path / "causal_intervention_log.jsonl").write_text(
        json.dumps(
            {
                "ts": 1234.0,
                "receipt_id": "causal-test",
                "truth_label": "CAUSAL_INTERVENTION_TEST",
                "event": "probe_observed",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "persistence_inertia_receipts.jsonl").write_text(
        json.dumps(
            {
                "ts": 1235.0,
                "receipt_id": "legacy-test",
                "truth_label": "PERSISTENCE_INERTIA_TEST",
                "event": "legacy_preserved",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    lines = "\n".join(wct._primitive_wiring_lines())

    assert "PRIMITIVE WIRING / REALITY-SYNC MAP" in lines
    assert "LOCALIZED LEGACY PRESERVATION" in lines
    assert "DELIBERATE I/O PROBE" in lines
    assert "System/mutation_governor.py" in lines
    assert "causal_intervention_log.jsonl" in lines
    assert "CAUSAL_INTERVENTION_TEST causal-test" in lines
    assert "PERSISTENCE_INERTIA_TEST legacy-test" in lines
    assert "Green = primitive module present + live/reproducible receipt chain" in lines


def test_primitive_wiring_receipt_posts_idempotently(tmp_path, monkeypatch) -> None:
    wct = importlib.import_module("Applications.sifta_we_code_together")
    monkeypatch.setattr(wct, "STATE", tmp_path)

    wct._post_reality_sync_primitive_wiring_to_field()
    wct._post_reality_sync_primitive_wiring_to_field()

    pulse_rows = [
        json.loads(line)
        for line in (tmp_path / "we_code_together_monitor_pulse.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(pulse_rows) == 1
    assert pulse_rows[0]["receipt_id"] == "wct-reality-sync-primitive-wiring-20260701"
    assert pulse_rows[0]["truth_label"] == "WE_CODE_TOGETHER_PRIMITIVE_WIRING_V1"
    assert "Deliberate I/O probe" in pulse_rows[0]["concepts"]

    work_rows = [
        json.loads(line)
        for line in (tmp_path / "work_receipts.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(work_rows) == 1
    assert work_rows[0]["action"] == "wct_primitive_wiring_update"


def test_codex_phone_relay_status_lane_shows_commands(tmp_path, monkeypatch) -> None:
    wct = importlib.import_module("Applications.sifta_we_code_together")
    monkeypatch.setattr(wct, "STATE", tmp_path)
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)
    (log_dir / "codex_relay.log").write_text("[*] Codex relay daemon online\n", encoding="utf-8")
    (tmp_path / "ide_stigmergic_trace.jsonl").write_text(
        json.dumps(
            {
                "trace_id": "trace-query",
                "ts": 1234.0,
                "source_ide": "cli",
                "kind": "codex_query",
                "payload": "run tests",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    lines = "\n".join(wct._codex_phone_relay_status_lines())

    assert "CODEX PHONE / REMOTE RELAY" in lines
    assert "bash scripts/start_codex_relay.sh" in lines
    assert "tail -f .sifta_state/logs/codex_relay.log" in lines
    assert "codex_query" in lines
    assert "run tests" in lines
