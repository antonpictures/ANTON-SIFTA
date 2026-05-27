# Grok PTY Arm

## Name
`grok_pty_arm`

## Entrypoint
`Applications/sifta_talk_to_alice_widget.py` via `TalkToAliceWidget._bring_up_grok_in_global_chat(...)`

## Payload Schema
- `user_text`: owner operational instruction
- `delegate`: bool, whether to paste a shaped prompt into Grok

## Receipt Schema
- `delegation_intent_<id>` (queue/dispatch receipt)
- `matrix_terminal_process_trace.jsonl` rows
- `GROK_RESULT` capture rows with hash/span

## Example Call
`Alice, dispatch Grok in the matrix-terminal PTY to run the focused coding task and print receipts.`
