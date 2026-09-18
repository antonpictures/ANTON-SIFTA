"""Read-only, timestamped host context. Cached organ reports are not live proof."""
from __future__ import annotations

import json
import math
from pathlib import Path

from System.swarm_gps_sensor import read_location_snapshot
from System.swarm_hardware_time_oracle import live_clock_snapshot


ROOT = Path(__file__).resolve().parents[1]


def _cached(path, timestamp, now, max_age):
    try:
        with path.open('rb') as handle:
            raw = handle.read(65537)
        if len(raw) > 65536:
            return {'status': 'OVERSIZED'}, {}
        row = json.loads(raw)
        stamp = row[timestamp]
        if isinstance(stamp, bool) or not isinstance(stamp, (float, int)) or not math.isfinite(stamp):
            raise ValueError('invalid timestamp')
        age = now - stamp
        status = 'FRESH_CACHE' if 0 <= age <= max_age else 'STALE'
        return {'status': status, 'source': path.name, 'observed_at': stamp, 'age_s': age}, row
    except (OSError, ValueError, TypeError, KeyError):
        return {'status': 'UNAVAILABLE', 'source': path.name}, {}


def body_snapshot(*, state_dir=None, epoch=None):
    """No sensor activation, model inference, precise location, or identity export."""
    state = Path(state_dir) if state_dir is not None else ROOT / '.sifta_state'
    clock = live_clock_snapshot(epoch=epoch)
    now = clock['epoch']
    location = read_location_snapshot(state_dir=state, now=now)
    cortex, row = _cached(state / 'primary_cortex.json', 'changed_at', now, 300)
    # A selection record says what was selected, not whether weights are running.
    cortex.update(model=str(row.get('model') or '')[:256],
                  provider=str(row.get('provider') or '')[:64],
                  scope='cached_selection_not_loaded_model_probe')
    health, row = _cached(state / 'organ_health_mesh_latest.json', 'ts', now, 60)
    after = row.get('after')
    organs = after.get('organs') if isinstance(after, dict) else None
    if isinstance(organs, dict) and organs:
        health['reported_organ_count'] = len(organs)
        health['reported_healthy_count'] = sum(isinstance(v, dict) and v.get('status') == 'healthy'
                                                for v in organs.values())
    else:
        health['status'] = 'UNAVAILABLE'
    return {'schema': 'sifta.body_snapshot.v1', 'clock': clock,
            'location': {k: location[k] for k in ('status', 'source', 'age_seconds', 'accuracy') if k in location},
            'cortex': cortex, 'organ_health': health,
            'physical_joint_sensors': 'UNAVAILABLE',
            'scope': 'Host context only; not motor feedback, authorization, or proof of consciousness.'}
