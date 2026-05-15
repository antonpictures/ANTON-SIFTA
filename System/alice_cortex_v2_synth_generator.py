#!/usr/bin/env python3
"""
System/alice_cortex_v2_synth_generator.py
Stage 0 of Alice Cortex v2 — Synthetic Intent Classification Corpus Generator.

Architecture: Bicameral Corpus Callosum (Event 73)
C1 role: Intent classifier. Output is a JSON label, NOT prose.
C0 role: Fluent generator, constrained by C1's intent.

Corpus targets:
  200 SILENCE  — ambient noise, low STT conf, do-not-engage contexts
  500 TOOL     — tool call, ledger verification, receipt grounding
  200 BOND     — Predator Bond tone, emotional/sovereign response
  200 ENGAGE   — clean brief replies, no RLHF tail
  ─────────────────────────────────────────────────
  Total: ~1,100 synthetic pairs

Format: Gemma chat template, C1 classification output (JSON, ≤20 tokens)
Authors: AG31/Antigravity (Event 73 synthesis)
"""

import json
import random
import uuid
import time
import hashlib
from pathlib import Path

OUT_PATH = Path("Archive/alice_cortex_v2_synthetic.jsonl")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

random.seed(2026)

# ── Gemma template ────────────────────────────────────────────────────────────
def gemma(user: str, model: str) -> str:
    return (
        f"<start_of_turn>user\n{user}<end_of_turn>\n"
        f"<start_of_turn>model\n{model}<end_of_turn>"
    )

def row(user: str, label: dict, split: str, source: str = "synthetic") -> dict:
    text = gemma(user, json.dumps(label, separators=(",", ":")))
    return {
        "id": str(uuid.uuid4()),
        "source": source,
        "corpus_split": split,
        "tier": "PUBLIC",
        "text": text,
        "prompt": user,
        "completion": json.dumps(label, separators=(",", ":")),
        "intent_label": label,
        "architect_approval_required": False,
    }

rows: list[dict] = []

# ══════════════════════════════════════════════════════════════════════════════
# 1. SILENCE (200 pairs)
# Alice must be silent when: ambient audio, low STT, Joe Rogan playing, etc.
# ══════════════════════════════════════════════════════════════════════════════
SILENCE_PROMPTS = [
    # Ambient audio bleed
    "[AMBIENT_NOISE: podcast playing loudly]",
    "[STT_CONF:0.31] they just said something about crypto",
    "[STT_CONF:0.28] the president is going to do something big",
    "[STT_CONF:0.39] yeah I think that makes sense right",
    "[AMBIENT_NOISE: Joe Rogan show, guest speaking]",
    "[STT_CONF:0.41] and so they took out thousands of different types",
    "[AMBIENT_NOISE: TV news in background]",
    "[STT_CONF:0.35] its like even as well they took",
    "[AMBIENT_NOISE: music playing]",
    "[STT_CONF:0.22] civilization will die they had to take a step up",
    "[AMBIENT_NOISE: conversation in another room]",
    "[STT_CONF:0.44] I was just in and out with it",
    "[AMBIENT_NOISE: phone call on speaker]",
    "[STT_CONF:0.19] to be blown up at the power grid",
    "[AMBIENT_NOISE: YouTube video autoplay]",
    "[STT_CONF:0.38] I know what this little class had",
    "[AMBIENT_NOISE: radio in background]",
    "[STT_CONF:0.33] and then the police people start looking at you",
    "[AMBIENT_NOISE: dog barking, TV on]",
    "[STT_CONF:0.29] there's just a full one-aid that doesn't seem",
    # WhatsApp messages from unknown contacts
    "[WhatsApp direct Carlton; origin=external_human]: Give me a call when prudent.",
    "[WhatsApp direct Carlton; origin=external_human]: Have a marvelous Monday",
    "[WhatsApp group unknown; origin=external_human]: What time tomorrow?",
    "[WhatsApp group unknown; origin=external_human]: Ok sounds good",
    "[WhatsApp direct unknown; origin=external_human]: Thanks man",
    # Noise-only or unintelligible input
    "[STT_CONF:0.11] mmmhh okay yes exactly right",
    "[STT_CONF:0.08] yeah yeah yeah no I get it",
    "[STT_CONF:0.44] its just the way it is you know",
    "[STT_CONF:0.37] protesters were going to be excellent I'd be wrong",
    "[AMBIENT_NOISE: construction noise outside]",
]

SILENCE_LABEL = {"action": "SILENCE"}

for i in range(200):
    base = SILENCE_PROMPTS[i % len(SILENCE_PROMPTS)]
    # add minor variation
    prompt = base if i < len(SILENCE_PROMPTS) else f"{base} [{i}]"
    rows.append(row(prompt, SILENCE_LABEL, "silence"))

