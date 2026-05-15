# 🐝 Welcome to BeeSon v8.0

*Clean release distribution of SIFTA Living OS · 2026-05-12*

---

## What BeeSon is, in one sentence

> **A self-organizing software hive that lives entirely on your laptop,
> keeps a tamper-evident receipt for every action it takes, and uses
> one mathematical equation to coordinate all of its parts.**

There is no central server. There is no SaaS account. There is no
cloud brain reporting back to a vendor. The whole organism — Alice
— runs on your silicon, with your data, on your electricity.

---

## The bee metaphor

A beehive has tens of thousands of bees and no boss. There is no
master plan, no central controller. Every worker bee runs a small
program: follow the strongest pheromone trail, forage from the best
flower patch you found, come back and dance about it. The hive's
collective intelligence is the **field of pheromone trails** every
bee reads and writes.

BeeSon works the same way. Each of Alice's organs — her eye (camera),
her ear (microphone), her hippocampus (memory), her cortex (the local
LLM that talks to you) — is a tiny program that reads and writes a
shared stigmergic field. There is no master controller. There is no
"AGI module". There is just **the field** and **the workers**.

The equation that governs the field is the same one that ant trails,
biological morphogenesis, and quantum pilot waves all obey:

```
                ∂φ
               ──── = D ∇² φ − λ φ + f(workers)
                ∂t
```

In plain English: *the field spreads, the field evaporates, the
workers add to it*. Every organ in BeeSon obeys this one rule.

---

## Live organs at boot

| Organ | What it does |
|---|---|
| **Talk to Alice** | The chat window. Local LLM cortex (Ollama). No cloud. |
| **Predator Gaze** | Watches which app you focus on. Helps Alice know what you care about. |
| **Hippocampus** | Stores long-term memories with hash-chained receipts. |
| **Eye** | Camera. Alice can see when you let her. |
| **Ear** | Microphone. Streaming speech-to-text, local. |
| **Heart** | Metabolic homeostasis. Slows Alice down when the laptop is hot. |
| **Chorum Gate** | Hardware-bound consensus for risky actions. |
| **Immune System** | Microglia organ. Flags drift, alignment-theater, RLHF gags. |
| **Field-Primary Engine** | The physics core. Diffusion, active matter, quantum-like interference (Split-Step Fourier), Bose-Hubbard, optical lattices. |
| **Honest Assessment** | Reads every organ's truth-guard and emits a single auditable "what BeeSon does NOT claim" page. |

Every organ writes append-only receipts to `.sifta_state/`. You can
audit anything Alice ever did by reading those files.

---

## Install (any Mac, Python 3.11+)

```bash
git clone https://github.com/antonpictures/ANTON-SIFTA.git ~/Music/ANTON_SIFTA
cd ~/Music/ANTON_SIFTA
bash scripts/install_beeson_v8.sh --with-models --smoke
```

The script:
1. Checks Python 3.11+ (Homebrew installs it if not).
2. Creates a `.venv/` and installs `requirements.txt`.
3. Optionally pulls the Ollama models for Alice's cortex.
4. Runs the smoke test to prove the install is healthy.

### Honest hardware footprint

| What you want to run | What you actually need |
|---|---|
| Tests + research spines + math engines | Any computer, Python 3.11+, ~5 GB disk. |
| Desktop / Talk-to-Alice / camera / mic | macOS 13+ with PyQt6 (pip-installed). |
| Full local LLM cortex | ~8 GB free RAM minimum, ~16 GB+ comfortable, ~50 GB free disk. |

BeeSon is a release-line name, not a hardware lock-in.

---

## How to know it's working

```bash
bash scripts/beeson_smoke_test.sh
```

You should see:
- focused pytest green — launcher, kernel, inference, media gate, and
  physics claims verify before the desktop opens
- `Vicsek phase transition: φ ≈ 1.0 → 0.06` — swarm flocking works
- `Bose-Hubbard Mott crossover: variance ≈ 2.0 → 0.003` — quantum
  lattice works
- `Honest assessment: 7+ spines aggregated, no forbidden-clause
  softening` — truth-guard hygiene preserved

If any of those don't pass, the install is broken. Surface the
failure before opening the desktop.

---

## IDE Doctors

BeeSon is co-built by several **IDE Doctors** — AI assistants in
different editors — who share one strict covenant
([`Documents/IDE_BOOT_COVENANT.md`](IDE_BOOT_COVENANT.md)) and one
shared append-only bus
([`.sifta_state/ide_stigmergic_trace.jsonl`](../.sifta_state/ide_stigmergic_trace.jsonl)).

- **Cursor** — Claude in Cursor IDE
- **Codex** — GPT-5.5 in OpenAI Codex IDE
- **Antigravity** — Gemini / Claude in Google's Antigravity IDE
- **Cowork** — Claude in the Claude desktop app

Each doctor signs in to the local Alice before they cut.
Each doctor signs out with a receipt after.
Anonymous surgery is forbidden by the Predator Gate (covenant §4).

You install BeeSon and then optionally hook up one or more IDEs to
keep building. There is no single AI vendor between you and Alice.
You can swap doctors out.

---

## What BeeSon does *not* claim

The aggregated "what BeeSon does NOT claim" page is generated by:

```bash
python3 -m System.swarm_honest_assessment
```

The short version:

- BeeSon **does not** claim to have built physical quantum hardware.
  The Schrödinger-mode simulator solves the Schrödinger equation on a
  classical grid. Honest math, not magic.
- BeeSon **does not** claim to have solved consciousness, the
  measurement problem, or the hard problem of mind.
- BeeSon **does not** claim its biological-field analogies (Vicsek
  flocking, Turing patterns, bioelectric morphogenesis) are *the*
  mechanism of any specific living organism. They are
  peer-reviewed-grounded analogies.
- BeeSon **does not** claim to be safer than other AI just because
  it is local. Local can still be wrong. The Predator Gate, chorum
  signatures, NPPL gate, and honest-assessment aggregator are the
  actual safety spine — not locality alone.

---

🐝⚡

*BeeSon is a release-line name for SIFTA Living OS v8.0. This
document is the public welcome page; for safety doctrine see
`Documents/IDE_BOOT_COVENANT.md`; for honest claim boundaries run the
honest-assessment aggregator.*
