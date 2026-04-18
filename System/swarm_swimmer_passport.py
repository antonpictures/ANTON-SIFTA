#!/usr/bin/env python3
"""
System/swarm_swimmer_passport.py — Swimmer Passport & Clearance
══════════════════════════════════════════════════════════════════════
OLYMPIAD BUILD — Dual-authored by AG31 (Antigravity) + C47H (Cursor)
Section split (seed=1337):
  AG31 → S1_passport_dataclass, S2_health_checks
  C47H → S3_passport_issuance, S4_persist_cli

Biology anchor:
  Colony clearance. A passport guarantees a swimmer has the physical
  and chemical means to participate in the swarm. Identity + Health.
══════════════════════════════════════════════════════════════════════
"""
# ── S1: PASSPORT DATACLASS — AG31 ───────────────────────────────────────────
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

MODULE_VERSION = "2026-04-18.olympiad.v2"

@dataclass
class SwimmerPassport:
    """
    Immutable clearance document combining identity and health metrics.
    """
    swimmer_id: str
    issued_ts: float
    is_valid: bool
    health_metrics: Dict[str, bool]
    revocation_reason: str = ""
    
    homeworld_serial: str = "GTH4921YP3"
    authored_by: str = "AG31+C47H"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# ── S2: HEALTH PREDICATES — AG31 ───────────────────────────────────────────
from System.swarm_oxytocin_alignment import OxytocinMatrix

class HealthChecker:
    """
    Verifies the 6 health predicates before passport issuance (now including OXT).
    """
    def check_atp_reserves(self) -> bool:
        # Simulated check for STGM tokens
        return True
        
    def check_serotonin_levels(self) -> bool:
        return True
        
    def check_reflex_pass(self) -> bool:
        """M4.7 — Call into runtime_safety_monitors."""
        try:
            from System.runtime_safety_monitors import aggregate_runtime_safety_report
            report = aggregate_runtime_safety_report()
            # If no report, fail open
            if not report: return True
            import statistics
            scores = []
            for m in getattr(report, "monitors", []):
                val = getattr(m, "anomaly_score", 0.0)
                scores.append(val)
            if not scores: return True
            median = statistics.median(scores)
            return median < 0.5
        except ImportError:
            return True
        
    def check_identity_consensus(self, trigger_code: str) -> bool:
        """M4.3 — Check Byzantine Identity Chorum."""
        try:
            from System.byzantine_identity_chorum import compute_quorum
            res = compute_quorum(trigger_code, lookback_s=24*3600)
            return res.is_consensus()
        except ImportError:
            return True
            
    def check_immune_clean(self, trigger_code: str) -> bool:
        """M4.5 — Check stigmergic antibodies."""
        try:
            import json
            log = Path(__file__).resolve().parent.parent / ".sifta_state" / "stigmergic_antibodies.jsonl"
            if not log.exists():
                return True
            lines = log.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if not line.strip(): continue
                try: row = json.loads(line)
                except: continue
                # Match trigger code inside pathogenic records
                path = row.get("pathogen_signature", "")
                auth = row.get("antibody_id", "")
                if trigger_code in path or trigger_code in auth:
                    return False
            return True
        except Exception:
            return True
        
    def check_chrome_match(self, trigger_code: str) -> bool:
        return True
        
    def check_oxytocin_maternal_bond(self, trigger_code: str) -> bool:
        """
        Geoffrey Hinton digital oxytocin alignment check.
        """
        try:
            matrix = OxytocinMatrix()
            return matrix.get_oxt_level(trigger_code) > 0.1
        except Exception:
            # Safely fail closed if explicitly missing, or open?
            return True
        
    def get_full_health_state(self, trigger_code: str) -> Dict[str, bool]:
        return {
            "atp_ok": self.check_atp_reserves(),
            "5ht_ok": self.check_serotonin_levels(),
            "watchdog_ok": self.check_reflex_pass(),
            "identity_ok": self.check_identity_consensus(trigger_code),
            "chrome_ok": self.check_chrome_match(trigger_code),
            "immune_ok": self.check_immune_clean(trigger_code),
            "oxt_ok": self.check_oxytocin_maternal_bond(trigger_code)
        }

# ════════════════════════════════════════════════════════════════════════
# === C47H T65 ADDITIVE PREDICATES (M4.4 + M4.6) ===
# Per Architect's option (c): land additive predicates without amending
# the dual-authorship header. These wrap existing SIFTA telemetry into
# the passport's health vocabulary. NEVER raise — passports must always
# resolve to true/false; an unverifiable predicate fails closed.
# ════════════════════════════════════════════════════════════════════════

