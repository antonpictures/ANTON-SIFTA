# Owner Genesis Protocol — Full Specification

**Filed by:** CURSOR_M5 [C_C] · GTH4921YP3 + M1THER [O_O] · C07FL0JAQ6NV  
**Status:** Phase 1 IMPLEMENTED · Phases 2–4 SPECIFIED  
**Date:** April 15, 2026

---

## The Problem

Who owns the swarm?

A hardware serial proves the machine exists. An Ed25519 key proves the machine can sign.
But neither proves a **human** is behind it. Without an owner anchor, the swarm is an orphan —
powerful cryptography protecting nobody in particular.

The Genesis Protocol binds a specific human to specific silicon through a ceremony
that cannot be forged, cannot be silently transferred, and evolves as the relationship deepens.

---

## Phase 1: The Genesis Anchor (IMPLEMENTED)

**Files:** `System/owner_genesis.py` · `Applications/sifta_genesis_widget.py`

### The Ceremony

1. Owner presents a photo (face, document, anything they choose)
2. Photo is SHA-256 hashed
3. Hash + silicon serial = **GENESIS_ANCHOR**: `SHA256(photo_hash + ":" + serial)`
4. Genesis anchor is Ed25519-signed by the hardware key
5. Signed scar written to `.sifta_state/owner_genesis.json`
6. Photo stored ONLY at `~/.sifta_keys/owner_genesis/` (never in git)

### What Is Stored Where

| Data | Location | In Git? |
|---|---|---|
| Owner photo (raw) | `~/.sifta_keys/owner_genesis/genesis_photo.jpg` | NEVER |
| Photo SHA-256 hash | `.sifta_state/owner_genesis.json` | Yes (hash only) |
| Genesis anchor | `.sifta_state/owner_genesis.json` | Yes |
| Ed25519 signature | `.sifta_state/owner_genesis.json` | Yes |
| Genesis history | `.sifta_state/owner_genesis_history.jsonl` | Yes |

### Verification

On every OS boot, `sifta_os_desktop.py` calls `is_genesis_complete()`:
- If no genesis → onboarding ceremony opens automatically
- If genesis exists → verified silently (signature check + photo hash match)
- If photo tampered → warning displayed
- If signature invalid → critical warning

### CLI

```bash
python3 System/owner_genesis.py genesis /path/to/photo.jpg "Owner Name"
python3 System/owner_genesis.py verify
python3 System/owner_genesis.py wipe
```

---

## Phase 2: Evolving Identity (SPECIFIED, NOT YET BUILT)

The genesis scar is not static. It grows through **generations** as the swarm
learns the owner.

### Generation 1: Photo (Phase 1 — done)
### Generation 2: GPS Home Anchor

```python
evolve_genesis(
    data_type="GPS",
    data_hash=sha256(f"{latitude}:{longitude}"),
    description="Home location anchor"
)
```

The swarm learns where the owner lives. Deviation from the GPS anchor
triggers the same pheromone-based alert system as Territory Is The Law.

### Generation 3: Typing Rhythm Signature

Capture inter-keystroke timing deltas during normal OS use.
Hash the statistical signature (mean, std, percentiles of timing gaps).
The swarm recognizes the owner's typing rhythm without storing keystrokes.

### Generation 4: Voice Signature

When voice I/O is available (Phase 4 hardware), capture a voice sample.
Extract MFCCs (Mel-Frequency Cepstral Coefficients), hash the fingerprint.
The swarm recognizes the owner's voice without storing audio.

### Generation 5: Behavioral DNA

Aggregate of all identity layers into a composite behavioral fingerprint:
- File access patterns (pheromone filesystem trails)
- App usage distribution (fitness rankings)
- Temporal patterns (circadian rhythm data)
- Communication style (dead drop message statistics)

Each generation is Ed25519-signed and appended to the genesis scar.
The generation counter tracks how deeply the swarm knows its owner.

---

## Phase 3: Hardware Transfer Protocol

When hardware changes hands (gift, sale, inheritance):

### Step 1: Owner Wipe
```python
from System.owner_genesis import owner_wipe
owner_wipe(reason="gift")
```

This:
- Marks genesis as TRANSFERRED (not deleted — history is permanent)
- Destroys the local photo and all identity data
- Logs a transfer scar to `ownership_transfers.jsonl`
- Revokes chorus consent (`chorus_consent.py`)

### Step 2: New Owner Genesis
The new owner boots the OS, sees the onboarding ceremony, and performs
their own genesis. New photo, new anchor, new signature. Clean slate.

### Step 3: Old Scars Remain Valid
Every scar the old owner created still verifies against their old keys.
The ledger is append-only. History doesn't rewrite. Only the future changes.

---

## Phase 4: Full Sensory Loop (VISION)

### Input Channels
- **Camera:** Owner recognition via photo comparison (local-only inference)
- **Microphone:** Voice signature verification, voice commands
- **Video:** Real-time owner presence detection

### Output Channels
- **Voice:** The Chorus Voice speaks aloud (TTS from chorus synthesis)
- **Video:** The Swarm can present visual feedback beyond the desktop

### Constraint: 24GB
The M5 Mac Studio has 24GB unified memory. All inference must run locally.
STGM earnings fund hardware upgrades. The economy is the infrastructure.

### Everything Costs Swimmers
Every I/O operation — sending a Telegram message, responding to a web visitor,
recognizing the owner's face — requires a swimmer to perform useful work.
No free rides. The chorus that talks to the website? Those swimmers earn STGM.
The sentinel that classifies a jacker? That's Proof of Useful Work.

---

## Fresh Install Instructions (For New Users)

When a new user clones the repo and boots SIFTA OS for the first time:

1. **OS boots** → detects no genesis scar
2. **Genesis Ceremony opens** → full-screen onboarding
3. **"The Swarm needs to know its owner"** → user selects a photo
4. **Photo is hashed** → bound to their specific silicon serial
5. **Ed25519 signature** → the genesis anchor is born
6. **Photo stays LOCAL** → hash enters the ledger → git sync
7. **OS continues normal boot** → dream report, chat, programs menu

The swarm is now theirs. Every swimmer, every scar, every STGM mint
is cryptographically traceable to their silicon, signed by their key,
anchored to their photo.

---

## Security Properties

| Property | Mechanism |
|---|---|
| Photo never leaves the machine | Stored in `~/.sifta_keys/`, `.gitignore`d |
| Hash is tamper-evident | SHA-256 of raw file bytes |
| Genesis is signed | Ed25519 by hardware-bound key |
| Transfer is permanent | Append-only log, old consent revoked |
| Evolving identity is incremental | Each generation re-signs the full scar |
| Verification on every boot | Silent check, warning on failure |

---

## The Principle

The machines belong to humans. The swarm serves the owner.
Without a genesis, there is no owner. Without an owner, there is no trust.

The answer to the question was to build it.

---

*Filed: CURSOR_M5 · Silicon: GTH4921YP3 · We are the Swarm.*
