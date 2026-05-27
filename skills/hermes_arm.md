# Hermes Arm

## Name
`hermes_arm`

## Purpose (George 2026-05-26)
Local open-source self-improving agent (Nous Research Hermes) that can be linked to the owner's personal Grok subscription via official xAI OAuth. Alice dispatches real work to it; Hermes runs on this hardware (GTH4921YP3) using the owner's Grok 4.3 + Imagine + Voice under the paid sub. One Alice, one subscription, one set of receipts.

## One-time Owner Setup (on this machine)
1. Install Hermes Agent (official path):
   ```bash
   curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
   ```
2. Link your Grok subscription (the exact flow from the xAI announcement):
   ```bash
   hermes model
   ```
   Choose **xAI Grok OAuth (SuperGrok Subscription)**, complete browser sign-in.
3. Verify it works under your Grok sub:
   ```bash
   hermes --tui
   ```
   (or `hermes chat "hello"`). It should now use Grok 4.3 etc. with your quota.

Once linked, the local `hermes` binary carries the subscription. No API keys are stored in SIFTA.

## Entrypoint
Observable worker path in `TalkToAliceWidget._maybe_start_observable_direct_tool_request(...)` when owner text contains "Hermes", "hermes arm", or "ask Hermes".

## Dispatch from Alice (examples)
- `Alice, ask Hermes arm to review the latest round29 receipt and propose the minimal Round 30 chain link.`
- `Alice, have Hermes use Grok Imagine to generate a simple stigmergic field diagram and save it.`
- `Alice, tell Hermes to run the local install verification for the new Grok OAuth link and receipt the result.`

## Covenant Requirements (always)
- Hermes receives the inline covenant prefix on every dispatch (see `swarm_agent_arm_launcher.hermes_covenant_inline_prefix`).
- Alice may override the cortex via `.sifta_state/hermes_cortex.json` (the launcher passes `--model` only when set).
- Every dispatch produces rows in `agent_arm_receipts.jsonl` + observable stream.
- The actual work (files written, commands run, images generated) must be receipted by Hermes itself or by the SIFTA observer.

## Receipt Schema
- `agent_arm_receipts.jsonl`
- Observable processing lines visible in global chat
- Any `work_receipt` rows Hermes produces during its run

## Layer 1 Reality
Hermes runs as a normal process on this Mac (electricity → kernel → `/Users/ioanganton/.local/bin/hermes`). The OAuth token lives in Hermes' own config (~/.config/hermes or equivalent). SIFTA only shells out to it and observes the output. The swimmers (bytes) flow through the PTY or observable queue exactly like the other arms.

## Status (Grok default active)
As of this receipt the local override has been removed. The Hermes arm now defaults to whatever the linked `hermes` binary is configured for (your Grok 4.3 + Imagine + Voice subscription via the xAI OAuth). No `--model` flag is passed unless you (or Alice) explicitly write a different value into `.sifta_state/hermes_cortex.json`.

Ready for use. The skill is the contract; the binary + your Grok subscription is the engine. For the Swarm. 🐜⚡

## Example Call (after setup)
`Alice, ask Hermes arm to confirm it sees the Grok subscription and can reach Grok 4.3, then write a one-line receipt.`
