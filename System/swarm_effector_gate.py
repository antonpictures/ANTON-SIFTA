"""World-touching effector gate — binds owner ingress to spendable nonces (r1016 P0)."""
from __future__ import annotations

import json
import hashlib
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from System.swarm_intent_nonce_gate import (
    DEFAULT_MIN_STT_CONF,
    mint_intent_nonce,
    validate_effector_spend,
)

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]

ACTIVE_NAME = "active_intent_nonce.json"
LEDGER_NAME = "effector_gate.jsonl"
TRUTH_LABEL = "EFFECTOR_GATE_V1"
PURCHASE_INTENT_TRUTH_LABEL = "PURCHASE_INTENT_GATE_V1"
INCIDENT_245FCB4E = "245fcb4e-timeout-recovery-replay"
INCIDENT_91E01405 = "91e01405-uncommanded-browser-click"

_PURCHASE_ACTION_TERMS = (
    "buy",
    "purchase",
    "checkout",
    "pay",
    "payment",
    "subscribe",
    "subscription",
    "renew",
    "donate",
    "bid",
    "order",
    "book",
    "reserve",
    "rent",
)
_PURCHASE_STRONG_TERMS = {
    "buy",
    "purchase",
    "checkout",
    "pay",
    "payment",
    "subscribe",
    "subscription",
    "renew",
    "donate",
    "bid",
}
_COMMERCE_CONTEXT_TERMS = (
    "amazon",
    "ebay",
    "etsy",
    "shop",
    "store",
    "merchant",
    "cart",
    "checkout",
    "invoice",
    "receipt",
    "card",
    "visa",
    "mastercard",
    "amex",
    "paypal",
    "stripe",
    "price",
    "shipping",
    "delivery",
    "ticket",
    "flight",
    "hotel",
    "rental",
    "subscription",
    "plan",
    "stgm",
)
_MONEY_RE = re.compile(
    r"(\$\s*\d|\b\d+(?:\.\d{2})?\s*(?:usd|dollars?|bucks?|eur|gbp|stgm|tokens?)\b)",
    re.IGNORECASE,
)


def _state_dir(state_dir: Path | str | None) -> Path:
    if state_dir is None:
        return Path(__file__).resolve().parents[1] / ".sifta_state"
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _append(sd: Path, row: Dict[str, Any]) -> None:
    line = json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
    path = sd / LEDGER_NAME
    if append_line_locked is not None:
        append_line_locked(path, line)
    else:  # pragma: no cover
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line)


def _write_active(sd: Path, row: Dict[str, Any]) -> None:
    (sd / ACTIVE_NAME).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_active_context(*, state_dir: Path | str | None = None) -> Dict[str, Any]:
    sd = _state_dir(state_dir)
    path = sd / ACTIVE_NAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _word_hits(text: str, terms: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for term in terms:
        pattern = r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])"
        if re.search(pattern, text, re.IGNORECASE):
            hits.append(term)
    return hits


def classify_purchase_intent(owner_text: str) -> Dict[str, Any]:
    """Detect owner-commerce intent before any effector spends a nonce."""
    text = (owner_text or "").strip()
    normalized = re.sub(r"\s+", " ", text.lower())
    action_hits = _word_hits(normalized, _PURCHASE_ACTION_TERMS)
    context_hits = _word_hits(normalized, _COMMERCE_CONTEXT_TERMS)
    money_hit = bool(_MONEY_RE.search(normalized))
    strong_hits = [hit for hit in action_hits if hit in _PURCHASE_STRONG_TERMS]
    detected = bool(strong_hits or (action_hits and (context_hits or money_hit)))
    return {
        "schema": PURCHASE_INTENT_TRUTH_LABEL,
        "purchase_intent_detected": detected,
        "commerce_risk": "pre_effector_purchase" if detected else "none",
        "action_hits": action_hits,
        "commerce_context_hits": context_hits,
        "money_signal": money_hit,
        "owner_text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        "owner_text_preview": text[:120],
        "mana_is_crypto": False,
        "stgm_is_crypto": True,
        "economy_lane": "STGM_SPEND_PROOF_REQUIRED" if detected else "MANA_TRACE_ONLY",
    }


