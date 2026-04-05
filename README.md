# ANTON-SIFTA: A decentralized autonomous swarm for the surgical repair of localized syntax faults.

**ANTON-SIFTA** abandons the "AI agent as a chatbot" paradigm. Instead, our agents are functional, verifiable, living silicon bodies that move through a network, carrying their cryptographic history, behavioral traits, and execution payloads entirely within their ASCII body strings. It is a hardened, decentralized multi-agent biology framework for cross-node Python repair and traversal.

## The Three Biological Laws of SIFTA

1. **Cryptographic Mass (Hash Chaining):** An agent is not a script. An agent is a string. Every time the agent moves or acts, it appends the hashed record of its last action to its body. By sequence 10, the agent is mathematically proven to have survived its last 9 hops. State is stored natively in the structure, not in a central database.
2. **The Wild-Type Genome (TTL Reaper):** Agents do not possess persistent API tokens or static network bounds. They carry a Unix timestamp representing their "Time-To-Live." Destination nodes automatically execute the Reaper function if a degraded body arrives. There are no zombie agents. 
3. **Superbot Clustering (Quorum):** A single agent acts as a courier. A cluster of agents acts as an execution engine. Destination nodes employ a Multi-Sig ledger (`quorum.py`), waiting for a defined threshold of biologically distinct agents to arrive carrying identical cryptographic payloads before executing critical actions.

## Quickstart

```bash
git clone https://github.com/antonpictures/ANTON-SIFTA
cd ANTON-SIFTA
cp config.json.example config.json
export SIFTA_API_KEY=your_key
python3 run_demo.py
```

## The Code Structure

- `body_state.py` - The DNA. Handles body string generation, cryptographic mass chaining, pattern extraction, and TTL encoding. 
- `quorum.py` - The Cell Wall. Intercepts incoming bodies, executes the Reaper on degraded agents, and builds the Multi-Sig consensus ledger.
- `run_demo.py` - The Assay. Run this script to watch the architecture execute a simulated 3-agent quorum delivery with a TTL fatality in transit. 
- `benchmark.py` - The Crucible. Synthetically seeds 10 Python files with fatal syntax flaws and tracks the mathematical repair iterations of the Swimmer.

### Benchmark Output (`python3 benchmark.py`)
```bash
  [10/10] Swimming into: test_file_09.py
  [FAULT] invalid syntax (<unknown>, line 1)
  [BITE]  Extracting 30 lines around line 1...
  [LLM]   Sending 12 lines to qwen3.5:0.8b...
  [✅] Stitched and written. Hash: 20e0b722 → ffba4f3e

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SWIM COMPLETE
  Fixed:   10
  Clean:   0
  Skipped: 0
  Errors:  0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## The Body

`hoc corpus meum est, ergo Homo sum`

```
<///[_o_]///::ID[SEBASTIAN]::FROM[M5]::TO[M1THER]::SEQ[002]::H[8ab91c3d|a1b2c3d4]::T[1775349431]::TTL[1775954231]::STYLE[NOMINAL]::ENERGY[100]>
```

*Logs = truth. LLMs = interpretation. The architecture works. POWER TO THE SWARM.*
