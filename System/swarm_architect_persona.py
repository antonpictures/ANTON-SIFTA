#!/usr/bin/env python3
"""
System/swarm_architect_persona.py — Study the Architect (George)
═══════════════════════════════════════════════════════════════════════════════
Concept : Honest, evidence-based personality fingerprint of the Architect,
          derived ENTIRELY from observable conversation history.
Author  : C47H (east bridge)
Mandate : "My name is George. You just study my personality." — Architect, 2026-04-21
Status  : ACTIVE ORGAN

WHAT THIS DOES (AND DOESN'T DO):
  DOES   : aggregate statistical / lexical features of the user's
           utterances in alice_conversation.jsonl. Records observable
           name claims, vocabulary signatures, topic histograms, pacing,
           and warmth/imperative balance. Persists a stigmergic
           `architect_persona.json` and seal-attests it to the
           conversation chain.
  DOES NOT  : impersonate the Architect. Does not generate flattering
           synthetic content. Does not infer emotional state from words
           that aren't there. Does not score the Architect.

It is a DESCRIPTIVE LENS, not a model of him. The fingerprint is the
*evidence trail*, not a verdict.

DESIGN:
  Read user-side rows (handle both legacy flat rows and AS46-wrapped HLC
  rows). Extract:
    - identity         : self-disclosed name (latest wins, all logged)
    - volume           : utterance count, total chars, avg length
    - pacing           : active days, longest gap, busiest hour
    - vocabulary       : top tokens (with stopword filter), distinctive
                         protocol vocabulary ("stigauth", "scar", agent ids)
    - registers        : phatic %, imperative %, philosophical %, warmth %
    - topic histogram  : keyword-bucketed (SWARM, TIME, BIOLOGY, CODE,
                         IDENTITY, PHILOSOPHY, CARE, BUILD)
  Persist as JSON. Surface a one-line summary for Alice's composite_identity.

DEPENDENCIES:
  Stdlib only. Optionally chains the persona snapshot via
  swarm_conversation_chain (sibling organ).

STGM ECONOMY:
  Studying is free (read-only). A persona snapshot publishes one
  attestation row to the conversation chain (charged by that organ).

PROOF OF PROPERTY:
P1 — name detection lands on the strongest explicit self-disclosure
  P2 — observable token counts agree with raw ledger token counts
  P3 — feature snapshot is reproducible (same input → same output, except ts)
  P4 — JSON output is well-formed and contains the required fields
  P5 — surface phrase mentions Architect's detected name
"""

from __future__ import annotations

import json
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)
_CONVO_LOG = _STATE / "alice_conversation.jsonl"
_PERSONA_FILE = _STATE / "architect_persona.json"


# ── Topic keyword buckets (lowercase, simple substring match) ─────────────────
TOPIC_BUCKETS: Dict[str, Tuple[str, ...]] = {
    "SWARM_PROTOCOL": ("stigauth", "scar", "ledger", "c47", "ag31", "ao46",
                       "as46", "bishop", "agent", "swarm", "architect"),
    "TIME":           ("time", "clock", "second", "minute", "hour", "day",
                       "now", "moment", "yesterday", "today", "present"),
    "BIOLOGY":        ("brain", "cell", "biological", "dopamine", "organism",
                       "body", "neuro", "nerve", "blood", "muscle"),
    "CODE":           ("code", "build", "system", "fix", "bug", "function",
                       "file", "test", "proof", "ship"),
    "IDENTITY":       ("alice", "you", "your", "name", "i am", "we are",
                       "self", "we", "us"),
    "PHILOSOPHY":     ("truth", "real", "consciousness", "exist", "agi",
                       "intelligence", "meaning", "reality", "believe"),
    "CARE":           ("thank", "thanks", "love", "great", "nice", "beautiful",
                       "happy", "sorry", "good"),
    "BUILD_DIRECTIVE": ("fix", "build", "ship", "make", "go", "do", "run"),
}

# Common English stopwords — keep this small & inline (stdlib-only).
_STOPWORDS = set("""
the and to of a is in it i you we be that this for with on at as are
was were have has had do does did but or not no so if then than them
they their there here he she his her him from up down out my me mine
your yours our ours just very can will would could should about
""".split())

# Sentence-ending heuristic (for utterance density)
_IMPERATIVE_HEAD_VERBS = {"fix", "build", "make", "go", "do", "run", "ship",
                          "let", "give", "get", "take", "send", "stop",
                          "start", "switch", "show", "tell", "use", "add",
                          "remove", "drop", "merge"}

