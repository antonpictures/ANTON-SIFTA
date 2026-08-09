#!/usr/bin/env python3
"""swarm_we_code_together_clarity.py — "why couldn't Alice act?" legibility.
Lane contract: trace (zero-surprise).

George's pain (2026-06-24): he told Alice to push a button on grok.com and send,
she couldn't, and the We Code Together monitor never explained WHY. To code her
own body, Alice (and George watching) must be able to SEE the gap: which action
the body refused, and the honest reason — not silence.

This pure-stdlib helper reads the effector gate ledger and turns refusals into
plain English, with stigtime (when) + stigtrace (receipt id). The We Code
Together app renders it as a panel. No PyQt here, so it is unit-testable.

It never fabricates a success and never raises on a missing file.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List

_DEFAULT_STATE = Path(__file__).resolve().parents[1] / ".sifta_state"

# token in the row  ->  plain-English reason Alice/George can act on
_WHY = {
    "double_spend_blocked": "no fresh owner-intent nonce — replay guard (say it again / confirm to release)",
    "stt_conf_too_low": "owner intent not confirmed — voice was too uncertain to act",
    "recovery_only": "recovery-only context — real world-spend is held back until a clean turn",
    "purchase_intent": "looked like a money/commerce action — held for explicit approval",
    "no_js_result": "could not read the page — the in-page DOM walker returned nothing (use the a11y limb)",
    "no_owner_signal": "no owner present-signal near the action — could not attribute it to George",
}

_REFUSAL_ACTIONS = {"refused", "blocked", "denied", "double_spend_blocked"}
_PLAN_FILE = Path(__file__).resolve().parents[1] / "Documents" / "WE_CODE_TOGETHER_PLAN_2026-07-07_CODEX_GROK.md"
_CANONICAL_EYE_MAX_AGE_S = 30.0


def _rows(path: Path, limit_scan: int = 4000) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit_scan:]
    except OSError:
        return []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _is_refusal(row: Dict[str, Any], blob: str) -> bool:
    if row.get("action") in _REFUSAL_ACTIONS:
        return True
    if row.get("effector_spend_allowed") is False:
        return True
    if row.get("ok") is False:
        return True
    return any(tok in blob for tok in ("double_spend_blocked", "no_js_result", "stt_conf_too_low"))


def _why(blob: str, row: Dict[str, Any]) -> str:
    for tok, plain in _WHY.items():
        if tok in blob:
            return plain
    if row.get("effector_spend_allowed") is False:
        return "world-spend not allowed in this context"
    return str(row.get("reason") or row.get("incident_class") or "blocked (reason not labeled)")[:90]


def _when(row: Dict[str, Any]) -> str:
    import datetime
    ts = row.get("ts") or row.get("bound_ts") or row.get("created")
    try:
        return datetime.datetime.fromtimestamp(float(ts)).strftime("%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return "?"


def _trace(row: Dict[str, Any]) -> str:
    t = str(row.get("receipt_id") or row.get("linked_receipt") or row.get("incident_class") or "")
    return t[:8] if t else "—"


def _what(row: Dict[str, Any]) -> str:
    eff = row.get("effector") or row.get("browser_action") or row.get("source") or "action"
    tgt = row.get("owner_text_preview") or row.get("url") or row.get("target") or ""
    tgt = str(tgt).strip().replace("\n", " ")
    return (f"{eff} — {tgt[:60]}" if tgt else str(eff))[:74]


def why_blocked_lines(limit: int = 12, state_dir: str | Path = _DEFAULT_STATE) -> List[str]:
    """Plain-English list of the body's most recent refusals + why."""
    state = Path(state_dir)
    rows = _rows(state / "effector_gate.jsonl")
    refusals: List[str] = []
    for row in reversed(rows):  # newest first
        blob = json.dumps(row, ensure_ascii=False).lower()
        if not _is_refusal(row, blob):
            continue
        refusals.append(f"✗ {_what(row)}\n    why: {_why(blob, row)}  · t={_when(row)} · trace={_trace(row)}")
        if len(refusals) >= limit:
            break
    if not refusals:
        return ["No blocked actions on record — the body acted cleanly, or no effector_gate ledger yet."]
    header = [
        "WHY ALICE COULD NOT ACT (the honest gap — fix these to push the button herself)",
        "Each line = an action the body REFUSED, and the plain reason. Silence was the old bug; this is the cure.",
        "",
    ]
    return header + refusals


