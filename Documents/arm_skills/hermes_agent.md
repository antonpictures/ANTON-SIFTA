## Identity
arm_id: hermes_agent
display_name: Hermes Agent
model: alice-m5-cortex-8b-6.3gb:latest
command: ("hermes", "chat", "-Q")
max_turns: 30
default_toolsets: ("file", "terminal", "code_execution")
live_env_var: SIFTA_AGENT_ARMS_ENABLE
current enabled state: True (registry enabled; live_enabled({}) returns True without owner env unlock)

## Strengths (from declared capabilities + observed receipts)
- Builder-capable: file + terminal + code_execution toolsets, multi-turn (up to 30).
- Declared capabilities: single_query_research, codebase_build.
- Registry notes (2026-05-24/25): uncaged from prior "clarify/1-turn" cage; now non-interactive --yolo style; owner standing always-allow for workspace writes; verifier + git diff as audit.

## Known failure modes (from recent receipts where status != ok)
- Recent hermes launch (receipt fd00d70d-4dcb-4969-886e-3179c7f73971, ~2026-05-27): COMMAND_FAILED. "Ollama loaded `alice-m5-cortex-8b-6.3gb:latest` with only 8,192 tokens of runtime context, but Hermes needs at least 64,000 tokens for reliable tool use."
- Context starvation kills tool use even when registry declares the toolsets.
- Earlier patterns in tail: stalled or timeout when context exhausted mid-build.

## First lesson task (smoke probe)
Write a file Documents/arm_skills/hermes_pong.txt containing one line 'pong from hermes at <utc iso>' and stop. Use the file toolset. Expect clean agent_arm_receipts.jsonl row with arm_id=hermes_agent, status=OK/success, plus the file on disk with the exact line.

## Cost estimate
Recent observed: context error aborts before full tool loop (no full token count in failure receipt). Prior successful live passes on other arms show 25 input / 41k output in one claude parallel run, but hermes-specific hot data not in last 50 rows for successful long runs. First dispatch will calibrate. Expect high on 8b local if context not raised.

## Receipt path
agent_arm_receipts.jsonl with arm_id=hermes_agent (plus any matrix_terminal_process_trace if routed through PTY). Look for truth_label containing AGENT_ARM_LAUNCH_RESULT, status OK/success, and the file write artifact.
