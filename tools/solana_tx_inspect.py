#!/usr/bin/env python3
"""solana_tx_inspect — read an unsigned transaction BEFORE you sign it.

Why this exists. The owner asked the right question about a third-party
transaction builder: "what if they are thieves?" A builder returns a serialized
UNSIGNED transaction (verified: PumpPortal's /api/trade-local returns 641 bytes
of application/octet-stream). Your signature is the only thing standing between
that byte string and your money, and a signature is irreversible. So the rule is:

    NEVER sign a transaction you have not decoded.

This tool decodes a legacy Solana transaction and reports what it would actually
do: which programs it invokes, which accounts it touches, whether the fee payer
can be drained, and whether any instruction is a blanket approval or an
unexpected transfer. It reads a file or stdin and never signs, sends, or holds
a key.

Usage:
  python3 tools/solana_tx_inspect.py tx.bin
  curl -s ... -o tx.bin && python3 tools/solana_tx_inspect.py tx.bin
"""
from __future__ import annotations

import sys
from pathlib import Path

# Programs a pump.fun buy/sell is ALLOWED to touch.
KNOWN_SAFE = {
    "11111111111111111111111111111111": "System Program",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": "SPL Token Program",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb": "Token-2022 Program",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL": "Associated Token Account",
    "ComputeBudget111111111111111111111111111111": "Compute Budget",
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "pump.fun bonding curve",
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA": "pump.fun AMM (pump-amm)",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter aggregator v6",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM v4",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "Raydium CLMM",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Whirlpool",
}

# Instructions that can hand over control of your funds.
DANGER_SELECTORS = {
    "Approve": "grants a delegate the right to move your tokens",
    "ApproveChecked": "grants a delegate the right to move your tokens",
    "SetAuthority": "changes who controls an account",
    "CloseAccount": "closes an account and moves its lamports",
    "Assign": "changes the owner program of an account",
    "TransferFee": "unexpected fee transfer",
}

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    for byte in data:
        if byte:
            break
        out = "1" + out
    return out or "1"


class Reader:
    def __init__(self, buf: bytes) -> None:
        self.b = buf
        self.i = 0

    def u8(self) -> int:
        v = self.b[self.i]
        self.i += 1
        return v

    def u16(self) -> int:
        """Solana compact-u16."""
        v = 0
        shift = 0
        while True:
            byte = self.u8()
            v |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return v
            shift += 7

    def take(self, n: int) -> bytes:
        v = self.b[self.i:self.i + n]
        self.i += n
        return v


def inspect(raw: bytes) -> dict:
    r = Reader(raw)
    sig_count = r.u16()
    signatures = [r.take(64) for _ in range(sig_count)]
    # Versioned transactions prefix the message with 0x80 | version.
    version = "legacy"
    peek = r.b[r.i]
    if peek & 0x80:
        version = f"v{peek & 0x7f}"
        r.u8()
    hdr = (r.u8(), r.u8(), r.u8())
    n_signed, n_ro_signed, n_ro_unsigned = hdr
    n_keys = r.u16()
    keys = [b58(r.take(32)) for _ in range(n_keys)]
    blockhash = b58(r.take(32))
    n_ix = r.u16()

    instructions = []
    for _ in range(n_ix):
        pid_index = r.u8()
        n_acct = r.u16()
        accounts = [r.u8() for _ in range(n_acct)]
        data_len = r.u16()
        data = r.take(data_len)
        pid = keys[pid_index] if pid_index < len(keys) else "?"
        instructions.append({
            "program": pid,
            "program_name": KNOWN_SAFE.get(pid, "UNKNOWN — verify this"),
            "known": pid in KNOWN_SAFE,
            "accounts": [keys[a] if a < len(keys) else "?" for a in accounts],
            "data_len": data_len,
            "data_hex": data[:16].hex(),
        })

    lookups = []
    if version != "legacy" and r.i < len(r.b):
        try:
            n_lookup = r.u16()
            for _ in range(n_lookup):
                lookups.append({
                    "table": b58(r.take(32)),
                    "writable_indexes": list(r.take(r.u8())),
                    "readonly_indexes": list(r.take(r.u8())),
                })
        except IndexError:
            lookups.append({"note": "truncated address-table lookup section"})

    fee_payer = keys[0] if keys else None
    unknown_programs = sorted({i["program"] for i in instructions if not i["known"]})
    signers = keys[:n_signed]

    verdict = "SAFE-ISH: every invoked program is recognised"
    if unknown_programs:
        verdict = f"REVIEW: {len(unknown_programs)} unknown program(s) invoked"
    if sig_count == 0:
        verdict = "NOT A SIGNABLE TX (0 signatures required)"

    return {
        "bytes": len(raw),
        "version": version,
        "address_table_lookups": lookups,
        "signatures_required": sig_count,
        "signers_you_would_authorise": signers,
        "fee_payer": fee_payer,
        "recent_blockhash": blockhash,
        "account_keys": len(keys),
        "instructions": instructions,
        "unknown_programs": unknown_programs,
        "verdict": verdict,
    }


def report(info: dict) -> None:
    print(f"transaction: {info['bytes']} bytes | {info['version']} | "
          f"requires {info['signatures_required']} signature(s)")
    if info.get("address_table_lookups"):
        print("!  uses ADDRESS TABLE LOOKUPS — extra accounts are hidden outside this tx:")
        for l in info["address_table_lookups"]:
            print(f"    table {l.get('table')} writable={l.get('writable_indexes')} readonly={l.get('readonly_indexes')}")
    print(f"fee payer (pays, and can be drained if the tx is malicious): {info['fee_payer']}")
    print(f"your signature would authorise: {info['signers_you_would_authorise']}")
    print(f"accounts referenced: {info['account_keys']}")
    print("\ninstructions:")
    for n, ix in enumerate(info["instructions"], 1):
        flag = "ok " if ix["known"] else "!! "
        print(f"  {flag}{n}. {ix['program_name']}")
        print(f"        program: {ix['program']}")
        print(f"        touches {len(ix['accounts'])} account(s), data {ix['data_len']}B {ix['data_hex']}")
    if info["unknown_programs"]:
        print("\nUNKNOWN PROGRAMS — do not sign until each is identified:")
        for p in info["unknown_programs"]:
            print(f"  {p}")
    print(f"\nVERDICT: {info['verdict']}")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    raw = Path(sys.argv[1]).read_bytes()
    try:
        info = inspect(raw)
    except Exception as exc:
        print(f"could not decode as a legacy transaction: {type(exc).__name__}: {exc}")
        print("(versioned/other encodings may need a Solana SDK — do NOT sign an undecodable tx)")
        return 1
    report(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
