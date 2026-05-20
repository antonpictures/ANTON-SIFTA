from pathlib import Path

from System.swarm_duplicate_organ_audit import audit_repo


REPO = Path(__file__).resolve().parents[1]


def test_current_repo_has_no_duplicate_organ_blockers() -> None:
    result = audit_repo(REPO)
    errors = [item for item in result["findings"] if item["severity"] == "error"]
    assert errors == []


def test_owner_face_identity_stays_single_canonical_lane() -> None:
    result = audit_repo(REPO)
    duplicate_identity = [
        item
        for item in result["findings"]
        if item["kind"] == "owner_face_identity_duplicate"
    ]
    assert duplicate_identity == []
    assert result["canonical_owner_face_identity"] == "System/swarm_architect_face_recognition.py"
