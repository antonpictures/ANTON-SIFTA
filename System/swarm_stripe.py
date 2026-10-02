"""swarm_stripe — taking money, and only believing Stripe about it.

The rule this module exists to enforce: **credit is added only when a payment is
proven**, by a signed message from Stripe, for an amount that was actually paid,
against an account id that Stripe echoed back to us. Nothing a visitor sends can
create credit, and nothing in here trusts an unsigned request.

Config lives in .sifta_state/stripe.json (mode 0600, gitignored):

    {
      "restricted_key": "rk_live_...",     # checkout sessions: write, links: read
      "webhook_secrets": ["whsec_..."],    # one per Stripe event destination
      "bundles": { ... }                   # optional override of the price list
    }

Signature verification follows Stripe's own scheme: the `Stripe-Signature`
header carries `t=<unix>,v1=<hex>`, and the signed payload is "<t>.<raw body>"
hashed with HMAC-SHA256 under the destination's signing secret.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

STRIPE_CONFIG = "stripe.json"
STRIPE_EVENTS = "stripe_events.jsonl"
TRUTH_LABEL = "SIFTA_STRIPE_V1"

SIGNATURE_TOLERANCE_SECONDS = 300
MAX_EVENT_LOG_BYTES = 2_000_000      # ~2MB, then only the last 200 events are kept
API_BASE = "https://api.stripe.com/v1"

# ── the price list, in credit dollars ────────────────────────────────────────
# A question costs PRICE_PER_QUESTION of credit, so a bundle is worth
# questions x price in credit and is sold for less than that. The visitor is
# told the question count; the ledger records real credit dollars.
PRICE_PER_QUESTION = float(os.environ.get("SIFTA_PRICE_PER_QUESTION", "0.30"))

DEFAULT_BUNDLES = {
    "questions_25": {"amount_usd": 5.00, "questions": 25},
    "questions_150": {"amount_usd": 20.00, "questions": 150},
}


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


# ── config ───────────────────────────────────────────────────────────────────

def config(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    p = _state_dir(state_dir) / STRIPE_CONFIG
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return d if isinstance(d, dict) else {}


def bundles(*, state_dir: Path | str | None = None) -> dict[str, dict[str, Any]]:
    out = dict(DEFAULT_BUNDLES)
    for name, row in (config(state_dir=state_dir).get("bundles") or {}).items():
        if isinstance(row, dict) and row.get("amount_usd") and row.get("questions"):
            out[str(name)] = {"amount_usd": float(row["amount_usd"]),
                              "questions": int(row["questions"])}
    return out


def credit_for_amount(amount_usd: float, *, state_dir: Path | str | None = None) -> dict[str, Any]:
    """Map money paid to credit granted, at the best matching bundle rate."""
    amount = round(float(amount_usd or 0), 2)
    for name, row in sorted(bundles(state_dir=state_dir).items(),
                            key=lambda kv: -kv[1]["amount_usd"]):
        if amount + 0.01 >= float(row["amount_usd"]):
            return {"bundle": name, "paid_usd": amount,
                    "credit_usd": round(int(row["questions"]) * PRICE_PER_QUESTION, 2),
                    "questions": int(row["questions"])}
    return {"bundle": "", "paid_usd": amount, "credit_usd": amount,
            "questions": int(amount / PRICE_PER_QUESTION) if PRICE_PER_QUESTION else 0}


# ── signatures ───────────────────────────────────────────────────────────────

def parse_signature_header(header: str) -> tuple[int, list[str]]:
    ts, sigs = 0, []
    for part in (header or "").split(","):
        if "=" not in part:
            continue
        k, _, v = part.strip().partition("=")
        if k == "t":
            try:
                ts = int(v)
            except ValueError:
                ts = 0
        elif k == "v1":
            sigs.append(v.strip())
    return ts, sigs


def verify_signature(payload: bytes, header: str, secret: str, *,
                     now: Optional[float] = None,
                     tolerance: int = SIGNATURE_TOLERANCE_SECONDS) -> tuple[bool, str]:
    """True only for a payload Stripe signed with this secret, recently."""
    if not secret:
        return False, "no_secret"
    ts, sigs = parse_signature_header(header)
    if not ts or not sigs:
        return False, "malformed_header"
    age = abs((now if now is not None else time.time()) - ts)
    if age > tolerance:
        return False, f"stale_timestamp({int(age)}s)"
    signed = f"{ts}.".encode() + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    for candidate in sigs:
        if hmac.compare_digest(candidate, expected):
            return True, "ok"
    return False, "bad_signature"


def verify_any_secret(payload: bytes, header: str, *, state_dir: Path | str | None = None,
                      now: Optional[float] = None) -> tuple[bool, str]:
    secrets = config(state_dir=state_dir).get("webhook_secrets") or []
    if isinstance(secrets, str):
        secrets = [secrets]
    if not secrets:
        return False, "no_secret_configured"
    reasons = []
    for secret in secrets:
        ok, why = verify_signature(payload, header, str(secret), now=now)
        if ok:
            return True, "ok"
        reasons.append(why)
    return False, ";".join(reasons) or "bad_signature"


# ── events ───────────────────────────────────────────────────────────────────

def log_event(row: dict[str, Any], *, state_dir: Path | str | None = None) -> None:
    """Append one event, keeping the file bounded.

    The owner's destination currently listens to every event type Stripe has
    (243 of them). This endpoint ignores all but a handful, but it still logs
    what arrives — so the log is capped rather than allowed to grow without
    limit on his Mac. Recent events are what matter for debugging; old ones go.
    """
    sd = _state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    path = sd / STRIPE_EVENTS
    if path.exists() and path.stat().st_size > MAX_EVENT_LOG_BYTES:
        keep = 200
        tail = path.read_text(encoding="utf-8", errors="replace").splitlines()[-keep:]
        path.write_text("\n".join(tail) + "\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _fetch_object(kind: str, obj_id: str, *, state_dir: Path | str | None = None) -> dict[str, Any]:
    """Thin payloads carry only an id; fetch the object to credit anything."""
    key = str(config(state_dir=state_dir).get("restricted_key") or "")
    if not key or not obj_id or not kind:
        return {}
    url = f"{API_BASE}/{kind}/{urllib.parse.quote(obj_id)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception:
        return {}


def paid_session_account(session: dict[str, Any]) -> tuple[str, str]:
    """Which account paid, and how — from Stripe's echo, never from a visitor."""
    acct = str(session.get("client_reference_id") or "").strip()
    if acct:
        return acct, "client_reference_id"
    meta = session.get("metadata") or {}
    acct = str(meta.get("account_id") or meta.get("visitor_id") or "").strip()
    if acct:
        return acct, "metadata"
    return "", ""


