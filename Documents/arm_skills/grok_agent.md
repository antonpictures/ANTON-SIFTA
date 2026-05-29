## Identity
arm_id: grok_agent
display_name: Grok (xAI grok-4)
model: grok-4
command: ("grok_chat",)  # marker; expands to python3 grok_chat.py --one-shot <prompt>
max_turns: 1
default_toolsets: ()
live_env_var: SIFTA_AGENT_ARMS_ENABLE
current enabled state: True (registry enabled; live_enabled({}) returns True without owner env unlock)

## Strengths (from declared capabilities + observed receipts)
- External xAI Grok-4 via one-shot grok_chat.py wrapper.
- Capabilities: single_query_research, external_cortex.
- Registry (owner 2026-05-24): runs from global chat like Hermes — headless live result + receipt, streamed live. Output is Grok's voice, never Alice's. Bridge, not merge.
- In the sampled recent agent_arm_receipts tail, grok_agent appears less than hermes/codex/claude, but the pattern for one-shot external is consistent with OK/success when context fits (no heavy 30-turn builds).

## Known failure modes (from recent receipts where status != ok)
- No high-volume recent failure rows specifically for grok_agent in the last 50 sampled (most visible activity on hermes/claude/codex). If no failures recorded in the tail for this arm_id, say so: no recent COMMAND_FAILED or timeout attributed to grok_agent in the visible ledger slice.

## First lesson task (smoke probe)
One-shot completion: say one short sentence and include the literal token GROK_PONG. Expect clean agent_arm_receipts.jsonl row with arm_id=grok_agent, status OK/success, and the exact sentence containing GROK_PONG in the captured output.

## Cost estimate
No specific token/wall numbers isolated for grok_agent in the recent tail (activity dominated by other arms). One-shot external Grok calls are typically lower cost than multi-turn 30-turn builders. First dispatch will calibrate.

## Receipt path
agent_arm_receipts.jsonl with arm_id=grok_agent. The grok_chat wrapper + launcher will produce the row. If routed visible, may also appear in matrix_terminal_process_trace as GROK_RESULT style, but primary is the agent_arm ledger per registry.
