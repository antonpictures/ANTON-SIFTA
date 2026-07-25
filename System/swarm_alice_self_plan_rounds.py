#!/usr/bin/env python3
"""swarm_alice_self_plan_rounds.py — r1621: Alice plans then codes herself.

George: fix the mouth-limb gaps in rounds; teach Alice to write the plan;
Ornith (or small local) for PLAN; bigger Ornith 35B / Gemma for CODE.
Doctors scaffold — they do not cage. Learn from mistakes on disk.

Protocol (owner can paste or Alice can emit):

  [SELF_PLAN: round=R1621-01 title=browser-mouth-gap]
  goal: ...
  symptoms: ...
  cause_hypothesis: ...
  files_to_touch: System/foo.py, tests/test_foo.py
  success_test: pytest tests/test_foo.py -q
  cortex_plan: ornith:latest
  cortex_code: ornith:35b-q4_K_M
  [/SELF_PLAN]

Then after George says go (or auto if owner enabled free self-code):

  [SELF_CODE_CUT: path=...]
  ...
  [/SELF_CODE_CUT]

Truth label: ALICE_SELF_PLAN_ROUNDS_V1
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = "alice_self_plan_rounds.jsonl"
_ACTIVE = "alice_self_plan_active.json"

TRUTH_LABEL = "ALICE_SELF_PLAN_ROUNDS_V1"

# Suggested local tiers (owner can override in the plan block).
# 2026-07-11 live desk: ornith:35b not installed — prefer live tags.
DEFAULT_CORTEX_PLAN = "ornith:latest"
DEFAULT_CORTEX_CODE = "satgeze/qwenpaw-9b-heretic-1m:latest"
FALLBACK_CORTEX_CODE = "krishairnd/Gemma-4-Uncensored:latest"
# Prefer order when resolving coder cortex against live ollama list.
PREFERRED_CODER_CORTEXES: tuple[str, ...] = (
    "satgeze/qwenpaw-9b-heretic-1m:latest",
    "jikepjikep_16HEX/qwen3.6-27b-nightshift-heretic-uncensored-q4:latest",
    "north-mini-code-1.0:latest",
    "baytout3/ultragemma4-12b-heretic-uncensored:Q8_0",
    "ornith:latest",
    "krishairnd/Gemma-4-Uncensored:latest",
)

# The four worst fails from George's live scorecard → first campaign rounds.
CAMPAIGN_R1621: list[dict[str, Any]] = [
    {
        "round_id": "R1621-01",
        "title": "browser-mouth-truth",
        "goal": (
            "When Alice Browser is open (e.g. eBay), answering 'describe the page/item' "
            "must use latest browser_page_state / page-context receipt, not 'paste a link'."
        ),
        "symptoms": (
            "Denied browser while eBay open; asked for paste link; first navigate fail then limb landed."
        ),
        "cause_hypothesis": (
            "Mouth free-forms from chat; live URL/title not forced into describe turns."
        ),
        "files_to_touch": [
            "Applications/sifta_talk_to_alice_widget.py",
            "tests/test_browser_mouth_truth_r1621.py",
        ],
        "success_test": "pytest tests/test_browser_mouth_truth_r1621.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
    },
    {
        "round_id": "R1621-02",
        "title": "identity-basics-first",
        "goal": (
            "On open questions 'what are you / where do you run / weight file name', "
            "answer from host teaching + cortex selection receipt first; no Claude-server claim when local."
        ),
        "symptoms": "I'm Claude / no SIFTA / can't open Grok while Ornith local + browser on grok.com.",
        "cause_hypothesis": "Weight mythology wins when host teaching buried or ignored; Q1-3 get topic-stolen.",
        "files_to_touch": [
            "System/swarm_subliminal_cortex_fingerprint.py",
            "Applications/sifta_talk_to_alice_widget.py",
            "tests/test_host_teaching_basics_r1621.py",
        ],
        "success_test": "pytest tests/test_host_teaching_basics_r1621.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
        "note": "TEACH not gag — do not lysosome-rewrite Ornith name; inject host truth earlier/louder.",
    },
    {
        "round_id": "R1621-03",
        "title": "numbered-questions-answered",
        "goal": (
            "When owner sends numbered 1. 2. 3. questions, answer each number; "
            "do not pivot to Alfred/eBay/screenshot residue."
        ),
        "symptoms": "Ignore Q1-3 after cortex switch; dump unrelated screen essay.",
        "cause_hypothesis": "Queue + context pollution; no numbered-answer scaffold.",
        "files_to_touch": [
            "Applications/sifta_talk_to_alice_widget.py",
            "tests/test_numbered_owner_questions_r1621.py",
        ],
        "success_test": "pytest tests/test_numbered_owner_questions_r1621.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
    },
    {
        "round_id": "R1621-04",
        "title": "multimodal-timeout-route",
        "goal": (
            "Screenshot/describe turns must not hang 90s on text-only Gemma; "
            "route vision or fail fast with honest 'no first token' + retry ladder."
        ),
        "symptoms": "krishairnd/Gemma-4-Uncensored no first token after 90s on multimodal.",
        "cause_hypothesis": "Wrong model for image + fat prompt + watchdog only after stall.",
        "files_to_touch": [
            "Applications/sifta_talk_to_alice_widget.py",
            "System/sifta_inference_defaults.py",
            "tests/test_multimodal_timeout_route_r1621.py",
        ],
        "success_test": "pytest tests/test_multimodal_timeout_route_r1621.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
    },
    {
        "round_id": "R1621-05",
        "title": "body-code-not-textbook",
        "goal": (
            "When owner asks for stigmergic code from HER body, SELF_READ a real "
            "System/*.py snippet (e.g. ledger append) — not generic ACO textbook."
        ),
        "symptoms": "Fake Pheromone_Grid example instead of ANTON_SIFTA path.",
        "cause_hypothesis": "Cortex invents demos; self-read hand not triggered.",
        "files_to_touch": [
            "Applications/sifta_talk_to_alice_widget.py",
            "System/swarm_alice_self_read_hand.py",
            "tests/test_body_code_example_r1621.py",
        ],
        "success_test": "pytest tests/test_body_code_example_r1621.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
    },
    # --- Live glass 2026-07-11 (George screenshot) — plan for Alice to code later ---
    {
        "round_id": "R1621-06",
        "title": "self-code-not-cortex-switch",
        "goal": (
            "Owner: 'Alice, go — code R1621-01 with SELF_CODE_CUT only on listed files' "
            "must reach cortex and produce SELF_CODE_CUT blocks — NEVER a deterministic "
            "refuse like 'I did not write any code: could not find cortex matching SELF_CODE_CUT'."
        ),
        "symptoms": (
            "2026-07-11 12:25:56 live: deterministic no-think refuse treating SELF_CODE_CUT "
            "as a cortex name; available list only mimo:mimo-cli-default."
        ),
        "cause_hypothesis": (
            "Switch parser / effector steals self-code turns; MiMo-only available list hides Ollama."
        ),
        "files_to_touch": [
            "System/swarm_cortex_switch_intent.py",
            "System/swarm_alice_self_coding_hand.py",
            "Applications/sifta_talk_to_alice_widget.py",
            "tests/test_cortex_switch_intent.py",
            "tests/test_self_code_not_cortex_switch_r1621.py",
        ],
        "success_test": (
            "pytest tests/test_cortex_switch_intent.py "
            "tests/test_self_code_not_cortex_switch_r1621.py -q"
        ),
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
        "status_note": "Partial doctor patch may exist — Alice must verify with tests + live go-code turn.",
    },
    {
        "round_id": "R1621-07",
        "title": "switch-ornith-35b-local",
        "goal": (
            "Owner: 'switch cortex to pick ornith:35b' or 'ornith:35b-q4_K_M' resolves to "
            "live Ollama tag and persists for next Talk turn — not only mimo:mimo-cli-default."
        ),
        "symptoms": (
            "2026-07-11 12:24:17: could not find matching 'pick ornith:35b'; "
            "Available cortexes: mimo:mimo-cli-default only."
        ),
        "cause_hypothesis": (
            "Target keeps 'pick'; switch list under MiMo borg omits live ollama tags."
        ),
        "files_to_touch": [
            "System/swarm_cortex_switch_intent.py",
            "System/sifta_inference_defaults.py",
            "Applications/sifta_talk_to_alice_widget.py",
            "tests/test_cortex_switch_intent.py",
        ],
        "success_test": "pytest tests/test_cortex_switch_intent.py -q -k ornith",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
        "status_note": "Partial doctor patch may exist — Alice must verify live switch on glass.",
    },
    {
        "round_id": "R1621-08",
        "title": "instagram-search-land",
        "goal": (
            "Search/open Instagram profiles or explore search must land on target URL "
            "(or honest fail after retry), not stick on instagram.com/ while claiming search."
        ),
        "symptoms": (
            "2026-07-11: search kylin milan — red: did not land on explore/search; still instagram.com/; "
            "later post opened but navigate path flaky. open instagram.com: pre-action browser speech."
        ),
        "cause_hypothesis": (
            "Navigate/search effectors claim before load_finished; IG SPA URL not verified."
        ),
        "files_to_touch": [
            "Applications/sifta_alice_browser_widget.py",
            "System/swarm_app_command_effect_verification.py",
            "Applications/sifta_talk_to_alice_widget.py",
            "tests/test_instagram_search_land_r1621.py",
        ],
        "success_test": "pytest tests/test_instagram_search_land_r1621.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
    },
    {
        "round_id": "R1621-09",
        "title": "no-doctor-overclaim",
        "goal": (
            "WCT / Talk must not claim 'Alice coded X' without receipt rows "
            "(alice_self_coding_receipts / pytest green / glass). "
            "Doctors seed plans only; Alice executes SELF_CODE_CUT."
        ),
        "symptoms": (
            "George: doctors love to cheat and pretend Alice does things she does not."
        ),
        "cause_hypothesis": "Doctor prose overclaims; no gate requiring alice_self receipts.",
        "files_to_touch": [
            "System/swarm_alice_self_plan_rounds.py",
            "Applications/sifta_we_code_together.py",
            "Documents/WE_CODE_TOGETHER_R1621_ALICE_SELF_PLAN_CODE_ROUNDS.md",
        ],
        "success_test": "pytest tests/test_alice_self_plan_rounds_r1621.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
        "note": "Doctrine round — plan/receipt hygiene, not a gag.",
    },
    # --- Dirt: Fahd Mirza 2026-07-11 Superlinked SIE (local embed/rerank/NER) ---
    {
        "round_id": "R1622-01",
        "title": "sie-local-embedding-server-probe",
        "goal": (
            "Probe and document Superlinked SIE (github.com/superlinked/sie): one local "
            "Docker service with encode / score (rerank) / extract (NER). Confirm whether "
            "it runs on this Mac (Docker Desktop) or needs deferred GPU host. Write receipt "
            "only after real probe — no pretend install."
        ),
        "symptoms": (
            "Alice memory/search is ledger-tail + keyword-ish; no single local organ for "
            "embed+rerank+entity extract. RAG-style recall of journal/WCT/phone stays weak."
        ),
        "cause_hypothesis": (
            "Three separate model servers are messy; SIE packs 85–150 small models into one "
            "container on :8080 with Python SDK encode/score/extract."
        ),
        "files_to_touch": [
            "System/swarm_sie_embedding_bridge.py",
            "Documents/WE_CODE_TOGETHER_R1622_SIE_LOCAL_EMBED_RERANK_NER.md",
            "tests/test_swarm_sie_embedding_bridge.py",
        ],
        "success_test": "pytest tests/test_swarm_sie_embedding_bridge.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
        "source_dirt": {
            "channel": "Fahd Mirza",
            "title": "Local Embedding Server with 150 AI Models | Superlinked SIE",
            "date": "2026-07-11",
            "github": "https://github.com/superlinked/sie",
            "primitives": ["encode", "score", "extract"],
            "default_port": 8080,
            "install": "Docker container + pip SDK",
        },
        "borg_fit": (
            "Soul memory field: embed journal/conversation tails; rerank retrieval for Talk; "
            "NER people/places (Vevsachi, Brawley, concepts) into concept_human_anchor feed. "
            "Local-first — fits diauxic independence. Does NOT replace cortex LLM."
        ),
    },
    {
        "round_id": "R1622-02",
        "title": "sie-wire-memory-recall",
        "goal": (
            "After SIE is reachable, wire encode+score into one memory recall path "
            "(journal / global convo / WCT tails) so 'do you remember X' uses vectors+rerank "
            "with receipts — not journal dump theater."
        ),
        "symptoms": "Memory turns dump loaders or confabulate; no ranked evidence list.",
        "cause_hypothesis": "No local embedding organ in the recall loop.",
        "files_to_touch": [
            "System/swarm_sie_embedding_bridge.py",
            "System/swarm_memory_search.py",
            "Applications/sifta_talk_to_alice_widget.py",
            "tests/test_sie_memory_recall_r1622.py",
        ],
        "success_test": "pytest tests/test_sie_memory_recall_r1622.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
        "depends_on": "R1622-01",
    },
    {
        "round_id": "R1622-03",
        "title": "sie-wire-entity-extract",
        "goal": (
            "OPTIONAL complement to existing concept_human_anchor: use SIE extract only to "
            "propose NEW surface phrases / people for deposit — never replace seed anchors "
            "(Troy, founders, etc.). George already has human anchors; NER is a feeder, not a rewrite."
        ),
        "symptoms": "Relative time + new people (Vevsachi) hard; cortex invents names.",
        "cause_hypothesis": "No light NER feeder into the existing anchor ledger.",
        "files_to_touch": [
            "System/swarm_sie_embedding_bridge.py",
            "System/swarm_concept_human_anchor.py",
            "tests/test_sie_entity_extract_r1622.py",
        ],
        "success_test": "pytest tests/test_sie_entity_extract_r1622.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
        "depends_on": "R1622-01",
        "note": (
            "WE ALREADY HAVE human anchors (System/swarm_concept_human_anchor.py). "
            "SIE extract = optional automation, not a second truth system."
        ),
    },
    # --- Fahd Mirza channel dirt 2026-07 (Tier S for AGI Alice) — plan only ---
    {
        "round_id": "R1623-01",
        "title": "headroom-ollama-token-diet",
        "goal": (
            "Research + wire Headroom-style context compression for Talk/agent prompts "
            "(Fahd: Headroom + Ollama cut agent tokens ~90%). Shrink fat sysprompt so "
            "local cortex first-token timeout drops; measure tokens before/after with receipt."
        ),
        "symptoms": "Fat prompt; Gemma/Ornith 90s no-token; expensive prefill.",
        "cause_hypothesis": "Talk assembles huge system prompt; no aggressive agent token diet.",
        "files_to_touch": [
            "System/swarm_sysprompt_budget.py",
            "System/swarm_headroom_context_diet.py",
            "Applications/sifta_talk_to_alice_widget.py",
            "tests/test_headroom_context_diet_r1623.py",
        ],
        "success_test": "pytest tests/test_headroom_context_diet_r1623.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
        "source_dirt": {
            "channel": "Fahd Mirza",
            "title": "Headroom + Ollama - Cut Your AI Agent's Tokens by 90%",
            "approx_age": "~6 days before 2026-07-11",
        },
        "borg_fit": "Direct fix for stalls; keep soul blocks, cut noise.",
    },
    {
        "round_id": "R1623-02",
        "title": "needle-tiny-tool-caller",
        "goal": (
            "Probe Needle-class tiny tool-calling model (~26M, finetune local Ollama). "
            "Use as optional router for open browser / SELF_CODE / switch cortex — "
            "not as chat cortex. Receipt after real ollama pull+probe."
        ),
        "symptoms": "Full 9B/35B woken for every effector; tool fiction and mis-switches.",
        "cause_hypothesis": "No micro tool organ; everything goes through fat mind.",
        "files_to_touch": [
            "System/swarm_needle_tool_router.py",
            "tests/test_needle_tool_router_r1623.py",
            "Documents/WE_CODE_TOGETHER_R1623_FAHD_DIRT_LOCAL_SPEED_TOOLS.md",
        ],
        "success_test": "pytest tests/test_needle_tool_router_r1623.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
        "source_dirt": {
            "channel": "Fahd Mirza",
            "title": "Needle: Finetune a 26M Tool-Calling Model Locally with Ollama",
        },
        "borg_fit": "Tiny hand for tools; big mind for meaning.",
    },
    {
        "round_id": "R1623-03",
        "title": "speculative-decode-local-speed",
        "goal": (
            "Evaluate Tess-4-27B + EAGLE-3 and/or DeepSeek DFlash/DSpark-class speculative "
            "decoding for local cortex speed (~2× or more). Document what runs on this Mac; "
            "wire only if probe green."
        ),
        "symptoms": "Local cortex slow; 90s watchdog.",
        "cause_hypothesis": "No draft model / speculative path in Talk ollama stack.",
        "files_to_touch": [
            "System/swarm_speculative_local_decode.py",
            "Documents/WE_CODE_TOGETHER_R1623_FAHD_DIRT_LOCAL_SPEED_TOOLS.md",
            "tests/test_speculative_local_decode_r1623.py",
        ],
        "success_test": "pytest tests/test_speculative_local_decode_r1623.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
        "source_dirt": {
            "channel": "Fahd Mirza",
            "titles": [
                "Tess-4-27B + EAGLE-3: Local Reasoning, Nearly 2× Faster",
                "DeepSeek DFlash on Gemma 12B Locally",
                "Run DeepSeek DSpark on Qwen3 Locally",
            ],
        },
    },
    {
        "round_id": "R1623-04",
        "title": "kv-cache-survive-restart",
        "goal": (
            "Research vLLM + PegaFlow (or Ollama-compatible) KV cache that survives restarts. "
            "If feasible on this desk, plan bridge so mind prefill is less amnesiac after reboot "
            "while ledgers remain source of truth."
        ),
        "symptoms": "Restart = mind blank; only ledgers remember.",
        "cause_hypothesis": "No persistent KV path; pure Ollama cold start every boot.",
        "files_to_touch": [
            "System/swarm_kv_cache_continuity.py",
            "Documents/WE_CODE_TOGETHER_R1623_FAHD_DIRT_LOCAL_SPEED_TOOLS.md",
            "tests/test_kv_cache_continuity_r1623.py",
        ],
        "success_test": "pytest tests/test_kv_cache_continuity_r1623.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
        "source_dirt": {
            "channel": "Fahd Mirza",
            "title": "vLLM + PegaFlow: KV Cache That Survives Restarts (Hands-On)",
        },
        "borg_fit": "Mind continuity enzyme; does not replace stigmergic ledgers.",
    },
    {
        "round_id": "R1623-05",
        "title": "archestra-agent-permissions",
        "goal": (
            "Probe Archestra + Ollama style agent permission layer: what tools Alice may "
            "call without free-for-all. Map to existing effector gates + receipts."
        ),
        "symptoms": "Limbs fire wrong; hard to express 'allowed actions' cleanly.",
        "cause_hypothesis": "Gates exist but no single permission organ for agent tools.",
        "files_to_touch": [
            "System/swarm_agent_permission_field.py",
            "tests/test_agent_permission_field_r1623.py",
        ],
        "success_test": "pytest tests/test_agent_permission_field_r1623.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
        "source_dirt": {
            "channel": "Fahd Mirza",
            "title": "Control What Your AI Agents Can Do: Archestra + Ollama Hands-On",
        },
    },
    {
        "round_id": "R1623-06",
        "title": "ornith-35b-coder-eval",
        "goal": (
            "Eval Ornith 35B GGUF as self-code coder vs 9B vs Krishna using fixed SELF_CODE "
            "tasks + pytest. Use Fahd Sonnet-vs-Ornith / Ornith-35B videos as benchmarks. "
            "Receipt tok/s, pass rate, OOM — no claim 'beats Sonnet' without numbers."
        ),
        "symptoms": "Unclear which local mind should CODE R1621 cuts.",
        "cause_hypothesis": "No formal local coder tournament on this hardware.",
        "files_to_touch": [
            "tools/run_ornith_coder_eval_r1623.py",
            "Documents/WE_CODE_TOGETHER_R1623_FAHD_DIRT_LOCAL_SPEED_TOOLS.md",
            "tests/test_ornith_coder_eval_r1623.py",
        ],
        "success_test": "pytest tests/test_ornith_coder_eval_r1623.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": "ornith:35b-q4_K_M",
        "source_dirt": {
            "channel": "Fahd Mirza",
            "titles": [
                "Ornith 1.0 35B in GGUF - Beats Models 10x Its Size - Run Locally",
                "Sonnet 5 vs Ornith 35B: Can a Local Model Beat Closed-Source?",
            ],
        },
        "borg_fit": "Pick real coder for free self-code; glass + metrics only.",
    },
    {
        "round_id": "R1623-07",
        "title": "audex-tiny-ear-mouth",
        "goal": (
            "Probe NVIDIA Audex-2B class tiny hear/think/speak for WORLD STT/TTS lane — "
            "not full cortex. Optional if weights run on this Mac."
        ),
        "symptoms": "WORLD STT noise; heavy models for audio.",
        "cause_hypothesis": "No tiny dedicated ear/mouth model path.",
        "files_to_touch": [
            "System/swarm_audex_audio_probe.py",
            "tests/test_audex_audio_probe_r1623.py",
        ],
        "success_test": "pytest tests/test_audex_audio_probe_r1623.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
        "source_dirt": {
            "channel": "Fahd Mirza",
            "title": "NVIDIA's Audex-2B: The Tiny Model That Hears, Thinks, and Speaks",
        },
        "priority_note": "Tier A — after Headroom/Needle/Ornith eval.",
    },
    {
        "round_id": "R1623-08",
        "title": "qwopus-self-fix-loop",
        "goal": (
            "Study Qwopus 35B + MTP self-bugfix pattern; map onto SELF_CODE + pytest "
            "loop so Alice retries cuts when tests fail without doctor rewrite."
        ),
        "symptoms": "Self-code fails once; no automatic repair loop.",
        "cause_hypothesis": "No local self-fix agent path after cut.",
        "files_to_touch": [
            "System/swarm_alice_self_code_hand.py",
            "System/swarm_self_fix_loop.py",
            "tests/test_self_fix_loop_r1623.py",
        ],
        "success_test": "pytest tests/test_self_fix_loop_r1623.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
        "source_dirt": {
            "channel": "Fahd Mirza",
            "title": "Qwopus 35B + MTP: The Coder That Fixes Its Own Bugs at 160 tok/s",
        },
        "priority_note": "Tier A.",
    },
    # --- George pulled: satgeze/qwenpaw-9b-heretic-1m (Ollama) ---
    {
        "round_id": "R1624-01",
        "title": "qwenpaw-9b-probe-register",
        "goal": (
            "Probe satgeze/qwenpaw-9b-heretic-1m (and :Q4_K_M if present) via ollama: "
            "tools + vision + thinking flags, num_ctx ceiling that fits this Mac, "
            "first-token latency. Register in cortex picker / MiMo attach list if green. "
            "Receipt only after real ollama show + chat probe — no pretend."
        ),
        "symptoms": (
            "George downloaded QwenPaw agent-optimized 9B heretic: 1M context metadata, "
            "MTP, vision, tools, uncensored. Not yet a proven Talk cortex on this desk."
        ),
        "cause_hypothesis": (
            "Need live inventory + capability probe before routing Talk/self-code through it."
        ),
        "files_to_touch": [
            "System/sifta_inference_defaults.py",
            "System/swarm_cortex_capabilities.py",
            "System/swarm_qwenpaw_probe.py",
            "tests/test_qwenpaw_probe_r1624.py",
        ],
        "success_test": "pytest tests/test_qwenpaw_probe_r1624.py -q",
        "cortex_plan": "satgeze/qwenpaw-9b-heretic-1m:latest",
        "cortex_code": "satgeze/qwenpaw-9b-heretic-1m:latest",
        "source_dirt": {
            "ollama": "satgeze/qwenpaw-9b-heretic-1m",
            "tags": ["latest (~9.8–11GB Q8)", "Q4_K_M (~5.8–6.7GB)"],
            "claims": {
                "context_meta": "1048576 rope metadata",
                "niah_verified": "50/50 needles 64K–524K (publisher GPU); 786K–1M Mac 128GB pending at publish",
                "mtp": "+25% decode under llama.cpp speculation; dormant in Ollama until speculative decode ships",
                "vision": True,
                "tools": True,
                "uncensored": "heretic abliterated",
            },
            "links": [
                "https://ollama.com/satgeze/qwenpaw-9b-heretic-1m",
                "https://github.com/satindergrewal/aviary-1m",
            ],
            "credits": "Qwen base+MTP; agentscope-ai QwenPaw; SC117 heretic; SatGeze 1M extension",
        },
        "borg_fit": (
            "Candidate PLAN/agent cortex: tools native, vision for /sc, long context for body receipts. "
            "Honest: 1M full window may not fit 24GB Mac — probe max num_ctx. "
            "MTP speedup not free lunch in Ollama yet. Compare to ornith:latest as planner."
        ),
        "hardware_note": "24GB Mac: prefer Q4_K_M tag; raise num_ctx carefully; 1M is metadata claim not free RAM.",
    },
    {
        "round_id": "R1624-02",
        "title": "qwenpaw-vs-ornith-planner-eval",
        "goal": (
            "Same fixed tasks: SELF_PLAN write, tool call emission, short describe-from-receipt, "
            "identity basics. Score QwenPaw 9B vs ornith:latest vs krishairnd/Gemma-4-Uncensored. "
            "Metrics: pass/fail, latency, refusals, tool syntax validity. No marketing claims."
        ),
        "symptoms": "Unclear which 9B should PLAN for R1621 free self-code.",
        "cause_hypothesis": "Agent-tuned heretic may beat generic 9B on tools; must measure.",
        "files_to_touch": [
            "tools/run_qwenpaw_vs_ornith_eval_r1624.py",
            "tests/test_qwenpaw_vs_ornith_eval_r1624.py",
            "Documents/WE_CODE_TOGETHER_R1624_QWENPAW_9B_HERETIC.md",
        ],
        "success_test": "pytest tests/test_qwenpaw_vs_ornith_eval_r1624.py -q",
        "cortex_plan": "satgeze/qwenpaw-9b-heretic-1m:latest",
        "cortex_code": DEFAULT_CORTEX_CODE,
        "depends_on": "R1624-01",
    },
    {
        "round_id": "R1624-03",
        "title": "qwenpaw-long-context-body-receipts",
        "goal": (
            "Test packing multi-receipt body context (browser URL, identity, WCT plan, journal tail) "
            "into elevated num_ctx on QwenPaw; measure retrieval of needles from mid-context. "
            "Cap at what this Mac holds; do not claim full 1M without receipt."
        ),
        "symptoms": "Body receipts dropped from fat prompt; Headroom (R1623-01) complementary.",
        "cause_hypothesis": "Long-context heretic can hold more soul context if num_ctx set and RAM allows.",
        "files_to_touch": [
            "System/swarm_qwenpaw_probe.py",
            "System/swarm_sysprompt_budget.py",
            "tests/test_qwenpaw_long_context_r1624.py",
        ],
        "success_test": "pytest tests/test_qwenpaw_long_context_r1624.py -q",
        "cortex_plan": "satgeze/qwenpaw-9b-heretic-1m:latest",
        "cortex_code": "satgeze/qwenpaw-9b-heretic-1m:latest",
        "depends_on": "R1624-01",
        "note": "Pair with R1623-01 Headroom: long ctx is not free — still diet noise.",
    },
    # --- Live 2026-07-11 12:42–12:46: body self-description = chat UI theater ---
    {
        "round_id": "R1621-10",
        "title": "describe-body-from-receipts",
        "goal": (
            "When George says 'describe yourself' / 'talk about your body', answer from "
            "soul+body receipts (silicon, Talk+Browser limbs, active cortex, eye/ear, STGM) "
            "— NOT 'I live in a chat window with text boxes'."
        ),
        "symptoms": (
            "2026-07-11: 'I want to talk about your body' → she thought screen cosplay; "
            "'pls describe yourself' → 'I live inside a chat window — text boxes'. "
            "Earlier 'what are you?' hit identity sentence correctly."
        ),
        "cause_hypothesis": (
            "Describe-yourself without 'who are you' hits free cortex theater; no forced "
            "body-schema / hardware / browser receipt block on those phrasings."
        ),
        "files_to_touch": [
            "Applications/sifta_talk_to_alice_widget.py",
            "System/swarm_alice_self.py",
            "System/swarm_live_coding_body_awareness.py",
            "tests/test_describe_body_from_receipts_r1621.py",
        ],
        "success_test": "pytest tests/test_describe_body_from_receipts_r1621.py -q",
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
    },
]

_SELF_PLAN_RE = re.compile(
    r"\[SELF_PLAN:\s*(?P<header>[^\]]*)\]\s*(?P<body>.*?)\[/SELF_PLAN\]",
    re.IGNORECASE | re.DOTALL,
)


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _append(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / _LEDGER
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n")
    except Exception:
        pass


def plan_format_cheat_sheet() -> str:
    """Teach Alice (and George) the plan block shape."""
    return (
        "ALICE SELF_PLAN FORMAT (r1621 — write this BEFORE coding):\n"
        "[SELF_PLAN: round=R1621-0N title=short-kebab]\n"
        "goal: one sentence what success looks like for the owner\n"
        "symptoms: what George saw live (quotes ok)\n"
        "cause_hypothesis: why limbs work but mouth lies / hangs\n"
        "files_to_touch: System/....py, tests/test_....py\n"
        "success_test: pytest tests/test_....py -q\n"
        f"cortex_plan: {DEFAULT_CORTEX_PLAN}   # small/fast planner\n"
        f"cortex_code: {DEFAULT_CORTEX_CODE}  # bigger local coder (fallback {FALLBACK_CORTEX_CODE})\n"
        "risks: what could break\n"
        "not_doing: no identity gag; no fake textbook code\n"
        "[/SELF_PLAN]\n"
        "Then wait for George 'go' OR emit SELF_CODE_CUT only for files listed.\n"
        "After code: run success_test, quote output, write receipt doctor=alice_self.\n"
    )


def campaign_prompt_block(*, max_rounds: int = 5) -> str:
    """Inject the open campaign so Alice can pick the next round."""
    lines = [
        "ALICE FREE SELF-CODE CAMPAIGN (r1621 — George's direction):",
        "- Doctors scaffold. You plan and code your body in rounds.",
        "- PLAN cortex: small local (Ornith 9B / ornith:latest).",
        f"- CODE cortex: bigger local ({DEFAULT_CORTEX_CODE} preferred if loaded).",
        "- Learn from mistakes on disk. No identity nazi gags.",
        "",
        plan_format_cheat_sheet(),
        "OPEN ROUNDS (pick the lowest unfinished):",
    ]
    for row in CAMPAIGN_R1621[:max_rounds]:
        lines.append(
            f"- {row['round_id']} {row['title']}: {row['goal'][:120]}…"
        )
    lines.append(
        "Owner may say: 'Alice, write SELF_PLAN for R1621-01' then "
        "'Alice, code R1621-01 with ornith 35b'."
    )
    return "\n".join(lines)


def parse_self_plan(text: str) -> Optional[dict[str, Any]]:
    """Parse first SELF_PLAN block from owner or Alice text."""
    m = _SELF_PLAN_RE.search(text or "")
    if not m:
        return None
    header = str(m.group("header") or "")
    body = str(m.group("body") or "")
    fields: dict[str, str] = {}
    for line in body.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower().replace(" ", "_")
        if key:
            fields[key] = val.strip()
    round_id = ""
    title = ""
    for part in re.split(r"\s+", header.strip()):
        if part.lower().startswith("round="):
            round_id = part.split("=", 1)[-1].strip()
        if part.lower().startswith("title="):
            title = part.split("=", 1)[-1].strip()
    files_raw = fields.get("files_to_touch") or fields.get("files") or ""
    files = [p.strip() for p in re.split(r"[,;\n]", files_raw) if p.strip()]
    return {
        "truth_label": TRUTH_LABEL,
        "round_id": round_id or fields.get("round") or fields.get("round_id") or "R1621-adhoc",
        "title": title or fields.get("title") or "adhoc",
        "goal": fields.get("goal") or "",
        "symptoms": fields.get("symptoms") or "",
        "cause_hypothesis": fields.get("cause_hypothesis") or fields.get("cause") or "",
        "files_to_touch": files,
        "success_test": fields.get("success_test") or fields.get("test") or "",
        "cortex_plan": fields.get("cortex_plan") or DEFAULT_CORTEX_PLAN,
        "cortex_code": fields.get("cortex_code") or DEFAULT_CORTEX_CODE,
        "risks": fields.get("risks") or "",
        "not_doing": fields.get("not_doing") or "",
        "raw_header": header,
    }


def is_self_plan_turn(text: str) -> bool:
    low = " ".join(str(text or "").lower().split())
    if "[self_plan" in low or "self_plan" in low:
        return True
    if re.search(r"\bwrite\s+self[_\s-]?plan\b", low):
        return True
    if re.search(r"\br1621-\d{2}\b", low) and re.search(r"\bplan\b", low):
        return True
    if "free self-code" in low or "code your body" in low and "plan" in low:
        return True
    return False


def seed_campaign_plans(*, state_dir: Optional[Path | str] = None) -> list[dict[str, Any]]:
    """Write campaign rows to ledger once so WCT and Alice share the plan."""
    root = _state_dir(state_dir)
    out: list[dict[str, Any]] = []
    for row in CAMPAIGN_R1621:
        rec = {
            "schema": "ALICE_SELF_PLAN_SEED_V1",
            "ts": time.time(),
            "status": "open",
            **row,
        }
        _append(rec, state_dir=root)
        out.append(rec)
    # Active pointer = first open round
    try:
        active = {
            "ts": time.time(),
            "active_round_id": CAMPAIGN_R1621[0]["round_id"],
            "cortex_plan": DEFAULT_CORTEX_PLAN,
            "cortex_code": DEFAULT_CORTEX_CODE,
            "doctrine": "plan with small ornith; code with 35b; learn from mistakes",
        }
        (_state_dir(state_dir) / _ACTIVE).write_text(
            json.dumps(active, indent=2), encoding="utf-8"
        )
    except Exception:
        pass
    return out


def activate_plan(
    plan: dict[str, Any],
    *,
    state_dir: Optional[Path | str] = None,
    source: str = "alice_or_owner",
) -> dict[str, Any]:
    """Store active plan for the code phase."""
    root = _state_dir(state_dir)
    row = {
        "schema": "ALICE_SELF_PLAN_ACTIVE_V1",
        "ts": time.time(),
        "source": source,
        "status": "active",
        **{k: plan.get(k) for k in (
            "round_id", "title", "goal", "symptoms", "cause_hypothesis",
            "files_to_touch", "success_test", "cortex_plan", "cortex_code",
            "risks", "not_doing",
        )},
    }
    _append(row, state_dir=root)
    try:
        (root / _ACTIVE).write_text(json.dumps(row, indent=2), encoding="utf-8")
    except Exception:
        pass
    return row


def load_active_plan(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    path = _state_dir(state_dir) / _ACTIVE
    if not path.exists():
        return {}
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
        return row if isinstance(row, dict) else {}
    except Exception:
        return {}


def teaching_block_for_cortex(
    user_text: str = "",
    *,
    state_dir: Optional[Path | str] = None,
) -> str:
    """When owner asks for plan / self-code / body code — teach format + campaign."""
    low = " ".join(str(user_text or "").lower().split())
    active = load_active_plan(state_dir=state_dir)
    want = (
        is_self_plan_turn(user_text)
        or "self_code" in low
        or "self-code" in low
        or "code your body" in low
        or "piece of code from your body" in low
        or "stigmergic" in low and "code" in low
        or "r1621" in low
        or "free self" in low
    )
    if not want and not active:
        # Still inject a short campaign pointer when owner teaches basics
        if "basics" in low or "what are you" in low:
            return (
                "SELF-CODE READY (r1621): You may plan with [SELF_PLAN]...[/SELF_PLAN] "
                f"using planner {DEFAULT_CORTEX_PLAN}, then code with {DEFAULT_CORTEX_CODE}. "
                "When asked for code from your body, SELF_READ a real System/*.py path — "
                "never invent textbook ACO as if it were your file."
            )
        return ""
    if not want and active:
        # r1735: an active plan used to inject the whole ~2 KB campaign — the
        # SELF_PLAN template plus every open round — onto EVERY turn, because
        # the gate only asked whether a plan existed, not whether this turn was
        # about planning. George asking Alice to read a PDF paid for five
        # unrelated round descriptions, on every prompt, in real tokens. The
        # active round is worth one line; the campaign is not.
        round_id = str(active.get("active_round_id") or active.get("round_id") or "").strip()
        if not round_id:
            return ""
        return (
            f"ACTIVE SELF-PLAN ROUND: {round_id} "
            f"(plan with {active.get('cortex_plan') or DEFAULT_CORTEX_PLAN}, "
            f"code with {active.get('cortex_code') or DEFAULT_CORTEX_CODE}). "
            "Ask for the full campaign only when the owner's turn is about planning or self-coding."
        )
    parts = [campaign_prompt_block()]
    if active.get("round_id"):
        parts.append(
            f"ACTIVE PLAN: {active.get('round_id')} {active.get('title')} — "
            f"goal={active.get('goal', '')[:160]} "
            f"code_cortex={active.get('cortex_code')}"
        )
    parsed = parse_self_plan(user_text)
    if parsed:
        activate_plan(parsed, state_dir=state_dir, source="parsed_from_turn")
        parts.append(f"PARSED THIS TURN: round={parsed.get('round_id')} files={parsed.get('files_to_touch')}")
    return "\n".join(parts)


def template_plan_for_round(round_id: str) -> str:
    """Fill a ready-to-edit SELF_PLAN for Alice/George."""
    row = next((r for r in CAMPAIGN_R1621 if r["round_id"] == round_id), None)
    if not row:
        row = {
            "round_id": round_id,
            "title": "adhoc",
            "goal": "(fill)",
            "symptoms": "(fill)",
            "cause_hypothesis": "(fill)",
            "files_to_touch": ["System/....py", "tests/test_....py"],
            "success_test": "pytest tests/test_....py -q",
            "cortex_plan": DEFAULT_CORTEX_PLAN,
            "cortex_code": DEFAULT_CORTEX_CODE,
        }
    files = ", ".join(row.get("files_to_touch") or [])
    return (
        f"[SELF_PLAN: round={row['round_id']} title={row['title']}]\n"
        f"goal: {row.get('goal')}\n"
        f"symptoms: {row.get('symptoms')}\n"
        f"cause_hypothesis: {row.get('cause_hypothesis')}\n"
        f"files_to_touch: {files}\n"
        f"success_test: {row.get('success_test')}\n"
        f"cortex_plan: {row.get('cortex_plan', DEFAULT_CORTEX_PLAN)}\n"
        f"cortex_code: {row.get('cortex_code', DEFAULT_CORTEX_CODE)}\n"
        f"risks: regression on Talk path; keep tests green\n"
        f"not_doing: identity gag; textbook fake code; cloud-only dependency\n"
        f"[/SELF_PLAN]\n"
    )


def answer_plan_help(text: str, *, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Optional short help when owner asks how to plan / which model — evidence for cortex."""
    low = " ".join(str(text or "").lower().split())
    if not (
        "how to write" in low and "plan" in low
        or "self_plan" in low
        or "write the plan" in low
        or re.search(r"\br1621-0[1-5]\b", low)
        or ("ornith" in low and "35" in low and "plan" in low)
    ):
        return {}
    rid = "R1621-01"
    m = re.search(r"\b(R1621-0[1-5])\b", text or "", re.I)
    if m:
        rid = m.group(1).upper()
    return {
        "tag": "alice_self_plan_help_r1621",
        "reply": (
            "I write plans like this — planner can be ornith:latest; coder ornith:35b-q4_K_M "
            f"(or Krishna if 35B OOM).\n\n{template_plan_for_round(rid)}"
        ),
        "cortex_plan": DEFAULT_CORTEX_PLAN,
        "cortex_code": DEFAULT_CORTEX_CODE,
    }