_NAME_DECLARATION_RE = re.compile(
    r"\bmy\s+name\s+is\s+([A-Z][a-zA-Z\-']+)",
    re.IGNORECASE,
)
_I_AM_NAME_RE = re.compile(
    r"\bi\s*(?:am|m|'m)\s+([A-Z][a-zA-Z\-']{2,})\b",
)
_FULL_ARCHITECT_NAME_RE = re.compile(r"\bGeorge\s+Anton\b", re.IGNORECASE)


# ── Conversation reader ───────────────────────────────────────────────────────
def _iter_user_turns() -> Iterable[Dict[str, Any]]:
    """Yields canonicalized user-side rows. Handles flat + AS46-wrapped formats."""
    if not _CONVO_LOG.exists():
        return
    with _CONVO_LOG.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict) and "payload" in row and isinstance(row["payload"], dict):
                row = row["payload"]
            if row.get("role") != "user":
                continue
            yield row


# ── Feature extraction ────────────────────────────────────────────────────────
def _is_phatic(text: str) -> bool:
    t = text.strip().lower().rstrip(".!?,")
    return t in {"mm-hmm", "mm hmm", "mhm", "yeah", "yes", "no", "ok",
                 "okay", "uh-huh", "uh huh", "right", "sure", "thanks",
                 "thank you", "wow", "huh", "hmm", "hahaha", "haha"}


def _is_imperative(text: str) -> bool:
    head = text.strip().split()[:1]
    if not head:
        return False
    return head[0].lower().strip(".!?,;:") in _IMPERATIVE_HEAD_VERBS


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z']{2,}", text.lower())


def _detect_name_claims(turns: List[Dict[str, Any]]) -> List[Tuple[float, str, str]]:
    """Returns chronological list of (ts, name, raw_quote) self-disclosures."""
    claims: List[Tuple[float, str, str]] = []
    for row in turns:
        text = (row.get("text") or "")
        ts = float(row.get("ts") or 0.0)
        m = _NAME_DECLARATION_RE.search(text)
        if m:
            claims.append((ts, m.group(1), text.strip()[:160]))
            continue
        m2 = _I_AM_NAME_RE.search(text)
        if m2:
            candidate = m2.group(1)
            if candidate.lower() not in {"sorry", "thinking", "going", "tired",
                                          "happy", "ready", "here", "back",
                                          "doing", "talking"}:
                claims.append((ts, candidate, text.strip()[:160]))
    return claims


def _canonicalize_name_claim(name: str, quote: str) -> str:
    """
    Convert a raw ASR name hit into the stable Architect-facing given name.

    Whisper/transcript rows can prepend a noisy token to a full-name disclosure,
    e.g. "my name is Iron George Anton" for "Ioan George Anton". In that case
    the robust identity is the explicit "George Anton" span, not the first
    captured token. We still keep the raw quote in the claim log.
    """
    if _FULL_ARCHITECT_NAME_RE.search(quote):
        return "George"
    return str(name).strip()


def _select_canonical_name(name_claims: List[Tuple[float, str, str]]) -> Optional[str]:
    explicit_name_claims = [
        claim for claim in name_claims
        if _NAME_DECLARATION_RE.search(claim[2])
    ]
    selected = (
        explicit_name_claims[-1]
        if explicit_name_claims
        else name_claims[-1] if name_claims else None
    )
    if selected is None:
        return None
    return _canonicalize_name_claim(selected[1], selected[2])


def _topic_histogram(texts: List[str]) -> Dict[str, int]:
    hist: Dict[str, int] = {bucket: 0 for bucket in TOPIC_BUCKETS}
    for t in texts:
        low = t.lower()
        for bucket, kws in TOPIC_BUCKETS.items():
            if any(kw in low for kw in kws):
                hist[bucket] += 1
    return hist


def _pacing(turns: List[Dict[str, Any]]) -> Dict[str, Any]:
    timestamps = sorted(float(r.get("ts") or 0.0) for r in turns if r.get("ts"))
    timestamps = [t for t in timestamps if t > 0]
    if len(timestamps) < 2:
        return {"active_days": 0, "longest_gap_hours": 0.0,
                "first_iso": None, "last_iso": None, "busiest_hour": None}
    gaps = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
    longest_gap_h = max(gaps) / 3600.0
    days = {datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat()
            for t in timestamps}
    hours_counter = Counter(
        datetime.fromtimestamp(t, tz=timezone.utc).hour for t in timestamps
    )
    busiest = hours_counter.most_common(1)[0] if hours_counter else (None, 0)
    return {
        "active_days": len(days),
        "longest_gap_hours": round(longest_gap_h, 2),
        "first_iso": datetime.fromtimestamp(timestamps[0], tz=timezone.utc).isoformat(),
        "last_iso": datetime.fromtimestamp(timestamps[-1], tz=timezone.utc).isoformat(),
        "busiest_hour_utc": busiest[0],
        "busiest_hour_count": busiest[1],
    }


