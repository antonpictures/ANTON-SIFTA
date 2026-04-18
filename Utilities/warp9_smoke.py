#!/usr/bin/env python3
"""
Utilities/warp9_smoke.py — End-to-end smoke for the WARP 9 stack
══════════════════════════════════════════════════════════════════════
Exercises every owner-facing surface of:
  System.swarm_owner_identity   (substrate)
  System.swarm_warp9_federation (Module 1)
  System.swarm_warp9_devices    (Module 2)
  System.swarm_warp9            (Module 3 + umbrella)

Usage:
    python3 -m Utilities.warp9_smoke
    python3 -m Utilities.warp9_smoke --verbose
    python3 -m Utilities.warp9_smoke --enable-federation   # opt-in real-mode

Exit codes:
    0  — all green
    1  — at least one segment failed (details printed)
    2  — fatal import error (warp9 stack is structurally broken)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from typing import Any, Callable, List, Tuple


def _step(name: str, fn: Callable[[], Any], *, verbose: bool) -> Tuple[bool, str]:
    t0 = time.time()
    try:
        result = fn()
        ms = round((time.time() - t0) * 1000, 1)
        msg = f"PASS [{ms:>6}ms] {name}"
        if verbose and result is not None:
            msg += f"  -> {result}"
        return True, msg
    except AssertionError as exc:
        ms = round((time.time() - t0) * 1000, 1)
        return False, f"FAIL [{ms:>6}ms] {name}: assertion: {exc}"
    except Exception as exc:
        ms = round((time.time() - t0) * 1000, 1)
        tb = "\n" + traceback.format_exc(limit=3) if verbose else ""
        return False, f"FAIL [{ms:>6}ms] {name}: {exc!r}{tb}"


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="WARP 9 end-to-end smoke")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--enable-federation", action="store_true",
                        help="set SIFTA_OWNER_FEDERATION=1 for the duration of this smoke")
    args = parser.parse_args(argv)

    if args.enable_federation:
        os.environ["SIFTA_OWNER_FEDERATION"] = "1"

    try:
        from System.swarm_owner_identity import (
            get_or_create_owner, register_homeworld, list_owner_homeworlds,
            is_federated, detect_self_homeworld_serial, detect_self_architect_id,
            FEDERATION_ENABLED,
        )
        from System.swarm_warp9_federation import (
            send_chat, send_swimmer_visit, recv, list_spool_pairs,
        )
        from System.swarm_warp9_devices import (
            register_device, list_devices_for_homeworld,
            speak_via_best_device, recent_device_signals,
            DeviceConsentMissingError,
        )
        from System.swarm_warp9 import (
            warp9_status, snapshot_owner_behavior,
            propose_setting_change, list_open_proposals, ratify_proposal,
        )
    except Exception as exc:
        print(f"[WARP9-SMOKE FATAL] structural import failure: {exc!r}",
              file=sys.stderr)
        return 2

    print("=" * 72)
    print("SIFTA WARP 9 — END-TO-END SMOKE")
    print("=" * 72)
    print(f"FEDERATION_ENABLED={FEDERATION_ENABLED}  "
          f"self={detect_self_architect_id()} ({detect_self_homeworld_serial()})")
    print("-" * 72)

    results: List[Tuple[bool, str]] = []
    self_serial = detect_self_homeworld_serial()

    # ── Substrate: owner_identity ──────────────────────────────────────
    def _owner():
        owner = get_or_create_owner("IOAN")
        homes = list_owner_homeworlds(owner.key)
        assert any(h.homeworld_serial == self_serial for h in homes), \
            "self homeworld not in IOAN federation"
        return f"owner={owner.label} key={owner.key} homeworlds={len(homes)}"
    results.append(_step("substrate.owner_identity", _owner, verbose=args.verbose))

    # ── Federation send/recv ──────────────────────────────────────────
    def _federation_loopback():
        # Use force=True so the smoke works whether or not federation is on.
        msg = send_chat(self_serial, "WARP9 smoke loopback ping", force=True)
        assert msg is not None, "send_chat returned None"
        # Wait a tick for the spool write to settle (filesystem time)
        time.sleep(0.05)
        msgs = recv(kinds=["chat"], since_ts=time.time() - 5)
        assert any(m.msg_id == msg.msg_id for m in msgs), \
            f"loopback message {msg.msg_id} not visible to recv()"
        return f"sent+recv'd msg_id={msg.msg_id}"
    results.append(_step("federation.loopback_send_recv", _federation_loopback,
                         verbose=args.verbose))

    def _federation_refuses_off():
        if FEDERATION_ENABLED:
            return "skipped (federation explicitly enabled)"
        # Without force=True and federation OFF, send must refuse.
        msg = send_chat("FAKE_PEER_SERIAL", "should be refused")
        assert msg is None, "send_chat without force should refuse when federation off"
        return "refused as expected"
    results.append(_step("federation.test_mode_refusal", _federation_refuses_off,
                         verbose=args.verbose))

    def _federation_swimmer_visit():
        msg = send_swimmer_visit(self_serial, "C47H",
                                 capabilities=["read_log", "write_proposal"],
                                 force=True)
        assert msg is not None
        assert msg.kind == "swimmer_visit"
        assert "C47H" in str(msg.payload)
        return f"swimmer C47H visit announced"
    results.append(_step("federation.swimmer_visit_kind", _federation_swimmer_visit,
                         verbose=args.verbose))

    # ── Devices: consent gate + register + capability filter + speak ──
    def _devices_consent():
        try:
            register_device("BAD", "google_home", transport="lan_mdns",
                            capabilities={"can_speak": True}, scopes=[],
                            consent_signature="")
        except DeviceConsentMissingError:
            return "consent gate enforced"
        raise AssertionError("consent gate should have refused empty signature")
    results.append(_step("devices.consent_gate", _devices_consent, verbose=args.verbose))

    def _devices_register_and_route():
        dev = register_device(
            nickname="WARP9 smoke speaker",
            vendor="amazon_alexa",
            transport="cloud_api",
            capabilities={"can_speak": True, "can_listen": True},
            scopes=["read:speech_in", "write:tts"],
            consent_signature="warp9_smoke_consent",
        )
        speakers = list_devices_for_homeworld(capability="can_speak")
        assert any(d.device_id == dev.device_id for d in speakers), \
            "device not visible to capability filter"
        used = speak_via_best_device("Smoke greeting from the swarm.")
        assert used is not None
        return f"registered + spoke via {used!r}"
    results.append(_step("devices.register_and_route", _devices_register_and_route,
                         verbose=args.verbose))

    def _devices_signals_visible():
        sigs = recent_device_signals(since_ts=time.time() - 30)
        # speak_via_best_device emits a signal — at least one expected
        assert len(sigs) >= 1, f"no recent device signals (expected >= 1, got {len(sigs)})"
        return f"device signals in last 30s: {len(sigs)}"
    results.append(_step("devices.signals_visible", _devices_signals_visible,
                         verbose=args.verbose))

    # ── Concierge: snapshot + propose + ratify ────────────────────────
    def _concierge_snapshot():
        snap = snapshot_owner_behavior()
        assert snap.architect_id, "snapshot missing architect_id"
        assert snap.homeworld_serial, "snapshot missing homeworld_serial"
        return (f"oxt={snap.oxt_level} eye={snap.recent_eye_captures} "
                f"chat={snap.recent_chat_count} dev={snap.recent_device_signals} "
                f"peers={snap.federated_peers}")
    results.append(_step("concierge.snapshot_owner_behavior", _concierge_snapshot,
                         verbose=args.verbose))

    def _concierge_propose_ratify():
        prop = propose_setting_change(
            title="Smoke proposal — set probe interval to 90s",
            rationale="WARP9 smoke verifies the propose/ratify ledger contract",
            target_setting="probe.interval_s",
            proposed_value=90,
            current_value=120,
            confidence=0.7,
            expires_in_s=3600,
        )
        opens = list_open_proposals()
        assert any(p.proposal_id == prop.proposal_id for p in opens), \
            f"new proposal {prop.proposal_id} not in open list"
        rec = ratify_proposal(prop.proposal_id, note="warp9 smoke ratify")
        assert rec is not None, "ratify_proposal returned None"
        # After ratify, proposal should NOT be in open list anymore
        opens_after = list_open_proposals()
        assert not any(p.proposal_id == prop.proposal_id for p in opens_after), \
            "ratified proposal still appears as open"
        return f"propose -> ratify cycle clean: {prop.proposal_id}"
    results.append(_step("concierge.propose_then_ratify", _concierge_propose_ratify,
                         verbose=args.verbose))

    def _umbrella_status():
        status = warp9_status()
        for k in ("module_version", "owner_label", "self_homeworld_serial",
                  "homeworlds_known", "devices_on_self", "behavior_snapshot",
                  "spool_pairs"):
            assert k in status, f"warp9_status missing key {k}"
        return (f"homeworlds={len(status['homeworlds_known'])} "
                f"devices={len(status['devices_on_self'])} "
                f"spool_pairs={len(status['spool_pairs'])}")
    results.append(_step("umbrella.warp9_status", _umbrella_status, verbose=args.verbose))

    # Print + tally
    print()
    for ok, msg in results:
        print(msg)
    print("-" * 72)
    n_ok = sum(1 for ok, _ in results if ok)
    n_fail = sum(1 for ok, _ in results if not ok)
    line = f"PASSED {n_ok}/{len(results)}"
    if n_fail:
        line += f"   FAILED {n_fail}"
    print(line)
    print("=" * 72)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