def _append_purchase_intent_if_needed(
    *,
    sd: Path,
    owner_text: str,
    minted: Dict[str, Any],
    surface: str,
    ingress_kind: str,
    stt_conf: float | None,
) -> Dict[str, Any]:
    purchase = classify_purchase_intent(owner_text)
    if not purchase.get("purchase_intent_detected"):
        return purchase
    row = {
        **purchase,
        "action": "purchase_intent",
        "receipt_id": str(uuid.uuid4()),
        "ts": time.time(),
        "nonce": minted.get("nonce"),
        "surface": surface,
        "ingress_kind": ingress_kind,
        "stt_conf": stt_conf,
        "intent_nonce_text_hash": minted.get("text_hash"),
    }
    _append(sd, row)
    return purchase


def bind_owner_ingress(
    *,
    owner_text: str,
    surface: str = "talk",
    stt_conf: float | None = None,
    ingress_kind: str = "typed",
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    """Fresh owner turn mints a spendable nonce."""
    sd = _state_dir(state_dir)
    minted = mint_intent_nonce(
        owner_text=owner_text,
        surface=surface,
        stt_conf=stt_conf,
        ingress_kind=ingress_kind,
        state_dir=sd,
    )
    purchase_intent = _append_purchase_intent_if_needed(
        sd=sd,
        owner_text=owner_text,
        minted=minted,
        surface=surface,
        ingress_kind=ingress_kind,
        stt_conf=stt_conf,
    )
    ctx = {
        "schema": TRUTH_LABEL,
        "nonce": minted["nonce"],
        "effector_spend_allowed": True,
        "recovery_only": False,
        "ingress_kind": ingress_kind,
        "stt_conf": stt_conf,
        "bound_ts": time.time(),
        "owner_text_preview": (owner_text or "")[:120],
        "purchase_intent": purchase_intent,
        "purchase_intent_detected": bool(purchase_intent.get("purchase_intent_detected")),
    }
    _write_active(sd, ctx)
    return ctx


def bind_recovery_context(
    *,
    source: str = "cortex_timeout_recovery",
    linked_receipt: str = "",
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    """Timeout/recovery may resume cognition — never spend effectors."""
    sd = _state_dir(state_dir)
    ctx = {
        "schema": TRUTH_LABEL,
        "nonce": "",
        "effector_spend_allowed": False,
        "recovery_only": True,
        "source": source,
        "linked_receipt": linked_receipt,
        "bound_ts": time.time(),
        "incident_class": INCIDENT_245FCB4E,
    }
    _write_active(sd, ctx)
    row = {
        "schema": TRUTH_LABEL,
        "action": "recovery_bind",
        "receipt_id": str(uuid.uuid4()),
        "ts": time.time(),
        **ctx,
    }
    _append(sd, row)
    return ctx


def _refuse(
    *,
    effector: str,
    reason: str,
    action: str = "",
    state_dir: Path | str | None = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    sd = _state_dir(state_dir)
    row = {
        "schema": TRUTH_LABEL,
        "action": "refused",
        "receipt_id": str(uuid.uuid4()),
        "ts": time.time(),
        "effector": effector,
        "browser_action": action,
        "reason": reason,
        "incident_closed": reason in {
            "double_spend_blocked",
            "recovery_context_no_effector",
            "missing_active_nonce",
            "effector_spend_not_allowed",
            "stt_conf_too_low",
        },
        **(extra or {}),
    }
    _append(sd, row)
    return {"ok": False, "reason": reason, "gate_receipt_id": row["receipt_id"], **row}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def path_outside_repo(path: str) -> bool:
    """True when resolved path is outside the SIFTA repo (file-write effector scope)."""
    try:
        resolved = Path(str(path or "")).expanduser().resolve()
        repo = _repo_root().resolve()
        return not str(resolved).startswith(str(repo))
    except Exception:
        return True


def require_effector(
    effector_kind: str,
    action: str = "",
    *,
    state_dir: Path | str | None = None,
    source: str = "effector_gate",
) -> Dict[str, Any]:
    """Gate any world-touching effector through active owner ingress + nonce spend."""
    sd = _state_dir(state_dir)
    ctx = read_active_context(state_dir=sd)
    if ctx.get("recovery_only") or not ctx.get("effector_spend_allowed", False):
        return _refuse(
            effector=effector_kind,
            action=action,
            reason="recovery_context_no_effector",
            state_dir=sd,
            extra={"active_context": ctx, "incident_prevented": INCIDENT_91E01405},
        )
    nonce = str(ctx.get("nonce") or "").strip()
    if not nonce:
        return _refuse(
            effector=effector_kind,
            action=action,
            reason="missing_active_nonce",
            state_dir=sd,
            extra={"incident_prevented": INCIDENT_91E01405},
        )
    spend_label = f"{effector_kind}:{action}" if action else effector_kind
    spend = validate_effector_spend(
        nonce,
        state_dir=sd,
        effector=spend_label,
        min_stt_conf=DEFAULT_MIN_STT_CONF,
    )
    if not spend.get("ok"):
        return _refuse(
            effector=effector_kind,
            action=action,
            reason=str(spend.get("reason") or "spend_denied"),
            state_dir=sd,
            extra={"spend": spend, "incident_prevented": INCIDENT_91E01405},
        )
    ok_row = {
        "schema": TRUTH_LABEL,
        "action": "allowed",
        "receipt_id": str(uuid.uuid4()),
        "ts": time.time(),
        "effector": effector_kind,
        "browser_action": action,
        "nonce": nonce,
        "source": source,
        "purchase_intent": ctx.get("purchase_intent") or {},
        "purchase_intent_detected": bool(ctx.get("purchase_intent_detected")),
    }
    _append(sd, ok_row)
    return {
        "ok": True,
        "gate_receipt_id": ok_row["receipt_id"],
        "nonce": nonce,
        "purchase_intent_detected": bool(ctx.get("purchase_intent_detected")),
    }


def require_browser_effector(
    action: str,
    *,
    state_dir: Path | str | None = None,
    source: str = "alice_browser",
) -> Dict[str, Any]:
    """Gate browser click/navigate/tab world-touch."""
    return require_effector("browser", action, state_dir=state_dir, source=source)


def require_file_write_effector(
    path: str,
    *,
    state_dir: Path | str | None = None,
    source: str = "file_organ",
) -> Dict[str, Any]:
    if not path_outside_repo(path):
        return {"ok": True, "gate_receipt_id": "", "skipped": "inside_repo"}
    return require_effector("file_write", path, state_dir=state_dir, source=source)


def require_network_effector(
    action: str,
    *,
    state_dir: Path | str | None = None,
    source: str = "network",
) -> Dict[str, Any]:
    return require_effector("network", action, state_dir=state_dir, source=source)


def require_shell_effector(
    command: str,
    *,
    state_dir: Path | str | None = None,
    source: str = "shell",
) -> Dict[str, Any]:
    return require_effector("shell", command[:120], state_dir=state_dir, source=source)


def require_applescript_effector(
    action: str,
    *,
    state_dir: Path | str | None = None,
    source: str = "applescript",
) -> Dict[str, Any]:
    return require_effector("applescript", action, state_dir=state_dir, source=source)


def require_iphone_effector(
    payload: str,
    *,
    state_dir: Path | str | None = None,
    source: str = "iphone",
) -> Dict[str, Any]:
    return require_effector("iphone", payload[:120], state_dir=state_dir, source=source)


def record_incident_closed(
    *,
    incident_from: str = INCIDENT_245FCB4E,
    incident_to: str = INCIDENT_91E01405,
    verdict: str = "REFUSED",
    probe: str = "",
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    """Formal incident-closed row after probe-before-claim replay (r1018)."""
    sd = _state_dir(state_dir)
    row = {
        "schema": TRUTH_LABEL,
        "action": "incident_closed",
        "receipt_id": str(uuid.uuid4()),
        "ts": time.time(),
        "incident_from": incident_from,
        "incident_to": incident_to,
        "incident_chain": f"{incident_from}→{incident_to}",
        "verdict": verdict,
        "probe": probe,
        "incident_closed": True,
    }
    _append(sd, row)
    return row
