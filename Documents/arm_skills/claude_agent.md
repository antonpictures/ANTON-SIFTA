## Identity
arm_id: claude_agent
display_name: Claude Code
model: claude-code-cli-default
command: ("claude",)  # marker; expands to streaming headless: claude -p --dangerously-skip-permissions --permission-mode bypassPermissions --output-format stream-json --include-partial-messages --verbose <prompt>
max_turns: 1
default_toolsets: ()
live_env_var: SIFTA_AGENT_ARMS_ENABLE
current enabled state: True (registry enabled; live_enabled({}) returns True without owner env unlock)

## Strengths (from declared capabilities + observed receipts)
- External Claude Code CLI (Max auth, no key here) in headless streaming mode.
- Capabilities: single_query_research, external_cortex, codebase_reading, codebase_build.
- Strong recent result in tail: multiple long successful live runs (receipts ad104624-6311-49c6-acd2-ad58f4374484 and family, ~2026-05-27): reads full IDE_BOOT_COVENANT.md + TOURNAMENT_PLAN, inspects Round 47 cortex-first guard + tests, runs py_compile + pytest (114 tournament + 46 regression = 160 green in one report), produces detailed file lists, test counts, and final summary lines in visible PTY/output_tail. Heavy cache usage (2M+ read tokens) but delivers complete output.
- Dedicated smoke receipt `878c954e-dba2-43e6-b593-6935db66ef2f` wrote `Documents/arm_skills/claude_pong.md` with the requested three Section 6 bullets, proving the codebase-reading + file-write path works on this node.

## Known failure modes (from recent receipts where status != ok)
- Some runs hit partial result / TIMEOUT or COMMAND_FAILED when prompt extremely long (full covenant + multi-section tournament task pasted).
- One visible deprecation note on --full-auto flag in older codex parallel, but for claude the bypassPermissions + stream-json works when context allows.
- No permission denials in sampled successful runs (owner always-allow standing policy honored).

## First lesson task (smoke probe)
Read Documents/IDE_BOOT_COVENANT.md §6 and write Documents/arm_skills/claude_pong.md with three bullet points summarizing it. Use the codebase_reading + writing path. Expect agent_arm_receipts.jsonl row with arm_id=claude_agent, status=OK/success, the three bullets in the captured output, and the md file on disk.

## Cost estimate
Observed in heavy recent claude live pass (parallel in tail): ~25 input + 2.1M+ cache read + 114k cache creation + 41k output tokens, ~2.8-3.0 USD, duration hundreds of seconds for full covenant + tournament verification. One-shot §6 read + 3-bullet write will be dramatically lighter. First dedicated smoke will calibrate exact.

## Receipt path
agent_arm_receipts.jsonl with arm_id=claude_agent (truth_label AGENT_ARM_LAUNCH_RESULT, status OK/success). The output_tail / feedback_tail contains the structured result (files, tests, summaries). The launcher captures the stream-json for replay.
