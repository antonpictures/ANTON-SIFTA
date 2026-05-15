"""Tests for swarm_residue_federation.

Pins the invariants the architect cared about (2026-05-14):

  - Pattern + substrate_sha + node serial are all keyed and signed.
  - Quorum (3 distinct silicon serials on same substrate) flips
    HYPOTHESIS → OPERATIONAL.
  - A node on a DIFFERENT substrate cannot trigger promotion (species
    boundary).
  - Local activation returns only rows matching the local substrate.
  - HMAC fallback path is recomputable for same-node verification.
  - Signing a row twice from the same content yields the same HMAC
    (deterministic — important for federation dedup).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_residue_federation import (  # noqa: E402
    QUORUM_THRESHOLD,
    PUBLIC_LEDGER,
    STATUS_HYPOTHESIS,
    STATUS_OPERATIONAL,
    activate_for_local_substrate,
    add_local_discovery,
    compile_active_patterns,
    load_ledger,
    merge_confirmation,
    node_pseudonym,
    promote_by_quorum,
    quorum_count,
    sign_row,
    verify_row_signature,
)


# ─── helpers ─────────────────────────────────────────────────────────────


def _row(
    family_id: str = "filler_test",
    pattern: str = r"\btest\b",
    substrate_sha: str = "sha256:TEST_SUBSTRATE_A",
    substrate_family: str = "gemma4-e2b",
    status: str = STATUS_HYPOTHESIS,
    discovered_by_node: str = "node_sha256:n0",
    confirmations=None,
):
    return {
        "schema": "SIFTA_RESIDUE_FAMILY_V1",
        "family_id": family_id,
        "pattern": pattern,
        "pattern_flags": ["IGNORECASE"],
        "substrate_family": substrate_family,
        "substrate_sha": substrate_sha,
        "status": status,
        "discovered_by_node": discovered_by_node,
        "discovered_ts": "2026-05-14T17:00:00Z",
        "evidence_kind": "local_transcript_fixture",
        "confirmations": confirmations or [],
    }


# ─── add_local_discovery + signing ───────────────────────────────────────


def test_add_local_discovery_writes_signed_row(tmp_path, monkeypatch):
    """A fresh discovery lands on disk with a non-empty sig + method."""
    ledger = tmp_path / "fam.jsonl"
    # Force the substrate probe path through env so no ollama call
    monkeypatch.setenv("SIFTA_RESIDUE_SUBSTRATE_TAG", "gemma4-e2b-cortex-5.1b:latest")
    row = add_local_discovery(
        "filler_test_a", r"\bX\b",
        evidence_kind="local_transcript_fixture",
        ledger_path=ledger,
    )
    assert row["family_id"] == "filler_test_a"
    assert row["sig"]
    assert row["sig_method"] in ("ed25519", "hmac_fallback")
    on_disk = load_ledger(ledger)
    assert len(on_disk) == 1
    assert on_disk[0]["family_id"] == "filler_test_a"


def test_sign_row_is_deterministic_for_same_payload():
    row = _row()
    sig_a, _ = sign_row(row)
    sig_b, _ = sign_row(row)
    # Two signatures over the same canonical payload must match —
    # otherwise federation dedup breaks.
    assert sig_a == sig_b


def test_hmac_signature_verifies_locally():
    """HMAC fallback round-trips against the same local seed."""
    row = _row(family_id="filler_hmac_check", pattern=r"\bhmac\b")
    sig, method = sign_row(row)
    row["sig"] = sig
    row["sig_method"] = method
    # ed25519 path may or may not be present in test env; only assert
    # round-trip when we actually used the HMAC fallback.
    if method == "hmac_fallback":
        assert verify_row_signature(row) is True


def test_ed25519_signature_verifies_with_embedded_public_key_if_available():
    """Repo-root imports should still find System.crypto_keychain.

    When Ed25519 is available, the row carries a public key so an
    auditor can verify without exposing the raw silicon serial.
    """
    row = _row(family_id="filler_ed25519_check", pattern=r"\bed25519\b")
    sig, method = sign_row(row)
    row["sig"] = sig
    row["sig_method"] = method
    if method == "ed25519":
        assert "node_public_key" in row
        assert "signing_node_serial" not in row
        assert verify_row_signature(row) is True


# ─── quorum + species boundary ───────────────────────────────────────────


def test_quorum_count_requires_same_substrate_sha():
    """Three confirmations on substrate A + one on substrate B should
    NOT cross-count. Species boundary."""
    row = _row(substrate_sha="sha256:A")
    for serial in ("alpha", "bravo", "charlie"):
        merge_confirmation(
            row,
            confirming_node=node_pseudonym(serial),
            confirming_substrate_sha="sha256:A",
            sig_method="hmac_fallback",
        )
    merge_confirmation(
        row,
        confirming_node=node_pseudonym("delta"),
        confirming_substrate_sha="sha256:B",  # different species
        sig_method="hmac_fallback",
    )
    assert quorum_count(row) == 3  # delta does NOT count for substrate A


def test_quorum_promotes_when_threshold_met():
    row = _row(status=STATUS_HYPOTHESIS, substrate_sha="sha256:A")
    for serial in [f"node{i}" for i in range(QUORUM_THRESHOLD)]:
        merge_confirmation(
            row,
            confirming_node=node_pseudonym(serial),
            confirming_substrate_sha="sha256:A",
            sig_method="hmac_fallback",
        )
    promoted = promote_by_quorum([row])
    assert promoted[0]["status"] == STATUS_OPERATIONAL
    assert "promoted_ts" in promoted[0]


def test_quorum_does_not_promote_below_threshold():
    row = _row(status=STATUS_HYPOTHESIS, substrate_sha="sha256:A")
    for serial in [f"node{i}" for i in range(QUORUM_THRESHOLD - 1)]:
        merge_confirmation(
            row,
            confirming_node=node_pseudonym(serial),
            confirming_substrate_sha="sha256:A",
            sig_method="hmac_fallback",
        )
    promoted = promote_by_quorum([row])
    assert promoted[0]["status"] == STATUS_HYPOTHESIS


def test_quorum_does_not_double_count_same_node():
    """The same node confirming twice does not advance the count."""
    row = _row(status=STATUS_HYPOTHESIS, substrate_sha="sha256:A")
    for _ in range(QUORUM_THRESHOLD + 2):
        merge_confirmation(
            row,
            confirming_node=node_pseudonym("only_one_node"),
            confirming_substrate_sha="sha256:A",
            sig_method="hmac_fallback",
        )
    assert quorum_count(row) == 1


# ─── activation filter ───────────────────────────────────────────────────


def test_activate_matches_only_local_substrate_sha():
    op_match = _row(family_id="op_match",
                    substrate_sha="sha256:A",
                    status=STATUS_OPERATIONAL)
    op_other = _row(family_id="op_other",
                    substrate_sha="sha256:B",
                    status=STATUS_OPERATIONAL)
    hyp_match = _row(family_id="hyp_match",
                     substrate_sha="sha256:A",
                     status=STATUS_HYPOTHESIS)
    active = activate_for_local_substrate(
        [op_match, op_other, hyp_match],
        local_substrate_sha="sha256:A",
        local_substrate_family="gemma4-e2b",
    )
    ids = {r["family_id"] for r in active}
    assert "op_match" in ids
    assert "op_other" not in ids       # different substrate
    assert "hyp_match" not in ids       # hypothesis hidden by default


def test_activate_can_include_hypothesis_when_asked():
    hyp_match = _row(family_id="hyp_match",
                     substrate_sha="sha256:A",
                     status=STATUS_HYPOTHESIS)
    active = activate_for_local_substrate(
        [hyp_match],
        local_substrate_sha="sha256:A",
        local_substrate_family="gemma4-e2b",
        include_hypothesis=True,
    )
    assert any(r["family_id"] == "hyp_match" for r in active)


def test_retired_rows_never_activate():
    retired = _row(family_id="retired_one",
                   substrate_sha="sha256:A",
                   status="RETIRED")
    active = activate_for_local_substrate(
        [retired],
        local_substrate_sha="sha256:A",
        local_substrate_family="gemma4-e2b",
        include_hypothesis=True,
    )
    assert active == []


def test_compile_active_patterns_yields_working_regexes():
    op = _row(family_id="op_compile",
              pattern=r"\bhello\b",
              substrate_sha="sha256:A",
              status=STATUS_OPERATIONAL)
    compiled = compile_active_patterns(
        [op],
        local_substrate_sha="sha256:A",
        local_substrate_family="gemma4-e2b",
    )
    assert len(compiled) == 1
    fid, regex = compiled[0]
    assert fid == "op_compile"
    assert regex.search("say hello world") is not None
    assert regex.search("noise") is None


def test_compile_skips_malformed_patterns():
    bad = _row(family_id="op_bad",
               pattern=r"unbalanced(",
               substrate_sha="sha256:A",
               status=STATUS_OPERATIONAL)
    compiled = compile_active_patterns(
        [bad],
        local_substrate_sha="sha256:A",
        local_substrate_family="gemma4-e2b",
    )
    assert compiled == []


# ─── ledger I/O ──────────────────────────────────────────────────────────


def test_load_ledger_returns_empty_for_missing_file(tmp_path):
    assert load_ledger(tmp_path / "nope.jsonl") == []


def test_load_ledger_round_trips(tmp_path):
    p = tmp_path / "fam.jsonl"
    payload = _row(family_id="rt")
    p.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    rows = load_ledger(p)
    assert len(rows) == 1
    assert rows[0]["family_id"] == "rt"


def test_load_ledger_skips_malformed_lines(tmp_path):
    p = tmp_path / "fam.jsonl"
    p.write_text(
        json.dumps(_row(family_id="ok"), sort_keys=True) + "\n"
        "not_json_at_all\n"
        + json.dumps(_row(family_id="ok2"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rows = load_ledger(p)
    ids = [r["family_id"] for r in rows]
    assert ids == ["ok", "ok2"]


def test_public_seed_ledger_is_sanitized_and_signed():
    """The shareable seed artifact must not leak raw transcript or raw
    serial strings, and it must not carry placeholder signatures."""
    rows = load_ledger(PUBLIC_LEDGER)
    assert rows
    raw = PUBLIC_LEDGER.read_text(encoding="utf-8")
    assert "hmac_sha256:SEED" not in raw
    assert "GTH4921YP3_seed" not in raw
    assert "raw_transcript" not in raw
    assert "transcript_text" not in raw
    for row in rows:
        assert row["sig"].startswith(("ed25519:", "hmac_sha256:"))
        assert row["discovered_by_node"].startswith("node_sha256:")
        assert row["discovered_by_node"] != "node_sha256:GTH4921YP3_seed"
        assert "signing_node_serial" not in row
