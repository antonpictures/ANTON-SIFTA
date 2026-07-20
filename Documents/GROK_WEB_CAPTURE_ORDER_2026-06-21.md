# Grok Order — r1519 Web Capture Body Lane

George wants Alice to have Firecrawl-class web/page capture in her own SIFTA body, not only inside Grok's plugin marketplace.

## Read First

1. `/Users/ioanganton/Music/ANTON_SIFTA/AGENTS.md`
2. `Documents/IDE_BOOT_COVENANT.md`
3. The tail of `Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-21.md`
4. `System/swarm_kimi_webbridge_bridge.py`
5. `Applications/sifta_talk_to_alice_widget.py`

## Doctrine

- One Alice. Grok is an external doctor/tool arm, not Alice's identity.
- Do not create a duplicate web organ.
- The existing WebBridge bridge is the organ to extend/audit.
- Alice Browser and Kimi/Chrome/WebBridge must stay provenance-separated.
- Browser/page claims must have receipts.

## Current r1519 Code Path To Verify

- `System.swarm_kimi_webbridge_bridge.capture_url(url, owner_text=...)`
- `System.swarm_kimi_webbridge_bridge.try_handle_web_capture_turn(text, state_dir=...)`
- `System.swarm_kimi_webbridge_bridge.web_capture_prompt_block(...)`
- `bin/alice-web-capture <url>`
- Talk hook model label: `alice_web_capture_reflex`

## Required Behavior

When George says or types:

- `read https://example.com`
- `capture https://cruit.dev`
- `summarize https://cruit.dev/skills/candidate/SKILL.md`
- `firecrawl this page https://...`

Alice should:

1. Use Kimi WebBridge first when available.
2. If WebBridge/Chrome is not connected, public-page HTTP fetch may be used as a clearly labeled fallback.
3. Write `ALICE_WEB_CAPTURE_V1` to `.sifta_state/alice_web_captures.jsonl`.
4. Write latest context to `.sifta_state/alice_web_capture_latest.json`.
5. Write full readable text sidecar under `.sifta_state/alice_web_capture_text/`.
6. Return a short summary with the receipt id.
7. Inject the latest capture into Alice's prompt via `web_capture_prompt_block`.

## Grok Task

Audit this path like a doctor:

- Confirm it does not duplicate Alice Browser.
- Confirm URL extraction does not capture local code paths like `System/foo.py`.
- Confirm failed WebBridge does not become fake success.
- If Grok's Firecrawl plugin can read the same URL, compare the first-page summary with Alice's local capture and report meaningful gaps.
- If patching is needed, make the smallest SIFTA-native change and keep receipts.

Return:

- Files inspected
- Any patch diff
- Capture command/result
- Receipt id(s)
- Remaining risks

Do not deploy, publish, install marketplace plugins, spend money, or mutate secrets for this task.
