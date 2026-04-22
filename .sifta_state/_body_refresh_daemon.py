#!/usr/bin/env python3
from __future__ import annotations
import time
from pathlib import Path
import json
import sys

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

state = _REPO / '.sifta_state'
state.mkdir(parents=True, exist_ok=True)
heartbeat = state / '_body_refresh_daemon_heartbeat.json'

print('[body-refresh] starting (5s cadence)', flush=True)
while True:
    now = time.time()
    try:
        from System.swarm_somatic_interoception import SwarmSomaticInteroception
        SwarmSomaticInteroception().scan()
    except Exception as e:
        print(f'[body-refresh] interoception error: {e}', flush=True)
    try:
        from System.swarm_mirror_lock import tick_once
        tick_once(now=now)
    except Exception as e:
        print(f'[body-refresh] mirror-lock error: {e}', flush=True)
    try:
        heartbeat.write_text(json.dumps({'ts': now}) + '\n', encoding='utf-8')
    except Exception:
        pass
    time.sleep(5.0)
