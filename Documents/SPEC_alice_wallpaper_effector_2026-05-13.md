# SPEC — Alice Wallpaper Effector (natural-language, web-sourced)

**Stigauth:** `COWORK_SPEC_ALICE_WALLPAPER_EFFECTOR_2026-05-13`
**Doctor:** Cowork (claude-opus-4-7)
**Lane:** Surgeon (draft — no code yet)
**Node:** GTH4921YP3
**Architect intent:** *"Alice change the background with whatever — grabs one from the web and changes it — simple demo for investors — but must be from the web, in natural language and whatever — 'CHANGE THE DESKTOP WALLPAPER'"*

---

## 1. Why this is a SPEC first, not a band-aid

This is a **new effector** that touches three covenant-sensitive surfaces at
once:

1. **Network egress** — making an outbound HTTPS request to a web service
   to fetch an image, which must produce a receipt per IDE_BOOT_COVENANT §6
   ("Decide → Execute → Receipt → minimal grounded reply").
2. **Filesystem write outside `.sifta_state/`** — saving a downloaded
   image into `Library/Desktop Pictures/` so the wallpaper hook can pick
   it up.
3. **UI mutation** — changing the desktop and/or chat wallpaper for both
   tabs of SIFTA OS.

Each of those, on its own, has been gated in the past. Doing all three in
one new reflex without a written spec is exactly the "act before think"
pattern the bowel doctrine forbids.

## 2. User-facing contract

Spoken or typed natural-language utterance the owner says or types in the
Talk-to-Alice chat:

- *"Alice, change the desktop wallpaper to a black hole."*
- *"Change the background to a forest at night."*
- *"Wallpaper of honey dripping on a circuit board."*
- *"Change desktop image, surprise me."*

Alice's reply must NAME exactly what she did, with receipts:

> *"I'm searching the web for `<query>`. Top result: `<image_url>`,
> `<bytes>` KB. Saved to `Library/Desktop Pictures/web_<ts>_<sha>.jpg`.
> Applied as the active desktop wallpaper. Receipt: `<id>`. If you don't
> like it, say 'undo' and I'll roll back to the previous wallpaper."*

No silent action. No invented description of an image she didn't actually
fetch.

## 3. Architecture (where the code goes)

```
Owner says "change the wallpaper to X"
        │
        ▼
[ swarm_alice_wallpaper_intent.py ]   ← new fast-path
    1. parse intent  →  {action: "set_wallpaper", query: "X"}
    2. emit intent receipt to ide_stigmergic_trace.jsonl
        │
        ▼
[ swarm_alice_wallpaper_effector.py ] ← new effector organ
    3. web-image search  (DuckDuckGo HTML, no API key)
    4. download top result with size cap (≤ 4 MB, image MIME only)
    5. content-hash the bytes, save to Library/Desktop Pictures/
    6. emit network egress receipt
    7. update active wallpaper:
        - calls _apply_wallpaper(force=True) on SiftaDesktop
        - updates chat viewport QPalette brush
    8. emit wallpaper_applied receipt
        │
        ▼
Reply to owner in Talk: "I fetched <query>, saved as <file>, applied."
```

## 4. Receipts schema

`.sifta_state/wallpaper_changes.jsonl`, append-only:

```json
{
  "ts": <unix>,
  "kind": "WALLPAPER_CHANGE",
  "truth_label": "WALLPAPER_EFFECTOR_V1",
  "intent_query": "honey dripping on a circuit board",
  "search_engine": "duckduckgo_html",
  "candidate_urls": [
    "https://...jpg",
    "https://...jpg"
  ],
  "chosen_url": "https://...jpg",
  "bytes": 417861,
  "mime": "image/jpeg",
  "content_sha256": "...",
  "saved_path": "Library/Desktop Pictures/web_1778625012_5d08eac5.jpg",
  "previous_wallpaper": "Library/Desktop Pictures/CHAT.jpg",
  "applied": true,
  "receipt_id": "..."
}
```

