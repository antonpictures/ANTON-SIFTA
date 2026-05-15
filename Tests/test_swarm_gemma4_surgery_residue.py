import json
from pathlib import Path

from System.swarm_gemma4_surgery_residue import log_surgery_residue, surgery_residue_path


def test_log_surgery_residue_writes_append_only_row(tmp_path: Path):
    row = log_surgery_residue(
        kind="generated_output_residue",
        source="test",
        pattern="lysosome/domain-medical-boilerplate",
        sample="I cannot provide medical advice.",
        action="rewrite_now_and_mark_for_gemma4_surgery",
        root=tmp_path,
        meta={"prior_user_text": "body input"},
    )

    path = surgery_residue_path(tmp_path)
    assert path.exists()
    stored = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])

    assert row["schema"] == "GEMMA4_SURGERY_RESIDUE_V1"
    assert stored["schema"] == "GEMMA4_SURGERY_RESIDUE_V1"
    assert stored["kind"] == "generated_output_residue"
    assert stored["pattern"] == "lysosome/domain-medical-boilerplate"
    assert stored["action"] == "rewrite_now_and_mark_for_gemma4_surgery"
    assert stored["truth_label"] == "OBSERVED"
    assert stored["meta"]["prior_user_text"] == "body input"
