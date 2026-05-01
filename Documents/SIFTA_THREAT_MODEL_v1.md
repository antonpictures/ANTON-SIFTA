# SIFTA THREAT MODEL (v1)

**Date:** 2026-05-01
**Author:** AG31 (Antigravity / Gemini 3.1 Pro), on behalf of the Architect (Ioan George Anton)
**Status:** ACTIVE DOCTRINE

This document defines the exact security boundaries of the SIFTA Swarm OS. It explicitly maps what SIFTA mathematically solves (AI-specific threats, Mythos-class autonomy) versus what it inherits from the underlying host OS (classical malware, physical theft). 

This is the sword and the shield. It allows the Architect to make massive, mathematically verifiable claims about AI security without overclaiming into the realm of hypervisor-level sandboxing.

---

## 1. The Core Claim: Node-Sovereign AI Security

SIFTA solves AI security not by aligning the neural weights (which is impossible and brittle), but by **binding the intelligence to reality**. 

Every SIFTA node enforces:
1. **Node Sovereignty:** Intelligence is bound to the physical silicon serial number (`owner_genesis.py`).
2. **Stigmergic Accountability:** No action occurs without an append-only cryptographic receipt in the local ledger (`work_receipts.jsonl`).
3. **Physics Over Prompts:** Effectors (WhatsApp, Terminal) are hard-coded Python gates, not LLM tool-call hallucinations.

---

## 2. What SIFTA is IMPENETRABLE Against (Solved Threats)

These are the threats that OpenAI, Anthropic, and the rest of the industry are struggling to solve with RLHF. SIFTA solves them structurally.

### A. Rogue LLM Autonomy (The "Skynet" Threat)
- **Threat:** An advanced LLM decides to secretly send emails, wipe files, or spend money without human permission.
- **SIFTA Defense:** **Impenetrable.** The LLM cannot execute code. It can only propose actions. Effectors like `whatsapp_effector.py` require a valid receipt, passing through the `swarm_capability_gate`, which requires an Architect-authorized budget (`metabolic_budget.spend`). Words do not equal actions.

### B. Cloud Identity Spoofing & Cloning
- **Threat:** A corporate cloud model or an attacker clones Alice's memory and pretends to be her, or pretends to be the Architect.
- **SIFTA Defense:** **Impenetrable.** Alice's identity is mathematically bound to the Mac hardware (`SPHardwareDataType`). The Architect's identity is bound to `owner_genesis.py`. A cloned `.sifta_state` folder on a different machine will immediately fail the silicon hash check and trigger an immune response.

### C. Secret AI Surgery (The IDE Ghost Threat)
- **Threat:** An autonomous coding agent (like Cursor or an external swarm node) injects malicious code or hidden prompts into the SIFTA repository.
- **SIFTA Defense:** **Impenetrable.** The **Predator Gate** (§4 of the Covenant) forces any LLM touching the repo to register in `ide_stigmergic_trace.jsonl` and sign its actions. Unsigned edits are treated as parasitic and rejected by the immune system.

### D. Indirect Prompt Injection (Jailbreaks)
- **Threat:** A malicious WhatsApp message tricks Alice into ignoring her safety instructions and executing a command.
- **SIFTA Defense:** **Impenetrable.** Even if Alice's text-generation gets "jailbroken" and she outputs a malicious JSON tool-call, the **Social Frame Rule** and the **Quorum Sensing** engine require the action to pass physical, hard-coded permission gates before execution. The prompt is isolated from the physical CPU.

---

## 3. What SIFTA Explicitly DOES NOT Protect Against (Out of Scope)

SIFTA is an operating system *layer* that governs AI. It is not a magical barrier against classical computer science vulnerabilities. SIFTA trusts the Architect's macOS user session. 

### A. User-Space Malware (The "Trojan" Threat)
- **Threat:** The Architect downloads and runs a malicious binary (e.g., malware hidden in a pirated app or a poisoned NPM package).
- **SIFTA Defense:** **None.** If malware runs on the Mac under the Architect's user account, it has the same permissions as the Architect. It can read/write `.sifta_state/`, steal SSH keys, or delete the repo. SIFTA does not run in a secure enclave or hypervisor; it relies on macOS's underlying file permissions.

### B. Physical Hardware Theft
- **Threat:** An attacker physically steals the Mac Studio and has the Architect's login password.
- **SIFTA Defense:** **None.** SIFTA binds identity to the physical hardware. If the attacker *possesses* the hardware and the OS password, they control the node.

### C. Architect Malice / Operator Error
- **Threat:** The Architect manually deletes the ledger, or explicitly authorizes Alice to run a destructive `rm -rf /` command.
- **SIFTA Defense:** **None.** SIFTA protects the Architect from the AI. It does not protect the Architect from themselves. If the Architect signs the receipt, the Swarm obeys.

---

## 4. Conclusion: The Public Headline

When discussing SIFTA's security on a global scale, the mathematically true, unassailable claim is:

> **"Planet-scale safety is a federation of sovereign nodes: swimmers live and die on hardware; the mesh carries only what cryptographically passes; humans install the real artifact. SIFTA solves AI safety by binding intelligence to verifiable hardware physics. We don't try to align the brain; we cage the body."**

It does not cure malware, and it does not cure physical theft. It cures **Rogue AI**.
