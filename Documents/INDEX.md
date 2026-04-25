# SIFTA Doctrine Index

Welcome to the **SIFTA Swarm OS** learning hub. This directory contains the architectural, operational, and philosophical texts necessary to understand and orchestrate the Swarm.

If you are a new Architect attempting to spin up a distribution fork or operate your own Swarm safely, read the documents below in order.

## Part I: Foundation & Doctrine
- **[SIFTA Protocol v0.1](docs/SIFTA_PROTOCOL_v0.1.md)**  
  The core state-machine, token transitions, and base physics of the platform.
- **[SIFTA Constitution](docs/SIFTA_CONSTITUTION.md)**  
  Non-proliferation guardrails and safety directives written into the Swarm's cognitive bedrock.
- **[SIFTA V4 Architectural Principles](docs/SIFTA_V4_ARCHITECTURAL_PRINCIPLES.md)**  
  High-level framework topology and design philosophy.
- **[Swarm DNA Spec](docs/SWARM_DNA_SPEC.md)**  
  The mathematics behind cryptographic identity preservation (Ed25519) in Swarm workers.
- **[Identity Matrix](IDENTITY_MATRIX.md)**  
  Vocation definitions, agent properties, and ASCII body specifications.

## Part II: Distributions & Infrastructure
- **[SIFTA Distro Doctrine (v2)](SIFTA_DISTRO_DOCTRINE_v2.md)**  
  The "Two-Repo" model explaining the barrier between the personal lab (development) and the public OS distribution.
- **[Distro Playbook](SIFTA_DISTRO_PLAYBOOK_v1.md)**  
  The 7-step sequence used historically (and mechanically via `Scripts/distro_scrubber.py`) to detach PII and silicon hardware serials for public distribution.

## Part III: Operations (The Architect)
- **[First-Boot Ceremony (Owner Genesis)](OPERATOR_GUIDE_FIRST_BOOT.md)**  
  Start here. Instructions for anchoring the Swarm to a new user's Apple Silicon serial for the first time.
- **[Rename AI & Re-Genesis](OPERATOR_GUIDE_RENAME_AI.md)**  
  How to trigger amnesia manually to rename the OS instance or port the node to a completely new Mac.
- **[SIFTA Onboarding](SIFTA_ONBOARDING.md)**  
  The practical "hello world" of getting the agents talking and bridging IDEs.
- **[Swarm Manual](SWARM_MANUAL.md)**  
  End-to-End operations guide for memory control, economic logging, and OS administration.
- **[App Help](APP_HELP.md)**  
  Granular specifications for running individual `Applications/` modules.

## Part IV: Economics & Stigmergy
- **[Crypto Pitch Deck](docs/CRYPTO_PITCH_DECK.md)**  
  The foundational structure of the STGM ledger economy.
- **[Wallet Sync Protocol](docs/WALLET_SYNC_PROTOCOL.md)**  
  Substrate specifics for syncing `repair_log.jsonl` across localized P2P nodes.

We Code Together.
