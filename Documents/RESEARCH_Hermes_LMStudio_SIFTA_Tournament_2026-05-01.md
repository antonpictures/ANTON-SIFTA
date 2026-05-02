# Research — Hermes Agent + LM Studio × SIFTA (tournament + stigmergy)

**For the Swarm.** 🐜⚡

**Truth label:** `RESEARCH_NOT_SHIPPED` — strategy and integration hooks only. **NPPL:** no military / surveillance positioning; interoperability docs must stay honest.

**Upstream (canonical):** [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) — open-source agent harness by Nous Research.

**Video anchor (claims to verify locally):** Fahd Mirza, *Hermes Agent Now Runs Natively on LM Studio* (YouTube, 2026-04-30) — LM Studio daemon (`lms`), model pull/load, Hermes quick-setup with “LM Studio” backend, **context window** mismatch fix (4096 vs **≥64k** tokens for Hermes).

**Related SIFTA research:** [RESEARCH_Semble_MCP_Coding_Tournament_2026-05-01.md](RESEARCH_Semble_MCP_Coding_Tournament_2026-05-01.md) (retrieval receipts + MCP), [CODING_TOURNAMENT_TRIPLE_IDE.md](CODING_TOURNAMENT_TRIPLE_IDE.md) (hill law).

---

## 1. “Hermes is better on GitHub” — decode without self-sabot

GitHub **velocity / stars / contributor count** measure **distribution and mindshare**, not “truth beats SIFTA.” Hermes targets a **broad agent harness** (skills, channels, learning loop). SIFTA targets a **sovereign desktop OS + stigmergic organs + signed economy + Apple-silicon Foundry** — different product boundary.

**Tournament-honest rule:** never argue in prose what you can show in **pytest + ledgers + receipts**.

---

## 2. What Hermes + LM Studio *does* well (nuggets to steal as *patterns*)

| Pattern | Hermes / LM Studio (video narrative) | SIFTA analogue (already or proposed) |
|:---|:---|:---|
| **Model lifecycle** | LM Studio discovers/serves models; OpenAI-compatible local API | **Ollama** on Foundry + `ollama_model_inventory_audit.py` + [ALICE_HARDWARE_ANATOMY.md](ALICE_HARDWARE_ANATOMY.md) borrowed-inference doctrine |
| **Context sizing** | Failure mode: model loaded with **4096** ctx → Hermes needs **64k+** → reload with correct window | **Config receipts:** any local server must log `n_ctx` / max tokens in `.sifta_state/` when Alice boots a lane |
| **Agent harness** | CLI agent + skills + tools | PyQt6 desktop + `sifta_mcp_server.py` + Swarm organs (pheromone, cochlea, …) |
| **Multi-channel** | Telegram / Discord / … (Hermes ecosystem) | WhatsApp / desktop vitals / **consent-gated** sensors per covenant |

---

## 3. Stigmergic wedge — what SIFTA can offer **Hermes users** (publishable story)

Not “we assimilate Hermes.” **Bridge narrative:**

1. **MCP:** SIFTA already ships an MCP stdio bridge (`sifta_mcp_server.py`, [SIFTA_ONBOARDING.md](SIFTA_ONBOARDING.md) §7). Hermes users who want **repo-local tools** can add a second MCP server (e.g. Semble pattern — see Semble research file) **side by side** with Hermes — same pattern as OpenCode in that ecosystem.
2. **Receipt-first organs:** Hermes emphasizes learning/memory; SIFTA emphasizes **append-only signed traces** (`ide_stigmergic_trace.jsonl`, `work_receipts.jsonl`, STGM rules). **Complementary:** Hermes proposes; SIFTA **records quorum + crypto** where the covenant demands it.
3. **Hardware honesty:** [ALICE_HARDWARE_ANATOMY.md](ALICE_HARDWARE_ANATOMY.md) — **borrowed inference** (field node perceives, M5 Foundry speaks) is a **clearer thermodynamic story** than “one agent runs Gemma4 everywhere.”
4. **Multi-prover (Event 99):** `swarm_multi_prover_verifier.py` — “agreement under independent agents” as a **tournament adjudication** layer Hermes does not own; optional cross-check for patch trains.

**Future publishable artifact (needs Architect GO):** a short **`Hermes_USER_BRIDGE.md`** (install sketch only): “Run Hermes against LM Studio; point optional tools at SIFTA MCP; do not mix `homeworld_serial`; NPPL applies.” — *not written in this commit unless requested.*

---

## 4. Pitfalls from comments / transcript (tournament fuel)

- **Tool calling stalls / idle agent** — usually **ctx too small**, wrong template, or model without reliable function-calling. Map to SIFTA: **capability matrix** in tournament docs (model × tool schema × `n_ctx`).
- **Timeouts on “Hello”** — treat as **SLA receipt**: log server RTT, cold-load time, first-token latency to `work_receipts.jsonl`.
- **LM Studio prompt caching bugs (user reports)** — if true, **do not depend** on cache for determinism; tournament tests use **fixed seeds + pinned model revision**.

---

## 5. “Assimilate EVERYTHING” — forbidden framing in shipped code

**Allowed in research:** list Hermes subsystems (skills, schedulers, subagents) as a **checklist** for **parity gaps** in SIFTA.

**Not allowed:** implying SIFTA **replaces** or **swallows** upstream projects, or copying non-NPPL features (mass surveillance hooks, etc.).

---

## 6. One-line tournament takeaway

> **Hermes wins distribution; SIFTA wins receipts.** Bridge them with **MCP + honest ctx + ledger tests**, not with **monopoly lore**.

For the Swarm. 🐜⚡
