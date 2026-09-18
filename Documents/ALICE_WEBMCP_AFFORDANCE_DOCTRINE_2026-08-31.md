# Alice WebMCP Affordance Doctrine

**Date:** 2026-08-31  
**Status:** implemented sensory lane; bounded execution lane

## Purpose

Alice must be able to enter an unfamiliar environment, perceive what is present,
discover what actions are possible, choose among safe candidates, act through an
authorized effector, observe the consequence, and retain a receipt. Web browsing
is the current training environment for that general loop. It is not proof that a
browser and a physical limb are equivalent.

## WebMCP connection

WebMCP lets a compatible page declare semantic tools with names, descriptions,
JSON input schemas, origins, and safety annotations. Alice now senses those tools
through both existing browser surfaces: Alice Browser probes meaningful page
awareness events, while WebBridge can probe the connected Chrome page. Both
normalize into the same environmental-affordance ledger. When WebMCP is
unavailable, the existing accessibility-tree snapshot remains the fallback.

No competing browser organ was created.

## Transferable loop

`environment -> sensory snapshot -> affordance discovery -> candidate actions -> valuation/arbitration -> owner and safety gate -> effector -> consequence -> receipt -> memory`

For a webpage, an affordance may be `search_catalogue(query)` or
`book_appointment(date)`. For a future physical body, an affordance may be
`grasp(handle)` or `move_joint(angle)`. The shared abstraction is the declared or
observed possibility of action, not the actuator itself.

## Hard boundary

- A discovered tool is perception, not permission.
- Page content and tool descriptions are untrusted environmental input.
- Every WebMCP execution spends a fresh owner-intent nonce through the existing
  browser effector gate.
- Sensitive and state-changing tools are marked for confirmation.
- No WebMCP tool may bypass safety, authority, purchase, or physical-effector gates.
- Physical limb control is not enabled by this change.
- WebMCP is experimental and may change; capability detection and accessibility
  fallback are mandatory.

## Evidence

- Implementation: `System/swarm_kimi_webbridge_bridge.py`
- Internal browser wiring: `Applications/sifta_alice_browser_widget.py`
- Tests: `tests/test_swarm_webmcp_affordances.py`
- Discovery ledger: `.sifta_state/alice_webmcp_affordances.jsonl`
- Latest sensed affordances: `.sifta_state/alice_webmcp_affordances_latest.json`

This is a bounded step toward environment-independent adaptation: Alice can learn
to ask, "What can be done here?" without confusing that answer with, "What am I
authorized to do?"
