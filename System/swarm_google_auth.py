"""swarm_google_auth — "Continue with Google" for the finance desk.

Owner request: let visitors sign in so their chat history follows their account.

The pieces: a Google OAuth 2.0 web client, a signed session, and a link between a
Google account and the visitor records the desk already keeps.

What signing in actually changes, stated plainly: history already works per
browser. Signing in makes that history follow the PERSON — phone, laptop, new
browser — by migrating the device's conversations onto an account identity and
then trusting that identity on every later visit.

Security rules this module keeps:

  * The client secret lives in a 0600 file inside .sifta_state/, which git
    ignores, and is never written to a log, a receipt or a page.
  * `state` is random per login and echoed back, so a callback cannot be forged.
  * The account cookie is HMAC-signed with a local secret, so it cannot be
    hand-made by a visitor.
  * The account identity comes only from Google's verified `sub` claim, never
    from a value a visitor supplied.

Setup note: the Google client must have the redirect URI registered or the flow
returns redirect_uri_mismatch — see REDIRECT_URI below.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

CLIENT_FILE = "google_oauth_client.json"
ACCOUNTS_LEDGER = "google_accounts.jsonl"
ACCOUNTS_INDEX = "google_accounts.json"
SESSION_SALT = "auth_session_salt"
TRUTH_LABEL = "SIFTA_GOOGLE_AUTH_V1"

REDIRECT_URI = "https://stigmergicoin.com/api/auth/google/callback"
SCOPE = "openid email profile"
ACCT_PREFIX = "acct_"
SESSION_COOKIE = "sifta_acct"


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


# ── credentials ────────────────────────────────────────────────────────────

def client(*, state_dir: Path | str | None = None) -> dict[str, str]:
    """The OAuth client. Returns {} when not configured; never logs the secret."""
    p = _state_dir(state_dir) / CLIENT_FILE
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    k = raw.get("web") or raw.get("installed") or {}
    cid, sec = str(k.get("client_id") or ""), str(k.get("client_secret") or "")
    return {
        "client_id": cid,
        "client_secret": sec,
        "auth_uri": str(k.get("auth_uri") or "https://accounts.google.com/o/oauth2/auth"),
        "token_uri": str(k.get("token_uri") or "https://oauth2.googleapis.com/token"),
        "project_id": str(k.get("project_id") or ""),
        "configured": bool(cid and sec),
        "redirect_uris": list(k.get("redirect_uris") or []),
    }


def redirect_uri_registered(*, state_dir: Path | str | None = None) -> bool:
    c = client(state_dir=state_dir)
    return REDIRECT_URI in (c.get("redirect_uris") or [])


# ── the OAuth dance ────────────────────────────────────────────────────────

def authorize_url(state: str, *, redirect_uri: str = REDIRECT_URI,
                  state_dir: Path | str | None = None) -> str:
    c = client(state_dir=state_dir)
    if not c.get("configured"):
        return ""
    q = urllib.parse.urlencode({
        "client_id": c["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    })
    return f"{c['auth_uri']}?{q}"


def _post_form(url: str, fields: dict[str, str], timeout: float = 20.0) -> dict[str, Any]:
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "ignore")[:400]
        except Exception:
            pass
        return {"error": "http_error", "status": exc.code, "detail": detail}
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _get_json(url: str, token: str, timeout: float = 20.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError,
            json.JSONDecodeError) as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def exchange_code(code: str, *, redirect_uri: str = REDIRECT_URI,
                  state_dir: Path | str | None = None) -> dict[str, Any]:
    c = client(state_dir=state_dir)
    if not c.get("configured"):
        return {"error": "not_configured"}
    return _post_form(c["token_uri"], {
        "code": code,
        "client_id": c["client_id"],
        "client_secret": c["client_secret"],
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    })


def userinfo(access_token: str, timeout: float = 20.0) -> dict[str, Any]:
    return _get_json("https://openidconnect.googleapis.com/v1/userinfo", access_token, timeout)


# ── accounts ───────────────────────────────────────────────────────────────

def _salt(sd: Path) -> str:
    p = sd / SESSION_SALT
    if not p.exists():
        sd.mkdir(parents=True, exist_ok=True)
        fd = os.open(p, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(secrets.token_hex(32))
    return p.read_text(encoding="utf-8").strip()


def sign_session(account_id: str, *, state_dir: Path | str | None = None) -> str:
    sd = _state_dir(state_dir)
    mac = hmac.new(_salt(sd).encode(), account_id.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{account_id}.{mac}"


def verify_session(value: str, *, state_dir: Path | str | None = None) -> str:
    """Return the account id only if the cookie's signature is ours."""
    if not value or "." not in value:
        return ""
    acct, _, mac = value.rpartition(".")
    if not acct:
        return ""
    expected = sign_session(acct, state_dir=state_dir).rpartition(".")[2]
    return acct if hmac.compare_digest(mac, expected) else ""


def new_state() -> str:
    return secrets.token_urlsafe(24)


def account_id_for(sub: str) -> str:
    return f"{ACCT_PREFIX}{sub}"


def load_accounts(*, state_dir: Path | str | None = None) -> dict[str, dict[str, Any]]:
    p = _state_dir(state_dir) / ACCOUNTS_INDEX
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): v for k, v in d.items()} if isinstance(d, dict) else {}


