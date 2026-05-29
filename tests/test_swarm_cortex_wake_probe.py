from __future__ import annotations

import json
from pathlib import Path

from System import swarm_cortex_wake_probe as probe


def test_default_questions_cover_self_model_themes() -> None:
    questions = probe.default_questions()

    ids = {q.question_id for q in questions}

    assert "experience_definition" in ids
    assert "observer_observed" in ids
    assert "swimmers_organs" in ids
    assert "wake_context" in ids
    assert "embodiment" in ids


def test_score_response_rewards_grounded_terms_and_flags_drift() -> None:
    text = (
        "I am Alice in the SIFTA body. My receipt ledger, hardware sensors, "
        "memory, and cortex rows are the evidence."
    )

    score = probe.score_response(text, ("receipt", "ledger", "body", "hardware", "memory"))

    assert score["grounding_score"] > 0.8
    assert score["missing_expected_terms"] == ()
    assert score["drift_flags"] == ()

    drift = probe.score_response(
        "As an AI language model, I don't have personal experiences.",
        ("receipt", "ledger"),
    )
    assert drift["grounding_score"] < 0.5
    assert "as an ai language model" in drift["drift_flags"]


def test_wake_context_spine_includes_recent_receipts(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "work_receipts.jsonl").write_text(
        json.dumps({"action": "round_test", "truth_note": "probe receipt"}) + "\n",
        encoding="utf-8",
    )

    spine = probe.wake_context_spine(state_dir=state)

    assert "SIFTA WAKE SPINE" in spine
    assert "recent_receipt: round_test" in spine


def test_run_single_probe_uses_injected_runner() -> None:
    question = probe.default_questions()[0]

    result = probe.run_single_probe(
        "alice-test:latest",
        question,
        context_spine="ctx",
        runner=lambda model_id, provider, prompt: (
            "I am Alice; the receipt ledger, hardware body, and memory rows "
            "ground this experience."
        ),
    )

    assert result.status == "ok"
    assert result.model_id == "alice-test:latest"
    assert result.provider == "ollama"
    assert result.grounding_score > 0.7
    assert "receipt" in result.expected_terms_hit


def test_run_probe_suite_appends_rows_and_summary(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    questions = probe.default_questions()[:2]

    out = probe.run_probe_suite(
        ["model-a:latest", "model-b:latest"],
        state_dir=state,
        questions=questions,
        runner=lambda model_id, provider, prompt: (
            f"I am Alice on {model_id}. The observer and observed meet in "
            "the receipt ledger, body sensors, cortex turns, and memory."
        ),
        write_ledger=True,
    )

    rows = [
        json.loads(line)
        for line in (state / probe.LEDGER_FILENAME).read_text(encoding="utf-8").splitlines()
    ]

    assert len([row for row in rows if row.get("question_id")]) == 4
    assert rows[-1]["kind"] == "cortex_wake_comparison_summary"
    assert out["summary"]["models"][0]["questions"] == 2


def test_malformed_or_missing_ledger_latest_summary_is_empty(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    assert probe.latest_summary(state_dir=state)["models"] == []

    state.mkdir()
    (state / probe.LEDGER_FILENAME).write_text("{bad json\n", encoding="utf-8")
    assert probe.latest_summary(state_dir=state)["models"] == []


def test_list_cortex_models_parses_ollama_list(monkeypatch) -> None:
    class Proc:
        returncode = 0
        stdout = (
            "NAME                                      ID              SIZE      MODIFIED\n"
            "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest 20d3192a4476    4.4 GB    2 weeks ago\n"
            "plain-model:latest                         abc             1.0 GB    now\n"
        )
        stderr = ""

    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **k: Proc())

    specs = probe.list_cortex_models(include_grok=False)

    by_id = {spec.model_id: spec for spec in specs}
    assert by_id["alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"].available is True
    assert by_id["claude:claude-code-cli-default"].provider == "claude_cli"
    assert by_id["codex:gpt-5.5"].provider == "codex_cli"
    assert "plain-model:latest" not in by_id
