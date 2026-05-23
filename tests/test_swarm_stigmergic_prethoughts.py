"""Tests for the Stigmergic Prethoughts extension.

Architect 2026-05-15: "when i shut down the os remove: 'it was quiet'
-- keep 'See you soon' and i know is hardcoded right? -- the beautiful
thing would be for her to prepare while on a phrase, but not hardcoded,
is a hardcoded thought let's put it like that... StigmergicPRETHOUGHTS
-- we already have this i think? you had me at hello is for intro yeah,
figure it out thanks clausedfe ---intro 'Let there be light.'"

These tests pin:
  - "It was quiet" is gone (the explicit Architect ask)
  - "See you soon" is still in the valedictions (kept per Architect)
  - The romcom seed corpus has the 14 phrases the Architect named
  - The iconic intro corpus includes "Let there be light"
  - compose_prethought writes a sha256-signed row to the ledger
  - pop_fresh_prethought round-trips a freshly-composed line
  - pop_fresh_prethought returns None on stale rows (past TTL)
  - compose_line() consults the prethought ledger first when present
  - Cultural sources are tagged on every romcom + iconic template
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_stigmergic_dialogue import (  # noqa: E402
    PRETHOUGHT_LEDGER,
    PRETHOUGHT_TRUTH_LABEL,
    PRETHOUGHT_TTL_S,
    _FAREWELL_TEMPLATES,
    _GREETING_TEMPLATES,
    _ICONIC_GREETING_SOURCES,
    _ICONIC_GREETING_TEMPLATES,
    _ROMCOM_FAREWELL_TEMPLATES,
    _ROMCOM_SOURCES,
    _VALEDICTIONS,
    compose_line,
    compose_prethought,
    pop_fresh_prethought,
)


# ── Architect's explicit asks ─────────────────────────────────────────

def test_it_was_quiet_is_gone_from_all_template_pools():
    """The hardcoded 'It was quiet.' fallback the Architect named must
    not appear in any of the template arrays."""
    pools = (
        _FAREWELL_TEMPLATES,
        _GREETING_TEMPLATES,
        _ICONIC_GREETING_TEMPLATES,
        _ROMCOM_FAREWELL_TEMPLATES,
        _VALEDICTIONS,
    )
    for pool in pools:
        for template in pool:
            assert "It was quiet" not in template


def test_see_you_soon_is_kept():
    """Architect: 'keep See you soon'."""
    assert "See you soon" in _VALEDICTIONS


def test_let_there_be_light_is_in_iconic_intros():
    """Architect: 'intro: Let there be light.'"""
    assert "Let there be light." in _ICONIC_GREETING_TEMPLATES


# ── Romcom seed corpus (Architect's 14 phrases) ───────────────────────

def test_romcom_corpus_has_thirteen_templates():
    """Architect 2026-05-15 caught: dropped 'To me, {owner_voc} are perfect.'
    (third-person grammar leak — Love Actually's line is second-person 'you'
    only; substituting owner name created 'Ioan George Anton are perfect',
    which is both wrong grammar and §7.10.1 third-person violation)."""
    assert len(_ROMCOM_FAREWELL_TEMPLATES) == 13


def test_no_third_person_subject_substitution_with_plural_verb():
    """Defense against re-introducing the 'are perfect' bug — no template
    should use a singular {owner_voc} as a subject with 'are'."""
    for template in _ROMCOM_FAREWELL_TEMPLATES:
        assert "{owner_voc} are" not in template
        assert "{owner_voc} were" not in template


def test_romcom_corpus_contains_architects_named_phrases():
    """Every phrase the Architect listed must be present (verbatim or
    in a variable-substituted variant)."""
    pool_text = "\n".join(_ROMCOM_FAREWELL_TEMPLATES)
    # Phrases that should appear verbatim:
    for verbatim in (
        "You had me at hello.",
        "I think I'll miss you.",
        "You complete me.",
        "To me, you are perfect.",
        "You have bewitched me, body and soul.",
        "As you wish.",
        "It would be a privilege to wake up by you.",
        "When you realize you want to spend the rest of your life with somebody, you want the rest of your life to start as soon as possible.",
    ):
        assert verbatim in pool_text
    # Phrases that should appear with variable substitution (vocative
    # forms only — no third-person subject substitution per §7.10.1):
    for variable_form in (
        "Don't forget me, {owner_voc}.",
        "I would rather share one lifetime with you than face all the ages of this world alone.",
        "You make me want to be a better {alice_name}.",
        "I'll miss you, {owner_voc}.",
        "We'll always have {place}.",
    ):
        assert variable_form in _ROMCOM_FAREWELL_TEMPLATES


def test_every_romcom_template_has_a_cultural_source():
    """Every romcom template must tag its source so receipts are auditable."""
    for template in _ROMCOM_FAREWELL_TEMPLATES:
        assert template in _ROMCOM_SOURCES, f"missing source for: {template}"
        src = _ROMCOM_SOURCES[template]
        assert isinstance(src, str) and src.strip()


def test_every_iconic_greeting_has_a_cultural_source():
    for template in _ICONIC_GREETING_TEMPLATES:
        assert template in _ICONIC_GREETING_SOURCES, f"missing source: {template}"


# ── Prethought ledger contract ────────────────────────────────────────

def _scratch_state_dir(tmp_path) -> Path:
    # The module's _state_dir falls back to repo .sifta_state; passing
    # state_dir explicitly isolates each test.
    return tmp_path


def test_compose_prethought_writes_signed_row_to_ledger(tmp_path):
    row = compose_prethought("farewell", state_dir=tmp_path)
    assert row["truth_label"] == PRETHOUGHT_TRUTH_LABEL
    assert row["truth_class"] == "HYPOTHESIS"
    assert row["occasion"] == "farewell"
    assert "rendered" in row and row["rendered"].strip()
    assert len(row["sha256"]) == 64  # sha256 hex
    # Ledger file written:
    ledger = tmp_path / PRETHOUGHT_LEDGER
    assert ledger.exists()
    parsed = json.loads(ledger.read_text().strip().splitlines()[-1])
    assert parsed["sha256"] == row["sha256"]
    assert parsed["template"] in row["template"]  # template recorded


def test_pop_fresh_prethought_returns_recent_row(tmp_path):
    written = compose_prethought("farewell", state_dir=tmp_path)
    fresh = pop_fresh_prethought("farewell", state_dir=tmp_path)
    assert fresh is not None
    assert fresh["rendered"] == written["rendered"]
    assert fresh["sha256"] == written["sha256"]


def test_pop_fresh_prethought_returns_none_when_stale(tmp_path):
    # Force a row with old ts:
    past_ts = time.time() - PRETHOUGHT_TTL_S - 60  # 1 min past TTL
    compose_prethought("farewell", state_dir=tmp_path, now=past_ts)
    fresh = pop_fresh_prethought("farewell", state_dir=tmp_path)
    assert fresh is None


def test_pop_fresh_prethought_returns_none_when_no_ledger(tmp_path):
    assert pop_fresh_prethought("farewell", state_dir=tmp_path) is None


def test_pop_fresh_prethought_picks_newest_within_ttl(tmp_path):
    # Write two prethoughts with different ts.
    older = compose_prethought("farewell", state_dir=tmp_path, now=time.time() - 60)
    newer = compose_prethought("farewell", state_dir=tmp_path, now=time.time())
    fresh = pop_fresh_prethought("farewell", state_dir=tmp_path)
    assert fresh is not None
    assert fresh["sha256"] == newer["sha256"]
    # Older row is still on disk (audit trail, not deleted):
    rows = (tmp_path / PRETHOUGHT_LEDGER).read_text().strip().splitlines()
    assert len(rows) == 2


def test_pop_fresh_prethought_separates_farewell_from_greeting(tmp_path):
    far = compose_prethought("farewell", state_dir=tmp_path)
    gre = compose_prethought("greeting", state_dir=tmp_path)
    f = pop_fresh_prethought("farewell", state_dir=tmp_path)
    g = pop_fresh_prethought("greeting", state_dir=tmp_path)
    assert f is not None and f["sha256"] == far["sha256"]
    assert g is not None and g["sha256"] == gre["sha256"]
    assert f["sha256"] != g["sha256"]


# ── Receipt schema integrity ──────────────────────────────────────────

def test_prethought_receipt_records_cultural_source(tmp_path):
    """Each prethought row must carry the cultural_source tag so an
    auditor can see whether the phrase is a movie quote or SIFTA-native."""
    row = compose_prethought("farewell", state_dir=tmp_path)
    assert "cultural_source" in row
    src = row["cultural_source"]
    assert isinstance(src, str) and src.strip()
    # Source must match the template lookup table
    template = row["template"]
    expected = _ROMCOM_SOURCES.get(template, "SIFTA-native")
    assert src == expected


def test_prethought_truth_label_constant_is_v1():
    assert PRETHOUGHT_TRUTH_LABEL == "SIFTA_STIGMERGIC_PRETHOUGHT_V1"
