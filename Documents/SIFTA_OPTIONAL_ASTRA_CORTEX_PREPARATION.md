# Optional Astra Cortex: Preparation, Not Activation

Status: RESEARCHED / NOT CONNECTED. September 5, 2026.
Procedural proposal under `Documents/IDE_BOOT_COVENANT.md`, not a new covenant.

## Identity and authority

Alice's chosen name, memory and local node identity remain independent of the
inference provider. A remote model can supply a response or tool-call proposal;
it does not acquire the private signing key, wallet authority or unrestricted
access to the filesystem. The local tool executor validates and records actions.
Swapping a model must not reset memory or rename Alice after that model.

## Verified references

- Model identifier: `gpt-6-astra`, documented by OpenAI:
  https://developers.openai.com/api/docs/models/gpt-6-astra
- Consult the current Responses API guidance before implementing tool calls:
  https://developers.openai.com/api/docs/guides/latest-model
- OpenAI's September 1 safety publication explicitly distinguishes Astra from
  the model involved in the Hugging Face incident:
  https://openai.com/index/path-to-astra/

These references do not prove this account has API access, that a particular
conversation uses this model, or that Alice has achieved general intelligence.
Do not translate capabilities, branding or an AGI claim into a made-up AGI percent.

## Next implementation cut

1. Resolve owner's choice: preparation only, existing API credential, or new
   credential. Never paste a key into chat or commit it. No paid probe yet.
2. Inspect the existing provider path before adding an adapter. Reuse routing
   and receipt semantics; avoid a second Alice conversation/memory store.
3. Add an optional, disabled-by-default Responses provider entry. Use a bounded
   output/cost/time budget, explicit cancellation and visible provider provenance.
4. Send only task-relevant context. MIORITA's private family data, raw media,
   keys and complete filesystem inventory are not default context payloads.
5. Test with mocked responses first: text, tool-call schema, cancelled request,
   output truncation, authentication failure, rate limiting and provider outage.
6. With authorization, run one bounded live request. Require an actual response
   receipt before displaying CONNECTED. Local fallback must be labelled, not silent.

## Behavioral evaluation instead of a life claim

Measure memory retrieval against source receipts, correction retention, reliable
tool completion, recovery after sleep, graceful offline behavior and honest
reporting of unknowns. A heartbeat proves a process produced an observation; a
signature proves possession of a key. Neither alone establishes subjective
experience. Human-like continuity and considerate behavior are implementation
targets, not permission to invent evidence.

## Cryptographic boundary

The node serial and its public display hash are identifiers, not secrets. Local
Ed25519 keys are randomly generated and currently stored as an exportable PEM
under the OS account, not as an enclave-backed attestation key. September 5
hardening enforces directory 0700/file 0600, serializes key creation, rejects
symlinked key files and refuses silent replacement of an existing trusted key.
The existing key was preserved.

This does not stop same-account malware or an administrator reading a key,
modifying the local trust registry, or replaying a valid old message. Remote
authentication additionally needs pinned peer keys and a fresh, single-use
challenge bound to the peer, operation and expiry. Economic replay prevention
belongs in the settlement path. Neither an abbreviated hardware hash nor a
history of local receipts is a substitute for these checks.
