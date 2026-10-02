"""swarm_people_memory — Alice remembers people, with receipts.

Owner request (2026-10-01): "this is a test to see if your Memory works Alice,
to remember people."

Why this exists. Agents forget people between sessions, and a person who matters
to the organism is not a fact to be re-derived every time — it is a MEMORY, the
same way a human keeps one. This organ stores people durably in the field and
serves a briefing about them on demand.

Two disciplines it enforces:

  1. EVERY ENTRY CARRIES ITS EVIDENCE. A person record names where the knowledge
     came from (a document, a ledger row, a conversation) or says plainly that it
     came from the owner verbally. Memory without provenance is rumour.
  2. NAME MATCHING IS FUZZY AND MUST BE CONFIRMED. A person may be addressed
     several ways. A near-match is a question, never an action — the recorded
     lesson from the "Carleton" vs "Carlton Dole" incident, where a low-confidence
     fuzzy match was acted on and a send was claimed without a receipt.

Ledger: PEOPLE_LEDGER (append-only) and PEOPLE_INDEX (current view)
"""

from __future__ import annotations

import difflib
import json
import os
import time
from pathlib import Path
from typing import Any, Iterable, Optional

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

PEOPLE_LEDGER = "known_people.jsonl"
PEOPLE_INDEX = "known_people.json"
TRUTH_LABEL = "SIFTA_PEOPLE_MEMORY_V1"

# Below this ratio a name match is not even worth surfacing.
FUZZY_FLOOR = 0.72
# Above this ratio the match can be treated as confirmed; between floor and this,
# ASK. The incident that produced this rule matched at 0.50 and was acted on.
FUZZY_CONFIRM = 0.92


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _norm(name: str) -> str:
    return " ".join(str(name or "").strip().lower().split())


