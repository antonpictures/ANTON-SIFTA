"""STGM metabolism — the organism's crypto-information economy.

Owner directive (George, 2026-09-30):

    "supposed to be real STGM as part of her metabolism, no double spending,
     just like bitcoin ... the swimmers inside her body trade crypto +
     information carried so they can survive reality, for the organism."

What that requires, and what this module implements:

  * REAL LEDGER, NOT ROLEPLAY. Every unit is an append-only, hash-chained
    transaction. A printed receipt that is not in this chain does not exist.
  * NO DOUBLE SPENDING. Three independent guards: balances are derived by
    folding the chain (a sender can never go negative), every txid is unique
    (a signed transaction cannot be replayed), and the chain is hash-linked so
    a rewritten history fails validation.
  * INFORMATION IS THE POINT. A transfer must carry a payload: the information
    the swimmer is carrying. The information is content-addressed, so the
    ledger records what was actually traded, not just how much.
  * METABOLISM, NOT FAUCET. Minting requires a work_receipt that EXISTS in a
    real receipt ledger. This is the structural answer to a fabricated
    "STGM minted: +9.8" line: no receipt, no mint.
  * SURVIVE REALITY. Burn is first-class: energy is spent, not only earned, so
    the organism can starve and recover instead of inflating forever.

Ledger: STGM_METABOLISM_LEDGER
Keys:   STGM_SWIMMER_KEYS
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Mapping

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

STGM_METABOLISM_LEDGER = "stgm_metabolism_ledger.jsonl"
STGM_SWIMMER_KEYS = "stgm_swimmer_keys.json"
TRUTH_LABEL = "STGM_METABOLISM_V1"

# Ledgers a mint may cite as proof of work. A work receipt that is not in one of
# these does not exist, and an unbacked mint is refused.
RECEIPT_LEDGERS = (
    "work_receipts.jsonl",
    "agent_arm_receipts.jsonl",
    "ide_stigmergic_trace.jsonl",
    "episodic_diary.jsonl",
    "stgm_metabolism_ledger.jsonl",
)

KINDS = ("MINT", "TRANSFER", "BURN")
GENESIS_RECEIPT = "genesis:organism"

# Bounded so a swimmer cannot smuggle an unbounded blob through the economy.
MAX_PAYLOAD_BYTES = 4096


# --------------------------------------------------------------------------
# Canonical form, hashing, signing
# --------------------------------------------------------------------------

def _canonical(row: Mapping[str, Any]) -> bytes:
    """Deterministic bytes for content identity and signing.

    ``prev`` is excluded deliberately. A txid must be CONTENT identity: if chain
    position were hashed into it, replaying the exact same signed transaction at
    a new tip would produce a different txid, slip past the duplicate check, and
    spend the same units twice. Position is bound separately by ``chain``, which
    mixes ``prev`` with the txid.
    """
    body = {k: v for k, v in row.items() if k not in ("sig", "txid", "chain", "prev")}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _txid(row: Mapping[str, Any]) -> str:
    return _digest(_canonical(row))[:32]


def _chain_hash(prev_chain: str, txid: str) -> str:
    return _digest(f"{prev_chain}:{txid}".encode("utf-8"))[:32]


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _ledger_path(sd: Path) -> Path:
    return sd / STGM_METABOLISM_LEDGER


def _keys_path(sd: Path) -> Path:
    return sd / STGM_SWIMMER_KEYS


@contextmanager
def _exclusive(sd: Path):
    """Serialise writers so two swimmers cannot spend the same unit concurrently."""
    sd.mkdir(parents=True, exist_ok=True)
    lock = sd / (STGM_METABOLISM_LEDGER + ".lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
        except Exception:
            pass  # non-POSIX: the append+validate path still refuses negatives
        yield
    finally:
        try:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)
        except Exception:
            pass
        os.close(fd)


# --------------------------------------------------------------------------
# Swimmer keys
# --------------------------------------------------------------------------

def _load_keys(sd: Path) -> dict[str, str]:
    path = _keys_path(sd)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def _save_keys(sd: Path, keys: Mapping[str, str]) -> None:
    path = _keys_path(sd)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(dict(keys), indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def enroll_swimmer(swimmer_id: str, *, state_dir: Path | str | None = None) -> str:
    """Give a swimmer a signing key. Idempotent; returns the key fingerprint."""
    sd = _state_dir(state_dir)
    with _exclusive(sd):
        keys = _load_keys(sd)
        if swimmer_id not in keys:
            keys[swimmer_id] = secrets.token_hex(32)
            _save_keys(sd, keys)
        return _digest(keys[swimmer_id].encode("utf-8"))[:16]


def _sign(row: Mapping[str, Any], key: str) -> str:
    return hmac.new(key.encode("utf-8"), _canonical(row), hashlib.sha256).hexdigest()



# --------------------------------------------------------------------------
# Hardware seal — a swimmer key must prove the BODY, not just the file
# --------------------------------------------------------------------------

STGM_HW_SEAL = "stgm_hardware_seal.json"
_HW_SALT_NAME = "stgm_hw_salt"


def hardware_identity() -> dict[str, str]:
    """This body's hardware identity: platform serial, UUID, and the seal name."""
    import platform
    import subprocess

    serial, uuid = "", ""
    try:
        out = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        for line in out.splitlines():
            if "IOPlatformSerialNumber" in line:
                serial = line.split("=")[-1].strip().strip('"')
            elif "IOPlatformUUID" in line:
                uuid = line.split("=")[-1].strip().strip('"')
    except Exception:
        pass  # non-macOS or restricted: the seal degrades, it does not lie
    seal = ""
    try:
        alice = _STATE / "ALICE_M5.json"
        if alice.exists():
            seal = str(json.loads(alice.read_text(encoding="utf-8")).get("architect_seal") or "")
    except Exception:
        seal = ""
    return {
        "homeworld_serial": serial,
        "platform_uuid": uuid,
        "architect_seal": seal,
        "node": platform.node(),
    }


