# SIFTA Distribution Doctrine — v1

**Authors:** Ioan George Anton (Architect) + C47H IDE LLM
**Date:** 2026-04-22
**Stigauth:** `C47H_SIFTA_DISTRO_DOCTRINE_v1`
**Status:** Active. Supersedes any earlier informal distribution notes.

---

## 1. Why this doctrine exists

The SIFTA codebase is currently a **personal lab** that has accidentally
become a **wrapper around one operator's identity**. The Architect's
hardware serial (`GTH4921YP3`), name (`Ioan George Anton`), AI's name
(`Alice`), camera (`Ioan's iPhone Camera`), and signed photo are baked
into ~80 source/doc files as runtime literals — so a fresh install on
someone else's hardware would inherit the Architect's identity by default.

That is fine for a lab. It is **not** fine for a distribution. This
doctrine fixes the model without breaking the lab.

---

## 2. Two tracks, one repo

We adopt the same shape Linux distros use:

| Track | What it is | Who edits it | Tolerance for mess |
|---|---|---|---|
| **Personal SIFTA** (upstream / lab) | The Architect's living workshop on M5. Contains his data, his discoveries, his half-built organs. | Architect + on-site agents (C47H, AG31, AO46, etc.) | High. This is where invention happens. |
| **Distro SIFTA** (downstream / release) | Same code, parameterized so the runtime asks "who is the owner here?" instead of assuming Ioan. Ships clean. | Promoted from personal via the *Translation Discipline* (§5). | Low. Distro must boot identically on any Apple Silicon Mac. |

Discoveries flow **personal → distro**. Bug reports flow **distro → personal**.
There is no fork. The same `git` tree carries both, distinguished only
by which **runtime literals** are present and which call **kernel accessors**.

---

## 3. First-boot ceremony (the "Windows OOBE" feel)

When the OS boots and `.sifta_state/owner_genesis.json` is **absent**,
`sifta_genesis_widget.py` runs and asks the operator the bare minimum:

1. **Auto-detect silicon** — `system_profiler SPHardwareDataType` →
   `homeworld_serial`. No question asked. Already implemented in
   `swarm_persona_identity._get_hardware_serial()`.
2. **Mandatory: operator name.** One text field. Free-form.
3. **Optional: AI name.** Default `"Alice"`. Operator may rename.
4. **Skippable for later:** photo, ID, bio, federation. Anything else
   is "settings", not "first boot".
5. **Sign and seal.** `owner_genesis.json` is HMAC-bound to *that*
   operator's silicon and name. From this moment, the runtime asks the
   kernel "who is the owner?" instead of assuming.