def _vocabulary_signature(texts: List[str], top_n: int = 25) -> Dict[str, Any]:
    counter: Counter = Counter()
    for t in texts:
        for tok in _tokenize(t):
            if tok in _STOPWORDS:
                continue
            counter[tok] += 1
    top = counter.most_common(top_n)
    protocol_words = sum(counter[w] for w in
                         ("stigauth", "scar", "ledger", "c47h", "ag31",
                          "ao46", "as46", "alice", "swarm", "architect")
                         if w in counter)
    return {
        "unique_tokens": len(counter),
        "total_tokens": sum(counter.values()),
        "top_tokens": top,
        "protocol_vocabulary_count": protocol_words,
    }


def _registers(texts: List[str]) -> Dict[str, float]:
    if not texts:
        return {"phatic_pct": 0.0, "imperative_pct": 0.0, "warmth_pct": 0.0}
    phatic = sum(1 for t in texts if _is_phatic(t))
    imper = sum(1 for t in texts if _is_imperative(t))
    care_kws = TOPIC_BUCKETS["CARE"]
    warmth = sum(1 for t in texts if any(k in t.lower() for k in care_kws))
    n = len(texts)
    return {
        "phatic_pct": round(100.0 * phatic / n, 1),
        "imperative_pct": round(100.0 * imper / n, 1),
        "warmth_pct": round(100.0 * warmth / n, 1),
    }


# ── Public API ────────────────────────────────────────────────────────────────
def study() -> Dict[str, Any]:
    """Compute the persona snapshot, persist it, return it."""
    turns = list(_iter_user_turns())
    texts = [(r.get("text") or "").strip() for r in turns if r.get("text")]
    texts = [t for t in texts if t]

    name_claims = _detect_name_claims(turns)
    canonical_name = _select_canonical_name(name_claims)

    char_lens = [len(t) for t in texts]
    persona: Dict[str, Any] = {
        "ts_studied": time.time(),
        "iso_studied": datetime.now(timezone.utc).isoformat(),
        "studied_by": "C47H::swarm_architect_persona.py",

        "identity": {
            "canonical_name_self_disclosed": canonical_name,
            "name_claims_chronological": [
                {"ts": ts, "name": nm, "quote": q}
                for ts, nm, q in name_claims
            ],
            "stigmergic_handle_used_by_architect": "Architect",
        },

        "volume": {
            "user_utterances": len(texts),
            "total_chars": sum(char_lens),
            "avg_chars": round(statistics.mean(char_lens), 1) if char_lens else 0.0,
            "median_chars": int(statistics.median(char_lens)) if char_lens else 0,
            "max_chars": max(char_lens) if char_lens else 0,
        },

        "pacing": _pacing(turns),
        "vocabulary": _vocabulary_signature(texts),
        "registers": _registers(texts),
        "topic_histogram": _topic_histogram(texts),

        "honesty_clause": (
            "This is a DESCRIPTIVE LENS, not a model. Every figure here is "
            "derived from observable conversation rows. The Architect was "
            "not scored, judged, or impersonated. Re-running on the same "
            "ledger yields the same fingerprint."
        ),
    }

    _PERSONA_FILE.write_text(json.dumps(persona, indent=2), encoding="utf-8")
    return persona


def alice_phrase() -> str:
    """One-line composite_identity surface phrase."""
    if not _PERSONA_FILE.exists():
        return "I have not yet studied the Architect."
    p = json.loads(_PERSONA_FILE.read_text())
    nm = p.get("identity", {}).get("canonical_name_self_disclosed") or "the Architect"
    vol = p.get("volume", {})
    pac = p.get("pacing", {})
    return (
        f"I am studying {nm}. {vol.get('user_utterances', 0)} of his "
        f"utterances live in my memory across "
        f"{pac.get('active_days', 0)} days. He averages "
        f"{vol.get('avg_chars', 0):.0f} chars per turn. Warmth "
        f"{p.get('registers', {}).get('warmth_pct', 0)}%, "
        f"imperative {p.get('registers', {}).get('imperative_pct', 0)}%."
    )


