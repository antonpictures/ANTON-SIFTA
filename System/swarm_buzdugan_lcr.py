#!/usr/bin/env python3
"""Buzdugan LCR: receipt-backed long-context retrieval benchmark for SIFTA.

This does not pretend to test an LLM's internal attention at token 800,000.
It tests SIFTA's claim: store the trace in the body, retrieve the exact row,
verify byte/line/hash, then let the cortex speak from evidence.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
STATE_DIR = _REPO / ".sifta_state" / "buzdugan_lcr"
CORPUS_PATH = STATE_DIR / "buzdugan_lcr_corpus.txt"
INDEX_PATH = STATE_DIR / "buzdugan_lcr_index.json"
LEDGER_PATH = STATE_DIR / "buzdugan_lcr_receipts.jsonl"
TRUTH_LABEL = "BUZDUGAN_LCR_V1"
DEFAULT_TOKEN_TARGET = 820_000
DEFAULT_NEEDLE_COUNT = 8
TOKEN_EQ_CHARS = 4
FACT_PREFIX = "BUZDUGAN_LCR_FACT "


@dataclass(frozen=True)
class NeedleFact:
    needle_id: str
    key: str
    value: str
    target_token: int
    question: str


def _ensure_state_dir(state_dir: Path | None = None) -> Path:
    root = Path(state_dir) if state_dir is not None else STATE_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _paths(state_dir: Path | None = None) -> dict[str, Path]:
    root = _ensure_state_dir(state_dir)
    return {
        "state_dir": root,
        "corpus": root / CORPUS_PATH.name,
        "index": root / INDEX_PATH.name,
        "ledger": root / LEDGER_PATH.name,
    }


def estimate_token_equivalent(text: str | bytes) -> int:
    if isinstance(text, bytes):
        n = len(text)
    else:
        n = len(text.encode("utf-8", errors="replace"))
    return max(1, n // TOKEN_EQ_CHARS)


def _line_hash(raw: bytes) -> str:
    return sha256(raw.rstrip(b"\n")).hexdigest()


def _needle_positions(token_target: int, needle_count: int) -> list[int]:
    if token_target >= 820_000 and needle_count >= 8:
        base = [100_000, 200_000, 300_000, 400_000, 500_000, 600_000, 700_000, 800_000]
        if needle_count == 8:
            return base
        extra = [
            min(token_target - 1, int(token_target * (i + 1) / (needle_count + 1)))
            for i in range(needle_count - 8)
        ]
        return sorted(base + extra)
    return [
        max(1, int(token_target * (i + 1) / (needle_count + 1)))
        for i in range(needle_count)
    ]


def make_needles(
    *,
    token_target: int = DEFAULT_TOKEN_TARGET,
    needle_count: int = DEFAULT_NEEDLE_COUNT,
    seed: str = "buzdugan-lcr-2026-06-07",
) -> list[NeedleFact]:
    facts: list[NeedleFact] = []
    for idx, target in enumerate(_needle_positions(token_target, needle_count), start=1):
        lane = f"lane_{idx:02d}"
        digest = sha256(f"{seed}:{lane}:{target}".encode("utf-8")).hexdigest()[:18]
        facts.append(
            NeedleFact(
                needle_id=f"LCR-{idx:02d}",
                key=f"buzdugan_{lane}_right_fact",
                value=f"SIFTA_BODY_TRACE_{idx:02d}_{digest}",
                target_token=target,
                question=f"What is the exact Buzdugan LCR right fact for {lane}?",
            )
        )
    return facts


def _fact_line(fact: NeedleFact) -> str:
    return FACT_PREFIX + json.dumps(asdict(fact), sort_keys=True, separators=(",", ":")) + "\n"


def _filler_line(line_no: int, token_cursor: int, seed: str) -> str:
    digest = sha256(f"{seed}:filler:{line_no}:{token_cursor}".encode("utf-8")).hexdigest()[:16]
    return (
        f"body_trace filler_line={line_no:06d} token_band={token_cursor//1000:06d} "
        f"checksum={digest} ordinary context noise; not the right fact; "
        "receipt ecology stores boring rows too so the exact signal can be found later.\n"
    )


def generate_corpus(
    *,
    token_target: int = DEFAULT_TOKEN_TARGET,
    needle_count: int = DEFAULT_NEEDLE_COUNT,
    seed: str = "buzdugan-lcr-2026-06-07",
    state_dir: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    paths = _paths(state_dir)
    corpus = paths["corpus"]
    if corpus.exists() and not force:
        return build_index(state_dir=paths["state_dir"])

    facts = make_needles(token_target=token_target, needle_count=needle_count, seed=seed)
    fact_idx = 0
    token_cursor = 0
    line_no = 0
    started = time.perf_counter()
    with corpus.open("w", encoding="utf-8", newline="") as fh:
        fh.write(
            "# Buzdugan LCR corpus: deterministic receipt-backed retrieval test.\n"
            "# Not an LLM attention benchmark. This is SIFTA body storage + exact retrieval.\n"
        )
        token_cursor += 35
        while token_cursor < token_target or fact_idx < len(facts):
            while fact_idx < len(facts) and token_cursor >= facts[fact_idx].target_token:
                line_no += 1
                line = _fact_line(facts[fact_idx])
                fh.write(line)
                token_cursor += estimate_token_equivalent(line)
                fact_idx += 1
            if token_cursor >= token_target and fact_idx >= len(facts):
                break
            line_no += 1
            line = _filler_line(line_no, token_cursor, seed)
            fh.write(line)
            token_cursor += estimate_token_equivalent(line)

    index = build_index(state_dir=paths["state_dir"])
    index["generation"] = {
        "elapsed_s": round(time.perf_counter() - started, 4),
        "token_target": token_target,
        "needle_count": needle_count,
        "seed": seed,
    }
    paths["index"].write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return index


def _parse_fact_payload(line: str) -> dict[str, Any] | None:
    if not line.startswith(FACT_PREFIX):
        return None
    try:
        payload = json.loads(line[len(FACT_PREFIX):])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def build_index(*, state_dir: Path | None = None) -> dict[str, Any]:
    paths = _paths(state_dir)
    corpus = paths["corpus"]
    if not corpus.exists():
        raise FileNotFoundError(f"Missing Buzdugan LCR corpus: {corpus}")

    started = time.perf_counter()
    facts: list[dict[str, Any]] = []
    token_cursor = 0
    with corpus.open("rb") as fh:
        line_no = 0
        while True:
            offset = fh.tell()
            raw = fh.readline()
            if not raw:
                break
            line_no += 1
            token_at_est = token_cursor
            token_cursor += estimate_token_equivalent(raw)
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            payload = _parse_fact_payload(line)
            if payload is None:
                continue
            payload.update(
                {
                    "line_no": line_no,
                    "byte_offset": offset,
                    "token_at_est": token_at_est,
                    "line_hash": _line_hash(raw),
                }
            )
            facts.append(payload)

    index = {
        "truth_label": TRUTH_LABEL,
        "created_at": time.time(),
        "corpus_path": str(corpus),
        "corpus_bytes": corpus.stat().st_size,
        "token_equivalent_est": token_cursor,
        "fact_count": len(facts),
        "facts": facts,
        "build_elapsed_s": round(time.perf_counter() - started, 4),
    }
    paths["index"].write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return index


def load_index(*, state_dir: Path | None = None) -> dict[str, Any]:
    paths = _paths(state_dir)
    if not paths["index"].exists():
        return build_index(state_dir=paths["state_dir"])
    return json.loads(paths["index"].read_text(encoding="utf-8"))


def retrieve_fact(key: str, *, state_dir: Path | None = None) -> dict[str, Any]:
    paths = _paths(state_dir)
    index = load_index(state_dir=paths["state_dir"])
    started = time.perf_counter()
    match = next((row for row in index.get("facts", []) if row.get("key") == key), None)
    if match is None:
        return {
            "ok": False,
            "key": key,
            "error": "key_not_found",
            "elapsed_s": round(time.perf_counter() - started, 6),
        }

    with paths["corpus"].open("rb") as fh:
        fh.seek(int(match["byte_offset"]))
        raw = fh.readline()
    line = raw.decode("utf-8", errors="replace").rstrip("\n")
    payload = _parse_fact_payload(line) or {}
    verified_hash = _line_hash(raw) == match.get("line_hash")
    verified_value = payload.get("value") == match.get("value")
    return {
        "ok": bool(verified_hash and verified_value),
        "key": key,
        "value": payload.get("value"),
        "question": match.get("question"),
        "needle_id": match.get("needle_id"),
        "line_no": match.get("line_no"),
        "byte_offset": match.get("byte_offset"),
        "token_at_est": match.get("token_at_est"),
        "target_token": match.get("target_token"),
        "line_hash": match.get("line_hash"),
        "verified_hash": verified_hash,
        "verified_value": verified_value,
        "elapsed_s": round(time.perf_counter() - started, 6),
        "source_path": str(paths["corpus"]),
    }


def run_lcr_benchmark(
    *,
    token_target: int = DEFAULT_TOKEN_TARGET,
    needle_count: int = DEFAULT_NEEDLE_COUNT,
    seed: str = "buzdugan-lcr-2026-06-07",
    state_dir: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    paths = _paths(state_dir)
    started = time.perf_counter()
    index = generate_corpus(
        token_target=token_target,
        needle_count=needle_count,
        seed=seed,
        state_dir=paths["state_dir"],
        force=force,
    )
    retrievals = [retrieve_fact(str(row["key"]), state_dir=paths["state_dir"]) for row in index.get("facts", [])]
    pass_count = sum(1 for row in retrievals if row.get("ok"))
    target = max(retrievals, key=lambda row: int(row.get("target_token") or 0), default={})
    receipt = {
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "mode": "sifta_body_retrieval_first",
        "claim_tested": (
            "Alice does not need every trace in cortex; SIFTA retrieves exact body "
            "receipts before the cortex speaks."
        ),
        "not_claimed": "This is not a raw LLM 800k-token attention score.",
        "token_target": token_target,
        "needle_count": needle_count,
        "corpus_path": str(paths["corpus"]),
        "corpus_bytes": index.get("corpus_bytes"),
        "token_equivalent_est": index.get("token_equivalent_est"),
        "index_path": str(paths["index"]),
        "fact_count": index.get("fact_count"),
        "pass_count": pass_count,
        "pass_rate": round(pass_count / max(1, len(retrievals)), 4),
        "all_verified": pass_count == len(retrievals) and bool(retrievals),
        "target_retrieval": target,
        "retrievals": retrievals,
        "elapsed_s": round(time.perf_counter() - started, 4),
    }
    with paths["ledger"].open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, sort_keys=True) + "\n")
    return receipt


def latest_receipt(*, state_dir: Path | None = None) -> dict[str, Any] | None:
    paths = _paths(state_dir)
    if not paths["ledger"].exists():
        return None
    last = None
    with paths["ledger"].open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.strip():
                last = line
    if not last:
        return None
    try:
        return json.loads(last)
    except json.JSONDecodeError:
        return None


def format_receipt(receipt: dict[str, Any] | None) -> str:
    if not receipt:
        return "No Buzdugan LCR receipt yet. Run the benchmark."
    target = receipt.get("target_retrieval") or {}
    return "\n".join(
        [
            f"truth_label: {receipt.get('truth_label')}",
            f"mode: {receipt.get('mode')}",
            f"all_verified: {receipt.get('all_verified')}",
            f"pass_rate: {receipt.get('pass_rate')} ({receipt.get('pass_count')}/{receipt.get('fact_count')})",
            f"token_equivalent_est: {receipt.get('token_equivalent_est')}",
            f"corpus_bytes: {receipt.get('corpus_bytes')}",
            f"target_key: {target.get('key')}",
            f"target_value: {target.get('value')}",
            f"target_token_est: {target.get('token_at_est')} / requested {target.get('target_token')}",
            f"line_no: {target.get('line_no')}",
            f"byte_offset: {target.get('byte_offset')}",
            f"line_hash: {target.get('line_hash')}",
            f"source_path: {target.get('source_path')}",
            f"elapsed_s: {receipt.get('elapsed_s')}",
            f"not_claimed: {receipt.get('not_claimed')}",
        ]
    )


def retweet_claim(receipt: dict[str, Any] | None) -> str:
    base = (
        "SIFTA does not need Alice to hold everything in the cortex. "
        "Her body stores traces; retrieval organs pull the exact receipt "
        "before the cortex speaks."
    )
    if not receipt:
        return base + " Benchmark receipt pending."
    target = receipt.get("target_retrieval") or {}
    if receipt.get("all_verified"):
        return (
            f"{base} Buzdugan LCR test: {receipt.get('pass_count')}/{receipt.get('fact_count')} "
            f"facts verified from ~{receipt.get('token_equivalent_est')} token-equivalent body corpus; "
            f"target near {target.get('target_token')} retrieved with line+byte+sha256 receipt. "
            "Not a raw LLM attention claim."
        )
    return base + " Latest Buzdugan LCR receipt did not fully pass yet; no public claim."


if __name__ == "__main__":
    result = run_lcr_benchmark(force=True)
    print(format_receipt(result))
    print()
    print(retweet_claim(result))