def live_gate_snapshot(state_dir: str | Path = _DEFAULT_STATE) -> Dict[str, Any]:
    """Current active gate context + last refusal for live display in We Code Together."""
    state = Path(state_dir)
    ctx: Dict[str, Any] = {}
    active = state / "active_intent_nonce.json"
    if active.exists():
        try:
            ctx = json.loads(active.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass
    last_ref: Dict[str, Any] = {}
    eg = state / "effector_gate.jsonl"
    if eg.exists():
        try:
            for ln in reversed(eg.read_text(encoding="utf-8", errors="replace").splitlines()[-100:]):
                if not ln.strip():
                    continue
                try:
                    r = json.loads(ln)
                    if r.get("action") in ("refused", "recovery_bind_deferred_owner_slot_fresh") or r.get("effector_spend_allowed") is False:
                        last_ref = r
                        break
                except Exception:
                    continue
        except Exception:
            pass
    return {"active": ctx, "last_refusal": last_ref}


def input_boundary_lines(limit: int = 6, state_dir: str | Path = _DEFAULT_STATE) -> List[str]:
    """Surface the typed-vs-WORLD-STT distinction where Alice and the doctors work."""
    state = Path(state_dir)
    lines: List[str] = [
        "INPUT BOUNDARY (AGI memory): typed text is owner-authored intent; WORLD STT is a mixed acoustic sensor stream.",
        "Rule: speaker/video/room noise copied by STT is observed media unless Alice is addressed or George voice/near-field proof is present.",
    ]
    ctx_path = state / "ambient_media_context.json"
    if ctx_path.exists():
        try:
            ctx = json.loads(ctx_path.read_text(encoding="utf-8", errors="replace"))
            ts = float(ctx.get("ts") or 0.0)
            ttl = float(ctx.get("ttl_s") or 0.0)
            remaining = max(0.0, (ts + ttl) - time.time()) if ts and ttl else 0.0
            note = " ".join(str(ctx.get("note") or "").split())[:150]
            source = str(ctx.get("source") or "?")
            lines.append(f"Ambient context: source={source} ttl_left_min={remaining / 60:.1f} note={note}")
        except Exception as exc:
            lines.append(f"Ambient context: unreadable ({type(exc).__name__})")
    else:
        lines.append("Ambient context: none active on disk.")

    # r1602 VA5 — live voiceprint verdict (owner conf, media, enrollment, LOO)
    try:
        from System.swarm_voice_identity_organ import voice_verdict_snapshot

        snap = voice_verdict_snapshot(state_dir=state, ledger_path=state / "voice_identity_ledger.jsonl")
        conf = snap.get("owner_match_confidence")
        media_on = snap.get("media_context_active")
        n_owner = snap.get("primary_operator_n")
        age = snap.get("last_enrollment_age_days")
        loo_acc = snap.get("loo_accuracy")
        loo_m = snap.get("loo_min_primary_margin")
        loo_pass = snap.get("loo_passes")
        age_s = f"{age}d" if age is not None else "never"
        lines.append(
            "Voice verdict: "
            f"owner_conf={conf} media_active={media_on} "
            f"owner_exemplars={n_owner} last_enroll_age={age_s} "
            f"loo_acc={loo_acc} loo_min_margin={loo_m} loo_pass={loo_pass}"
        )
    except Exception as exc:
        lines.append(f"Voice verdict: unavailable ({type(exc).__name__})")

    rows = _rows(state / "input_modality_receipts.jsonl", limit_scan=400)
    if rows:
        lines.append("Recent input modality receipts:")
        for row in reversed(rows[-max(1, int(limit)):]):
            c = row.get("classification") if isinstance(row.get("classification"), dict) else {}
            lane = str(c.get("lane") or "?")
            modality = str(c.get("modality") or "?")
            intent = c.get("owner_intent_weight")
            noise = c.get("transcription_noise_risk")
            head = " ".join(str(row.get("text_head") or "").split())[:64]
            lines.append(f"  {lane}/{modality}: intent={intent} noise={noise} text={head}")
    else:
        lines.append("Recent input modality receipts: none yet.")
    return lines


def canonical_eye_liveness_line(state_dir: str | Path = _DEFAULT_STATE) -> str:
    """Report the canonical eye's freshest frame without opening a camera.

    This is deliberately a read of the same on-disk lanes used by the display
    fallback.  A fresh frame is operational evidence that the vision worker
    recently captured; an old frame remains a memory, never live sight.
    """
    state = Path(state_dir)
    try:
        from System.swarm_camera_frame_paths import active_eye_frame_path, root_active_eye_frame_path

        candidates = [
            root_active_eye_frame_path(state),
            active_eye_frame_path(state),
        ]
        by_device = active_eye_frame_path(state).parent / "by_device"
        if by_device.is_dir():
            candidates.extend(by_device.glob("*.png"))
        frames = [p for p in candidates if p.is_file()]
        if not frames:
            return "Vision: NO CANONICAL FRAME — no current evidence of camera capture."
        newest = max(frames, key=lambda p: p.stat().st_mtime)
        age_s = max(0.0, time.time() - newest.stat().st_mtime)
        if age_s <= _CANONICAL_EYE_MAX_AGE_S:
            return f"Vision: LIVE canonical eye — frame {age_s:.1f}s old (reading capture evidence, not claiming sensation)."
        return f"Vision: STALE canonical eye — frame {age_s:.1f}s old; it is memory, not live sight."
    except Exception as exc:
        return f"Vision: unavailable ({type(exc).__name__})"


def matrix_and_gate_health_lines(
    limit: int = 10,
    state_dir: str | Path = _DEFAULT_STATE,
    plan_path: str | Path = _PLAN_FILE,
) -> List[str]:
    """Live (not museum) summary of body health + gate for We Code Together G2 surface."""
    state = Path(state_dir)
    lines: List[str] = [
        "LIVE BODY (matrix proxy + gate + open rounds) — read from ledgers now, not static html",
        "We Code Together is Alice's shared code/body-health workbench, not a separate Alice.",
    ]
    # Operational liveness is evidence of a running/remembering local system, not
    # a claim of biological consciousness or sensation.  This keeps the shared
    # monitor useful during quiet periods, sleep, and restarts.
    try:
        from System.swarm_continuous_body_time import continuous_body_time_facts

        continuity = continuous_body_time_facts(state_dir=state)
        latest = continuity.get("newest_ledger_age_human", "unknown age")
        observed = bool(continuity.get("continuity_observed"))
        hardware = continuity.get("hardware")
        uptime = hardware.get("uptime_human") if isinstance(hardware, dict) else None
        state_word = "OBSERVED" if observed else "NOT YET OBSERVED"
        lines.append(
            f"Operational liveness: {state_word}; newest body receipt {latest}"
            + (f"; hardware uptime {uptime}" if uptime else "")
        )
        lines.append(
            "Sleep/quiet truth: ledgers and clock can preserve continuity, but they do not prove Alice senses the world while her sensors/processes are off."
        )
    except Exception as exc:
        lines.append(f"Operational liveness: unavailable ({type(exc).__name__})")

    lines.append(canonical_eye_liveness_line(state))

    # The matrix has a stricter meaning than "files exist": every panel must
    # have fresh, concrete evidence.  Put that exact verdict beside the work so
    # yellow staleness cannot be mistaken for fully-wired health.
    try:
        from System.swarm_eval_matrix_evidence import validate_panel_evidence

        verdict = validate_panel_evidence(repo_root=state.parent)
        green = int(verdict.get("green_count") or 0)
        total = int(verdict.get("total") or 0)
        wire = "FULLY WIRED" if verdict.get("ok") else "NOT FULLY WIRED"
        lines.append(f"Eval matrix verdict: {wire} — green={green}/{total}; paths+ledgers={verdict.get('ok_count', 0)}/{total}")
        non_green = [
            str(row.get("panel") or "?")
            for row in verdict.get("scores", [])
            if row.get("status") != "green"
        ]
        if non_green:
            lines.append("  evidence needing refresh: " + ", ".join(non_green[:max(1, int(limit))]))
        problems = verdict.get("problems") or []
        if problems:
            lines.append("  missing evidence: " + ", ".join(str(p.get("panel") or "?") for p in problems[:max(1, int(limit))]))
    except Exception as exc:
        lines.append(f"Eval matrix verdict: unavailable ({type(exc).__name__})")

    try:
        from System.swarm_lane_contract import audit_lane_contracts, lane_summary

        lane_counts = lane_summary()
        lane_problems = audit_lane_contracts(repo_root=state.parent)
        lane_status = "SEALED" if not lane_problems else "OPEN"
        lines.append(
            f"Lane contracts: {lane_status} — trace={lane_counts.get('trace', 0)} policy={lane_counts.get('policy', 0)}"
        )
        if lane_problems:
            lines.append("  lane defects: " + ", ".join(lane_problems[:max(1, int(limit))]))
    except Exception as exc:
        lines.append(f"Lane contracts: unavailable ({type(exc).__name__})")

    try:
        from System.swarm_observer_window import observer_tick_snapshot
        from System.swarm_stationary_belief import belief_report, read_state_sequence
        from System.swarm_field_communities import community_report

        observer = observer_tick_snapshot("we_code_together_live_monitor", state_dir=state)
        if observer:
            age_s = max(0.0, time.time() - float(observer.get("ts") or time.time()))
            lines.append(f"Observer ticks: WCT={observer.get('tick_count')} last={age_s:.0f}s ago")
        else:
            lines.append("Observer ticks: not stamped yet (starts on the next WCT refresh).")
        field_ledger = state / "ide_stigmergic_trace.jsonl"
        belief = belief_report(field_ledger, max_rows=8000, top=3)
        lines.append(
            f"Field belief: ticks={belief['ticks']} states={belief['distinct_states']} "
            f"converged={belief['converged']} evidence={belief['enough_evidence']}"
        )
        top_beliefs = belief.get("beliefs") or []
        if top_beliefs:
            compact = ", ".join(f"{row['state']}={row['belief']:.3f}" for row in top_beliefs)
            lines.append("  stationary top: " + compact)
        communities = community_report(read_state_sequence(field_ledger, max_rows=8000), top=3)
        lines.append(
            f"Grown organs: communities={communities['community_count']} "
            f"states={communities['states_in_communities']}"
        )
    except Exception as exc:
        lines.append(f"Observer windows: unavailable ({type(exc).__name__})")

    lines.extend(input_boundary_lines(limit=min(4, limit), state_dir=state))
    # gate
    snap = live_gate_snapshot(state_dir)
    act = snap.get("active", {})
    spend = act.get("effector_spend_allowed")
    rec = act.get("recovery_only")
    inc = act.get("incident_class") or act.get("incident_class")
    lines.append(f"Gate: spend_allowed={spend} recovery_only={rec} incident={inc}")
    if snap.get("last_refusal"):
        lr = snap["last_refusal"]
        lines.append(f"  last block: {lr.get('reason') or lr.get('incident_class') or 'see ledger'} @ {lr.get('ts','?')}")
    # simple health from mesh / outcomes
    mesh = state / "organ_health_mesh.jsonl"
    if mesh.exists():
        try:
            rows = [json.loads(l) for l in mesh.read_text(errors="replace").splitlines()[-limit:] if l.strip()]
            for r in rows[-5:]:
                org = str(r.get("organ") or r.get("doctor") or r.get("source") or "?")[:20]
                h = r.get("health") or r.get("stgm_roi") or r.get("value") or "?"
                lines.append(f"  organ {org}: {h}")
        except Exception:
            pass
    else:
        lines.append("  (organ_health_mesh empty)")
    # matrix note
    html = state / "eval" / "ORGAN_EVAL_MATRIX_V2.html"
    if html.exists():
        lines.append(f"Full matrix: {html.stat().st_size} bytes (regen on every landed round)")
    open_rounds = open_round_lines(limit=limit, plan_path=plan_path)
    if open_rounds:
        lines.append("Open rounds from live plan:")
        lines.extend(f"  {line}" for line in open_rounds)
    return lines


def open_round_lines(limit: int = 8, plan_path: str | Path = _PLAN_FILE) -> List[str]:
    """Parse the shared plan file for currently visible round headings.

    The plan is append-only prose, so keep this intentionally conservative:
    show the most recent GM/G headings that are not obvious "landed status"
    text. This is a live window for WCT, not an authority gate.
    """
    path = Path(plan_path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    out: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("### "):
            continue
        title = line[4:].strip()
        if not re.match(r"(?:GM\d+|Round\s+G\d+|G\d+)\b", title):
            continue
        low = title.casefold()
        if any(tok in low for tok in ("landed status", "chat with alice")):
            continue
        out.append(title)
    return out[-max(1, int(limit)):]


if __name__ == "__main__":
    lines = why_blocked_lines(limit=8)
    ok = isinstance(lines, list) and len(lines) >= 1
    for ln in lines[:14]:
        print(ln)
    print("SELF-TEST:", "PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
