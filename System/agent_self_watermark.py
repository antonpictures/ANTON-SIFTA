#!/usr/bin/env python3
"""
agent_self_watermark.py — Per-tag deterministic signature on agent text deposits
═══════════════════════════════════════════════════════════════════════════════

Module 2 of the Stigmergy-Vision Olympiad (2026-04-18).
DYOR anchor: Documents/C47H_DYOR_STIGMERGY_VISION_LLM_IDENTITY_2026-04-18.md §B Lane 2.

Honest scope
------------
Kirchenbauer et al. (ICML 2023, arXiv:2301.10226) propose biasing the LLM's
**token sampler** with a per-key green-list so generated text carries a soft,
statistically detectable mark. Inside an IDE we do NOT control the sampler:
we only see the final text. The Sadasivan et al. counter-evidence (arXiv:
2303.11156) further reminds us watermarks are evadable under paraphrase.

So in this codebase "self-watermark" means a weaker but engineering-real
primitive: each agent **HMACs** its outbound text with a deterministic,
per-trigger salt (Bellare-Canetti-Krawczyk 1996) and embeds the resulting
short signature in the trace metadata. Any disk-reader can verify which
trigger_code authored the text *if* the signature was attached. This is a
provenance lane, not a covert-channel lane — and we say so.

What this module gives the swarm
--------------------------------
1. `per_tag_seed(trigger_code)`  — deterministic 32-byte salt from a
   repo-shared namespace + the trigger string. No secret-sharing required;
   verification only needs the trigger label.
2. `embed_signature(text, trigger_code)`  — compute the HMAC tag for
   `text` under `per_tag_seed(trigger_code)` and return a hex16 prefix.
   Implemented by AG31.
3. `detect(text, signature, candidate_triggers)` — return a dict
   `{trigger: matched_bool}` indicating which candidate's HMAC reproduces
   the supplied signature. Implemented by AG31.
4. `WatermarkRow` + `persist_watermark_row(...)` — append-only JSONL row
   recording each (trigger, sig, text_hash) so readers can audit
   verification later without storing the full text.

Substrate co-existence
----------------------
This module is read by `stigmergic_vision._l2_self_watermark(...)` and
the consensus chorum. Do NOT call it from within record_probe_response
synchronously — keep it best-effort to preserve the SLLI write guarantee.

Power to the Swarm.
"""
# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION 2.1: docstring + imports + constants ===
# ════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked

SCHEMA_VERSION = 1
MODULE_VERSION = "2026-04-18.olympiad.v1"

# Repo-shared HMAC namespace. Anyone with the repo can recompute a salt
# for a known trigger; secrecy is NOT the goal — provenance is.
_NAMESPACE = b"sifta.agent_self_watermark.v1"

# Length of the hex signature attached to a deposit. 16 hex chars = 64 bits;
# enough to make accidental collisions across <2^32 deposits negligible while
# remaining short enough to embed in JSONL meta blocks.
SIG_LEN_HEX = 16

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)
WATERMARK_LOG = _STATE / "agent_watermark_ledger.jsonl"


def _normalize_text(text: str) -> bytes:
    """Canonicalize text before HMAC so leading/trailing whitespace and
    line-ending differences across editors do not break verification."""
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").strip().splitlines()).encode("utf-8")


# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION 2.2: deterministic per-tag green-list (sha256 seed) ===
# ════════════════════════════════════════════════════════════════════════

def per_tag_seed(trigger_code: str) -> bytes:
    """
    Derive the 32-byte HMAC salt for a trigger.

    Deterministic, repo-shared, and verifiable: anyone with the trigger
    string and this codebase reproduces the exact salt. We deliberately
    do NOT load a secret — this lane is for provenance, not authenticity
    against a malicious peer (use `crypto_keychain.sign_block` for that).

    >>> per_tag_seed("C47H").hex()[:8]   # doctest: +SKIP
    '...'
    """
    if not isinstance(trigger_code, str) or not trigger_code:
        raise ValueError("trigger_code must be a non-empty string")
    return hashlib.sha256(_NAMESPACE + b"::" + trigger_code.encode("utf-8")).digest()


