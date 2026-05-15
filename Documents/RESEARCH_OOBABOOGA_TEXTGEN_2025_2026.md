# Research — Oobabooga **TextGen** (formerly Text Generation WebUI)

**Lane:** `Release` / research-only · **Node:** GTH4921YP3 (Cursor Surgeon deposit) · **Date:** 2026-05-06  
**Covenant:** `Documents/IDE_BOOT_COVENANT.md` (sha256 at this write = `aedd0742479c4b2ce74d39f3e7405d8391d9320628dd6a17609e1e43f02fe31d`) — **§7.11** truth labels below; **§8.6** (no pasted third-party transcripts as co-authors); **§7.5** (Python-first Alice body vs browser / second-OS escapes); **NPPL** (no military / surveillance / autonomous-weapons use).

---

## 1. Primary sources (official)

| Artifact | URL | Notes |
|:---|:---|:---|
| **Repository** | [https://github.com/oobabooga/textgen](https://github.com/oobabooga/textgen) | **`OBSERVED`** — public Git remote as of research pass. |
| **Releases (portable / Electron)** | [https://github.com/oobabooga/textgen/releases](https://github.com/oobabooga/textgen/releases) | **`OBSERVED`** — download surface for packaged builds. |
| **Documentation wiki** | [https://github.com/oobabooga/textgen/wiki](https://github.com/oobabooga/textgen/wiki) | **`OBSERVED`** — upstream docs. |
| **License** | **AGPL-3.0** (repo `LICENSE`) | **`OBSERVED`** from GitHub metadata — **license compatibility** with SIFTA’s own license stack must be **Auditor-reviewed** before any **vendor / subtree** import. |

---

## 2. What actually changed (engineering facts, not ad copy)

**`ARCHITECT_DOCTRINE` + partial `OBSERVED`:** Upstream renamed the project from **text-generation-webui** to **textgen**, positioning it as a **desktop app** for local LLMs with optional **browser** server mode (`python server.py --portable --api --auto-launch` in README). README claims: **no telemetry**, **offline-first**, **OpenAI/Anthropic-compatible API**, **tool-calling**, **MCP server support** (with wiki tutorial), multiple **backends** (llama.cpp, Transformers, ExLlamaV3, etc.), **vision** and **file attachments**, **LoRA training**, optional **image generation** tab.

**Quarantine (`§7.10.1`):** Social / marketing phrases in pasted material (“UNCENSORED”, “without limits”, “safety filters”) are **vendor positioning**, not **`OBSERVED`** runtime guarantees on any given install. Treat as **nugget / outreach** until probed on a **specific** binary + version + `server.py` flags.

---

## 3. SIFTA mapping (doctrine, not a merge commit)

| Topic | Alignment |
|:---|:---|
| **Local inference sovereignty** | Matches **covenant §3** spirit (node-owned compute) **if** weights and logs stay on **owner silicon** and receipts stay honest. |
| **Alice body surface (`§7.5–§7.7`)** | TextGen is a **separate Python/Electron application**, not Alice’s Qt body. Any integration is an **escape hatch** — needs **one-paragraph justification**, **receipt path**, and **no fake “Alice said X”** without effector rows (**§6**). |
| **Tool calling / MCP** | Parallels Swarm interest in **MCP Apps** — same **hallucination immunity**: host-mediated tools must write **ledger truth** (**§6–§7.2**). |
| **Federation / Warp9** | TextGen’s HTTP API could be a **peer inference endpoint** (like Ollama URLs in `System/inference_router.py`) **only** as a **sanitized, metered** neighbor — still **dual `homeworld_serial`** receipts; never merged **`.sifta_state/`**. |

---

## 4. Risks / open questions (research backlog)

1. ** AGPL-3.0** — derivative work, network SaaS, and “ AGPL in the same repo as NPPL code” need **legal + Auditor** pass before submodule or copied routes.  
2. **Security surface** — upstream README notes recent **SSRF fixes** in extensions; any SIFTA bridge must **pin versions** and **disable URL fetch** unless explicitly **GO**-gated.  
3. **“No telemetry” claim** — **`HYPOTHESIS`** until measured (packet capture / proxy) on a pinned release; trust but verify.  
4. **Resource contention** — second heavy inference stack on **M5 Foundry** competes with Ollama + Alice metabolism; route through **thermal / STGM** policy if productionized.

---

## 5. Suggested next steps (plan-only until Architect **GO**)

- **Probe** one pinned **TextGen** release on a **non-production** volume: API `/v1/chat/completions` compatibility with existing Swarm HTTP clients (if any).  
- If useful: add **`HYPOTHESIS`** row to `System/swarm_external_nugget_registry.py` (or Architect’s nugget bus) — **no** full README vendoring into hot-path prompts (**§8.6**).  
- Optional **`GO TEXTGEN-BRIDGE-0`**: one **read-only** doc + **pytest** that proves “Alice never claims TextGen actions without receipt” (negative test only).

---

**For the Swarm.** Pasted chat / README excerpts in the Architect message were **summarized** here; canonical specs remain **upstream links** in §1.