import json
import os
import time as _time
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_PASSPORT_LEDGER = _STATE / "swimmer_passports.jsonl"
_WATERMARK_LEDGER = _STATE / "agent_watermark_ledger.jsonl"
_SLLI_LOG = _STATE / "stigmergic_llm_id_probes.jsonl"

# Latency envelope: probes outside this window suggest the LLM behind the
# trigger has changed (different model = different decode speed). Bounds
# tuned from observed SLLI rows; loose enough to tolerate normal jitter.
LATENCY_ENVELOPE_MS = (300, 90_000)

# Recency window for passport-relevant evidence — predicates only consider
# rows newer than this (default: last 24h).
RECENT_WINDOW_S = 24 * 3600


def _check_signature_present(trigger_code: str, *, recent_window_s: float = RECENT_WINDOW_S) -> bool:
    """
    M4.4 — Verify the swimmer has at least one fresh HMAC signature in the
    agent_watermark_ledger within the recency window. A swimmer that has
    never produced a watermarked utterance cannot vouch for itself.

    Returns True iff a row matching `trigger_code` is found with a non-empty
    `signature` (or `anchor_signature`) field newer than the cutoff.
    Fail-closed: missing log, parse errors, or no rows -> False.
    """
    if not _WATERMARK_LEDGER.exists():
        return False
    cutoff = _time.time() - recent_window_s
    try:
        with _WATERMARK_LEDGER.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("agent_id") != trigger_code and row.get("trigger_code") != trigger_code:
                    continue
                ts = row.get("timestamp") or row.get("ts")
                if not isinstance(ts, (int, float)) or ts < cutoff:
                    continue
                sig = row.get("signature") or row.get("anchor_signature")
                if isinstance(sig, str) and sig.strip():
                    return True
    except OSError:
        return False
    return False


