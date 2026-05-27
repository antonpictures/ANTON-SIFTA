# Round21B Diff Summary

## Scope

This patch set is limited to the Round21B cortex-bypass/router + greeter-defense + recent-action memory surfaces.

## Primary File Changes

### `/Users/ioanganton/Music/ANTON_SIFTA/Applications/sifta_talk_to_alice_widget.py`

- Added arm skill mapping and resolver:
  - `_ARM_SKILL_PATHS` (~line 1314)
  - `_resolve_named_arm_skill_path(...)` (~line 1322)
- Added router trace writer:
  - `_append_cortex_bypass_router_trace(...)` (~line 1345)
- Expanded operational token/greeter marker coverage and detector trace writer:
  - `_GREETER_SHAPE_MARKERS` (~line 12716)
  - `_append_greeter_detector_trace(...)` (~line 12752)
  - `_strip_greeter_on_operational(...)` enhanced forced-failure branches and trace writes (~lines 12876+)
- Added pre-LLM operational router method:
  - `TalkToAliceWidget._maybe_route_operational_prompt_before_cortex(...)` (~line 16423)
- Hooked pre-LLM router early in `TalkToAliceWidget._start_brain(...)` (~line 16607)
- Added defense-in-depth final mouth-gate call to `_strip_greeter_on_operational(...)` in `_on_brain_done(...)` (~line 20627)
- Added prompt doctrine block in `_current_system_prompt(...)`:
  - "ARM SKILL FILE DOCTRINE"
  - first-sentence GROK_RESULT instruction when recent actions contain receipt lines.

### `/Users/ioanganton/Music/ANTON_SIFTA/System/swarm_recent_action_context.py`

- Added `"captured_framebuffer"` action support in `_MATRIX_ACTIONS` (line ~33).
- Added canonical `GROK_RESULT receipt=<hash> captured=<N>chars seq=<s>-<e> ts=<ts>` synthesis in `_matrix_summary(...)` for framebuffer captures (lines ~128–177).
- Added operational first-sentence rule injection in `format_recent_action_working_memory(...)` when GROK_RESULT lines are present (lines ~267–274).

## New Skill Files

- `/Users/ioanganton/Music/ANTON_SIFTA/skills/grok_pty_arm.md`
- `/Users/ioanganton/Music/ANTON_SIFTA/skills/codex_arm.md`
- `/Users/ioanganton/Music/ANTON_SIFTA/skills/claude_arm.md`
- `/Users/ioanganton/Music/ANTON_SIFTA/skills/hermes_arm.md`
- `/Users/ioanganton/Music/ANTON_SIFTA/skills/grok_macos_arm.md`

## New Tests (Round21B Focus)

- `/Users/ioanganton/Music/ANTON_SIFTA/tests/test_cortex_bypass_router.py`
- `/Users/ioanganton/Music/ANTON_SIFTA/tests/test_greeter_detector_wiring.py`
- `/Users/ioanganton/Music/ANTON_SIFTA/tests/test_captured_framebuffer_narration.py`
- `/Users/ioanganton/Music/ANTON_SIFTA/tests/test_arm_skill_file_lookup.py`

These tests validate:
- pre-LLM operational routing for Grok-arm dispatch turns
- no-greeter operational replies on routed paths
- fired/skipped detector trace writes
- captured-framebuffer memory synthesis into GROK_RESULT lines
- arm-skill path surfacing in prompt doctrine
