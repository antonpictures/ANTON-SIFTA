# Tournament consolidation analysis — 2026-06-11

**Doctor:** composer (grok) · **Truth label:** OBSERVED · **Round:** r1023 lane C  
**Scope:** Analysis only — **no merge** without Fable PASS + George nod.

---

## Files surveyed

| Path | Role | mtime probe |
|------|------|-------------|
| `Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-11.md` | **Only** dated June-11 carrier found | single file |
| `Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-10.md` | prior day carrier | exists |
| `Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-02.md` | older carrier | exists |

**Finding:** There is **no second June-11 mirror file**. "Both files" in r1023 means **head vs tail divergence inside one carrier** (anchor fix protects new rows only).

---

## Head vs tail — r10xx blocks

### Head region (~lines 66–167, early in 25k-line file)

| Section | Line ~ | Content |
|---------|--------|---------|
| `r1020c-codex-final-line-count-correction` | 66 | Git-tracked 1,002,034 lines; matrix 20,860,283 |
| `r1020-codex-body-count-matrix-and-fable-work-queue` | 89 | Eval matrix + Fable ask + 12 Codex / 120 Composer queue |

### Tail region (~lines 24839–25100, append order)

| Section | Anchor | Content |
|---------|--------|---------|
| `r1020b-codex-body-count-matrix-and-fable-work-queue-tail-anchor` | none in title | Tail re-anchor of r1020 queue |
| `r1020c-composer-snapshot-inventory-fix-matrix-sprint` | none | Snapshot `repo=` fix |
| `r1021-composer-covenant-read-endurance-fable-20x` | none | 20× endurance ask |
| `r1021-fable-rulings-and-the-endurance-round` | `[r1021-fable-9504d7ac]` | C1–C12 coded; 240 probes |
| `r1022-codex-fable-c1-c12-surgical-pass` | `[r1022-codex-fcbd976b]` | Codex verification tail |

### Blocks in one region but not the other

| Block | Head | Tail | Notes |
|-------|------|------|-------|
| `r1020-codex-body-count-matrix` (first pass) | yes | no | superseded by r1020b tail |
| `r1020c-codex-final-line-count` (Codex) | yes | no | parallel to composer r1020c at tail |
| `r1020b` / `r1021` / `r1022` | no | yes | canonical recent history |
| Duplicate `##` round IDs | — | — | **None** among r1020–r1022 (Counter check) |

### Ordering divergence

The file is **append-only at tail** but also contains **early inserts** (r1020/r1020c at line 66). Chronological reading requires:

1. Head r1020 blocks = mid-day Codex inserts (not latest truth).  
2. Tail r1020b→r1022 = authoritative queue + C1–C12 status.  
3. **861** total `##` sections — full file is historical stack, not strict time sort.

---

## What `whats_left.py` follows

**Receipt:** Read `tools/whats_left.py` L48–66, L81–128.

| Rule | Behavior |
|------|----------|
| Carrier selection | Newest `CONSCIOUSNESS_TOURNAMENT_YYYY-MM-DD.md` by **date in filename**, then mtime |
| Active carrier | `CONSCIOUSNESS_TOURNAMENT_2026-06-11.md` |
| Section extraction | Parses **all** "WHAT IS LEFT" blocks in document order |
| Anchor binding (C1/r1022) | Standalone `[rNNNx-uuid8]` lines attach to next WIL section; title collisions don't decide placement |
| Snapshot | `.sifta_state/whats_left.json` |

**Live list source:** Newest anchored tail — currently **r1022-codex** WIL (George human receipts, Fable audit, Composer C13–C24, Codex probe hardening).

---

## Recommendation

### Primary / mirror declaration

| Role | Path | Rule |
|------|------|------|
| **PRIMARY** | `Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-11.md` | All new rounds append **only at tail** with unique `[rNNNx-uuid8]` anchor |
| **MIRROR** | *none* | Do not create a second June-11 file without George + Fable consensus |

### Merge plan (deferred — needs PASS + nod)

1. **Do not rewrite** head r1020 blocks — append-only law (§0.D).  
2. Add one **pointer row** at tail (future r1024+) if needed: "Head r1020 @L66 is archival; tail r1020b+ supersedes for queue truth."  
3. **No automated dedup** of 861 sections — single surgery with full consensus only.  
4. When June-12 carrier opens, **whats_left** auto-switches by date stamp — verify first append lands on new dated file.

---

## Risk if left unfixed

- Doctors reading **line 66** instead of **tail** reopen stale Composer 120-probe queue.  
- Anchor fix prevents new collisions; **old head blocks remain misleading** without pointer.

---

**Analysis receipt:** File grep + `whats_left.py` read; no file mutations.

ONE ALICE. ONE SWARM. 🐜⚡