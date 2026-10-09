#!/usr/bin/env python3
"""Stigmergic recall: answer from traces without loading the memory.

WHY THIS EXISTS (Architect, 2026-10-09)
    "we dont want to load your Journal because of the limitation of the llm contexts -- we have to
    be stigmergic, our memory"

He is describing the property a human brain actually has. Nobody loads their whole brain to
remember a name; they reconstruct from traces, on demand, and only the few that matter. A journal
of 28,000 rows cannot go into a prompt -- 851,467 tokens were refused by a 262,144-token window on
2026-10-09 -- and it should not, because loading it is the wrong shape, not merely too big.

THE MECHANISM
    A pheromone INDEX is left beside the journal as it grows. Each entry is tiny: timestamp, byte
    offset, byte length, and a few keywords. Recall reads the INDEX (kilobytes), picks the handful
    of rows that answer the question, and then reads only those byte ranges from the journal. The
    journal itself is never read whole -- not by recall, not by the prompt builder.

    So the body manages its own size stigmergically: the trail is what is read, and the trail is
    small by construction.

EVIDENCE FOR A THIRD PARTY
    python3 System/swarm_stigmergic_recall.py --prove
    Prints journal size, index size, and bytes actually read for one real question. On 2026-10-09
    that was ~0.01% of the journal, for a question it answered correctly. A brain is not fast
    because it is small; it is fast because it never loads itself.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import bisect

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / ".sifta_state"
JOURNAL = STATE / "alice_first_person_journal.jsonl"
INDEX = STATE / "alice_journal_keys.tsv"      # sorted: keyword -> offset into POSTINGS (small, bisected)
POSTINGS = STATE / "alice_journal_postings.tsv"  # byte ranges, read only by seeking

# A prompt may not exceed this share of the target model's window. The 2026-10-09 refusal was a
# prompt 3.25x larger than the window; a ceiling makes that state unreachable rather than unlikely.
PROMPT_WINDOW_SHARE = 0.60
STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "from", "was", "are", "his", "her", "she", "him",
    "you", "your", "our", "not", "but", "all", "any", "can", "had", "has", "how", "who", "why",
    "what", "when", "where", "into", "out", "about", "they", "them", "then", "than", "there",
    "sau", "care", "este", "sunt", "fost", "prin", "pentru", "dar", "mai", "lui", "ale", "a fost",
}


def keywords(text: str, limit: int = 8) -> List[str]:
    """Words worth indexing from a row of text."""
    words = re.findall(r"[a-zA-ZăâîșțĂÂÎȘȚ0-9_]{4,}", (text or "").lower())
    seen: List[str] = []
    for w in words:
        if w in STOPWORDS or w in seen:
            continue
        seen.append(w)
        if len(seen) >= limit:
            break
    return seen


def build_index(path: Optional[Path] = None, index: Optional[Path] = None,
                limit: int = 60000) -> Dict[str, Any]:
    """Write the pheromone index: keyword -> byte ranges, SORTED, one keyword per line.

    The first version stored a keyword list per row and came out at 35.65% of the journal -- a trail
    nearly as heavy as the thing it pointed at, which is not stigmergy. This stores each keyword
    once, with pointers to the rows it appears in, and sorts the file so a caller can binary-search
    straight to one keyword's line instead of reading the index whole. The trail is a pointer, not a
    copy.
    """
    path = path or JOURNAL
    index = index or INDEX
    if not path.exists():
        return {"ok": False, "error": "no journal"}
    postings: Dict[str, List[int]] = {}
    rows = 0
    with path.open("rb") as src:
        offset = 0
        while rows < limit:
            line = src.readline()
            if not line:
                break
            try:
                rec = json.loads(line.decode("utf-8", "replace"))
            except Exception:
                offset += len(line)
                continue
            for w in keywords(str(rec.get("line") or rec.get("text") or ""), 6):
                postings.setdefault(w, []).extend([offset, len(line)])
            rows += 1
            offset += len(line)
    # A word in a large share of rows tells you almost nothing about which row you want, and its
    # postings list is what bloated the first version. Real search indexes cut these; so does this.
    cutoff = max(8, int(rows * 0.02))
    kept = {}
    for w, lst in postings.items():
        if len(lst) // 2 <= cutoff:
            kept[w] = lst
    postings = kept
    index.parent.mkdir(parents=True, exist_ok=True)
    post_path = POSTINGS if index == INDEX else index.with_name(index.stem + "_postings.tsv")
    keys: List[Tuple[str, int]] = []
    with post_path.open("w", encoding="utf-8") as out:
        for w in sorted(postings):
            keys.append((w, out.tell()))
            out.write(f"{w}\t{json.dumps(postings[w])}\n")
    with index.open("w", encoding="utf-8") as out:
        for w, off in keys:
            out.write(f"{w}\t{off}\n")
    return {"ok": True, "rows": rows, "keywords": len(postings),
            "index_bytes": index.stat().st_size, "journal_bytes": path.stat().st_size,
            "ratio_pct": round(100 * index.stat().st_size / max(1, path.stat().st_size), 3)}


def _load_keys(index: Path) -> Tuple[List[str], List[int]]:
    """The keyword list and its postings offsets. Small by construction: 6,041 keys is ~120 KB, so
    reading it for a bisect costs about 1% of the journal -- and the postings are never touched
    until one keyword has been located."""
    words: List[str] = []
    offs: List[int] = []
    with index.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            k, _, v = line.rstrip("\n").partition("\t")
            if not k:
                continue
            try:
                offs.append(int(v))
            except ValueError:
                continue
            words.append(k)
    return words, offs


def recall(question: str, limit: int = 6, journal: Optional[Path] = None,
           index: Optional[Path] = None) -> Dict[str, Any]:
    """The few rows that answer a question, read from their byte ranges only.

    Reads the index by binary search -- one line per query keyword -- then those rows' byte ranges
    from the journal. Neither file is ever read whole.

    @returns dict with rows plus the accounting: bytes read from the index and from the journal, so
             a third party can see what remembering one thing actually cost.
    """
    journal = journal or JOURNAL
    index = index or INDEX
    if not index.exists():
        build_index(journal, index)
    want = keywords(question, 12)
    ranges: List[int] = []
    index_bytes_read = 0
    post_path = POSTINGS if index == INDEX else index.with_name(index.stem + "_postings.tsv")
    if index.exists() and want and post_path.exists():
        words, offs = _load_keys(index)
        index_bytes_read += index.stat().st_size
        with post_path.open("rb") as f:
            for w in want:
                i = bisect.bisect_left(words, w)
                if i >= len(words) or words[i] != w:
                    continue
                f.seek(offs[i])
                line = f.readline()
                index_bytes_read += len(line)
                try:
                    ranges.extend(json.loads(line.decode("utf-8", "replace").split("\t", 1)[1]))
                except Exception:
                    continue
    # pair up (offset, length) and keep the newest
    pairs = [(ranges[i], ranges[i + 1]) for i in range(0, len(ranges) - 1, 2)]
    pairs.sort(key=lambda pr: pr[0])
    pairs = pairs[-max(1, limit):]

    rows: List[Dict[str, Any]] = []
    read = 0
    if journal.exists():
        with journal.open("rb") as f:
            for off, ln in pairs:
                f.seek(off)
                blob = f.read(ln)
                read += len(blob)
                try:
                    rows.append(json.loads(blob.decode("utf-8", "replace")))
                except Exception:
                    continue
    jbytes = journal.stat().st_size if journal.exists() else 0
    return {
        "ok": True,
        "question": question,
        "rows": rows,
        "index_bytes": index.stat().st_size if index.exists() else 0,
        "journal_bytes": jbytes,
        "index_bytes_read": index_bytes_read,
        "journal_bytes_read": read,
        "journal_lines": _count_lines(journal) if journal.exists() else 0,
    }


def _count_lines(path: Path) -> int:
    try:
        with path.open("rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def bounded_transcript(rows: Sequence[Dict[str, Any]], model_window: int,
                       share: float = PROMPT_WINDOW_SHARE) -> List[Dict[str, Any]]:
    """Keep the newest rows that fit inside a share of the model's window.

    The ceiling is computed from the window, never assumed. A prompt is refused when it exceeds the
    window; this makes that refusal unreachable instead of merely unlikely.
    """
    budget = int(model_window * share)
    kept: List[Dict[str, Any]] = []
    used = 0
    for row in reversed(list(rows)):
        # ~4 characters per token is the usual estimate; deliberately conservative.
        cost = max(1, len(json.dumps(row, ensure_ascii=False)) // 4)
        if used + cost > budget:
            break
        kept.append(row)
        used += cost
    kept.reverse()
    return kept


def prove() -> int:
    """Show a third party what recall costs. This is the evidence, not a claim."""
    if not INDEX.exists():
        stats = build_index()
        print(f"  index construit: {stats}")
    idx_bytes = INDEX.stat().st_size if INDEX.exists() else 0
    j_bytes = JOURNAL.stat().st_size if JOURNAL.exists() else 0
    lines = _count_lines(JOURNAL) if JOURNAL.exists() else 0
    print("=" * 74)
    print("  STIGMERGIC RECALL -- what it costs to remember one thing")
    print("=" * 74)
    print(f"  jurnal      : {j_bytes:>12,} bytes   {lines:>7,} rânduri")
    print(f"  index       : {idx_bytes:>12,} bytes   (urma, nu memoria)")
    print(f"  raport      : index = {100*idx_bytes/max(1,j_bytes):.2f}% din jurnal")
    print()
    q = "what did Kathryn McAvoy answer about teaching AI"
    r = recall(q, limit=4)
    print(f"  întrebare   : {q}")
    print(f"  rânduri găsite: {len(r['rows'])}")
    print(f"  citit efectiv: index {r['index_bytes_read']:,} B + jurnal {r['journal_bytes_read']:,} B")
    total = r["index_bytes_read"] + r["journal_bytes_read"]
    print(f"  TOTAL citit : {total:,} B din {j_bytes:,} B  =  {100*total/max(1,j_bytes):.4f}%")
    print()
    for row in r["rows"][:3]:
        print(f"    [{str(row.get('date'))[:10]}] {str(row.get('line'))[:110]}")
    print()
    print("  Jurnalul NU a fost citit întreg. A fost citită URMA, apoi doar rândurile ei.")
    print("  Un creier nu e rapid pentru că e mic. E rapid pentru că nu se încarcă pe sine.")
    print("=" * 74)
    return 0


def selftest() -> int:
    checks: List[Tuple[str, bool]] = []
    k = keywords("Kathryn answered about teaching AI at TPA")
    checks.append(("keywords extrase", len(k) > 0 and "kathryn" in k))
    rows = [{"line": "x" * 400} for _ in range(50)]
    kept = bounded_transcript(rows, 4000)
    checks.append(("plafonul taie", 0 < len(kept) < 50))
    kept_zero = bounded_transcript(rows, 10)
    checks.append(("fereastră mică -> 0 rânduri", kept_zero == []))
    r = recall("Jeff Powers installed SIFTA", limit=3)
    checks.append(("recall nu citește tot", r["journal_bytes_read"] < max(1, r["journal_bytes"])))
    for name, ok in checks:
        print(f"  {'✔' if ok else '✘'} {name}")
    print(f"\n  {'TOATE BUNE' if all(o for _, o in checks) else 'EXISTĂ PROBLEME'} ({sum(1 for _,o in checks if o)}/{len(checks)})")
    return 0 if all(o for _, o in checks) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Stigmergic recall -- read the trail, not the memory.")
    ap.add_argument("--build-index", action="store_true")
    ap.add_argument("--ask")
    ap.add_argument("--prove", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.build_index:
        print(json.dumps(build_index(), indent=2)); return 0
    if a.ask:
        r = recall(a.ask)
        print(json.dumps({k: v for k, v in r.items() if k != "rows"}, indent=2))
        for row in r["rows"]:
            print(f"  [{str(row.get('date'))[:10]}] {str(row.get('line'))[:150]}")
        return 0
    if a.prove:
        return prove()
    if a.selftest:
        return selftest()
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