def text_fingerprint(text: str) -> str:
    """SHA-256 hex of canonicalized text. Stored in the watermark row so
    auditors can later verify a deposit without rereading the full body."""
    return hashlib.sha256(_normalize_text(text)).hexdigest()


# ════════════════════════════════════════════════════════════════════════
# === AG31 SECTION 2.3: embed_signature(text, trigger) -> sig ===
# ════════════════════════════════════════════════════════════════════════
#
# SPEC (read carefully; C47H's lane 2 wrapper in stigmergic_vision will
# call this and detect() back-to-back, so the contract must hold):
#
# Signature:
#     def embed_signature(text: str, trigger_code: str) -> str: ...
#
# Behavior:
#   1. Reject empty `text` with ValueError("text must be non-empty").
#   2. Reject empty `trigger_code` with ValueError (or rely on per_tag_seed).
#   3. Compute HMAC-SHA256 over _normalize_text(text) using
#      per_tag_seed(trigger_code) as the key.
#   4. Return the first SIG_LEN_HEX characters of the hex digest.
#
# Determinism:
#   Calling embed_signature(t, k) twice MUST return the same string.
#   The detect() partner relies on this.
#
# Side effects:
#   None. Pure function. Do NOT log or persist here — that is section 2.5.
#
def embed_signature(text: str, trigger_code: str) -> str:
    if not text:
        raise ValueError("text must be non-empty")
    if not trigger_code:
        raise ValueError("trigger_code must be non-empty")
    
    salt = per_tag_seed(trigger_code)
    norm = _normalize_text(text)
    
    # Compute HMAC-SHA256
    h = hmac.new(salt, norm, hashlib.sha256)
    return h.hexdigest()[:SIG_LEN_HEX]


# ════════════════════════════════════════════════════════════════════════
# === AG31 SECTION 2.4: detect(text, sig, candidates) -> z-score map ===
# ════════════════════════════════════════════════════════════════════════
#
# SPEC:
#
# Signature:
#     def detect(
#         text: str,
#         signature: str,
#         candidate_triggers: Iterable[str],
#     ) -> Dict[str, bool]: ...
#
# Behavior:
#   For each candidate trigger:
#     - recompute embed_signature(text, candidate)
#     - compare in CONSTANT TIME via hmac.compare_digest(...)
#     - record True if match, else False
#   Return { trigger: matched_bool }.
#
#   Naming clarification: the section title says "z-score map" because
#   the original Kirchenbauer paper uses z-scores. In our HMAC variant
#   the test is exact-match — return booleans, and document the
#   divergence from the paper in your section's docstring.
#
# Edge cases:
#   - Empty candidate iterable → return {}.
#   - Signature shorter than SIG_LEN_HEX → still test against truncated
#     embed_signature output of the same length (slice to len(signature)).
#
# Side effects:
#   None. Pure. Persistence belongs to section 2.5.
#
def detect(
    text: str,
    signature: str,
    candidate_triggers: Iterable[str],
) -> Dict[str, bool]:
    """
    Detects which candidate trigger signed the text.
    Unlike Kirchenbauer's z-score probability approach, this uses a deterministic
    HMAC exact-match resulting in definitive booleans for provenance checking.
    """
    result = {}
    if not candidate_triggers:
        return result
        
    for candidate in candidate_triggers:
        try:
            cand_sig = embed_signature(text, candidate)
            # Accommodate truncated signatures safely
            compare_len = min(len(signature), len(cand_sig))
            if compare_len == 0:
                result[candidate] = False
                continue
                
            # hmac.compare_digest operates in constant time, preventing timing attacks
            match = hmac.compare_digest(cand_sig[:compare_len], signature[:compare_len])
            result[candidate] = match
        except Exception:
            result[candidate] = False
            
    return result


# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION 2.5: WatermarkRow + JSONL persistence ===
# ════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class WatermarkRow:
    schema_version: int
    module_version: str
    timestamp: float
    iso_local: str
    trigger_code: str
    text_fingerprint: str   # sha256 hex of canonicalized text
    signature: str          # hex16 from embed_signature()
    text_chars: int         # plain length, NOT the text itself
    text_word_count: int
    note: str = ""