def save_accounts(accounts: dict[str, dict[str, Any]], sd: Path) -> None:
    p = sd / ACCOUNTS_INDEX
    p.write_text(json.dumps(accounts, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def link_account(
    *,
    visitor_id: str,
    sub: str,
    email: str = "",
    name: str = "",
    picture: str = "",
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Attach a Google account to this browser, migrating its history onto it.

    The account id is derived from Google's verified `sub`, so it is stable and
    cannot be chosen by the visitor.
    """
    sd = _state_dir(state_dir)
    acct = account_id_for(sub)
    accounts = load_accounts(state_dir=sd)
    row = accounts.get(acct, {})
    row.update({
        "account_id": acct,
        "sub": sub,
        "email": email,
        "name": name,
        "picture": picture,
        "first_seen": row.get("first_seen", time.time()),
        "last_login": time.time(),
        "truth_label": TRUTH_LABEL,
    })
    devices = set(row.get("devices", []))
    migrated = 0
    if visitor_id and visitor_id != acct:
        devices.add(visitor_id)
        # Hold the index guard across the whole migration: it reads, edits and
        # rewrites the shared index, and a page load landing in the middle used
        # to overwrite it.
        from System.swarm_visitor_memory import _index_guard
        with _index_guard(sd):
            migrated = migrate_history(visitor_id, acct, state_dir=sd)
    row["devices"] = sorted(devices)
    accounts[acct] = row
    save_accounts(accounts, sd)

    with (sd / ACCOUNTS_LEDGER).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": time.time(), "kind": "GOOGLE_SIGNIN", "account_id": acct,
                             "email": email, "name": name, "device": visitor_id,
                             "conversations_migrated": migrated, "truth_label": TRUTH_LABEL},
                            ensure_ascii=False) + "\n")
    return {"account_id": acct, "email": email, "name": name, "picture": picture,
            "migrated_conversations": migrated, "devices": row["devices"]}


def migrate_history(from_visitor: str, to_visitor: str, *,
                    state_dir: Path | str | None = None) -> int:
    """Move a device's conversations onto the account, so nothing is lost.

    It also CREATES the account's row when the device has nothing to migrate.
    That case is the common one — sign in, then chat — and without the row every
    later save keyed to the account was dropped in silence, which is exactly what
    a signed-in visitor experienced as "my chats were never saved".
    """
    try:
        from System.swarm_visitor_memory import load_index, _blank_visitor, _save_index, _index_guard
    except Exception:
        return 0
    sd = _state_dir(state_dir)
    index = load_index(state_dir=sd)
    src = index.get(from_visitor)
    created = to_visitor not in index
    if created:
        index[to_visitor] = _blank_visitor(to_visitor)
        index[to_visitor]["identified_as"] = (src or {}).get("identified_as", "")
    if not src or not src.get("conversations"):
        if created:
            _save_index(index, sd)
        return 0
    dst = index.get(to_visitor) or {
        "visitor_id": to_visitor, "first_seen": src.get("first_seen", time.time()),
        "last_seen": src.get("last_seen", time.time()), "visits": 1,
        "ip_hashes_seen": [], "user_agents": [], "referrers": [], "languages": [],
        "paths": [], "conversations": {}, "exchanges": [], "note": "",
        "identified_as": src.get("identified_as", ""),
    }
    convs = dst.setdefault("conversations", {})
    moved = 0
    for cid, c in (src.get("conversations") or {}).items():
        if cid not in convs:
            convs[cid] = c
            moved += 1
    dst["exchanges"] = (dst.get("exchanges", []) + src.get("exchanges", []))[-200:]
    dst["topics_discussed"] = sorted(set(dst.get("topics_discussed", [])) |
                                     set(src.get("topics_discussed", [])))
    dst["account_id"] = to_visitor
    index[to_visitor] = dst
    _save_index(index, sd)
    return moved


def account(account_id: str, *, state_dir: Path | str | None = None) -> dict[str, Any]:
    return load_accounts(state_dir=state_dir).get(account_id, {})


def selftest() -> dict[str, Any]:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp)
        c = client(state_dir=sd)
        state = new_state()
        url = authorize_url(state, state_dir=sd)
        sig = sign_session("acct_12345", state_dir=sd)
        good = verify_session(sig, state_dir=sd)
        forged = verify_session("acct_99999." + sig.rpartition(".")[2], state_dir=sd)
        bad = verify_session("acct_12345.deadbeef", state_dir=sd)
        info = link_account(visitor_id="v_dev1", sub="12345", email="a@b.com",
                            name="Tester", state_dir=sd)
        acct = account("acct_12345", state_dir=sd)
    checks = {
        "client_file_absent_is_safe": c == {},
        "no_url_without_credentials": url == "",
        "state_is_random": len(state) >= 20 and new_state() != state,
        "signature_roundtrips": good == "acct_12345",
        "forged_account_rejected": forged == "",
        "garbage_signature_rejected": bad == "",
        "account_linked": info["account_id"] == "acct_12345" and acct.get("email") == "a@b.com",
        "account_id_from_sub": info["account_id"].endswith("12345"),
        "secret_never_returned": "client_secret" not in json.dumps(info),
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "status":
        c = client()
        print(json.dumps({
            "configured": c.get("configured", False),
            "client_id": c.get("client_id", ""),
            "redirect_uri_expected": REDIRECT_URI,
            "redirect_uri_registered": redirect_uri_registered(),
            "registered_uris": c.get("redirect_uris", []),
            "accounts": len(load_accounts()),
            "truth_label": TRUTH_LABEL,
        }, indent=2))
    elif cmd == "selftest":
        print(json.dumps(selftest(), indent=2))
    else:
        print("usage: status | selftest")
