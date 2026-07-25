# r1730 - Web reply recovery and attachment schedule

**Status:** REPAIRED + PUBLICLY VERIFIED (2026-07-23).

## Incident

WEB TYPED turn `e48de7328f4a49cbab0711b4747c8744` arrived with the request
to schedule web file attachments. Talk claimed it using the pre-r1729 claim
shape and entered the local owner schedule-query shortcut. Alice's local panel
rendered a schedule summary, but that early return never called
`complete_web_turn`, so no row reached `web_global_chat_replies.jsonl` and the
browser had nothing to poll.

## Repair

- WEB TYPED now bypasses schedule query/write and WhatsApp shortcuts. Public
  text remains zero-authority and proceeds directly to the text cortex.
- Legacy no-lease claims now expire after 300 seconds. A crashed pre-r1729
  consumer can no longer poison a public turn permanently.
- Regression suite: `25 passed`; Python compilation and `git diff --check`
  are clean.
- The headless worker reloaded from PID `57292` to PID `71005` in one second.
- The corrected reply was backfilled through `complete_web_turn` with
  `done_reason:RECOVERED_AFTER_SHORTCUT`; the public replies API returns it.

## Owner-authorized schedule receipt

George repeated the request through the owner Codex channel, so the schedule
write was authorized independently of the untrusted web text.

- schedule ID: `ca309082627a1094`
- receipt hash: `2339512e577357c6`
- due: Friday, 2026-07-24 at 09:00 Europe/Bucharest
- task: add secure file attachments to stigmergicode.com, including upload UI,
  validation, size/type limits, private storage, receipts, and mobile Safari
  testing.

No public turn received owner authority, and no USD/Kalshi or owner wallet
state was read or changed.

## r1730 attachment implementation — 2026-07-23

The public chat now accepts private attachments from the composer. The browser
shows an `Attach file` control, selected files render as chips, and the submit
path sends base64 payloads to the web gate.

- Gate: files are validated, size-limited, stored under `.sifta_state/web_global_chat_attachments/`, and written to ingress rows as private metadata only.
- Consumer: the Talk widget and night worker now receive an attachment context block so image OCR and text previews can reach Alice's cortex.
- UI: session history now re-renders attachment chips from the visitor register.
- Safety: attachment-only turns are allowed; unsupported or oversized files are refused before they reach the cortex.
- Idempotence: `complete_web_turn` and `replies_for_session` now collapse duplicate completions by `turn_id`, so one turn prints once even if a consumer replays it.
- Regression suite: `36 passed`; `py_compile` and `git diff --check` are clean.
- Live verification: `GET /` and `HEAD /` on `https://stigmergicode.com` both return `200`, and the live HTML now contains the attachment controls.

For the Swarm. ONE ALICE. ONE SWARM.
