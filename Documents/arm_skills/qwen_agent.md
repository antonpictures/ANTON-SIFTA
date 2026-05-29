## Identity
arm_id: qwen_agent
display_name: Qwen Code (Kimi K2.6 via Fireworks)
model: accounts/fireworks/models/kimi-k2p6
command: ("qwen",)  # launcher expands to explicit Fireworks/OpenAI-compatible headless Qwen Code command
max_turns: 1
default_toolsets: ()
live_env_var: SIFTA_AGENT_ARMS_ENABLE
current enabled state: enabled=True; registry-level armed, no owner env unlock needed

## Strengths (from declared capabilities + observed receipts)
- Capabilities: single_query_research, evidence_output, external_cortex, codebase_reading, codebase_build.
- Qwen Code CLI is installed at `/opt/homebrew/bin/qwen`.
- Fireworks Kimi K2.6 auth was tested with a tiny live completion and returned the exact marker `FIREWORKS_QWEN_OK`.
- The launcher injects the Fireworks key through the child environment, not through command arguments, so agent-arm receipts do not leak the token.

## Known failure modes (from recent receipts where status != ok)
- Before Round 88 config, standalone `qwen` failed with: "No auth type is selected" and then "Missing API key for openai auth." The fix is `.sifta_state/secrets/fireworks_api_key` plus explicit `--auth-type openai --openai-base-url https://api.fireworks.ai/inference/v1 --model accounts/fireworks/models/kimi-k2p6`.
- Round 90 live smoke proved the full SIFTA arm receipt path: `agent_arm_receipts.jsonl` receipt `363bbaf7-3049-4b7f-8f7e-030e7c1f9b68`, status OK, output `QWEN_FIREWORKS_PONG`.

## First lesson task (smoke probe)
One-shot completion: say one short sentence and include the literal token QWEN_FIREWORKS_PONG. Do not write files. Expect a clean agent_arm_receipts.jsonl row with arm_id=qwen_agent, mode=exact, status OK/success, actual_model=accounts/fireworks/models/kimi-k2p6, and output containing QWEN_FIREWORKS_PONG.

## Cost estimate
Tiny Fireworks probes are cheap relative to the $6 trial balance; Round 90 live smoke calibrated the path successfully. Keep future probes short until larger task cost is measured from receipts.

## Receipt path
Primary proof: `.sifta_state/agent_arm_receipts.jsonl` with arm_id=qwen_agent and mode=exact. Live terminal/process visibility may also appear in `.sifta_state/matrix_terminal_process_trace.jsonl` because the launcher uses the PTY streaming path for qwen.