def handle_event(event: dict[str, Any], *, state_dir: Path | str | None = None) -> dict[str, Any]:
    """Do the one thing an event asks for. Never raises: Stripe retries 5xx."""
    etype = str(event.get("type") or "")
    data = (event.get("data") or {}).get("object") or {}
    result: dict[str, Any] = {"type": etype, "handled": False}

    if etype not in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        return result

    session = data
    if not session.get("client_reference_id") and not session.get("metadata"):
        # a thin payload: only an id came through, so go and ask Stripe
        session = _fetch_object("checkout/sessions", str(session.get("id") or ""),
                                state_dir=state_dir) or session
        result["fetched"] = True

    status = str(session.get("payment_status") or "")
    if status and status != "paid":
        result["skipped"] = f"payment_status={status}"
        return result

    account, how = paid_session_account(session)
    if not account:
        result["skipped"] = "no_account_reference"
        return result

    amount_usd = float(session.get("amount_total") or 0) / 100.0
    grant = credit_for_amount(amount_usd, state_dir=state_dir)

    from System.swarm_credits import top_up
    credited = top_up(account, grant["credit_usd"],
                      reference=str(session.get("id") or event.get("id") or ""),
                      provider="stripe", state_dir=state_dir)
    result.update({"handled": True, "account": account, "identified_by": how,
                   "paid_usd": grant["paid_usd"], "credited_usd": grant["credit_usd"],
                   "questions": grant["questions"], "bundle": grant["bundle"],
                   "duplicate": bool(credited.get("duplicate"))})
    return result


def selftest() -> dict[str, Any]:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp)
        secret = "whsec_test_secret"
        (sd / STRIPE_CONFIG).write_text(json.dumps({"webhook_secrets": [secret]}), encoding="utf-8")

        body = json.dumps({
            "id": "evt_test_1", "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_1", "payment_status": "paid",
                                "amount_total": 500, "currency": "usd",
                                "client_reference_id": "acct_test"}},
        }).encode()
        now = time.time()
        good = (f"t={int(now)},v1=" + hmac.new(secret.encode(), f"{int(now)}.".encode() + body,
                                               hashlib.sha256).hexdigest())

        ok_sig, why_sig = verify_signature(body, good, secret, now=now)
        bad_sig, why_bad = verify_signature(body, "t=%d,v1=deadbeef" % int(now), secret, now=now)
        old_sig, why_old = verify_signature(body, f"t={int(now) - 4000},v1=x", secret, now=now)
        wrong_secret, _ = verify_signature(body, good, "whsec_other", now=now)

        handled = handle_event(json.loads(body), state_dir=sd)
        from System.swarm_credits import state as credit_state
        after = credit_state("acct_test", signed_in=True, state_dir=sd)
        again = handle_event(json.loads(body), state_dir=sd)
        after_again = credit_state("acct_test", signed_in=True, state_dir=sd)

        unpaid = dict(json.loads(body))
        unpaid["data"] = {"object": {**json.loads(body)["data"]["object"],
                                     "payment_status": "unpaid", "id": "cs_test_2"}}
        unpaid_res = handle_event(unpaid, state_dir=sd)

        orphan = dict(json.loads(body))
        orphan["data"] = {"object": {"id": "cs_test_3", "payment_status": "paid",
                                     "amount_total": 500}}
        orphan_res = handle_event(orphan, state_dir=sd)

    checks = {
        "valid_signature_accepted": ok_sig and why_sig == "ok",
        "forged_signature_rejected": (not bad_sig) and why_bad == "bad_signature",
        "stale_signature_rejected": not old_sig,
        "wrong_secret_rejected": not wrong_secret,
        "payment_credits_the_account": handled["handled"] and handled["account"] == "acct_test",
        "bundle_rate_applies": handled["credited_usd"] == 7.50 and handled["questions"] == 25,
        "credit_lands_in_the_ledger": after["bought_usd"] == 7.50,
        "replayed_event_does_not_double_credit": again["duplicate"] is True
                                                 and after_again["bought_usd"] == 7.50,
        "unpaid_session_is_ignored": unpaid_res["handled"] is False
                                     and "payment_status" in str(unpaid_res.get("skipped")),
        "payment_without_an_account_is_ignored": orphan_res["handled"] is False,
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "status":
        c = config()
        print(json.dumps({"configured": bool(c.get("restricted_key")),
                          "webhook_secrets": len(c.get("webhook_secrets") or []),
                          "bundles": bundles(),
                          "price_per_question": PRICE_PER_QUESTION,
                          "truth_label": TRUTH_LABEL}, indent=2))
    elif cmd == "bundles":
        print(json.dumps(bundles(), indent=2))
    else:
        print(json.dumps(selftest(), indent=2))
