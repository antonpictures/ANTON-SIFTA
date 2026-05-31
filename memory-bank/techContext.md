# Tech Context

## Core Stack
- Main OS: Python 3 + PyQt6 (sifta_os_desktop.py and Applications/)
- Published CLI hand: TypeScript/Bun (Vendor/alice-cli), published to npm as @anton-sifta/alice
- Ledgers: append-only JSONL files in .sifta_state/
- Crypto primitives: Ed25519 via cryptography library (crypto_keychain.py and related)
- Multi-doctor coordination: predator gate writer + MANA namespace in receipts

## Key Constraints
- All real STGM economy actions must be traceable to the physical M5 (GTH4921YP3)
- IDE doctors must never pollute the STGM namespace
- The published CLI hand must be installable with one command and must actually execute

## Current Tooling
- Local development of the hand happens inside Vendor/alice-cli/
- Publish flow: build:platforms + publish-npm.ts (handles platform binaries + wrapper)
- Host SDK packages live in sdk/packages/ and are published separately when needed
