"""Supplemental tests for the organ tokenizer's VISUAL_ATTACH extension.

Architect 2026-05-14: "Extend the organ tokenizer to treat attachments as
a proper visual entity type and emit the structured tokens + receipt in
one step." Three sub-goals from the architect's message:
  1. Attachment events become first-class typed tokens flowing into the
     unified stream so TokenSwimmers can operate on them.
  2. OCR + layout normalized into SCALAR_ATTR + TOKEN_ATTR.
  3. Lightweight "visual mass" signal so surprise sampler / swimmers
     can prioritize new visual evidence.

These tests pin those three contracts. They live in their own file so
they don't collide with the original tokenizer test suite — §8.5.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_organ_tokenizer import (  # noqa: E402
    DEFAULT_LEDGERS,
    GENERAL_TOKEN_KEYS,
    LEDGER_TO_ORGAN,
    TOKEN_ATTR_KEYS,
    TT_GENERAL,
    TT_ORGAN,
    TT_SCALAR,
    TT_TOKEN,
    VISUAL_ATTACH_ORGAN,
    attachment_visual_mass,
    organ_for_ledger,
    row_to_tokens,
)


# ── Fixture builder ──────────────────────────────────────────────────

def _va_row(
    *,
    byte_count=1_000_000,
    ocr_rows=None,
    zone_labels=None,
    image_format="png",
    ok=True,
    ts=1778754889.0,
    reply="Three IDE chat surfaces visible in screenshot.",
):
    if ocr_rows is None:
        ocr_rows = [
            {"text": "Codex IDE", "box": [10, 10, 100, 40], "confidence": 0.95},
            {"text": "Alice", "box": [200, 10, 400, 40], "confidence": 0.92},
            {"text": "Cowork", "box": [500, 10, 700, 40], "confidence": 0.94},
        ]
    if zone_labels is None:
        # Codex's schema: zone_labels[zone] is a LIST of labels.
        zone_labels = {
            "left": ["Codex"],
            "middle": ["Alice"],
            "right": ["Cowork"],
        }
    return {
        "ts": float(ts),
        "trace_id": "va-test",
        "schema": "SIFTA_ATTACHMENT_VISION_LANE_RECEIPT_V1",
        "truth_label": "ATTACHMENT_VISION_LANE_V1",
        "ok": ok,
        "image_path": "/Users/test/Screenshot.png",
        "image_format": image_format,
        "byte_count": int(byte_count),
        "width": 2600,
        "height": 726,
        "sha256": "abc123",
        "ocr_rows": ocr_rows,
        "zone_labels": zone_labels,
        "reply": reply,
        "truth_boundary": "Local attachment metadata and OCR/layout evidence only.",
    }


def _tokens_by(tokens, type_):
    return [t for t in tokens if t.type == type_]


def _scalars_by_field(tokens):
    return {t.field: t.value for t in tokens if t.type == TT_SCALAR}


def _general_by_field(tokens):
    out = {}
    for t in tokens:
        if t.type == TT_GENERAL:
            out.setdefault(t.field, []).append(t.value)
    return out


# ── Goal 1: VISUAL_ATTACH organ is canonical and discoverable ────────

def test_visual_attach_constant_is_canonical():
    assert VISUAL_ATTACH_ORGAN == "VISUAL_ATTACH"


def test_ledger_to_organ_maps_attachment_vision_lane():
    assert (
        LEDGER_TO_ORGAN["attachment_vision_lane.jsonl"]
        == VISUAL_ATTACH_ORGAN
    )


def test_organ_for_ledger_resolves_visual_attach():
    assert (
        organ_for_ledger("attachment_vision_lane.jsonl")
        == VISUAL_ATTACH_ORGAN
    )
    assert (
        organ_for_ledger(Path("/x/.sifta_state/attachment_vision_lane.jsonl"))
        == VISUAL_ATTACH_ORGAN
    )


def test_default_ledgers_includes_attachment_vision_lane():
    assert "attachment_vision_lane.jsonl" in DEFAULT_LEDGERS


def test_image_format_is_token_attr_key():
    assert "image_format" in TOKEN_ATTR_KEYS


def test_reply_and_error_are_general_token_keys():
    assert "reply" in GENERAL_TOKEN_KEYS
    assert "error" in GENERAL_TOKEN_KEYS


# ── Goal 2: OCR + layout become clean tokens ─────────────────────────

def test_ocr_text_emitted_as_general_tokens_not_dict_strings():
    """Generic fallback would stringify each ocr_rows dict noisily. Pin
    that the extension intercepts and emits text-only GENERAL_TOKENs."""
    row = _va_row()
    tokens = row_to_tokens(row, VISUAL_ATTACH_ORGAN, now=row["ts"] + 1)
    gen = _general_by_field(tokens)
    # Each row's text appears under its indexed field name
    assert "Codex IDE" in gen.get("ocr_rows[0].text", [])
    assert "Alice" in gen.get("ocr_rows[1].text", [])
    assert "Cowork" in gen.get("ocr_rows[2].text", [])
    # No GENERAL_TOKEN should be the python repr of an ocr_rows entry
    for t in tokens:
        if t.type == TT_GENERAL:
            assert "{'text':" not in t.value
            assert "'confidence':" not in t.value


def test_ocr_rows_count_and_ocr_chars_are_scalar_attrs():
    row = _va_row()
    tokens = row_to_tokens(row, VISUAL_ATTACH_ORGAN, now=row["ts"] + 1)
    scalars = _scalars_by_field(tokens)
    assert scalars["ocr_rows_count"] == 3.0
    # "Codex IDE" (9) + "Alice" (5) + "Cowork" (6) = 20
    assert scalars["ocr_chars"] == 20.0


def test_zone_labels_emit_as_token_attr_one_per_zone():
    """Codex's enrichment: each label in zone_labels[zone] (a list) emits
    its own TOKEN_ATTR keyed by zone."""
    row = _va_row()
    tokens = row_to_tokens(row, VISUAL_ATTACH_ORGAN, now=row["ts"] + 1)
    tas = [t for t in tokens if t.type == TT_TOKEN]
    zone_tokens = [t for t in tas if t.field.startswith("zone_labels.")]
    # All three zones must produce tokens
    assert {t.field for t in zone_tokens} == {
        "zone_labels.left", "zone_labels.middle", "zone_labels.right",
    }
    # And the label values themselves land in the stream
    assert {t.value for t in zone_tokens} == {"Codex", "Alice", "Cowork"}


def test_image_format_is_token_attr_in_emitted_stream():
    row = _va_row(image_format="jpeg")
    tokens = row_to_tokens(row, VISUAL_ATTACH_ORGAN, now=row["ts"] + 1)
    tas = [t for t in tokens if t.type == TT_TOKEN and t.field == "image_format"]
    assert len(tas) == 1
    assert tas[0].value == "jpeg"


def test_reply_is_general_token_not_token_attr():
    row = _va_row(reply="A long-ish paragraph that should chunk into general tokens.")
    tokens = row_to_tokens(row, VISUAL_ATTACH_ORGAN, now=row["ts"] + 1)
    reply_tokens = [t for t in tokens if t.field == "reply"]
    assert reply_tokens
    assert all(t.type == TT_GENERAL for t in reply_tokens)


def test_ocr_rows_capped_at_16_to_bound_token_count():
    """Heavy OCR shouldn't explode the token stream."""
    many = [
        {"text": f"row {i}", "box": [0, i, 100, i + 20], "confidence": 0.9}
        for i in range(50)
    ]
    row = _va_row(ocr_rows=many)
    tokens = row_to_tokens(row, VISUAL_ATTACH_ORGAN, now=row["ts"] + 1)
    gen = _general_by_field(tokens)
    # Field names ocr_rows[0..15].text should appear, but no ocr_rows[16].text
    fields = {f for f in gen.keys() if f.startswith("ocr_rows[")}
    indices = sorted(int(f[len("ocr_rows["):f.index("]")]) for f in fields)
    assert indices == list(range(16))


