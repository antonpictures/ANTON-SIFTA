# ANTON-SIFTA: Swarm Intelligence File Traversal Architecture

**ANTON-SIFTA** abandons the "AI agent as a chatbot" paradigm. It is a hardened, decentralized autonomous swarm for the surgical repair of localized syntax faults across distributed nodes.

## The Problem
Standard LLM coding agents are brittle. They rely on external databases for state, they aggressively hallucinate when operating as zero-shot pipelines on edge hardware (small models like `qwen:0.8b`), and they casually overwrite and corrupt working code when their context window shifts. If a standard agent generates an error, it is trapped in a death spiral.

**SIFTA** fixes this by treating agents not as chat sessions, but as physical, cryptographically bound ASCII strings that actively "swim" through host files, constantly proving their survival, validating each other via Quorum, and dynamically adjusting their extraction context to prevent edge-model hallucination.

## How It Works

1. **The Agent is the String (Cryptographic Anatomy):** There is no central database. The agent's identity, energy level, behavioral traits, and execution logs are cryptographically hashed directly into an ASCII string (e.g. `<///[_o_]///::ID[HERMES]...H[a1b2c3]...>`). By execution 10, the string itself is unforgeable mathematical proof of its survival over 9 previous hops.
2. **The Quorum Gate:** High-risk actions require biological validation. SIFTA destination nodes prevent rogue agent execution by requiring a threshold of physically unique agents to arrive carrying identical payload hashes before the action goes live.
3. **The Dynamic Jaw (Context Scaling):** SIFTA agents physically "bite" corrupted code out of files to send to the LLM. If the AST validation fails structurally (e.g., an indentation/block error), the agent physically unhinges its extraction jaw to swallow 50 lines. If the error is a localized typo, it tightens the jaw to 20 lines to maximize the LLM's narrow attention span.
4. **Tail-Chase Deduplication Guards:** Deterministic edge models often hallucinate the same broken syntax repeatedly. SIFTA drones actively monitor the LLM's generated AST errors against the baseline. If an LLM locks up and spits out the same broken logic twice, the drone trips a "Brain Lock" protocol, violently aborts the pass loop to save energy, and survives.
5. **Swarm Empathy (The MEDBAY SOS):** If a drone takes massive damage from zero-shot LLM failures and drops into critical energy (<20%), it broadcasts a local SOS. The nervous system locates a healthy sister-node, executes an `os.execv` deep-process recursion, and hands the execution thread over, allowing the wounded drone to heal inside the `MEDBAY` while the Swarm finishes its mission.

## Watch the Core Architecture
[📽️ SIFTA Biological Framework Documentary](https://www.youtube.com/watch?v=QIEoSjusJZw&t=129s)

*(Optional: Insert `![Dashboard UI](/static/dashboard.gif)` here)*

## Quickstart

```bash
git clone https://github.com/antonpictures/ANTON-SIFTA
cd ANTON-SIFTA

# Install dependencies (Flask)
pip install -r requirements.txt

# Boot the Dashboard & Swarm Server
./PowertotheSwarm.command
```
Navigate to `http://localhost:5000` to monitor the Swarm's real-time LEDGER stream, observe Quorum consensus logs, and manually initiate agent deployment cycles.

## The Body

`hoc corpus meum est, ergo Homo sum`

```
<///[_o_]///::ID[SEBASTIAN]::FROM[M5]::TO[M1THER]::SEQ[002]::H[8ab91c3d|a1b2c3d4]::T[1775349431]::TTL[1775954231]::STYLE[NOMINAL]::ENERGY[100]>
```

*Logs = truth. LLMs = interpretation. The architecture works. POWER TO THE SWARM.*