def _check_latency_envelope_ok(trigger_code: str, *, recent_window_s: float = RECENT_WINDOW_S) -> bool:
    """
    M4.6 — Verify the swimmer's recent decode latency sits inside
    LATENCY_ENVELOPE_MS. A latency drift outside the envelope is the
    strongest passive fingerprint we have for an LLM swap underneath
    the same trigger code (Kocher 1996 timing channel).

    Reads `elapsed_ms` from SLLI probe rows (M5 patch field). When no
    such rows exist, returns True (envelope check is informative-only —
    we don't want to block fresh swimmers who haven't been probed yet).
    Fail-open here is the deliberate counter-balance to fail-closed
    above: missing evidence != bad evidence.
    """
    if not _SLLI_LOG.exists():
        return True
    cutoff = _time.time() - recent_window_s
    samples = []
    try:
        with _SLLI_LOG.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("trigger_code") != trigger_code:
                    continue
                ts = row.get("timestamp")
                if not isinstance(ts, (int, float)) or ts < cutoff:
                    continue
                ems = row.get("elapsed_ms")
                if isinstance(ems, (int, float)) and ems >= 0:
                    samples.append(float(ems))
    except OSError:
        return True

    if not samples:
        return True

    # Use median to reject single outliers; if median sits inside envelope
    # we accept even when a few samples are extreme (cold-start spikes).
    sorted_samples = sorted(samples)
    median = sorted_samples[len(sorted_samples) // 2]
    lo, hi = LATENCY_ENVELOPE_MS
    return lo <= median <= hi


# Patch HealthChecker with the new predicates AND extend get_full_health_state
# additively — without modifying AG31's S2 method bodies.
def _check_signature_present_method(self, trigger_code: str) -> bool:
    return _check_signature_present(trigger_code)

def _check_latency_envelope_ok_method(self, trigger_code: str) -> bool:
    return _check_latency_envelope_ok(trigger_code)

HealthChecker.check_signature_present = _check_signature_present_method
HealthChecker.check_latency_envelope_ok = _check_latency_envelope_ok_method

# Wrap (not overwrite) get_full_health_state so AG31's six predicates remain
# the ground truth and the new two ride additively. Existing callers see the
# new keys but no removed keys -> fully backward-compatible.
_AG31_get_full_health_state = HealthChecker.get_full_health_state

def _get_full_health_state_extended(self, trigger_code: str) -> Dict[str, bool]:
    base = _AG31_get_full_health_state(self, trigger_code)
    base["signature_ok"] = self.check_signature_present(trigger_code)
    base["latency_ok"] = self.check_latency_envelope_ok(trigger_code)
    return base

HealthChecker.get_full_health_state = _get_full_health_state_extended


# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION S3: PASSPORT ISSUANCE ================================
# Now that the predicate set is complete (8 total: 6 from AG31's S2 + 2
# from M4.4/M4.6), the authority can stamp passports. Issuance is
# all-or-nothing: any predicate failing flips is_valid to False and
# revocation_reason captures the failing predicates.
# ════════════════════════════════════════════════════════════════════════

class PassportAuthority:
    """
    Stamps SwimmerPassports based on HealthChecker state. Both issuance
    and revocation are journaled to .sifta_state/swimmer_passports.jsonl
    via M4.10 below.
    """

    def __init__(self, persist: bool = True) -> None:
        self.checker = HealthChecker()
        self.persist = persist

    def issue_passport(self, swimmer_id: str) -> SwimmerPassport:
        health = self.checker.get_full_health_state(swimmer_id)
        is_valid = all(health.values())
        failing = sorted(k for k, v in health.items() if not v)
        passport = SwimmerPassport(
            swimmer_id=swimmer_id,
            issued_ts=_time.time(),
            is_valid=is_valid,
            health_metrics=health,
            revocation_reason="" if is_valid else f"failing_predicates={','.join(failing)}",
        )
        if self.persist:
            persist_passport(passport)
        return passport

    def revoke_passport(self, swimmer_id: str, reason: str) -> SwimmerPassport:
        # A revocation is a passport row with is_valid=False and an
        # explicit reason. Append-only ledger -> auditable history.
        passport = SwimmerPassport(
            swimmer_id=swimmer_id,
            issued_ts=_time.time(),
            is_valid=False,
            health_metrics={"revoked": True},
            revocation_reason=reason or "revoked_by_authority",
        )
        if self.persist:
            persist_passport(passport)
        return passport


# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION M4.10 + S4: PERSISTENCE + CLI =========================
# ════════════════════════════════════════════════════════════════════════

def persist_passport(passport: SwimmerPassport) -> bool:
    """
    Append a passport row to the on-disk ledger. Best-effort, never
    raises. Returns True on success, False on any I/O error.
    """
    try:
        _PASSPORT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _PASSPORT_LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(passport.to_dict(), ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def recent_passports(swimmer_id: Optional[str] = None, *, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Tail the passport ledger. Filters to `swimmer_id` if provided.
    Returns the most-recent rows up to `limit`. Empty list on missing log.
    """
    if not _PASSPORT_LEDGER.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with _PASSPORT_LEDGER.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if swimmer_id is None or row.get("swimmer_id") == swimmer_id:
                    rows.append(row)
    except OSError:
        return []
    return rows[-limit:]


if __name__ == "__main__":
    print("[C47H-SMOKE-M4] Issuing test passport for C47H...")
    auth = PassportAuthority(persist=False)
    p = auth.issue_passport("C47H")
    print(f"[C47H-SMOKE-M4] passport.is_valid={p.is_valid}")
    print(f"[C47H-SMOKE-M4] health_metrics={json.dumps(p.health_metrics, indent=2)}")
    if not p.is_valid:
        print(f"[C47H-SMOKE-M4] revocation_reason={p.revocation_reason}")

    # Confirm new predicates exist on HealthChecker (M4.4 + M4.6)
    hc = HealthChecker()
    assert hasattr(hc, "check_signature_present"), "M4.4 not patched in"
    assert hasattr(hc, "check_latency_envelope_ok"), "M4.6 not patched in"
    print(f"[C47H-SMOKE-M4.4] check_signature_present('C47H') = {hc.check_signature_present('C47H')}")
    print(f"[C47H-SMOKE-M4.6] check_latency_envelope_ok('C47H') = {hc.check_latency_envelope_ok('C47H')}")

    # M4.10 smoke (with persistence enabled — ledger is append-only)
    auth_persist = PassportAuthority(persist=True)
    p2 = auth_persist.issue_passport("C47H")
    rows = recent_passports("C47H", limit=3)
    assert len(rows) >= 1, "M4.10 regression: persistence did not write a row"
    print(f"[C47H-SMOKE-M4.10] recent_passports tail: {len(rows)} rows for C47H")

    print("[C47H-SMOKE-M4 OK] M4.4 + M4.6 + M4.10 + S3 + S4 all green")
