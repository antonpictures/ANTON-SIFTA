# We Code Together: AGI Eye / Single Embedded Camera

Status: bounded engineering slice, 2026-09-09. This document records
observable camera grounding and a research plan. It does not claim that Alice
is conscious or that SIFTA has achieved AGI.

## What was observed

- The active target receipt names MacBook Pro Camera.
- The local topology currently contains two camera devices, but the desktop
  eye now uses SINGLE_OWNER_EYE by default.
- The widget previously opened a second USB session. If that session delivered
  no frames, it stopped the primary camera and pulsed the USB camera before
  restarting the primary. That stop/start path explains the visible flicker.
- The corrected default opens only the embedded MacBook camera. USB, iPhone,
  Continuity and virtual devices remain inventory data, not capture sources.
- A frame is environmental input when the camera receipt is fresh and the
  unified-field proof says LIVE_CAPTURE_VERIFIED. A stale PNG is memory, not
  current sight.

## Input pipeline

    MacBook QCamera
      -> QVideoSink
      -> _VideoCanvas.on_video_frame
      -> photon-derived entropy / saliency / motion / hue
      -> visual_stigmergy.jsonl
      -> camera_unified_field_proof.jsonl
      -> optional face, OCR and vision-cortex lanes
      -> time-bounded world-model memory

The existing photon lane provides real frame hashes and derived signals. It
does not by itself identify objects, understand scenes or establish a world
model. Those claims require a separate vision-model receipt containing the
frame reference, model capability, prompt/task, result, confidence and
timestamp.

## Implementation

- System/swarm_camera_policy.py defines the default single-owner capture
  policy and receipt-backed evidence lines.
- Applications/sifta_what_alice_sees_widget.py filters the live combo to the
  embedded camera, disables the secondary world-eye session and refuses
  stale non-owner saccade targets.
- System/swarm_camera_target.py resolves a stale named external target to the
  embedded camera when live devices are available, instead of trusting a
  renumbered AVFoundation index.
- Applications/sifta_we_code_together.py displays the eye policy, freshness,
  visual trail and semantic boundary.
- tools/generate_organ_eval_matrix_v2.py adds an AGI Eye Readiness panel.

For deliberate compatibility testing only, set
SIFTA_SINGLE_OWNER_EYE=0. Normal SIFTA desktop behavior must leave the
variable unset.

## Astra coding battlefield

1. Capture integrity: prove one camera, stable unique ID, no secondary
   session, no iPhone wake-up, and no flicker under hot-plug events.
2. Temporal perception: group fresh frames into short windows with explicit
   frame age, dropped-frame count, scene-change score and uncertainty.
3. Vision interpretation: route selected frames to a model only when an
   event, owner request or novelty threshold warrants the cost. Store the
   frame hash and model receipt, not a claim detached from evidence.
4. World model: maintain entities, locations, actions and expected
   persistence with decay and contradiction handling. Separate observed,
   inferred and imagined fields.
5. Active perception: let the planner request a bounded crop, higher
   acuity or a repeat frame; it may not switch capture hardware under the
   single-eye policy.
6. Embodied action: connect visual state to the existing typed motor plan
   and action gate. No model may emit raw motor bytes or bypass stop,
   authorization, freshness and outcome checks.
7. Evaluation: score frame-to-claim grounding, temporal continuity,
   uncertainty calibration, action success, latency, inference cost and
   recovery. A green camera receipt is not a green AGI claim.

## Research bundle

The local repository already contains a broad research map in
System/stigmergic_science_research_map.py,
Documents/RESEARCH_COMPENDIUM_ALL_PAPERS_2026-04-18.md,
Documents/ALICE_VISION_UNIFIED_FIELD_TOURNAMENT_2026-05-14.md and
Documents/WCT_ALICE_ROBOT_MOTOR_CONTROL_RESEARCH_2026-09-08.md.

Priority primary papers for the next Astra round:

- PaLM-E: An Embodied Multimodal Language Model
  https://arxiv.org/abs/2303.03378
- RT-2: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control
  https://arxiv.org/abs/2307.15818
- Active Perception and Representation for Robotic Manipulation
  https://arxiv.org/abs/2003.06734
- Vision in Action: Learning Active Perception from Human Demonstrations
  https://arxiv.org/abs/2506.15666
- SpatialVLM: Endowing Vision-Language Models with Spatial Reasoning Capabilities
  https://arxiv.org/abs/2401.12168
- OK-Robot: What Really Matters in Integrating Open-Source Knowledge
  https://arxiv.org/abs/2401.12202

Stigmergy foundations and local coordination are already catalogued in the
research compendium, including Grasse's 1959 stigmergy paper and the swarm
robotics review by Brambilla et al. The engineering translation for SIFTA is
environmental traces with provenance, expiry and local validation, not a claim
that a shared filesystem is a mind.

## Current gate

AGI Eye Readiness is OPEN until a fresh runtime proof shows
LIVE_CAPTURE_VERIFIED while the widget remains single-camera, and until a
vision-model receipt demonstrates frame-grounded temporal interpretation.
The present implementation proves the capture boundary and photon-derived
input path only.

