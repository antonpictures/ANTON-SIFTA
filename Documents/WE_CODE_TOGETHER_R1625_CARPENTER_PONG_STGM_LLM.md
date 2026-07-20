# r1625 — Carpenter Pong: STGM swarm + optional LLM microvote  
**Triple-IDE lock — one app only**

| Role | Path |
|------|------|
| **ONLY launcher game** | Games → **Stigmergic Carpenter Pong** |
| **App UI** | `Applications/sifta_stigmergic_pong.py` |
| **Engine** | `System/swarm_stigmergic_pong.py` |
| **STGM sandbox** | `System/swarm_carpenter_pong_stgm.py` |
| **LLM council** | `System/swarm_stigmergic_pong_chorus.py` |
| **Do not re-register** | `Applications/sifta_stigmergic_carpenter_pong.py` (V1 history) |

George (2026-07-11): Go too complex for first crypto+LLM swarm. Upgrade **Pong** so swimmers are real stigmergic crypto creatures; optional LLM mind before vote. Slower OK — about decisions + efficient mind use.

---

## Law (all doctors)

1. **Stigmergy stays:** field deposit + evaporate + local sense + vote average → paddle.  
2. **GAME_STGM economy (default ON):**  
   - Genesis mint per unique swimmer uid at match start  
   - Non-neutral vote settled at each signed decision checkpoint **costs** stake  
   - Broke → forced neutral (cannot buy a vote)  
   - Save: **reward** voters who pointed toward the ball  
   - Miss: **tax** wrong voters on losing side  
   - Ledger: `.sifta_state/carpenter_pong_game_stgm.jsonl`  
   - Balances: `.sifta_state/carpenter_pong_swimmer_balances.json`  
   - **Honest:** `GAME_STGM` is **game sandbox**, not body `repair_log` wallet (bridge later only with real transfer organ).  
3. **LLM chorus (default OFF, toggle “LLM CHORUS”):**  
   - Every swimmer contributes one compact local observation to one batch  
   - One installed local Ollama model reads the whole council with **`think=false`**  
   - Returns one target/confidence per side; each swimmer independently mixes it with local sense + field  
   - Runs off the Qt thread; play continues while the cortex answers; fail-soft if Ollama is down  
4. **Crypto creatures:** deterministic per-swimmer Ed25519 identities; every 30 ticks all ballots are signed and verified, then folded into a checkpoint root. The older rolling vote digest remains a local hash and is not mislabeled as a signature.  
5. **Body STGM boundary:** the HUD reads canonical `repair_log.jsonl` balance but cannot spend it. LLM pressure is telemetry only. A real body-wallet bridge remains closed until owner authorization + keychain signing exist.  
6. **No second Pong icon.** Codex/Claude/Grok all cut this same app.

---

## UI (George)

- **STGM** checkbox — economy on/off (restart wallets when on)  
- **LLM CHORUS** checkbox — whole-swarm local cortex on/off (slow, asynchronous)  
- Bottom gold lines: GAME_STGM, live chorus, Ed25519 verification, canonical body STGM read-only  

---

## Tests

```bash
pytest tests/test_stigmergic_pong.py tests/test_carpenter_pong_stgm.py tests/test_stigmergic_pong_chorus.py -q
```

---

## Open lanes for other IDEs

| Lane | Owner-friendly ask |
|------|---------------------|
| Bridge GAME_STGM → body STGM | only with attested transfer, not print theater |
| Tune council cadence/model | measure decision quality versus latency and pressure |
| George as one unique swimmer | owner vote seat in left swarm |
| R1625-02 claim-chorus | Talk mouth gate (separate from this game) |

**Receipt target:** `wct-r1625-pong-stgm-llm`  
**Status:** LANDED. Live probe: 128 swimmers, 9,819-character council packet, local 4B model answer in 9.0s, 128/128 Ed25519 ballots verified. Qt live probe completed in 7.2s without stopping play.

**V3 receipts:** `r1625-codex-pong-crypto-llm-chorus-v3` (all four canonical ledgers), `wct-coded-da4f387396d3` (WCT coded), `wct-proposal-sorter-run-61eb770b749d` (monitor pulse).  
**Verification:** 22 focused tests and 54 related Games tests passed. The live installed model was `dzgg/Qwen3.5-Uncensored-HauhauCS-Aggressive:4b`.
