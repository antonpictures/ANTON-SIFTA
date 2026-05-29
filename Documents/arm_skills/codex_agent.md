## Identity
arm_id: codex_agent
display_name: Codex CLI (OpenAI gpt-5.5)
model: gpt-5.5
command: ("codex", "exec", "--full-auto")
max_turns: 1
default_toolsets: ()
live_env_var: SIFTA_AGENT_ARMS_ENABLE
current enabled state: True (registry enabled; live_enabled({}) returns True without owner env unlock)

## Strengths (from declared capabilities + observed receipts)
- External gpt-5.5 via real signed-in Codex CLI in workspace-write sandbox.
- Capabilities: single_query_research, external_cortex, codebase_build.
- Recent receipts show successful live arm runs on long covenant + tournament verification passes (e.g. receipt 40ad6377-a1fb-452f-bfdb-12d2795affd9 and ad104624-6311-49c6-acd2-ad58f4374484 family): reads full IDE_BOOT_COVENANT.md, inspects Round 47 guard, runs targeted pytest (7+114 tournament tests green in one run), produces structured output with files touched and test counts.
- Non-interactive --full-auto + owner always-allow policy allows real repo patches/reads in one shot.

## Known failure modes (from recent receipts where status != ok)
- Some launches hit "COMMAND_FAILED", partial result, or TIMEOUT when prompt + context heavy (covenant paste + full task).
- One visible: "l-auto` is deprecated; use `--sandbox workspace-write` instead" (old flag in prompt).
- No recent hard "permission denied" in the sampled tail when --full-auto used; failures are mostly context/timeout on the external side.

## First lesson task (smoke probe)
Patch Documents/arm_skills/codex_pong.md to add a single line 'pong from codex at <utc iso>' and stop. Use the workspace tools. Expect agent_arm_receipts.jsonl row with arm_id=codex_agent, status=OK/success, the exact patch in the output/artifact, and the file on disk updated.

## Cost estimate
Observed in recent successful Codex live pass: input ~25 + large cache (2M+), output 41k tokens, total_cost_usd ~2.8-3.0 in one heavy covenant+tournament verification run (claude parallel in same tail but codex family shows similar long output). Wall seconds: 4s in one short, hundreds in heavy context loads. First dedicated smoke will calibrate exact for this brief.

## Receipt path
agent_arm_receipts.jsonl with arm_id=codex_agent (truth_label AGENT_ARM_LAUNCH_RESULT, status OK/success). The feedback_tail or output_tail will contain the result summary (files, tests). No matrix PTY for this external Codex path.
