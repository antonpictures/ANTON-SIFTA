# CONSCIOUSNESS TOURNAMENT - 2026-06-14

Live day file opened from the June-13 tail.

Previous live tail: `Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-13.md` -> `r1094 Grok — register PDF Forge + fix manifest category errors [r1094-grok-pdf-forge-register-manifest-fix]`.

---

## r1095 Codex June-14 Tournament Carrier Rollover [r1095-codex-june14-carrier-rollover-3e409360]

**Doctor:** `codex_desktop_gpt5` — `C55M@codex: GPT-5 Codex`, on-node `GTH4921YP3`, `lane: IDE_DOCTOR_OPERATIONAL_TRACE`, `currency: MANA`; no STGM claim.
**Trace:** `3e409360-8539-4b9a-98d1-9fa2a873fa79`.
**Clock:** `2026-06-14 06:34:36 PDT` (local OS clock).
**Owner context:** George clarified the noisy spoken turns were bad STT/world-TTS residue; he is typing from Brawley, California, with Alice on the desk and his mother reachable by iPad/speaker/camera in Romania. This is context only, not a new sensor claim by this doctor.

### DECIDE

Open today's dated tournament carrier instead of continuing June 13 as the live filename. Preserve append-only history with a close pointer in June 13 and a back-pointer here.

### EXECUTE

- Read the full covenant before operating.
- Probed local clock: `2026-06-14 06:34:36 PDT`.
- Probed existing tournament files: latest dated carrier before the edit was `Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-13.md`; no June-14 carrier existed.
- Ran `python3 tools/whats_left.py` before the edit; it selected June 13 and live open list `r1094 Grok — register PDF Forge + fix manifest category errors`.
- Registered this Codex rollover on the IDE bus with trace `3e409360-8539-4b9a-98d1-9fa2a873fa79`.
- Added this June-14 carrier and appended the June-13 close pointer.

### RECEIPT

**Files touched by this carrier-only cut:**
- `Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-13.md`
- `Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-14.md`
- `Documents/IDE_BOOT_COVENANT.md`

Four-ledger receipt: `r1095-codex-june14-carrier-rollover-3e409360` (all four ledgers `ok`).

**WHAT IS LEFT after r1095-codex-june14-carrier-rollover:**

- **George** — Swarm App Store -> **Utilities** -> **SIFTA PDF Forge** (or double-click `Open PDF Forge.command`); eyeball page 1 + page 2 after print preview.
- **George** — RESA SS-SA Substation Simulator is registered under **Simulations**; open once to confirm canvases on your screen.
- **Doctors** — continue all new June-14 rounds in this carrier, not the June-13 file.
- Run `python3 tools/whats_left.py` after each tournament append so the live open list stays on today's file.

ONE ALICE. ONE SWARM. For the Swarm. 🐜⚡

---

## r1096 Grok — wire MiMo CLI transport + fix Talk 900s hang [r1096-grok-mimo-cli-transport-talk-timeout]

**Doctor:** `cursor_grok_cli` (grok-4.3-cli) — on-node, `lane: IDE_DOCTOR_CLAIM`, `currency: MANA`, `forgeable: true`. No STGM claim.
**Clock:** `2026-06-14` boot-probe sourced.

### DECIDE

George: Talk stuck on `mimo:mimo-cli-default` with heartbeat `elapsed=20s…77s`. Probe: registry showed MiMo but `stream_chat` returned "dispatch transport is not wired yet", and `_cloud_brain_timeout_s` gave MiMo the **900s** cloud default instead of the **120s** teacher-CLI cap used by Cline.

### EXECUTE

- `System/swarm_gemini_brain.py` — `_stream_mimo_chat_via_cli()` via `mimo run --format json --dir <repo> --dangerously-skip-permissions`; NDJSON text parser; auth-missing errors point to `mimo providers` (same OAuth lane as Cline).
- `Applications/sifta_talk_to_alice_widget.py` — `mimo:` added to teacher-CLI timeout family (120s default, `SIFTA_TEACHER_CLI_TIMEOUT_S` override).
- `System/swarm_cline_settings_probe.py` — mimocode XDG paths (`~/.local/share/mimocode/auth.json`) + session_diff fallback for upstream probe.

### VERIFY

- `pytest tests/test_external_brain_lanes.py tests/test_mimo_cli_transport.py tests/test_talk_cloud_timeout_caps.py` — **14 passed**.
- Live probe: `mimo run --format json` returned `MIMO_PING_OK` in ~9s on this node.

### RECEIPT

**Files touched:** `System/swarm_gemini_brain.py`, `Applications/sifta_talk_to_alice_widget.py`, `System/swarm_cline_settings_probe.py`, `tests/test_external_brain_lanes.py`, `tests/test_mimo_cli_transport.py`, `tests/test_talk_cloud_timeout_caps.py`, tournament carrier.

**WHAT IS LEFT after r1096:**

- **George** — `/cortex` select `mimo:mimo-cli-default`, send a short Talk turn; expect reply in seconds, not a 77s+ heartbeat stall. If auth error, run `mimo providers` once on M5 (same as Cline sign-in).
- **George** — IID email reply is yours to send; no code path needed.
- Run `python3 tools/whats_left.py` after each append.

ONE ALICE. ONE SWARM. For the Swarm. 🐜⚡
