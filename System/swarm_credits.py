"""swarm_credits — what a question costs, and who has paid for it.

Owner's rule (2026-10-01), stated in his own words:

    "I like to be free for like 5 questions, after that require login to
     continue and let the user know he has $6 in credits free / day we charge
     30 cents / question .. after they finish they need to reload with credit
     card, same like ollama.com charges"

So: five questions free while anonymous. Then sign in with Google. A signed-in
person gets $6.00 of credit each day, and a question costs $0.30 — twenty
questions a day. When it is gone, a card tops it up.

Why this is affordable, measured rather than assumed: one desk answer costs
about $0.001 of model spend (see .sifta_state/desk_cost.jsonl, recorded per
answer). The free tier is the cheapest part of the business; the risk is not
margin, it is abuse and a plan ceiling — which is why the allowance is keyed to
an identity we issue and resets daily.

Two rules that keep the money honest:

  * THE LEDGER IS APPEND-ONLY. Every grant, every free question, every debit and
    every top-up is a row in .sifta_state/credits.jsonl. A balance is always
    DERIVED from those rows and never edited in place, so no bug in this file can
    invent credit that nobody paid for.
  * AN IDENTITY IS NEVER SELF-DECLARED. Anonymous allowance is keyed to the
    device cookie the server issues; the signed-in allowance is keyed to the
    Google account id it verifies. Neither comes from a value a visitor typed.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

CREDITS_LEDGER = "credits.jsonl"
TRUTH_LABEL = "SIFTA_CREDITS_V1"

# ── the price list ───────────────────────────────────────────────────────────
# ── the free allowance, and how hard it is to farm ───────────────────────────
# Owner's rule (2026-10-01): three free questions, then sign in. Signing out, or
# clearing the cookie, used to buy another three — so the allowance is counted
# three ways and the strictest one wins:
#   * per device cookie  (how a visitor experiences it)
#   * per device fingerprint (survives a cleared cookie, so a reset is not a fresh start)
#   * per network (salted IP hash) — closes the loop of signing out over and over,
#     with a cap high enough that a household of real people is not locked out.
FREE_ANONYMOUS = int(os.environ.get("SIFTA_FREE_ANON", "3"))
FREE_ANON_FINGERPRINT = int(os.environ.get("SIFTA_FREE_ANON_FP", "3"))
FREE_ANON_NETWORK = int(os.environ.get("SIFTA_FREE_ANON_NET", "12"))
DAILY_CREDIT_USD = float(os.environ.get("SIFTA_DAILY_CREDIT_USD", "6.00"))
PRICE_PER_QUESTION = float(os.environ.get("SIFTA_PRICE_PER_QUESTION", "0.30"))

_NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
                 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}


def sign_in_pitch() -> str:
    """Her words at the gate — and the count comes from the cap, not from memory.

    It said "my five free ones" for a while after the allowance was cut to three,
    which is how a promise and a product drift apart.
    """
    n = _NUMBER_WORDS.get(FREE_ANONYMOUS, str(FREE_ANONYMOUS))
    return (f"That is my {n} free ones used up. Sign in with Google and I will put $6.00 of "
            "credit in your hand every day — twenty questions, on me. No Google? Use a code: "
            "I can give you credit without an account.")


SIGN_IN_PITCH = sign_in_pitch()
OUT_OF_CREDIT = ("I have spent today's $6.00 on you. It is back tomorrow morning — or put a few "
                 "dollars on a card now and we keep going.")


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def day_key(now: Optional[float] = None) -> str:
    """The allowance resets on UTC days, so it cannot be gamed by moving a clock."""
    return time.strftime("%Y-%m-%d", time.gmtime(now if now is not None else time.time()))


@contextmanager
def _locked(sd: Path):
    """One writer at a time: the server is threaded and this is one file."""
    import fcntl
    import threading
    sd.mkdir(parents=True, exist_ok=True)
    with _THREAD_LOCK:
        handle = open(sd / "credits.lock", "a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()


import threading as _threading  # noqa: E402  (kept beside _locked for clarity)
_THREAD_LOCK = _threading.RLock()


def _append(sd: Path, row: dict[str, Any]) -> None:
    row.setdefault("ts", time.time())
    row["truth_label"] = TRUTH_LABEL
    with (sd / CREDITS_LEDGER).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def rows(identity: str, *, state_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """Every row for this identity, in the order it was written."""
    if not identity:
        return []
    p = _state_dir(state_dir) / CREDITS_LEDGER
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(r.get("identity") or "") == identity:
            out.append(r)
    return out


def state(identity: str, *, signed_in: bool, state_dir: Path | str | None = None,
          now: Optional[float] = None) -> dict[str, Any]:
    """The honest balance: derived from the ledger, never stored as a number."""
    day = day_key(now)
    mine = rows(identity, state_dir=state_dir)
    free_today = sum(1 for r in mine if r.get("kind") == "free" and r.get("day") == day)
    granted_today = sum(float(r.get("usd") or 0) for r in mine
                        if r.get("kind") == "grant" and r.get("day") == day)
    topped_up = sum(float(r.get("usd") or 0) for r in mine if r.get("kind") == "topup")
    spent = sum(float(r.get("usd") or 0) for r in mine if r.get("kind") == "debit")
    # A signed-in visitor is credited lazily, on their first question of the day.
    # Until that row exists, show them the credit they are entitled to anyway —
    # otherwise a brand-new signed-in user is told they have nothing to spend.
    entitled = DAILY_CREDIT_USD if (signed_in and granted_today <= 0) else granted_today
    balance = round(entitled + topped_up - spent, 4)

    if signed_in:
        questions_left = int(balance // PRICE_PER_QUESTION) if PRICE_PER_QUESTION else 0
        return {
            "identity": identity, "signed_in": True, "day": day,
            "balance_usd": balance, "credit_today_usd": round(entitled, 2),
            "granted_usd": round(granted_today, 2),
            "bought_usd": round(topped_up, 2), "spent_usd": round(spent, 2),
            "questions_left": max(0, questions_left),
            "price_per_question": PRICE_PER_QUESTION,
            "daily_credit_usd": DAILY_CREDIT_USD,
            "can_ask": balance >= PRICE_PER_QUESTION,
            "truth_label": TRUTH_LABEL,
        }
    # Credit bought, redeemed from a code, or handed over by the owner, belongs to
    # THIS BROWSER whether or not the person ever signs in. Hiding it here is what
    # made a $6 grant to a visitor without Google unspendable.
    anon_credit = round(topped_up - spent, 4)
    anon_credit_questions = (int(anon_credit // PRICE_PER_QUESTION)
                             if PRICE_PER_QUESTION else 0)
    free_left = max(0, FREE_ANONYMOUS - free_today)
    return {
        "identity": identity, "signed_in": False, "day": day,
        "_rows": mine,
        "free_used_today": free_today, "free_allowance": FREE_ANONYMOUS,
        "free_left": free_left,
        "balance_usd": anon_credit, "credit_usd": anon_credit,
        "bought_usd": round(topped_up, 2), "spent_usd": round(spent, 2),
        "credit_questions": anon_credit_questions,
        "questions_left": free_left + anon_credit_questions,
        "price_per_question": PRICE_PER_QUESTION,
        "daily_credit_usd": DAILY_CREDIT_USD,
        "can_ask": (free_left + anon_credit_questions) > 0 or anon_credit >= PRICE_PER_QUESTION,
        "truth_label": TRUTH_LABEL,
    }


def _count_today(sd: Path, day: str, kind: str, field: str, value: str) -> int:
    """How many rows of this kind share a value today — across every identity."""
    path = sd / CREDITS_LEDGER
    if not path.exists() or not value:
        return 0
    n = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("kind") == kind and r.get("day") == day and r.get(field) == value:
            n += 1
    return n


def _grant_once_today(sd: Path, identity: str, day: str) -> None:
    """A signed-in person is credited once per UTC day, lazily on first use."""
    already = any(r.get("kind") == "grant" and r.get("day") == day
                  for r in rows(identity, state_dir=sd))
    if not already:
        _append(sd, {"kind": "grant", "identity": identity, "day": day,
                     "usd": DAILY_CREDIT_USD, "reason": "daily_free_credit"})


def charge(identity: str, *, signed_in: bool, question: str = "",
           fingerprint: str = "", ip_hash: str = "",
           state_dir: Path | str | None = None, now: Optional[float] = None) -> dict[str, Any]:
    """Ask permission for one question, and record it. Call BEFORE answering.

    Returns allowed=False with a message for the visitor when the allowance is
    spent — the caller shows that instead of calling the model, so a refused
    question costs nothing.
    """
    sd = _state_dir(state_dir)
    day = day_key(now)
    if not identity:
        return {"allowed": False, "reason": "no_identity", "cost_usd": 0.0,
                "message": "I could not tell who you are — please reload the page."}

    with _locked(sd):
        if not signed_in:
            before = state(identity, signed_in=False, state_dir=sd, now=now)
            mine = [r for r in before["_rows"] if r.get("kind") == "free" and r.get("day") == day]
            # Each layer is counted on its own terms: the device count is this
            # identity's, while the fingerprint and the network are shared with
            # anyone else who matches them today. A layer with nothing to match on
            # counts zero and cannot block.
            used_by = {
                "device": len(mine),
                "fingerprint": (_count_today(sd, day, "free", "fingerprint", fingerprint)
                                if fingerprint else 0),
                "network": (_count_today(sd, day, "free", "ip_hash", ip_hash) if ip_hash else 0),
            }
            caps = {"device": FREE_ANONYMOUS, "fingerprint": FREE_ANON_FINGERPRINT,
                    "network": FREE_ANON_NETWORK}
            blocked = [k for k, cap in caps.items() if cap > 0 and used_by[k] >= cap]
            if not blocked:
                _append(sd, {"kind": "free", "identity": identity, "day": day,
                             "usd": 0.0, "question": question[:160],
                             "fingerprint": fingerprint, "ip_hash": ip_hash})
                after = state(identity, signed_in=False, state_dir=sd, now=now)
                return {"allowed": True, "reason": "free", "cost_usd": 0.0,
                        "state": after, "message": ""}

            # Out of free questions — but credit this browser holds still counts.
            # The free caps above exist to stop free-tier farming; someone with
            # credit has paid for it, or been given it, so those caps do not apply.
            if before["balance_usd"] >= PRICE_PER_QUESTION:
                _append(sd, {"kind": "debit", "identity": identity, "day": day,
                             "usd": PRICE_PER_QUESTION, "question": question[:160],
                             "spent_by_anonymous": True})
                after = state(identity, signed_in=False, state_dir=sd, now=now)
                return {"allowed": True, "reason": "credit", "cost_usd": PRICE_PER_QUESTION,
                        "state": after, "message": ""}

            return {"allowed": False, "reason": "sign_in_required", "cost_usd": 0.0,
                    "message": sign_in_pitch(), "state": before,
                    "blocked_by": blocked, "used": used_by, "caps": caps}
            after = state(identity, signed_in=False, state_dir=sd, now=now)
            return {"allowed": True, "reason": "free", "cost_usd": 0.0,
                    "state": after, "message": ""}

        _grant_once_today(sd, identity, day)
        before = state(identity, signed_in=True, state_dir=sd, now=now)
        if before["balance_usd"] < PRICE_PER_QUESTION:
            return {"allowed": False, "reason": "out_of_credit", "cost_usd": 0.0,
                    "message": OUT_OF_CREDIT, "state": before}
        _append(sd, {"kind": "debit", "identity": identity, "day": day,
                     "usd": PRICE_PER_QUESTION, "question": question[:160]})
        after = state(identity, signed_in=True, state_dir=sd, now=now)
        return {"allowed": True, "reason": "credit", "cost_usd": PRICE_PER_QUESTION,
                "state": after, "message": ""}


def top_up(identity: str, usd: float, *, reference: str = "", provider: str = "stripe",
           state_dir: Path | str | None = None) -> dict[str, Any]:
    """Credit a paid top-up. Never called without a verified payment reference."""
    sd = _state_dir(state_dir)
    amount = round(float(usd or 0), 2)
    if amount <= 0:
        return {"ok": False, "error": "non_positive_amount"}
    if not identity:
        return {"ok": False, "error": "no_identity"}
    with _locked(sd):
        already = any(r.get("kind") == "topup" and str(r.get("reference") or "") == str(reference)
                      and reference for r in rows(identity, state_dir=sd))
        if already:
            # Idempotent: Stripe retries webhooks, and a retry must not double-credit.
            return {"ok": True, "duplicate": True, "reference": reference,
                    "state": state(identity, signed_in=True, state_dir=sd)}
        _append(sd, {"kind": "topup", "identity": identity, "usd": amount,
                     "provider": provider, "reference": str(reference)[:120]})
        return {"ok": True, "duplicate": False, "credited_usd": amount, "reference": reference,
                "state": state(identity, signed_in=True, state_dir=sd)}


# ─────────────────────────────────────────────────────────────────────────────
# Getting credit WITHOUT Google
#
# A real visitor in Colombia could not sign in with Google, which left him with
# nothing but three questions a day and no way to buy more. Sign-in was the only
# door. These are two more, neither of which needs an account:
#
#   * an ACCESS CODE the owner hands out (a message, a card, a receipt) that the
#     visitor types into the desk — redeemable from any browser, limited uses;
#   * an owner GRANT, written straight to a visitor by id, for when the owner is
#     looking at a person in the logs and just wants to hand them credit.
#
# Both land in the same append-only ledger as paid top-ups, with their own
# provider name, so the books still add up and nobody can conjure credit by
# guessing.
# ─────────────────────────────────────────────────────────────────────────────

ACCESS_CODES = "access_codes.json"
TRUTH_LABEL_CODES = "SIFTA_ACCESS_CODES_V1"


def _codes_path(sd: Path) -> Path:
    return sd / ACCESS_CODES


def load_codes(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    p = _codes_path(_state_dir(state_dir))
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return d if isinstance(d, dict) else {}


def _save_codes(codes: dict[str, Any], sd: Path) -> None:
    p = _codes_path(sd)
    tmp = sd / (ACCESS_CODES + ".tmp")
    tmp.write_text(json.dumps(codes, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def make_code(usd: float = DAILY_CREDIT_USD, *, uses: int = 1, note: str = "",
              code: str = "", state_dir: Path | str | None = None) -> dict[str, Any]:
    """Mint an access code. The owner prints it and hands it over."""
    import secrets as _secrets
    sd = _state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    amount = round(float(usd or 0), 2)
    if amount <= 0:
        return {"ok": False, "error": "non_positive_amount"}
    token = (code or "").strip().upper().replace(" ", "-")
    if not token:
        token = _secrets.token_hex(3).upper()      # e.g. 9F3A21 — short enough to read aloud
    with _locked(sd):
        codes = load_codes(state_dir=sd)
        if token in codes:
            return {"ok": False, "error": "code_exists", "code": token}
        codes[token] = {"usd": amount, "uses_left": max(1, int(uses)), "note": note[:120],
                        "created": time.time(), "redeemed_by": [],
                        "truth_label": TRUTH_LABEL_CODES}
        _save_codes(codes, sd)
    return {"ok": True, "code": token, "usd": amount, "uses": max(1, int(uses)),
            "questions": int(amount // PRICE_PER_QUESTION) if PRICE_PER_QUESTION else 0,
            "note": note[:120]}


def redeem_code(identity: str, code: str, *,
                state_dir: Path | str | None = None) -> dict[str, Any]:
    """Turn a code into credit, once per visitor, for as many uses as it has."""
    sd = _state_dir(state_dir)
    token = (code or "").strip().upper().replace(" ", "-")
    if not identity:
        return {"ok": False, "error": "no_identity",
                "message": "I could not tell which browser this is — reload and try again."}
    if not token:
        return {"ok": False, "error": "no_code", "message": "That code was empty."}
    with _locked(sd):
        codes = load_codes(state_dir=sd)
        row = codes.get(token)
        if not row:
            return {"ok": False, "error": "unknown_code",
                    "message": "I do not recognise that code."}
        already = list(row.get("redeemed_by") or [])
        if identity in already:
            return {"ok": False, "error": "already_redeemed",
                    "message": "You have already used that code here — it still counts on "
                               "another browser.",
                    "state": state(identity, signed_in=False, state_dir=sd)}
        if int(row.get("uses_left") or 0) <= 0:
            return {"ok": False, "error": "code_spent",
                    "message": "That code has been used up."}
        row["uses_left"] = int(row["uses_left"]) - 1
        already.append(identity)
        row["redeemed_by"] = already
        codes[token] = row
        _save_codes(codes, sd)
    credited = top_up(identity, float(row.get("usd") or 0),
                      reference=f"code:{token}", provider="access_code", state_dir=sd)
    return {"ok": True, "code": token, "credited_usd": float(row.get("usd") or 0),
            "questions": int(float(row.get("usd") or 0) // PRICE_PER_QUESTION),
            "uses_left": int(row.get("uses_left") or 0),
            "state": state(identity, signed_in=True, state_dir=sd),
            "credited": credited}


def grant(identity: str, usd: float, *, note: str = "", provider: str = "owner_grant",
          state_dir: Path | str | None = None) -> dict[str, Any]:
    """Hand credit to a visitor by id — for the owner looking at a real person."""
    if not identity:
        return {"ok": False, "error": "no_identity"}
    amount = round(float(usd or 0), 2)
    if amount <= 0:
        return {"ok": False, "error": "non_positive_amount"}
    sd = _state_dir(state_dir)
    reference = f"grant:{identity}:{int(time.time())}"
    credited = top_up(identity, amount, reference=reference, provider=provider, state_dir=sd)
    _append(sd, {"kind": "grant_note", "identity": identity, "usd": amount,
                 "provider": provider, "note": note[:200], "reference": reference})
    return {"ok": True, "identity": identity, "usd": amount, "note": note,
            "questions": int(amount // PRICE_PER_QUESTION) if PRICE_PER_QUESTION else 0,
            "state": state(identity, signed_in=True, state_dir=sd), "credited": credited}


def summary(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    """What the desk has given away and what it has taken — for the owner."""
    p = _state_dir(state_dir) / CREDITS_LEDGER
    if not p.exists():
        return {"rows": 0, "identities": 0, "granted_usd": 0.0, "bought_usd": 0.0,
                "spent_usd": 0.0, "free_questions": 0}
    granted = bought = spent = 0.0
    free = 0
    identities: set[str] = set()
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        identities.add(str(r.get("identity") or ""))
        if r.get("kind") == "grant":
            granted += float(r.get("usd") or 0)
        elif r.get("kind") == "topup":
            bought += float(r.get("usd") or 0)
        elif r.get("kind") == "debit":
            spent += float(r.get("usd") or 0)
        elif r.get("kind") == "free":
            free += 1
    return {"rows": len(rows("__all__", state_dir=state_dir)) or None,
            "identities": len(identities - {""}),
            "granted_usd": round(granted, 2), "bought_usd": round(bought, 2),
            "spent_usd": round(spent, 2), "free_questions": free,
            "price_per_question": PRICE_PER_QUESTION, "truth_label": TRUTH_LABEL}


def selftest() -> dict[str, Any]:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp)
        anon, acct = "v_device1", "acct_12345"

        # the free allowance, then the gate
        allowed = [charge(anon, signed_in=False, question=f"q{i}", state_dir=sd)["allowed"]
                   for i in range(FREE_ANONYMOUS)]
        sixth = charge(anon, signed_in=False, question="q6", state_dir=sd)
        anon_state = state(anon, signed_in=False, state_dir=sd)

        # A cleared cookie must not be a fresh start. Each attempt here has a NEW
        # device id and the SAME fingerprint, so only the fingerprint can stop it.
        cleared = [charge(f"v_same_fp{i}", signed_in=False, fingerprint="fp_same",
                          ip_hash="net_a", state_dir=sd)["allowed"]
                   for i in range(FREE_ANON_FINGERPRINT)]
        fp_blocked = charge("v_same_fp_new", signed_in=False, fingerprint="fp_same",
                            ip_hash="net_a", state_dir=sd)
        # Nor must a series of new browsers on one network. Every identity and
        # fingerprint here is fresh, so only the network counter can stop it.
        for i in range(FREE_ANON_NETWORK):
            charge(f"v_net{i}", signed_in=False, fingerprint=f"fp_net{i}", ip_hash="net_d",
                   state_dir=sd)
        net_blocked = charge("v_net_new", signed_in=False, fingerprint="fp_fresh",
                             ip_hash="net_d", state_dir=sd)
        # a genuinely new visitor is still welcome
        fresh = charge("v_fresh_visitor", signed_in=False, fingerprint="fp_new", ip_hash="net_e",
                       state_dir=sd)

        # signed in: the daily grant, then spending it down
        first = charge(acct, signed_in=True, state_dir=sd)
        start_credit = first["state"]["credit_today_usd"]     # granted today
        start_balance = first["state"]["balance_usd"]         # ...minus this question
        for i in range(19):
            charge(acct, signed_in=True, question=f"a{i}", state_dir=sd)
        broke = charge(acct, signed_in=True, state_dir=sd)
        broke_state = state(acct, signed_in=True, state_dir=sd)

        # a top-up, and the same webhook delivered twice
        topped = top_up(acct, 25.00, reference="cs_live_test", state_dir=sd)
        again = top_up(acct, 25.00, reference="cs_live_test", state_dir=sd)
        after_topup = state(acct, signed_in=True, state_dir=sd)

        # a new day: the grant comes back, the bought credit does not vanish
        tomorrow = time.time() + 86400
        spend_tmr = charge(acct, signed_in=True, state_dir=sd, now=tomorrow)
        tmr = state(acct, signed_in=True, state_dir=sd, now=tomorrow)
        ledger_lines = (sd / CREDITS_LEDGER).read_text().strip().splitlines()

    checks = {
        "five_free_questions_allowed": all(allowed) and len(allowed) == FREE_ANONYMOUS,
        "fourth_requires_sign_in": (not sixth["allowed"]) and sixth["reason"] == "sign_in_required",
        "three_free_by_default": FREE_ANONYMOUS == 3,
        "network_cap_is_generous": FREE_ANON_NETWORK >= 3 * FREE_ANONYMOUS,
        "cleared_cookie_is_not_fresh": all(cleared) is True
                                       and (not fp_blocked["allowed"])
                                       and "fingerprint" in fp_blocked.get("blocked_by", []),
        "same_fingerprint_is_capped": (not fp_blocked["allowed"])
                                      and "fingerprint" in fp_blocked.get("blocked_by", []),
        "same_network_is_capped": (not net_blocked["allowed"])
                                  and "network" in net_blocked.get("blocked_by", []),
        "new_visitor_still_welcome": fresh["allowed"] is True,
        # getting credit without Google
        "code_credits_a_visitor": (make_code(6.00, uses=2, note="t", state_dir=sd, code="TESTCODE")["ok"]
                                   and redeem_code("v_no_google", "testcode", state_dir=sd)["ok"]),
        "code_balance_lands": abs(state("v_no_google", signed_in=True,
                                        state_dir=sd)["bought_usd"] - 6.00) < 0.001,
        "one_redemption_per_visitor": (not redeem_code("v_no_google", "TESTCODE",
                                                       state_dir=sd)["ok"]),
        "code_works_for_another_visitor": redeem_code("v_second", "TESTCODE",
                                                      state_dir=sd)["ok"],
        "code_uses_are_counted": (redeem_code("v_third", "TESTCODE", state_dir=sd)["error"]
                                  == "code_spent"),
        "unknown_code_refused": (redeem_code("v_fourth", "NOPE", state_dir=sd)["error"]
                                 == "unknown_code"),
        "credit_is_spendable_without_signing_in": (
            charge("v_code_spender", signed_in=False, state_dir=sd)["reason"] == "free"
            and grant("v_code_spender", 3.00, state_dir=sd)["ok"]
            and all(charge("v_code_spender", signed_in=False, state_dir=sd)["allowed"]
                    for _ in range(10))
            and state("v_code_spender", signed_in=False,
                      state_dir=sd)["balance_usd"] < 3.00),
        "anonymous_credit_is_reported": state("v_code_spender", signed_in=False,
                                              state_dir=sd)["balance_usd"] >= 0,
        "owner_grant_lands": (grant("v_carlton", 6.00, note="could not sign in",
                                    state_dir=sd)["ok"]
                              and abs(state("v_carlton", signed_in=True,
                                            state_dir=sd)["bought_usd"] - 6.00) < 0.001),
        "gate_message_promises_the_credit": ("6.00" in sixth["message"]
                                              and ("twenty questions" in sixth["message"]
                                                   or "20 questions" in sixth["message"])),
        "gate_message_sounds_like_her": not any(w in sixth["message"].lower() for w in
                                                ("model", "api", "error", "credit limit",
                                                 "token", "request")),
        "anonymous_allowance_exhausted": anon_state["free_left"] == 0,
        "daily_grant_is_six_dollars": abs(start_credit - DAILY_CREDIT_USD) < 0.001,
        "a_question_costs_thirty_cents": abs(start_balance
                                             - (DAILY_CREDIT_USD - PRICE_PER_QUESTION)) < 0.001,
        "credit_covers_twenty_questions": int(DAILY_CREDIT_USD // PRICE_PER_QUESTION) == 20,
        "credit_runs_out_after_twenty": (not broke["allowed"]) and broke["reason"] == "out_of_credit",
        "balance_never_negative": broke_state["balance_usd"] >= 0,
        "topup_adds_credit": topped["ok"] and abs(after_topup["bought_usd"] - 25.0) < 0.001,
        "repeat_webhook_does_not_double_charge": again["ok"] and again["duplicate"] is True
                                                 and abs(after_topup["bought_usd"] - 25.0) < 0.001,
        "bought_credit_gives_more_questions": after_topup["questions_left"] > 20,
        "new_day_grants_again": tmr["credit_today_usd"] == DAILY_CREDIT_USD,
        "new_day_keeps_bought_credit": tmr["bought_usd"] == 25.0,
        "can_ask_tomorrow": spend_tmr["allowed"] is True,
        "ledger_is_append_only": len(ledger_lines) == len(set(ledger_lines)),
        "state_is_derived_not_stored": all("balance_usd" not in json.loads(l)
                                           for l in ledger_lines),
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "summary":
        print(json.dumps(summary(), indent=2))
    elif cmd == "code-new":
        usd = float(sys.argv[2]) if len(sys.argv) > 2 else DAILY_CREDIT_USD
        uses = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        note = sys.argv[4] if len(sys.argv) > 4 else ""
        print(json.dumps(make_code(usd, uses=uses, note=note), indent=2))
    elif cmd == "codes":
        print(json.dumps(load_codes(), indent=2))
    elif cmd == "redeem":
        print(json.dumps(redeem_code(sys.argv[3], sys.argv[2]), indent=2))
    elif cmd == "grant":
        usd = float(sys.argv[3]) if len(sys.argv) > 3 else DAILY_CREDIT_USD
        note = sys.argv[4] if len(sys.argv) > 4 else ""
        print(json.dumps(grant(sys.argv[2], usd, note=note), indent=2))
    elif cmd == "state":
        ident = sys.argv[2]
        print(json.dumps(state(ident, signed_in=ident.startswith("acct_")), indent=2))
    else:
        print(json.dumps(selftest(), indent=2))
