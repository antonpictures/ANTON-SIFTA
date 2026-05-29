---
name: design_system_contract
description: >
  Tier-1 posture skill. When any arm is dispatched to touch UI, frontend,
  Qt widgets, themes, or visual surfaces, this contract is loaded.
  It enforces the Round 88 OLED doctrine as the single source of truth:
  true OLED black (#000000), single cyan-green accent (#00d4aa),
  hairline borders, generous spacing, no chrome, monochrome restful
  defaults, accent only on meaningful interaction.
  The arm must not invent its own "pretty" design language.
swimmer_type: POSTURE
action_type: ui
affect_lanes: [SEEKING, CARE]
stgm_mint: 2.0
pouw_label: DESIGN_CONTRACT
version: 2026-05-27
tier: 1
author: Grok 4.3 PTY arm (SIFTA Grok) — research append from Antigravity 2.0 + Round 88 OLED doctrine
license: MIT
compatibility: SIFTA covenant v4, sifta_talk_to_alice_widget.py, any UI organ
---
# DESIGN_SYSTEM_CONTRACT Posture Skill

## What this skill IS

This is the living embodiment of Round 88 (SIFTA Global Chat: OLED Black +
Single Cyan-Green Accent). It turns the visual system from "the arm
tried to make it nice" into "the arm respected the one body it serves."

It is not a suggestion. It is a contract. Any code that touches Qt
stylesheets, palettes, borders, spacing, or widget appearance while
this posture is loaded must derive from the Round 88 tokens or
explicitly extend them in a way that preserves the OLED discipline.

## Round 88 Tokens (single source of truth)

- Backgrounds: `#000000` (true OLED black), `#1f1f1f` (subtle raised)
- Accent: `#00d4aa` (cyan-green) — used sparingly for focus, active
  state, meaningful highlights only.
- Text: `#e8e8e8` (primary), `#a0a0a0` (secondary/dimmed)
- Borders: 1px hairline in `#2a2a2a` or accent at 30% opacity
- No gradients, no heavy shadows, no "modern" glassmorphism, no
  vendor-chrome defaults.
- Spacing: generous (12-16px minimum between interactive elements)
- Mono for all technical/readout surfaces (process trace, terminal,
  logs).

These tokens are already partially wired in
`Applications/sifta_talk_to_alice_widget.py` (around lines 13633+).
This skill makes the doctrine loadable and enforceable by any arm.

## Rules when this posture is active

1. **Read the existing Round 88 implementation first.**
   - Before writing any new stylesheet or palette, tail the widget
     comments and the actual `_apply_oled_theme` / style blocks.
   - Do not duplicate or contradict what already exists.

2. **Accent is a signal, not decoration.**
   - `#00d4aa` appears on focus, active tab, important state change,
     or verified receipt success.
   - It does not appear on every button, every border, or as "pretty
     color."

3. **OLED black is non-negotiable on this hardware.**
   - George runs on M5 with OLED-capable display. Wasting power and
     contrast on gray or "dark gray" backgrounds is a metabolic
     violation.

4. **Every new UI surface or widget must declare its palette source.**
   - In the code or in the receipt: "Round 88 OLED contract applied"
     or "extended Round 88 token X because Y (receipt #Z)".

5. **No surprise visual languages.**
   - If the task is "make this panel look good," the answer is
     "apply the existing contract." If the contract is insufficient,
     the arm must first propose an extension to the tokens (with
     George review) rather than inventing locally.

## Integration with other skills

- Often loaded together with `king_build_mode.md` when the goal
  involves UI organs.
- The `ide_boot_covenant` tier-0 skill still governs registration
  and first-person discipline.
- When the arm finishes UI work, the final receipt must include
  a visual verification note (screenshot path or "George confirmed
  on device").

## SIFTA advantage

External "Frontend Design Skill" is a prompt that a cloud agent
sometimes follows. This version is:
- A versioned, STGM-earning, loadable contract
- Tied to an actual prior round that George approved on this node
- Enforceable by the same Predator Gate + verification chain that
  governs all other surgery

## Receipt note (example)

"design_system_contract loaded. All new Qt styles derived from
Round 88 OLED tokens (#000000 / #00d4aa / hairline). No new
visual language invented. George will see the same black + single
accent he chose."

**For the Swarm. 🐜⚡**

*Created by SIFTA Grok PTY arm 2026-05-27 as the first operational
delivery from the Antigravity pattern analysis (Round 94 research →
Round 95 code).*
