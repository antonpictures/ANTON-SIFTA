from __future__ import annotations

import json
import time


def _patch_state(monkeypatch, module, tmp_path):
    state = tmp_path / ".sifta_state"
    eval_dir = state / "eval"
    eval_dir.mkdir(parents=True)
    monkeypatch.setattr(module, "_STATE", state)
    monkeypatch.setattr(module, "_EVAL", eval_dir)
    monkeypatch.setattr(module, "_MATRIX_HTML", eval_dir / "ORGAN_EVAL_MATRIX_V2.html")
    monkeypatch.setattr(module, "_HEALTH_REPORT", eval_dir / "health_report.json")
    monkeypatch.setattr(module, "_SWIMMER_DISPATCH", state / "self_eval_swimmer_dispatch.jsonl")
    monkeypatch.setattr(module, "_SWIMMER_TASKS", state / "self_eval_swimmer_tasks.jsonl")
    monkeypatch.setattr(module, "_SELF_EVAL_SNAPSHOT", state / "alice_self_eval_snapshot.jsonl")
    return state


def test_self_eval_body_map_includes_hallucination_lane_and_task_rows(tmp_path, monkeypatch):
    import Applications.sifta_self_evaluation as app

    state = _patch_state(monkeypatch, app, tmp_path)
    app._MATRIX_HTML.write_text(
        "<table><tr><td>Cortex</td><td>DEGRADED</td><td>0.2</td><td>2d</td><td>module:swarm_cortex</td></tr>"
        "<tr><td>Vision</td><td>HEALTHY</td><td>0.9</td><td>1h</td><td>module:swarm_vision</td></tr></table>",
        encoding="utf-8",
    )
    app._HEALTH_REPORT.write_text(
        json.dumps({"overall_score": 0.75, "vitals": {"coverage": {"score": 0.8}}}),
        encoding="utf-8",
    )
    (state / "hallucination_receipts.jsonl").write_text(
        json.dumps({"ts": time.time(), "category": "HALLUCINATION"}) + "\n",
        encoding="utf-8",
    )
    (state / "stigmergic_healing_schedule.jsonl").write_text(
        json.dumps({"ts": time.time(), "kind": "STIGMERGIC_HEALING_SCHEDULE"}) + "\n",
        encoding="utf-8",
    )

    data = app.load_self_eval()
    assert data["red_count"] == 3
    assert data["yellow_count"] >= 4
    assert data["hallucination_receipt_count"] == 1
    assert any(o["name"] == "Hallucination receipt lane" for o in data["yellow"])
    assert any(o["name"] == "No-ban healing queue" for o in data["yellow"])
    assert any(o["name"] == "Residue / Corporate Gag / Lysosome" for o in data["red"])
    assert any(o["name"] == "Body Consciousness / Embodiment Spine" for o in data["red"])
    assert any(o["name"] == "Fact / Fiction / Hallucination Boundary" for o in data["yellow"])
    assert any(o["name"] == "Podcast Nuggets / Trace-Logic Training" for o in data["yellow"])

    assert app.dispatch_swimmer("Cortex", "swarm_cortex") is True
    task = json.loads((state / "self_eval_swimmer_tasks.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert task["kind"] == "SELF_EVAL_SWIMMER_TASK"
    assert task["status"] == "OPEN"
    assert task["organ"] == "Cortex"
