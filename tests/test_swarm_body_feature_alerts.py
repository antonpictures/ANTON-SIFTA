import json
from pathlib import Path

from System.swarm_body_feature_alerts import append_body_feature_alert, format_body_feature_alerts


def test_body_feature_alert_append_is_idempotent(tmp_path: Path):
    kwargs = {
        "feature": "test_feature",
        "code_path": "System/test_feature.py",
        "summary": "feature entered the body map",
        "state_dir": tmp_path,
        "now": 123.0,
    }

    append_body_feature_alert(**kwargs)
    append_body_feature_alert(**kwargs)

    lines = (tmp_path / "body_feature_alerts.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["feature"] == "test_feature"


def test_body_feature_alert_formatter_includes_integration_gap(monkeypatch, tmp_path: Path):
    def fake_body_alert_line() -> str:
        return "[body-integration] ALERT IN MY BODY: 1 new part added. Register it."

    import System.swarm_body_integration_alert as integration

    monkeypatch.setattr(integration, "body_alert_line", fake_body_alert_line)
    append_body_feature_alert(
        feature="cortex_options",
        code_path="System/swarm_cortex_options.py",
        summary="cortex options wired",
        state_dir=tmp_path,
        now=124.0,
    )

    text = format_body_feature_alerts(state_dir=tmp_path, max_items=1)
    assert "ALERT IN MY BODY" in text
    assert "body-integration" in text
    assert "cortex_options" in text
