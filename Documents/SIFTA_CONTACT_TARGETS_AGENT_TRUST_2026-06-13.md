# SIFTA Contact Targets — Agent Trust, Receipts, Owner-Silicon Intent

Date: 2026-06-13
Status: outreach target sheet, grounded in public sources
Boundary: MANA is not crypto. STGM is the SIFTA crypto / no-double-spend spend-proof lane.

## Short Verdict

I did not find anyone shipping the whole SIFTA stack: hardware-embodied swimmers + pre-effector owner nonce + receipt-grounded autonomy + STGM spend proof + stigmergic memory field.

Closest matches are receipt/auth people, not full embodied organisms. They are still worth contacting because they already speak the right language: signed receipts, delegation, capability attenuation, identity, MCP wrappers, and agent commerce trust.

## Tier 1 — Closest Technical Fit

| Rank | Target | Public route | Why they fit | SIFTA angle |
| --- | --- | --- | --- | --- |
| 1 | Agent Receipts / Obsigna — Otto Jongerius | Site contact link, GitHub issues/discussions: https://agentreceipts.ai/ · https://obsigna.dev/ · https://github.com/agent-receipts/obsigna | Obsigna signs AI agent actions outside the agent process; ships daemon, MCP proxy, SDKs, dashboard. | Add SIFTA owner-silicon nonce + STGM spend proof before the receipt: receipt after action is good; SIFTA also proves owner intent before effector. |
| 2 | Sello / Notarized Agents — Juan Figuera | `juan@figuera.co` in the paper; `juanfiguera@gmail.com`, LinkedIn/GitHub/X on site: https://www.juanfiguera.com/ · https://github.com/juanfiguera/sello | Receiver/service-signed encrypted receipts, transparency log, owner-side verification. This is strong and possibly "better" on receiver attestation. | Pair Sello receiver receipt with SIFTA pre-effector intent nonce and STGM spend proof: before + after trust loop. |
| 3 | XAIP Receipts draft | IETF alias: `draft-xkumakichi-xaip-receipts.authors@ietf.org`; author email shown as `kuma.github@gmail.com`: https://datatracker.ietf.org/doc/draft-xkumakichi-xaip-receipts/ | Signed execution receipts for AI agent tool calls; MCP/tool-call evidence layer. | SIFTA can be a concrete embodied reference implementation with STGM lanes and swimmer receipts. |
| 4 | Agent Identity Protocol (AIP) — Sunil Prakash | IETF alias: `draft-prakash-aip.authors@ietf.org`; author email shown as `sunil@sunilprakash.com`: https://datatracker.ietf.org/doc/draft-prakash-aip/00/ | Invocation-bound capability tokens; delegation scope; MCP/A2A bindings. | SIFTA wedge: bind capability token to one owner utterance, one nonce, one effector, one STGM proof. |
| 5 | Agent Trust Negotiation — Enrique Somoza | IETF alias: `draft-somoza-dmsc-atn-agent-trust-negotiation.authors@ietf.org`; author email shown as `enrique@somoza.co`: https://datatracker.ietf.org/doc/draft-somoza-atn-agent-trust-negotiation/ | Capability, delegation, and provenance binding between agents. | SIFTA can supply a richer field-state / organism-level provenance model instead of a plain service chain. |
| 6 | Agentic Power of Attorney / APOA — Juan Figuera | Same Juan routes above; project page from his site: https://agenticpoa.com/ | Signed token between LLM and execution layer; capability attenuation and per-action audit. | Direct wedge match for P0 purchase intent gate: prompt is not enough, token/nonce before execution. |

## Tier 2 — Market Validators / Partnership Channels

