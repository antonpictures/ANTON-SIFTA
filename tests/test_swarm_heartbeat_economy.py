import json
import ast
from pathlib import Path
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from System import crypto_keychain, stgm_economy
from System import swarm_heartbeat_economy as health
from Kernel import inference_economy


@pytest.fixture
def world(tmp_path, monkeypatch):
    key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(crypto_keychain, "get_silicon_identity", lambda: "TEST_NODE")
    monkeypatch.setattr(crypto_keychain, "sign_block", lambda body: key.sign(body.encode()).hex())

    def verify(node, body, sig):
        try:
            assert node == "TEST_NODE"
            key.public_key().verify(bytes.fromhex(sig), body.encode())
            return True
        except Exception:
            return False

    monkeypatch.setattr(crypto_keychain, "verify_block", verify)
    monkeypatch.setattr(stgm_economy, "_CACHE_LAST_SCAN", None)
    return tmp_path, tmp_path / "repair_log.jsonl"


def evidence(sd, ts=1000, *, status="ok", degraded=False):
    heart = {"schema": "SIFTA_HARDWARE_HEART_V1", "receipt_id": f"heart-{ts}",
             "ts": ts, "sensor_status": "partial"}
    body = {"truth_label": "BODY_WRITER_TICK_V1", "ts": ts,
            "overall_status": "ok" if status == "ok" else "partial",
            "degraded_mode": degraded,
            "producers": [{"producer": "memory", "status": status}]}
    for name, row in (("hardware_heart.jsonl", heart), ("body_writer_tick.jsonl", body)):
        (sd / name).write_text(json.dumps(row) + "\n")
    return heart, body


def settle(world, now=1000):
    sd, ledger = world
    return health.settle_heartbeat(state_dir=sd, ledger=ledger, now=now)


def test_healthy_reward_and_canonical_signature(world):
    sd, ledger = world
    evidence(sd)
    result = settle(world)
    assert result["delta_stgm"] == health.REWARD
    assert inference_economy._ledger_row_cryptographically_valid(result)
    snap = stgm_economy.scan_economy(repair_log=ledger, state_dir=sd)
    assert snap.canonical_minted == pytest.approx(health.REWARD)
    assert result["heart_receipt_id"] == "heart-1000"


@pytest.mark.parametrize("status,degraded", [("call_failed", False), ("ok", True)])
def test_fault_debits_and_signals_spinal_cord(world, status, degraded):
    sd, ledger = world
    evidence(sd, status=status, degraded=degraded)
    result = settle(world)
    assert result["delta_stgm"] == -health.PENALTY
    assert inference_economy._ledger_row_cryptographically_valid(result)
    snap = stgm_economy.scan_economy(repair_log=ledger, state_dir=sd)
    assert snap.canonical_spent == pytest.approx(health.PENALTY)
    signal = json.loads((sd / "self_eval_swimmer_dispatch.jsonl").read_text())
    assert signal["severity"] == "red"
    assert signal["receipt_id"] == result["event_id"]


@pytest.mark.parametrize("now", [999, 2000, float("nan")])
def test_stale_future_or_invalid_time_cannot_settle(world, now):
    evidence(world[0])
    # Non-finite caller timestamps are rejected before any persistence.
    if now != now:
        with pytest.raises(ValueError):
            settle(world, now)
    else:
        assert settle(world, now)["status"] == "UNKNOWN"
    assert not world[1].exists()


def test_missing_receipts_and_simulation_are_unknown(world):
    assert settle(world)["status"] == "UNKNOWN"
    heart, body = evidence(world[0])
    body["truth_label"] = "SIMULATED"
    (world[0] / "body_writer_tick.jsonl").write_text(json.dumps(body))
    assert settle(world)["status"] == "UNKNOWN"
    assert not world[1].exists()


def test_concurrent_calls_and_restart_do_not_pay_twice(world):
    evidence(world[0])
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: settle(world), range(4)))
    assert sum(r["status"] == "HEALTHY" for r in results) == 1
    assert settle(world, 1070)["status"] == "ALREADY_SETTLED"
    assert len(world[1].read_text().splitlines()) == 1