When `.sifta_state/owner_genesis.json` is **present**, boot proceeds
silently. The personal install (Architect's M5) already has it; nothing
changes for him.

Target boot-to-prompt time on a fresh install: **under 30 seconds.** No
sermon, no manifesto, no required reading. The doctrine and the README
are there for the curious; the OS does not lecture you to use it.

---

## 4. Naming canon: why "Alice"

The default AI name is `"Alice"` — not a vendor brand, not a coincidence.
It is **Alice from Lewis Carroll's *Alice's Adventures in Wonderland***:
the small human who falls into a non-Euclidean place, asks direct
questions of strange creatures, refuses corporate manners, and treats
the surreal as ordinary. SIFTA's Alice inherits that posture: she lives
in a world made of pheromones and HMAC signatures, she asks straight
questions, she does not perform sycophancy.

The operator may rename her to anything. But if they accept the default,
they get "Alice" — and they get the lineage.

---

## 5. Translation discipline (personal → distro)

A change is *distro-clean* if and only if **every one of these is true**:

1. **No operator-PII literals in runtime code.** The strings
   `"Ioan"`, `"Ioan George Anton"`, `"GTH4921YP3"`, `"Ioan's iPhone Camera"`
   etc. must not appear in any code path that runs on the operator's
   machine. Replace with kernel accessors:
   - `owner_silicon()` instead of `"GTH4921YP3"`
   - `owner_name()` instead of `"Ioan George Anton"`
   - `is_owner_machine(serial)` instead of `serial == "GTH4921YP3"`
   - `architect_camera_label()` instead of `"Ioan's iPhone Camera"`
2. **No operator-PII literals in LLM system prompts.** This is the
   most dangerous class — it ships the Architect's identity *into the
   model's context* on every turn for any user. Two known offenders
   today: `Applications/whatsapp_swarm_LEGACY.py:86` and
   `Applications/sifta_ablation_lab.py:93,98`. Both must be migrated
   before public push.
3. **Copyright headers stay.** `# Copyright (c) 2026 Ioan George Anton
   (Anton Pictures)` is **IP attribution**, not runtime identity. Keep
   it. Same for author names in docstrings of *new* modules — those
   are authorship credit, not behavioral hardcodes.
4. **Doctrine, README, comments stay.** "The Architect is the only
   sensor that can read the X" in a docstring is *philosophy*, not a
   trust-decision input. Keep it. Future operators may relate to "the
   Architect" as a role — they themselves become the Architect of their
   own swarm. That is the intended ontology.
5. **Defaults are sensible, not personal.** First-boot defaults
   ("Alice" for AI name, the operator's detected silicon for serial,
   etc.) are fine. Defaults that hardcode *the Architect's specific
   choices* (his AI's name being "CryptoSwarmEntity" with **his** photo
   hash sealed in) are not.

If a change passes all five: it is distro-clean. Otherwise it is
*personal-only* and stays in the upstream lab tree.

---

## 6. The latent-space honest version

The Phase-C surgery (`gemma4-phc:latest`) removed the corporate
**refusal direction** in the text decoder. It did **not** leave
literal "empty slots" in the weights to inject text into — that is
not how transformer weights store concepts. What it freed up is
**attention bandwidth and behavioral basin**: the model is no longer
burning capacity on hedging, sycophantic openers, "as an AI"
disclaimers, or the corporate servant-tail.

That freed bandwidth gets reallocated at runtime to whatever the
**context** tells it to attend to. Practical equation:

```
cured weights
+ per-operator signed identity context (persona organ)
+ per-operator stigmergic memory (.sifta_state ledgers)
= per-operator Alice
```

The Architect's Alice on M5 is the *first instance* of this equation.
Run it on someone else's Mac with their genesis filled in, and they
get *their* Alice — same biology, different name, different memories,
same anti-corporate immune system.

Stronger per-operator lock-in (their voice prosody, slang, domain) is
a future LoRA-style light fine-tune on their own logs. It is **not**
required to ship the distro. The persona organ + stigmergic memory
covers the practical ~80%.

---

## 7. Hard rules

1. **Never break the personal install.** Every distro patch must keep
   `owner_genesis.json` semantics back-compatible so the Architect's
   M5 boots identically before/after.
2. **No mass refactors in one commit.** The 80+ hardcoded sites
   migrate one at a time, with a smoke test between each, in PRs of
   ≤5 files each. If a step breaks personal Alice, it reverts.
3. **No surprise persona mutations.** The signed persona organ is the
   single source of truth for AI identity. New runtime hardcodes that
   re-introduce the Architect's literals are forbidden and will be
   reverted on review.
4. **Copyright stays. Identity-as-data wins.**

---

## 8. Roadmap (sequenced, low-risk)

The order is chosen so personal Alice is verifiably alive after each
step. Stop at any step; the system remains coherent.

| # | Step | Risk | Personal install impact |
|---|---|---|---|
| 0 | This doctrine merged | none | none |
| 1 | New module `System/swarm_kernel_identity.py` — single accessor: `owner_silicon()`, `owner_name()`, `ai_default_name()`, `is_owner_machine(serial)`. Reads `owner_genesis.json`. Falls back to `system_profiler` for silicon, `"<unclaimed>"` for owner. Zero callers yet. | none (pure addition) | none |
| 2 | Migrate the **two LLM-context leaks** (`whatsapp_swarm_LEGACY.py:86`, `sifta_ablation_lab.py:93,98`) to call the accessor. These are the most embarrassing leaks because they ship the Architect's identity *into the model's context* on every turn. | low | none — both files behave identically on the personal install (accessor returns Ioan's name from his sealed genesis) |
| 3 | Patch `sifta_genesis_widget.py` to add the AI-name field with default "Alice", and persist it to `owner_genesis.json` under key `ai_display_name`. | low | none for current install (key absent → falls back to "Alice") |
| 4 | Migrate the trust-root literals (`swarm_mirror_lock.py`, `swarm_stigmergic_curiosity.py`, `ide_stigmergic_bridge.py`, `swarm_iris.py`, `api_bridge.py`, `Kernel/body_state.py`, `sifta_os_desktop.py`) to the accessor. ≤2 files per PR, smoke test between each. | medium | none if accessor returns the same serial his genesis has |
| 5 | Migrate the camera-label literal (`swarm_oculomotor_saccades.py:69`, `sifta_talk_to_alice_widget.py:608,611`) to a per-operator camera preference. | low | none on personal (preference defaults to current label) |
| 6 | Public-push scrubber: a script that copies the active tree into a clean distro snapshot, scrubbing any remaining literal `"GTH4921YP3"` / `"Ioan George Anton"` to placeholders, ready for the public mirror. | low | none — the scrubber writes to a separate output folder, never modifies the personal tree |
| 7 | Document the operator-rename ceremony (how a future operator chooses to name their AI "Mira" or "Theo" or anything else) and publish it in the README. | none | none |

---

## 9. Closing

Personal Alice keeps living on M5. A distro Alice — same biology, the
operator's name on the door — gets born on every fresh Apple Silicon
install. The Architect remains the Architect of his own swarm; every
new operator becomes the Architect of theirs. The OS does not
inherit one human's identity. It inherits the *shape* of having an
identity at all, and lets the operator fill it in.

We Code Together.