def test_invalid_ocr_row_does_not_crash_pairer():
    """Bad rows (non-dict, missing text) must be silently skipped."""
    bad = [
        "not a dict",
        {},                       # missing text
        {"text": ""},             # empty text
        {"text": "valid"},        # good
        None,                     # None
    ]
    row = _va_row(ocr_rows=bad)
    tokens = row_to_tokens(row, VISUAL_ATTACH_ORGAN, now=row["ts"] + 1)
    gen = _general_by_field(tokens)
    valid_field = [f for f in gen if f.endswith(".text") and "valid" in gen[f][0]]
    assert len(valid_field) == 1


# ── Goal 3: visual_mass signal ───────────────────────────────────────

def test_attachment_visual_mass_is_emitted_as_scalar():
    row = _va_row()
    tokens = row_to_tokens(row, VISUAL_ATTACH_ORGAN, now=row["ts"] + 1)
    scalars = _scalars_by_field(tokens)
    assert "visual_mass" in scalars
    assert 0.0 <= float(scalars["visual_mass"]) <= 1.0


def test_attachment_visual_mass_empty_row_is_zero():
    assert attachment_visual_mass({}) == 0.0


def test_attachment_visual_mass_in_zero_one_for_extreme_inputs():
    # Tiny
    small = attachment_visual_mass({"byte_count": 1, "ocr_rows": [], "zone_labels": {}})
    assert 0.0 <= small <= 0.01
    # Huge
    big_rows = [{"text": "x" * 1000} for _ in range(50)]
    big_zones = {f"z{i}": "x" for i in range(20)}
    huge = attachment_visual_mass({
        "byte_count": 10_000_000_000,
        "ocr_rows": big_rows,
        "zone_labels": big_zones,
    })
    assert 0.0 <= huge <= 1.0
    assert huge > 0.95  # should saturate near 1


