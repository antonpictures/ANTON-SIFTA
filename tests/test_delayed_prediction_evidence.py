from copy import deepcopy

import pytest

from System.swarm_active_inference_world_model import evaluate_delayed_prediction


def pair():
    scope = dict(node_id="mac1", device_id="phone1", session_id="s1",
                 coordinate_frame="sensor:phone1", units={"battery": "ratio"})
    return (dict(trace_id="p1", ts=10, target_at=30, tolerance_s=2,
                 source_event_ids=["e1"], evaluation_scope=scope,
                 predicted_next_state={"battery": 0.6}),
            dict(event_id="e2", ts=30, evaluation_scope=deepcopy(scope), values={"battery": 0.5}))


def test_later_observation_scores_frozen_forecast_without_training():
    prediction, observation = pair()
    before = deepcopy((prediction, observation))
    result = evaluate_delayed_prediction(prediction, observation)
    assert result["status"] == "SCORED"
    assert result["residuals"]["battery"]["absolute_error"] == pytest.approx(0.1)
    assert not result["training_performed"]
    assert (prediction, observation) == before


@pytest.mark.parametrize("key", ["node_id", "device_id", "session_id", "coordinate_frame", "units"])
def test_incompatible_frames_and_units_do_not_score(key):
    prediction, observation = pair()
    observation["evaluation_scope"][key] = "different"
    assert evaluate_delayed_prediction(prediction, observation)["status"] == "UNSCORABLE"


@pytest.mark.parametrize("change", ["empty", "missing_metric", "reused", "early", "late", "nan", "bool"])
def test_missing_or_leaked_evidence_is_unscorable(change):
    p, o = pair()
    if change == "empty": p["predicted_next_state"] = {}
    elif change == "missing_metric": o["values"] = {}
    elif change == "reused": o["event_id"] = "e1"
    elif change == "early": o["ts"] = 10
    elif change == "late": o["ts"] = 99
    elif change == "nan": o["values"]["battery"] = float("nan")
    elif change == "bool": o["values"]["battery"] = True
    assert evaluate_delayed_prediction(p, o)["status"] == "UNSCORABLE"
