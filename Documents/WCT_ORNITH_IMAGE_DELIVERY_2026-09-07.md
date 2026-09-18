# Ornith: finish image delivery in We Code Together

Status: QUEUED; image delivery end-to-end remains unverified.
Assigned coding arm: ornith-1.5:9b. Requested by George through Codex.

We Code Together is Alice's internal shared coding monitor:
`Applications/sifta_we_code_together.py`. It displays the task backlog,
owner corrections, and work receipts. It is distinct from the DeepSeek
Harness coding interface inside Alice Browser. Read this task there and
report observed results back to the same monitor; queueing is not execution.

## Bounded task

1. Read the current diff and actual functions before editing. Use only code
   you observe; do not assume nonexistent functions from previous reports.
2. Audit message rendering in `System/chorus_node_server.py`:
   - If add() increments viewEpoch, check whether that invalidates legitimate
     history/poll requests. Keep navigation invalidation separate from rendering.
   - Every message-key insertion must maintain its node reference. A missing
     node must not throw or silently discard an arriving image.
   - location.origin is browser JavaScript. Resolve local Python chat image
     links through Alice's configured web address, not an undefined variable.
3. Read the installed Kimi WebBridge instructions. Open the actual Alice web
   page using that bridge. Reuse the existing server on port 8100 if confirmed
   by current configuration. Verify it serves updated code; restart only that
   service if needed. Leave DeepSeek Harness on port 3080 unchanged.
4. Confirm Bonsai backend readiness, then send one fresh test request:
   /create a blue ceramic fish beside a yellow vase
5. Verify actual behavior:
   - Preview loads with nonzero naturalWidth.
   - Download is a valid image matching the generated-image receipt SHA256.
   - Refresh preserves the image; repeated polls do not duplicate its message.
   - Local chat link opens the same image.
   - A different visitor session cannot retrieve the image.
   - The new reply retains #SIFTA and omits the unwanted disclaimer.
6. Fix only failures in this delivery path with focused apply_patch edits.
   Preserve unrelated work and historical receipts. Do not regenerate the
   image unnecessarily. Do not implement artistic reasoning yet.
7. Run relevant checks. Report PASS/FAIL per criterion, changed files, and
   exact blockers into We Code Together's existing work/monitor receipt paths.
   Keep session tokens and private image URLs out of the report. Do not replace
   browser evidence with syntax checks or a 200 response from /api/history.

## Monitor paths

- Task: `.sifta_state/we_code_together_to_be_coded.jsonl`
- Owner correction: `.sifta_state/we_code_together_owner_corrections.jsonl`
- Progress: `.sifta_state/we_code_together_monitor_pulse.jsonl`
- Work evidence: `.sifta_state/work_receipts.jsonl`
- Task ID: `wct-ornith-image-delivery-20260907`

Use existing append-only helpers and task identity to avoid duplicate entries.
Do not mark implementation completed or award STGM merely for writing a plan.