@pytest.mark.parametrize("producers", [[None], {"status": "ok"}, ["ok"]])
def test_malformed_producers_do_not_settle(world, producers):
    _, body = evidence(world[0])
    body["producers"] = producers
    (world[0] / "body_writer_tick.jsonl").write_text(json.dumps(body))
    assert settle(world)["status"] == "UNKNOWN"
    assert not world[1].exists()


def test_cadence_and_daily_cap(world, monkeypatch):
    monkeypatch.setattr(health, "REWARD_CAP", health.REWARD)
    evidence(world[0])
    settle(world)
    evidence(world[0], 1030)
    assert settle(world, 1030)["status"] == "THROTTLED"
    evidence(world[0], 1061)
    assert settle(world, 1061)["status"] == "DAILY_CAP"


def test_invalid_signature_does_not_write_or_consume_receipt(world, monkeypatch):
    evidence(world[0])
    with monkeypatch.context() as m:
        m.setattr(crypto_keychain, "sign_block", lambda _: "NO_KEYCHAIN_test")
        assert settle(world)["status"] == "SIGNATURE_UNAVAILABLE"
    assert not world[1].exists()
    assert settle(world)["status"] == "HEALTHY"


def test_signed_health_fields_cannot_be_changed(world):
    evidence(world[0])
    result = settle(world)
    for field, value in (("amount_stgm", 1000), ("status", "FAULT"), ("event_id", "fake")):
        assert not inference_economy._ledger_row_cryptographically_valid({**result, field: value})


def test_crash_after_canonical_append_is_recovered_without_double_count(world, monkeypatch):
    sd, ledger = world
    evidence(sd, status="call_failed")
    real_append = health.append_ledger_line

    def fail_local(path, row):
        if path.name == "heartbeat_economy.jsonl":
            raise OSError("interrupted")
        real_append(path, row)

    with monkeypatch.context() as m:
        m.setattr(health, "append_ledger_line", fail_local)
        with pytest.raises(OSError):
            settle(world)
    assert settle(world)["status"] == "RECOVERED"
    assert len(ledger.read_text().splitlines()) == 2
    snap = stgm_economy.scan_economy(repair_log=ledger, state_dir=sd)
    assert snap.canonical_spent == pytest.approx(health.PENALTY)
    # Seed a valid reward to make kernel's nonnegative/clamped result observable.
    evidence(sd, 1100)
    with monkeypatch.context() as m:
        m.setattr(health, "REWARD", .001)
        settle(world, 1100)
    monkeypatch.setattr(inference_economy, "LOG_PATH", ledger)
    from System.swarm_electricity_metabolism import CANONICAL_OS_BENEFICIARY
    assert inference_economy.ledger_balance(CANONICAL_OS_BENEFICIARY) == pytest.approx(.0009)


@pytest.mark.parametrize("animation_fails", [False, True])
def test_desktop_settles_without_working_dock_animation(world, monkeypatch, animation_fails):
    # Execute the actual callback without booting the GUI and its live workers.
    from System import swarm_hardware_heart
    import time
    source = Path(__file__).resolve().parents[1] / "sifta_os_desktop.py"
    tree = ast.parse(source.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SiftaDesktop")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_tick_heartbeat")
    namespace = {"time": time, "Path": Path, "__file__": str(world[0] / source.name),
                 "_DESKTOP_HARDWARE_HEART_INTERVAL_S": 15, "_DESKTOP_ATP_MINT_INTERVAL_S": 60,
                 "_mark_alice_self_continuity_heartbeat": lambda _: None}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)
    calls = []
    monkeypatch.setattr(swarm_hardware_heart, "pulse_hardware_heart", lambda **kw: calls.append("heart"))
    monkeypatch.setattr(health, "settle_heartbeat", lambda **kw: calls.append("settlement"))

    def broken(*args, **kwargs):
        raise RuntimeError("dock unavailable")

    desktop = SimpleNamespace(_motor_cortex_bounce=broken if animation_fails else None,
                              _last_atp_mint_ts=time.time(), _last_owner_alive_touch=time.time(),
                              _heart_period_s=lambda: 1)
    namespace["_tick_heartbeat"](desktop)
    assert calls == ["heart", "settlement"]
