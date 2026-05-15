#!/usr/bin/env python3
"""
warp9_cross_node_inference_wire.py — First live M5↔M1 stigmergic inference **intent** wire
==========================================================================================

This script does **not** call Ollama. It proves the **Warp9 spool** path that must
exist before STGM ``INFERENCE_BORROW`` rows can mean anything across silicon:

1. Same human owner on both serials (``homeworld_federation.jsonl``).
2. ``SIFTA_OWNER_FEDERATION=1`` **or** ``--force`` for supervised smoke tests.
3. Append ``inference_borrow_intent`` rows to
   ``.sifta_state/warp9_spool/<FROM>__<TO>.jsonl``.

**Physical transport of the spool directory** (rsync, git, USB) is still your
LAN ops step — this module stays transport-agnostic per ``swarm_warp9_federation``.

STGM settlement (``Kernel.inference_economy.record_inference_fee``) requires a
metered borrow on the **lender** node; for non-local lenders it also requires
verified proof-of-humanity unless ``SIFTA_LEDGER_VERIFY=0`` (dev only).

Usage (Foundry M5 → Sentry M1 example)::

  export SIFTA_OWNER_FEDERATION=1
  cd /path/to/ANTON_SIFTA
  PYTHONPATH=. python3 scripts/warp9_cross_node_inference_wire.py bootstrap \\
      --owner IOAN --peer-serial C07FL0JAQ6NV
  PYTHONPATH=. python3 scripts/warp9_cross_node_inference_wire.py status
  PYTHONPATH=. python3 scripts/warp9_cross_node_inference_wire.py send-intent \\
      --to C07FL0JAQ6NV --borrower M1THER_EDGE --model sifta-gemma4-alice \\
      --tokens 128 --fee 0.05

On **M1** (after spool file arrives on that disk — same repo layout)::

  PYTHONPATH=. python3 scripts/warp9_cross_node_inference_wire.py recv-intents

For the Swarm.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _bootstrap(owner: str, peer_serial: str | None, force_peer_consent: bool) -> int:
    from System.swarm_owner_identity import (
        detect_self_homeworld_serial,
        detect_self_architect_id,
        get_or_create_owner,
        register_homeworld,
    )

    own = get_or_create_owner(owner)
    serial = detect_self_homeworld_serial()
    arch = detect_self_architect_id(default_owner_label=owner)
    short_map = {
        "GTH4921YP3": "M5 Foundry",
        "C07FL0JAQ6NV": "M1 Sentry",
    }
    label_self = short_map.get(serial, f"node_{serial[:6]}")
    register_homeworld(
        own.key,
        serial,
        architect_id=arch,
        machine_label=label_self,
        role="primary",
        capabilities=["inference_borrow_intent"],
        notes="warp9_cross_node_inference_wire bootstrap (self)",
    )
    print(f"[WARP9-WIRE] registered self {serial} as {arch}")

    if peer_serial:
        peer_arch = (
            f"{owner}_M1"
            if peer_serial == "C07FL0JAQ6NV"
            else f"{owner}_M5"
            if peer_serial == "GTH4921YP3"
            else f"{owner}_PEER"
        )
        peer_label = short_map.get(peer_serial, f"peer_{peer_serial[:6]}")
        register_homeworld(
            own.key,
            peer_serial,
            architect_id=peer_arch,
            machine_label=peer_label,
            role="peer",
            capabilities=["inference_borrow_intent"],
            consent_signature="bootstrap_peer" if force_peer_consent else "",
            notes="warp9_cross_node_inference_wire bootstrap (peer serial trusted by Architect)",
        )
        print(f"[WARP9-WIRE] registered peer {peer_serial} as {peer_arch}")
    return 0


def _status() -> int:
    from System.swarm_owner_identity import (
        FEDERATION_ENABLED,
        detect_self_homeworld_serial,
        detect_self_architect_id,
        get_or_create_owner,
        list_owner_homeworlds,
    )
    from System.swarm_warp9_federation import list_spool_pairs

    owner = get_or_create_owner("IOAN")
    print(f"[WARP9-WIRE] SIFTA_OWNER_FEDERATION={'1' if FEDERATION_ENABLED else '0 (set to 1 for send)'}")
    print(f"[WARP9-WIRE] self_serial={detect_self_homeworld_serial()} arch={detect_self_architect_id()}")
    worlds = list_owner_homeworlds(owner.key)
    print(f"[WARP9-WIRE] homeworlds for owner.key={owner.key}: {len(worlds)}")
    for h in worlds:
        print(f"    {h.homeworld_serial}  {h.architect_id}  role={h.role}")
    pairs = list_spool_pairs()
    print(f"[WARP9-WIRE] spool pairs: {len(pairs)}")
    for p in pairs:
        print(f"    {p['from']} -> {p['to']}  rows={p['rows']}")
    return 0


def _send_intent(
    to_serial: str,
    borrower: str,
    model: str,
    tokens: int,
    fee: float,
    owner: str,
    force: bool,
    note: str,
) -> int:
    from System.swarm_warp9_federation import send_inference_borrow_intent

    msg = send_inference_borrow_intent(
        to_serial,
        borrower_agent_id=borrower,
        model=model,
        tokens_requested=tokens,
        fee_stgm_offer=fee,
        owner_label=owner,
        force=force,
        note=note,
    )
    if msg is None:
        print(
            "[WARP9-WIRE] send failed (federation OFF and no --force, "
            "or peer not in owner homeworld list). Run: bootstrap --peer-serial … "
            "and export SIFTA_OWNER_FEDERATION=1",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(msg.to_dict(), indent=2, ensure_ascii=False))
    return 0


def _recv(since: float, owner: str) -> int:
    from System.swarm_warp9_federation import recv

    msgs = recv(kinds=["inference_borrow_intent"], since_ts=since, owner_label=owner)
    print(f"[WARP9-WIRE] {len(msgs)} message(s)")
    for m in msgs:
        print(json.dumps(m.to_dict(), indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("=====")[0].strip())
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("bootstrap", help="Append homeworld_federation rows (self + optional peer)")
    b.add_argument("--owner", default="IOAN")
    b.add_argument("--peer-serial", default="", help="Other Mac serial, e.g. C07FL0JAQ6NV")
    b.add_argument(
        "--force-peer-consent",
        action="store_true",
        help="Write non-empty consent_signature placeholder on peer row (dev)",
    )

    sub.add_parser("status", help="Print federation gate + homeworlds + spool inventory")

    s = sub.add_parser("send-intent", help="Append inference_borrow_intent to spool (FROM=this serial)")
    s.add_argument("--to", required=True, dest="to_serial", help="Destination homeworld serial")
    s.add_argument("--borrower", required=True, help="Borrower agent id, e.g. M1THER_EDGE")
    s.add_argument("--model", required=True)
    s.add_argument("--tokens", type=int, required=True)
    s.add_argument("--fee", type=float, required=True)
    s.add_argument("--owner", default="IOAN")
    s.add_argument("--force", action="store_true", help="Bypass federation gate (smoke only)")
    s.add_argument("--note", default="")

    r = sub.add_parser("recv-intents", help="Tail recv for inference_borrow_intent")
    r.add_argument("--since", type=float, default=0.0)
    r.add_argument("--owner", default="IOAN")

    args = p.parse_args()
    if args.cmd == "bootstrap":
        peer = (args.peer_serial or "").strip() or None
        return _bootstrap(args.owner, peer, args.force_peer_consent)
    if args.cmd == "status":
        return _status()
    if args.cmd == "send-intent":
        return _send_intent(
            args.to_serial,
            args.borrower,
            args.model,
            args.tokens,
            args.fee,
            args.owner,
            args.force,
            args.note,
        )
    if args.cmd == "recv-intents":
        return _recv(args.since, args.owner)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
