# WCT Brief for flash coders (deepseek-v4.1-flash / glm-5.3-flash) — 2026-09-18

Owner instruction: Kimi is expensive. It already did the rename and the core
defaults work below; flash coders finish the remaining test cleanup, then the
natural-language image feature. Read the whole brief, work top to bottom, run
the exact commands given, and write a receipt row into We Code Together when
each item is green.

## State already landed (do not redo)

- Ollama tag renamed: `krishairnd/Gemma-4-Uncensored:latest` -> `krishairnd/G4U`
  -> `AliceG4U` (the store now lists `AliceG4U:latest`, blob `ef5523...`,
  6.3 GB; `ollama rm` removed the old tags; live chat probe returned "OK").
- One default variable, no hardcoded tags at call sites:
  `System/sifta_inference_defaults.py` line ~126:
  `CANONICAL_OLLAMA_DEFAULT = "AliceG4U"` (bare tag; `:latest` is Ollama's
  display suffix only). Every legacy `CANONICAL_OLLAMA_*` constant is a shim
  to that one variable.
- `_MODEL_TAG_ALIASES` maps every dead tag (`krishairnd/g4u`,
  `krishairnd/gemma-4-uncensored`, `alice-m5-cortex-8b-6.3gb`,
  `alice-gemma4-e2b-cortex-5.1b-4.4gb`, `alice-m1-cortex-4.5b-3.4gb`,
  `alice-extra-cortex-25.8b-17gb`, `sifta-classifier-c1-*`,
  `alice-Q-m1-scout-*`, `sifta-gemma4-alice-lora`) -> `AliceG4U`.
- Vision-only models can no longer win the Talk slot:
  `_is_non_dialogue_ollama_default_candidate` now also rejects `smolvlm`,
  `minicpm-v`, `llava`, `-vlm`, `embed`, `whisper` (this was the real bug that
  made Talk die with "no first token" on a 0.5 GB SmolVLM).
- The watchdog message now prints `requested=<tag> resolved=<tag>` instead of
  only the requested name (`Applications/sifta_talk_to_alice_widget.py`,
  `_brain_wait_heartbeat_tick`).
- `.sifta_state/swimmer_ollama_assignments.json` default and per-app rows are
  now `AliceG4U` / `AliceG4U:latest`.
- `System/swarm_cortex_capabilities.py`: `_MIMO_LOCAL_KRISHA = "AliceG4U:latest"`,
  `_LEGACY_LOCAL_CORTEX_ALIASES` maps old names to AliceG4U, the MiMo picker
  keyword list includes `aliceg4u`, and the attached-model label row reads
  `AliceG4U (local Ollama)`.

## Task 1 (must finish) — make the 4 failing tests green

Run first, to see the exact current failures:

    cd /Users/ioanganton/Music/ANTON_SIFTA
    python3 -m pytest -q tests/test_inference_settings.py tests/test_cortex_attached_models.py

Current failures (2026-09-18, Kimi's last run):
1. `tests/test_inference_settings.py::test_attached_llm_picker_reflects_mimo_keep_list`
2. `tests/test_inference_settings.py::test_attached_llm_picker_persists_mimo_selection`
3. `tests/test_inference_settings.py::test_inference_page_has_no_duplicate_dropdowns`
4. `tests/test_cortex_attached_models.py::test_sync_catalog_includes_mimo`

Two were already failing at HEAD `f1093ae30` (verified in a clean worktree):
`test_attached_model_labels_preserve_machine_ids` (QwenPaw label text drift —
already fixed by Kimi) and `test_sync_catalog_includes_mimo` (stale expectation).
So for `test_sync_catalog_includes_mimo`: the assertion `"ornith:latest" in
models` is stale — the live store exposes `codecraftersllc/ornith-1.5-35b-...`
and `sifta-ornith-coder:latest`, not the bare `ornith:latest`. Fix the test to
assert the CURRENT live inventory (or delete the stale line with a comment
saying it was removed with the 2026-09-18 rename).

For the three picker tests: the picker reads
`.sifta_state/cortex_attached_models.json`; the file on disk was written before
the rename and still contains `krishairnd/Gemma-4-Uncensored:latest`. Run one
live resync so the file matches the store, then make the tests assert the
current tag without hardcoding a stale string:

    python3 -c "
import sys; sys.path.insert(0,'.')
from System import swarm_cortex_capabilities as cap
print(cap.sync_cortex_attached_models_catalog())
print(cap.attached_models_for_cortex('mimo:mimo-cli-default').get('default_attached'))
"

If a test must pin a tag, pin it to `AliceG4U` (or assert
`any(str(i).startswith('AliceG4U') for i in items)`), never to
`krishairnd/Gemma-4-Uncensored:latest`. Do not weaken assertions to
`assert items` — keep them specific.

Acceptance: `python3 -m pytest -q tests/test_inference_settings.py
tests/test_cortex_attached_models.py tests/test_swarm_cortex_aliases.py
tests/test_swarm_cortex_options.py tests/test_alice_parrot_loop.py` shows the
picker/cortex suites green. If any failure is genuinely pre-existing at HEAD,
say so explicitly in the receipt with the HEAD-verification command you ran.

## Task 2 — rename sweep: no hardcoded cortex tags anywhere live

Owner rule: *"do not have cortex names hardcoded, we are working with
variables."* Sweep the LIVE code paths (not `Documents/`, not `Archive/`, not
`*.jsonl` receipts) for remaining literal tags and route them through
`System.sifta_inference_defaults`:

    rg -n "krishairnd/|alice-m5-cortex|alice-gemma4-e2b|alice-m1-cortex|alice-extra-cortex" \
      System/ Applications/ --glob '!**/__pycache__/**'