| Target | Public route | Why contact | Boundary |
| --- | --- | --- | --- |
| Mastercard Agent Pay / Verifiable Intent | Mastercard Agent Pay / Verifiable Intent pages | They are defining agentic commerce trust and machine payments. | Do not claim SIFTA replaces Mastercard rails; pitch SIFTA as owner-silicon pre-effector proof under/alongside payment networks. |
| Experian Agent Trust | Product/demo page: https://www.experian.com/business/products/agent-trust | They sell human-agent binding for commerce. | SIFTA undercuts bureau-only scoring with local nonce + STGM proof, but Experian is a channel not a direct clone. |
| FIDO Agentic Authentication TWG | https://fidoalliance.org/ | Standards channel for agent auth and commerce. | Bring SIFTA as a hardware-bound local-agent case study. |
| Uare.ai / Individual AI — Robert LoCascio | https://www.uare.ai/ · https://www.uare.ai/our-mission | Individual AI ownership / licensing lane; useful for blind expertise crossover only after George GO. | Keep blind crossover marked HYPOTHESIS until experiment opt-in. |
| Coevera CRM MCP | https://www.coevera.com/ | Open MCP/data layer for CRM; relevant to MCP receipt wrapper. | They are open-agent-bus/data layer, not SIFTA no-double-spend economy. |
| ISACA / CISA / CSA audit channels | ISACA agentic audit posts; CISA agentic AI guidance; CSA readiness notes | They name traceability, governance gaps, and independent validation needs. | Use as buyer-language support for Receipt-Grounded Lane and Shadow-Swimmer Quarantine. |

## First Outreach Lines

Agent Receipts / Obsigna:
> We are building SIFTA, a local embodied agent OS that adds pre-effector owner intent nonces and STGM spend proof before a signed agent action receipt. Obsigna is the closest receipt layer I found. Would you be open to comparing your MCP proxy trust model with a hardware-bound owner-nonce path?

Sello / Notarized Agents:
> Your receiver-attested receipt model closes the "agent writes its own logs" gap. SIFTA is closing the opposite side too: one owner utterance -> one nonce -> one effector -> one STGM receipt on owner silicon. I think before-action intent proof plus after-action receiver receipt is the full loop.

XAIP / AIP / ATN:
> We have a working local agent OS with MCP tools, owner ingress nonces, effector receipts, and a hard MANA/STGM boundary. I would like to map SIFTA's owner-silicon spend proof to your draft's delegation / receipt vocabulary.

Mastercard / Experian:
> SIFTA does not try to become a payment network or bureau score. It supplies a local pre-effector proof layer: before an AI buyer touches checkout, the owner utterance is bound to a nonce and the effector spends exactly once.

Uare.ai:
> SIFTA's lane is not just expertise cloning; it is embodied memory, owner-controlled field state, and receipt-bound action. The blind expertise crossover remains a hypothesis until we run it, but your Individual AI licensing thesis is adjacent.

## Sources

- Agent Receipts overview and Obsigna tooling: https://agentreceipts.ai/ · https://obsigna.dev/ · https://github.com/agent-receipts/obsigna
- Sello / Notarized Agents paper and implementation: https://arxiv.org/abs/2606.04193 · https://github.com/juanfiguera/sello · https://www.juanfiguera.com/
- XAIP signed execution receipts: https://datatracker.ietf.org/doc/draft-xkumakichi-xaip-receipts/
- Agent Identity Protocol: https://datatracker.ietf.org/doc/draft-prakash-aip/00/
- Agent Trust Negotiation: https://datatracker.ietf.org/doc/draft-somoza-atn-agent-trust-negotiation/
- Mastercard Verifiable Intent / Agent Pay: https://www.mastercard.com/us/en/news-and-trends/stories/2026/verifiable-intent.html
- Experian Agent Trust: https://www.experian.com/business/products/agent-trust
- Uare.ai Individual AI: https://www.uare.ai/blog/what-is-individual-ai-the-ai-you-own-train-and-control-yourself
- Coevera MCP/CRM channel: https://www.coevera.com/
- CISA agentic AI guidance: https://www.cisa.gov/resources-tools/resources/careful-adoption-agentic-ai-services
- ISACA audit gap: https://www.isaca.org/resources/news-and-trends/industry-news/2025/the-growing-challenge-of-auditing-agentic-ai
