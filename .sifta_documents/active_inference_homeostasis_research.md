# Computational Neurobiology in Active Inference

Following the Architect's directive, the SIFTA Swarm OS is formally graduating from heuristic agents to **computational neurobiology**. 

We have established three critical fields:
* `Φ(t)` — Stigmergic Speech Potential (LIF Membrane)
* `Ψ(t)` — Motor Readiness Gate
* `Ω(t)` — Synaptic Homeostasis Field (Negative Gain Control)

## The Fundamental Nexus: Stability vs Plasticity
The latest research mapping biological learning to artificial systems (e.g., Stanford NIH Bienenstock-Cooper-Munro modeling) frames the challenge as a conflict between Hebbian Potentiation and Homeostatic Regulation.

1. **Hebbian Learning ("Neurons that fire together, wire together"):** This is a positive feedback amplification. In artificial Swarms, unchecked Hebbian updates (rapidly updating internal weights based solely on recent success) leads directly to synaptic saturation and runaway excitation. *This is why Alice occasionally enters endless "chaos loops" where she rapidly changes files until the buffer bursts.*
2. **Homeostatic Plasticity (Synaptic Scaling):** This acts as the biological negative-feedback controller. By modulating synaptic weights dynamically around a target baseline (our `target_activity = 0.5` inside `Ω(t)`), it stabilizes the runaway dynamics. 
3. **The Active Inference Bridge:** Friston's Active Inference unites these two. The Swarm minimizes variational free energy (Prediction Error = `AGC + optical anomaly`). The Homeostatic Field `Ω(t)` ensures the probabilistic bounds stay strictly within a viable operational envelope.

## Moving to Phase 2: Learned Synapses
The Architect explicitly defines the Two Directions for the Swarm OS implementation:
1. **Coupled Fields:** `Φ(t)`, `Ψ(t)`, and `Ω(t)` must influence each other continuously. Over the next iteration, we will rewire Alice's underlying clock daemon so that whenever `Ψ(t)` rises (action hesitation drops), `Φ(t)` correspondingly adjusts.
2. **Plastic Coefficients:** Currently, parameters like $a, b, c, \eta, \lambda$ are biologically-plausible hardcoded floats. Moving forward, these coefficients must become **Learned Synapses**. Instead of random Simulated Annealing across the constants (our genetic drift script), we will deploy Hebbian scaling. When an action succeeds, the specific coefficients responsible will naturally potentiate.

This research guarantees Alice's mathematical models are theoretically grounded in modern Active Inference equations rather than standard Machine Learning vector adjustments.
