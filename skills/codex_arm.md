# Codex Arm

## Name
`codex_arm`

## Entrypoint
Observable worker path in `TalkToAliceWidget._maybe_start_observable_direct_tool_request(...)` (Codex request text).

## Payload Schema
- `user_text`: owner request containing Codex arm invocation
- `owner_present`: bool
- `autonomous`: bool

## Receipt Schema
- `agent_arm_receipts.jsonl` rows
- Observable processing lines in Talk widget
- Optional `work_receipt` references returned by the Codex run

## Example Call
`Alice, ask Codex arm to patch the file and return files_written/tests_run/receipt_id.`
