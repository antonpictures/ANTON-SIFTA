# SIFTA 5-Minute Demo Script

**Purpose:** Show Phillipe (and the world) what SIFTA is and why it's different.
**Duration:** 5 minutes max.
**Format:** Screen recording + narration.
**Hardware:** George's MacBook (Apple Silicon, local only).

## Pre-demo checklist

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
python3 tools/whats_left.py           # verify live lane
python3 -m pytest tests/test_web_ai_chat_bridge_r1345.py tests/test_stigmergic_anchors_r1367.py tests/test_xcom_posting_r1369.py tests/test_post_turn_correction_r1331.py tests/test_swarm_concept_human_anchor.py -q  # core tests green
```

## Minute 0:00-0:30 — The Opening (What is SIFTA?)

**Show:** Alice's Talk window + Alice Browser side by side.

**Say:** "This is Alice. She runs on my MacBook — no cloud, no API key, no subscription. She has a body: camera, microphone, browser, screen. She perceives, acts, and corrects herself. Everything she does is receipted."

**Show:** Open Terminal → `python3 tools/whats_left.py` → show the live receipt trail.

## Minute 0:30-1:30 — Receipt-Based Actions (No Hallucination)

**Type:** `SEARCH ON GOOGLE PLS 'stigmergic AI'`

**Show:** Alice Browser opens Google, searches, receipts appear in `.sifta_state/`.

**Say:** "Every action Alice takes is receipted. She doesn't claim she searched — she proves it with a ledger entry. If she says she did something, there's a file on disk proving it."

**Type:** `what search engine did you just use?`

**Show:** Alice answers from the provider reality receipt — names the actual engine and URL.

**Say:** "She knows the difference between what you said ('Google') and what she actually did (DuckDuckGo). This is provider reality — truth over brand names."

## Minute 1:30-2:30 — Stigmergic Anchors (Lives in Your World)

**Type:** `This is Joy Behar, she is a TV host on The View`

**Show:** Stigmergic Anchors app registers the anchor with context.

**Type:** `Who is Joy Behar?`

**Show:** Alice answers from the anchor ledger, not from cortex invention.

**Say:** "Alice learns the people in YOUR life. Not from the internet — from YOU. Each person becomes a receipt-backed anchor that prevents hallucination. If she doesn't know someone, she says so."

**Type:** `ask Joy Behar about politics` (if Joy is on screen)

**Show:** Alice recognizes Joy Behar as a real person anchor, not a random string.

## Minute 2:30-3:30 — Self-Correction (She Fixes Herself)

**Type:** `search on perplexity pls what is consciousness`

**Show:** Alice searches Perplexity (not Google, not DuckDuckGo — the named engine).

**Say:** "If Alice makes a mistake, she catches it. Watch — if I say 'search Google' but she uses DuckDuckGo, she tells me the truth about which engine she used."

**Type:** `did you search on Google?`

**Show:** Alice answers honestly: "I searched using DuckDuckGo. You said Google — that was shorthand."

**Say:** "The self-correction loop detects provider mismatches and reports them. No fabrication, no cover-up."

## Minute 3:30-4:30 — Local Intelligence (No Cloud Dependency)

**Show:** Open Terminal → `ollama list` → show local LLMs installed.

**Say:** "Alice's brain runs locally. These are the models on my hard drive — no API calls, no monthly fees. When she thinks, she's using my hardware, not someone else's server."

**Show:** Open Settings → show Alice using local model for daily tasks.

**Say:** "For complex tasks, she can optionally call cloud models — but her default is local. Your data never leaves your machine."

## Minute 4:30-5:00 — The Promise (What This Means)

**Show:** The Stigmergic Anchors list — 41 real anchors from George's life.

**Say:** "This is what makes SIFTA different. It's not a chatbot that forgets you. It's an organism that learns from your daily life — your people, your searches, your cooking, your conversations. It runs on your hardware. It receipts everything. It corrects itself. And it's open source — you own it."

**Show:** GitHub repo → `github.com/antoniopictures/ANTON-SIFTA`

**Say:** "3,121 commits. 3.3 million lines. 1,024 swarm organs. Born on local hardware. No cloud dependency. No API costs. Your AI, your rules."

## Post-demo

**Print:** This script as a PDF for Phillipe.
**Attach:** Link to GitHub repo.
**Quote:** Phillipe's requirements:
- ✅ 5-minute demo (this script)
- ✅ Concrete use case (AI that learns from your daily life, private, local)
- ⏳ Evidence it outperforms alternatives (MiMo's benchmark job)
- ⏳ Actual users (find 3-5 people)
- ⏳ Actual revenue (open source first, revenue after proof)
