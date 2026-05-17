---
name: whatsapp_macos_cli
description: >
  Use when George asks Alice to send a WhatsApp message from this Mac.
  Trigger: explicit owner instruction with target contact/group and message body.
swimmer_type: MESSENGER_EFFECTOR
action_type: social_send
affect_lanes: [CARE, SEEKING]
stgm_mint: 8.0
pouw_label: WHATSAPP_MACOS_CLI
version: 2026-05-07
---

# WHATSAPP_MACOS_CLI Skill

## What this swimmer does

This swimmer sends WhatsApp messages through the installed macOS
`/Applications/WhatsApp.app`, using the same app surface George uses.
It does not require the optional bridge contact cache before trying a visible
contact or group name.

## Trigger conditions

- George explicitly says to send a WhatsApp message.
- The utterance contains a target and message body, or a pending draft exists
  and George says `Execute`, `send it`, or equivalent.
- The action is not a group send unless the utterance clearly names a group.

## Procedure

1. Extract `(target, message)` with `System.swarm_alice_invariants.extract_whatsapp_intent`.
2. Execute:
   ```bash
   python3 -m System.swarm_macos_messenger send --via whatsapp --to "<target>" --msg "<message>"
   ```
3. Read the printed result and the append-only receipt in
   `.sifta_state/macos_messenger_sends.jsonl`.
4. Claim success only when the receipt has `ok=true` and `status=SENT`.
5. If execution fails, say the exact status and preserve a pending draft.

## Quality gate

- No "message Alice first" or bridge-registration instruction for outbound
  owner commands.
- No success claim without a receipt.
- The receipt proves local WhatsApp.app UI dispatch, not remote read state.
