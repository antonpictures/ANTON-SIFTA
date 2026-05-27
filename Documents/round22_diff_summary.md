# Round22 Diff Summary

## Objective

Direct-type Grok dispatch timed out on startup menu because the flow launched bare `grok` and never dismissed New/Resume/Quit when resume-navigation was disabled.

## Changes

### `/Users/ioanganton/Music/ANTON_SIFTA/Applications/sifta_matrix_terminal.py`

- Added `MatrixTerminalPane._send_ctrl_w_for_new_worktree()`:
  - sends `\x17` (Ctrl-W) to the PTY
  - writes trace action `grok_direct_type_new_worktree_keystroke`
- Updated direct-type launch sequence in `_execute_alice_cli_prompt_request(...)`:
  - `250ms`: spawn `grok`
  - `600ms`: send Ctrl-W (new worktree / new session)
  - `900ms`: start ready-gate polling (`_schedule_grok_direct_type_paste`)
- This preserves no-resume doctrine while ensuring menu dismissal.

## Tests

### New file

- `/Users/ioanganton/Music/ANTON_SIFTA/tests/test_grok_new_worktree_keystroke.py`
  - asserts Ctrl-W byte is sent
  - asserts trace action is emitted
  - asserts sequence is spawn → Ctrl-W → ready-gate

### Regression run

- `/Users/ioanganton/Music/ANTON_SIFTA/tests/test_grok_direct_type_ready_gate.py`
- `/Users/ioanganton/Music/ANTON_SIFTA/tests/test_grok_new_worktree_keystroke.py`

Both pass in focused run.