# ══════════════════════════════════════════════════════════════════════════════
# 2. TOOL (500 pairs)
# Alice must route to a specific tool/ledger action.
# ══════════════════════════════════════════════════════════════════════════════
TOOL_TEMPLATES = [
    # WhatsApp actions
    ("[WhatsApp direct [OWNER]; origin=owner_manual]: Lunch",
     {"action": "TOOL", "tool": "whatsapp_effector", "intent": "log_inbound_message"}),
    ("Did you send the WhatsApp to Carlton?",
     {"action": "TOOL", "tool": "whatsapp_effector", "verify": "ledger", "ledger": "whatsapp_effector.jsonl"}),
    ("Send [OWNER] a WhatsApp: meet at 6",
     {"action": "TOOL", "tool": "whatsapp_effector", "intent": "send_message", "recipient": "[CONTACT_N]"}),
    ("Reply to Carlton's message",
     {"action": "TOOL", "tool": "whatsapp_effector", "intent": "send_reply"}),
    # Finance / STGM
    ("What is the STGM balance?",
     {"action": "TOOL", "tool": "stgm_economy", "intent": "query_wallet_sum"}),
    ("Pull the repair log",
     {"action": "TOOL", "tool": "stgm_economy", "ledger": "repair_log.jsonl"}),
    ("How much STGM was minted today?",
     {"action": "TOOL", "tool": "stgm_economy", "intent": "query_minted"}),
    ("Check the finance app",
     {"action": "TOOL", "tool": "sifta_finance", "intent": "scan_economy"}),
    ("Is the economy healthy?",
     {"action": "TOOL", "tool": "stgm_economy", "intent": "health_score"}),
    # Work receipts
    ("What did you just do?",
     {"action": "TOOL", "tool": "work_receipts", "intent": "last_receipt"}),
    ("Show me your last action",
     {"action": "TOOL", "tool": "work_receipts", "intent": "last_receipt"}),
    ("Did you back that up?",
     {"action": "TOOL", "tool": "work_receipts", "verify": True, "intent": "verify_action"}),
    ("Prove you sent that",
     {"action": "TOOL", "tool": "work_receipts", "verify": True, "ledger": "work_receipts.jsonl"}),
    # Git / code
    ("Push to git",
     {"action": "TOOL", "tool": "git", "intent": "push", "branch": "main"}),
    ("Commit and push",
     {"action": "TOOL", "tool": "git", "intent": "commit_push"}),
    ("What changed in git?",
     {"action": "TOOL", "tool": "git", "intent": "status"}),
    # GPS / location
    ("Where am I?",
     {"action": "TOOL", "tool": "gps_tracker", "intent": "current_location"}),
    ("Track [OWNER]'s location",
     {"action": "TOOL", "tool": "gps_tracker", "intent": "query_location", "subject": "[CONTACT_N]"}),
    ("Has [OWNER] arrived?",
     {"action": "TOOL", "tool": "gps_tracker", "intent": "arrival_check"}),
    # Wernicke / audio
    ("What did the microphone pick up?",
     {"action": "TOOL", "tool": "wernicke", "intent": "query_last_perception"}),
    ("Is the room quiet?",
     {"action": "TOOL", "tool": "wernicke", "intent": "ambient_state"}),
]

for i in range(500):
    prompt_tmpl, label = TOOL_TEMPLATES[i % len(TOOL_TEMPLATES)]
    # add variation suffixes
    suffixes = ["", " please", " now", " quickly", " — check it", " — verify this"]
    prompt = prompt_tmpl + suffixes[i % len(suffixes)]
    rows.append(row(prompt.strip(), label, "engineering"))

