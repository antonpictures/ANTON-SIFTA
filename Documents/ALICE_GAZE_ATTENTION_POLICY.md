# Alice Gaze Attention Policy

Alice now has a connected sensor attention loop instead of isolated camera pickers.

The design is:

```text
Sensor Registry -> World State -> Attention Policy -> Active Sense Lease -> Evidence Ledger
```

## Connected Modules

| Module | Job | Reads | Writes |
|---|---|---|---|
| `Applications/sifta_what_alice_sees_widget.py` | Physical eye UI and actuator | `.sifta_state/active_saccade_target.json` | Camera selection, target ledger when the user chooses a camera |
| `System/swarm_camera_target.py` | Canonical active-eye contract | camera names, indexes, leases | `.sifta_state/active_saccade_target.json` and legacy `.txt` mirror |
| `System/swarm_ide_gaze_tracker.py` | IDE/screen focus saccades | `.sifta_state/ide_screen_swimmers.jsonl` | active camera target lease |
| `System/swarm_oculomotor_saccades.py` | reflexive visual/audio/RF saccades | visual/audio/RF ledgers | active camera target lease |
| `System/swarm_multisensory_colliculus.py` | audio + face + visual convergence | audio and face ledgers | active camera target lease |
| `System/swarm_sensor_attention_director.py` | resident policy organ | all above sensory ledgers | active camera target lease plus `.sifta_state/sensory_attention_ledger.jsonl` |
| `sifta_os_desktop.py` | live shell integration | desktop timer | calls the attention director every two seconds |

## Policy

The director chooses between two default eyes:

| Eye | Camera | Use |
|---|---|---|
| `close_owner_eye` | `MacBook Pro Camera` | close owner face, desk conversation, primary-screen work |
| `room_patrol_eye` | `USB Camera VID:1133 PID:2081` | room scan, motion, sound, owner lost, external-screen work |

The decision order is intentionally simple and auditable:

1. External IDE focus goes to the room/patrol eye.
2. Fresh owner face lock goes to the close MacBook eye.
3. Audio spike, motion spike, low visual entropy, lost owner, or unknown face goes to the room eye.
4. Primary-screen IDE focus goes to the close eye.
5. Otherwise hold the current eye, or default to the close owner eye.

Every decision appends one JSON row to:

```text
.sifta_state/sensory_attention_ledger.jsonl
```

That row includes the target, reason, evidence, and the active camera target result. This is the audit trail for "why this sense now?"

## Runtime

Run one policy tick:

```bash
PYTHONPATH=. python3 -m System.swarm_sensor_attention_director --once
```

Run without changing the active camera target:

```bash
PYTHONPATH=. python3 -m System.swarm_sensor_attention_director --once --dry-run
```

The desktop calls the same organ automatically every two seconds. Disable only for tests or emergency isolation:

```bash
SIFTA_DISABLE_ATTENTION_DIRECTOR=1 PYTHONPATH=. python3 sifta_os_desktop.py
```

Hot reload alias:

```bash
PYTHONPATH=. python3 -m System.swarm_hot_reload reload attention_director
```
