#!/usr/bin/env python3
"""Serving-efficiency and local-first gem used by the J2 calibration harness.

Two things live here because both are properties of *how* Alice runs a local model,
not of any single decision:

1. **Efficient serving profile + hardware fit.** Measured locally on 2026-09-22
   (``outputs/sifta_kv_efficiency/kv-20260922-172652.json``), quantizing the KV cache to
   q8_0 and enabling flash attention reduced resident memory at identical context against
   f16 KV. The DIRECTION was confirmed by two instruments (``ps`` tree RSS and ``vmmap``
   physical footprint); the two magnitudes disagreed, so this is recorded as an engineering
   default with provenance, never as a certified ratio. CPU prefill measured ~38 ms/token,
   which is why every prompt in this pipeline stays tiny.

2. **Mechanical loopback-only egress proof.** A runtime guard that raises on any attempt to
   reach a non-loopback address, so "local-first" is demonstrated by the code path rather
   than asserted in prose. There is no automatic cloud fallback anywhere in J1/J2/J3.
"""
from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]

EFFICIENT_SERVING_PROFILE: dict[str, Any] = {
    "name": "kv_q8_0_fa_on",
    "flags": ["-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on"],
    "provenance": "llama.cpp KV quantization (q8_0) + flash attention; direction confirmed "
                  "locally 2026-09-22 via ps RSS and vmmap footprint, magnitude inconclusive",
}

BASELINE_SERVING_PROFILE: dict[str, Any] = {
    "name": "f16_kv_default",
    "flags": [],
    "provenance": "llama.cpp defaults (f16 KV, flash attention auto)",
}

KV_BYTES_PER_ELEMENT: dict[str, float] = {"f16": 2.0, "q8_0": 1.0, "q4_0": 0.5}


class EgressViolation(RuntimeError):
    """Raised when guarded code attempts to reach a non-loopback address."""


def estimate_kv_bytes(*, n_layer: int, n_kv_head: int, head_dim: int, n_ctx: int,
                      dtype: str = "f16") -> int:
    """KV cache bytes for a full context: 2 (K and V) x layers x kv-heads x head_dim x ctx."""
    per_element = KV_BYTES_PER_ELEMENT.get(dtype, 2.0)
    return int(2 * int(n_layer) * int(n_kv_head) * int(head_dim) * int(n_ctx) * per_element)


def serving_flags(profile: dict[str, Any] | None = None) -> list[str]:
    """Extra llama-server flags for a serving profile."""
    chosen = EFFICIENT_SERVING_PROFILE if profile is None else profile
    return [str(flag) for flag in (chosen.get("flags") or [])]


def serving_profile_block(profile: dict[str, Any] | None = None) -> dict[str, Any]:
    chosen = EFFICIENT_SERVING_PROFILE if profile is None else profile
    return {"name": chosen.get("name"), "flags": serving_flags(chosen),
            "provenance": chosen.get("provenance")}


def machine_ram_mb() -> float | None:
    """Total physical RAM in MB from sysctl; None when unavailable (never guessed)."""
    try:
        out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
        value = int((out.stdout or "").strip())
        return round(value / 1024 / 1024, 1) if value > 0 else None
    except Exception:
        return None


