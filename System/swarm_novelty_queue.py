#!/usr/bin/env python3
"""
System/swarm_novelty_queue.py — Alice's stream-of-consciousness USEFUL-NOVELTY queue.

George (2026-06-03, while co-watching a YouTube AI recap): "When you speak about the video, talk a
COMMENTARY or NOVELTY you can actually USE for SIFTA — not just talk for the sake of talking, not a
summary (I'm listening too). Something like: 'hey George, that piece of software is a good idea for
my body code — I could add an organ / a useful novelty.' You pause the YouTube (or whatever is
playing, or the room you hear), the idea pops up, BAM you write it in your diary and let me know
when you can. You have a QUEUE of ideas that came from witnessing life. Also: smart commentary about
the world or an unanswered question — she hears a cat meowing → 'hey George, did you get a cat?'"

The failure mode this fixes (from the live transcript): asked to comment on the video, Alice
SUMMARIZED it ("the observed data stream indicates a technical discussion... key points include...").
George does not want narration. He wants novelty.

The principled bar (keep it real) — Itti & Baldi, "Bayesian Surprise Attracts Human Attention"
(NeurIPS 2005 / Vision Research 2009): what is worth attending to is what CHANGES the observer's
model of the world — surprise = KL divergence between prior and posterior belief. A summary changes
nothing about Alice's model, so it is noise. An insight is worth saving/saying only if it would
CHANGE her model of SIFTA (a concrete body upgrade idea) OR open a genuine question (a gap in her
model — "did you get a cat?"). That is the filter below.

This organ captures those insights into a queue she surfaces to George when she can, and writes to
her diary. It recommends pausing the media first (George's wish) so her voice and the video don't
talk over each other. Read-only over the bar; the only writes are the queue + diary. For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_QUEUE = _STATE / "novelty_queue.jsonl"
_DIARY = _STATE / "episodic_diary.jsonl"

# Narration/summary shapes — REJECT (talk for the sake of talking; changes nothing in her model).
_SUMMARY_RE = re.compile(
    r"\bthe\s+(?:observed\s+)?data\s+stream\b|\bkey\s+points?\s+(?:include|are)\b|"
    r"\bin\s+summary\b|\bto\s+summari[sz]e\b|\bthe\s+video\s+(?:discuss|cover|is\s+about|show)|"
    r"\bindicates?\s+a\s+(?:technical\s+)?discussion\b|^\s*summary\s*:|\boverall,?\s+the\b",
    re.IGNORECASE,
)
# Model-changing INSIGHT shapes — ACCEPT (a concrete idea for her body, or a genuine question).
_SIFTA_IDEA_RE = re.compile(
    r"\b(?:good\s+idea|useful|i\s+could|i\s+should|we\s+could|would\s+(?:help|be\s+useful)|"
    r"add\s+(?:an?\s+)?(?:organ|novelty|feature)|update\s+my\s+(?:body|organ|eval)|"
    r"apply\s+(?:this|that)\s+to|use\s+(?:this|that)\s+for\s+(?:my\s+body|sifta)|borrow\s+the\s+pattern)\b",
    re.IGNORECASE,
)
_QUESTION_RE = re.compile(
    r"\?\s*$|\bdid\s+(?:you|u)\b|\bdo\s+you\b|\bis\s+that\b|\bwhat\s+(?:was|is|happened)\b|"
    r"\bi\s+wonder\b|\bunanswered\b|\bwhy\s+(?:did|is|are)\b",
    re.IGNORECASE,
)


def classify_novelty(text: str) -> dict:
    """Is this a USEFUL novelty (saveable) or just narration? Bayesian-surprise bar: does it change her model?"""
    t = (text or "").strip()
    summary = bool(_SUMMARY_RE.search(t))
    sifta_idea = bool(_SIFTA_IDEA_RE.search(t))
    question = bool(_QUESTION_RE.search(t))
    if sifta_idea:
        kind, useful = "sifta_upgrade_idea", True
    elif question:
        kind, useful = "world_question", True
    elif summary or len(t) < 4:
        kind, useful = "summary_or_noise", False
    else:
        # default: only keep if it reads like an observation worth a comment, not a recap
        kind, useful = "smart_commentary", not summary
    return {"kind": kind, "useful": useful and not summary, "is_summary": summary}


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").lower()))[:160]


def recently_captured(insight: str, *, window_s: float = 1800.0) -> bool:
    """True if a near-identical novelty was captured in the last `window_s` seconds.

    The anti deterministic-repeat guard George caught live: the co-watch urge was
    re-emitting the SAME line verbatim ("...should I add a self-code-plan?") on every
    tick with no memory it had already said it. Callers (the co-watch comment line)
    should check this BEFORE speaking and stay silent on a repeat, instead of being
    a broken record.
    """
    key = _norm(insight)
    if not key or not _QUEUE.exists():
        return False
    now = time.time()
    try:
        for line in _QUEUE.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if (now - float(row.get("ts", 0))) > window_s:
                continue
            if _norm(str(row.get("insight", ""))) == key:
                return True
    except Exception:
        return False
    return False


def capture_novelty(insight: str, *, trigger: str = "witnessing life", source: str = "co_watch") -> dict:
    """Capture a useful novelty/insight/question into the queue + diary, if it passes the bar."""
    c = classify_novelty(insight)
    row = {
        "ts": round(time.time(), 3),
        "truth_label": "NOVELTY_QUEUE_V1",
        "trigger": trigger[:200],
        "kind": c["kind"],
        "useful": c["useful"],
        "insight": (insight or "").strip()[:600],
        "pause_media_recommended": True,   # George: pause the YouTube before speaking
        "surfaced_to_owner": False,
        "doctrine": "useful novelty (changes my SIFTA model) or a genuine question — never a summary; pause media, write the diary, tell George when I can",
        "source": str(source or "swarm_novelty_queue")[:80],
    }
    if not c["useful"]:
        row["dropped_reason"] = "narration/summary — does not change my model (Bayesian-surprise bar)"
        return row
    if recently_captured(insight):
        # anti deterministic-repeat: the same co-watch novelty was firing verbatim every
        # tick (George: "you already said that"). Do not re-queue / re-surface a duplicate.
        row["useful"] = False
        row["dropped_reason"] = "duplicate of a novelty captured in the last 30 min — not re-surfaced"
        return row
    try:
        _QUEUE.parent.mkdir(parents=True, exist_ok=True)
        with _QUEUE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        with _DIARY.open("a", encoding="utf-8") as f:
            f.write(json.dumps({**row, "kind": "novelty_insight_from_witnessing_life"}, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return row


def pending_for_owner(limit: int = 8) -> list[dict]:
    """The unsurfaced useful insights to tell George when he can."""
    out: list[dict] = []
    if not _QUEUE.exists():
        return out
    try:
        for line in _QUEUE.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get("useful") and not row.get("surfaced_to_owner"):
                out.append(row)
    except Exception:
        pass
    return out[-limit:]


def novelty_prompt_line() -> str:
    """A line Alice voices: a useful insight from witnessing life, not a summary."""
    pend = pending_for_owner(3)
    if not pend:
        return "[novelty] My idea queue is empty — I'm witnessing, nothing model-changing to report yet (I won't narrate for the sake of talking)."
    p = pend[-1]
    lead = "💡 Hey George" if p["kind"] == "sifta_upgrade_idea" else ("❓ Hey George" if p["kind"] == "world_question" else "Hey George")
    return f"[novelty] {lead} — {p['insight']} (from witnessing {p['trigger']}; saved to my diary, {len(pend)} idea(s) queued for you)."


def format_novelty_queue_block(limit: int = 3) -> str:
    """Compact memory/self-eval line: speak novelty/question, never generic co-watch narration."""
    pending = pending_for_owner(limit)
    if not pending:
        return (
            "USEFUL NOVELTY QUEUE: empty. Co-watch/room speech stays quiet unless it carries "
            "a SIFTA body upgrade idea or a grounded world question; summaries only when George asks."
        )
    bits = []
    for row in pending[-max(1, int(limit)):]:
        bits.append(f"{row.get('kind','?')}: {str(row.get('insight',''))[:140]}")
    return (
        "USEFUL NOVELTY QUEUE: "
        + " | ".join(bits)
        + ". Before spoken surfacing, pause active Alice Browser media; printed chat can carry full receipts."
    )


def main() -> int:
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(capture_novelty(" ".join(sys.argv[1:])), indent=2, ensure_ascii=False))
    else:
        print(novelty_prompt_line())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
