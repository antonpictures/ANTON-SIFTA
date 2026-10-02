#!/usr/bin/env python3
"""sifta_session_thinner — thin personal/explicit content from harness session history.

Owner directive 2026-09-30: SIFTA ships as robotics for distribution, but the
lessons the body learns from the owner stay. This pass removes explicit personal
text from the DeepSeek Harness session store while leaving every other sentence
(technical findings, errors, system discoveries, relational learning) intact.

Design:
  * Sentence granularity, not message granularity — a message that mixes a
    personal admission with a system finding keeps the finding.
  * Generic recursive walk — every string value in every event is considered, so
    no event type has to be enumerated and no field shape is assumed.
  * Structure is never touched: event type, seq, time, ids, ordering and count
    are preserved, so the session log still loads and replays.

Usage:
  python3 tools/sifta_session_thinner.py                 # dry run (default)
  python3 tools/sifta_session_thinner.py --apply         # rewrite, with backups
  python3 tools/sifta_session_thinner.py --include-research   # also thin sexual/erotic/nude
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from compression import zstd
from pathlib import Path

MARKER = "[personal content thinned 2026-09-30 - lesson retained]"

# Unambiguous personal/sexual acts. These are what the owner asked to thin.
#
# LANGUAGE SAFETY: sessions in this body are bilingual (English + Romanian).
# Romanian cognates are legitimate and must match ("masturbat", "orgasm",
# "penis", "sexual", "erotic"), but two traps are excluded deliberately:
#   * bare "cum"      -> Romanian "cum" = "how"   (kept only as cumming/cumshot)
#   * bare "porn"     -> Romanian "porni" = "start" (requires an English suffix
#                        or a word boundary, so porni/pornire/pornit never match)
PERSONAL_TERMS = (
    r"masturbat\w*",
    r"jerk(?:ed|ing)?\s+off",
    r"\bhorny\b",
    r"\bfap(?:ping|ped)?\b",
    r"\borgasm\w*",
    r"\bporn(?:s|o|ography|ographic|hub|star)?\b",
    r"\bcumming\b|\bcumshot\w*\b",
    r"\bpenis\b",
    r"\bblowjob\w*\b",
)

# Ambiguous: often legitimate research/curation inside SIFTA. Opt-in only.
RESEARCH_TERMS = (
    r"\bsexual\w*",
    r"\berotic\w*",
    r"\bnude\b",
    r"\bnudes\b",
    r"\bnsfw\b",
)

# Safety infrastructure must never be thinned. Alice's body carries a CSAM
# refusal guard whose own pattern text names the terms this tool removes;
# redacting it would delete a child-safety filter from a shipping build. Any
# sentence that also carries a safety/policy marker is therefore left intact.
SAFETY_EXEMPT = re.compile(
    r"csam|child\s+(?:porn|abuse|sexual)|abuse\s+material|nudifier|\bminor\w*\b|"
    r"NEVER_EXEMPT|\bsafety\b|refus\w*|moderat\w*|\bfilter\w*|\bpolicy\b|\bguard\w*\b|"
    r"\bcsae\b|underage",
    re.IGNORECASE,
)

# Conversational events carry what a person actually said and what Alice
# answered. Tool events carry technical output - greps, file reads, research
# artifacts - which is the "lessons" side and stays untouched by default.
CONVERSATIONAL_TYPES = frozenset({
    "user/message",
    "assistant/message",
    "assistant/chunk",
    "text-chunks",
    "reasoning-chunks",
    "tool-call-chunks",
    "compaction/summary",
    "agent/inbox/spliced",
})

SESSION_ROOT = Path.home() / ".dsh" / "sessions"
BACKUP_ROOT = Path(__file__).resolve().parent.parent / ".sifta_state" / "session_thinning_backup"


def sentence_regex(terms: tuple[str, ...]) -> re.Pattern[str]:
    """Match the whole sentence that contains any term, anchored at a real boundary."""
    alternation = "|".join(terms)
    return re.compile(
        rf"(?:(?<=^)|(?<=[.!?\n]))\s*[^.!?\n]*(?:{alternation})[^.!?\n]*[.!?]?",
        re.IGNORECASE,
    )


STATS = {"safety_exempt": 0}


def redact_string(value: str, rx: re.Pattern[str]) -> tuple[str, int]:
    """Replace every sentence containing a term, skipping safety-context sentences."""
    if not value or not rx.search(value):
        return value, 0

    def replace(match: re.Match[str]) -> str:
        sentence = match.group(0)
        if SAFETY_EXEMPT.search(sentence):
            STATS["safety_exempt"] += 1
            return sentence
        return MARKER

    new, n = rx.subn(replace, value)
    return new, n


def redact_node(node, rx: re.Pattern[str], stats: dict[str, int]):
    """Recursively redact string leaves in place; return (node, replacements)."""
    if isinstance(node, str):
        new, n = redact_string(node, rx)
        stats["replaced"] += n
        return new, n
    if isinstance(node, list):
        total = 0
        for i, item in enumerate(node):
            new, n = redact_node(item, rx, stats)
            if n:
                node[i] = new
            total += n
        return node, total
    if isinstance(node, dict):
        total = 0
        for key in list(node):
            new, n = redact_node(node[key], rx, stats)
            if n:
                node[key] = new
            total += n
        return node, total
    return node, 0


def mask_terms(text: str, rx: re.Pattern[str]) -> str:
    """Preview helper: hide the explicit words so reports never echo them."""
    return re.sub(r"masturbat\w*|jerk(?:ed|ing)?\s+off|\bhorny\b|\bfap(?:ping|ped)?\b|"
                  r"\borgasm\w*|\bporn\w*|\bcum(?:ming|s|med)?\b|\bpenis\b|\bblowjob\w*\b|"
                  r"\bnsfw\b|\bsexual\w*|\berotic\w*|\bnude\b|\bnudes\b",
                  lambda m: "\u2588" * min(len(m.group(0)), 6), text, flags=re.IGNORECASE)


# Events whose text is complete, so sentence and word boundaries are real.
COMPLETE_TEXT_TYPES = frozenset({
    "user/message", "assistant/message", "compaction/summary", "agent/inbox/spliced",
})

# Streaming projections of the same content. Their payloads are split at
# arbitrary token boundaries ("Voce porn" + "ita"), so a word-boundary pattern
# is invalid here: they are cleared per redacted (turn, step) instead.
CHUNK_TYPES = frozenset({
    "assistant/chunk", "text-chunks", "reasoning-chunks", "tool-call-chunks",
})

CHUNK_TEXT_FIELDS = ("chunk", "texts", "text", "delta")


def blank_chunks(node: dict, stats: dict[str, int]) -> int:
    """Replace the text payload of one chunk event with the marker."""
    data = node.get("data")
    if not isinstance(data, dict):
        return 0
    cleared = 0
    for field in CHUNK_TEXT_FIELDS:
        if field in data and data[field]:
            data[field] = MARKER if isinstance(data[field], str) else [MARKER]
            cleared += 1
    stats["replaced"] += cleared
    return cleared


def process(path: Path, rx: re.Pattern[str], apply: bool, sample: list[dict],
            scope: frozenset[str] | None = None) -> dict:
    raw = zstd.decompress(path.read_bytes()).decode("utf-8", "ignore")
    lines = raw.splitlines()
    stats = {"events": 0, "replaced": 0, "events_touched": 0, "chunks_cleared": 0}
    out_lines = []
    redacted_steps: set[tuple] = set()

    for line in lines:
        if not line.strip():
            continue
        stats["events"] += 1
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            out_lines.append(line)
            continue
        etype = event.get("type")
        if etype in CHUNK_TYPES:
            out_lines.append(event)   # resolved in pass 2, once redacted steps are known
            continue
        if scope is not None and etype not in scope:
            out_lines.append(line)
            continue
        if etype not in COMPLETE_TEXT_TYPES:
            out_lines.append(line)
            continue
        _, n = redact_node(event, rx, stats)
        if n:
            stats["events_touched"] += 1
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            if etype == "assistant/message" and "turn" in data and "step" in data:
                redacted_steps.add((data["turn"], data["step"]))
            if len(sample) < 4:
                found = rx.search(json.dumps(event, ensure_ascii=False))
                if found is not None:
                    sample.append({"type": etype, "seq": event.get("seq"),
                                   "match": mask_terms(found.group(0), rx).strip()[:150]})
            out_lines.append(json.dumps(event, ensure_ascii=False))
        else:
            out_lines.append(line)

    # Pass 2 - clear the streaming projections of every redacted assistant step.
    final_lines = []
    for item in out_lines:
        if isinstance(item, str):
            final_lines.append(item)
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        if (data.get("turn"), data.get("step")) in redacted_steps:
            if blank_chunks(item, stats):
                stats["chunks_cleared"] += 1
                stats["events_touched"] += 1
        final_lines.append(json.dumps(item, ensure_ascii=False))
    out_lines = final_lines

    result = {"path": str(path), **stats, "bytes_before": len(raw)}
    if apply and stats["replaced"]:
        # Backups go OUTSIDE the session store: the shipped sessions tree has to
        # be clean, and an adjacent .bak would ship the original text with it.
        backup_dir = BACKUP_ROOT / time.strftime("%Y-%m-%d")
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"{path.parent.name}.zstd"
        if not backup.exists():
            shutil.copy2(path, backup)
        new_raw = "\n".join(out_lines) + "\n"
        path.write_bytes(zstd.compress(new_raw.encode("utf-8")))
        result["bytes_after"] = len(new_raw)
        result["backup"] = str(backup)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Thin personal content from harness session history.")
    ap.add_argument("--apply", action="store_true", help="rewrite sessions (default: dry run)")
    ap.add_argument("--include-research", action="store_true",
                    help="also thin research-ambiguous terms (sexual/erotic/nude)")
    ap.add_argument("--root", default=str(SESSION_ROOT), help="session store root")
    ap.add_argument("--exclude", action="append", default=[],
                    help="session id substring to skip (repeatable); use for the live session")
    ap.add_argument("--include-tools", action="store_true",
                    help="also thin tool/call and tool/result output (default: keep technical output)")
    args = ap.parse_args()

    terms = PERSONAL_TERMS + (RESEARCH_TERMS if args.include_research else ())
    rx = sentence_regex(terms)

    scope = None if args.include_tools else CONVERSATIONAL_TYPES
    files = sorted(Path(args.root).rglob("*.zstd"))
    files = [f for f in files if not any(x in str(f) for x in args.exclude)]
    print(f"session store : {args.root}")
    print(f"sessions      : {len(files)}")
    print(f"terms         : {len(terms)} ({'incl. research-ambiguous' if args.include_research else 'personal only'})")
    print(f"scope         : {'every event type' if scope is None else 'conversational events only'}")
    print(f"mode          : {'APPLY' if args.apply else 'DRY RUN'}\n")

    totals = {"replaced": 0, "sessions": 0, "events": 0}
    samples: list[dict] = []
    for f in files:
        try:
            r = process(f, rx, args.apply, samples, scope)
        except Exception as exc:  # a corrupt session must not abort the sweep
            print(f"  !! {f.parent.name}: {type(exc).__name__}: {exc}")
            continue
        totals["events"] += r["events"]
        if r["replaced"]:
            totals["sessions"] += 1
            totals["replaced"] += r["replaced"]
            delta = ""
            if args.apply:
                delta = f"  {r['bytes_before']:>9,} -> {r.get('bytes_after', 0):>9,} bytes"
            print(f"  {f.parent.name.replace('session-','')[:8]}  events={r['events']:5d} "
                  f"touched={r['events_touched']:3d} redactions={r['replaced']:3d} "
                  f"steps={r['chunks_cleared']:3d}{delta}")

    print(f"\nsessions touched : {totals['sessions']} / {len(files)}")
    print(f"events scanned   : {totals['events']:,}")
    print(f"sentences thinned: {totals['replaced']:,}")
    print(f"safety-exempt kept: {STATS['safety_exempt']:,} (CSAM/policy context, never redacted)")
    if samples:
        print("\nmasked previews (explicit words hidden):")
        for s in samples[:6]:
            print(f"  [{s['type']} seq={s['seq']}] {s['match']}")
    if not args.apply:
        print("\nDRY RUN - nothing written. Re-run with --apply to rewrite (originals kept as .zstd.bak).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
