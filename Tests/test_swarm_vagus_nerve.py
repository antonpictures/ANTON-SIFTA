from __future__ import annotations

import json
import os
import time

from System import swarm_vagus_nerve as vagus


def test_bishop_event32_proof_still_passes():
    assert vagus._selftest_proof_of_property() is True


def test_dry_run_never_kills_rogue_doctor(monkeypatch, tmp_path):
    killed = []
    monkeypatch.setattr(vagus, "_LEDGER", tmp_path / "vagus_nerve.jsonl")
    monkeypatch.setattr(vagus, "_protected_pids", lambda: {})
    monkeypatch.setattr(os, "kill", lambda pid, sig: killed.append((pid, sig)))

    presences = {
        "AG31": vagus.DoctorPresence(
            name="AG31",
            pids=[4242],
            top_cpu_pid=4242,
            top_cpu_value=95.0,
            cpu_pct_total=95.0,
            resident=True,
        )
    }
    stigauth = {"AG31": {"status": "UNAUTHORIZED_MUTATION"}}

    response = vagus.vagal_immune_response(
        presences,
        stigauth,
        mode_override="dry_run",
    )

    assert response["mode"] == "dry_run"
    assert response["proposed_actions"]
    assert response["executed_actions"] == []
    assert killed == []


def test_protected_pid_is_refused_even_in_nuclear(monkeypatch, tmp_path):
    killed = []
    monkeypatch.setattr(vagus, "_LEDGER", tmp_path / "vagus_nerve.jsonl")
    monkeypatch.setattr(vagus, "_protected_pids", lambda: {4242: "protected test pid"})
    monkeypatch.setattr(os, "kill", lambda pid, sig: killed.append((pid, sig)))

    presences = {
        "Codex": vagus.DoctorPresence(
            name="Codex",
            pids=[4242],
            top_cpu_pid=4242,
            top_cpu_value=200.0,
            cpu_pct_total=200.0,
            resident=True,
        )
    }
    stigauth = {"Codex": {"status": "UNAUTHORIZED_MUTATION"}}

    response = vagus.vagal_immune_response(
        presences,
        stigauth,
        mode_override="nuclear",
    )

    assert response["executed_actions"] == []
    assert response["protected_skips"][0]["status"] == "REFUSED_PROTECTED"
    assert killed == []


def test_census_does_not_double_charge_shared_codex_process():
    processes = [
        {
            "pid": 100,
            "ppid": 1,
            "pcpu": 30.0,
            "pmem": 1.2,
            "command": "/Applications/Codex.app/Contents/MacOS/Codex",
        }
    ]

    presences = vagus.census(processes=processes)

    assert presences["Codex"].resident is True
    assert presences["Codex"].cpu_pct_total == 30.0
    assert presences["doctor_codex_ide"].resident is True
    assert presences["doctor_codex_ide"].cpu_pct_total == 0.0


def test_legacy_govern_aliases_are_accepted(monkeypatch):
    monkeypatch.setattr(vagus, "read", lambda: {"ok": True})
    monkeypatch.setattr(
        vagus,
        "vagal_immune_response",
        lambda **_kwargs: {"mode": "dry_run", "surprise": 0.0},
    )

    assert vagus.govern("scan_surgeons")["ok"] is True
    assert vagus.govern("vagal_response")["ok"] is True


def test_thermoregulation_flood_path_survives(tmp_path):
    organ = vagus.SwarmVagusNerve()
    organ.state_dir = tmp_path
    organ.endocrine_ledger = tmp_path / "endocrine_glands.jsonl"
    api_path = tmp_path / "api_metabolism.jsonl"
    now = time.time()
    api_path.write_text(
        "".join(json.dumps({"ts": now - 5, "provider": "test"}) + "\n" for _ in range(40)),
        encoding="utf-8",
    )

    assert organ.monitor_thermoregulation() is True
    rows = [json.loads(line) for line in organ.endocrine_ledger.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["hormone"] == "CORTISOL_NOCICEPTION"
    assert rows[0]["reason"] == "THERMAL_EXHAUSTION"
