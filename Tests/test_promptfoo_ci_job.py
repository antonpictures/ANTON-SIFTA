from __future__ import annotations

import json
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


def test_promptfoo_ci_job_is_local_receipted_and_budget_guarded() -> None:
    script = REPO / "scripts" / "run_promptfoo_rlhs_ci.sh"
    body = script.read_text(encoding="utf-8")

    assert script.exists()
    assert "tests/rlhs_evals" in body
    assert "127.0.0.1:11434/api/tags" in body
    assert "npm ci" in body
    assert "promptfoo eval" in body
    assert "STATE_DIR=" in body
    assert "promptfoo_rlhs_ci" in body
    assert "promptfoo_rlhs_ci_runs.jsonl" in body
    assert "PROMPTFOO_DISABLE_TELEMETRY" in body
    assert "tests/test_rlhs_evals_provider.py" in body
    assert "tests/test_swarm_rlhf_detector.py" in body
    assert "tests/test_immune_budget_simulation.py" in body


def test_promptfoo_package_exposes_local_ci_script() -> None:
    pkg = json.loads((REPO / "tests" / "rlhs_evals" / "package.json").read_text(encoding="utf-8"))
    scripts = pkg["scripts"]

    assert scripts["ci:local"] == "../../scripts/run_promptfoo_rlhs_ci.sh"
    assert scripts["eval"] == "promptfoo eval"
    assert scripts["view"] == "promptfoo view"


def test_promptfoo_readme_names_receipt_outputs() -> None:
    readme = (REPO / "tests" / "rlhs_evals" / "README.md").read_text(encoding="utf-8")

    assert "scripts/run_promptfoo_rlhs_ci.sh" in readme
    assert ".sifta_state/promptfoo_rlhs_ci/" in readme
    assert ".sifta_state/promptfoo_rlhs_ci_runs.jsonl" in readme
    assert "Kleiber budget simulation" in readme
