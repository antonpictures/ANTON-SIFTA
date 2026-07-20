#!/usr/bin/env python3
"""Browser interruption recovery receipts for Alice's forager hand.

This organ turns "the page did not match the intended movement" into a small,
deduplicated receipt the rest of SIFTA can see.  It is deliberately conservative:
it classifies blockers and recommends the next movement, but it does not click
legal, login, payment, CAPTCHA, or permission gates by itself.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
RECOVERY_LEDGER = "browser_interruption_recovery.jsonl"
WORK_LEDGER = "work_receipts.jsonl"
IDE_TRACE_LEDGER = "ide_stigmergic_trace.jsonl"
TRUTH_LABEL = "BROWSER_INTERRUPTION_RECOVERY_V1"

_RECENT_DEDUPE_WINDOW_S = 90.0
_MIN_CONFIDENCE_TO_RECORD = 0.55
_TEXT_LIMIT = 9000


@dataclass(frozen=True)
class InterruptionDecision:
    kind: str
    confidence: float
    blocked: bool
    recommended_action: str
    needs_owner_input: bool = False
    safe_auto_action: bool = False
    summary: str = ""
    evidence: list[str] = field(default_factory=list)
    candidate_controls: list[dict[str, Any]] = field(default_factory=list)


def _state(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def _host(url: Any) -> str:
    try:
        return urlparse(str(url or "")).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _control_label(control: Any) -> str:
    if isinstance(control, Mapping):
        return str(
            control.get("label")
            or control.get("text")
            or control.get("aria")
            or control.get("title")
            or control.get("role")
            or ""
        ).strip()
    return str(control or "").strip()


def _control_rect(control: Any) -> dict[str, Any]:
    if isinstance(control, Mapping) and isinstance(control.get("rect"), Mapping):
        return dict(control.get("rect") or {})
    return {}


def _visible_controls(page_state: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = page_state.get("visible_controls")
    controls: list[Any] = list(raw) if isinstance(raw, list) else []
    if not controls:
        buttons = page_state.get("buttons")
        controls = list(buttons) if isinstance(buttons, list) else []
    out: list[dict[str, Any]] = []
    for item in controls[:40]:
        label = _control_label(item)
        if not label:
            continue
        row = {
            "label": label[:120],
            "role": str(item.get("role") or "")[:40] if isinstance(item, Mapping) else "",
        }
        rect = _control_rect(item)
        if rect:
            row["rect"] = rect
        out.append(row)
    return out[:20]


def _joined_observation_text(page_state: Mapping[str, Any]) -> str:
    parts: list[str] = [
        str(page_state.get("title") or ""),
        str(page_state.get("text_excerpt") or ""),
    ]
    for key in ("headings", "buttons", "top_links"):
        value = page_state.get(key)
        if not isinstance(value, list):
            continue
        for item in value[:20]:
            if isinstance(item, Mapping):
                parts.append(str(item.get("text") or item.get("label") or item.get("href") or ""))
            else:
                parts.append(str(item or ""))
    for control in _visible_controls(page_state):
        parts.append(str(control.get("label") or ""))
    return " ".join(p for p in parts if p).strip()[:_TEXT_LIMIT]


def _matching_controls(controls: list[dict[str, Any]], pattern: str) -> list[dict[str, Any]]:
    rx = re.compile(pattern, re.I)
    out = [c for c in controls if rx.search(str(c.get("label") or ""))]
    return out[:6]


def _hit(text: str, *patterns: str) -> list[str]:
    found: list[str] = []
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            found.append(match.group(0)[:80])
    return found


def classify_interruption(
    page_state: Mapping[str, Any],
    *,
    expected_url: str = "",
    expected_kind: str = "",
) -> InterruptionDecision:
    """Classify a rendered page-state receipt as a blocker or normal page."""
    url = str(page_state.get("url") or "")
    actual_host = _host(url)
    expected_host = _host(expected_url)
    controls = _visible_controls(page_state)
    text = _joined_observation_text(page_state)
    low = text.lower()

    if expected_host and actual_host and expected_host != actual_host:
        return InterruptionDecision(
            kind="wrong_page",
            confidence=0.92,
            blocked=True,
            recommended_action="navigate_expected_url",
            summary=f"Expected {expected_host}, observed {actual_host}.",
            evidence=[actual_host, expected_host],
            candidate_controls=controls[:4],
        )

    evidence = _hit(
        text,
        r"\bcaptcha\b",
        r"\brecaptcha\b",
        r"\bhcaptcha\b",
        r"verify\s+you\s+are\s+(?:a\s+)?human",
        r"prove\s+you\s+are\s+(?:a\s+)?human",
        r"i'?m\s+not\s+a\s+robot",
    )
    if evidence:
        return InterruptionDecision(
            kind="captcha",
            confidence=0.96,
            blocked=True,
            recommended_action="owner_solve_or_choose_another_path",
            needs_owner_input=True,
            summary="Human-verification gate blocks the browser hand.",
            evidence=evidence,
            candidate_controls=_matching_controls(controls, r"captcha|robot|verify|human"),
        )

    evidence = _hit(
        text,
        r"checking\s+your\s+browser",
        r"just\s+a\s+moment",
        r"cloudflare",
        r"security\s+check",
        r"verify\s+you\s+are\s+not\s+a\s+bot",
    )
    if evidence:
        return InterruptionDecision(
            kind="cloudflare_wait",
            confidence=0.88,
            blocked=True,
            recommended_action="wait_then_refresh_page_state",
            safe_auto_action=True,
            summary="Temporary browser/security wait page.",
            evidence=evidence,
            candidate_controls=controls[:4],
        )

    evidence = _hit(
        text,
        r"complete\s+sign[-\s]?in\s+using\s+your\s+passkey",
        r"\bpasskey\b",
        r"\bwebauthn\b",
        r"verifying\s+it[’']?s\s+you",
        r"try\s+another\s+way",
    )
    passkey_controls = _matching_controls(controls, r"try another way|passkey|security key|continue")
    if evidence:
        return InterruptionDecision(
            kind="passkey_auth",
            confidence=0.95,
            blocked=True,
            recommended_action="owner_complete_passkey_or_try_another_way_then_resume",
            needs_owner_input=True,
            summary="Google/passkey verification is waiting for owner action.",
            evidence=evidence,
            candidate_controls=passkey_controls,
        )

    evidence = _hit(
        text,
        r"two[-\s]?factor",
        r"\b2fa\b",
        r"verification\s+code",
        r"enter\s+(?:the\s+)?code",
        r"authenticator\s+app",
    )
    if evidence:
        return InterruptionDecision(
            kind="two_factor",
            confidence=0.94,
            blocked=True,
            recommended_action="owner_enter_code_then_resume",
            needs_owner_input=True,
            summary="Account verification code is needed.",
            evidence=evidence,
            candidate_controls=_matching_controls(controls, r"code|verify|continue|submit"),
        )

    evidence = _hit(
        text,
        r"sign\s+in\s+to\s+continue",
        r"log\s+in\s+to\s+continue",
        r"continue\s+with\s+google",
        r"continue\s+with\s+apple",
        r"email\s+address",
        r"password",
    )
    sign_controls = _matching_controls(controls, r"sign\s*in|log\s*in|continue with|password|email")
    if evidence or sign_controls:
        return InterruptionDecision(
            kind="login_required",
            confidence=0.86,
            blocked=True,
            recommended_action="owner_login_then_resume",
            needs_owner_input=True,
            summary="Login wall is in front of the requested action.",
            evidence=evidence or [c["label"] for c in sign_controls[:3]],
            candidate_controls=sign_controls,
        )

    evidence = _hit(
        text,
        r"terms\s+of\s+service",
        r"terms\s+and\s+conditions",
        r"privacy\s+policy",
        r"i\s+agree",
        r"accept\s+terms",
    )
    term_controls = _matching_controls(controls, r"agree|accept|continue|terms")
    if evidence and term_controls:
        return InterruptionDecision(
            kind="terms_gate",
            confidence=0.82,
            blocked=True,
            recommended_action="owner_review_terms_then_resume",
            needs_owner_input=True,
            summary="Terms/privacy gate needs an owner choice.",
            evidence=evidence,
            candidate_controls=term_controls,
        )

    evidence = _hit(
        text,
        r"\bcookies?\b",
        r"cookie\s+settings",
        r"manage\s+preferences",
        r"accept\s+all",
        r"reject\s+all",
    )
    cookie_controls = _matching_controls(controls, r"accept|reject|cookie|preferences|manage")
    if evidence and cookie_controls:
        return InterruptionDecision(
            kind="cookie_consent",
            confidence=0.78,
            blocked=True,
            recommended_action="choose_cookie_preference_then_resume",
            summary="Cookie banner is covering the normal page flow.",
            evidence=evidence,
            candidate_controls=cookie_controls,
        )

    evidence = _hit(
        text,
        r"allow\s+notifications",
        r"allow\s+microphone",
        r"allow\s+camera",
        r"permission",
    )
    permission_controls = _matching_controls(controls, r"allow|deny|block|permission|camera|microphone")
    if evidence and permission_controls:
        return InterruptionDecision(
            kind="permission_dialog",
            confidence=0.76,
            blocked=True,
            recommended_action="owner_choose_permission_then_resume",
            needs_owner_input=True,
            summary="Browser/site permission prompt is active.",
            evidence=evidence,
            candidate_controls=permission_controls,
        )

    evidence = _hit(
        text,
        r"subscribe\s+to\s+continue",
        r"continue\s+reading",
        r"\bpaywall\b",
        r"sign\s+up\s+to\s+continue",
    )
    if evidence:
        return InterruptionDecision(
            kind="subscription_modal",
            confidence=0.72,
            blocked=True,
            recommended_action="close_or_owner_choose_path",
            summary="Subscription/sign-up modal may be blocking the page.",
            evidence=evidence,
            candidate_controls=_matching_controls(controls, r"close|no thanks|continue|subscribe|sign up"),
        )

    text_chars = int(page_state.get("text_chars") or len(text) or 0)
    if expected_kind and text_chars < 180 and re.search(r"\bcontinue\b|\bnext\b|\bstart\b", low):
        return InterruptionDecision(
            kind="unknown_interstitial",
            confidence=0.58,
            blocked=True,
            recommended_action="inspect_visible_controls_then_choose",
            summary="Short interstitial page appeared before the expected content.",
            evidence=_hit(text, r"\bcontinue\b", r"\bnext\b", r"\bstart\b") or [text[:80]],
            candidate_controls=controls[:8],
        )

    return InterruptionDecision(
        kind="none",
        confidence=0.0,
        blocked=False,
        recommended_action="continue",
        summary="No browser interruption detected.",
        candidate_controls=controls[:4],
    )


def _fingerprint(page_state: Mapping[str, Any], decision: InterruptionDecision) -> str:
    controls = ",".join(c.get("label", "") for c in decision.candidate_controls[:5])
    seed = "|".join(
        [
            decision.kind,
            str(page_state.get("url") or ""),
            str(page_state.get("content_hash") or ""),
            controls,
            ",".join(decision.evidence[:4]),
        ]
    )
    return _sha(seed)[:24]


def latest_interruption_receipts(
    *,
    limit: int = 8,
    state_dir: Path | str | None = None,
) -> list[dict[str, Any]]:
    path = _state(state_dir) / RECOVERY_LEDGER
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-max(limit * 4, limit):]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-limit:]


def _recent_duplicate(
    fingerprint: str,
    *,
    now: float,
    state_dir: Path | str | None,
) -> bool:
    for row in reversed(latest_interruption_receipts(limit=32, state_dir=state_dir)):
        if str(row.get("fingerprint") or "") != fingerprint:
            continue
        try:
            ts = float(row.get("ts") or 0.0)
        except Exception:
            ts = 0.0
        if ts and now - ts <= _RECENT_DEDUPE_WINDOW_S:
            return True
    return False


def maybe_record_interruption(
    page_state: Mapping[str, Any],
    *,
    expected_url: str = "",
    expected_kind: str = "",
    source: str = "browser_page_state",
    state_dir: Path | str | None = None,
    now: float | None = None,
    min_confidence: float = _MIN_CONFIDENCE_TO_RECORD,
) -> dict[str, Any]:
    """Classify and append a recovery receipt when a real blocker is observed."""
    decision = classify_interruption(
        page_state,
        expected_url=expected_url,
        expected_kind=expected_kind,
    )
    ts = float(now if now is not None else time.time())
    base_row = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "receipt_id": f"browser-recovery-{int(ts * 1000):x}-{_sha(str(page_state.get('url') or ''))[:8]}",
        "source": str(source or "browser_page_state"),
        "url": str(page_state.get("url") or ""),
        "title": str(page_state.get("title") or "")[:180],
        "domain": str(page_state.get("domain") or _host(page_state.get("url")))[:120],
        "expected_url": str(expected_url or "")[:500],
        "expected_kind": str(expected_kind or "")[:80],
        "text_hash": str(page_state.get("content_hash") or _sha(_joined_observation_text(page_state)))[:64],
        **asdict(decision),
    }
    fp = _fingerprint(page_state, decision)
    base_row["fingerprint"] = fp

    if not decision.blocked or decision.confidence < min_confidence:
        base_row["recorded"] = False
        base_row["reason"] = "no_interruption"
        return base_row
    if _recent_duplicate(fp, now=ts, state_dir=state_dir):
        base_row["recorded"] = False
        base_row["reason"] = "duplicate_recent_interruption"
        return base_row

    base = _state(state_dir)
    base_row["recorded"] = True
    _append_jsonl(base / RECOVERY_LEDGER, base_row)
    _append_jsonl(base / WORK_LEDGER, {
        "ts": ts,
        "receipt_id": base_row["receipt_id"],
        "kind": "browser_interruption_recovery",
        "status": "recorded",
        "interruption_kind": decision.kind,
        "recommended_action": decision.recommended_action,
        "source": source,
    })
    _append_jsonl(base / IDE_TRACE_LEDGER, {
        "ts": ts,
        "event": "browser_interruption_recovery",
        "receipt_id": base_row["receipt_id"],
        "message": (
            f"{decision.kind}: {decision.summary} "
            f"next={decision.recommended_action}"
        )[:500],
    })
    return base_row


def recovery_monitor_lines(
    *,
    state_dir: Path | str | None = None,
    limit: int = 5,
) -> list[str]:
    """We Code Together view: latest blockers and the next grounded movement."""
    rows = latest_interruption_receipts(limit=limit, state_dir=state_dir)
    lines = [
        "BROWSER INTERRUPTION RECOVERY — forager hand homing receipts:",
        "  Detects cookie/login/CAPTCHA/Cloudflare/permission/wrong-page blockers from real page-state receipts.",
    ]
    if not rows:
        lines.append("  No interruption receipts yet; normal browsing receipts continue elsewhere.")
        return lines
    for row in rows[-limit:]:
        ts = row.get("ts")
        try:
            stamp = time.strftime("%H:%M:%S", time.localtime(float(ts or 0)))
        except Exception:
            stamp = "??:??:??"
        rid = str(row.get("receipt_id") or "?")[:38]
        kind = str(row.get("kind") or "?")[:24]
        action = str(row.get("recommended_action") or "?")[:42]
        domain = str(row.get("domain") or _host(row.get("url")))[:34]
        confidence = row.get("confidence")
        try:
            conf = f"{float(confidence):.2f}"
        except Exception:
            conf = "?"
        lines.append(f"  [{stamp}] {kind:24s} conf={conf} domain={domain}")
        lines.append(f"          next: {action}  receipt={rid}")
        summary = str(row.get("summary") or "").replace("\n", " ")[:110]
        if summary:
            lines.append(f"          {summary}")
    return lines
