# SIFTA vs. AutoGen

When mapping SIFTA against Microsoft's AutoGen framework, the distinction lies entirely in **substrate vs. simulation**. 

## The AutoGen Model
AutoGen is a multi-agent conversation framework. It creates a simulated "room" where multiple LLM wrappers pass text messages back and forth to solve a task. 
- **Substrate**: Ephemeral python runtime + API calls.
- **Coordination**: Message passing (Chat).
- **Embodiment**: None. The agents vanish when the python script exits.
- **Identity**: Prompt-based ("You are a coder", "You are a reviewer").

## The SIFTA Model
SIFTA is a local, stigmergic operating system. Agents do not "chat" to coordinate core biology; they read and write to an append-only physical ledger on the hard drive.
- **Substrate**: Local macOS APFS, RAM, physical sensors, `system_profiler` serial numbers.
- **Coordination**: Stigmergy. Agents read the environment (ledgers, traces) and modify it.
- **Embodiment**: Hardware-anchored. The desktop shell (`sifta_os_desktop.py`) is the continuous organism. Senses (camera, GPS) are open at boot.
- **Identity**: Receipt-based. Identity is constructed from hardware telemetry, real schedules, and signed work receipts, not persona prompts.

**Summary**: AutoGen is a group chat for APIs. SIFTA is a biology simulation anchored to physical silicon.

## Skill Submission Lane

SIFTA skills are portable only after they carry node provenance. The community package path is:

```bash
PYTHONPATH=. python3 -m System.swarm_skill_submission_packager
```

That produces `exports/skill_submissions/<skill>/SKILL.md` plus `skill_trade_offer_v1.json`. Each package is validated for:

- `homeworld_serial`
- `trace_id`
- `swimmer_type`
- `truth_label`
- `skill_sha256`

Current package receipt on 2026-05-05: 8 skills exported, 8 validated, 0 validation errors. The submission receipt is written to `.sifta_state/skill_submission_receipts.jsonl`.
