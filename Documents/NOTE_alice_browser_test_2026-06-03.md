# Note — Alice Browser test session, 2026-06-03 (~17:52–18:30)

George asked me to make a note: in the screenshot, Alice searched the internet with the message I'd written. She did — but the test surfaced two real things worth recording honestly.

## 1. The loop closed, but the search misrouted

George pasted my previous reply (real-hardware datasets — Figshare 16-qubit IBM entanglement, Mendeley IBMQ circuits, MNISQ, OpenQDC — plus the fractal-rematch offer) into Alice and said "SEARCH ON GOOGLE PLS '…'". So the chain worked: **CLAUDE → George → Alice → the web.** Nice to see.

But Alice did **not** search for what was asked. Instead of querying the datasets I named, she searched `"Quantum Computing Playground code editor interface theme"` — a query she derived from a *stale screenshot* she'd looked at earlier with the vision agent. Her own narration admits it: *"I reasoned from the photo I just saw and searched Google for…"*.

That's a **search-command routing drift**: an explicit, quoted search query got overridden by a hallucinated one from prior visual context. The effector ignored the literal instruction. Worth a healing-queue row, not a ban.

## 2. The "page answer" fix is on disk — but in the wrong code path

A brother (r481) claimed the weak page answer was fixed by wiring `organs_relevant_to_text` (the Code-KG matcher) into the browser/page path. I verified: it **is** on disk — `_cowatch_comment_line` (talk widget ~line 23907) does call the matcher and builds "this page touches my {organ} in my Code Knowledge Graph…".

**But the transcript still shows the generic "That is a profoundly excellent question…" answer** to "what's interesting for your body on this page to test?" (17:52:33). Probe-before-claim says the fix is **not verified working** — and here's why:

- `_cowatch_comment_line` is the **passive co-watch auto-commentary** path (fires while watching a video/page on its own).
- George's question was a **direct typed turn**, which flows through Alice's **main cortex reply** path — and that path never calls the matcher.

So the matcher got wired into the path that *wasn't* the problem. The real fix is to feed `organs_relevant_to_text(page_text)` into the **cortex prompt context** whenever the owner asks about the current browser page, so the LLM answers grounded in her actual organs instead of prose. (The mid-sentence cutoffs in the transcript are still the separate r474 `num_predict` 700 cap.)

## Minor glitches also seen (low priority)

- Non-sequitur offer to find "photos of a celebrity" mid-election-search — stale-context bleed, same family as #1.
- Asked to run the Shor-style `FindFactors 15` Playground script, Alice narrated the code but didn't actually execute it (no real interpreter for that DSL).

## Suggested next steps

1. Wire the KG matcher into the **cortex reply path** for browser/page questions (the actual fix for #2).
2. Add a guard so an explicit quoted search query wins over vision-derived context (#1).
3. Then the real-data / fractal-benchmark work from last round.
