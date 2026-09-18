# We Code Together: Alice robot movement research task

Status: first bounded simulation implemented and tested; wider research and
physical robotics remain pending. No AGI completion claim.

## Model context supplied by George

- Ollama tag: `krishairnd/Gemma-4-Uncensored:latest`
- Publisher: `krishairnd`
- Published page reports 1,557 downloads and an update three months ago.
- Model page labels the family `Gemma-4-Uncensored-HauhauCS-Aggressive` and
  `visiontoolsthinking`.
- Reported parameter hash: `56380ca2ab89`
- Pasted params artifact size: `42B`; this is not evidence of model parameter count.
- Sampling shown: temperature `1`, top-k `64`, top-p `0.95`.

Treat these as supplied model metadata. Verify current Ollama facts before
using them in a benchmark or capability claim.

Local verification on 2026-09-08 via Ollama `/api/show`: parameter_size `8.0B`,
quantization `Q4_K_M`, family `gemma4`, parent
`fredrezones55/Gemma-4-Uncensored-HauhauCS-Aggressive:latest`. Advertised
capabilities: completion, vision, audio, tools, thinking. Sampling matches the
values above. These capability labels are not end-to-end test results.

## Research and build question

George wants Alice to become a practical software bridge from perception to
robot motion: visual input becomes tokens or features, a controller reasons
about the next action, and a bounded effector converts that action into joint
commands. The system must account for latency, energy from food/electricity,
sensor uncertainty, safety limits, and the fact that repeated visual encoding
is expensive.

Research one-shot or event-triggered vision encoding, visual servoing,
robot-learning policies, inverse kinematics, motor control, proprioception,
human finger and hand movement, energy-aware inference, and low-latency
perception-action loops. Use primary research papers and official robotics
documentation. Record DOI or stable URL, task relevance, assumptions, and
whether the result applies to Alice's current hardware.

## First bounded prototype

Do not move a physical robot. Build a simulated joint controller with a fixed
arm model, explicit joint and velocity limits, a perception update budget,
and a receipt for every proposed action. Compare continuous vision updates
with event-triggered updates. Measure end-to-end latency, inference count,
tracking error, energy proxy, rejected actions, and recovery after stale or
missing observations.

Required outputs are a research ledger, a small simulation, focused tests,
and a clear boundary between measured results, hypotheses, and future hardware
work. This task does not establish AGI or consciousness; it makes the path to
physical robot control testable.

## Implemented experiment

`System/stigmerobotics_motor_feedback_lab.py` provides a two-joint planar arm,
inverse kinematics, proportional feedback, velocity/joint bounds, stale-input
hold and unreachable-target rejection. It never drives hardware. Run with
`python3 -m System.stigmerobotics_motor_feedback_lab` from the repository root.
We Code Together's live proof section reads the recorded result; reload the
application code to load this new integration.

Recorded run: `motor-8beb5419a09e4635932e72b3c2f48e57`, under
`.sifta_state/motor_feedback_runs/`. All results are `SIMULATED`.

- 30 trials: 3 seeds, 5 scenarios, 2 observation policies.
- 12,000 unique command/echo receipts; action-log SHA256 verified.
- Continuous refreshes: 5,850; event/timer refreshes: 585 (90% fewer).
- Largest final-window reachable-target error: 0.045821 m (limit 0.09 m).
- Speed <= 1.5 rad/s and joint magnitude <= 2.8 rad in every recorded action.
- Sensor dropout triggers a hold and subsequent recovery; unreachable targets
  produce no motion. All four benchmark checks pass.

The event policy still runs a synthetic novelty detector at each available
tick, and refreshes at least every 0.2 simulated seconds. It is not one-shot
vision. Inputs are perfect synthetic target features, not images. Timing is
host control-computation time, not camera-to-actuator latency. Command effort
is an angular-velocity proxy, not joules, STGM, or electricity. No LLM calls
occur in this benchmark; no token-saving claim is supported.

## Research notes

- Todorov and Jordan (2002), [Optimal feedback control as a theory of motor
  coordination](https://www.nature.com/articles/nn963), DOI 10.1038/nn963.
  Relevant idea: correct task-relevant deviations with feedback. This motivates
  tracking error and disturbance tests; the simulator does not reproduce a brain.
- Tabuada (2007), [Event-Triggered Real-Time Scheduling of Stabilizing Control
  Tasks](https://www.seas.ucla.edu/~tabuada/Papers/EventTriggered.pdf), DOI
  10.1109/TAC.2007.904277. Relevant idea: trigger updates using error conditions
  rather than blindly recomputing. Our threshold/timer policy is a simple
  experiment, not an implementation or proof of that paper's stability theorem.
- Chaumette and Hutchinson (2006), [Visual Servo Control, Part I: Basic
  Approaches](https://web.mit.edu/amcp/OldFiles/drg/Chaumette_Part_I.pdf).
  Connect image features and pose estimates to feedback control. Real camera
  calibration, noisy feature extraction and visual-servo evaluation are pending.

## Next bounded tasks

1. Add noisy/delayed feature observations and randomized target trajectories;
   test failure rates and recovery beyond the current five simple scenarios.
2. Add camera feature extraction with an explicit compute budget, then measure
   actual perception/control latency and refresh cost. Keep visitor data isolated.
3. Research human finger control and proprioception specifically; do not infer
   their full mechanism from this two-joint arm experiment.
4. Introduce a hardware adapter only with explicit owner approval, emergency
   stop, calibrated limits and independently verified command acknowledgement.
5. Learning, generalization, self-repair and energy accounting each need separate
   tests. This deterministic controller does not establish those capabilities.