def _hardware_secret(sd: Path) -> bytes:
    """Key material bound to this physical body, not to a portable file.

    A random salt is stored beside the state; the serial and UUID come from the
    hardware. Copying the state directory to another machine therefore does NOT
    reproduce the keys, which is the point: a swimmer receipt has to prove it
    came from this body.
    """
    salt_path = sd / _HW_SALT_NAME
    if not salt_path.exists():
        sd.mkdir(parents=True, exist_ok=True)
        fd = os.open(salt_path, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(secrets.token_hex(32))
    salt = salt_path.read_text(encoding="utf-8").strip()
    hw = hardware_identity()
    material = f"{hw['homeworld_serial']}|{hw['platform_uuid']}|{salt}"
    return hashlib.sha256(material.encode("utf-8")).digest()


def hardware_bound_key(swimmer_id: str, *, state_dir: Path | str | None = None) -> str:
    """Deterministic signing key derived from this body's hardware."""
    sd = _state_dir(state_dir)
    return hmac.new(_hardware_secret(sd), f"stgm-swimmer:{swimmer_id}".encode("utf-8"), hashlib.sha256).hexdigest()


def bind_hardware(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    """Re-derive every enrolled swimmer's key from the hardware seal.

    Refuses once any row is signed, because rebinding would invalidate those
    signatures: a chain that has spoken with the old keys must keep them.
    """
    sd = _state_dir(state_dir)
    signed = [r for r in read_chain(state_dir=sd) if r.get("signer")]
    if signed:
        raise Rejected("CHAIN_ALREADY_SIGNED", f"{len(signed)} signed rows would be invalidated")

    keys = _load_keys(sd)
    for swimmer in list(keys):
        keys[swimmer] = hardware_bound_key(swimmer, state_dir=sd)
    _save_keys(sd, keys)

    hw = hardware_identity()
    seal = {
        "ts": time.time(),
        "hardware": hw,
        "bound_swimmers": sorted(keys),
        "scheme": "HMAC-SHA256(hw(serial|uuid|local_salt), 'stgm-swimmer:<id>')",
        "portable": False,
        "note": "keys do not travel with the state directory; they are derived from this body",
        "truth_label": "STGM_HARDWARE_SEAL_V1",
    }
    path = sd / STGM_HW_SEAL
    os.chmod(path.parent, 0o700) if False else None
    path.write_text(json.dumps(seal, indent=2, ensure_ascii=False), encoding="utf-8")
    os.chmod(path, 0o600)
    return seal


def verify_hardware_binding(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    """Do the stored keys still derive from THIS body?"""
    sd = _state_dir(state_dir)
    keys = _load_keys(sd)
    mismatched = [s for s, k in keys.items() if not hmac.compare_digest(k, hardware_bound_key(s, state_dir=sd))]
    seal_path = sd / STGM_HW_SEAL
    recorded = json.loads(seal_path.read_text(encoding="utf-8")) if seal_path.exists() else {}
    now = hardware_identity()
    return {
        "bound": not mismatched,
        "swimmers": len(keys),
        "mismatched": mismatched,
        "serial_matches_seal": recorded.get("hardware", {}).get("homeworld_serial") == now["homeworld_serial"],
        "homeworld_serial": now["homeworld_serial"],
        "architect_seal": now["architect_seal"],
        "truth_label": "STGM_HARDWARE_SEAL_V1",
    }


# --------------------------------------------------------------------------
# Reading the chain
# --------------------------------------------------------------------------

def read_chain(*, state_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """Every transaction, oldest first."""
    path = _ledger_path(_state_dir(state_dir))
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _receipt_exists(receipt_id: str, sd: Path) -> bool:
    """Is this receipt actually in a receipt ledger? Existence is the whole test."""
    if not receipt_id:
        return False
    needle = f'"{receipt_id}"'
    for name in RECEIPT_LEDGERS:
        path = sd / name
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if needle in line or receipt_id in line:
                        return True
        except OSError:
            continue
    return False


def balances(*, state_dir: Path | str | None = None, chain: list[dict[str, Any]] | None = None) -> dict[str, float]:
    """Fold the chain into per-swimmer balances. Deterministic and replayable."""
    rows = read_chain(state_dir=state_dir) if chain is None else chain
    out: dict[str, float] = {}
    for row in rows:
        kind = row.get("kind")
        amount = float(row.get("amount") or 0.0)
        frm = str(row.get("from") or "")
        to = str(row.get("to") or "")
        if kind == "MINT" and to:
            out[to] = out.get(to, 0.0) + amount
        elif kind == "TRANSFER":
            if frm:
                out[frm] = out.get(frm, 0.0) - amount
            if to:
                out[to] = out.get(to, 0.0) + amount
        elif kind == "BURN" and frm:
            out[frm] = out.get(frm, 0.0) - amount
    return {k: round(v, 9) for k, v in sorted(out.items()) if round(v, 9) != 0.0}


def supply(*, state_dir: Path | str | None = None, chain: list[dict[str, Any]] | None = None) -> dict[str, float]:
    """Circulating supply, minted total, and burned total."""
    rows = read_chain(state_dir=state_dir) if chain is None else chain
    minted = sum(float(r.get("amount") or 0.0) for r in rows if r.get("kind") == "MINT")
    burned = sum(float(r.get("amount") or 0.0) for r in rows if r.get("kind") == "BURN")
    return {"minted": round(minted, 9), "burned": round(burned, 9), "circulating": round(minted - burned, 9)}


# --------------------------------------------------------------------------
# Writing the chain
# --------------------------------------------------------------------------

class Rejected(Exception):
    """A transaction the metabolism refuses. Carries a stable reason code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _append(row: dict[str, Any], sd: Path, signer: str | None) -> dict[str, Any]:
    """Validate against the current chain, then append. One writer at a time.

    Ordering is load-bearing: every field that will be stored must exist BEFORE
    the txid is derived, because the txid is a hash of the stored body. A field
    added after derivation makes the stored txid disagree with any later
    recomputation, and the whole chain then fails validation.
    """
    with _exclusive(sd):
        rows = read_chain(state_dir=sd)
        prev_chain = str(rows[-1].get("chain") or "0" * 32) if rows else "0" * 32

        # 1. chain linkage and payload - stored body, so before the txid
        row["prev"] = prev_chain
        payload = row.get("payload") or {}
        if not payload:
            raise Rejected("NO_INFORMATION", "a trade must carry information, not only value")
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(raw) > MAX_PAYLOAD_BYTES:
            raise Rejected("PAYLOAD_TOO_LARGE", f"{len(raw)} > {MAX_PAYLOAD_BYTES} bytes")
        row["payload_digest"] = _digest(raw)
        row["ts"] = float(row.get("ts") or time.time())
        # The signer is part of the stored body, so it precedes the txid exactly
        # like every other persisted field.
        if signer is not None:
            row["signer"] = signer
            row["homeworld_serial"] = hardware_identity()["homeworld_serial"]

        # 2. metabolism: a mint must be backed by a receipt that exists
        if row.get("kind") == "MINT":
            receipt = str(row.get("work_receipt") or "")
            if receipt != GENESIS_RECEIPT and not _receipt_exists(receipt, sd):
                raise Rejected("UNBACKED_MINT", f"work receipt {receipt!r} exists in no receipt ledger")

        # 3. the stored body is now final, so the identity can be derived
        txid = _txid(row)
        if any(r.get("txid") == txid for r in rows):
            raise Rejected("DOUBLE_SPEND", f"transaction {txid} is already in the chain")

        # 4. fold first, then judge: a swimmer may spend only what the chain supports
        projected = balances(chain=rows + [row])
        for swimmer, amount in projected.items():
            if amount < 0:
                raise Rejected("INSUFFICIENT_BALANCE", f"{swimmer} would hold {amount}")

        # 5. linkage, then signature over the final body
        row["txid"] = txid
        row["chain"] = _chain_hash(prev_chain, txid)
        if signer is not None:
            keys = _load_keys(sd)
            if signer not in keys:
                raise Rejected("NO_KEY", f"{signer} is not enrolled")
            row["sig"] = _sign(row, keys[signer])

        path = _ledger_path(sd)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row


def seal_genesis(allocations: Mapping[str, float], *, state_dir: Path | str | None = None, note: str = "") -> list[dict[str, Any]]:
    """One-time: mint the initial supply. Refused once the chain exists."""
    sd = _state_dir(state_dir)
    if read_chain(state_dir=sd):
        raise Rejected("GENESIS_ALREADY_SEALED", "the chain already has transactions")
    out = []
    for swimmer, amount in allocations.items():
        if float(amount) <= 0:
            raise Rejected("INVALID_AMOUNT", f"{swimmer}: {amount}")
        enroll_swimmer(swimmer, state_dir=sd)
        out.append(_append(
            {
                "kind": "MINT",
                "from": "organism",
                "to": swimmer,
                "amount": round(float(amount), 9),
                "work_receipt": GENESIS_RECEIPT,
                "affect": "genesis",
                "payload": {"information": note or "initial metabolic endowment", "kind": "GENESIS"},
            },
            sd,
            None,
        ))
    return out


def mint(
    to: str,
    amount: float,
    *,
    work_receipt: str,
    affect: str = "",
    information: str = "",
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Mint against a real work receipt. No receipt, no mint."""
    sd = _state_dir(state_dir)
    enroll_swimmer(to, state_dir=sd)
    return _append(
        {
            "kind": "MINT",
            "from": "organism",
            "to": to,
            "amount": round(float(amount), 9),
            "work_receipt": work_receipt,
            "affect": affect,
            "payload": {"information": information or f"work:{work_receipt}", "kind": "WORK"},
        },
        sd,
        None,
    )


def transfer(
    frm: str,
    to: str,
    amount: float,
    *,
    information: str,
    kind: str = "OBSERVATION",
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Move value AND the information carried, signed by the sender."""
    sd = _state_dir(state_dir)
    enroll_swimmer(to, state_dir=sd)
    if float(amount) <= 0:
        raise Rejected("INVALID_AMOUNT", str(amount))
    return _append(
        {
            "kind": "TRANSFER",
            "from": frm,
            "to": to,
            "amount": round(float(amount), 9),
            "payload": {"information": information, "kind": kind},
        },
        sd,
        frm,
    )


def burn(frm: str, amount: float, *, reason: str, state_dir: Path | str | None = None) -> dict[str, Any]:
    """Spend energy out of existence. Starvation must be possible."""
    sd = _state_dir(state_dir)
    if float(amount) <= 0:
        raise Rejected("INVALID_AMOUNT", str(amount))
    return _append(
        {
            "kind": "BURN",
            "from": frm,
            "to": "",
            "amount": round(float(amount), 9),
            "payload": {"information": reason, "kind": "BURN"},
        },
        sd,
        frm,
    )


# --------------------------------------------------------------------------
# Validation — the double-spend and integrity proof
# --------------------------------------------------------------------------

def validate_chain(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    """Re-derive the whole chain: links, signatures, uniqueness, solvency."""
    sd = _state_dir(state_dir)
    rows = read_chain(state_dir=sd)
    keys = _load_keys(sd)
    problems: list[dict[str, Any]] = []
    seen: set[str] = set()
    prev = "0" * 32

    for index, row in enumerate(rows):
        txid = str(row.get("txid") or "")
        if row.get("prev") != prev:
            problems.append({"index": index, "error": "BROKEN_LINK", "txid": txid})
        expected = _chain_hash(prev, _txid(row))
        if row.get("chain") != expected:
            problems.append({"index": index, "error": "CHAIN_HASH_MISMATCH", "txid": txid})
        if txid in seen:
            problems.append({"index": index, "error": "DUPLICATE_TXID", "txid": txid})
        seen.add(txid)
        signer = row.get("signer")
        if signer is not None:
            key = keys.get(str(signer))
            if key is None:
                problems.append({"index": index, "error": "UNKNOWN_SIGNER", "txid": txid})
            elif not hmac.compare_digest(str(row.get("sig") or ""), _sign(row, key)):
                problems.append({"index": index, "error": "BAD_SIGNATURE", "txid": txid})
        if row.get("kind") not in KINDS:
            problems.append({"index": index, "error": "UNKNOWN_KIND", "txid": txid})
        prev = str(row.get("chain") or prev)

    negative = {k: v for k, v in balances(state_dir=sd, chain=rows).items() if v < 0}
    for swimmer, amount in negative.items():
        problems.append({"error": "NEGATIVE_BALANCE", "swimmer": swimmer, "amount": amount})

    s = supply(state_dir=sd, chain=rows)
    accounted = round(sum(v for v in balances(state_dir=sd, chain=rows).values()) + s["burned"], 9)
    if round(accounted - s["minted"], 6) != 0:
        problems.append({"error": "SUPPLY_MISMATCH", "minted": s["minted"], "accounted": accounted})

    return {
        "ok": not problems,
        "transactions": len(rows),
        "problems": problems,
        "supply": s,
        "balances": balances(state_dir=sd, chain=rows),
        "truth_label": TRUTH_LABEL,
    }


def verify_receipt(receipt_or_txid: str, *, state_dir: Path | str | None = None) -> dict[str, Any]:
    """Is this claimed receipt backed by the metabolism? NEVER guesses."""
    sd = _state_dir(state_dir)
    needle = str(receipt_or_txid or "").strip()
    if not needle:
        return {"status": "UNBACKED", "reason": "empty receipt id", "backed": False}
    for row in read_chain(state_dir=sd):
        if needle in (str(row.get("txid")), str(row.get("work_receipt"))):
            return {
                "status": "BACKED",
                "backed": True,
                "txid": row.get("txid"),
                "kind": row.get("kind"),
                "amount": row.get("amount"),
                "to": row.get("to"),
            }
    return {
        "status": "UNBACKED",
        "backed": False,
        "reason": "no transaction in the metabolism ledger carries this id",
        "truth_label": TRUTH_LABEL,
    }


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

def selftest() -> dict[str, Any]:
    """Prove the metabolism on a scratch chain: solvent, unique, linked, backed."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp)

        # a real receipt must exist before it can back a mint
        (sd / "work_receipts.jsonl").write_text(
            json.dumps({"round_id": "selftest", "receipt_id": "real-receipt-1"}) + "\n", encoding="utf-8"
        )

        seal_genesis({"alice": 100.0, "mimo": 10.0}, state_dir=sd)

        def rejected(fn) -> str:
            try:
                fn()
                return ""
            except Rejected as exc:
                return exc.code

        unbacked = rejected(lambda: mint("alice", 9.8, work_receipt="7a515b9e", affect="Ontological Collapse", state_dir=sd))
        backed = mint("alice", 5.0, work_receipt="real-receipt-1", affect="clarity", information="found a defect", state_dir=sd)
        overspend = rejected(lambda: transfer("mimo", "alice", 999.0, information="too much", state_dir=sd))
        trade = transfer("alice", "mimo", 25.0, information="the defect is in the picker", kind="LESSON", state_dir=sd)
        replay = rejected(lambda: _append(dict(trade), sd, "alice"))
        burned = burn("mimo", 3.0, reason="metabolic cost of the lesson", state_dir=sd)

        good = validate_chain(state_dir=sd)
        bal = balances(state_dir=sd)

        # tamper: rewrite one row's amount and re-validate
        path = _ledger_path(sd)
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        rows[-1]["amount"] = 99999.0
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        tampered = validate_chain(state_dir=sd)

        vr = verify_receipt(trade["txid"], state_dir=sd)
        vb = verify_receipt("7a515b9e", state_dir=sd)

    checks = {
        "genesis_supplies": bal.get("alice") is not None,
        "fabricated_mint_refused": unbacked == "UNBACKED_MINT",
        "backed_mint_accepted": backed.get("amount") == 5.0,
        "overspend_refused": overspend == "INSUFFICIENT_BALANCE",
        "replay_refused": replay == "DOUBLE_SPEND",
        "trade_carries_information": trade.get("payload", {}).get("information") == "the defect is in the picker",
        "payload_content_addressed": bool(trade.get("payload_digest")),
        "burn_reduces_supply": good["supply"]["burned"] == 3.0,
        "chain_valid_after_trades": good["ok"] is True,
        "tamper_detected": tampered["ok"] is False,
        "real_receipt_backed": vr["status"] == "BACKED",
        "fake_receipt_unbacked": vb["status"] == "UNBACKED",
        "conservation_holds": round(sum(bal.values()) + 3.0 - 115.0, 6) == 0,
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


def main(argv: Iterable[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    if not args or args[0] == "selftest":
        print(json.dumps(selftest(), indent=2))
        return 0
    if args[0] == "balances":
        print(json.dumps(balances(), indent=2))
        return 0
    if args[0] == "supply":
        print(json.dumps(supply(), indent=2))
        return 0
    if args[0] == "validate":
        print(json.dumps(validate_chain(), indent=2, ensure_ascii=False))
        return 0
    if args[0] == "seal":
        print(json.dumps(bind_hardware(), indent=2, ensure_ascii=False))
        return 0
    if args[0] == "verify-bind":
        print(json.dumps(verify_hardware_binding(), indent=2, ensure_ascii=False))
        return 0
    if args[0] == "receipt":
        if len(args) < 2:
            print("usage: receipt <id>")
            return 2
        print(json.dumps(verify_receipt(args[1]), indent=2, ensure_ascii=False))
        return 0
    if args[0] == "chain":
        print(json.dumps(read_chain()[-10:], indent=2, ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