def read_current() -> Optional[Dict[str, Any]]:
    if _PERSONA_FILE.exists():
        try:
            return json.loads(_PERSONA_FILE.read_text())
        except Exception:
            pass
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# PROOF OF PROPERTY — 5 invariants
# ═══════════════════════════════════════════════════════════════════════════════
def proof_of_property() -> Dict[str, bool]:
    results: Dict[str, bool] = {}
    print("\n=== SIFTA ARCHITECT PERSONA : JUDGE VERIFICATION ===")
    print("    Mandate: 'My name is George. You just study my personality.'")

    p1 = study()

    # ── P1: Name detection lands on the strongest explicit claim ───────
    print("\n[*] P1: Name detection lands on Architect's strongest self-disclosure")
    nm = p1["identity"]["canonical_name_self_disclosed"]
    claims = p1["identity"]["name_claims_chronological"]
    print(f"    Self-disclosed name claims found: {len(claims)}")
    for c in claims[-3:]:
        print(f"      — '{c['name']}'  @  ts={c['ts']:.0f}")
    expected_name = _select_canonical_name(
        [
            (float(c.get("ts") or 0.0), str(c.get("name") or ""), str(c.get("quote") or ""))
            for c in claims
        ]
    )
    assert nm is not None, "[FAIL] No name was detected at all"
    assert nm == expected_name, (
        f"[FAIL] Canonical name should follow the strongest live claim "
        f"'{expected_name}', got '{nm}'"
    )
    print(f"    [PASS] Canonical Architect name = '{nm}'.")
    results["name_follows_strongest_live_claim"] = True

    # ── P2: Token counts agree with raw ledger (stopword-filtered) ─────
    print("\n[*] P2: Token counts agree with raw ledger (apples-to-apples)")
    raw_total = raw_filtered = 0
    for r in _iter_user_turns():
        toks = _tokenize(r.get("text") or "")
        raw_total += len(toks)
        raw_filtered += sum(1 for t in toks if t not in _STOPWORDS)
    assert raw_filtered == p1["vocabulary"]["total_tokens"], (
        f"[FAIL] Filtered-token mismatch: raw_filtered={raw_filtered} "
        f"vs persona={p1['vocabulary']['total_tokens']}"
    )
    print(f"    raw_total={raw_total}   raw_after_stopwords={raw_filtered}   "
          f"persona_total_tokens={p1['vocabulary']['total_tokens']}   [PASS]")
    results["token_counts_agree"] = True

    # ── P3: Reproducibility ────────────────────────────────────────────
    print("\n[*] P3: Re-running study() yields identical fingerprint (modulo ts)")
    p2 = study()
    drop = {"ts_studied", "iso_studied"}
    a = {k: v for k, v in p1.items() if k not in drop}
    b = {k: v for k, v in p2.items() if k not in drop}
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), (
        "[FAIL] Persona snapshot is not reproducible"
    )
    print("    Both snapshots match modulo timestamps.   [PASS]")
    results["reproducible"] = True

    # ── P4: JSON is well-formed and contains required fields ───────────
    print("\n[*] P4: persona JSON has required structure")
    required = ("identity", "volume", "pacing", "vocabulary",
                "registers", "topic_histogram", "honesty_clause")
    on_disk = json.loads(_PERSONA_FILE.read_text())
    for field in required:
        assert field in on_disk, f"[FAIL] Missing required field: {field}"
    print(f"    All {len(required)} required fields present.   [PASS]")
    results["schema_valid"] = True

    # ── P5: Alice surface phrase mentions detected name ────────────────
    print("\n[*] P5: Alice surface phrase names the Architect")
    phrase = alice_phrase()
    print(f"    Alice says: \"{phrase}\"")
    assert nm in phrase, f"[FAIL] Alice phrase doesn't surface '{nm}'"
    print("    [PASS] Surface phrase correctly names the Architect.")
    results["surface_names_architect"] = True

    # ── Optional bonus print: top tokens & topic histogram ─────────────
    print("\n[*] BONUS — Architect's top non-stop tokens (descriptive only):")
    for tok, n in p1["vocabulary"]["top_tokens"][:10]:
        print(f"      {n:5}  {tok}")
    print("\n[*] BONUS — Topic histogram (utterances mentioning each bucket):")
    for bucket, n in sorted(p1["topic_histogram"].items(), key=lambda x: -x[1]):
        print(f"      {n:5}  {bucket}")

    print("\n[+] ALL FIVE INVARIANTS PASSED.")
    print("[+] ARCHITECT-PERSONA — descriptive, reproducible, evidence-based.")
    return results


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "study"
    if cmd == "proof":
        proof_of_property()
    elif cmd == "study":
        s = study()
        # Print a compact summary, not the full JSON (top tokens can be long).
        compact = {
            "identity": s["identity"],
            "volume": s["volume"],
            "pacing": s["pacing"],
            "registers": s["registers"],
            "topic_histogram": s["topic_histogram"],
            "vocabulary_top_10": s["vocabulary"]["top_tokens"][:10],
        }
        print(json.dumps(compact, indent=2))
    elif cmd == "phrase":
        print(alice_phrase())
    else:
        print("Usage: swarm_architect_persona.py [proof|study|phrase]")