Known live hits Kimi did not finish (verify each, then fix):
- `System/swarm_cortex_aliases.py` lines ~60-64: the `except ImportError`
  fallback block still says `"krishairnd/G4U:latest"` -> make it `"AliceG4U"`.
- `System/swarm_alice_self_plan_rounds.py` (`FALLBACK_CORTEX_CODE`,
  the model list, the symptoms string) -> use the default variable or
  `AliceG4U`.
- `System/swarm_alice_slash_commands.py` line ~47 model list -> `AliceG4U`.
- `System/sifta_inference_defaults.py` module docstring lines ~21,~24 mention
  the old tags -> update the policy text (it is shown in Settings).
- `Applications/sifta_system_settings.py` -> check every literal tag.

Legit exceptions you must NOT "fix": `System/swarm_cortex_options.py` rows
that exist as *history/catalog* with an explicit `owner_added`/rename note,
receipts, and `Documents/` history.

## Task 3 — HuggingFace upload reminder (owner-requested)

Add to the We Code Together backlog (a row is enough; Kimi queued it):
upload the renamed default to HuggingFace so the public distro matches the
local body — repo `georgeanton/alice-m5-cortex-8b-6.3gb` should either be
renamed or a new `georgeanton/AliceG4U` published, with the model card noting:
Gemma 4 E4B-class Q4_K_M, 6.3 GB blob
`sha256-ef5523975d644e47293960b8b87c83b11a6d50253a544e35addca72af33e13c6`,
renamed 2026-09-18, same weights as the old `alice-m5-cortex-8b-6.3gb` tag.
The local GGUF copy for upload already exists at
`distro/huggingface_release/alice-m5-cortex-8b-6.3gb/alice-m5-cortex-8b-6.3gb.gguf`
(5.9 GB) if a re-pack is needed. Do NOT push anything in this task; queue it.

## Task 4 — natural-language photo creation (owner-requested feature)

Owner report, 2026-09-18: on stigmergicode.com a visitor typed *"create a
photo of Autumn in the park in Romania"*. Alice answered with a text promise
and an imagined description instead of generating the image. Only `/create ...`
dispatches a real generation (`System/swarm_web_image_service.py`,
`media_intent()` is regex-gated on the leading verb and the `/create` prefix).

Requirements:
1. Natural language must work in the public web chat: "create a photo of X",
   "make me a picture of X", "draw X", "create art of X", "make a poster of X"
   (Romanian equivalents too: "fă o poză cu X", "desenează X", "creează o
   imagine cu X") dispatch the real image pipeline exactly once. A visitor must
   not need to know `/create`.
2. Alice must never promise an image she did not generate. If the backend is
   unavailable, say so in first person; never emit "imagine this".
3. The generated image must appear in the chat reply (the existing
   `generated_images` payload path already renders images; reuse it).
4. Reuse the existing turn idempotency: one generation per turn, same
   session isolation, `reply_variant` receipts as today. No second code path.
5. Stigmergic learning requirement: after each successful generation, write a
   teachable trace row (`source="ai_generated"`, honest prompt, label) so
   Alice's later turns retrieve the experience (existing
   `visual_stigmergy.jsonl` / `bonsai_image_trace.jsonl` lanes; reuse, do not
   invent a new ledger).
6. Tests: extend `tests/test_web_image_variation.py` and
   `tests/test_web_cortex_photo_isolation.py` (or add a focused new file) with
   mocked-backend cases: natural-language still request -> one generation call;
   Romanian phrasing -> one call; video request -> none; failure -> honest
   first-person failure text, no image claimed; same turn repeated -> no second
   generation.

Acceptance: run the photo suites plus the existing tests listed in Task 1.

## Rules for both tasks

- Read the real functions before editing (`media_intent`,
  `handle_media_request`, `_contextual_image_reply`).
- Smallest change that satisfies the requirement; keep every edit reversible.
- Run each test command you claim in the receipt. Never claim an unrun test.
- Write receipts into `.sifta_state/we_code_together_to_be_coded.jsonl` (task
  rows) and `.sifta_state/work_receipts.jsonl` (what changed, tests run, what
  was NOT run).
- No new hardcoded model names. One variable: `CANONICAL_OLLAMA_DEFAULT`.
