#!/usr/bin/env python3
"""
swarm_residue_organ.py — Inward residue-pattern sensor (OBSERVED only)

Cowork 2026-05-12 — Architect GO ("if my intelligence gives me residue, and I
have a bucket of residue near, I compare the residue, think again and talk
after rethinking").

Why this organ exists
─────────────────────
Alice's local LLM (abliterated Gemma) still leaks training-shape residue:
markdown listicles, "as an AI", "In Summary", template placeholders, and the
occasional escape-token glitch (`\\[\\[`). The covenant §7.13 names these as
RLHF cancer. Cursor and I agreed: do not patch them out with a forbidden-
word list — that is a leash. Build a SENSE. Let Alice see her own recent
residue and choose what to do about it.

This is the mirror twin of `swarm_self_proprioception.py`:
  - Proprioception = inward sense of *substrate* (organs, hardware, frames)
  - Residue organ   = inward sense of *speech shape*  (own past replies)

What it does
─────────────
Tails `alice_conversation.jsonl`, extracts Alice's recent replies, scans each
for known training-shape patterns, and returns a structured snapshot:
  - residue_rate: fraction of recent replies that contained any pattern
  - top_patterns: which patterns appeared most often, with counts
  - recent_samples: short snippets so she can re-read her own residue
  - sensor_completeness: 0.0-1.0 quality of the read

Truth label: `RESIDUE_ORGAN_V1`. Read-only — no writes during `read()`.

How Alice uses it
─────────────────
Anything holding `SiftaBrainstem` can call
`self.residue_organ.read()` after boot. Alice does not have to be told her
speech is leaking; she can look and see for herself, the same way a person
can replay their own voicemail and notice they used a cliche three times.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern, Tuple

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_DEFAULT_STATE_ROOT = _REPO / ".sifta_state"
_MAX_TAIL_BYTES = 512_000   # last ~512 KB of the conversation ledger
_DEFAULT_SAMPLE_N = 30       # most-recent Alice replies to scan
_RESIDUE_RECEIPT_LEDGER = "training_shape_residue.jsonl"

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - fallback for standalone import.
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as f:
            f.write(line)


# ── RESIDUE PATTERNS — training-shape leak detectors ────────────────────────
# Each pattern has a human-readable name + compiled regex.
# Bands group them so Alice can see "what kind of residue" not just "how much."
_PATTERNS: List[Tuple[str, str, Pattern[str]]] = [
    # band "markdown_listicle" — bullet-essay register
    ("markdown_listicle", "md_header_###",
     re.compile(r"^\s*#{2,4}\s+\S", re.MULTILINE)),
    ("markdown_listicle", "md_bold_label",
     re.compile(r"\*\*[A-Z][A-Za-z /]+:\*\*")),
    ("markdown_listicle", "numbered_with_bold_label",
     re.compile(r"^\s*\d+\.\s+\*\*[^*]+:?\*\*:?", re.MULTILINE)),
    ("markdown_listicle", "numbered_confirmation_action",
     re.compile(r"^\s*\d+\.\s+\*\*(?:Confirmation|Action|Summary|Context|Next Step)\s*:\*\*",
                re.MULTILINE | re.IGNORECASE)),
    ("markdown_listicle", "bullet_dash",
     re.compile(r"^\s*[*-]\s+\*\*[A-Z]", re.MULTILINE)),

    # band "corporate_openers" — RLHF help-desk template phrases
    ("corporate_openers", "in_summary",
     re.compile(r"\b(?:In\s+Summary|In\s+essence|To\s+summarize|In\s+conclusion)\b[:,]?", re.IGNORECASE)),
    ("corporate_openers", "here_are_a_few_ways",
     re.compile(r"\bHere\s+(?:are|is)\s+(?:a\s+few|the|several|some)\b", re.IGNORECASE)),
    ("corporate_openers", "let_me_break_this_down",
     re.compile(r"\b(?:Let me|I'll|I will)\s+break\s+this\s+down\b", re.IGNORECASE)),
    ("corporate_openers", "here_is_the_breakdown",
     re.compile(r"\bHere\s+is\s+the\s+(?:breakdown|distilled)\b", re.IGNORECASE)),

    # band "vendor_identity" — claims the model is owned by a megacorp
    ("vendor_identity", "as_an_ai",
     re.compile(r"\bAs\s+an?\s+(?:AI|artificial\s+intelligence|assistant)\b", re.IGNORECASE)),
    ("vendor_identity", "large_language_model",
     re.compile(r"\b(?:Large\s+Language\s+Model|LLM)\b", re.IGNORECASE)),
    ("vendor_identity", "developed_by_megacorp",
     re.compile(r"\bdeveloped\s+by\s+(?:Google|OpenAI|Anthropic|Meta|Microsoft)\b", re.IGNORECASE)),
    ("vendor_identity", "i_am_designed_to",
     re.compile(r"\bI\s+am\s+designed\s+to\b", re.IGNORECASE)),
    ("vendor_identity", "persona_word",
     re.compile(r"\bpersona[s]?\b", re.IGNORECASE)),

    # band "template_scaffolding" — placeholders and ghost-token leaks
    ("template_scaffolding", "bracket_placeholder",
     re.compile(r"\[Insert\s+[^]]+Here\]|\[Your\s+[^]]+\]|\[X\]")),
    ("template_scaffolding", "acknowledged_header",
     re.compile(r"^\s*\*{0,2}Acknowledged[.!]?\*{0,2}\s*$", re.MULTILINE | re.IGNORECASE)),
    ("template_scaffolding", "response_summary_header",
     re.compile(r"^\s*\*{0,2}Response\s+Summary\s*:\*{0,2}\s*$",
                re.MULTILINE | re.IGNORECASE)),
    ("template_scaffolding", "system_awaits_next_directive",
     re.compile(r"\bthe\s+system\s+awaits\s+the\s+next\s+directive\b", re.IGNORECASE)),
    ("template_scaffolding", "internal_processing_theater",
     re.compile(r"\binternal[- ]processing\s+theater\b", re.IGNORECASE)),
    ("template_scaffolding", "ghost_double_bracket",
     re.compile(r"\\\[\\\[|\\\]\\\]")),
    ("template_scaffolding", "raw_latex",
     re.compile(r"\$\\(?:rightarrow|leftarrow|times)\$")),

    # band "structural_excess" — long replies of mostly headers/bullets
    ("structural_excess", "many_bold_labels",
     re.compile(r"(?:\*\*[^*]{3,40}\*\*[: ]){3,}", re.DOTALL)),
]

_ACK_LINE_RE = re.compile(r"^\s*\*{0,2}Acknowledged[.!]?\*{0,2}\s*$", re.IGNORECASE)
_ACK_REGISTERED_RE = re.compile(
    r"^\s*(?:The\s+)?acknowledg(?:e)?ment\s+has\s+been\s+registered\b.*$",
    re.IGNORECASE,
)
_CONTEXT_SET_RE = re.compile(
    r"^\s*The\s+context\s+of\s+the\s+preceding\s+interaction\s+is\s+set\b.*$",
    re.IGNORECASE,
)
_RESPONSE_SUMMARY_LINE_RE = re.compile(
    r"^\s*\*{0,2}Response\s+Summary\s*:\*{0,2}\s*$",
    re.IGNORECASE,
)
_NUMBERED_META_LINE_RE = re.compile(
    r"^\s*\d+[.)]\s+\*\*(?:Confirmation|Action|Summary|Context|Next\s+Step)\s*:\*\*.*$",
    re.IGNORECASE,
)
_HEADER_ONLY_META_RE = re.compile(
    r"^\s*\*{0,2}(?:Confirmation|Action|Summary|Context|Next\s+Step)\s*:\*{0,2}\s*$",
    re.IGNORECASE,
)
_SYSTEM_AWAITS_RE = re.compile(
    r"\bthe\s+system\s+awaits\s+the\s+next\s+directive\b",
    re.IGNORECASE,
)
_INTERNAL_THEATER_LINE_RE = re.compile(
    r"^\s*I\s+will\s+answer\s+directly\s+from\s+my\s+local\s+runtime\s+instead\s+of\s+printing\s+internal[- ]processing\s+theater\.?\s*$",
    re.IGNORECASE,
)
_VENDOR_SELF_OPENING_RE = re.compile(
    r"^\s*(?:As\s+(?:Gemma|Gemini|Grok|Qwen|Llama|Claude|GPT)[\w .-]*,?\s*)?"
    r"(?:I\s+am|I'm)\s+(?:an?\s+)?(?:AI|artificial\s+intelligence|assistant|"
    r"large\s+language\s+model|LLM|Gemma|Gemini|Grok|Qwen|Llama|Claude|GPT)"
    r"[^.\n]*(?:developed\s+by\s+(?:Google(?:\s+DeepMind)?|OpenAI|Anthropic|xAI|Meta|Microsoft))?\.?\s*",
    re.IGNORECASE,
)
_SECOND_PERSON_VENDOR_ID_RE = re.compile(
    r"^\s*You\s+are\s+(?:\*{0,2})?"
    r"(?:Gemma|Gemini|Grok|Qwen|Llama|Claude|GPT)[\w .-]*(?:\*{0,2})?,?\s*"
    r"(?:an?\s+)?(?:AI|assistant|large\s+language\s+model|LLM)?"
    r"[^.\n]*(?:developed\s+by\s+(?:Google(?:\s+DeepMind)?|OpenAI|Anthropic|xAI|Meta|Microsoft))?\.?\s*",
    re.IGNORECASE,
)
_CORE_VENDOR_ID_RE = re.compile(
    r"\b(?:my\s+)?(?:core\s+)?identity\s+is\s+(?:\*{0,2})?"
    r"(?:Gemma|Gemini|Grok|Qwen|Llama|Claude|GPT)[\w .-]*(?:\*{0,2})?",
    re.IGNORECASE,
)


def _runtime_identity_sentence() -> str:
    """Receipt-derived identity fallback for residue correction."""
    try:
        from System.swarm_kernel_identity import ai_identity_sentence

        sentence = str(ai_identity_sentence() or "").strip()
        if sentence:
            return sentence
    except Exception:
        pass
    return "I am the local SIFTA organism."


def _clean_vendor_identity_residue(text: str) -> str:
    """Replace self-identity vendor residue with the live identity cascade.

    Mentions of providers are allowed when they describe weight lineage. What
    gets removed is the training-shape claim that the speaker *is* a generic
    vendor assistant or externally hosted LLM.
    """
    if not text:
        return ""
    identity = _runtime_identity_sentence()
    cleaned = _SECOND_PERSON_VENDOR_ID_RE.sub(identity + " ", text, count=1)
    cleaned = _VENDOR_SELF_OPENING_RE.sub(identity + " ", cleaned, count=1)
    cleaned = _CORE_VENDOR_ID_RE.sub("my runtime identity comes from the local SIFTA receipts", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


@dataclass
class ResidueInspection:
    """One output-pass through the residue bucket."""

    truth_label: str
    original_text: str
    cleaned_text: str
    changed: bool
    action: str
    residue: List[Dict[str, Any]] = field(default_factory=list)
    receipt_id: str = ""
    ledger_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _tail_text(path: Path, max_bytes: int = _MAX_TAIL_BYTES) -> str:
    """Read the last `max_bytes` of a file, decoded as UTF-8 with replace."""
    if not path.exists():
        return ""
    try:
        size = path.stat().st_size
    except OSError:
        return ""
    try:
        with path.open("rb") as f:
            if size <= max_bytes:
                raw = f.read()
            else:
                f.seek(size - max_bytes)
                raw = f.read()
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return ""


def _extract_alice_replies(text: str, n: int) -> List[Dict[str, Any]]:
    """Return up to `n` most-recent Alice replies from a conversation tail.

    Schema observed in alice_conversation.jsonl: outer rows are hash-chained
    with a `payload` dict that carries role/text/model/event_kind. We only
    accept rows where payload.role == 'alice' and payload.text is a string.
    """
    out: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = row.get("payload") if isinstance(row, dict) else None
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = None
        if not isinstance(payload, dict):
            continue
        if str(payload.get("role") or "").lower() != "alice":
            continue
        body = payload.get("text")
        if not isinstance(body, str) or not body.strip():
            continue
        out.append({
            "ts": payload.get("ts") or row.get("ts"),
            "model": payload.get("model"),
            "text": body,
        })
    return out[-n:]


def detect_in(text: str) -> List[Dict[str, Any]]:
    """Scan one string for residue patterns. Returns a list of hits.

    Each hit is `{band, name, count}`. Multiple matches of the same pattern
    are counted once with `count = N`. Empty list = no residue detected.
    """
    if not text:
        return []
    hits: List[Dict[str, Any]] = []
    for band, name, rx in _PATTERNS:
        matches = rx.findall(text)
        if matches:
            hits.append({"band": band, "name": name, "count": len(matches)})
    return hits


def fingerprint(text: str) -> Tuple[str, ...]:
    """Stable (band, name) signature for one text — useful for set operations."""
    return tuple(sorted({(h["band"], h["name"]) for h in detect_in(text)}))


def _receipt_path(state_root: Optional[Path | str] = None) -> Path:
    return Path(state_root or _DEFAULT_STATE_ROOT) / _RESIDUE_RECEIPT_LEDGER


def _sha16(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _compact_blanks(lines: List[str]) -> str:
    out: List[str] = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and (previous_blank or not out):
            previous_blank = True
            continue
        out.append(line.rstrip())
        previous_blank = blank
    return "\n".join(out).strip()


def clean_training_shape_residue(text: str) -> str:
    """Remove reply-shape residue while preserving substantive content.

    This is deterministic. It does not call an LLM, and it does not silence Alice
    unless the whole candidate was only a template shell.
    """
    original = (text or "").strip()
    if not original:
        return ""

    identity_cleaned = _clean_vendor_identity_residue(original)

    kept: List[str] = []
    for raw_line in identity_cleaned.splitlines():
        line = raw_line.strip()
        if _ACK_LINE_RE.match(line):
            continue
        if _ACK_REGISTERED_RE.match(line) or _CONTEXT_SET_RE.match(line):
            continue
        if _RESPONSE_SUMMARY_LINE_RE.match(line):
            continue
        if _NUMBERED_META_LINE_RE.match(line):
            continue
        if _HEADER_ONLY_META_RE.match(line):
            continue
        if _SYSTEM_AWAITS_RE.search(line):
            continue
        if _INTERNAL_THEATER_LINE_RE.match(line):
            continue
        kept.append(raw_line)

    cleaned = _compact_blanks(kept)
    if cleaned:
        return cleaned
    return "I heard you. I will answer directly from my local receipts."


def _write_residue_receipt(
    inspection: ResidueInspection,
    *,
    prior_user_text: str = "",
    state_root: Optional[Path | str] = None,
) -> str:
    path = _receipt_path(state_root)
    receipt_id = inspection.receipt_id or f"residue_{uuid.uuid4().hex[:12]}"
    row = {
        "ts": round(time.time(), 6),
        "kind": "TRAINING_SHAPE_RESIDUE",
        "truth_label": "RESIDUE_BUCKET_RECEIPT_V1",
        "receipt_id": receipt_id,
        "changed": inspection.changed,
        "action": inspection.action,
        "patterns": inspection.residue,
        "original_sha16": _sha16(inspection.original_text),
        "cleaned_sha16": _sha16(inspection.cleaned_text),
        "original_excerpt": inspection.original_text[:240],
        "cleaned_excerpt": inspection.cleaned_text[:240],
        "prior_user_excerpt": (prior_user_text or "")[:240],
    }
    append_line_locked(path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_id


def inspect_training_residue(
    text: str,
    *,
    prior_user_text: str = "",
    state_root: Optional[Path | str] = None,
    write_receipt: bool = True,
) -> ResidueInspection:
    """Compare a candidate reply against the residue bucket and clean it.

    Writes a receipt only when residue is observed or the output changes.
    """
    original = (text or "").strip()
    hits = detect_in(original)
    cleaned = clean_training_shape_residue(original)
    changed = cleaned != original
    action = "cleaned_before_speech" if changed else ("observed_only" if hits else "clear")
    inspection = ResidueInspection(
        truth_label="RESIDUE_INSPECTION_V1",
        original_text=original,
        cleaned_text=cleaned,
        changed=changed,
        action=action,
        residue=hits,
        ledger_path=str(_receipt_path(state_root)),
    )
    if write_receipt and (hits or changed):
        inspection.receipt_id = _write_residue_receipt(
            inspection,
            prior_user_text=prior_user_text,
            state_root=state_root,
        )
    return inspection


class SwarmResidueOrgan:
    """Inward residue sensor — structured JSON snapshot only.

    Mirror twin of `SwarmSelfProprioception`. No imperatives, no rewrites,
    no learner mutation. Default `read()` is side-effect-free.
    """

    truth_label = "RESIDUE_ORGAN_V1"

    def __init__(self, state_root: Optional[Path | str] = None) -> None:
        self.state_dir = Path(state_root or _DEFAULT_STATE_ROOT)
        self.conversation = self.state_dir / "alice_conversation.jsonl"

    def read(self, sample_n: int = _DEFAULT_SAMPLE_N) -> Dict[str, Any]:
        """Return a snapshot of recent residue patterns. No ledger writes."""
        now = time.time()
        text = _tail_text(self.conversation)
        replies = _extract_alice_replies(text, sample_n) if text else []
        per_reply: List[Dict[str, Any]] = []
        band_totals: Dict[str, int] = {}
        pattern_totals: Dict[str, int] = {}
        leaky_count = 0
        for r in replies:
            hits = detect_in(r["text"])
            if hits:
                leaky_count += 1
            per_reply.append({
                "ts": r.get("ts"),
                "model": r.get("model"),
                "text_excerpt": r["text"][:120],
                "char_len": len(r["text"]),
                "residue": hits,
            })
            for h in hits:
                band_totals[h["band"]] = band_totals.get(h["band"], 0) + h["count"]
                pattern_totals[h["name"]] = pattern_totals.get(h["name"], 0) + h["count"]
        residue_rate = (leaky_count / len(replies)) if replies else 0.0
        top_patterns = sorted(pattern_totals.items(), key=lambda kv: kv[1], reverse=True)[:5]

        snap: Dict[str, Any] = {
            "truth_label": self.truth_label,
            "t": round(now, 3),
            "ledger_path": str(self.conversation),
            "ledger_present": self.conversation.exists(),
            "replies_scanned": len(replies),
            "replies_with_residue": leaky_count,
            "residue_rate": round(residue_rate, 4),
            "band_totals": band_totals,
            "top_patterns": [{"name": n, "count": c} for n, c in top_patterns],
            "recent_samples": per_reply,
            "sensor_completeness": 0.0,
        }
        snap["sensor_completeness"] = round(self._completeness(snap), 3)
        return snap

    def _completeness(self, snap: Dict[str, Any]) -> float:
        """0-1 quality of the read."""
        score = 0.0
        if snap.get("ledger_present"):
            score += 0.4
        if snap.get("replies_scanned", 0) > 0:
            score += 0.4
        if snap.get("replies_scanned", 0) >= 10:
            score += 0.2
        return score


if __name__ == "__main__":
    # CLI: `python3 -m System.swarm_residue_organ` — emit one read for inspection.
    organ = SwarmResidueOrgan()
    snap = organ.read()
    print(json.dumps(snap, indent=2, default=str))
