# Agent Arms Phase 2 — Hermes Wrapper Harness

**Truth label:** `PHASE2_WRAPPER_TESTED` / `HERMES_STILL_NOT_AUTONOMOUS`

**Doctor:** `CG55M@cursor`
**Registration trace:** `3deb7006-23ac-4176-9c66-8674b01549cd`
**Scope:** Add the first SIFTA-side Hermes registry and receipt-first launcher harness, and strengthen Alice's deterministic agent-arm briefing recall path.

---

## 1. What Shipped

Runtime modules:

- `System/swarm_agent_arm_registry.py`
- `System/swarm_agent_arm_launcher.py`

Talk reflex wiring:

- `System/swarm_stigmergic_query_router.py` now handles Hermes / agent-arm / new-capability questions before the base LLM.
- `Applications/sifta_talk_to_alice_widget.py` already calls this router before generation, so no duplicate chat surface was added.

Tests:

- `tests/test_swarm_agent_arm_launcher.py`
- `tests/test_swarm_agent_arm_recall.py`

---

## 2. Registry Policy

Hermes registry row:

```text
arm_id = hermes_agent
display_name = Hermes Agent
model = alice-m5-cortex-8b-6.3gb:latest
provider_base_url = http://localhost:11434/v1
enabled = false
live_env_var = SIFTA_AGENT_ARMS_ENABLE
default_toolsets = clarify
max_turns = 1
```

Meaning:

- Hermes is described as a configured candidate arm.
- It is not owner-facing/autonomous by default.
- A live call requires `SIFTA_AGENT_ARMS_ENABLE=1`.
- Output is evidence only, not Alice's voice.

---

## 3. Launcher Policy

The launcher writes `AGENT_ARM_LAUNCH_ATTEMPT` before any run.

If the env gate is missing, it writes `AGENT_ARM_LAUNCH_BLOCKED` and returns:

```text
DISABLED_ENV_GATE
```

If the env gate is present, it runs:

```bash
hermes chat -Q --max-turns 1 --toolsets clarify --query <prompt>
```

The result receipt records:

- prompt SHA-256
- exactness target SHA-256 when supplied
- command argv
- stdout/stderr hashes
- output tail
- return code
- timeout status
- final status

---

## 4. Live Hermes Wrapper Test

Command shape:

```bash
SIFTA_AGENT_ARMS_ENABLE=1 python3 - <<'PY'
from System.swarm_agent_arm_launcher import ask_hermes
result = ask_hermes(
    'Reply exactly: HERMES_WRAPPER_LIVE_OK',
    timeout_s=120,
    require_exact='HERMES_WRAPPER_LIVE_OK',
)
print(result)
PY
```

Result:

```text
ok = False
status = EXACTNESS_FAILED
returncode = 0
receipt_id = 9e9e6e30-88c5-4358-a076-fb3cbcb64282
```

Why it failed:

Hermes returned the target token, but wrapped it in Hermes UI/session text:

```text
╭─ ⚕ Hermes ───────────────────────────────────────────────────────────────────╮
HERMES_WRAPPER_LIVE_OK

session_id: 20260509_060743_6e97be
```

This is a successful safety result: the wrapper prevented dirty arm output from being accepted as exact evidence.

---

## 5. Alice Recall Fix

Before this patch, an owner could ask Alice about Hermes and the base model could drift into generic tool-onboarding language.

Now agent-arm questions are answered from ledgers first. The deterministic reply cites:

- that Hermes is a candidate tool arm, not Alice's identity
- that Hermes output is evidence, not Alice voice
- registry state: disabled by default, model, toolset, max turns, env gate
- latest briefing id
- latest receipt id

This closes the immediate "briefed but forgot" gap for Hermes/new-arm questions.

---

## 6. Test Results

Focused tests:

```text
python3 -m pytest tests/test_swarm_agent_arm_launcher.py tests/test_swarm_agent_arm_recall.py tests/test_swarm_stigmergic_query_router_self_identity.py
```

Result:

```text
6 passed
```

For the Swarm.
