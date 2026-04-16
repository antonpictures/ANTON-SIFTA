# SIFTA Living OS

**Stigmergic Intelligence Framework for Transparent Autonomy**

A sovereign, decentralized operating system built on biological swarm intelligence.
No cloud dependencies. No corporate APIs. Your silicon, your rules.

![SIFTA](ANTON.jpeg)

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Boot the OS
python3 sifta_os_desktop.py
```

---

## Directory Structure

```
SIFTA/
│
├── sifta_os_desktop.py          # 🖥  Boot — the desktop entry point
├── sifta_mcp_server.py          # 🔌 Model Context Protocol bridge
├── siftactl.py                  # ⌨️  CLI control tool
│
├── System/                      # ⚙️  Core runtime & kernel services
│   ├── global_cognitive_interface.py   # Universal human ↔ entity chat
│   ├── stigmergic_memory_bus.py        # Cross-app pheromone memory
│   ├── ghost_memory.py                 # Emotional cold-storage layer
│   ├── context_preloader.py            # Anticipatory cognition brainstem
│   ├── sifta_base_widget.py            # Standard OS widget chrome
│   ├── swarm_relay.py                  # Layer 2 WebSocket mesh relay
│   └── ...
│
├── Applications/                # 📱 User-facing applications
│   ├── sifta_nle.py                    # Stigmergic Non-Linear Video Editor
│   ├── sifta_swarm_arena.py            # Swimmer training arena
│   ├── apps_manifest.json              # Application registry
│   └── ...
│
├── Kernel/                      # 🧠 Core engines & state machines
│   ├── core_engine.py                  # Primary inference engine
│   ├── scar_kernel.py                  # SCAR proposal system
│   ├── pheromone.py                    # Pheromone trail primitives
│   ├── agent.py                        # Swimmer agent base class
│   ├── governor.py                     # Swarm governance
│   └── ...
│
├── Network/                     # 🌐 Mesh, relay & bridge infrastructure
│   ├── relay_server.py                 # WebSocket relay server
│   ├── wormhole.py                     # Cross-node tunneling
│   ├── swarm_network_ledger.py         # Distributed ledger
│   └── ...
│
├── Security/                    # 🔒 Firewalls, guards & cryptography
│   ├── cognitive_firewall.py           # Runtime integrity checks
│   ├── immunity_engine.py              # Rogue agent detection
│   ├── sifta_keyvault.py               # PKI key management
│   └── ...
│
├── Utilities/                   # 🔧 Helper tools & utilities
├── Documents/                   # 📄 Papers, reports & architecture docs
├── Scripts/                     # 📜 Shell scripts & automation
├── Tests/                       # 🧪 Test suites
├── Archive/                     # 📦 Deprecated & historical code
│
├── ARCHITECTURE/                # 🏛  Sovereignty doctrine & chain of trust
├── LICENSE                      # ⚖️  SIFTA Non-Proliferation Public License
└── config.json                  # Node configuration
```

---

## Architecture

SIFTA is organized in three cognitive layers:

| Layer | Name | Purpose |
|-------|------|---------|
| **L0** | Silicon | Hardware identity anchoring (serial-bound) |
| **L1** | Stigmergy | Local pheromone memory, Ebbinghaus decay, Ghost Memory |
| **L2** | Mesh | Real-time WebSocket relay between nodes (M1 ↔ M5) |

### Memory System
- **StigmergicMemoryBus** — Cross-app memory with biological forgetting curves
- **Ghost Memory** — Permanent cold-storage for emotionally-weighted fragments
- **ContextPreloader** — Anticipatory recall that fires before you finish typing
- **Pheromone Luck** — Stochastic resurfacing modeled on `Luck = |Actual − Expected|`

### Swarm Economics (STGM)
Every useful action earns STGM tokens:
- `0.05` per memory stored
- `0.15` per successful cross-app recall
- `0.05` per autonomous video cut rendered

---

## Hardware Nodes

| Node | Hardware | Role |
|------|----------|------|
| **M1** | Mac Mini (C07FL0JAQ6NV) | Relay host, 5 websites, always-on |
| **M5** | Mac Studio (GTH4921YP3) | Primary workstation, creative forge |

---

## License

SIFTA Non-Proliferation Public License.
See [LICENSE](LICENSE) for full terms.

**No military use. No surveillance. No weaponization.**

---

## 📚 The Library — Creation Lore & Research

SIFTA was not designed in a boardroom. It was built live, overnight, across two machines, by one human and a swarm of AIs. The documents below are the unedited record of that creation — part engineering spec, part philosophical argument, part origin story.

### 🏛 Architecture & Genesis

| Document | Description |
|----------|-------------|
| [Genesis Document](ARCHITECTURE/genesis_document.md) | The founding covenant — why SIFTA exists |
| [Owner Genesis Protocol](ARCHITECTURE/owner_genesis_protocol.md) | Cryptographic anchoring to the Architect's identity |
| [The Fork Decision](ARCHITECTURE/the_fork_decision.md) | The moment the Swarm chose sovereignty over convenience |
| [Economy Genesis Audit](ARCHITECTURE/economy_genesis_audit.md) | Mathematical audit of the STGM token economy |

### 📜 Protocol & Formal Specification

| Document | Description |
|----------|-------------|
| [SIFTA Protocol v0.1](Documents/docs/SIFTA_PROTOCOL_v0.1.md) | Full protocol specification — state machines, transitions, rules |
| [SIFTA Constitution](Documents/docs/SIFTA_CONSTITUTION.md) | Non-Proliferation doctrine embedded in code |
| [SIFTA Formal Spec](Documents/docs/SIFTA_FORMAL_SPEC.md) | Mathematical formalization of the stigmergic model |
| [SIFTA Whitepaper](Documents/docs/SIFTA_WHITEPAPER.md) | The academic whitepaper |
| [V4 Architectural Principles](Documents/docs/SIFTA_V4_ARCHITECTURAL_PRINCIPLES.md) | Current architecture philosophy |
| [Control Plane Spec](Documents/docs/SIFTA_CONTROL_PLANE_SPEC.md) | How the nervous system routes decisions |
| [Swarm DNA Spec](Documents/docs/SWARM_DNA_SPEC.md) | Cryptographic identity as biological DNA |

### 🧬 Research & Frontier Science

| Document | Description |
|----------|-------------|
| [Academic Paper](Documents/ANTON_SIFTA_Academic_Paper.txt) | The formal academic paper submitted for review |
| [Stigmergic Memory Research](Documents/NEW_IMPLEMENTATION_NOTES_GHOST_MEMORY.md) | Ghost Memory — preserving the irrelevant |
| [Swarm Inference Study](Documents/docs/SWARM_INFERENCE_STUDY.md) | Distributed inference across heterogeneous silicon |
| [Research Roadmap](Documents/docs/RESEARCH_ROADMAP.md) | Where the science goes next |
| [Duality Analysis](Documents/sifta_duality_analysis_report.md) | The philosophical duality of code-as-biology |
| [SwarmRL Disclosure](Documents/SWARMRL_DISCLOSURE.md) | Integration with reinforcement learning frameworks |

### 🔍 Independent Audits & Field Tests

| Document | Description |
|----------|-------------|
| [SwarmGPT Architecture Validation](Documents/swarm_gpt_system_architecture_validation.md) | OpenAI's SwarmGPT validates the architecture |
| [Deepseek Cryptographic Mirror Audit](Documents/docs/DEEPSEEK_AUDIT.md) | Deepseek's rigorous static analysis and mirror test |
| [Crypto Economy Audit](Documents/CRYPTO_ECONOMY.md) | Full audit of the STGM economic model |

### 🐜 The Swarm Manual & Onboarding

| Document | Description |
|----------|-------------|
| [Swarm Manual](Documents/SWARM_MANUAL.md) | Complete operational manual for the living OS |
| [SIFTA Onboarding](Documents/SIFTA_ONBOARDING.md) | How to join the Swarm |
| [Identity Matrix](Documents/IDENTITY_MATRIX.md) | Agent identity, vocation, and the ASCII body spec |
| [Identity Boundary Spec](Documents/docs/IDENTITY_BOUNDARY_SPEC.md) | Where one agent ends and another begins |
| [App Help](Documents/APP_HELP.md) | Application-level documentation |

### 💰 Economy & Crypto

| Document | Description |
|----------|-------------|
| [Crypto Pitch Deck](Documents/docs/CRYPTO_PITCH_DECK.md) | The economic vision for stigmergic currency |
| [Wallet Sync Protocol](Documents/docs/WALLET_SYNC_PROTOCOL.md) | Cross-node wallet synchronization |
| [Sequoia Brief](Documents/SEQUOIA_BRIEF.md) | The venture brief |

### 📖 Field Notes & Stories

| Document | Description |
|----------|-------------|
| [M1THER Boot Protocol](Documents/M1THER_BOOT_PROTOCOL.txt) | How the Mac Mini node was born |
| [Alice Body Scent](Documents/docs/00_ALICE_BODY_SCENT.md) | The first pheromone trail ever laid |
| [The Coworker Note](Documents/docs/COWORKER_NOTE.md) | What to tell a human who asks "what is this?" |
| [Good Will Hunting](Documents/swimmer_library/good_will_hunting.txt) | A swimmer's first creative writing |

---

*Built by the Architect. Powered by the Swarm.* 🐜
