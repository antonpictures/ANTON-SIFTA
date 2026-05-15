# MAMMAL Organ — Pull Guide

**Architect ask (2026-05-13 23:55):** "DID WE DOWNLOAD THE MAMMAL WEIGHTS I WANT THE LLM AS ONE OF OUR ORGANS / TOOLS"

**Probe answer:** NO. Weights are not on the machine. This document is the exact set of commands to make them present.

## What MAMMAL is

`ibm-research/biomed.omics.bl.sm.ma-ted-458m` — a 458M-parameter multi-modal biomedical foundation model from IBM Research. From the paper figure: pre-trained on Gene Expressions (CZ CellXGene), Small Molecules (PubChem, ZINC-22), and Proteins (UniProt, OAS, String). Handles 11+ drug-discovery downstream tasks (BBBP, ClinTox, Cancer-Drug Response, Ab Infilling, AbAg Bind, TCR Bind, PPI ΔΔG, DTI, Cell Type, etc.) via a Structured Universal Prompt of typed tokens (Protein, Small Molecule, Gene Expression, Antibody, Cell Type, Cell Line, Scalar Attribute, Token Attribute, General Token).

**MAMMAL is NOT a chat LLM.** It does not produce free-form natural-language replies. It scores, classifies, regresses over typed biomedical token prompts. The right framing inside SIFTA is **a specialized tool organ** — the cortex-gated router invokes it for biomedical-query intents, it returns a structured result, signed receipt is written.

## Pull command (run on YOUR Mac terminal, NOT inside the sandbox)

```bash
# 1. Install the libraries (one-time)
pip3 install --upgrade transformers huggingface_hub

# 2. Pull the weights to the default HF cache (~/.cache/huggingface/hub)
huggingface-cli download ibm-research/biomed.omics.bl.sm.ma-ted-458m

# Alternative if huggingface-cli isn't on PATH:
python3 -c "from huggingface_hub import snapshot_download; snapshot_download('ibm-research/biomed.omics.bl.sm.ma-ted-458m')"

# 3. Verify the wrapper sees them
cd /Users/ioanganton/Music/ANTON_SIFTA
python3 -m System.swarm_mammal_organ --probe
```

Expected output of step 3 after a successful pull:

```json
{
  "model_id": "ibm-research/biomed.omics.bl.sm.ma-ted-458m",
  "present": true,
  "location": "/Users/ioanganton/.cache/huggingface/hub/models--ibm-research--biomed.omics.bl.sm.ma-ted-458m",
  ...
  "evidence_files": [
    "...config.json",
    "...model.safetensors"
  ]
}
```

## If the pull errors out

### 403 / "gated repo"

The model may be gated on Hugging Face. Run:

```bash
huggingface-cli login
```

Paste your HF access token (get one at https://huggingface.co/settings/tokens). Then visit https://huggingface.co/ibm-research/biomed.omics.bl.sm.ma-ted-458m in a browser and click **"Agree and access repository"** if the license requires it. Then re-run step 2.

### Network timeout

The download is ~1-2 GB (safetensors fp16). On a slow link it can take several minutes. `huggingface-cli` resumes interrupted downloads by default — just re-run.

### Disk space

You have **129 GB free**. The model takes <2 GB. No issue.

## What the wrapper gives you once the weights are present

```python
from System.swarm_mammal_organ import MammalOrgan

organ = MammalOrgan()
result = organ.query({
    "protein": "MKTAYIAKQRQISFVKSHFSRQLEERLG",
    "task": "tcr_bind",
})
# result.ok           → True if the model loaded and ran
# result.truth_class  → "HYPOTHESIS"  (biomedical claims need wet-lab validation)
# result.output       → structured output (default: embedding vector)
# result.sha256       → 64-char signature of the result payload
# result.receipt_id   → 16-char id for the receipt in
#                       .sifta_state/mammal_organ_receipts.jsonl
```

## What the wrapper does WHEN weights are missing

It returns a `MammalQueryResult` with:
- `ok=False`
- `error="MAMMAL weights not found at ..."`
- `pull_instructions=<this guide's command block>`
- `output=None` (no silent fakes — per §7.12 Probe-Before-Claim)
- A failure receipt is still written to the ledger so the gap is auditable

## Truth-class discipline

Per the wrapper's `TRUTH_BOUNDARY`:

> MAMMAL is a multi-modal biomedical foundation model — NOT a chat LLM and NOT a finished medical authority. Its outputs are HYPOTHESIS until validated by wet-lab or independent receipts. This wrapper is OPERATIONAL scaffolding; the model's predictions inherit HYPOTHESIS class. No claim about reproducing ATLAS/CMS or beating CERN (§20.F).

Every `query()` result has `truth_class = "HYPOTHESIS"` baked in. Receipts in the ledger carry the same. Outreach copy must respect §20.F — no "we beat ATLAS / CERN" phrasing.

## Next steps (after weights land)

1. Run `python3 -m System.swarm_mammal_organ --query "PROTEIN MKTAYIA..."` to verify the forward pass works end-to-end.
2. Wire a `biomedical_query` intent into the cortex-gated router so Alice can route appropriate questions to MAMMAL automatically. (Bridge module pattern, see `System/swarm_wallpaper_router_bridge.py` for the template.)
3. Build the **Stigmergic Mammal Widget** the architect specified — Layer 1 (typed tokens, already done), Layer 2 (TokenSwimmers + ecology), with MAMMAL as the embedding/scoring backend the swimmers consult.

## Receipt of this guide

```
truth_label: MAMMAL_ORGAN_V1_PULL_GUIDE
file:        Documents/MAMMAL_ORGAN_PULL_GUIDE.md
written:     2026-05-13 by Cowork (claude-opus-4-7)
companion:   System/swarm_mammal_organ.py + tests/test_swarm_mammal_organ.py
```
