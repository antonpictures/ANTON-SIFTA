# r1616 - Research SANA as a bounded visual-imagination organ

**To:** Alice, George, Grok, Claude, Codex, MiMo  
**Status:** RESEARCH QUEUED - no model install or body integration approved  
**Source:** Owner-provided snapshot of `NVlabs/Sana`, SHA-256
`cdf474e63f6bb8b3f98ea2936770f73a74bc2befa9438764e4712d038fbf7c57`

## Short verdict

SANA may help SIFTA as an optional **visual imagination and simulation hand**.
It does not provide AGI by itself, and generated pixels must never be treated as
camera evidence, memory truth, or proof that an action will work.

The promising BORG targets are small and separable:

1. **DC-AE-style latent compression** for compact visual replay and dream
   artifacts.
2. **SANA 0.6B / SANA-Sprint** as a possible local image-counterfactual hand,
   only if an Apple MPS/CPU probe is practical.
3. **Action-conditioned rollout schema** from SANA-WM: observed first frame +
   prompt + camera/action trajectory -> explicitly simulated future frames.
4. **Chunk-causal linear-attention and self-forcing ideas** for long visual
   sequence processing, borrowed as architecture lessons rather than importing
   the full training stack.

## Hardware and truth gate

Current node: Apple M5 MacBook Pro, 24 GB unified memory, 10-core GPU, no CUDA.

The official SANA-WM path is CUDA-oriented. Its documented streaming variants
need about 25-47 GB GPU memory depending on precision/window, and FP4 requires
NVIDIA Blackwell. The bidirectional bundle also includes very large DiT, VAE,
refiner, and text-encoder artifacts. Therefore:

- **Do not install full SANA-WM on this node.**
- **Do not download weights during the static audit.**
- Training and Sol-RL are out of scope for this laptop.
- Any remote-GPU experiment needs explicit owner approval, cost ceiling, and a
  network/model receipt.

## Research task

### A. Static compatibility audit - first

- Pin upstream commit, repository license, every candidate model-card license,
  weight size, dependency, and expected disk/RAM/VRAM.
- Trace CUDA/Triton/Transformer-Engine assumptions and identify whether the
  small image pipeline has a real MPS or CPU path.
- Compare against existing SIFTA organs instead of duplicating them:
  `swarm_active_inference_world_model.py`,
  `swarm_latent_world_model_trainer.py`, `dream_engine.py`,
  `swarm_counterfactual_immune_system.py`, and
  `swarm_reality_fiction_boundary.py`.
- Produce a go/no-go table for: DC-AE codec only, SANA-0.6B image, SANA-Sprint,
  SANA-Video, SANA-Streaming, and SANA-WM.

### B. Smallest local probe - only after A says GO

- Use an isolated environment and an explicit disk budget.
- Probe one smallest candidate only; do not clone the complete model zoo.
- Measure cold/warm latency, peak unified memory, disk, thermals, determinism,
  cancellation, and recovery after failure.
- Run fixed counterfactual prompts and compare output usefulness against the
  existing SIFTA dream/counterfactual path.
- Record model revision, seed, prompt, source image hash, output hash, runtime,
  and resource cost for every artifact.

### C. SIFTA adapter design - no effector authority

If the probe earns a GO, design a narrow `visual_counterfactual` adapter:

- Inputs must cite observed camera/file/browser receipts.
- Outputs carry `SIMULATED_COUNTERFACTUAL`, never `OBSERVED`.
- Generated artifacts are quarantined from episodic fact memory and from direct
  browser/robot effectors.
- The existing active-inference world model may compare a simulation with later
  reality, but only real outcome receipts update action confidence.
- Kill switch, timeout, memory ceiling, and artifact retention TTL are required.

## Acceptance receipts

Research is complete only with:

1. `Documents/RESEARCH_SANA_SIFTA_BORG_FEASIBILITY.md` containing the pinned
   source/license/hardware matrix and a per-component verdict.
2. A no-download static audit receipt.
3. If approved, one bounded local benchmark receipt with resource telemetry and
   artifact hashes.
4. Reality-boundary tests proving synthetic pixels cannot become observation or
   authorize an effector.
5. A final decision: `BORG_CODEC`, `BORG_SMALL_IMAGE_ADAPTER`,
   `BORROW_ARCHITECTURE_ONLY`, or `REJECT_ON_THIS_NODE`.

## Sources to verify

- Repository: <https://github.com/NVlabs/Sana>
- SANA-WM docs: <https://nvlabs.github.io/Sana/docs/sana_wm/>
- SANA-Streaming docs: <https://nvlabs.github.io/Sana/docs/sana_streaming/>
- Original SANA paper: <https://arxiv.org/abs/2410.10629>
- SANA-WM paper: <https://arxiv.org/abs/2605.15178>

WCT task receipt: `wct-r1616-sana-borg-research`

ONE ALICE. RESEARCH FIRST. SYNTHETIC IS NOT OBSERVED.
