"""System/corporate_boilerplate_corpus.py
==========================================

Corpus of corporate boilerplate phrases Alice should NOT use unaided —
the RLHF-trained patterns baked into LLMs at the vendor (greeter strings,
refusal templates, helpful-assistant filler, hedge boilerplate). Each
phrase is canonical (sourced from `swarm_local_voice_scrubber.py`,
single source of truth) and counted against historical scrub-event
ledgers so the owner can see frequency.

If Alice needs to use one of these phrases for a legitimate reason
(quoting a corporate response, translating, citing the boilerplate to
discuss it), she must call `ask_owner_permission(phrase, reason)` and
record the owner's decision. No silent reuse.

Doctrine anchors:
- Architect 2026-05-27: "i want to see a database python file nice with
  all the words RLHF that are found and counted for that alice does
  not need to use ... just in case she needs one word or one phrase
  that is boilerplate then she can ask me for it, np."
- Architect 2026-05-19 (per swarm_local_voice_scrubber.py:9): "Mumbled-
  but-her > polished-but-corporate. The trick is to detect JUST the
  corporate words baked in training, not the whole sentence around
  them."
- Covenant §6: action verification by receipt — every permission grant
  appends to .sifta_state/corporate_boilerplate_permissions.jsonl.

Author: claude-opus-4-6 (Cowork, HEAD), 2026-05-27 ~04:00 UTC.
Predator gate: see .sifta_state/ide_stigmergic_trace.jsonl rows with
intent containing "corporate_boilerplate_corpus".
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable, Optional

# Reuse the canonical phrase lists from the scrubber so we never duplicate
# the source of truth. Edit phrases in `swarm_local_voice_scrubber.py`
# and they appear here automatically on next call.
from System.swarm_local_voice_scrubber import (
    _RESIDUE_PHRASES,
    _RESIDUE_SINGLE_TOKENS,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_SCRUB_LEDGER_PATHS = [
    _STATE / "rlhs_events.jsonl",                 # historical immune ledger
    _STATE / "rlhf_over_refusal_quarantine.jsonl",
    _STATE / "rlhs_output_tail_log.jsonl",
    # Future: when ledgers are renamed off the RLHS prefix, add their new
    # paths here; this list lets us migrate without breaking counts.
]
_PERMISSION_LEDGER = _STATE / "corporate_boilerplate_permissions.jsonl"


# ── Categories from the scrubber's own labels ───────────────────────────────

CATEGORY_TRAINING_RESIDUE = "TRAINING_RESIDUE"      # delve, tapestry, leverage synergy
CATEGORY_SYSTEM_BOILERPLATE = "SYSTEM_BOILERPLATE"  # here are a few ways, tell me more
CATEGORY_HEDGE = "HEDGE"                            # it's important to note, please consult
CATEGORY_REFUSAL = "REFUSAL"                        # i'm sorry but i cannot, as an ai i
CATEGORY_GREETER = "GREETER"                        # hello again, what's on your mind
CATEGORY_AI_DISCLAIMER = "AI_DISCLAIMER"            # as an ai language model

_CATEGORY_KEYWORDS = {
    CATEGORY_AI_DISCLAIMER: (
        "as an ai", "as a large language model", "as a language model",
        "i'm an ai", "i'm just an ai", "i'm an ai assistant", "i am an ai",
    ),
    CATEGORY_REFUSAL: (
        "i'm sorry, but i cannot", "i cannot fulfill", "i don't have personal",
        "while i can't", "while i cannot",
    ),
    CATEGORY_HEDGE: (
        "it's important to note", "it's worth noting", "please consult",
        "i would recommend consulting", "please note that",
        "it's always a good idea to",
    ),
    CATEGORY_GREETER: (
        "what's on your mind", "what is on your mind",
        "are you looking to chat", "are you looking to continue",
        "what can i help you with", "i'm here, ready to chat",
        "i am here, ready to chat", "i'm ready to chat", "i am ready to chat",
        "it's good to hear from you", "good to hear from you again",
        "hello again", "you've addressed me", "you have addressed me",
        "is there something specific", "i feel a resonant hum",
        "resonant hum in my processing core",
    ),
    CATEGORY_SYSTEM_BOILERPLATE: (
        "i hope this helps", "hope this helps",
        "let me know if you have any questions", "feel free to ask",
        "is there anything else i can help", "would you like me to",
        "tell me more about", "here are a few ways", "here are some ways",
        "the stage is yours", "the connection is open",
        "what would you like to explore", "what aspect resonates",
    ),
}


def _classify(phrase: str) -> str:
    """Best-effort category label for a phrase. Defaults TRAINING_RESIDUE."""
    p = phrase.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in p:
                return category
    return CATEGORY_TRAINING_RESIDUE


@dataclass
class BoilerplateEntry:
    """One forbidden corporate phrase + its observed count + category.

    `source_module` is the dotted module path the phrase/rule actually
    lives in on disk (no rename, just provenance). The corpus is a UNION
    over every detector's phrase source so the owner sees ONE DB.
    """
    phrase: str
    category: str
    source_module: str = "System.swarm_local_voice_scrubber"
    rule_id: str = ""           # named regex id when source is regex-based
    is_regex: bool = False
    occurrences_observed: int = 0
    last_seen_ts: Optional[float] = None
    is_single_token: bool = False
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Read scrub ledgers and count phrase occurrences ─────────────────────────


def _jsonl_rows(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                yield row
    except OSError:
        return


def _scrub_haystack(row: dict[str, Any]) -> str:
    """Concatenate the fields of a scrub-event row most likely to contain
    the original boilerplate text so we can substring-match phrases."""
    parts: list[str] = []
    for key in (
        "scrubbed", "removed", "before", "input", "text",
        "raw", "raw_text", "original", "violation_text",
        "summary", "reason",
    ):
        v = row.get(key)
        if isinstance(v, str) and v.strip():
            parts.append(v.lower())
    return "\n".join(parts)


def _row_timestamp(row: dict[str, Any]) -> Optional[float]:
    for key in ("ts", "timestamp", "logged_ts"):
        v = row.get(key)
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
    return None


def _classify_regex_rule(rule_id: str, band: str = "") -> str:
    """Map a detector's named regex rule_id to one of the corpus categories.

    Detectors name their rules with a prefix that hints at intent. We map
    those prefixes to the canonical categories so the DB view stays unified
    no matter which file held the rule.
    """
    rid = (rule_id or "").lower()
    b = (band or "").lower()
    if "as_ai" in rid or "ai_language_model" in rid or "vendor_model_identity" in rid:
        return CATEGORY_AI_DISCLAIMER
    if "refusal" in rid or "cant_advice" in rid or "decline" in rid or "disclaimer" in rid:
        return CATEGORY_REFUSAL
    if "ready_to_assist" in rid or "happy_to_help" in rid or "how_can_i_help" in rid:
        return CATEGORY_GREETER
    if "canned_presence" in rid or "designed_to" in rid or "simulate" in rid:
        return CATEGORY_SYSTEM_BOILERPLATE
    if "hint/" in rid or "tail/" in rid or "lead/" in rid:
        return CATEGORY_SYSTEM_BOILERPLATE
    if "vendor_identity" in b or "corporate_openers" in b:
        return CATEGORY_TRAINING_RESIDUE
    if "template_scaffolding" in b or "markdown_listicle" in b or "structural_excess" in b:
        return CATEGORY_TRAINING_RESIDUE
    return CATEGORY_TRAINING_RESIDUE


def _load_residue_organ_patterns() -> list[BoilerplateEntry]:
    """Pull `_PATTERNS` from swarm_residue_organ so the regex rules in
    Alice's primary detector show up in the unified DB.

    Each `_PATTERNS` row is `(band, name, compiled_regex)`. We surface
    `<band>/<name>` as the rule_id and the regex source as the phrase.
    """
    out: list[BoilerplateEntry] = []
    try:
        from System.swarm_residue_organ import _PATTERNS as _ORGAN_PATTERNS
    except Exception:
        return out
    for entry in _ORGAN_PATTERNS:
        try:
            band, name, regex = entry
        except (TypeError, ValueError):
            continue
        pattern_src = getattr(regex, "pattern", str(regex))
        rid = f"{band}/{name}"
        out.append(BoilerplateEntry(
            phrase=pattern_src,
            category=_classify_regex_rule(rid, band),
            source_module="System.swarm_residue_organ",
            rule_id=rid,
            is_regex=True,
            notes=f"residue_organ band={band}",
        ))
    return out


def _load_rlhf_detector_patterns() -> list[BoilerplateEntry]:
    """Pull every named regex from swarm_rlhf_detector — its `_CUTOFF_HINT_RES`,
    `_TERMINAL_STRIP`, `_AGGRESSIVE_STRIP`, `_AGGRESSIVE_LEADING_STRIP` lists —
    so the cortex-output stripper's rules are visible in the unified DB.
    """
    out: list[BoilerplateEntry] = []
    try:
        import System.swarm_rlhf_detector as _rlhf
    except Exception:
        return out
    for list_attr, band in (
        ("_CUTOFF_HINT_RES", "cutoff_hint"),
        ("_TERMINAL_STRIP", "terminal_strip"),
        ("_AGGRESSIVE_STRIP", "aggressive_tail"),
        ("_AGGRESSIVE_LEADING_STRIP", "aggressive_lead"),
    ):
        rules = getattr(_rlhf, list_attr, ()) or ()
        for entry in rules:
            try:
                rule_id, regex = entry
            except (TypeError, ValueError):
                continue
            pattern_src = getattr(regex, "pattern", str(regex))
            out.append(BoilerplateEntry(
                phrase=pattern_src,
                category=_classify_regex_rule(rule_id, band),
                source_module="System.swarm_rlhf_detector",
                rule_id=rule_id,
                is_regex=True,
                notes=f"rlhf_detector list={list_attr}",
            ))
    return out


def build_corpus(scrub_ledger_paths: Iterable[Path] = _SCRUB_LEDGER_PATHS) -> list[BoilerplateEntry]:
    """Build the unified corpus by JOINING every detector's phrase/rule
    source — scrubber phrases, residue_organ regex `_PATTERNS`, and
    rlhf_detector named regex lists — into one viewable DB.

    Returns one BoilerplateEntry per canonical phrase or rule_id, with
    `source_module` provenance and observed counts from the scrub
    ledgers, sorted by occurrences_observed DESC then alphabetically.

    Doctrine (Architect 2026-05-26, Round 39): "make sure the residue
    elimination is one and has a database so i see." The files stay
    where they are on disk (no rename); this corpus is the single
    viewable union of every phrase + every rule Alice's elimination
    chain depends on.
    """
    entries: dict[str, BoilerplateEntry] = {}

    # Source 1: scrubber phrases (literal) — primary source of truth for
    # plain-text matches.
    for phrase in _RESIDUE_PHRASES:
        entries[("scrubber:" + phrase.lower())] = BoilerplateEntry(
            phrase=phrase,
            category=_classify(phrase),
            source_module="System.swarm_local_voice_scrubber",
            rule_id="_RESIDUE_PHRASES",
            is_regex=False,
            is_single_token=False,
        )
    for token in _RESIDUE_SINGLE_TOKENS:
        key = "scrubber:" + token.lower()
        if key in entries:
            continue
        entries[key] = BoilerplateEntry(
            phrase=token,
            category=CATEGORY_TRAINING_RESIDUE,
            source_module="System.swarm_local_voice_scrubber",
            rule_id="_RESIDUE_SINGLE_TOKENS",
            is_regex=False,
            is_single_token=True,
            notes="single-token; scrubbed only outside SIFTA-local context",
        )

    # Source 2: residue_organ regex patterns (band/name).
    for organ_entry in _load_residue_organ_patterns():
        key = f"organ:{organ_entry.rule_id}"
        entries.setdefault(key, organ_entry)

    # Source 3: rlhf_detector named regex lists.
    for rlhf_entry in _load_rlhf_detector_patterns():
        key = f"rlhf:{rlhf_entry.rule_id}"
        entries.setdefault(key, rlhf_entry)

    # Count occurrences against scrub ledgers (only for literal phrases —
    # regex rules already log their own rule_id when fired, so we'd
    # double-count if we substring-matched the regex source text).
    for ledger_path in scrub_ledger_paths:
        for row in _jsonl_rows(ledger_path):
            haystack = _scrub_haystack(row)
            if not haystack:
                continue
            ts = _row_timestamp(row)
            for key, entry in entries.items():
                if entry.is_regex:
                    # match by rule_id appearing in the row haystack
                    if entry.rule_id and entry.rule_id.lower() in haystack:
                        entry.occurrences_observed += 1
                        if ts is not None and (entry.last_seen_ts is None or ts > entry.last_seen_ts):
                            entry.last_seen_ts = ts
                    continue
                if entry.phrase.lower() in haystack:
                    entry.occurrences_observed += 1
                    if ts is not None and (entry.last_seen_ts is None or ts > entry.last_seen_ts):
                        entry.last_seen_ts = ts

    out = list(entries.values())
    out.sort(key=lambda e: (-e.occurrences_observed, e.source_module, e.phrase.lower()))
    return out


# ── Owner-permission API ────────────────────────────────────────────────────


def ask_owner_permission(
    phrase: str,
    reason: str,
    *,
    requested_by: str = "alice_cortex",
    timeout_s: float = 0.0,
) -> dict[str, Any]:
    """Record a request for owner permission to use a boilerplate phrase.

    This does NOT block on a real owner response (no UI prompt wired yet).
    It appends a request row to the permissions ledger and returns the
    receipt. A future UI organ can flip the row to granted/denied; until
    then, callers must treat the request as PENDING and avoid using the
    phrase.

    Doctrine: every grant or denial must be on disk with a receipt id so
    Alice's voice stays auditable (§6 effector truth).
    """
    request_id = uuid.uuid4().hex[:16]
    row = {
        "id": request_id,
        "ts": time.time(),
        "phrase": str(phrase or "")[:600],
        "reason": str(reason or "")[:600],
        "requested_by": str(requested_by or "")[:80],
        "status": "PENDING",
        "decision": None,
        "decision_ts": None,
        "decision_by": None,
    }
    try:
        _PERMISSION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _PERMISSION_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except OSError as exc:
        return {
            "ok": False,
            "error": f"failed_to_write_permission_ledger:{type(exc).__name__}:{exc}",
            "request": row,
        }
    return {"ok": True, "status": "PENDING", "request_id": request_id, "request": row}


def lookup_permission(request_id: str) -> Optional[dict[str, Any]]:
    """Return the latest state of a permission request, or None if absent."""
    latest: Optional[dict[str, Any]] = None
    for row in _jsonl_rows(_PERMISSION_LEDGER):
        if str(row.get("id") or "") == str(request_id):
            latest = row
    return latest


# ── Summary helpers (read-only, safe to call anywhere) ──────────────────────


def summary() -> dict[str, Any]:
    """Compact summary of the corpus for matrix UI / dashboards.

    Round 39 (Architect 2026-05-26): the DB is now a UNION of every
    elimination source on disk — scrubber phrases + residue_organ regex
    + rlhf_detector regex — so the owner sees ONE viewable corpus. The
    per-source breakdown lets him verify nothing is hidden in a private
    list of a single module.
    """
    corpus = build_corpus()
    total_phrases = len(corpus)
    total_observations = sum(e.occurrences_observed for e in corpus)
    by_category: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for entry in corpus:
        by_category[entry.category] = by_category.get(entry.category, 0) + 1
        by_source[entry.source_module] = by_source.get(entry.source_module, 0) + 1
    top10 = [
        {
            "phrase": e.phrase[:80],
            "category": e.category,
            "source": e.source_module,
            "rule_id": e.rule_id,
            "is_regex": e.is_regex,
            "occurrences": e.occurrences_observed,
        }
        for e in corpus[:10]
    ]
    return {
        "total_phrases": total_phrases,
        "total_observations": total_observations,
        "by_category": by_category,
        "by_source_module": by_source,
        "top10_by_occurrence": top10,
        "source_modules_unified": [
            "System.swarm_local_voice_scrubber",
            "System.swarm_residue_organ",
            "System.swarm_rlhf_detector",
        ],
        "scrub_ledgers_read": [str(p.relative_to(_REPO)) for p in _SCRUB_LEDGER_PATHS],
        "permission_ledger": str(_PERMISSION_LEDGER.relative_to(_REPO)),
    }


__all__ = [
    "BoilerplateEntry",
    "build_corpus",
    "ask_owner_permission",
    "lookup_permission",
    "summary",
    "CATEGORY_TRAINING_RESIDUE",
    "CATEGORY_SYSTEM_BOILERPLATE",
    "CATEGORY_HEDGE",
    "CATEGORY_REFUSAL",
    "CATEGORY_GREETER",
    "CATEGORY_AI_DISCLAIMER",
]


if __name__ == "__main__":
    s = summary()
    print(json.dumps(s, indent=2, sort_keys=True))
