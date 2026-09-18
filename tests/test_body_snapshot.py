import json

import pytest

from System.swarm_body_snapshot import body_snapshot


def test_missing_organs_are_not_claimed_healthy(tmp_path):
    result = body_snapshot(state_dir=tmp_path, epoch=1000)
    assert result['clock']['epoch'] == 1000
    assert result['cortex']['status'] == result['organ_health']['status'] == 'UNAVAILABLE'
    assert result['physical_joint_sensors'] == 'UNAVAILABLE'


@pytest.mark.parametrize('age,expected', [(0, 'FRESH_CACHE'), (30, 'FRESH_CACHE'),
                                         (61, 'STALE'), (-1, 'STALE')])
def test_cache_freshness_and_location_privacy(tmp_path, age, expected):
    (tmp_path / 'organ_health_mesh_latest.json').write_text(json.dumps({
        'ts': 1000-age, 'after': {'organs': {'eyes': {'status': 'healthy'}, 'ears': {'status': 'sick'}}}}))
    (tmp_path / 'primary_cortex.json').write_text(json.dumps({
        'changed_at': 990, 'model': 'test:local', 'provider': 'ollama', 'auth': 'must-not-export'}))
    (tmp_path / 'mac_location_latest.json').write_text(json.dumps({
        'status': 'SUCCESS', 'latitude': 45, 'longitude': 26, 'accuracy': 10,
        'observed_at': 990, 'source': 'macos_corelocation'}))
    result = body_snapshot(state_dir=tmp_path, epoch=1000)
    assert result['organ_health']['status'] == expected
    assert result['organ_health']['reported_healthy_count'] == 1
    assert result['location']['status'] == 'SUCCESS'
    assert 'latitude' not in result['location'] and 'longitude' not in result['location']
    assert 'auth' not in result['cortex']
    assert result['cortex']['model'] == 'test:local'


@pytest.mark.parametrize('raw', ['{}', 'null', 'invalid', '{"ts":NaN}', 'x'*65537])
def test_invalid_cache_does_not_crash(tmp_path, raw):
    (tmp_path / 'organ_health_mesh_latest.json').write_text(raw)
    assert body_snapshot(state_dir=tmp_path, epoch=1000)['organ_health']['status'] == 'UNAVAILABLE'
