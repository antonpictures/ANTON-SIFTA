import math

import pytest

from System.swarm_motor_action_gate import MotorActionGate, PlanProposal
from System.stigmerobotics_motor_feedback_lab import run_trial


def decide(gate=None, sequence=0, stamp=1.0, target=(1.0, 1.0), **kwargs):
    gate = gate or MotorActionGate()
    return gate.decide(PlanProposal(sequence, stamp, target),
                       **dict(dict(now_s=1.0, joints=(0.0, .5), dt=.02), **kwargs))


@pytest.mark.parametrize('stamp,status', [(None, 'HOLD_STALE'), (.69, 'HOLD_STALE'),
    (math.nan, 'HOLD_STALE'), ('yesterday', 'HOLD_STALE'),
    (1.1, 'REJECT_FUTURE_OBSERVATION')])
def test_bad_observation_never_moves(stamp, status):
    result = decide(stamp=stamp)
    assert result.status == status
    assert result.command_rad_s == (0, 0)


@pytest.mark.parametrize('target', [(math.nan, 0), (3, 0), (0,), ('1', 0), (True, 0)])
def test_invalid_target(target):
    assert decide(target=target).status == 'REJECT_TARGET'


@pytest.mark.parametrize('kwargs', [{'dt': 0}, {'dt': math.inf}, {'dt': .2},
    {'now_s': 'now'}, {'joints': (3, 0)}, {'joints': (0, math.nan)}])
def test_invalid_state(kwargs):
    assert decide(**kwargs).status == 'REJECT_STATE'


def test_retry_and_out_of_order_never_repeat_motion():
    gate = MotorActionGate()
    assert decide(gate, sequence=2).status == 'LIMITED'
    for sequence in (2, 1, 0):
        result = decide(gate, sequence=sequence)
        assert result.status == 'HOLD_REPLAY'
        assert result.command_rad_s == (0, 0)


def test_stop_latches_and_reset_does_not_replay():
    gate = MotorActionGate()
    gate.stop()
    assert decide(gate).status == 'HOLD_STOP'
    assert decide(gate, sequence=1).status == 'HOLD_STOP'
    gate.reset_stop()
    assert decide(gate, sequence=1).status == 'HOLD_REPLAY'
    assert decide(gate, sequence=2).status == 'LIMITED'


def test_mode_and_bad_sequence():
    gate = MotorActionGate()
    assert gate.decide(PlanProposal(0, 1, (0, 0), 'HARDWARE'),
                       now_s=1, joints=(0, 0), dt=.02).status == 'REJECT_MODE'
    for value in (True, -1, '1'):
        assert decide(sequence=value).status == 'REJECT_INVALID_SEQUENCE'


def test_pair_limits_and_independent_echo():
    result = decide(target=(2.8, -2.8), joints=(2.79, -2.79))
    assert all(abs(v) <= 1.5 for v in result.command_rad_s)
    assert all(abs(q+.02*v) <= 2.8 for q, v in zip((2.79, -2.79), result.command_rad_s))
    rows = run_trial('event', 'disturbance')['rows']
    assert len({r['proposal']['sequence'] for r in rows}) == len(rows)
    for row in rows:
        assert row['outcome']['sequence'] == row['proposal']['sequence']
        assert row['outcome']['joint_echo'] == tuple(row['joint_echo'])
        assert row['outcome']['truth_label'] == 'SIMULATED'
    # A desired position is not passed off as the plant's actual position.
    assert rows[0]['proposal']['desired_joints'] != rows[0]['outcome']['joint_echo']
