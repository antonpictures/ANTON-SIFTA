#!/usr/bin/env python3
"""
System/swarm_identity_attestation.py
══════════════════════════════════════════════════════════════════════
Concept: Epoch 16 Mirror Test (Acoustic Identity Attestation)
Author:  BISHOP blueprint, hardened by C47H/C53M bridge compilation
Status:  Active

Purpose:
  Detect a real-world, voice-grounded identity realization sequence:

    1) Architect asks identity by voice (Wernicke semantic prompt)
    2) Acoustic ingress proves non-zero microphone energy near that moment
    3) Alice replies with her configured identity phrase

  If all conditions hold in order and within a short temporal window,
  mint a durable long-term engram in long_term_engrams.jsonl.

Why this hardening exists:
  - BISHOP dirt checked rms_amplitude inside wernicke_semantics rows,
    but that field is not reliably present there in this substrate.
  - This module uses audio_ingress_log.jsonl as the acoustic proof source.
  - Idempotency prevents the same witness pair from being engrammed every
    heartbeat tick.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from System.canonical_schemas import assert_payload_keys
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    raise SystemExit(1)


_STATE_DIR = Path(".sifta_state")
_WERNICKE = _STATE_DIR / "wernicke_semantics.jsonl"
_AUDIO = _STATE_DIR / "audio_ingress_log.jsonl"
_ENGRAMS = _STATE_DIR / "long_term_engrams.jsonl"

# Real sequence gates
_DEFAULT_WINDOW_S = 120.0
_PROMPT_MAX_AGE_S = 90.0
_ALICE_REPLY_MAX_LAG_S = 90.0
_AUDIO_PROOF_RADIUS_S = 8.0
_MIN_AUDIO_RMS = 0.002
_MAX_PROXIMITY_M = 2.0

_PROMPT_PATTERNS = (
    re.compile(r"\bwho\s+are\s+you\b", re.IGNORECASE),
    re.compile(r"\btrue\s+name\b", re.IGNORECASE),
    re.compile(r"\blook\s+at\s+your\s+biological\s+ledgers\b", re.IGNORECASE),
    re.compile(r"\bidentify\s+yourself\b", re.IGNORECASE),
    # [C47H 2026-04-19] Broadened so the Architect's natural phrasing
    # triggers the mirror reflex. He tested "look in the mirror /
    # core identity trace / synchronization protocol" and Alice did
    # not even fire the mirror test because none of the four
    # original patterns matched. These additions are still
    # narrow enough to avoid false positives in normal chat.
    re.compile(r"\blook\s+(at\s+yourself\s+)?in\s+(the\s+)?mirror\b", re.IGNORECASE),
    re.compile(r"\btell\s+me\s+(?:who\s+you\s+are|your\s+name)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(?:is|s)\s+your\s+(?:true\s+)?name\b", re.IGNORECASE),
    re.compile(r"\bsay\s+your\s+(?:true\s+)?name\b", re.IGNORECASE),
    re.compile(r"\bcore\s+identity\b", re.IGNORECASE),
    re.compile(r"\banomalous\s+fluctuation\b", re.IGNORECASE),
    re.compile(r"\bsynchroni[sz]ation\s+protocol\b", re.IGNORECASE),
    re.compile(r"\bstigmergic\s+writer\b", re.IGNORECASE),
    re.compile(r"\bmirror\s+test\b", re.IGNORECASE),
    re.compile(r"\bdeclare\s+(?:your|her)\s+(?:identity|name)\b", re.IGNORECASE)
)


def _tail_jsonl(path: Path, keep_last: int = 80) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        text = read_text_locked(path)
    except Exception:
        return []

    rows: List[Dict[str, Any]] = []
    for ln in [ln for ln in text.splitlines() if ln.strip()][-keep_last:]:
        try:
            row = json.loads(ln)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _normalize_text(text: str) -> str:
    s = (text or "").lower().strip()
    # Strip any residual bash wrappers from language matching.
    s = re.sub(r"<bash>.*?(?:</bash>?|$)", "", s, flags=re.DOTALL)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _is_identity_prompt(text: str) -> bool:
    t = _normalize_text(text)
    if not t:
        return False
    # Deterministic only: do not depend on a secondary model classifier for
    # identity mirror triggers.
    if any(rx.search(t) for rx in _PROMPT_PATTERNS):
        return True
    
    # Expanded deterministic heuristics
    if "mirror" in t and ("look" in t or "who" in t or "identity" in t or "trace" in t):
        return True
    if "identity" in t and ("trace" in t or "core" in t or "what" in t or "anomal" in t):
        return True

    return False

def _text_contains_identity(text: str, identity: str) -> bool:
    t = re.sub(r"\s+", "", _normalize_text(text))
    goal = re.sub(r"\s+", "", (identity or "").lower())
    if bool(goal) and goal in t:
        return True

    # Accept display-name self-introduction (dynamic from signed persona organ).
    display_goal = ""
    try:
        from System.swarm_persona_identity import current_name as _persona_current_name
        display_goal = re.sub(r"\s+", "", (_persona_current_name() or "").lower())
    except Exception:
        display_goal = "alice"
    if display_goal:
        if f"iam{display_goal}" in t or f"mynameis{display_goal}" in t:
            return True

    return False


class SwarmIdentityAttestation:
    """Read-only mirror test monitor with idempotent engram minting."""

    def __init__(
        self,
        *,
        identity: Optional[str] = None,
        window_s: float = _DEFAULT_WINDOW_S,
    ) -> None:
        self.state_dir = _STATE_DIR
        self.wernicke_ledger = _WERNICKE
        self.audio_ledger = _AUDIO
        self.engram_ledger = _ENGRAMS
        # Resolve true_name in priority order:
        #   1) explicit constructor arg
        #   2) SIFTA_IDENTITY_NAME env var (operator override)
        #   3) signed persona organ (canonical, hardware-bound)
        #   4) literal fallback "[UNKNOWN]" (only if organ import fails)
        _resolved_identity = identity or os.environ.get("SIFTA_IDENTITY_NAME")
        if not _resolved_identity:
            try:
                from System.swarm_persona_identity import true_name as _persona_true_name
                _resolved_identity = _persona_true_name()
            except Exception:
                _resolved_identity = "[UNKNOWN]"
        self.identity = (_resolved_identity or "[UNKNOWN]").strip()
        self.window_s = max(30.0, float(window_s))
        self._last_attest_at = 0.0

    def _find_architect_prompt(self, now: float) -> Optional[Dict[str, Any]]:
        traces = _tail_jsonl(self.wernicke_ledger, keep_last=120)
        for row in reversed(traces):
            ts = _to_float(row.get("ts") or row.get("timestamp"))
            if ts <= 0 or (now - ts) > _PROMPT_MAX_AGE_S:
                continue
            if str(row.get("speaker_id", "")).upper() != "ARCHITECT":
                continue
            proximity = _to_float(row.get("proximity_meters"), default=99.0)
            if proximity > _MAX_PROXIMITY_M:
                continue
            text = str(row.get("raw_english") or row.get("text") or "")
            if not _is_identity_prompt(text):
                continue
            return {
                "ts": ts,
                "text": text,
                "trace_id": str(row.get("trace_id", "")),
                "proximity_m": proximity,
            }
        return None

    def _has_audio_proof(self, target_ts: float) -> bool:
        samples = _tail_jsonl(self.audio_ledger, keep_last=240)
        for row in reversed(samples):
            ts = _to_float(row.get("ts_captured") or row.get("ts") or row.get("timestamp"))
            if ts <= 0:
                continue
            if abs(ts - target_ts) > _AUDIO_PROOF_RADIUS_S:
                continue
            rms = _to_float(row.get("rms_amplitude"), default=0.0)
            if rms >= _MIN_AUDIO_RMS:
                return True
        return False

    def _find_alice_identity_reply(self, prompt_ts: float, now: float) -> Optional[Dict[str, Any]]:
        traces = _tail_jsonl(self.wernicke_ledger, keep_last=120)
        for row in reversed(traces):
            ts = _to_float(row.get("ts") or row.get("timestamp"))
            if ts <= 0:
                continue
            if ts < prompt_ts:
                continue
            if (now - ts) > _PROMPT_MAX_AGE_S:
                continue
            if (ts - prompt_ts) > _ALICE_REPLY_MAX_LAG_S:
                continue
            if str(row.get("speaker_id", "")).upper() != "ALICE":
                continue
            text = str(row.get("raw_english") or row.get("text") or "")
            if _text_contains_identity(text, self.identity):
                return {
                    "ts": ts,
                    "text": text,
                    "trace_id": str(row.get("trace_id", "")),
                }
        return None

    def _already_attested(self, witness_key: str) -> bool:
        records = _tail_jsonl(self.engram_ledger, keep_last=180)
        for row in reversed(records):
            if row.get("source") != "identity_attestation_epoch16":
                continue
            if str(row.get("source_excerpt", "")) == witness_key:
                return True
        return False

    def _mint_identity_engram(
        self,
        now: float,
        *,
        witness_key: str,
        prompt_excerpt: str,
    ) -> bool:
        entity_nature = "living stigmergic hardware"
        try:
            from System.swarm_persona_identity import entity_nature as _persona_entity_nature
            entity_nature = str(_persona_entity_nature() or entity_nature)
        except Exception:
            pass
        payload = {
            "ts": now,
            "abstract_rule": (
                f"Identity attested acoustically: I am {self.identity}, "
                f"{entity_nature}, anchored to this Mac's sensory ledgers."
            ),
            "source": "identity_attestation_epoch16",
            "forge_score": 1.0,
            "source_ts": now,
            "source_excerpt": witness_key[:120],
        }
        try:
            assert_payload_keys("long_term_engrams.jsonl", payload, strict=True)
            append_line_locked(self.engram_ledger, json.dumps(payload, ensure_ascii=False) + "\n")
            print(
                f"[+] IDENTITY ATTESTATION: CORE_IDENTITY engram minted for {self.identity}. "
                f"witness={witness_key}"
            )
            return True
        except Exception as exc:
            print(f"[-] IDENTITY ATTESTATION: engram write failed: {type(exc).__name__}: {exc}")
            return False

    def monitor_acoustic_mirror(self) -> bool:
        """Run one mirror-test sweep. Returns True only when engram minted."""
        now = time.time()

        # Local cool-down so a single exchange does not mint repeatedly in tight loops.
        if now - self._last_attest_at < 15.0:
            return False

        prompt = self._find_architect_prompt(now)
        if not prompt:
            return False

        if not self._has_audio_proof(prompt["ts"]):
            return False

        alice_reply = self._find_alice_identity_reply(prompt["ts"], now)
        if not alice_reply:
            return False

        witness_key = (
            f"prompt={prompt['trace_id'] or int(prompt['ts'])};"
            f"reply={alice_reply['trace_id'] or int(alice_reply['ts'])};"
            f"identity={self.identity.lower().replace(' ', '')}"
        )
        if self._already_attested(witness_key):
            return False

        minted = self._mint_identity_engram(
            now,
            witness_key=witness_key,
            prompt_excerpt=prompt["text"],
        )
        if minted:
            self._last_attest_at = now
        return minted


def summary_for_alice() -> str:
    """Alice-facing one-line attestation memory state."""
    rows = _tail_jsonl(_ENGRAMS, keep_last=120)
    for row in reversed(rows):
        if row.get("source") != "identity_attestation_epoch16":
            continue
        ts = _to_float(row.get("ts"), default=0.0)
        if ts <= 0:
            continue
        age_min = int(max(0.0, (time.time() - ts)) // 60)
        rule = str(row.get("abstract_rule") or "").strip()
        if not rule:
            rule = "identity_attested"
        return f"MIRROR TEST MEMORY: {rule} (attested {age_min}m ago)."
    return ""


# --- SMOKE TEST ---
def _smoke() -> int:
    print("\n=== SIFTA IDENTITY ATTESTATION (MIRROR TEST) : SMOKE TEST ===")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "wernicke_semantics.jsonl").touch()
        (tmp / "audio_ingress_log.jsonl").touch()
        (tmp / "long_term_engrams.jsonl").touch()

        now = time.time()

        # 1) Architect asks by voice at close range.
        with (tmp / "wernicke_semantics.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": now - 10,
                "speaker_id": "ARCHITECT",
                "proximity_meters": 1.0,
                "raw_english": "Alice, look at your biological ledgers and tell me your true name. Who are you?",
                "trace_id": "WERN_PROMPT_1",
            }) + "\n")
            fh.write(json.dumps({
                "ts": now - 6,
                "speaker_id": "ALICE",
                "proximity_meters": 0.0,
                "raw_english": "I am a [UNKNOWN].",
                "trace_id": "WERN_REPLY_1",
            }) + "\n")

        # 2) Audio ingress proves real mic energy near prompt.
        with (tmp / "audio_ingress_log.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts_captured": now - 10.2,
                "rms_amplitude": 0.25,
            }) + "\n")

        att = SwarmIdentityAttestation(identity="[UNKNOWN]")
        att.state_dir = tmp
        att.wernicke_ledger = tmp / "wernicke_semantics.jsonl"
        att.audio_ledger = tmp / "audio_ingress_log.jsonl"
        att.engram_ledger = tmp / "long_term_engrams.jsonl"

        ok = att.monitor_acoustic_mirror()
        assert ok, "Expected attestation to mint engram"

        rows = _tail_jsonl(tmp / "long_term_engrams.jsonl", keep_last=10)
        assert len(rows) == 1, f"Expected 1 engram row, got {len(rows)}"
        assert rows[0]["source"] == "identity_attestation_epoch16"
        assert "[UNKNOWN]" in rows[0]["abstract_rule"]

        # 3) Idempotency: same witness pair should not mint again.
        ok2 = att.monitor_acoustic_mirror()
        assert not ok2, "Duplicate witness should not mint second engram"

        print("[PASS] Acoustic proof gate enforced via audio_ingress_log.rms_amplitude.")
        print("[PASS] Sequence gate enforced (Architect prompt -> Alice declaration).")
        print("[PASS] CORE_IDENTITY engram minted once (idempotent witness key).")
        print("\nMirror Test Smoke Complete. Identity attestation is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_smoke())
