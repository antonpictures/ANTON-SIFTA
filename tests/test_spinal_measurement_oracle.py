"""Patch retention needs executed tests and independent before/after readings."""
import pytest

from System import swarm_spinal_cord as sc


def setup_case(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "REPO", tmp_path)
    path = tmp_path / "organ.py"
    path.write_text("value = 1\n")
    monkeypatch.setattr(sc, "_check_mutation_governor", lambda *a, **k: True)
    monkeypatch.setattr(sc, "_run_tests", lambda paths: True)
    task = sc.PatchTask("t", 10, "s", ["organ.py"], "fix", ["test_organ.py"])
    patch = sc.PatchResult("t", 10, True, "", "value = 2\n", "fix", True, True, True)
    return path, task, patch


@pytest.mark.parametrize("missing", ["tests", "metric"])
def test_missing_evidence_does_not_touch_source(tmp_path, monkeypatch, missing):
    path, task, patch = setup_case(tmp_path, monkeypatch)
    if missing == "tests":
        task.test_paths = []
    out = sc.gate_and_apply(patch, task, state_dir=tmp_path / "state",
                            metric_probe=(lambda: 1) if missing == "tests" else None)
    assert out["status"] == "UNVERIFIED"
    assert out["measured_gain"] is None
    assert not out["tests_passed"]
    assert path.read_text() == "value = 1\n"


@pytest.mark.parametrize("after,status", [(0.5, "KEPT"), (0.1, "REVERTED"),
                                         (float("nan"), "REVERTED")])
def test_gain_is_measured_and_failure_restores_source(tmp_path, monkeypatch, after, status):
    path, task, patch = setup_case(tmp_path, monkeypatch)
    readings = iter([0.2, after])
    out = sc.gate_and_apply(patch, task, state_dir=tmp_path / "state",
                            metric_probe=lambda: next(readings))
    assert out["status"] == status
    assert path.read_text() == ("value = 2\n" if status == "KEPT" else "value = 1\n")
    if status == "KEPT":
        assert out["measured_gain"] == pytest.approx(0.3)
        assert out["measured_gain"] != task.predicted_gain


def test_test_runner_exception_restores_source(tmp_path, monkeypatch):
    path, task, patch = setup_case(tmp_path, monkeypatch)
    def broken(paths):
        raise TimeoutError()
    monkeypatch.setattr(sc, "_run_tests", broken)
    out = sc.gate_and_apply(patch, task, state_dir=tmp_path / "state", metric_probe=lambda: 1)
    assert out["status"] == "REVERTED"
    assert path.read_text() == "value = 1\n"


def test_empty_and_all_skipped_suite_are_not_success(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "REPO", tmp_path)
    assert not sc._run_tests([])
    (tmp_path / "test_empty.py").write_text("# no tests\n")
    (tmp_path / "test_skip.py").write_text("import pytest\n@pytest.mark.skip\ndef test_skip(): pass\n")
    (tmp_path / "test_pass.py").write_text("def test_arithmetic(): assert 2 + 2 == 4\n")
    assert not sc._run_tests(["test_empty.py"])
    assert not sc._run_tests(["test_skip.py"])
    assert sc._run_tests(["test_pass.py"])