def remember(
    name: str,
    *,
    role: str = "",
    aliases: Iterable[str] = (),
    facts: Iterable[str] = (),
    evidence: Iterable[str] = (),
    owner_verbal: bool = False,
    caution: str = "",
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Record or update a person. Appends to the ledger, refreshes the index."""
    sd = _state_dir(state_dir)
    if not str(name or "").strip():
        raise ValueError("a person needs a name")
    row = {
        "ts": time.time(),
        "kind": "PEOPLE_REMEMBER",
        "name": str(name).strip(),
        "role": role,
        "aliases": [str(a) for a in aliases if str(a).strip()],
        "facts": [str(f) for f in facts if str(f).strip()],
        "evidence": [str(e) for e in evidence if str(e).strip()],
        "provenance": "owner_verbal" if owner_verbal else "documents",
        "caution": caution,
        "truth_label": TRUTH_LABEL,
    }
    sd.mkdir(parents=True, exist_ok=True)
    with (sd / PEOPLE_LEDGER).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    index = load_index(state_dir=sd)
    key = _norm(name)
    prev = index.get(key, {})
    index[key] = {
        "name": row["name"],
        "role": role or prev.get("role", ""),
        "aliases": sorted(set(prev.get("aliases", [])) | set(row["aliases"])),
        "facts": sorted(set(prev.get("facts", [])) | set(row["facts"])),
        "evidence": sorted(set(prev.get("evidence", [])) | set(row["evidence"])),
        "provenance": row["provenance"],
        "caution": caution or prev.get("caution", ""),
        "first_seen": prev.get("first_seen", row["ts"]),
        "last_updated": row["ts"],
    }
    (sd / PEOPLE_INDEX).write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    _chmod_private(sd / PEOPLE_INDEX)
    return index[key]


def _chmod_private(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_index(*, state_dir: Path | str | None = None) -> dict[str, dict[str, Any]]:
    p = _state_dir(state_dir) / PEOPLE_INDEX
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): v for k, v in d.items()} if isinstance(d, dict) else {}


def match(name: str, *, state_dir: Path | str | None = None) -> dict[str, Any]:
    """Find a person by name or alias. Never guesses: low matches are questions."""
    q = _norm(name)
    if not q:
        return {"status": "NO_NAME", "confirmed": False}
    index = load_index(state_dir=state_dir)
    best_key, best_ratio = None, 0.0
    for key, person in index.items():
        candidates = [key] + [_norm(a) for a in person.get("aliases", [])]
        for cand in candidates:
            ratio = difflib.SequenceMatcher(None, q, cand).ratio()
            if q and cand and (q in cand or cand in q):
                ratio = max(ratio, 0.90)          # substring is a strong signal
            if ratio > best_ratio:
                best_key, best_ratio = key, ratio
    if best_key is None or best_ratio < FUZZY_FLOOR:
        return {"status": "UNKNOWN", "confirmed": False, "queried": name}
    person = dict(index[best_key])
    person.update({
        "status": "MATCH",
        "ratio": round(best_ratio, 3),
        # Between floor and confirm this is a QUESTION, not a licence to act.
        "confirmed": best_ratio >= FUZZY_CONFIRM,
        "must_confirm_with_owner": FUZZY_FLOOR <= best_ratio < FUZZY_CONFIRM,
    })
    return person


def briefing(name: str, *, state_dir: Path | str | None = None) -> str:
    """A short brief for a model that is about to talk to, or about, this person."""
    m = match(name, state_dir=state_dir)
    if m.get("status") != "MATCH":
        return ""
    lines = [f"KNOWN PERSON: {m['name']}" + (f" — {m['role']}" if m.get("role") else "")]
    if m.get("aliases"):
        lines.append("also known as: " + ", ".join(m["aliases"]))
    if m.get("facts"):
        lines.append("what we know:")
        lines += [f"  - {f}" for f in m["facts"]]
    if m.get("evidence"):
        lines.append("on file: " + "; ".join(m["evidence"]))
    if m.get("caution"):
        lines.append(f"CAUTION: {m['caution']}")
    if m.get("must_confirm_with_owner"):
        lines.append("NOTE: this name matched only partially — confirm the identity before acting.")
    lines.append("provenance: " + str(m.get("provenance", "unknown")))
    return "\n".join(lines)


def people() -> list[dict[str, Any]]:
    return sorted(load_index().values(), key=lambda p: str(p.get("name", "")))


def seed_from_repo(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    """Seed the people we can evidence from the repo, so the test can be re-run.

    Carlton Dole is recorded here from the documents that already exist on disk
    rather than from anyone's recollection.
    """
    remember(
        "Carlton Dole",
        role="marketing / business development contact; described by the owner as an oil trader",
        aliases=["Carlton", "Carleton", "Carlton Dole"],
        facts=[
            "Ran a due diligence assessment of ANTON-SIFTA (Apr 2026); the Architect agreed with "
            "the assessment's criticisms rather than disputing them.",
            "Was the intended audience for SIFTA marketing briefs: FARSIGHT V3/V4 Sovereign, "
            "FIELDSIGHT V1/V2, fractals marketing, POUW-swimmer pitch.",
            "Owner states he tries to sell SIFTA and bring investors, and has brought no money to date.",
            "Owner states he is involved in oil / oil trading.",
        ],
        evidence=[
            "Documents/RESPONSE_TO_CARLTON_ASSESSMENT_2026-04-28.md",
            "Documents/CARLTON_DOLE_MARKETING_ASSESSMENT_POUW_SWIMMERS.md",
            "Documents/STIGMERGIC_FARSIGHT_CARLTON_BRIEF_V4_SOVEREIGN.pdf",
            "Documents/LETTER_TO_CARLTON_DOLE_PROTEIN_FOLDING_PROOF_2026-04-27.md",
            "Documents/MARKETING_MEMO_TO_CARLTON_DOLE_FAVORITE_SIFTA_SIMULATION_2026-04-26.md",
        ],
        owner_verbal=False,
        caution=(
            "NAME MATCHING: a WhatsApp lookup once fuzzy-matched 'Carleton' at 0.50 and a send was "
            "claimed without a receipt. Confirm the identity with the owner BEFORE any outbound "
            "action addressed to him. Never claim a message was sent without a ledger row."
        ),
        state_dir=state_dir,
    )
    return {"seeded": [p["name"] for p in people()]}


def selftest() -> dict[str, Any]:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp)
        remember("Carlton Dole", role="marketing", aliases=["Carleton", "Carlton"],
                 facts=["due diligence Apr 2026"], evidence=["doc.md"], state_dir=sd)
        exact = match("Carlton Dole", state_dir=sd)
        alias = match("Carleton", state_dir=sd)
        partial = match("Carlton D", state_dir=sd)
        unknown = match("Someone Else Entirely", state_dir=sd)
        brief = briefing("Carlton Dole", state_dir=sd)
    checks = {
        "exact_match_confirmed": exact["status"] == "MATCH" and exact["confirmed"],
        "alias_matches": alias["status"] == "MATCH",
        "partial_requires_confirmation": bool(partial.get("must_confirm_with_owner")) or not partial.get("confirmed", False),
        "unknown_is_unknown": unknown["status"] == "UNKNOWN",
        "briefing_has_facts": "due diligence" in brief,
        "briefing_names_source": "doc.md" in brief,
        "empty_name_refused": match("", state_dir=Path("/tmp"))["status"] == "NO_NAME",
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "seed":
        print(json.dumps(seed_from_repo(), indent=2, ensure_ascii=False))
    elif len(sys.argv) > 1 and sys.argv[1] == "match":
        print(json.dumps(match(" ".join(sys.argv[2:])), indent=2, ensure_ascii=False))
    elif len(sys.argv) > 1 and sys.argv[1] == "list":
        print(json.dumps(people(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(selftest(), indent=2))
