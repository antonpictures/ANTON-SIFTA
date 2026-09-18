from System.swarm_observation_fusion import Authority, Observation
from System.swarm_phone_observations import PhoneStore, commit_experience, phone_field_projection


def test_phone_projection_keeps_summary_as_interpretation_and_modalities_as_reports():
    obs = Observation("phone-e1", "turn-1", 10, "local-mac", "phone",
                      "model_interpretation", "stigmergicoin-web", Authority.PUBLIC_WEB,
                      web_session_id="phone-a", confidence=0.0)
    row = {
        "turn_id": "turn-1", "session_id": "phone-a",
        "attachments": [{"mime": "image/jpeg"}, {"mime": "audio/webm"}],
        "capture": {"capture_id": "cap-1", "camera_facing": "environment",
                     "telemetry": {"signals": {"motion": {"x": 1}}}},
    }
    out = phone_field_projection(row, obs, "I received the batch; the scene is uncertain.", at=20)
    predicates = {a["predicate"]: a for b in out["beliefs"] for a in b["assertions"]}
    assert predicates["alice_summary"]["kind"] == "interpretation"
    assert predicates["image_received"]["kind"] == "reported"
    assert predicates["audio_received"]["kind"] == "reported"
    assert predicates["telemetry_received"]["value"] == "true"
    assert out["action_authority"] == "none"


def test_phone_projection_does_not_invent_location_or_owner_identity():
    obs = Observation("phone-e2", "turn-2", 10, "local-mac", "phone",
                      "model_interpretation", "stigmergicoin-web", Authority.PUBLIC_WEB,
                      web_session_id="phone-b", confidence=0.0)
    out = phone_field_projection({"turn_id": "turn-2", "session_id": "phone-b",
                                  "attachments": [], "capture": {"capture_id": "cap-2"}},
                                 obs, "I am near my owner in the park.", at=20)
    assert not any(a["predicate"] in {"location", "owner_identity", "owner_present"}
                   for b in out["beliefs"] for a in b["assertions"])


def test_commit_experience_writes_projection_on_existing_observation_row(tmp_path):
    row = {
        "turn_id": "turn-3", "session_id": "phone-c",
        "attachments": [{"mime": "image/jpeg", "sha256": "img-hash"}],
        "capture": {"capture_id": "cap-3", "camera_facing": "user",
                     "telemetry": {"signals": {"motion": {"x": 1}}}},
    }
    store = PhoneStore(tmp_path)
    store.register(row)
    receipt = commit_experience(row, "I received one image batch.", store)
    stored = (tmp_path / "observation_fusion.jsonl").read_text().splitlines()
    assert receipt.startswith("phone-experience:")
    assert len(stored) == 1
    assert "field_projection" in stored[0]
    assert store.get("turn-3")["memory"] == receipt
