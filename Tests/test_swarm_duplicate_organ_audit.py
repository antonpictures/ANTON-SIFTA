import json
from pathlib import Path

from System.swarm_duplicate_organ_audit import audit_repo


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _minimal_repo(root: Path) -> None:
    _write(
        root / "Applications" / "apps_manifest.json",
        json.dumps(
            {
                "Alice": {
                    "category": "Core",
                    "entry_point": "Applications/alice.py",
                    "widget_class": "AliceWidget",
                }
            }
        ),
    )
    _write(
        root / "System" / "swarm_architect_face_recognition.py",
        '_TRUTH_LABEL = "ARCHITECT_FACE_EMBEDDING_V1"\n',
    )


def _find(result: dict, kind: str) -> list[dict]:
    return [item for item in result["findings"] if item["kind"] == kind]


def test_duplicate_manifest_entry_point_is_error(tmp_path: Path) -> None:
    _minimal_repo(tmp_path)
    manifest = {
        "One": {
            "category": "Demo",
            "entry_point": "Applications/one.py",
            "widget_class": "OneWidget",
        },
        "Two": {
            "category": "Demo",
            "entry_point": "Applications/one.py",
            "widget_class": "TwoWidget",
        },
    }
    _write(tmp_path / "Applications" / "apps_manifest.json", json.dumps(manifest))

    result = audit_repo(tmp_path)

    assert result["ok"] is False
    assert _find(result, "duplicate_manifest_entry_point")


def test_retired_manifest_duplicate_is_ignored(tmp_path: Path) -> None:
    _minimal_repo(tmp_path)
    manifest = {
        "Living": {
            "category": "Demo",
            "entry_point": "Applications/shared.py",
            "widget_class": "LivingWidget",
        },
        "Retired": {
            "category": "Demo",
            "entry_point": "Applications/shared.py",
            "widget_class": "OldWidget",
            "_retired": True,
        },
    }
    _write(tmp_path / "Applications" / "apps_manifest.json", json.dumps(manifest))

    result = audit_repo(tmp_path)

    assert not _find(result, "duplicate_manifest_entry_point")


def test_owner_face_wrapper_delegating_to_ag46_is_allowed(tmp_path: Path) -> None:
    _minimal_repo(tmp_path)
    _write(
        tmp_path / "System" / "swarm_sovereign_recognition_organ.py",
        """
from System.swarm_architect_face_recognition import _EMBEDDING, _extract_face_patch

def wrapper(frame):
    return _extract_face_patch(frame), _EMBEDDING
""",
    )

    result = audit_repo(tmp_path)

    assert result["ok"] is True
    assert not _find(result, "owner_face_identity_duplicate")


def test_owner_face_duplicate_pipeline_without_delegation_is_error(tmp_path: Path) -> None:
    _minimal_repo(tmp_path)
    _write(
        tmp_path / "System" / "swarm_sovereign_recognition_organ.py",
        """
_EMBEDDING = ".sifta_state/new_owner_face_embedding.npy"

def _extract_face_patch(frame):
    # second owner-face pipeline; no delegation to canonical organ
    return frame
""",
    )

    result = audit_repo(tmp_path)

    assert result["ok"] is False
    findings = _find(result, "owner_face_identity_duplicate")
    assert findings
    assert findings[0]["lane"] == "owner_face_identity"


def test_duplicate_truth_label_is_warning_not_blocker(tmp_path: Path) -> None:
    _minimal_repo(tmp_path)
    _write(tmp_path / "System" / "a.py", 'TRUTH_LABEL = "SAME_LABEL"\n')
    _write(tmp_path / "System" / "b.py", '_TRUTH_LABEL = "SAME_LABEL"\n')

    result = audit_repo(tmp_path)

    assert result["ok"] is True
    findings = _find(result, "duplicate_truth_label")
    assert findings
    assert findings[0]["severity"] == "warning"
