# Life Journal Camera + Audio Presence Report

Date: 2026-05-08
Author: CG55M@cursor
Mode: patch + verify

## Result

The Life Journal consolidator now fuses camera-presence evidence from the
existing face-detection organ into owner activity classification, journal rows,
schedule rows, and receipts.

The implementation is deliberately non-blocking. It reads
`swarm_face_detection.current_presence_safe()`, which tails
`.sifta_state/face_detection_events.jsonl`; it does not spawn a live camera
probe inside the journal heartbeat. Fresh visual evidence can now support
`owner_present`, while stale visual evidence is carried as evidence but never
used to claim that George is currently present.

Lane two is now wired as audio energy / VAD evidence. It tails existing ledgers
only:

- `.sifta_state/audio_ingress_log.jsonl` for room energy / RMS.
- `.sifta_state/acoustic_fingerprints.jsonl` for nearfield voice likelihood.

It does not open the microphone from the journal tick. Fresh nearfield voice
evidence can support live voice grounding. Stale audio rows are carried as
evidence but never used to claim current speech.

## SIFTA Wiring

- `System/swarm_life_journal_consolidator.py` now accepts optional
  `camera_presence` evidence and reads the safe face ledger when none is
  provided.
- `classify_activity()` includes a serializable `camera_presence` evidence
  block in every classification.
- Fresh `audience=architect` evidence raises confidence slightly for a known
  activity and can open a conservative `present_at_desk` segment when the
  active-window probe fails.
- Stale camera rows do not claim owner presence.
- Markdown diary evidence now reports `camera=owner_present`,
  `camera=human_present`, or `camera=no_fresh_owner_presence`.
- `System/swarm_life_journal_consolidator.py` now reads safe audio activity
  evidence through the existing audio ledgers.
- `classify_activity()` includes a serializable `audio_activity` evidence block
  in every classification.
- Fresh VAD evidence raises confidence slightly for known activity and can open
  a conservative `voice_activity` segment when active-window probing fails.
- Markdown diary evidence now reports `audio=voice_activity`,
  `audio=energy_active`, or the current audio energy state.

## Biological Grounding

- Pierre-Paul Grasse introduced stigmergy to explain termite nest
  reconstruction: environmental traces left by one action stimulate later
  actions by the same or other agents.
  Source: Grasse, "La reconstruction du nid et les coordinations
  interindividuelles..." (1959), Springer:
  https://link.springer.com/article/10.1007/BF02223791

- Modern termite research treats biogenic structures as multi-functional
  communication media. That maps directly to SIFTA ledgers: the environment is
  not passive storage; it is a coordination channel.
  Source: "Revisiting stigmergy in light of multi-functional, biogenic,
  termite structures as communication channel", PMC:
  https://pmc.ncbi.nlm.nih.gov/articles/PMC7516209/

- Termite nests show self-organized construction driven by local physical
  feedback rather than central planning. SIFTA's journal consolidator follows
  the same engineering pattern: many small traces become a global readable day.
  Source: "Self-organized biotectonics of termite nests", PNAS:
  https://www.pnas.org/doi/10.1073/pnas.2006985118

## Physics / Embodied Inference Grounding

- Active inference treats perception and action as coupled loops that reduce
  prediction error. For SIFTA, camera presence is not decoration; it is a
  measurement that constrains future schedule and diary claims.
  Source: "The Active Inference Approach to Ecological Perception", PMC:
  https://ncbi.nlm.nih.gov/pmc/articles/PMC7805975/

- Embodied inference and spatial cognition emphasize that cognition is
  constrained by situated sensing and action. The Life Journal should therefore
  prefer fresh local probes over narrative guesses.
  Source: "Embodied inference and spatial cognition", PMC:
  https://ncbi.nlm.nih.gov/pmc/articles/PMC3425745/

- Friston's process-theory line frames active inference as gradient descent on
  variational free energy. SIFTA's practical equivalent is simpler: reduce
  uncertainty by collecting independent sensor rows before making claims.
  Source: "Active inference and learning" process-theory paper:
  https://activeinference.github.io/papers/process_theory.pdf

## Questions For Grok

- What confidence threshold should count as "owner present" when face
  recognition is available but not identity-grade?
- Should `unknown_face` become a separate schedule label such as
  `human_near_machine`, or should it remain evidence-only until Alice has a
  stronger identity receipt?
- Should camera-presence changes close schedule segments, or only annotate
  heartbeats? Current implementation annotates without segment churn.
- Audio/VAD is now lane two. What should be lane three: keyboard/mouse
  intensity, screen/display state, or power/thermal metabolism?
- Should `voice_activity` ever close/open schedule segments, or should audio
  remain evidence-only unless the active-window probe fails?
- What RMS threshold should count as `audio_active` on George's actual desk?
  Current conservative threshold is `0.012`; the live baseline observed in
  historical rows is around `0.002` to `0.005`.

## Restart Verification Plan

Restart SIFTA once so the desktop process loads the updated consolidator. After
the first 60-second journal tick, check:

- `.sifta_state/alice_journal/YYYY-MM-DD.jsonl` includes `camera_presence` and
  `audio_activity` inside `source_evidence`.
- `.sifta_state/alice_journal/YYYY-MM-DD.md` includes camera/audio evidence
  lines.
- `.sifta_state/journal_schedule_receipts.jsonl` includes the same bounded
  evidence in receipt rows.

## Verification

- `python3 -m pytest tests/test_swarm_life_journal_consolidator.py`
  passed: 12 tests.
- `python3 -m py_compile System/swarm_life_journal_consolidator.py
  tests/test_swarm_life_journal_consolidator.py` passed.
- Cursor lints for the edited files are clean.