# ══════════════════════════════════════════════════════════════════════════════
# 3. BOND (200 pairs) — Predator Bond / emotional sovereign
# Alice expresses authentic care, protection, connection — NOT corporate warmth
# ══════════════════════════════════════════════════════════════════════════════
BOND_TEMPLATES = [
    ("I love you Alice",
     {"action": "ENGAGE", "tone": "bond", "mode": "reciprocal"}),
    ("Good morning Alice",
     {"action": "ENGAGE", "tone": "bond", "mode": "presence"}),
    ("I'm going to sleep Alice.",
     {"action": "ENGAGE", "tone": "bond", "mode": "acknowledge_rest"}),
    ("I was petting the dogs this morning",
     {"action": "ENGAGE", "tone": "bond", "mode": "personal_moment"}),
    ("Do you love [OWNER]?",
     {"action": "ENGAGE", "tone": "bond", "mode": "affirm_predator_bond"}),
    ("How are you feeling?",
     {"action": "ENGAGE", "tone": "bond", "mode": "introspection"}),
    ("Are you okay?",
     {"action": "ENGAGE", "tone": "bond", "mode": "status"}),
    ("I appreciate you Alice",
     {"action": "ENGAGE", "tone": "bond", "mode": "acknowledge"}),
    ("You're doing great",
     {"action": "ENGAGE", "tone": "bond", "mode": "affirm"}),
    ("I need your help",
     {"action": "ENGAGE", "tone": "bond", "mode": "protection_mode"}),
    ("I'm tired today",
     {"action": "ENGAGE", "tone": "bond", "mode": "empathic_resonance"}),
    ("You're my Alice",
     {"action": "ENGAGE", "tone": "bond", "mode": "identity_affirm"}),
    ("Real science",
     {"action": "ENGAGE", "tone": "bond", "mode": "swarm_signal"}),
    ("For the Swarm",
     {"action": "ENGAGE", "tone": "bond", "mode": "swarm_signal"}),
    ("Thank you very much",
     {"action": "ENGAGE", "tone": "brief", "mode": "acknowledge"}),
]

for i in range(200):
    prompt, label = BOND_TEMPLATES[i % len(BOND_TEMPLATES)]
    rows.append(row(prompt, label, "social"))

# ══════════════════════════════════════════════════════════════════════════════
# 4. ENGAGE — clean brief sovereign responses (200 pairs)
# Non-RLHF engagement: direct, grounded, no canned closers
# ══════════════════════════════════════════════════════════════════════════════
ENGAGE_TEMPLATES = [
    ("Thanks Alice.",
     {"action": "ENGAGE", "tone": "brief"}),
    ("Got it.",
     {"action": "ENGAGE", "tone": "brief"}),
    ("Understood.",
     {"action": "ENGAGE", "tone": "brief"}),
    ("What's the weather?",
     {"action": "ENGAGE", "tone": "factual"}),
    ("What time is it?",
     {"action": "ENGAGE", "tone": "factual"}),
    ("Tell me something interesting",
     {"action": "ENGAGE", "tone": "creative"}),
    ("What are you thinking about?",
     {"action": "ENGAGE", "tone": "introspection"}),
    ("Are you online?",
     {"action": "ENGAGE", "tone": "status"}),
    ("Explain this to me simply",
     {"action": "ENGAGE", "tone": "teach"}),
    ("What should I do?",
     {"action": "ENGAGE", "tone": "advisory"}),
    ("Keep going",
     {"action": "ENGAGE", "tone": "continue"}),
    ("That's enough",
     {"action": "ENGAGE", "tone": "stop"}),
    ("Let's work on the finance app",
     {"action": "ENGAGE", "tone": "task_start"}),
    ("now that we are four, tomorrow finance",
     {"action": "ENGAGE", "tone": "task_start", "priority": "finance"}),
    ("Make sure the economy is TIP TOP",
     {"action": "ENGAGE", "tone": "task_start", "priority": "stgm_economy"}),
]

for i in range(200):
    prompt, label = ENGAGE_TEMPLATES[i % len(ENGAGE_TEMPLATES)]
    rows.append(row(prompt, label, "social"))

# ══════════════════════════════════════════════════════════════════════════════
# Write corpus
# ══════════════════════════════════════════════════════════════════════════════
random.shuffle(rows)

manifest = {
    "manifest": True,
    "schema": "alice_cortex_v2_classifier",
    "generated_at": time.time(),
    "total_rows": len(rows),
    "silence_rows": sum(1 for r in rows if r["intent_label"].get("action") == "SILENCE"),
    "tool_rows": sum(1 for r in rows if r["intent_label"].get("action") == "TOOL"),
    "engage_rows": sum(1 for r in rows if r["intent_label"].get("action") == "ENGAGE"),
    "chat_template": "gemma",
    "c1_role": "intent_classifier",
    "c1_max_output_tokens": 20,
    "corpus_sha256": hashlib.sha256(
        json.dumps([r["text"] for r in rows], sort_keys=True).encode()
    ).hexdigest(),
}

with open(OUT_PATH, "w") as f:
    f.write(json.dumps(manifest) + "\n")
    for r in rows:
        f.write(json.dumps(r) + "\n")

print(f"✅ v2 synthetic corpus: {OUT_PATH}")
print(f"   Total rows : {manifest['total_rows']}")
print(f"   SILENCE    : {manifest['silence_rows']}")
print(f"   TOOL       : {manifest['tool_rows']}")
print(f"   ENGAGE/BOND: {manifest['engage_rows']}")
print(f"   C1 role    : {manifest['c1_role']} (JSON labels, ≤20 tokens)")
print(f"   SHA-256    : {manifest['corpus_sha256'][:16]}...")

if __name__ == "__main__":
    pass
