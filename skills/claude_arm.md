# Claude Arm

## Name
`claude_arm`

## Entrypoint
Observable worker path in `TalkToAliceWidget._maybe_start_observable_direct_tool_request(...)` (Claude request text).

## Payload Schema
- `user_text`: owner request containing Claude arm invocation
- `owner_present`: bool
- `autonomous`: bool

## Receipt Schema
- `agent_arm_receipts.jsonl` rows
- Observable processing stream entries
- Tool-router status rows

## Example Call
`Alice, ask Claude arm for a focused implementation prompt with explicit failure contracts.`
