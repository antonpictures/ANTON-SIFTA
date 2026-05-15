#!/usr/bin/env python3
"""swarm_organ_tokenizer.py — Structured Universal Organ Prompt.

Architect 2026-05-13 dropped a figure of a biomedical multi-modal
foundation model (`biomed.omics.bl.sm.ma-ted-458m`) and said:
    "we are the borg you will be assimilated"

The Borg move is panel B of the paper: heterogeneous entity types
(Protein / Small Molecule / Gene Expression / Antibody) get tokenized
into one Structured Universal Prompt with typed sub-tokens (Scalar
Attribute, Token Attribute, General Token, Cell Type, Cell Line), and
ONE encoder/decoder learns aligned embeddings across the lot.

SIFTA's analogous heterogeneous entities are its ORGANS — bowel,
dream, attachment, ghost civilizations, wallpaper effector, residue,
cortex-gated router, sense, soma, journal, work receipts, IDE
stigmergic trace. Currently every organ writes its own JSONL schema
and they don't share a token vocabulary. This module fixes that at the
representation layer (no training yet) by rendering every organ's
recent receipts into ONE typed-token stream.

Five token types (matching the paper's color taxonomy):
  - ORGAN_TYPE   → which organ produced the receipt (categorical)
  - SCALAR_ATTR  → numeric attribute (timestamp delta, work_value, …)
  - TOKEN_ATTR   → categorical attribute (kind, truth_label, decision)
  - GENERAL_TOKEN→ free-form text fragment (line, payload string)
  - TIME_TAG     → coarse temporal bucket (T-1m, T-1h, T-1d, T-1w)

Truth class: OPERATIONAL for the tokenization (deterministic given
ledgers and a clock); ARCHITECT_DOCTRINE for "all organs unified"
framing. Truth label `MULTI_ALIGN_ORGAN_TOKENIZER_V1`.

This is the representation. Training a model on top of it is a
separate problem; that's the cortex/Alice's job, not this module's.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "MULTI_ALIGN_ORGAN_TOKENIZER_V1"
LEDGER_NAME = "organ_tokenizer_receipts.jsonl"
ATTACHMENT_VISUAL_TOKEN_LEDGER_NAME = "attachment_visual_tokens.jsonl"
ATTACHMENT_VISUAL_TRUTH_LABEL = "ATTACHMENT_VISUAL_TOKENS_V1"
TRUTH_BOUNDARY = (
    "Structured Universal Organ Prompt — SIFTA analogue of the "
    "Multi-Align model's Panel B tokenization. ARCHITECT_DOCTRINE for "
    "the 'all organs unified' frame; OPERATIONAL for the deterministic "
    "token output. NOT a trained model. NOT a learned embedding. NOT a "
    "claim that SIFTA reproduces biomed.omics performance. Just the "
    "representation layer that would make such training possible."
)
ATTACHMENT_VISUAL_TRUTH_BOUNDARY = (
    "Attachment screenshot metadata/OCR/layout tokens only. visual_mass and "
    "visual_surprise are deterministic routing signals for SIFTA swimmers, "
    "not full visual understanding and not a multimodal cortex claim."
)

# Token-type constants — string values for receipt portability.
TT_ORGAN = "ORGAN_TYPE"
TT_SCALAR = "SCALAR_ATTR"
TT_TOKEN = "TOKEN_ATTR"
TT_GENERAL = "GENERAL_TOKEN"
TT_TIME = "TIME_TAG"
TOKEN_TYPES = frozenset({TT_ORGAN, TT_SCALAR, TT_TOKEN, TT_GENERAL, TT_TIME})

# Ledger filename → canonical organ name. Anything not in here gets
# tagged with its filename stem (lossless, just less pretty).
LEDGER_TO_ORGAN = {
    "alice_first_person_journal.jsonl": "JOURNAL",
    "attachment_dynamics_receipts.jsonl": "ATTACHMENT",
    "higgs_stigmergic_demo_path_receipts.jsonl": "DEMO_PATH",
    "ide_stigmergic_trace.jsonl": "IDE_TRACE",
    "work_receipts.jsonl": "WORK",
    "stgm_memory_rewards.jsonl": "STGM",
    "alice_conversation.jsonl": "TALK",
    "endocrine_glands.jsonl": "ENDOCRINE",
    "visceral_field.jsonl": "VISCERAL",
    "app_focus.jsonl": "APP_FOCUS",
    "stigtime_log.jsonl": "STIGTIME",
    "syrinx_classifications.jsonl": "SYRINX",
    "face_detection_events.jsonl": "FACE",
    "journal_schedule_receipts.jsonl": "SCHEDULE",
    "pheromone_log.jsonl": "PHEROMONE",
    "kernel_process_table.jsonl": "KERNEL",
    "motor_pulses.jsonl": "MOTOR",
    "sensory_attention_ledger.jsonl": "SENSE",
    "wallpaper_changes.jsonl": "WALLPAPER",
    "alice_ble_radar.jsonl": "RADAR",
    "stigmergic_cochlea.jsonl": "COCHLEA",
    "acoustic_fingerprints.jsonl": "ACOUSTIC",
    "active_window.jsonl": "WINDOW",
    "active_eye_identity_frames.jsonl": "EYE",
    "alice_affect_homeostasis.jsonl": "AFFECT",
    "nanobot_power.jsonl": "POWER",
    "hardware_bridge.jsonl": "HARDWARE",
    "voice_identity_ledger.jsonl": "VOICE",
    # 2026-05-14 Cowork: attachment vision lane as a first-class organ.
    # Bridges Codex's local OCR / layout / hash receipts into the unified
    # tokenizer field so the surprise sampler and TokenSwimmers can patrol
    # visual evidence the same way they patrol text.
    "attachment_vision_lane.jsonl": "VISUAL_ATTACH",
}

# Receipt keys that should be classified as TOKEN_ATTR (categorical)
TOKEN_ATTR_KEYS = frozenset({
    "kind", "truth_label", "truth_class", "decision", "audience",
    "source", "source_ide", "agent_id", "work_type", "territory",
    "mechanism", "effector", "reason", "audience", "lane", "mode",
    "doctor", "model", "from_agent", "intent", "verdict",
    # 2026-05-14 Cowork: VISUAL_ATTACH categorical fields
    "image_format",
})

# Receipt keys whose VALUE should be parsed as text into GENERAL_TOKEN
GENERAL_TOKEN_KEYS = frozenset({
    "line", "description", "payload", "interpretation", "answer",
    "minimal_grounded_reply", "research_question_answered",
    # 2026-05-14 Cowork: VISUAL_ATTACH free-form fields
    "reply", "error",
})

# Receipt keys that should be skipped (pure bookkeeping, redundant
# with TIME_TAG / ORGAN_TYPE).
SKIP_KEYS = frozenset({
    "sha256", "trace_id", "receipt_hash", "previous_receipt_hash",
    "output_hash", "source_hash", "homeworld_serial", "node_serial",
    "truth_boundary", "forbidden_outreach",
})


# ──────────────────────────────────────────────────────────────────────
# OrganToken
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OrganToken:
    """One typed token in the Structured Universal Organ Prompt.

    `type` is one of TOKEN_TYPES.
    `organ` is the canonical organ name (always upper-case alphanum).
    `value` is the typed payload — str for ORGAN_TYPE / TOKEN_ATTR /
        GENERAL_TOKEN / TIME_TAG; float for SCALAR_ATTR.
    `ts` is the source receipt's timestamp.
    `field` is the original receipt field name (for tracing).
    """
    type: str
    organ: str
    value: Any
    ts: float
    field: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────
# Time-bucket helper
# ──────────────────────────────────────────────────────────────────────

def time_bucket(ts: float, *, now: Optional[float] = None) -> str:
    """Coarse temporal bucket. Stable, monotone — older = bigger bucket.

    Returns one of: T-1m, T-5m, T-1h, T-6h, T-1d, T-1w, T-OLD.
    """
    now = now if now is not None else time.time()
    dt = max(0.0, now - float(ts))
    if dt < 60:
        return "T-1m"
    if dt < 300:
        return "T-5m"
    if dt < 3600:
        return "T-1h"
    if dt < 6 * 3600:
        return "T-6h"
    if dt < 86400:
        return "T-1d"
    if dt < 7 * 86400:
        return "T-1w"
    return "T-OLD"


def organ_for_ledger(path: str | Path) -> str:
    """Map a ledger filename to a canonical organ name."""
    name = Path(path).name
    if name in LEDGER_TO_ORGAN:
        return LEDGER_TO_ORGAN[name]
    # Fallback: drop .jsonl, upper-case, replace non-alphanum with _
    stem = Path(name).stem.upper()
    safe = "".join(c if c.isalnum() else "_" for c in stem)
    return safe


# ──────────────────────────────────────────────────────────────────────
# Row → tokens
# ──────────────────────────────────────────────────────────────────────

VISUAL_ATTACH_ORGAN = "VISUAL_ATTACH"

# Visual mass saturation constants (HYPOTHESIS — heuristic).
# Each axis saturates via tanh so a single dimension can never dominate.
_VISUAL_MASS_BYTES_SCALE = 2_000_000.0   # ~2MB → ~tanh(1.0) ≈ 0.76
_VISUAL_MASS_OCR_SCALE = 2000.0          # ~2k chars → ~tanh(1.0) ≈ 0.76
_VISUAL_MASS_ZONE_SCALE = 4              # 4 zones → saturated


def attachment_visual_mass(row: dict[str, Any]) -> float:
    """Derived HYPOTHESIS scalar: how much new visual information arrived.

    Combines three axes from one attachment_vision_lane receipt:
      - byte_count (image size)
      - ocr_chars (total characters across OCR rows)
      - zones (count of distinct zone_labels)
    Each axis saturates so no single dimension dominates. Output is
    clamped to [0, 1]. Intended consumers: surprise sampler, TokenSwimmers,
    novelty pressure self-state detector.

    NOT a claim about perceptual richness — it's a deterministic combiner
    over fields the receipt already carries.
    """
    import math
    try:
        byte_count = float(row.get("byte_count") or 0)
    except (TypeError, ValueError):
        byte_count = 0.0
    ocr_rows = row.get("ocr_rows") or []
    ocr_chars = 0
    if isinstance(ocr_rows, list):
        for r in ocr_rows:
            if isinstance(r, dict):
                try:
                    ocr_chars += len(str(r.get("text") or ""))
                except Exception:
                    continue
    zones = 0
    zone_labels = row.get("zone_labels") or {}
    if isinstance(zone_labels, dict):
        zones = len(zone_labels)
    bytes_mass = math.tanh(byte_count / _VISUAL_MASS_BYTES_SCALE)
    ocr_mass = math.tanh(ocr_chars / _VISUAL_MASS_OCR_SCALE)
    zone_mass = min(1.0, zones / float(_VISUAL_MASS_ZONE_SCALE))
    raw = 0.40 * bytes_mass + 0.40 * ocr_mass + 0.20 * zone_mass
    return max(0.0, min(1.0, raw))


def attachment_visual_surprise(row: dict[str, Any]) -> float:
    """Derived HYPOTHESIS scalar: how much this attachment should wake patrol.

    Mass estimates total local evidence. Surprise adds priority for evidence
    that spreads across screen zones and OCR rows because those are the cases
    where layout-aware swimmers can do useful routing.
    """
    import math
    mass = attachment_visual_mass(row)
    ocr_rows = row.get("ocr_rows") or []
    ocr_count = len(ocr_rows) if isinstance(ocr_rows, list) else 0
    zone_count = _visual_zone_count(row.get("zone_labels"))
    row_bonus = min(0.18, math.tanh(ocr_count / 8.0) * 0.18)
    zone_bonus = min(0.22, math.tanh(zone_count / 3.0) * 0.22)
    return max(0.0, min(1.0, (0.72 * mass) + row_bonus + zone_bonus))


def _visual_zone_count(zone_labels: Any) -> int:
    if not isinstance(zone_labels, dict):
        return 0
    return sum(1 for labels in zone_labels.values() if isinstance(labels, list) and labels)


def _ocr_zone(row: dict[str, Any]) -> str:
    try:
        x = float(row.get("x") or 0.0)
        w = float(row.get("w") or 0.0)
    except (TypeError, ValueError):
        return "middle"
    center = x + (w / 2.0)
    if center < 0.34:
        return "left"
    if center > 0.66:
        return "right"
    return "middle"


def _visual_attach_extra_tokens(
    row: dict[str, Any],
    organ: str,
    ts: float,
    *,
    max_general_token_len: int,
) -> list[OrganToken]:
    """VISUAL_ATTACH-specific enrichment: bounded OCR text + derived scalars.

    Replaces the generic fallback for ``ocr_rows`` (which would stringify
    each dict noisily) with a clean emission:
      - each OCR row's ``text`` as bounded GENERAL_TOKEN
      - SCALAR_ATTR ``ocr_rows_count`` (count of OCR rows)
      - SCALAR_ATTR ``ocr_chars`` (sum of text lengths)
      - SCALAR_ATTR ``zone_count`` (layout zones with labels)
      - SCALAR_ATTR ``visual_mass`` / ``visual_surprise`` (derived signals)
      - TOKEN_ATTR ``zone_labels.<zone>`` and ``ocr_rows[i].zone``
    """
    tokens: list[OrganToken] = []
    ocr_rows = row.get("ocr_rows") or []
    ocr_chars = 0
    if isinstance(ocr_rows, list):
        for i, r in enumerate(ocr_rows[:16]):  # cap at 16 OCR rows
            if not isinstance(r, dict):
                continue
            text = str(r.get("text") or "").strip()
            if not text:
                continue
            ocr_chars += len(text)
            zone = _ocr_zone(r)
            tokens.append(OrganToken(
                type=TT_TOKEN, organ=organ, value=zone, ts=ts,
                field=f"ocr_rows[{i}].zone",
            ))
            if "confidence" in r:
                try:
                    tokens.append(OrganToken(
                        type=TT_SCALAR, organ=organ,
                        value=float(r.get("confidence") or 0.0), ts=ts,
                        field=f"ocr_rows[{i}].confidence",
                    ))
                except (TypeError, ValueError):
                    pass
            for chunk in _chunk_text(text, max_general_token_len):
                tokens.append(OrganToken(
                    type=TT_GENERAL, organ=organ, value=chunk, ts=ts,
                    field=f"ocr_rows[{i}].text",
                ))
        tokens.append(OrganToken(
            type=TT_SCALAR, organ=organ, value=float(len(ocr_rows)),
            ts=ts, field="ocr_rows_count",
        ))
        tokens.append(OrganToken(
            type=TT_SCALAR, organ=organ, value=float(ocr_chars),
            ts=ts, field="ocr_chars",
        ))
    zone_labels = row.get("zone_labels") or {}
    zone_count = _visual_zone_count(zone_labels)
    tokens.append(OrganToken(
        type=TT_SCALAR, organ=organ, value=float(zone_count),
        ts=ts, field="zone_count",
    ))
    if isinstance(zone_labels, dict):
        for zone in ("left", "middle", "right"):
            labels = zone_labels.get(zone) or []
            if not isinstance(labels, list):
                continue
            for label in labels[:8]:
                tokens.append(OrganToken(
                    type=TT_TOKEN, organ=organ, value=str(label), ts=ts,
                    field=f"zone_labels.{zone}",
                ))
    # Always emit visual_mass — even a metadata-only receipt has a value.
    tokens.append(OrganToken(
        type=TT_SCALAR, organ=organ,
        value=attachment_visual_mass(row), ts=ts, field="visual_mass",
    ))
    tokens.append(OrganToken(
        type=TT_SCALAR, organ=organ,
        value=attachment_visual_surprise(row), ts=ts, field="visual_surprise",
    ))
    return tokens


def row_to_tokens(
    row: dict[str, Any],
    organ: str,
    *,
    now: Optional[float] = None,
    max_general_token_len: int = 80,
) -> list[OrganToken]:
    """Render a single receipt dict as a list of typed tokens.

    Order of tokens: ORGAN_TYPE → TIME_TAG → (TOKEN_ATTR | SCALAR_ATTR
    | GENERAL_TOKEN)* drawn from the row's fields in sorted key order.
    For organ=VISUAL_ATTACH, ``ocr_rows`` is skipped from the generic loop
    and re-emitted via ``_visual_attach_extra_tokens`` along with derived
    SCALAR_ATTR signals (ocr_chars, ocr_rows_count, visual_mass).
    """
    if not isinstance(row, dict):
        return []
    ts_raw = row.get("ts") or row.get("timestamp") or 0.0
    try:
        ts = float(ts_raw) if isinstance(ts_raw, (int, float, str)) else 0.0
    except (TypeError, ValueError):
        ts = 0.0
    visual_attach = (organ == VISUAL_ATTACH_ORGAN)
    tokens: list[OrganToken] = []
    # ORGAN_TYPE first
    tokens.append(OrganToken(
        type=TT_ORGAN, organ=organ, value=organ, ts=ts, field="_organ",
    ))
    # TIME_TAG second
    tokens.append(OrganToken(
        type=TT_TIME, organ=organ, value=time_bucket(ts, now=now),
        ts=ts, field="_time",
    ))
    # Then field tokens in deterministic order.
    for key in sorted(row.keys()):
        if key in SKIP_KEYS:
            continue
        # VISUAL_ATTACH: these are enriched specially below.
        if visual_attach and key in {"ocr_rows", "zone_labels"}:
            continue
        if key in ("ts", "timestamp"):
            # Already encoded via TIME_TAG; also emit absolute ts as scalar
            try:
                tokens.append(OrganToken(
                    type=TT_SCALAR, organ=organ,
                    value=float(row[key]), ts=ts, field=key,
                ))
            except Exception:
                pass
            continue
        value = row[key]
        # Nested dicts: flatten one level into key.subkey tokens
        if isinstance(value, dict):
            for subkey in sorted(value.keys()):
                sub = value[subkey]
                tokens.extend(
                    _atomic_to_tokens(
                        f"{key}.{subkey}", sub, organ, ts,
                        max_general_token_len=max_general_token_len,
                    )
                )
            continue
        # Lists of scalars: emit each as SCALAR_ATTR if numeric
        if isinstance(value, list):
            for i, sub in enumerate(value[:8]):  # cap at 8 to bound size
                tokens.extend(
                    _atomic_to_tokens(
                        f"{key}[{i}]", sub, organ, ts,
                        max_general_token_len=max_general_token_len,
                    )
                )
            continue
        tokens.extend(
            _atomic_to_tokens(
                key, value, organ, ts,
                max_general_token_len=max_general_token_len,
            )
        )
    # VISUAL_ATTACH: bounded OCR text + derived scalars (visual_mass etc.)
    if visual_attach:
        tokens.extend(_visual_attach_extra_tokens(
            row, organ, ts,
            max_general_token_len=max_general_token_len,
        ))
    return tokens


def _atomic_to_tokens(
    key: str, value: Any, organ: str, ts: float,
    *, max_general_token_len: int,
) -> list[OrganToken]:
    """Classify a single (key, atomic value) pair into 0+ tokens."""
    # Numeric → SCALAR_ATTR
    if isinstance(value, bool):
        # bool is a special case — render as TOKEN_ATTR
        return [OrganToken(
            type=TT_TOKEN, organ=organ, value=f"{key}={value}",
            ts=ts, field=key,
        )]
    if isinstance(value, (int, float)):
        try:
            return [OrganToken(
                type=TT_SCALAR, organ=organ, value=float(value),
                ts=ts, field=key,
            )]
        except Exception:
            return []
    if value is None:
        return []
    # String — depends on key
    if isinstance(value, str):
        if key in TOKEN_ATTR_KEYS:
            return [OrganToken(
                type=TT_TOKEN, organ=organ, value=value,
                ts=ts, field=key,
            )]
        # Long strings or general-token-keyed strings → GENERAL_TOKEN,
        # possibly chunked
        if key in GENERAL_TOKEN_KEYS or len(value) > 32:
            chunks = _chunk_text(value, max_general_token_len)
            return [
                OrganToken(
                    type=TT_GENERAL, organ=organ, value=chunk,
                    ts=ts, field=key,
                )
                for chunk in chunks
            ]
        # Short string with unknown key — treat as TOKEN_ATTR
        return [OrganToken(
            type=TT_TOKEN, organ=organ, value=value,
            ts=ts, field=key,
        )]
    # Unknown type → str()
    return [OrganToken(
        type=TT_GENERAL, organ=organ, value=str(value)[:max_general_token_len],
        ts=ts, field=key,
    )]


def _chunk_text(text: str, max_len: int) -> list[str]:
    """Split text into chunks of at most max_len chars, on word boundaries."""
    text = text.strip()
    if len(text) <= max_len:
        return [text] if text else []
    chunks: list[str] = []
    words = text.split()
    cur = ""
    for w in words:
        if len(cur) + 1 + len(w) > max_len:
            if cur:
                chunks.append(cur)
            cur = w[:max_len]
        else:
            cur = (cur + " " + w) if cur else w
    if cur:
        chunks.append(cur)
    return chunks


# ──────────────────────────────────────────────────────────────────────
# Ledger sampler
# ──────────────────────────────────────────────────────────────────────

def tokenize_ledger(
    path: str | Path,
    *,
    last_n: int = 20,
    now: Optional[float] = None,
) -> list[OrganToken]:
    """Read the last N receipts from a ledger and tokenize them."""
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return []
    organ = organ_for_ledger(p)
    # Cheap last-N: read all lines (most SIFTA jsonl ledgers fit in mem).
    # For large ledgers we tail-read with seek + read backwards.
    if p.stat().st_size > 50 * 1024 * 1024:
        lines = _tail_lines(p, last_n)
    else:
        with p.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-last_n:]
    tokens: list[OrganToken] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        tokens.extend(row_to_tokens(row, organ, now=now))
    return tokens


def _tail_lines(path: Path, last_n: int) -> list[str]:
    """Memory-efficient tail of the last N lines of a file."""
    if last_n <= 0:
        return []
    block = 4096
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        lines: list[bytes] = []
        buf = b""
        while size > 0 and len(lines) <= last_n:
            read = min(block, size)
            size -= read
            f.seek(size)
            chunk = f.read(read)
            buf = chunk + buf
            parts = buf.split(b"\n")
            # Keep the leading partial fragment for the next iteration
            buf = parts[0]
            lines = parts[1:] + lines
            if size == 0 and buf:
                lines = [buf] + lines
        tail = lines[-last_n:]
        return [b.decode("utf-8", errors="replace") for b in tail if b]


def tokenize_recent(
    state_root: str | Path | None = None,
    *,
    ledgers: Optional[list[str]] = None,
    last_n_per_ledger: int = 15,
    now: Optional[float] = None,
) -> list[OrganToken]:
    """Read the last N receipts from each ledger and stitch them into
    one chronologically-sorted token stream.

    Default ledger set: the 12 most architecturally salient organ
    ledgers (see DEFAULT_LEDGERS). Pass `ledgers=[...]` to override.
    """
    state = Path(state_root) if state_root else _STATE
    if ledgers is None:
        ledgers = list(DEFAULT_LEDGERS)
    all_tokens: list[OrganToken] = []
    for name in ledgers:
        path = state / name
        all_tokens.extend(
            tokenize_ledger(path, last_n=last_n_per_ledger, now=now)
        )
    # Sort by ts ascending so the stream is chronological — older first.
    all_tokens.sort(key=lambda t: (t.ts, t.field))
    return all_tokens


DEFAULT_LEDGERS = (
    "alice_first_person_journal.jsonl",
    "attachment_dynamics_receipts.jsonl",
    "higgs_stigmergic_demo_path_receipts.jsonl",
    "ide_stigmergic_trace.jsonl",
    "work_receipts.jsonl",
    "alice_conversation.jsonl",
    "endocrine_glands.jsonl",
    "stgm_memory_rewards.jsonl",
    "wallpaper_changes.jsonl",
    "stigtime_log.jsonl",
    "syrinx_classifications.jsonl",
    "app_focus.jsonl",
    # 2026-05-14 Cowork: pull attachment vision lane into the unified stream
    # so visual evidence flows through the same tokenizer as everything else.
    "attachment_vision_lane.jsonl",
)


# ──────────────────────────────────────────────────────────────────────
# Receipt
# ──────────────────────────────────────────────────────────────────────

def summarize_tokens(tokens: list[OrganToken]) -> dict[str, Any]:
    """Aggregate counts by type and organ — receipt-friendly summary."""
    by_type: dict[str, int] = {}
    by_organ: dict[str, int] = {}
    for tok in tokens:
        by_type[tok.type] = by_type.get(tok.type, 0) + 1
        by_organ[tok.organ] = by_organ.get(tok.organ, 0) + 1
    return {
        "n_tokens": len(tokens),
        "tokens_by_type": dict(sorted(by_type.items())),
        "tokens_by_organ": dict(sorted(by_organ.items(), key=lambda kv: -kv[1])),
        "n_organs_seen": len(by_organ),
    }


def run_organ_tokenizer(
    state_root: str | Path | None = None,
    *,
    ledgers: Optional[list[str]] = None,
    last_n_per_ledger: int = 15,
    now: Optional[float] = None,
    write: bool = True,
) -> dict[str, Any]:
    """Tokenize recent organ receipts, summarize, and write a signed
    receipt. Returns the receipt payload."""
    tokens = tokenize_recent(
        state_root=state_root,
        ledgers=ledgers,
        last_n_per_ledger=last_n_per_ledger,
        now=now,
    )
    summary = summarize_tokens(tokens)
    preview = [t.to_dict() for t in tokens[:24]]  # first 24 tokens for the receipt
    result = {
        "truth_label": TRUTH_LABEL,
        "truth_class": "OPERATIONAL+ARCHITECT_DOCTRINE",
        "truth_boundary": TRUTH_BOUNDARY,
        "assimilation_note": (
            "SIFTA analogue of the biomed.omics multi-align paper's "
            "Panel B Structured Universal Prompt. Organ receipts → "
            "typed token stream (ORGAN_TYPE, SCALAR_ATTR, TOKEN_ATTR, "
            "GENERAL_TOKEN, TIME_TAG). No training, no learned "
            "embeddings — just the representation layer."
        ),
        "config": {
            "ledgers_consulted": (
                list(ledgers) if ledgers is not None else list(DEFAULT_LEDGERS)
            ),
            "last_n_per_ledger": last_n_per_ledger,
        },
        **summary,
        "preview_first_24_tokens": preview,
    }
    if write:
        write_tokenizer_receipt(result, state_root=state_root)
    return result


def write_tokenizer_receipt(
    result: dict[str, Any],
    *,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    state = Path(state_root) if state_root else _STATE
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "MULTI_ALIGN_ORGAN_TOKENIZER",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "truth_class": "OPERATIONAL+ARCHITECT_DOCTRINE",
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def write_attachment_visual_token_receipt(
    attachment_row: dict[str, Any],
    *,
    state_root: str | Path | None = None,
    now: Optional[float] = None,
) -> dict[str, Any]:
    """Write the attachment-vision row as a signed typed-token receipt.

    This is the one-step bridge for the vision stack:
    attachment evidence receipt → visual typed tokens → swimmer-readable ledger.
    """
    state = Path(state_root) if state_root else _STATE
    state.mkdir(parents=True, exist_ok=True)
    ts = float(now if now is not None else time.time())
    tokens = row_to_tokens(attachment_row, VISUAL_ATTACH_ORGAN, now=ts)
    payload = {
        "truth_label": ATTACHMENT_VISUAL_TRUTH_LABEL,
        "truth_class": "OPERATIONAL+HYPOTHESIS",
        "truth_boundary": ATTACHMENT_VISUAL_TRUTH_BOUNDARY,
        "source_schema": attachment_row.get("schema"),
        "source_trace_id": attachment_row.get("trace_id"),
        "source_sha12": str(attachment_row.get("sha256") or "")[:12],
        "visual_mass": attachment_visual_mass(attachment_row),
        "visual_surprise": attachment_visual_surprise(attachment_row),
        "token_count": len(tokens),
        "tokens": [t.to_dict() for t in tokens],
    }
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    row = {
        "schema": "SIFTA_ATTACHMENT_VISUAL_TOKENS_RECEIPT_V1",
        "ts": ts,
        "kind": "ATTACHMENT_VISUAL_TOKENS",
        "trace_id": str(uuid.uuid4()),
        "truth_label": ATTACHMENT_VISUAL_TRUTH_LABEL,
        "truth_class": "OPERATIONAL+HYPOTHESIS",
        "truth_boundary": ATTACHMENT_VISUAL_TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        "payload": payload,
    }
    with (state / ATTACHMENT_VISUAL_TOKEN_LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


# ──────────────────────────────────────────────────────────────────────
# CLI — small previewer
# ──────────────────────────────────────────────────────────────────────

def _format_token(tok: OrganToken) -> str:
    return f"[{tok.type[:3]}|{tok.organ}|{tok.field}={tok.value!r}]"


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--last-n", type=int, default=10)
    p.add_argument("--show", type=int, default=40)
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()
    r = run_organ_tokenizer(
        last_n_per_ledger=args.last_n, write=not args.no_write,
    )
    print(f"truth_label: {r['truth_label']}")
    print(f"n_tokens:    {r['n_tokens']}")
    print(f"n_organs:    {r['n_organs_seen']}")
    print(f"by_type:     {r['tokens_by_type']}")
    print(f"by_organ:    {r['tokens_by_organ']}")
    print(f"\nfirst {args.show} tokens of the unified stream:")
    for tok_dict in r["preview_first_24_tokens"][: args.show]:
        tok = OrganToken(**tok_dict)
        print("  " + _format_token(tok))
