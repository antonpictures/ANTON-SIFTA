## Identity
arm_id: cline_agent
display_name: Cline (open-source coding agent, Apache 2.0)
model: cline-cli-default
command: ("cline",)  # launcher expands to headless JSON mode
max_turns: 1
default_toolsets: ()
live_env_var: SIFTA_AGENT_ARMS_ENABLE
current enabled state: enabled=True; registry-level armed, no owner env unlock needed

## Strengths (from declared capabilities + observed receipts)
- Capabilities: single_query_research, evidence_output, external_cortex, codebase_reading, codebase_build, shell_execution, multi_agent_team.
- Cline CLI is installed at `/opt/homebrew/bin/cline`.
- `cline --help` confirms headless JSON mode, `--cwd`, `--provider`, `--model`, `--auto-approve`, and timeout flags are available.
- George reports Cline is currently signed into an OpenAI/Codex-model account; SIFTA does not store that provider secret.

## Known failure modes (from recent receipts where status != ok)
- No completed cline_agent agent_arm_receipts row is known in this brief yet; first SIFTA dispatch will calibrate auth/model behavior.
- Provider/model is owned by Cline's own config (`~/.cline/...`) and may not match the registry label until a live receipt reports the real model.

## First lesson task (smoke probe)
One-shot completion: say one short sentence and include the literal token CLINE_PONG. Do not write files. Expect a clean agent_arm_receipts.jsonl row with arm_id=cline_agent, mode=exact, status OK/success, and output containing CLINE_PONG.

## Cost estimate
No observed cost from SIFTA receipts yet. First dispatch will calibrate wall seconds, provider, model, and any billable token cost from Cline's configured backend.

## Receipt path
Primary proof: `.sifta_state/agent_arm_receipts.jsonl` with arm_id=cline_agent and mode=exact. Live terminal/process visibility may also appear in `.sifta_state/matrix_terminal_process_trace.jsonl` because the launcher uses the PTY streaming path for cline.
