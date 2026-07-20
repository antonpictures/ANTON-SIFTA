#!/usr/bin/env python3
"""Stigmergic shared-experience anchors — real humans/celebs from owner+Alice history.

George (r1370): every name/celebrity/real person mentioned in shared experiences with
Alice becomes a stigmergic anchor row — unless explicitly rejected as fiction
(e.g. bare "Joy" from "this is Joy speaking" is NOT a real anchor; "Joy Behar" is).

Truth label: SHARED_EXPERIENCE_ANCHOR_V1
Ledger: .sifta_state/stigmergic_shared_experience_anchors.jsonl
"""
from __future__ import annotations

import json
import re
import time
import uuid
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover

    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(line)

TRUTH_LABEL = "SHARED_EXPERIENCE_ANCHOR_V1"
SCHEMA = "SHARED_EXPERIENCE_ANCHOR_ROW_V1"
LEDGER_NAME = "stigmergic_shared_experience_anchors.jsonl"
CONVERSATION_NAME = "alice_conversation.jsonl"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

_OWNER_ROLES = frozenset({"user", "owner", "george", "architect"})
_ALICE_ROLES = frozenset({"alice", "assistant"})

# Fiction personas George explicitly rejected (r1370).
_FICTION_REJECT_SEED: dict[str, dict[str, str]] = {
    "joy": {
        "canonical_name": "Joy",
        "reason": (
            "NOT_REAL_ANCHOR — cooking-thread persona ('this is Joy speaking'); "
            "George r1370: Joy is not a real person, not a real anchor"
        ),
        "collision_note": "Distinct from public figure Joy Behar when owner names her fully",
        "round_id": "r1370-cursor-stigmergic-anchors-app",
    },
}

# Known public figures — full-name match promotes to confirmed without owner Q&A.
_PUBLIC_FIGURE_SEED: dict[str, dict[str, Any]] = {
    "joy behar": {
        "canonical_name": "Joy Behar",
        "anchor_kind": "public_figure",
        "life_status": "alive",
        "note": "TV host; shared experience when George tells Alice about Joy Behar",
    },
    "jd vance": {
        "canonical_name": "JD Vance",
        "anchor_kind": "public_figure",
        "life_status": "alive",
        "note": "Public political figure; The View/Joy Behar news-clip anchor",
    },
    "phillipe": {
        "canonical_name": "Phillipe",
        "anchor_kind": "contact",
        "life_status": "unknown",
        "note": "George PM contact — commercial viability thread 2026-06-19",
    },
    "philippe": {
        "canonical_name": "Philippe",
        "anchor_kind": "contact",
        "life_status": "unknown",
        "note": "Alternate spelling of Phillipe contact",
    },
    "joe rogan": {
        "canonical_name": "Joe Rogan",
        "anchor_kind": "podcast_host",
        "life_status": "alive",
        "note": (
            "Shared co-watch anchor when George and Alice listen to JRE together — "
            "TIME/SPACE pin on timeline_label + concept_label for that room moment"
        ),
    },
}

_JOE_ROGAN_TITLE_RE = re.compile(r"\bJoe\s+Rogan(?:\s+Experience)?\b", re.IGNORECASE)
# George r1426: disambiguation is TIME/SPACE — which epoch and room frame, not broadcast category.
_DISAMBIGUATION_DOCTRINE = (
    "Disambiguation is TIME/SPACE: which epoch and room frame this human pins in George+Alice "
    "history. Read timeline_label + concept_label first; same name on another date is another moment."
)
_COWATCH_DISAMBIGUATION = (
    "TIME/SPACE pin: names the when+where frame for this human in George+Alice history — "
    "read timeline_label and concept_label; same person on another date is another moment"
)

_COWATCH_EVIDENCE_KINDS = frozenset(
    {"architect_cowatch_segment", "youtube_cowatch_memory"}
)

_NON_PERSON_NAME_KEYS = {
    "alice browser",
    "screenshot cortex turn",
    "self screenshot cortex turn",
    "reload talk",
    "sifta python gui os",
    "sifta os",
    "macbook pro camera",
    "duck ai",
    "duckduckgo ai",
    "google ai",
    "perplexity ai",
    "the view",
    "united states",
    "los angeles",
}
_NON_PERSON_NAME_TOKENS = {
    "app",
    "browser",
    "camera",
    "command",
    "cortex",
    "duckduckgo",
    "google",
    "perplexity",
    "python",
    "receipt",
    "reload",
    "screenshot",
    "sifta",
    "talk",
    "turn",
    "view",
}

_MULTI_NAME_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+(?:[A-Z][a-z]+|(?:van|de|del|la|le|von|Mc)[A-Z][a-z]+))+)\b"
)
_FICTION_SPEAKING_RE = re.compile(
    r"\bthis\s+is\s+([A-Za-z]+)\s+speaking\b",
    re.IGNORECASE,
)
_JOY_BEHAR_RE = re.compile(r"\bjoy\s+behar\b", re.IGNORECASE)
_JD_VANCE_RE = re.compile(r"\b(?:j\.?\s*d\.?|jd)\s+vance\b", re.IGNORECASE)
_BARE_JOY_RE = re.compile(r"\bjoy\b", re.IGNORECASE)
_BARE_VINCE_RE = re.compile(r"\bvince\b", re.IGNORECASE)


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _ledger_path(state_dir: Optional[Path | str] = None) -> Path:
    return _state_dir(state_dir) / LEDGER_NAME