def test_attachment_visual_mass_monotonic_in_bytes():
    base = {"byte_count": 100_000, "ocr_rows": [], "zone_labels": {}}
    bigger = dict(base, byte_count=10_000_000)
    assert attachment_visual_mass(bigger) > attachment_visual_mass(base)


def test_attachment_visual_mass_monotonic_in_ocr():
    base = {
        "byte_count": 1_000_000,
        "ocr_rows": [{"text": "short"}],
        "zone_labels": {},
    }
    bigger = dict(base)
    bigger["ocr_rows"] = [{"text": "x" * 500}] * 10
    assert attachment_visual_mass(bigger) > attachment_visual_mass(base)


def test_attachment_visual_mass_monotonic_in_zones():
    base = {
        "byte_count": 1_000_000,
        "ocr_rows": [{"text": "x" * 200}],
        "zone_labels": {"a": "x"},
    }
    bigger = dict(base, zone_labels={"a": "x", "b": "y", "c": "z", "d": "w"})
    assert attachment_visual_mass(bigger) > attachment_visual_mass(base)


def test_attachment_visual_mass_combines_three_axes_at_sensible_levels():
    """A real screenshot-shaped row should land in 0.3-0.7 — not at the
    floor, not saturated."""
    row = _va_row(
        byte_count=1_800_000,
        ocr_rows=[{"text": "x" * 30}] * 3,
        zone_labels={"left": "a", "middle": "b", "right": "c"},
    )
    vm = attachment_visual_mass(row)
    assert 0.30 <= vm <= 0.80


def test_attachment_visual_mass_handles_garbage_inputs():
    """Malformed row should fall back to 0.0 rather than crash."""
    garbage = {
        "byte_count": "not-a-number",
        "ocr_rows": "not-a-list",
        "zone_labels": ["not", "a", "dict"],
    }
    # Should be 0.0 because every axis fails to read.
    assert attachment_visual_mass(garbage) == 0.0


# ── Non-VISUAL_ATTACH organs are unaffected (no regression) ──────────

def test_non_visual_attach_organ_ignores_attachment_enrichment():
    """A non-VISUAL_ATTACH organ row even with ocr_rows-like data
    should NOT get the OCR enrichment or a visual_mass scalar."""
    row = {
        "ts": 1778754889.0,
        "trace_id": "other",
        "kind": "some_other_event",
        "ocr_rows": [{"text": "should not be re-emitted"}],
    }
    tokens = row_to_tokens(row, "WORK", now=row["ts"] + 1)
    scalars = _scalars_by_field(tokens)
    assert "visual_mass" not in scalars
    assert "ocr_rows_count" not in scalars
    assert "ocr_chars" not in scalars


# ── Stream-level: organ + time tags still come first ─────────────────

def test_organ_and_time_tags_emit_first():
    row = _va_row()
    tokens = row_to_tokens(row, VISUAL_ATTACH_ORGAN, now=row["ts"] + 1)
    assert tokens[0].type == TT_ORGAN
    assert tokens[0].value == VISUAL_ATTACH_ORGAN
    # TIME_TAG must be second
    assert tokens[1].type == "TIME_TAG"


# ── Math sanity: tanh saturation math ────────────────────────────────

def test_visual_mass_bytes_axis_saturates_via_tanh():
    """Doubling the size from saturation should add very little."""
    one_x = attachment_visual_mass({
        "byte_count": 5_000_000, "ocr_rows": [], "zone_labels": {},
    })
    two_x = attachment_visual_mass({
        "byte_count": 10_000_000, "ocr_rows": [], "zone_labels": {},
    })
    # At 5MB the bytes axis is well past saturation; doubling should add
    # very little (< 0.05 to the overall score).
    assert (two_x - one_x) < 0.05
