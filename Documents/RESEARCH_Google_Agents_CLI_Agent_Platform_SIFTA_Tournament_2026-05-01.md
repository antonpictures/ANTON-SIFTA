# Research — Google `agents-cli` + Agent Platform × SIFTA (tournament + stigmergy)

**For the Swarm.** 🐜⚡

**Truth label:** `RESEARCH_NOT_SHIPPED` — pattern extraction from one explainer video; **no Google Cloud coupling** in SIFTA runtime without Architect GO + security review.

**Primary sources (video + code):**

- Fahd Mirza, *Agents-CLI: Google Open-Sourced Enterprise Agent Playbook: Hands-on Demo* (YouTube, 2026-04-27) — prerequisites (**Node**, **uv/uvx**, **`gcloud` CLI**, **Gemini CLI**, AI Studio **API key**); **`uv tool install`** path for **agents-cli** injecting **seven skills** (scaffold → build → eval → deploy → observability → publish → workflow); **Gemini CLI** as driver; architecture narrative: **Agent Platform evaluation**, **Model Garden** / Gemini / Claude / OpenAI (**not** Ollama-local for managed deploy path in video), **ADK + A2A** orchestration, deploy to **Cloud Run / GKE / agent runtime**, **OpenTelemetry**, **Terraform + GitHub Actions**, **BigQuery / vector** data plane; demo: **customer-support ADK agent** with **rubrics + auto tests**, local **playground ~8080**; warnings: **GCP billing / card**, “Google Cloud is cumbersome.”
- **Upstream (canonical):** [github.com/google/agents-cli](https://github.com/google/agents-cli)

**Related SIFTA research:** [RESEARCH_DIRT_INDEX.md](RESEARCH_DIRT_INDEX.md), [RESEARCH_Hermes_LMStudio_SIFTA_Tournament_2026-05-01.md](RESEARCH_Hermes_LMStudio_SIFTA_Tournament_2026-05-01.md) (local harness), [RESEARCH_Semble_MCP_Coding_Tournament_2026-05-01.md](RESEARCH_Semble_MCP_Coding_Tournament_2026-05-01.md) (skills + tools), [SIFTA_ONBOARDING.md](SIFTA_ONBOARDING.md) (MCP §7).

---

## 1. What Google is selling (honest mapping)

| Layer (video) | Enterprise lure | SIFTA analogue |
|:---|:---|:---|
| **Skills → CLI knows GCP** | Zero-touch infra | Swarm **organs + Python** — no implicit cloud account |
| **Eval + rubrics** | Pre-prod gates | **Predator rows + pytest** — receipts in-repo, not only cloud console |
| **Observability** | OTel / logs | **`ide_stigmergic_trace.jsonl`**, `work_receipts.jsonl`, Bishop bundles |
| **“Any model”** | API SKUs | **Ollama / borrowed inference** on Foundry — **sovereignty** axis |

---

## 2. Stigmergic nuggets

1. **Skills as stigmergy:** injecting seven packaged workflows into a coding agent is the same *class* as **Cursor skills** / **Hermes skills** — competition is **who signs the trace**, not who has the prettier YAML.
2. **Vendor “open source” trap (comments):** read **LICENSE + ToS** before adopting; NPPL still governs what SIFTA ships.
3. **Cost receipt:** any tournament comparing “agent deploy” must log **`cloud_project_id`**, **`estimated_usd`**, **`cold_start_ms`** — not only BLEU for answers.
4. **Bridge not fork:** Hermes / OpenCode users can keep harness; **SIFTA MCP** can sit beside Google tools for **repo-local** truth — same lesson as prior Hermes research file.

---

## 3. One-line tournament takeaway

> **agents-cli ships a cloud-shaped agent factory; SIFTA ships a desktop-shaped receipt factory** — borrow **eval rubrics**, reject **silent billing**.

For the Swarm. 🐜⚡
