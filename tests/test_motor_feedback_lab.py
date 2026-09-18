import hashlib
import json
import math

import pytest

from System.stigmerobotics_motor_feedback_lab import (
    MotorConfig, forward, inverse, motor_feedback_evidence_lines, run_trial,
    run_benchmark,
)


@pytest.mark.parametrize('target', [(1, .5), (1.5, .4), (.8, 1.1)])
def test_kinematic_roundtrip(target):
    assert forward(inverse(target, 2.8)) == pytest.approx(target)


@pytest.mark.parametrize('policy', ['continuous', 'event'])
def test_dropout_stops_and_recovers(policy):
    trial = run_trial(policy, 'dropout')
    held = [r for r in trial['rows'] if r['status'] == 'HOLD_STALE']
    assert held
    assert all(r['command_rad_s'] == [0, 0] and r['joint_echo'] == r['joint_before'] for r in held)
    assert trial['metrics']['recovery_after_sensor_return_s'] is not None
    assert trial['metrics']['final_error_m'] < .09


@pytest.mark.parametrize('scenario', ['static', 'moving', 'disturbance'])
def test_event_budget_preserves_tracking(scenario):
    a = run_trial('continuous', scenario)
    b = run_trial('event', scenario)
    assert b['metrics']['visual_feature_refreshes'] < a['metrics']['visual_feature_refreshes']/2
    assert b['metrics']['tail_max_error_m'] < .09
    for row in b['rows']:
        assert all(abs(q) <= 2.8 for q in row['joint_echo'])
        assert all(abs(v) <= 1.5 for v in row['command_rad_s'])


def test_unreachable_never_moves():
    trial = run_trial('event', 'unreachable')
    assert trial['metrics']['rejected_actions'] == 400
    assert all(r['joint_before'] == r['joint_echo'] for r in trial['rows'])
    assert inverse((math.nan, 0), 2.8) is None


def test_invalid_configuration_and_missing_evidence(tmp_path):
    with pytest.raises(ValueError):
        MotorConfig(dt=math.nan)
    with pytest.raises(ValueError):
        MotorConfig(refresh_age=1)
    assert 'NOT RUN' in motor_feedback_evidence_lines(tmp_path)


def test_benchmark_persists_unique_pairs_and_monitor_evidence(tmp_path):
    summary = run_benchmark(tmp_path)
    raw = (tmp_path / 'motor_feedback_runs' / summary['run_id'] / 'actions.jsonl').read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    assert summary['status'] == 'PASS'
    assert len(rows) == len({r['receipt_id'] for r in rows}) == 12000
    assert hashlib.sha256(raw).hexdigest() == summary['actions_sha256']
    assert all(len(r['command_rad_s']) == len(r['joint_echo']) == 2 for r in rows)
    assert any('12000 command/echo pairs' in line for line in motor_feedback_evidence_lines(tmp_path))
    (tmp_path / 'motor_feedback_experiments.jsonl').write_text('broken\n')
    assert any('UNAVAILABLE' in line for line in motor_feedback_evidence_lines(tmp_path))