def choose_local_backend(rows: Iterable[dict[str, Any]], *, required_ctx: int,
                         ram_budget_mb: float | None = None, kv_dtype: str = "q8_0",
                         n_layer: int = 28, n_kv_head: int = 8, head_dim: int = 64,
                         require_selectable: bool = True) -> dict[str, Any]:
    """Choose the smallest installed artifact that fits the RAM budget at the required context.

    Choosing the smallest fitting model is the efficiency decision: less resident memory and
    less prefill work per token, which is the dominant cost on this CPU-only machine.
    """
    kv_bytes = estimate_kv_bytes(n_layer=n_layer, n_kv_head=n_kv_head, head_dim=head_dim,
                                 n_ctx=required_ctx, dtype=kv_dtype)
    budget_bytes = None if ram_budget_mb is None else float(ram_budget_mb) * 1024 * 1024
    considered: list[dict[str, Any]] = []
    fitting: list[tuple[float, dict[str, Any]]] = []
    for row in rows or []:
        if require_selectable and not row.get("selectable"):
            continue
        size = row.get("size_bytes")
        if not isinstance(size, (int, float)) or size <= 0:
            continue
        total = float(size) + kv_bytes
        fits = budget_bytes is None or total <= budget_bytes
        considered.append({"id": row.get("id"), "size_mb": round(float(size) / 1024 / 1024, 1),
                           "quant": row.get("quant"), "backend": row.get("backend"),
                           "est_total_mb": round(total / 1024 / 1024, 1), "fits": fits})
        if fits:
            fitting.append((total, row))
    out: dict[str, Any] = {
        "ok": bool(fitting),
        "required_ctx": int(required_ctx),
        "ram_budget_mb": ram_budget_mb,
        "kv_dtype": kv_dtype,
        "estimated_kv_mb": round(kv_bytes / 1024 / 1024, 1),
        "candidates_considered": sorted(considered, key=lambda c: c["est_total_mb"]),
    }
    if not fitting:
        out["chosen"] = None
        out["reason"] = ("no installed selectable artifact fits the RAM budget at the required "
                         "context; refusing to recommend an over-budget model")
        return out
    fitting.sort(key=lambda item: (item[0], str(item[1].get("id"))))
    total, row = fitting[0]
    out["chosen"] = row.get("id")
    out["chosen_est_total_mb"] = round(total / 1024 / 1024, 1)
    out["reason"] = (f"smallest fitting artifact at ctx={int(required_ctx)} with {kv_dtype} KV "
                     f"(estimated {round(total / 1024 / 1024, 1)} MB resident)")
    return out


def assert_loopback_host(host: str) -> None:
    """Refuse to construct a client for a non-loopback host."""
    if str(host) not in ("127.0.0.1", "::1", "localhost") and not str(host).startswith("127."):
        raise EgressViolation(f"non-loopback host refused by local-first policy: {host!r}")


@contextlib.contextmanager
def loopback_only_egress(record: list[dict[str, Any]] | None = None):
    """Runtime proof that guarded code cannot reach a non-loopback address.

    Patches ``socket.socket.connect`` and ``socket.create_connection`` for the duration,
    raising :class:`EgressViolation` on any non-loopback destination and restoring both on
    exit. ``record`` receives one row per attempt so the evidence travels with a report.
    """
    import socket as _socket

    rows = record if record is not None else []
    original_connect = _socket.socket.connect
    original_create = _socket.create_connection

    def is_loopback(address: Any) -> bool:
        host = address[0] if isinstance(address, (tuple, list)) and address else address
        if isinstance(host, bytes):
            try:
                host = host.decode()
            except Exception:
                return False
        if isinstance(host, str):
            return host in ("127.0.0.1", "::1", "localhost") or host.startswith("127.")
        return False

    def guarded_connect(self, address):  # noqa: ANN001
        if not is_loopback(address):
            rows.append({"event": "blocked", "address": str(address)})
            raise EgressViolation(f"non-loopback connect blocked by local-first guard: {address}")
        rows.append({"event": "allowed_loopback", "address": str(address)})
        return original_connect(self, address)

    def guarded_create(address, *args, **kwargs):  # noqa: ANN001
        if not is_loopback(address):
            rows.append({"event": "blocked", "address": str(address)})
            raise EgressViolation(f"non-loopback connect blocked by local-first guard: {address}")
        rows.append({"event": "allowed_loopback", "address": str(address)})
        return original_create(address, *args, **kwargs)

    _socket.socket.connect = guarded_connect
    _socket.create_connection = guarded_create
    try:
        yield rows
    finally:
        _socket.socket.connect = original_connect
        _socket.create_connection = original_create


def egress_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"loopback_only_enforced": True,
            "attempts_recorded": len(rows),
            "non_loopback_blocked": sum(1 for r in rows if r.get("event") == "blocked"),
            "distinct_hosts": sorted({str(r.get("address")) for r in rows})}


def sha256_json(obj: Any) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


__all__ = ["BASELINE_SERVING_PROFILE", "EFFICIENT_SERVING_PROFILE", "EgressViolation",
           "assert_loopback_host", "choose_local_backend", "egress_block", "estimate_kv_bytes",
           "loopback_only_egress", "machine_ram_mb", "serving_flags", "serving_profile_block",
           "sha256_json"]
