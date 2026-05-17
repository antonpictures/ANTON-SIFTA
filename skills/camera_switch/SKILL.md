---
name: camera_switch
description: >
  Use when George asks Alice to switch camera, choose the next eye, use the
  MacBook camera, use the USB/Logitech camera, change acuity, or report the
  current active eye. This is a CLI-connected sensor/effector skill: the turn
  should route to the camera command path and then verify the saccade receipt.
swimmer_type: SENSOR_GATE
action_type: execute
affect_lanes: [SEEKING, CARE]
stgm_mint: 8.0
pouw_label: CAMERA_SWITCH
version: 1
---
# Camera Switch

## Purpose

Route natural language camera commands to Alice's eye effector without letting the language model merely claim success.

## Trigger Examples

- "Alice, switch camera."
- "Switch to the next camera."
- "Use the front camera."
- "Use the MacBook camera."
- "Use the side camera."
- "Use the Logitech camera."
- "Increase camera resolution one step."

## Procedure

1. Classify the command as an eye command only when the utterance contains a camera/eye/view/acuity term plus an action term such as switch, next, front, side, MacBook, Logitech, USB, or resolution.
2. Write the intended command to the camera command ledger.
3. Execute through the deterministic camera effector path, not through a conversational promise.
4. Verify `active_saccade_target.json` changed or a camera hardware probe row confirms the requested active eye.
5. Answer from the receipt. If the receipt changed, a short answer is enough: "Switched." If no receipt changed, say the switch was not confirmed and name the missing receipt.

## Receipts

- `.sifta_state/owner_camera_commands.jsonl`
- `.sifta_state/active_saccade_target.json`
- `.sifta_state/camera_hardware_probe.jsonl`

## Guard

Never say the camera switched without a fresh effector receipt.