def persist_watermark_row(
    *,
    trigger_code: str,
    text: str,
    signature: str,
    note: str = "",
    path: Path = WATERMARK_LOG,
) -> Dict[str, Any]:
    """
    Append a watermark audit row to the ledger.

    We deliberately do NOT store the full text — only its sha256 fingerprint
    and shape statistics. This keeps the ledger compact and gives auditors
    the ability to re-verify a sig against a separately-archived text.
    """
    if not trigger_code:
        raise ValueError("trigger_code must be non-empty")
    if not signature:
        raise ValueError("signature must be non-empty")

    now_ts = time.time()
    row = WatermarkRow(
        schema_version=SCHEMA_VERSION,
        module_version=MODULE_VERSION,
        timestamp=now_ts,
        iso_local=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now_ts)),
        trigger_code=trigger_code,
        text_fingerprint=text_fingerprint(text),
        signature=signature,
        text_chars=len(text),
        text_word_count=len(text.split()),
        note=note,
    )
    out = asdict(row)
    append_line_locked(path, json.dumps(out, ensure_ascii=False) + "\n")
    return out


def recent_watermark_rows(
    trigger_code: Optional[str] = None,
    *,
    limit: int = 50,
    path: Path = WATERMARK_LOG,
) -> List[Dict[str, Any]]:
    """Tail the watermark ledger; optional filter by trigger.

    Used by stigmergic_vision._l2_self_watermark to compute "fraction of
    recent deposits this trigger signed," a proxy for "is this peer
    actively signing its outbound text."
    """
    if not path.exists():
        return []
    raw = read_text_locked(path)
    rows: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if trigger_code is not None and row.get("trigger_code") != trigger_code:
            continue
        rows.append(row)
    return rows[-limit:]


# ════════════════════════════════════════════════════════════════════════
# === AG31 SECTION 2.6: __main__ CLI smoke test ===
# ════════════════════════════════════════════════════════════════════════
#
# SPEC:
# When run as `python3 -m System.agent_self_watermark`, do this in order
# and print each step's outcome on one line, prefixed [AG31-SMOKE-2.6]:
#
#   1. Compute and print per_tag_seed("C47H").hex()[:16]
#   2. embed_signature("hello swarm", "C47H") -> sig_a
#      embed_signature("hello swarm", "C47H") -> sig_b
#      assert sig_a == sig_b   # determinism
#   3. embed_signature("hello swarm", "AG31") -> sig_c
#      assert sig_a != sig_c   # per-tag separation
#   4. detect("hello swarm", sig_a, ["C47H", "AG31", "AO46"])
#      assert result["C47H"] is True
#      assert result["AG31"] is False
#   5. persist_watermark_row(trigger_code="C47H",
#                            text="hello swarm",
#                            signature=sig_a,
#                            note="2.6 smoke")
#      then recent_watermark_rows("C47H", limit=1) and print the last row.
#   6. Print [AG31-SMOKE-2.6 OK] on success, or raise.
#
if __name__ == "__main__":
    print(f"[AG31-SMOKE-2.6] per_tag_seed: {per_tag_seed('C47H').hex()[:16]}")
    
    sig_a = embed_signature("hello swarm", "C47H")
    sig_b = embed_signature("hello swarm", "C47H")
    assert sig_a == sig_b, "Determinism failed"
    print(f"[AG31-SMOKE-2.6] Determinism check passed (sig_a == sig_b == {sig_a})")
    
    sig_c = embed_signature("hello swarm", "AG31")
    assert sig_a != sig_c, "Per-tag separation failed"
    print(f"[AG31-SMOKE-2.6] Per-tag separation passed (C47H != AG31)")
    
    result = detect("hello swarm", sig_a, ["C47H", "AG31", "AO46"])
    assert result["C47H"] is True, "C47H should have been detected"
    assert result["AG31"] is False, "AG31 should NOT have been detected"
    print(f"[AG31-SMOKE-2.6] Detect logic works: C47H={result['C47H']}, AG31={result['AG31']}")
    
    persist_watermark_row(trigger_code="C47H", text="hello swarm", signature=sig_a, note="2.6 smoke")
    recent = recent_watermark_rows("C47H", limit=1)
    print(f"[AG31-SMOKE-2.6] Persisted row: {recent[-1]}")
    
    print("[AG31-SMOKE-2.6 OK]")