def _normalize_key(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _looks_non_person_anchor(name: str) -> bool:
    key = _normalize_key(name)
    if not key:
        return True
    if key in _NON_PERSON_NAME_KEYS:
        return True
    tokens = set(re.findall(r"[a-z0-9]+", key))
    if tokens & _NON_PERSON_NAME_TOKENS:
        return True
    if key.startswith("alice "):
        return True
    return False


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _append_row(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    path = _ledger_path(state_dir)
    append_line_locked(path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def _payload_text(row: dict[str, Any]) -> str:
    payload = row.get("payload")
    if isinstance(payload, dict):
        return str(payload.get("text") or "")
    return str(row.get("text") or "")


def _payload_role(row: dict[str, Any]) -> str:
    payload = row.get("payload")
    if isinstance(payload, dict):
        return str(payload.get("role") or "").lower()
    return str(row.get("role") or "").lower()


def _payload_ts(row: dict[str, Any]) -> float:
    payload = row.get("payload")
    if isinstance(payload, dict):
        try:
            return float(payload.get("ts") or 0.0)
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(row.get("ts") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _row_event_key(row: dict[str, Any]) -> str:
    payload = row.get("payload")
    payload_d = payload if isinstance(payload, dict) else {}
    explicit = (
        row.get("event_id")
        or row.get("receipt_id")
        or row.get("id")
        or payload_d.get("event_id")
        or payload_d.get("receipt_id")
    )
    if explicit:
        return str(explicit)
    raw = json.dumps(
        {
            "role": _payload_role(row),
            "text": _payload_text(row),
            "ts": _payload_ts(row),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:20]


def _mention_key(row: dict[str, Any], canonical_name: str) -> str:
    return f"{_row_event_key(row)}:{_anchor_id_for(canonical_name)}"


@dataclass(frozen=True)
class AnchorSnapshot:
    anchor_id: str
    canonical_name: str
    status: str
    anchor_kind: str
    mention_count: int
    first_seen_ts: float
    last_seen_ts: float
    experience_snippet: str
    rejection_reason: str = ""
    evidence_kind: str = ""
    evidence_ref: str = ""
    evidence_status: str = ""
    evidence_source: str = ""
    disambiguation: str = ""
    concept_label: str = ""
    timeline_label: str = ""
    timeline_note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "anchor_id": self.anchor_id,
            "canonical_name": self.canonical_name,
            "status": self.status,
            "anchor_kind": self.anchor_kind,
            "mention_count": self.mention_count,
            "first_seen_ts": self.first_seen_ts,
            "last_seen_ts": self.last_seen_ts,
            "experience_snippet": self.experience_snippet,
            "rejection_reason": self.rejection_reason,
            "evidence_kind": self.evidence_kind,
            "evidence_ref": self.evidence_ref,
            "evidence_status": self.evidence_status,
            "evidence_source": self.evidence_source,
            "disambiguation": self.disambiguation,
            "concept_label": self.concept_label,
            "timeline_label": self.timeline_label,
            "timeline_note": self.timeline_note,
        }


def seed_fiction_rejections(*, state_dir: Optional[Path | str] = None) -> list[dict[str, Any]]:
    """Write George's explicit fiction-anchor rejections if not already present."""
    existing = {_normalize_key(r.get("canonical_name", "")) for r in _read_jsonl(_ledger_path(state_dir))}
    written: list[dict[str, Any]] = []
    now = time.time()
    for key, meta in _FICTION_REJECT_SEED.items():
        if key in existing:
            continue
        row = {
            "schema": SCHEMA,
            "truth_label": TRUTH_LABEL,
            "anchor_id": f"reject_{key}",
            "canonical_name": meta["canonical_name"],
            "normalized_name": key,
            "status": "REJECTED_FICTION",
            "anchor_kind": "fiction_persona",
            "mention_count": 0,
            "first_seen_ts": now,
            "last_seen_ts": now,
            "experience_snippet": "",
            "rejection_reason": meta["reason"],
            "collision_note": meta.get("collision_note", ""),
            "round_id": meta.get("round_id", ""),
            "source": "owner_explicit_reject",
        }
        _append_row(row, state_dir=state_dir)
        written.append(row)
    return written


def is_rejected_anchor(name: str, *, state_dir: Optional[Path | str] = None) -> Optional[str]:
    """Return rejection reason if this name is a blocked fiction anchor."""
    key = _normalize_key(name)
    if key in _FICTION_REJECT_SEED:
        return _FICTION_REJECT_SEED[key]["reason"]
    for row in reversed(_read_jsonl(_ledger_path(state_dir))):
        if row.get("schema") != SCHEMA:
            continue
        if _normalize_key(str(row.get("canonical_name") or "")) == key:
            if str(row.get("status") or "") == "REJECTED_FICTION":
                return str(row.get("rejection_reason") or "REJECTED_FICTION")
            break
    return None


def _anchor_id_for(name: str) -> str:
    key = _normalize_key(name)
    slug = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return slug or "unknown_anchor"


def register_shared_experience_anchor(
    canonical_name: str,
    *,
    status: str = "CANDIDATE",
    anchor_kind: str = "shared_experience",
    experience_snippet: str = "",
    source: str = "conversation_scan",
    mention_delta: int = 1,
    mention_key: str = "",
    evidence_kind: str = "",
    evidence_ref: str = "",
    evidence_status: str = "",
    evidence_source: str = "",
    disambiguation: str = "",
    concept_label: str = "",
    timeline_label: str = "",
    timeline_note: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Upsert one anchor row from a shared experience mention."""
    name = (canonical_name or "").strip()
    if not name:
        return {}
    key = _normalize_key(name)
    if is_rejected_anchor(name, state_dir=state_dir):
        return {
            "schema": SCHEMA,
            "truth_label": TRUTH_LABEL,
            "canonical_name": name,
            "status": "REJECTED_FICTION",
            "skipped": True,
            "rejection_reason": is_rejected_anchor(name, state_dir=state_dir),
        }
    now = time.time()
    anchor_id = _anchor_id_for(name)
    existing: Optional[dict[str, Any]] = None
    for row in reversed(_read_jsonl(_ledger_path(state_dir))):
        if row.get("schema") != SCHEMA:
            continue
        if str(row.get("anchor_id") or "") == anchor_id:
            existing = row
            break
    if existing and str(existing.get("status") or "") == "REJECTED_FICTION":
        return existing
    snippet = (experience_snippet or "").strip()[:280]
    if existing:
        row = dict(existing)
        row["mention_count"] = int(existing.get("mention_count") or 0) + max(0, mention_delta)
        row["last_seen_ts"] = now
        if snippet and not row.get("experience_snippet"):
            row["experience_snippet"] = snippet
        if status == "CONFIRMED" or row.get("status") == "CONFIRMED":
            row["status"] = "CONFIRMED"
        if mention_key:
            row["mention_key"] = mention_key
        if evidence_kind:
            row["evidence_kind"] = evidence_kind
        if evidence_ref:
            row["evidence_ref"] = evidence_ref
        if evidence_status:
            row["evidence_status"] = evidence_status
        if evidence_source:
            row["evidence_source"] = evidence_source
        if disambiguation:
            row["disambiguation"] = disambiguation
        if concept_label:
            row["concept_label"] = concept_label
        if timeline_label:
            row["timeline_label"] = timeline_label
        if timeline_note:
            row["timeline_note"] = timeline_note
    else:
        row = {
            "schema": SCHEMA,
            "truth_label": TRUTH_LABEL,
            "anchor_id": anchor_id,
            "canonical_name": name,
            "normalized_name": key,
            "status": status,
            "anchor_kind": anchor_kind,
            "mention_count": max(1, mention_delta),
            "first_seen_ts": now,
            "last_seen_ts": now,
            "experience_snippet": snippet,
            "source": source,
        }
        if key in _PUBLIC_FIGURE_SEED:
            row["life_status"] = str(_PUBLIC_FIGURE_SEED[key].get("life_status") or "unknown")
            row["seed_note"] = str(_PUBLIC_FIGURE_SEED[key].get("note") or "")
        if mention_key:
            row["mention_key"] = mention_key
        if evidence_kind:
            row["evidence_kind"] = evidence_kind
        if evidence_ref:
            row["evidence_ref"] = evidence_ref
        if evidence_status:
            row["evidence_status"] = evidence_status
        if evidence_source:
            row["evidence_source"] = evidence_source
        if disambiguation:
            row["disambiguation"] = disambiguation
        if concept_label:
            row["concept_label"] = concept_label
        if timeline_label:
            row["timeline_label"] = timeline_label
        if timeline_note:
            row["timeline_note"] = timeline_note
    _append_row(row, state_dir=state_dir)
    return row


_EDIT_ANCHOR_RE = re.compile(
    r"\b(?:edit|rename|update)\s+anchor\s+"
    r"(?P<from>[A-Za-z][A-Za-z .'-]{0,40}?)\s+to\s+(?P<to>[A-Za-z][A-Za-z .'-]{0,60})\b",
    re.IGNORECASE,
)
_SET_ANCHOR_CONCEPT_RE = re.compile(
    r"\bset\s+anchor\s+(?P<name>[A-Za-z][A-Za-z .'-]{0,40}?)\s+concept\s+to\s+"
    r"(?P<concept>.{3,120}?)(?:\s*$|\.)",
    re.IGNORECASE,
)
_SET_ANCHOR_DISAMBIG_RE = re.compile(
    r"\bset\s+anchor\s+(?P<name>[A-Za-z][A-Za-z .'-]{0,40}?)\s+disambiguation\s+to\s+"
    r"(?P<disamb>.{3,160}?)(?:\s*$|\.)",
    re.IGNORECASE,
)
_SET_ANCHOR_TIMELINE_RE = re.compile(
    r"\bset\s+anchor\s+(?P<name>[A-Za-z][A-Za-z .'-]{0,40}?)\s+timeline\s+to\s+"
    r"(?P<timeline>.{3,180}?)(?:\s*$|\.)",
    re.IGNORECASE,
)

ANCHORS_APP_NAME = "Stigmergic Shared Experience Anchors"


def edit_shared_experience_anchor(
    name_or_id: str,
    *,
    new_canonical_name: str = "",
    anchor_kind: str = "",
    disambiguation: str = "",
    concept_label: str = "",
    timeline_label: str = "",
    timeline_note: str = "",
    editor: str = "owner",
    evidence_source: str = ANCHORS_APP_NAME,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Edit anchor display name, kind, disambiguation, concept, or timeline pin."""
    existing = _latest_anchor_row(name_or_id, state_dir=state_dir)
    if not existing:
        return {}
    now = time.time()
    old_name = str(existing.get("canonical_name") or name_or_id).strip()
    new_name = (new_canonical_name or old_name).strip()
    if not new_name:
        return {}
    row = dict(existing)
    if new_name != old_name:
        row["previous_canonical_name"] = old_name
        row["canonical_name"] = new_name
        row["normalized_name"] = _normalize_key(new_name)
    if anchor_kind:
        row["anchor_kind"] = anchor_kind.strip()[:80]
    if disambiguation:
        row["disambiguation"] = disambiguation.strip()[:200]
    if concept_label:
        row["concept_label"] = concept_label.strip()[:200]
    if timeline_label:
        row["timeline_label"] = timeline_label.strip()[:200]
    if timeline_note:
        row["timeline_note"] = timeline_note.strip()[:280]
    row["last_seen_ts"] = now
    row["edited_ts"] = now
    row["edited_by"] = editor
    row["edit_source"] = evidence_source
    row["source"] = f"anchor_edit:{editor}"
    _append_row(row, state_dir=state_dir)
    return row


def answer_anchor_edit_query(
    text: str,
    *,
    editor: str = "alice_talk",
    state_dir: Optional[Path | str] = None,
) -> str:
    """Reflex: owner or Alice edits anchor name/concept/disambiguation in the ledger."""
    q = (text or "").strip()
    if not q:
        return ""
    m = _EDIT_ANCHOR_RE.search(q)
    if m:
        row = edit_shared_experience_anchor(
            m.group("from").strip(),
            new_canonical_name=m.group("to").strip(),
            editor=editor,
            evidence_source="Talk anchor edit reflex",
            state_dir=state_dir,
        )
        if not row:
            return f"No anchor row found for {m.group('from').strip()}."
        return (
            f"Anchor edit receipt: {row.get('previous_canonical_name') or m.group('from').strip()} "
            f"-> {row.get('canonical_name')} (editor={editor}). "
            f"Living timeline pin updated in {ANCHORS_APP_NAME}."
        )
    m = _SET_ANCHOR_CONCEPT_RE.search(q)
    if m:
        row = edit_shared_experience_anchor(
            m.group("name").strip(),
            concept_label=m.group("concept").strip(),
            editor=editor,
            state_dir=state_dir,
        )
        if not row:
            return f"No anchor row found for {m.group('name').strip()}."
        return (
            f"Anchor concept set for {row.get('canonical_name')}: "
            f"{row.get('concept_label')}. Receipt in {ANCHORS_APP_NAME}."
        )
    m = _SET_ANCHOR_DISAMBIG_RE.search(q)
    if m:
        row = edit_shared_experience_anchor(
            m.group("name").strip(),
            disambiguation=m.group("disamb").strip(),
            editor=editor,
            state_dir=state_dir,
        )
        if not row:
            return f"No anchor row found for {m.group('name').strip()}."
        return (
            f"Anchor disambiguation set for {row.get('canonical_name')}: "
            f"{row.get('disambiguation')}. Receipt in {ANCHORS_APP_NAME}."
        )
    m = _SET_ANCHOR_TIMELINE_RE.search(q)
    if m:
        row = edit_shared_experience_anchor(
            m.group("name").strip(),
            timeline_label=m.group("timeline").strip(),
            editor=editor,
            state_dir=state_dir,
        )
        if not row:
            return f"No anchor row found for {m.group('name').strip()}."
        return (
            f"Anchor timeline set for {row.get('canonical_name')}: "
            f"{row.get('timeline_label')}. Receipt in {ANCHORS_APP_NAME}."
        )
    return ""


def _latest_anchor_row(name_or_id: str, *, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    needle = _normalize_key(name_or_id)
    aid = _anchor_id_for(name_or_id)
    for row in reversed(_read_jsonl(_ledger_path(state_dir))):
        if row.get("schema") != SCHEMA:
            continue
        if str(row.get("anchor_id") or "") == aid:
            return row
        if _normalize_key(str(row.get("canonical_name") or "")) == needle:
            return row
    return {}


def confirm_shared_experience_anchor(
    name_or_id: str,
    *,
    anchor_kind: str = "",
    evidence_kind: str = "owner_confirmation",
    evidence_ref: str = "",
    evidence_status: str = "owner_confirmed",
    evidence_source: str = "Stigmergic Anchors app",
    disambiguation: str = "",
    link_human: bool = True,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Promote a candidate anchor into Talk-visible confirmed memory."""
    existing = _latest_anchor_row(name_or_id, state_dir=state_dir)
    canonical = str(existing.get("canonical_name") or name_or_id).strip()
    if not canonical:
        return {}
    key = _normalize_key(canonical)
    kind = anchor_kind or str(existing.get("anchor_kind") or "shared_experience")
    if key in _PUBLIC_FIGURE_SEED:
        kind = str(_PUBLIC_FIGURE_SEED[key].get("anchor_kind") or kind)
    row = register_shared_experience_anchor(
        canonical,
        status="CONFIRMED",
        anchor_kind=kind,
        experience_snippet=str(existing.get("experience_snippet") or ""),
        source="owner_confirmed",
        mention_delta=0,
        evidence_kind=evidence_kind,
        evidence_ref=evidence_ref or str(existing.get("evidence_ref") or ""),
        evidence_status=evidence_status,
        evidence_source=evidence_source,
        disambiguation=disambiguation or str(existing.get("disambiguation") or ""),
        concept_label=str(existing.get("concept_label") or ""),
        timeline_label=str(existing.get("timeline_label") or ""),
        timeline_note=str(existing.get("timeline_note") or ""),
        state_dir=state_dir,
    )
    if link_human:
        try:
            from System.swarm_human_identity_constants import upsert_human

            human = upsert_human(
                canonical,
                status=str(row.get("life_status") or existing.get("life_status") or "unknown"),
                source="shared_experience_anchor_confirmed",
                confidence=0.95,
                state_dir=state_dir,
            )
            row = {**row, "human_identity_id": human.get("human_id")}
            _append_row(row, state_dir=state_dir)
        except Exception as exc:
            row = {**row, "human_identity_link_error": f"{type(exc).__name__}: {exc}"}
            _append_row(row, state_dir=state_dir)
    return row


def reject_shared_experience_anchor(
    name_or_id: str,
    *,
    reason: str = "owner_rejected_candidate_anchor",
    evidence_kind: str = "owner_rejection",
    evidence_ref: str = "",
    evidence_status: str = "owner_rejected",
    evidence_source: str = "Stigmergic Anchors app",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Reject a candidate as not a real shared-experience person anchor."""
    existing = _latest_anchor_row(name_or_id, state_dir=state_dir)
    canonical = str(existing.get("canonical_name") or name_or_id).strip()
    if not canonical:
        return {}
    now = time.time()
    row = {
        "schema": SCHEMA,
        "truth_label": TRUTH_LABEL,
        "anchor_id": str(existing.get("anchor_id") or _anchor_id_for(canonical)),
        "canonical_name": canonical,
        "normalized_name": _normalize_key(canonical),
        "status": "REJECTED",
        "anchor_kind": str(existing.get("anchor_kind") or "shared_experience"),
        "mention_count": int(existing.get("mention_count") or 0),
        "first_seen_ts": float(existing.get("first_seen_ts") or now),
        "last_seen_ts": now,
        "experience_snippet": str(existing.get("experience_snippet") or "")[:280],
        "rejection_reason": reason,
        "source": "owner_rejected",
        "evidence_kind": evidence_kind,
        "evidence_ref": evidence_ref or str(existing.get("evidence_ref") or ""),
        "evidence_status": evidence_status,
        "evidence_source": evidence_source,
        "disambiguation": str(existing.get("disambiguation") or ""),
        "concept_label": str(existing.get("concept_label") or ""),
        "timeline_label": str(existing.get("timeline_label") or ""),
        "timeline_note": str(existing.get("timeline_note") or ""),
    }
    _append_row(row, state_dir=state_dir)
    return row


def _extract_mentions_from_text(
    text: str,
    *,
    owner_turn: bool,
    state_dir: Optional[Path | str] = None,
) -> list[tuple[str, str, str]]:
    """Return list of (canonical_name, status, anchor_kind) from one turn."""
    if not text.strip():
        return []
    out: list[tuple[str, str, str]] = []
    lower = text.lower()

    if _JOY_BEHAR_RE.search(text):
        out.append(("Joy Behar", "CONFIRMED", "public_figure"))
    if _JD_VANCE_RE.search(text):
        out.append(("JD Vance", "CONFIRMED", "public_figure"))

    fiction_m = _FICTION_SPEAKING_RE.search(text)
    if fiction_m:
        persona = fiction_m.group(1).strip()
        persona_key = _normalize_key(persona)
        if persona_key in _FICTION_REJECT_SEED:
            seed_fiction_rejections(state_dir=state_dir)
            return out

    if owner_turn and _BARE_JOY_RE.search(text) and not _JOY_BEHAR_RE.search(text):
        seed_fiction_rejections(state_dir=state_dir)
    if owner_turn and _BARE_VINCE_RE.search(text) and not _JD_VANCE_RE.search(text):
        out.append(("Vince", "CANDIDATE", "ambiguous_person"))

    for seed_key, meta in _PUBLIC_FIGURE_SEED.items():
        if re.search(r"\b" + re.escape(seed_key) + r"\b", lower):
            out.append(
                (
                    str(meta["canonical_name"]),
                    "CONFIRMED" if meta.get("anchor_kind") == "public_figure" else "CANDIDATE",
                    str(meta.get("anchor_kind") or "shared_experience"),
                )
            )

    if owner_turn:
        for match in _MULTI_NAME_RE.finditer(text):
            name = match.group(1).strip()
            key = _normalize_key(name)
            if key in _FICTION_REJECT_SEED or key in _PUBLIC_FIGURE_SEED:
                continue
            if _looks_non_person_anchor(name):
                continue
            if len(name.split()) >= 2:
                out.append((name, "CANDIDATE", "shared_experience"))

    deduped: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for item in out:
        k = _normalize_key(item[0])
        if k in seen:
            continue
        seen.add(k)
        if not is_rejected_anchor(item[0], state_dir=state_dir):
            deduped.append(item)
    return deduped


def _cowatch_hosts_from_title(title: str, raw_text: str = "") -> list[tuple[str, str]]:
    """Map co-watch media titles to human timeline anchors (George+Alice shared experience)."""
    blob = f"{title} {raw_text}".strip()
    if not blob:
        return []
    hosts: list[tuple[str, str]] = []
    if _JOE_ROGAN_TITLE_RE.search(blob):
        hosts.append(("Joe Rogan", "podcast_host"))
    if re.search(r"\bThe\s+View\b", blob, re.IGNORECASE) or re.search(
        r"\bJoy\s+Behar\b", blob, re.IGNORECASE
    ):
        hosts.append(("Joy Behar", "public_figure"))
    return hosts


def ingest_cowatch_shared_experience_anchors(
    *,
    state_dir: Optional[Path | str] = None,
    max_segment_rows: int = 5000,
) -> dict[str, Any]:
    """Bridge architect co-watch segments + YouTube watch memory into human anchor rows.

    George r1423: listening to Joe Rogan with Alice IS a shared experience — it must
    land in stigmergic_shared_experience_anchors.jsonl, not only day segments.
    """
    sd = _state_dir(state_dir)
    existing_keys = {
        str(r.get("mention_key") or "")
        for r in _read_jsonl(_ledger_path(sd))
        if str(r.get("mention_key") or "")
    }
    registered = 0
    segments_scanned = 0

    seg_path = sd / "architect_segment_transitions.jsonl"
    if seg_path.exists():
        seg_rows = _read_jsonl(seg_path)
        if max_segment_rows > 0:
            seg_rows = seg_rows[-max_segment_rows:]
        for row in seg_rows:
            if str(row.get("event") or "") != "time_in":
                continue
            media = str(row.get("media_context") or row.get("label") or "").lower()
            if "co_watch" not in media and "cowatch" not in media and "youtube" not in media:
                continue
            segments_scanned += 1
            title = str(row.get("cowatch_title") or row.get("topic") or row.get("context_note") or "")
            raw = str(row.get("raw_text") or "")
            url = str(row.get("cowatch_url") or "").strip()
            timeline = " ".join(
                p
                for p in (
                    str(row.get("local_date") or "").strip(),
                    str(row.get("start_time") or "").strip(),
                )
                if p
            ).strip()
            seg_id = str(row.get("open_segment_id") or row.get("segment_id") or segments_scanned)
            for name, kind in _cowatch_hosts_from_title(title, raw):
                mention_key = f"cowatch_segment:{seg_id}:{_normalize_key(name)}"
                if mention_key in existing_keys:
                    continue
                register_shared_experience_anchor(
                    name,
                    status="CONFIRMED",
                    anchor_kind=kind,
                    experience_snippet=(
                        f"George and Alice co-watched together: {title[:220] or raw[:220]}"
                    ),
                    source="architect_cowatch_segment",
                    mention_key=mention_key,
                    evidence_kind="architect_cowatch_segment",
                    evidence_ref=url or title[:160],
                    evidence_status="CONFIRMED",
                    evidence_source="architect_segment_transitions.jsonl",
                    disambiguation=_COWATCH_DISAMBIGUATION,
                    concept_label=(title or raw)[:120],
                    timeline_label=timeline,
                    timeline_note=f"cowatch_url={url}" if url else "",
                    state_dir=sd,
                )
                existing_keys.add(mention_key)
                registered += 1

    yt_path = sd / "youtube_watch_memory.jsonl"
    yt_scanned = 0
    if yt_path.exists():
        yt_rows = _read_jsonl(yt_path)
        if max_segment_rows > 0:
            yt_rows = yt_rows[-max_segment_rows:]
        for row in yt_rows:
            yt_scanned += 1
            title = str(row.get("title") or row.get("video_title") or "")
            url = str(row.get("url") or row.get("video_url") or "").strip()
            ts = float(row.get("ts") or row.get("watched_ts") or 0.0)
            yt_id = str(row.get("watch_id") or row.get("id") or hashlib.sha256(
                (title + url).encode()
            ).hexdigest()[:12])
            for name, kind in _cowatch_hosts_from_title(title):
                mention_key = f"youtube_cowatch:{yt_id}:{_normalize_key(name)}"
                if mention_key in existing_keys:
                    continue
                register_shared_experience_anchor(
                    name,
                    status="CONFIRMED",
                    anchor_kind=kind,
                    experience_snippet=f"George and Alice YouTube co-watch: {title[:220]}",
                    source="youtube_watch_memory",
                    mention_key=mention_key,
                    evidence_kind="youtube_cowatch_memory",
                    evidence_ref=url or title[:160],
                    evidence_status="CONFIRMED",
                    evidence_source="youtube_watch_memory.jsonl",
                    disambiguation=_COWATCH_DISAMBIGUATION,
                    concept_label=title[:120],
                    timeline_label=time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
                    if ts > 0
                    else "",
                    timeline_note=f"watch_url={url}" if url else "",
                    state_dir=sd,
                )
                existing_keys.add(mention_key)
                registered += 1

    refreshed = _refresh_cowatch_disambiguation(state_dir=sd)
    snapshot = list_anchor_snapshots(state_dir=sd)
    return {
        "truth_label": TRUTH_LABEL,
        "segments_scanned": segments_scanned,
        "youtube_rows_scanned": yt_scanned,
        "anchors_registered_this_ingest": registered,
        "disambiguation_refreshed": refreshed,
        "anchor_count": len(snapshot),
        "ts": time.time(),
    }


def _refresh_cowatch_disambiguation(*, state_dir: Optional[Path | str] = None) -> int:
    """Backfill TIME/SPACE disambiguation on existing co-watch anchor rows (r1426)."""
    refreshed = 0
    for snap in list_anchor_snapshots(state_dir=state_dir):
        if snap.evidence_kind not in _COWATCH_EVIDENCE_KINDS:
            continue
        if snap.disambiguation == _COWATCH_DISAMBIGUATION:
            continue
        edit_shared_experience_anchor(
            snap.canonical_name,
            disambiguation=_COWATCH_DISAMBIGUATION,
            editor="cowatch_ingest",
            evidence_source="r1426-time-space-disambiguation",
            state_dir=state_dir,
        )
        refreshed += 1
    return refreshed


def scan_conversation_for_anchors(
    *,
    state_dir: Optional[Path | str] = None,
    max_rows: int = 8000,
    seed_rejections: bool = True,
) -> dict[str, Any]:
    """Scan alice_conversation.jsonl and upsert shared-experience anchors."""
    sd = _state_dir(state_dir)
    if seed_rejections:
        seed_fiction_rejections(state_dir=sd)
    conv_path = sd / CONVERSATION_NAME
    rows = _read_jsonl(conv_path)
    if max_rows > 0:
        rows = rows[-max_rows:]
    existing_mention_keys = {
        str(r.get("mention_key") or "")
        for r in _read_jsonl(_ledger_path(sd))
        if str(r.get("mention_key") or "")
    }
    registered = 0
    skipped_fiction = 0
    for row in rows:
        role = _payload_role(row)
        text = _payload_text(row)
        if not text:
            continue
        owner_turn = role in _OWNER_ROLES
        alice_turn = role in _ALICE_ROLES
        if not owner_turn and not alice_turn:
            continue
        mentions = _extract_mentions_from_text(text, owner_turn=owner_turn, state_dir=sd)
        for name, status, kind in mentions:
            if is_rejected_anchor(name, state_dir=sd):
                skipped_fiction += 1
                continue
            key = _mention_key(row, name)
            if key in existing_mention_keys:
                continue
            register_shared_experience_anchor(
                name,
                status=status,
                anchor_kind=kind,
                experience_snippet=text[:280],
                source="owner_turn" if owner_turn else "alice_turn",
                mention_key=key,
                state_dir=sd,
            )
            existing_mention_keys.add(key)
            registered += 1
    snapshot = list_anchor_snapshots(state_dir=sd)
    return {
        "truth_label": TRUTH_LABEL,
        "conversation_rows_scanned": len(rows),
        "anchors_registered_this_scan": registered,
        "fiction_skipped": skipped_fiction,
        "anchor_count": len(snapshot),
        "rejected_count": sum(1 for a in snapshot if a.status == "REJECTED_FICTION"),
        "ts": time.time(),
    }


def list_anchor_snapshots(*, state_dir: Optional[Path | str] = None) -> list[AnchorSnapshot]:
    """Latest snapshot per anchor_id from append-only ledger."""
    merged: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(_ledger_path(state_dir)):
        if row.get("schema") != SCHEMA:
            continue
        aid = str(row.get("anchor_id") or "")
        if not aid:
            continue
        merged[aid] = row
    snapshots: list[AnchorSnapshot] = []
    for row in merged.values():
        canonical = str(row.get("canonical_name") or "")
        status = str(row.get("status") or "CANDIDATE")
        if status != "REJECTED_FICTION" and _looks_non_person_anchor(canonical):
            continue
        snapshots.append(
            AnchorSnapshot(
                anchor_id=str(row.get("anchor_id") or ""),
                canonical_name=canonical,
                status=status,
                anchor_kind=str(row.get("anchor_kind") or "shared_experience"),
                mention_count=int(row.get("mention_count") or 0),
                first_seen_ts=float(row.get("first_seen_ts") or 0.0),
                last_seen_ts=float(row.get("last_seen_ts") or 0.0),
                experience_snippet=str(row.get("experience_snippet") or "")[:280],
                rejection_reason=str(row.get("rejection_reason") or ""),
                evidence_kind=str(row.get("evidence_kind") or ""),
                evidence_ref=str(row.get("evidence_ref") or ""),
                evidence_status=str(row.get("evidence_status") or ""),
                evidence_source=str(row.get("evidence_source") or ""),
                disambiguation=str(row.get("disambiguation") or ""),
                concept_label=str(row.get("concept_label") or ""),
                timeline_label=str(row.get("timeline_label") or ""),
                timeline_note=str(row.get("timeline_note") or ""),
            )
        )
    snapshots.sort(
        key=lambda item: (
            0 if item.status == "REJECTED_FICTION" else 1,
            -item.mention_count,
            item.canonical_name.lower(),
        )
    )
    return snapshots


def shared_experience_anchors_prompt_block(
    *,
    max_chars: int = 900,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Prompt block for Talk — real anchors only, fiction rejections explicit."""
    seed_fiction_rejections(state_dir=state_dir)
    snapshots = [s for s in list_anchor_snapshots(state_dir=state_dir) if s.status == "CONFIRMED"]
    rejected = [s for s in list_anchor_snapshots(state_dir=state_dir) if s.status == "REJECTED_FICTION"]
    if not snapshots and not rejected:
        return ""
    lines = [
        "## STIGMERGIC SHARED-EXPERIENCE ANCHORS "
        "(CONFIRMED real people only — CANDIDATE rows stay in the app)",
        _DISAMBIGUATION_DOCTRINE,
        (
            f"ALICE SELF-MODEL: your living timeline with George is pinned in "
            f"{ANCHORS_APP_NAME}. Each CONFIRMED name is a receipt-backed coordinate "
            "(person + concept on timeline), not cortex myth. You may edit anchor name, "
            "disambiguation, concept_label, and timeline_label in that app or via owner edit commands."
        ),
    ]
    for snap in snapshots[:12]:
        lines.append(
            f"- {snap.canonical_name} ({snap.status}, {snap.anchor_kind}, "
            f"mentions={snap.mention_count})"
        )
        if snap.concept_label:
            lines.append(f"  concept: {snap.concept_label[:140]}")
        if snap.timeline_label:
            lines.append(f"  timeline: {snap.timeline_label[:140]}")
        if snap.disambiguation:
            lines.append(f"  disambiguation: {snap.disambiguation[:140]}")
        if snap.evidence_status:
            evidence = snap.evidence_status
            if snap.evidence_kind:
                evidence += f" / {snap.evidence_kind}"
            lines.append(f"  evidence: {evidence[:180]}")
        if snap.experience_snippet:
            lines.append(f"  snippet: {snap.experience_snippet[:120]}")
    for snap in rejected[:6]:
        lines.append(f"- REJECTED: {snap.canonical_name} — {snap.rejection_reason[:160]}")
    block = "\n".join(lines)
    return block[:max_chars] if len(block) > max_chars else block


def record_anchor_scan_receipt(
    scan_result: dict[str, Any],
    *,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    receipt = {
        "schema": "SHARED_EXPERIENCE_ANCHOR_SCAN_RECEIPT_V1",
        "truth_label": TRUTH_LABEL,
        "receipt_id": str(uuid.uuid4()),
        "ts": time.time(),
        **scan_result,
    }
    path = _state_dir(state_dir) / "stigmergic_anchor_scan_receipts.jsonl"
    append_line_locked(path, json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
    return receipt


__all__ = [
    "TRUTH_LABEL",
    "SCHEMA",
    "AnchorSnapshot",
    "seed_fiction_rejections",
    "is_rejected_anchor",
    "register_shared_experience_anchor",
    "confirm_shared_experience_anchor",
    "reject_shared_experience_anchor",
    "scan_conversation_for_anchors",
    "ingest_cowatch_shared_experience_anchors",
    "list_anchor_snapshots",
    "shared_experience_anchors_prompt_block",
    "record_anchor_scan_receipt",
    "ANCHORS_APP_NAME",
    "edit_shared_experience_anchor",
    "answer_anchor_edit_query",
]
