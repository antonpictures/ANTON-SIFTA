# MiMo Borg vs Plain macOS MiMo

This is the r1133 comparison artifact. The control is a plain MiMo terminal
writing a file on macOS. The SIFTA path is Alice's Borg adapter:
`System.swarm_mimo_stigmergic.mimo_stigmergic_call()`.

| Capability | Plain macOS MiMo | Alice Borg MiMo |
|---|---:|---:|
| Writes a useful `.py` file | Yes, if prompted | Yes: `tools/sifta_receipt_digest.py` |
| Reads Alice's field before acting | No | Yes: field injection before call |
| Writes a MiMo stigmergic trace | No | Yes: `.sifta_state/mimo_stigmergic_traces.jsonl` |
| Deposits pheromone for other organs | No | Yes: `.sifta_state/mimo_stigmergic_pheromones.jsonl` |
| Writes four canonical ledgers | No | Yes: `work_receipts`, `agent_arm_receipts`, `ide_stigmergic_trace`, `episodic_diary` |
| Visible to Alice's body inventory | Not by itself | Yes, as repo files + digest artifacts |
| Memory available to the next run | Terminal scrollback only | Yes, via field trace + receipt digest |

## Borg Artifact

- Tool: `tools/sifta_receipt_digest.py`
- Driver: `tools/run_mimo_borg_receipt_digest_build.py`
- Output: `.sifta_state/receipt_digests/<YYYY-MM-DD>.md`
- Live trace ledger: `.sifta_state/mimo_stigmergic_traces.jsonl`
- Final successful call: `7bb95737-688b-41a5-b76d-ce8f544526a9`
- Build receipt: `r1133-mimo-borg-receipt-digest-build`

## Honest Boundary

Codex seeded the digest target for repeatability before the live MiMo call. The
live Borg path then ran through `mimo_stigmergic_call()`, read the field, called
MiMo, wrote trace/pheromone/four-ledger rows, compiled the tool, executed it,
and wrote the dated digest. That proves Alice's Borg field path can operate on a
useful tool and remember it. A stricter future proof can require a blank target
and apply only code extracted directly from MiMo output.
