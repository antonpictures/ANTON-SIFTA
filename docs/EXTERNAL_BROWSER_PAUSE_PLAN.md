# Pause video in the EXTERNAL browser when Alice talks — browser-aware

Status: **IMPLEMENTED & LIVE-VERIFIED** (V2, browser-aware). Supersedes the V1 CDP-only plan,
which was built on a wrong assumption (see §4).

Truth labels: `EXTERNAL_BROWSER_PAUSE_V2`, `EXTERNAL_BROWSER_VIDEO_PAUSE_V2`
Organ: `external_browser_media` (layer `effector`) in `System/swarm_canonical_organ_registry.py`

## 1. What already worked (not rebuilt)

Alice already pauses video **in her own embedded browser** before she speaks — in-process
QtWebEngine JavaScript against her own `_view`:

- `Applications/sifta_alice_browser_widget.py`
  - `pause_active_video_receipt()` — L4457 → `{ok, was_paused, paused, current_time, duration, url}`
  - `play_active_video_receipt()` — L4487, the resume counterpart
- `System/swarm_cowatch_body_loop.py`
  - `run_cowatch_video_pause_body_loop()` — fires **before speech**
  - `run_cowatch_video_resume_body_loop()` — fires after speech

**The trigger already existed.** This work added a *new effector* and *browser awareness*, not a trigger.

## 2. The real requirement (owner's correction)

> "Alice, you opened chrome, I m playing in safari. Alice you have to be aware of what browser is
> on, w yt video in so you know what browser to pause :)"

Two requirements, not one:
1. **Browser awareness** — Alice must know which browsers are running, which is frontmost, and
   **which one actually holds the playing video**.
2. **Route the pause to the correct browser** — not to a hardcoded assumption.

The owner may use any browser. Detection must not be browser-specific.

## 3. Architecture — four components

```
TRIGGER (existed)          AWARENESS + DETECT (new)      CONTROL (new)          MERGE (new)
run_cowatch_video_  ──►  running browsers                Safari: AppleScript ──► Alice-Browser receipt
pause_body_loop          frontmost app                    `do JavaScript`        + external receipt
(before speech)          which browser/tab is PLAYING     Chrome family: CDP     ok = alice_ok OR external_ok
                         which tab has a <video>          (secondary)
```

## 4. Chosen approach — and the correction

**Primary effector: Safari via AppleScript `do JavaScript … in <tab>`.**
Requires Safari → Develop → *Allow JavaScript from Apple Events*. **Already enabled on this Mac.**
Focus-free, tab-targeted, returns a real pause receipt.

**Secondary effector: Chrome DevTools Protocol (CDP, port 9222)** for Chromium-family browsers
(Chrome/Brave/Edge/Arc). Kept for completeness; **port 9222 is closed on this Mac** and nothing
relaunches Chrome to force it open.

**No effector: Firefox** — detected and reported, but has no JS bridge, so it is skipped, not faked.

### Correction of record

V1 assumed Chrome/CDP was the target and even attempted `open -na "Google Chrome"` to force port
9222 open. That was **wrong on the facts** (the owner was playing in Safari) and **wrong in spirit**
(AGENTS.md forbids macOS `open` for browser launching). V2: the relaunch is gone; Safari is primary;
`ensure_cdp_port()` is now a passive check that explicitly notes Safari needs no port.

Rejected: System Events `keystroke space` (steals focus) · Chrome AppleScript media control (not
exposed) · blind `CGEventPost` (no confirming receipt) · requiring a browser extension (unnecessary —
AppleScript already works).

## 5. Implementation

### `System/swarm_external_browser_pause.py` — the effector + awareness organ
`TRUTH_LABEL = "EXTERNAL_BROWSER_PAUSE_V2"`

| Function | Purpose |
|---|---|
| `running_browsers()` | `pgrep -x` over the known-browser profiles |
| `frontmost_app()` | `System Events` frontmost process name |
| `_safari_tab_scan()` | **one** osascript call → every Safari tab + video state |
| `browser_awareness_snapshot()` | the full computer-use picture |
| `pick_video_browser(url)` | **decides which browser to pause** |
| `pause_video_anywhere(url)` / `resume_video_anywhere(url)` | dispatch to the right effector |
| `detect_external_video_tab()` | detection helper (V1-compatible) |
| `ensure_cdp_port()` | passive CDP check — no relaunch |

`BROWSER_PROFILES` maps each browser to its effector: Safari → `applescript_js`; Chrome / Chrome
Canary / Brave / Edge / Arc / Chromium → `cdp`; Firefox → `none`.

