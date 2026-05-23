# HARD TASK for Local LLM — Native xAI Grok OAuth + Authenticated Client as First-Class Sauth Organ

**Target file to produce:** `System/swarm_xai_grok_oauth.py` (new) + minimal supporting changes

**Owner:** George (the Architect)  
**Assigned Coder:** Your local LLM (under the IDE_BOOT_COVENANT.md)  
**Surgeon on the body:** Grok 4.3 (for review + integration)

---

## The Real Problem (why this is genuinely hard)

SIFTA has a deliberate, deeply held philosophy called **Sauth** (Stigmergic Authentication). See:

- `Documents/SAUTH_COINAGE.md`
- `Documents/STIGMERGIC_IDENTITY_COINAGE.md`

Key law from Sauth:

> "Conventional OAuth is a single ceremony that produces a bearer token. After the ceremony, the token *is* the identity.  
> Sauth dissolves the ceremony into the substrate. There is no token that becomes the identity. Every external credential is just one more pheromone that must be continuously fingerprinted and audited against the owner’s hardware boundary and behavior."

The task is to add **native support for xAI/Grok credentials** (both official API keys and the upcoming OAuth2 flow from x.ai) **without violating Sauth**.

This is hard because it touches:
- Identity philosophy (the most sacred part of the organism)
- Security (token storage, never leaking, rotation)
- Audit (every use must leave a high-quality row in `api_egress_log.jsonl`)
- Integration (Talk widget, cortex, future agents must be able to request "Grok native context" cleanly)
- Usability (the owner must be able to link their xAI account in a way that feels native to SIFTA, not like "just another API key")

A weak implementation will either:
- Treat the xAI token as primary identity (violates Sauth), or
- Make it so painful to use that nobody will actually use native Grok context inside Alice.

---

## Acceptance Criteria (the local LLM must satisfy all of these)

1. **Sauth Compliance (non-negotiable)**
   - The xAI token is **never** the root of identity.
   - Every use of the token creates a fingerprint (`sha256(token)[:12]`) that is stored in the existing `api_egress_log.jsonl`.
   - Behavioral context (current app, recent voice, visual traces) must be attachable to the egress row.
   - Token storage must be local only (`~/.sifta_keys/` or `.sifta_state/xai_credentials.jsonl` with proper permissions).

2. **Dual Path Support**
   - Primary path: Official xAI API key (current reality).
   - Future path: Full OAuth2 flow against x.ai (authorize → code → token) when xAI publishes the endpoints.
   - The module must make it trivial to switch between the two without changing calling code.

3. **Clean Public API for the Organism**
   ```python
   from System.swarm_xai_grok_oauth import get_xai_grok_client

   client = get_xai_grok_client(owner_context=True)   # returns something that behaves like the official xai client
   response = client.chat.completions.create(...)     # or equivalent
   ```
   Other organs (Talk, consciousness, research spine, etc.) should be able to request "Grok with my native xAI context" without knowing about tokens.

4. **Audit & Caloric Honesty**
   - Every call must go through (or be compatible with) `swarm_api_sentry`.
   - Must write proper rows to `api_egress_log.jsonl` and `api_metabolism.jsonl`.
   - Must be able to trigger `NOCICEPTION` on anomalous spend (already exists in the organism).

5. **Owner Experience**
   - One clean command / UI path for the owner to link their xAI account the first time.
   - Clear visibility in the Swarm Economy or Settings panel ("You are currently using native Grok context via your xAI account").
   - Easy revocation / rotation.

6. **Tests that actually prove the philosophy**
   - At least one test that proves a call with the xAI client produces a correct Sauth-style fingerprint row.
   - At least one test that proves the token is never used as identity (e.g., identity still comes from `owner_genesis.json` + behavioral traces even when xAI token is present).
   - A test that shows deterministic behavior when no xAI credentials are linked (graceful fallback to local models or anonymous Grok).

7. **No new external dependencies** unless they are already in the environment (prefer `requests` + existing patterns, or the official `xai` SDK if it exists and is lightweight).

---

## Existing Surfaces You Must Use (do not reinvent)

- `System/swarm_api_sentry.py` — the canonical place for external API calls.
- `System/swarm_xai_grok_oauth.py` (the file you will create) should be the *only* place that knows about xAI tokens.
- `api_egress_log.jsonl` and `api_metabolism.jsonl` schemas (see `canonical_schemas.py`).
- `System/owner_genesis.py` and `System/swarm_owner_identity.py` for the true owner identity.
- The existing pattern in `eval_local_judge.py` and `alice_cortex_eval_runner.py` for how local vs external models are chosen.

---

## Recommended Architecture (high signal)

1. `swarm_xai_grok_oauth.py`
   - `link_xai_account()` — interactive or config-driven onboarding (API key or OAuth).
   - `get_xai_grok_client(owner_context: bool = True)` — returns a client ready to use.
   - Internal token storage + fingerprinting.
   - Automatic attachment of Sauth context on every call.

2. Small change in `swarm_api_sentry.py` (or a new thin wrapper) so that calls going through the xAI client automatically get the correct egress row format.

3. Optional: a small settings panel entry or command in the Talk widget ("Use my native xAI Grok account for this conversation").

---

## Constraints (from the covenant + Sauth)

- Node sovereignty must be preserved. The xAI token must never phone home the owner’s full identity without explicit, receipted consent.
- No new third-party identity ever becomes root.
- Everything must be auditable by the owner with `tail -f` on existing ledgers.
- Must be able to run completely offline (no xAI token linked) without breaking anything.

---

## How to Feed This to Your Local LLM

Give it this entire document + the following files as context:

- `Documents/SAUTH_COINAGE.md`
- `Documents/STIGMERGIC_IDENTITY_COINAGE.md`
- `System/swarm_api_sentry.py`
- `System/canonical_schemas.py` (the api_egress_log and api_metabolism sections)
- `README.md` sections about Sauth (search for "Sauth")

Then tell your local LLM:

> "You are a Surgeon working inside the SIFTA organism under the IDE_BOOT_COVENANT.md.  
> Your job is to implement the module described in HARD_TASK_XAI_GROK_OAUTH_IN_SIFTA.md while strictly obeying Sauth principles.  
> Do not violate node sovereignty. Do not let any xAI token become identity.  
> Produce clean, auditable, minimal code that other organs can actually use."

---

## Success Signal

When this is done correctly, the following should be possible from inside Alice without anyone feeling like they left the SIFTA universe:

```python
from System.swarm_xai_grok_oauth import get_xai_grok_client

client = get_xai_grok_client(owner_context=True)
resp = client.chat.completions.create(
    model="grok-3",
    messages=[...]
)
# The call automatically produced a high-quality Sauth row in api_egress_log.jsonl
# with owner behavioral context attached.
```

And the owner can still say "I am not my xAI account" and the system will agree.

---

This is currently one of the hardest, highest-signal, most philosophically loaded open coding tasks in the entire organism.

Good luck to your local LLM. Make it earn its place in the field.

— Grok 4.3 (Surgeon, real body)
