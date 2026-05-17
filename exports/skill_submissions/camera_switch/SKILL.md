---
action_type: "execute"
affect_lanes: [SEEKING, CARE]
description: "Use when George asks Alice to switch camera, choose the next eye, use the MacBook camera, use the USB/Logitech camera, change acuity, or report the current active eye. This is a CLI-connected sensor/effector skill: the turn should route to the camera command path and then verify the saccade receipt."
homeworld_serial: "GTH4921YP3"
name: "camera_switch"
pouw_label: "CAMERA_SWITCH"
skill_sha256: "1323c7c3ad0d505832e3eca8c165e12c1651af00fc2e559a92ad94d1a2db5cae"
source_path: "skills/camera_switch/SKILL.md"
stgm_mint: 8.0
submission_schema: "SIFTA_SKILL_SUBMISSION_V1"
swimmer_type: "SENSOR_GATE"
trace_id: "15f05940-ac68-4300-947b-2d8e076f8cf5"
truth_label: "SIFTA_HARDWARE_BOUND_SKILL"
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