**Target selection order** (`pick_video_browser`):
frontmost browser with a *playing* video → any *playing* video → frontmost browser with a video →
any video tab. In practice this returned `frontmost_playing`.

JS returns `|`-joined fields (single-quotes only) so it embeds safely inside an AppleScript
double-quoted string without escaping — no JSON-stringify quoting hazard.

### `System/swarm_external_browser_video_pause.py` — integration layer
`TRUTH_LABEL = "EXTERNAL_BROWSER_VIDEO_PAUSE_V2"`

- `try_pause_external_video()` / `try_resume_external_video()` — return `(bool, receipt)`, **never raise**
- `enrich_cowatch_body_loop(url, receipt)` — merges the external attempt into the Alice-Browser
  receipt; **`ok = alice_ok OR external_ok`**, so external failure can never block Alice's speech
- `browser_awareness()` — exposes the snapshot to the rest of the body

### `System/swarm_cowatch_body_loop.py` — the existing trigger, extended
`run_cowatch_video_pause_body_loop` now calls `enrich_cowatch_body_loop`; `actual` includes
`external_ok=` and `external_reason=`; `expected` reads "Alice Browser + external browser pause
video at {url} before speech".

## 6. Live verification (observed, not assumed)

**Safari pause + resume, real embed tab, real playing video:**

```
--- PAUSE ---
  ok: True   browser: Safari   effector: applescript_js
  was_paused: False  ->  paused: True   current_time: 1285.1   duration: 3991.5
  chosen_why: frontmost_playing   frontmost_app: Safari
  AFTER 1.5s -> paused=True t=1285.1     <- time FROZEN == genuinely paused
--- RESUME ---
  ok: True   was_paused: True  ->  paused: False   current_time: 1285.1
```

**Awareness, with Safari *and* Chrome both running:**

```
running_browsers : ['Safari', 'Google Chrome']
frontmost_app    : Safari (browser=True)
video_tabs       : 2
  Safari w1t1 playing=False t=388.6  https://www.youtube.com/watch?v=stCsG2s2LG4
  Safari w1t2 playing=True  t=1322.3 https://www.youtube-nocookie.com/embed/uVlx2en1RRc?...
playing_tabs     : 1
-> chose Safari via frontmost_playing
```

Alice correctly distinguished the **paused** video from the **playing** one, and picked the playing
embed — the exact thing the owner asked for.

**Full wired chain:**

```
System/test_external_browser_pause.py  ->  ALL TESTS PASSED (8/8)
  imports · organ registered · browser awareness · target picking ·
  enrich external-failure-never-blocks · enrich external-success-merges ·
  cowatch body loop shape · fail-soft on effector crash
```

Tests stub the external layer so running the suite does **not** disturb the owner's playing video
(verified: the video kept playing at t=1322.3 through the full test run).

## 7. Safety / consent boundaries (kept)

- **Never steal focus** — AppleScript targets a specific tab by reference; nothing is activated.
- **Pause/resume only** — never navigate, never read unrelated tabs, never screenshot.
- **Owner-sensitive** — registered with `owner_sensitive=True`; fires on the cowatch intent only.
- **Fail soft, proven** — a crashing effector is swallowed and reported as
  `{ok: False, reason: "error", details: …}`; Alice still speaks and Alice-Browser pause still works.
- One-tab-per-browser targeting; no viral/recombinant code; observation/automation arm only.

## 8. Definition of done — met

- [x] Detection finds the external embed tab and reports which is *playing*
- [x] Pause/resume returns the same receipt shape Alice-Browser already returns
- [x] Pre-speech pause fires on BOTH Alice Browser and the external browser
- [x] External failure does not block speech (stubbed test + real fail-soft path)
- [x] Browser-aware: knows which browser is on, routes the pause to it
- [x] Organ registered in the canonical registry; `py_compile` clean; 8/8 tests pass
- [x] No macOS `open`; Safari needs no extension and no port

## 9. Remaining (optional, not blocking)

1. **CDP path is untested live** — port 9222 is closed on this Mac; the Chrome/browser-family branch
   is written and compiles but has no live-fire evidence. Deliberately *not* forced by relaunching Chrome.
2. **Firefox** is detected but has no effector — would need an extension if ever required.
3. **Multiple simultaneous playing videos across two browsers** — current rule is deterministic
   (frontmost-playing first) but has not been exercised against a live two-browser-playing case.
