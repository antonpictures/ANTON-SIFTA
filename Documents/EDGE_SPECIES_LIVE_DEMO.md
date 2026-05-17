# SIFTA Edge Species - Live 90-Second Demo

Truth label: `OPERATIONAL` on M5 simulation, `HYPOTHESIS` for real Jetson actuation until a Jetson hardware receipt exists.

## Claim

The slow SIFTA field and the fast CPG/motor layer share one append-only receipt discipline. On the M5, motor commands are simulated. On a Jetson, the same binding can drive PWM only when `SIFTA_JETSON_MOTOR_ENABLE=1` is explicitly set.

## Run

These commands are deliberately manual and non-blocking. Keep each terminal visible. Do not wrap a forever loop in `subprocess.run()` for the investor demo.

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
python3 -m System.swarm_fast_layer_cpg --steps 200
python3 -m System.swarm_edge_species_live_demo
python3 Utilities/verify_unified_chain.py --write-receipt
```

## Current Proof Boundary

- `OPERATIONAL`: M5 simulation path, SHA-256 receipt chains, chain-head sidecars, slow-field modulation, VETO blocking, and finite demo/verifier commands.
- `HYPOTHESIS`: Real Jetson actuation until a Jetson receipt shows `hardware_sent=true` from actual `Jetson.GPIO`.
- `NOT YET`: Servo calibration, measured loop jitter, physical emergency stop, and a filmed hardware bring-up.

## What To Show

1. Baseline field: `dfa_state=SAFE`, low thermal load, normal CPG frequency.
2. Thermal pulse: `dfa_state=WARN`, higher thermal load, lower oscillator frequency and lower coupling.
3. Stacked damage: `dfa_state=VETO`, fast layer writes receipts but blocks motor output.
4. Recovery: field returns to `SAFE`, CPG resumes without breaking the hash chain.
5. Verifier: `fast_cpg_modulation.jsonl`, `fast_layer_cpg_ticks.jsonl`, and `fast_layer_cpg.jsonl` validate as SHA-256 chained ledgers.

## Talk Track

Most AI-on-robot systems are an LLM wrapper talking to a robot API. This is a nervous-system slice: a slow stigmergic field modulates a fast oscillator/motor layer, and the safety state can stop hardware without losing continuity.

The electrons move through the M5 now. On Jetson, the same receipt path can move real PWM, but only after explicit arming. No fake actuation claim. No lost hash. One ledger discipline from cortex to joint.
