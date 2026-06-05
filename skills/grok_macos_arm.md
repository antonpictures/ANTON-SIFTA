---
name: grok_macos_arm
description: >
  Use when Alice needs the external macOS Grok reserve or diagnostic witness
  as a bounded, cross-checked arm with explicit receipt boundaries.
swimmer_type: GROK_RESERVE_SWIMMER
action_type: diagnose
affect_lanes: [SEEKING, CARE]
stgm_mint: 2.0
pouw_label: GROK_MACOS_ARM
version: 2026-06-05
---

# Grok macOS Arm (Reserve / Diagnostic)

## Name
`grok_macos_arm`

## Entrypoint
External reserve/diagnostic hop operated outside the SIFTA-owned PTY surface.

## Payload Schema
- `routing_prompt`: strict shape prompt for external Grok
- `diagnostic_scope`: expected evidence to verify (hashes, spans, receipts)

## Receipt Schema
- External output text relayed by operator
- Cross-check against `.sifta_state/*` traces

## Role
Reserve/diagnostic witness only. Not a local direct effector for SIFTA file mutation.

## Example Call
`Use Grok macOS arm as a second witness to validate whether dispatch text drifted before Alice paste.`
