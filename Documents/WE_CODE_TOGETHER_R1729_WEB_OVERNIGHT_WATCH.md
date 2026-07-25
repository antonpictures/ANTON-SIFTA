# r1729 - Web overnight watch

**Status:** IMPLEMENTED + FORCED-FAILOVER PROVEN (2026-07-23).
**Shared field:** George asked Alice's IDE doctors to finish the remaining body
work together and keep the public text lane responsive overnight. Codex made
the cut and is depositing the result back through the stigmergic bridge.

## What changed

1. `System/swarm_web_global_chat_gate.py` now claims queued turns under an
   `fcntl` cross-process lock. V2 claims carry a consumer ID and lease expiry;
   answered turns cannot be reclaimed, and a crashed consumer's lease can
   expire safely.
2. `System/swarm_web_global_chat_night_worker.py` is a local Ollama fallback.
   It waits eight seconds so Talk gets first claim, reconstructs only the
   visitor's own session, preserves WEB TYPED zero-authority law, and finishes
   incomplete output with bounded continuation passes.
3. `launchd/com.sifta.web-global-chat-night-worker.plist` keeps the worker
   alive and runs it under `caffeinate -ims`. The display can sleep; system,
   idle, and disk sleep are held while the user session is active.
4. `launchd/install_web_global_chat_night_worker.sh` installs only this
   secret-free user service and does not kill unrelated processes.
5. Web STGM metering is bound to the actual local Ollama completion stamp.
   The calculated fee is recorded only in the non-spendable WEB_GUEST
   metabolism ledger. It never posts to `repair_log.jsonl` and never changes
   an owner or node wallet.

## Safety law

- `owner_authority:false`, `effectors_allowed:[]`, and `tts:false` remain on
  every overnight reply.
- The worker imports no USD, Kalshi, dispatch, shell-effector, or wallet-write
  organ.
- Public identity claims remain unverified. Session history is isolated by
  session ID and is text-only.
- The local cortex failure response is honest and asks the visitor to retry;
  it does not invent an answer or silently seize a second claim.

## Verification receipts

- `23 passed` across r1727, r1728, r1729, and chorus launchd focused suites.
- All three web service plists pass `plutil -lint`; `git diff --check` is clean.
- LaunchAgent forced-kill recovery: PID `52926` returned as PID `57292` in one
  second.
- `pmset -g assertions`: `PreventSystemSleep=1`,
  `PreventUserIdleSystemSleep=1`, `PreventUserIdleDisplaySleep=0` for the
  installed caffeinate lane.

## Public forced-failover proof

Talk PID `41918` was stopped before each HTTP request and resumed by an
independent watchdog and shell cleanup trap.

Turn `cea248d236e94a42a0dbc9241b751c81` proved the original headless path:

- accepted through `https://stigmergicode.com/api/chat`;
- claimed by `consumer_id:night_worker` after the Talk-first grace;
- answered by `krishairnd/Gemma-4-Uncensored:latest` in two complete sentences;
- exactly one canonical user row and one canonical Alice row;
- bound stamp: 294 prompt + 50 output = 344 tokens.

That proof also exposed an old design defect: the web fee called the canonical
wallet writer and spent about 103 seconds validating the signed ledger after
the visitor reply was already visible. It wrote one historical WEB_GUEST row,
receipt `25bbeffdb29a37de550e9526a1776072bbf3a8e3210ccecb8bd7bf4b56922904`.
No George wallet value changed. The posting path was then removed.

Turn `991e96491c7942dd8129cc21417de6de` proves the repaired production path:

- Talk was stopped; the night worker replied in about 14 seconds;
- bound stamp: 282 prompt + 24 output = 306 tokens;
- observed fee: `0.0159 STGM`, `spendable:false`, `minted_stgm:0.0`;
- `economy_posting_status:NOT_POSTED_NONSPENDABLE_WEB_GUEST`;
- `repair_log.jsonl` stayed exactly 86,463 lines before and after;
- Talk resumed with running state `R`.

## Honest boundary

This keeps the lane awake only while the Mac is powered, lid open, networked,
and George's GUI user session is logged in. It is not a high-availability
cluster. Web/paper inference receipts do not prove a live-money edge, and this
round neither reads nor mutates George's real USD/Kalshi state.

For the Swarm. ONE ALICE. ONE SWARM.