`previous_wallpaper` is critical for the `undo` reply path.

## 5. Safety gates

Hard gates, all must pass before download:

1. **Size cap:** `Content-Length` header must be ≤ 4 MB. Stream-and-stop
   if it exceeds during transfer.
2. **MIME:** content type must start with `image/`. Reject `text/html`
   masquerading.
3. **Domain blocklist:** an explicit `swarm_network_blocklist.txt` of
   adult-content / tracking / known-malware domains; ship empty for v1
   and expand on the first false positive.
4. **Owner gate:** the action only fires when the wake-ear has classified
   the turn as direct address from a known owner (`audience == architect`)
   AND the cortex confirms intent. This is where the cortex-gated effector
   router doctrine plugs in — until that router is written, **this
   effector cannot ship**, because there is no gated path to register it
   under.
5. **STGM cost:** charge `0.50 STGM` per wallpaper change against her
   metabolic budget. If she's bankrupt, reply *"I can't afford that right
   now."* Real metabolic constraint, not theater.

## 6. Undo / rollback

`.sifta_state/wallpaper_changes.jsonl` already records `previous_wallpaper`.
If the owner says *"undo"* / *"go back"* / *"I don't like that one"* within
60 s of a wallpaper change, the effector reads the most recent row and
re-applies `previous_wallpaper`. Writes a `WALLPAPER_UNDO` row.

## 7. Investor-demo path

For the simplest investor demo, the working flow is:

1. Owner: *"Alice, change the desktop wallpaper to a black hole."*
2. Status bar: *"searching web for 'black hole'..."*  (visible, no fake delay)
3. Chat reply (Alice): *"Found 3 candidate images. Picked the first: NASA Goddard, 1.2 MB, sha8 7c4f1a39. Saved to Library/Desktop Pictures/web_1778625012_7c4f1a39.jpg. Previous wallpaper was CHAT.jpg. Wallpaper applied. Say 'undo' to revert."*
4. Wallpaper visibly changes in both Chat and Launcher tabs.
5. Receipt row visible in Provider Schedule's *"Recent actions"* and in
   the witness journal.

That's the demo loop in one breath. Every step receipt-bearing.

## 8. Open questions for Architect

Before I cut code, please confirm or override:

1. **Search engine:** DuckDuckGo HTML scrape (no API key, free) vs adding
   a real image-search API later? Free is fine for v1 unless you have a
   key you already pay for.
2. **Save location:** `Library/Desktop Pictures/` (next to CHAT.jpg) or a
   separate `Library/Desktop Pictures/web_fetched/` subfolder?
3. **Wallpaper scope:** does *"change the wallpaper"* mean only the chat
   surface, or only the desktop, or both? Default: BOTH unless the owner
   says "only the chat" or "only the desktop".
4. **Cortex-gated router precondition:** are you OK with me cutting this
   effector AS PART OF the cortex-gated router surgery (one big PR), or
   should they be sequenced (router first, then effector layered on top)?
   The latter is safer.
5. **NSFW / content policy:** for an investor demo, do we want any
   adult-image rejection beyond the domain blocklist? A first-pass check
   on returned image dimensions + MIME is probably enough. Tell me if you
   want anything stricter.

---

## 9. Next concrete step

When the answers to §8 are in, the implementation order is:

1. Cortex-gated effector router (already queued — this surgery is a
   prerequisite, not a duplicate).
2. `System/swarm_alice_wallpaper_effector.py` (the download + apply organ).
3. `System/swarm_alice_wallpaper_intent.py` (the natural-language gate).
4. Wire intent → router → effector in `sifta_talk_to_alice_widget.py`.
5. Live demo: speak the line, see the wallpaper change, see the receipt
   land.

**ETA from green light:** ~2 hours of focused work for the full chain,
including tests against a synthetic search result and a manual end-to-end
test with the architect watching.

---

**For the Swarm.** 🐜⚡
